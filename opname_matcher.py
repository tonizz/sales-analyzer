"""
Stock Opname Matcher — cocokkan hasil scan dengan stok sistem.
Cara pakai:
  python opname_matcher.py --scan opname_hasil.json --output selisih.xlsx
  python opname_matcher.py --scan opname_hasil.csv --output selisih.xlsx
  python opname_matcher.py --scan opname_hasil.json  # default: opname_selisih.xlsx
"""
from __future__ import annotations

import argparse
import json
import csv
import os
from pathlib import Path

import pandas as pd

SA_PATH = r"D:\scr\stok awal januari 2026.xlsx"
DBU_PATH = r"D:\scr\DBUTHN_55_2026.xlsx"
DBKS_PATH = r"D:\scr\DBKSTHN_55_2026.xlsx"
STOCK_CARD_OUTPUT = r"D:\scr\stock_card_output.xlsx"
SHEET_NAMES = {
    "kartu_stok": "Kartu Stok",
    "stok_per_plu": "Stok per PLU",
    "stok_per_lokasi": "Stok per Lokasi",
}


def load_stock_from_card(path: str = STOCK_CARD_OUTPUT) -> pd.DataFrame:
    """Load stok akhir per PLU dengan menjumlah stok dari bulan terakhir."""
    path_obj = Path(path)
    if not path_obj.exists():
        try:
            from stock_card import StockCard
            sc = StockCard()
            sc.load_data(SA_PATH, DBU_PATH, DBKS_PATH)
            df = sc._build_stok_per_plu() if hasattr(sc, '_build_stok_per_plu') else sc.stok_per_plu()
            return df
        except Exception as e:
            print(f"Error: {e}. Jalankan stock_card.py dulu.")
            raise

    xl = pd.ExcelFile(path)
    # Cari sheet bulan terakhir: Stok Jan, Stok Feb, ... Stok Jun
    months_order = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
    month_sheets = []
    for m in months_order:
        for s in xl.sheet_names:
            if m in s and 'stok' in s.lower():
                month_sheets.append(s)
                break
    if not month_sheets:
        month_sheets = xl.sheet_names[:1]
    last_sheet = month_sheets[-1]

    df = pd.read_excel(path, sheet_name=last_sheet)
    cols_upper = {c.upper().strip(): c for c in df.columns}
    plu_col = cols_upper['PLU']
    stok_col = cols_upper['STOCK']
    nama_col = cols_upper.get('NAMA_BRG')

    # Group by PLU: jumlah stok semua lokasi
    result = df.groupby(plu_col).agg(
        STOK_SISTEM=(stok_col, 'sum'),
        NAMA=(nama_col, 'first') if nama_col else ('PLU', 'first')
    ).reset_index()
    result.rename(columns={plu_col: 'PLU'}, inplace=True)
    result['PLU'] = result['PLU'].astype(str).str.strip()
    result['STOK_SISTEM'] = pd.to_numeric(result['STOK_SISTEM'], errors='coerce').fillna(0).astype(int)
    if nama_col:
        result['NAMA'] = result['NAMA'].fillna('')
    return result


def load_scanned(path: str) -> pd.DataFrame:
    """Load hasil scan (JSON atau CSV)."""
    ext = Path(path).suffix.lower()
    if ext == '.json':
        with open(path) as f:
            raw = json.load(f)
        items = raw.get('items', raw) if isinstance(raw, dict) else raw
        df = pd.DataFrame(items)
    elif ext == '.csv':
        df = pd.read_csv(path)
    else:
        raise ValueError(f"Format tidak didukung: {ext}. Pakai .json atau .csv")

    # Standarisasi kolom
    df.columns = df.columns.str.upper().str.strip()
    plu_col = [c for c in df.columns if 'PLU' in c][0]
    qty_col = [c for c in df.columns if 'STOK' in c or 'QTY' in c or 'FISIK' in c]
    if not qty_col:
        qty_col = [c for c in df.columns if c != plu_col]
    qty_col = qty_col[0]

    result = df[[plu_col, qty_col]].copy()
    result.columns = ['PLU', 'STOK_FISIK']
    result['PLU'] = result['PLU'].astype(str).str.strip()
    result['STOK_FISIK'] = pd.to_numeric(result['STOK_FISIK'], errors='coerce').fillna(0).astype(int)
    return result


