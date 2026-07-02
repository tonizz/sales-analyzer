"""
Generate barcode_map.json + nama_map.json untuk Stock Opname Scanner.
Run: python gen_maps.py
"""
import json
import pandas as pd
from pathlib import Path

BC_PATH = r"D:\scr\barcodexls.xlsx"
SA_PATH = r"D:\scr\stok awal januari 2026.xlsx"
DBKS_PATH = r"D:\scr\DBKSTHN_55_2026.xlsx"
OUT_DIR = Path(r"D:\scr")
DOCS_DIR = OUT_DIR / "docs"

def build_nama_map() -> dict:
    nama = {}
    sa = pd.read_excel(SA_PATH)
    for _, r in sa.iterrows():
        nama[str(int(r['plu']))] = str(r['nama_brg']).strip()
    dbks = pd.read_excel(DBKS_PATH)
    for _, r in dbks.iterrows():
        plu = str(r['PLU'])
        if plu not in nama:
            nama[plu] = str(r['NAMA_BRG']).strip()
    return nama

def build_barcode_map() -> dict:
    """BARCODE -> PLU_INTERNAL (string). Jika 1 barcode ke banyak PLU, simpan sebagai PLU_FIRST."""
    bc = pd.read_excel(BC_PATH)
    bc = bc.dropna(subset=['PLU', 'BARCODE'])
    bc['PLU'] = bc['PLU'].astype(int).astype(str)
    bc['BARCODE'] = bc['BARCODE'].astype(str).str.strip()
    # Hapus duplikat barcode -> PLU (ambil pertama)
    bc = bc.drop_duplicates(subset=['BARCODE'])
    return dict(zip(bc['BARCODE'], bc['PLU']))

def build_multi_barcode_map() -> dict:
    """BARCODE -> list[PLU] untuk barcode yang punya >1 PLU."""
    bc = pd.read_excel(BC_PATH)
    bc = bc.dropna(subset=['PLU', 'BARCODE'])
    bc['PLU'] = bc['PLU'].astype(int).astype(str)
    bc['BARCODE'] = bc['BARCODE'].astype(str).str.strip()
    # Cari barcode dengan multiple PLU
    dups = bc.groupby('BARCODE')['PLU'].apply(list)
    dups = dups[dups.apply(len) > 1]
    return dups.to_dict()

def save_json(data, filename):
    """Simpan ke root (gitignored) dan docs/ (untuk GitHub Pages)."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for d in [OUT_DIR, DOCS_DIR]:
        with open(d / filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"  -> {d.name}/{filename}")

if __name__ == '__main__':
    print("Building nama map...")
    nama_map = build_nama_map()
    save_json(nama_map, "nama_map.json")
    print(f"  {len(nama_map)} PLU mapped to names")

    print("Building barcode map (single PLU)...")
    bc_map = build_barcode_map()
    save_json(bc_map, "barcode_map.json")
    print(f"  {len(bc_map)} barcodes mapped")

    print("Building multi-barcode map...")
    multi_map = build_multi_barcode_map()
    save_json(multi_map, "barcode_multi.json")
    print(f"  {len(multi_map)} barcodes with multiple PLU")

    print("\nDone! Maps generated.")