def match(scanned: pd.DataFrame, sistem: pd.DataFrame) -> tuple:
    """Cocokkan scanned vs sistem. Return (matched, unscanned)."""
    matched = scanned.merge(sistem, on='PLU', how='left')
    matched['STOK_SISTEM'] = matched['STOK_SISTEM'].fillna(0).astype(int)
    matched['STOK_FISIK'] = matched['STOK_FISIK'].fillna(0).astype(int)
    matched['SELISIH'] = matched['STOK_FISIK'] - matched['STOK_SISTEM']
    matched['STATUS'] = matched['SELISIH'].apply(
        lambda x: 'SESUAI' if x == 0 else ('LEBIH' if x > 0 else 'KURANG'))
    cols = ['PLU', 'NAMA', 'STOK_SISTEM', 'STOK_FISIK', 'SELISIH', 'STATUS']
    avail = [c for c in cols if c in matched.columns]
    matched = matched[avail].sort_values('SELISIH')

    # Item sistem yang belum di-scan
    scanned_plus = set(scanned['PLU'])
    unscanned = sistem[~sistem['PLU'].isin(scanned_plus)].copy()
    unscanned['STOK_FISIK'] = 0
    unscanned['SELISIH'] = 0
    unscanned['STATUS'] = 'BELUM DI-SCAN'
    ucols = [c for c in cols if c in unscanned.columns]
    unscanned = unscanned[ucols].sort_values('STOK_SISTEM', ascending=False)

    return matched, unscanned


def output_excel(matched: pd.DataFrame, unscanned: pd.DataFrame, path: str):
    """Output ke Excel dengan formatting."""
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        # Sheet 1: Semua hasil scan
        matched.to_excel(writer, sheet_name='Hasil Scan', index=False)
        _set_col_width(writer.sheets['Hasil Scan'])

        # Sheet 2: Hanya yang tidak sesuai
        mismatch = matched[matched['STATUS'] != 'SESUAI']
        mismatch.to_excel(writer, sheet_name='Tidak Sesuai', index=False)
        _set_col_width(writer.sheets['Tidak Sesuai'])

        # Sheet 3: Ringkasan
        summary = matched['STATUS'].value_counts().reset_index()
        summary.columns = ['Status', 'Jumlah']
        summary['Pct'] = (summary['Jumlah'] / summary['Jumlah'].sum() * 100).round(1)
        summary.to_excel(writer, sheet_name='Ringkasan', index=False)

        # Sheet 4: Belum di-scan
        unscanned.to_excel(writer, sheet_name='Belum di-Scan', index=False)
        _set_col_width(writer.sheets['Belum di-Scan'])

        n_ok = len(matched[matched['STATUS'] == 'SESUAI'])
        n_mismatch = len(matched[matched['STATUS'] != 'SESUAI'])
        print(f"Output: {path}")
        print(f"  Total di-scan: {len(matched)}")
        print(f"  Sesuai: {n_ok}")
        print(f"  Tidak sesuai: {n_mismatch}")
        print(f"  Belum di-scan: {len(unscanned)}")
        print(f"  Selisih total: {matched['SELISIH'].sum():,}")


def _set_col_width(ws):
    col_w = {'A': 12, 'B': 40, 'C': 14, 'D': 14, 'E': 12, 'F': 16}
    for c, w in col_w.items():
        if c in ws.column_dimensions:
            ws.column_dimensions[c].width = w


def main():
    parser = argparse.ArgumentParser(description='Stock Opname Matcher')
    parser.add_argument('--scan', required=True, help='File hasil scan (JSON/CSV)')
    parser.add_argument('--output', default='opname_selisih.xlsx', help='Output Excel')
    args = parser.parse_args()

    if not Path(args.scan).exists():
        print(f"File tidak ditemukan: {args.scan}")
        return

    print("Loading scanned data...")
    scanned = load_scanned(args.scan)
    print(f"  {len(scanned)} item di-scan")

    print("Loading stock sistem...")
    sistem = load_stock_from_card()
    print(f"  {len(sistem)} PLU di sistem")

    print("Matching...")
    matched, unscanned = match(scanned, sistem)
    output_excel(matched, unscanned, args.output)


if __name__ == '__main__':
    main()
