"""
Stock Card Analyzer v2 — optimasi performa dengan merge-based approach.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_REORDER_MULTIPLIER = 1.5
DEAD_STOCK_MONTHS = 3
MIN_ITEMS_FOR_LOW_STOCK = 5
MONTH_NAMES = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun",
               7: "Jul", 8: "Agu", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des"}

JN_IN = ["EX", "TR"]
JN_OUT = ["KR", "BS", "UP"]


class StockCard:

    def __init__(self, reorder_multiplier: float = DEFAULT_REORDER_MULTIPLIER):
        self.reorder_multiplier = reorder_multiplier
        self.sa: pd.DataFrame | None = None
        self.dbu: pd.DataFrame | None = None
        self.dbks: pd.DataFrame | None = None
        self._months: list[int] = []
        self._master: pd.DataFrame | None = None

    def load_data(self, path_sa: str, path_dbu: str, path_dbks: str,
                  sheet_sa: str | None = None, months: list[int] | None = None):
        self.sa = pd.read_excel(path_sa) if sheet_sa is None else pd.read_excel(path_sa, sheet_name=sheet_sa)
        self.dbu = pd.read_excel(path_dbu)
        self.dbks = pd.read_excel(path_dbks)
        self._standardize()
        self._months = months or self._detect_months()
        if not self._months:
            raise ValueError("Tidak bisa deteksi bulan dari data.")
        self._build_master()
        return self

    def _standardize(self):
        if self.sa is not None:
            self.sa.columns = self.sa.columns.str.lower().str.strip()
        if self.dbu is not None:
            self.dbu.columns = self.dbu.columns.str.upper().str.strip()
            # DBU: TGL format YYYYMMDD int
            tgl_col = "TGL" if "TGL" in self.dbu.columns else None
            if tgl_col:
                self.dbu["_TGL_DT"] = pd.to_datetime(self.dbu[tgl_col].astype(str), format="%Y%m%d", errors="coerce")
                self.dbu["_BULAN"] = self.dbu["_TGL_DT"].dt.month
            if "NAMA_BRG" not in self.dbu.columns and "FNAMA" in self.dbu.columns:
                self.dbu["NAMA_BRG"] = self.dbu["FNAMA"]
        if self.dbks is not None:
            self.dbks.columns = self.dbks.columns.str.upper().str.strip()
            # DBKS: FDATE datetime
            tgl_col = "FDATE" if "FDATE" in self.dbks.columns else ("TGL" if "TGL" in self.dbks.columns else None)
            if tgl_col:
                if self.dbks[tgl_col].dtype == "object":
                    self.dbks["_TGL_DT"] = pd.to_datetime(self.dbks[tgl_col], errors="coerce")
                else:
                    self.dbks["_TGL_DT"] = self.dbks[tgl_col]
                self.dbks["_BULAN"] = self.dbks["_TGL_DT"].dt.month
            if "FLOCCD" not in self.dbks.columns and "LOKASI" in self.dbks.columns:
                self.dbks["FLOCCD"] = self.dbks["LOKASI"]

    def _detect_months(self) -> list[int]:
        if self.dbu is not None and "_BULAN" in self.dbu.columns:
            return sorted(self.dbu["_BULAN"].dropna().unique().astype(int).tolist())
        return []

    def _get_map(self, df: pd.DataFrame, k_cols: list[str], v_col: str) -> dict:
        """Build dict mapping tuple->value for fast lookup."""
        d = {}
        for _, r in df.iterrows():
            key = tuple(r[c] for c in k_cols)
            val = r[v_col]
            if pd.notna(val):
                d[key] = val
        return d

    def _build_master(self):
        months = self._months
        sa = self.sa
        dbu = self.dbu
        dbks = self.dbks

        # Build dicts
        stok_awal_map = {}
        lokasi_map = {}
        nama_brg_map = {}
        if "plu" in sa.columns and "lokasi" in sa.columns:
            for _, r in sa.iterrows():
                k = (r["plu"], r["lokasi"])
                stok_awal_map[k] = r.get("qt_awal", 0)
                if "namalokasi" in sa.columns:
                    lokasi_map[r["lokasi"]] = r.get("namalokasi", "")
                if "nama_brg" in sa.columns:
                    nama_brg_map[r["plu"]] = r.get("nama_brg", "")

        # Build nama_brg from DBU/DBKS fallback
        if "PLU" in dbu.columns:
            for _, r in dbu.iterrows():
                v = r.get("NAMA_BRG")
                if pd.notna(v):
                    nama_brg_map.setdefault(r["PLU"], v)
        if "PLU" in dbks.columns:
            for _, r in dbks.iterrows():
                v = r.get("NAMA_BRG")
                if pd.notna(v):
                    nama_brg_map.setdefault(r["PLU"], v)
        if "LOKASI" in dbu.columns:
            # Use first few rows for nama lokasi from stok awal
            pass

        # --- Aggregate DBU IN/OUT ---
        dbu_agg = pd.DataFrame()
        if "JN" in dbu.columns and len(dbu) > 0:
            dbu["_ARAH"] = dbu["JN"].map(lambda j: "IN" if j in JN_IN else ("OUT" if j in JN_OUT else None))
            dbu_focus = dbu[dbu["_ARAH"].notna()].copy()
            if len(dbu_focus) > 0:
                dbu_agg = dbu_focus.groupby(["PLU", "LOKASI", "_BULAN", "JN"])["QTY"].sum().reset_index()
                dbu_agg.rename(columns={"_BULAN": "BULAN"}, inplace=True)

        # --- Aggregate DBKS ---
        dbks_agg = pd.DataFrame()
        if "_BULAN" in dbks.columns and "QTY" in dbks.columns and "FLOCCD" in dbks.columns and len(dbks) > 0:
            dbks_agg = dbks.groupby(["PLU", "FLOCCD", "_BULAN"])["QTY"].sum().reset_index()
            dbks_agg.rename(columns={"FLOCCD": "LOKASI", "_BULAN": "BULAN"}, inplace=True)

        # --- Collect unique (PLU, LOKASI) ---
        pairs = set(stok_awal_map.keys())
        if len(dbu_agg) > 0:
            for _, r in dbu_agg.iterrows():
                pairs.add((r["PLU"], r["LOKASI"]))
        if len(dbks_agg) > 0:
            for _, r in dbks_agg.iterrows():
                pairs.add((r["PLU"], r["LOKASI"]))

        # --- Build per-bulan with carry-forward ---
        # Pre-index aggregated data for fast lookup
        ex_idx = {}
        tr_idx = {}
        out_idx = {"KR": {}, "BS": {}, "UP": {}}
        terjual_idx = {}

        if len(dbu_agg) > 0:
            for _, r in dbu_agg.iterrows():
                k = (r["PLU"], r["LOKASI"], r["BULAN"])
                if r["JN"] == "EX":
                    ex_idx[k] = ex_idx.get(k, 0) + r["QTY"]
                elif r["JN"] == "TR":
                    tr_idx[k] = tr_idx.get(k, 0) + r["QTY"]
                elif r["JN"] == "KR":
                    out_idx["KR"][k] = out_idx["KR"].get(k, 0) + r["QTY"]
                elif r["JN"] == "BS":
                    out_idx["BS"][k] = out_idx["BS"].get(k, 0) + r["QTY"]
                elif r["JN"] == "UP":
                    out_idx["UP"][k] = out_idx["UP"].get(k, 0) + r["QTY"]

        if len(dbks_agg) > 0:
            for _, r in dbks_agg.iterrows():
                k = (r["PLU"], r["LOKASI"], r["BULAN"])
                terjual_idx[k] = terjual_idx.get(k, 0) + r["QTY"]

        rows = []
        for (plu, lokasi) in pairs:
            sa_val = stok_awal_map.get((plu, lokasi), 0)
            nama = nama_brg_map.get(plu, "")
            nama_lok = lokasi_map.get(lokasi, "")
            for bulan in months:
                k = (plu, lokasi, bulan)
                ex = int(ex_idx.get(k, 0))
                tr = int(tr_idx.get(k, 0))
                kr = int(out_idx["KR"].get(k, 0))
                bs = int(out_idx["BS"].get(k, 0))
                up = int(out_idx["UP"].get(k, 0))
                terjual = int(terjual_idx.get(k, 0))
                masuk = ex + tr
                stok_akhir = sa_val + masuk - kr - bs - up - terjual
                rows.append({
                    "PLU": plu,
                    "NAMA_BRG": nama,
                    "LOKASI": lokasi,
                    "NAMA_LOKASI": nama_lok,
                    "BULAN": bulan,
                    "BULAN_NAMA": MONTH_NAMES.get(bulan, bulan),
                    "STOK_AWAL": sa_val,
                    "EX": ex,
                    "TR": tr,
                    "MASUK": masuk,
                    "KELUAR_KR": kr,
                    "RUSAK_BS": bs,
                    "PAKAI_UP": up,
                    "TERJUAL": terjual,
                    "STOK_AKHIR": int(stok_akhir),
                    "STATUS": self._classify_stock(stok_akhir),
                })
                sa_val = stok_akhir

        self._master = pd.DataFrame(rows)
        self._master["YEAR"] = self._detect_year()

    def _detect_year(self) -> int:
        if self.dbu is not None and "_TGL_DT" in self.dbu.columns:
            yr = self.dbu["_TGL_DT"].dt.year.dropna()
            if len(yr) > 0:
                return int(yr.mode().iloc[0])
        return 2026

    @staticmethod
    def _classify_stock(val: int) -> str:
        if val < 0:
            return "NEGATIF"
        elif val == 0:
            return "HABIS"
        elif val <= 2:
            return "KRITIS"
        elif val <= 5:
            return "MENIPIS"
        else:
            return "NORMAL"

    def get_stock_card(self) -> pd.DataFrame:
        if self._master is None:
            raise ValueError("Belum load_data().")
        cols = ["PLU", "NAMA_BRG", "LOKASI", "NAMA_LOKASI",
                "YEAR", "BULAN", "BULAN_NAMA",
                "STOK_AWAL", "EX", "TR", "MASUK",
                "KELUAR_KR", "RUSAK_BS", "PAKAI_UP",
                "TERJUAL", "STOK_AKHIR", "STATUS"]
        return self._master[cols].sort_values(["LOKASI", "PLU", "BULAN"]).reset_index(drop=True)

    def summarize_by_plu(self) -> pd.DataFrame:
        m = self._master
        grp = m.groupby(["PLU", "NAMA_BRG"])
        res = grp.agg(
            STOK_AKHIR_TERAKHIR=("STOK_AKHIR", "last"),
            TOTAL_MASUK=("MASUK", "sum"),
            TOTAL_KELUAR=("KELUAR_KR", "sum"),
            TOTAL_RUSAK=("RUSAK_BS", "sum"),
            TOTAL_PAKAI=("PAKAI_UP", "sum"),
            TOTAL_TERJUAL=("TERJUAL", "sum"),
            BULAN_TERAKHIR=("BULAN_NAMA", "last"),
            RATA2_TERJUAL=("TERJUAL", "mean"),
            LOKASI_DI=("LOKASI", "nunique"),
        ).reset_index()
        res["RATA2_TERJUAL"] = res["RATA2_TERJUAL"].round(1)
        res["STATUS"] = res["STOK_AKHIR_TERAKHIR"].apply(self._classify_stock)
        return res.sort_values("STOK_AKHIR_TERAKHIR", ascending=True).reset_index(drop=True)

    def summarize_by_lokasi(self) -> pd.DataFrame:
        m = self._master
        grp = m.groupby(["LOKASI", "NAMA_LOKASI"])
        res = grp.agg(
            TOTAL_PLU=("PLU", "nunique"),
            STOK_AKHIR=("STOK_AKHIR", "sum"),
            TOTAL_MASUK=("MASUK", "sum"),
            TOTAL_KELUAR=("KELUAR_KR", "sum"),
            TOTAL_RUSAK=("RUSAK_BS", "sum"),
            TOTAL_PAKAI=("PAKAI_UP", "sum"),
            TOTAL_TERJUAL=("TERJUAL", "sum"),
            PLU_NEGATIF=("STOK_AKHIR", lambda x: (x < 0).sum()),
            PLU_MENIPIS=("STOK_AKHIR", lambda x: ((x > 0) & (x <= 5)).sum()),
        ).reset_index()
        return res.sort_values("STOK_AKHIR", ascending=False).reset_index(drop=True)

    def format_stok(self, month: int | None = None) -> pd.DataFrame:
        """
        Output dalam format seperti format_stok.txt:
          LOKASI | NAMALOK | PLU (0-padded) | NAMA_BRG | Stock Awal | TR | KR | UP | BS | sales | Stock

        Hanya menampilkan (PLU, LOKASI) yang benar-benar aktif di bulan tersebut
        (punya stok atau pernah ada transaksi). Jika month=None, ambil bulan terakhir.
        """
        if self._master is None:
            raise ValueError("Belum load_data().")
        if month is None:
            month = self._months[-1]
        df = self._master[self._master["BULAN"] == month].copy()
        if len(df) == 0:
            return pd.DataFrame()
        # Filter: hanya (PLU, LOKASI) yang punya stok atau ada transaksi di bulan ini
        activity = (df["STOK_AWAL"] != 0) | (df["EX"] != 0) | (df["TR"] != 0) | \
                   (df["KELUAR_KR"] != 0) | (df["RUSAK_BS"] != 0) | (df["PAKAI_UP"] != 0) | \
                   (df["TERJUAL"] != 0) | (df["STOK_AKHIR"] != 0)
        df = df[activity].copy()
        result = df.copy()
        result["PLU"] = result["PLU"].astype(int).apply(lambda x: f"{x:07d}")
        result = result.rename(columns={
            "NAMA_LOKASI": "NAMALOK",
            "STOK_AWAL": "Stock Awal",
            "TR": "TR",
            "KELUAR_KR": "KR",
            "PAKAI_UP": "UP",
            "RUSAK_BS": "BS",
            "TERJUAL": "sales",
            "STOK_AKHIR": "Stock",
        })
        cols_out = ["LOKASI", "NAMALOK", "PLU", "NAMA_BRG",
                     "Stock Awal", "TR", "KR", "UP", "BS", "sales", "Stock"]
        return result[cols_out].sort_values(["LOKASI", "PLU"]).reset_index(drop=True)

    def format_stok_all(self) -> dict[int, pd.DataFrame]:
        """Return dict {bulan: DataFrame} for all months."""
        return {b: self.format_stok(b) for b in self._months}

    def negative_stock(self) -> pd.DataFrame:
        df = self._master[self._master["STOK_AKHIR"] < 0].copy()
        if len(df) > 0:
            df = df.sort_values(["LOKASI", "PLU", "BULAN"]).reset_index(drop=True)
        return df

    def low_stock(self, threshold: int | None = None) -> pd.DataFrame:
        t = threshold or MIN_ITEMS_FOR_LOW_STOCK
        df = self._master[(self._master["STOK_AKHIR"] >= 0) & (self._master["STOK_AKHIR"] <= t)].copy()
        if len(df) > 0:
            df = df.sort_values(["STOK_AKHIR", "LOKASI", "PLU", "BULAN"]).reset_index(drop=True)
        return df

    def dead_stock(self, min_months: int | None = None) -> pd.DataFrame:
        months = min_months or DEAD_STOCK_MONTHS
        m = self._master.copy()
        hasil = []
        for (plu, lokasi), grp in m.groupby(["PLU", "LOKASI"]):
            grp = grp.sort_values("BULAN")
            stok_akhir = grp["STOK_AKHIR"].iloc[-1]
            if stok_akhir <= 0:
                continue
            last_n = grp.tail(months)
            if last_n["TERJUAL"].sum() == 0:
                hasil.append(grp.iloc[-1].to_dict())
        if not hasil:
            return pd.DataFrame()
        return pd.DataFrame(hasil).sort_values(["LOKASI", "PLU"]).reset_index(drop=True)

    def stock_trend(self) -> pd.DataFrame:
        grp = self._master.groupby(["YEAR", "BULAN", "BULAN_NAMA"])
        res = grp.agg(
            TOTAL_PLU=("PLU", "nunique"),
            TOTAL_LOKASI=("LOKASI", "nunique"),
            STOK_AWAL=("STOK_AWAL", "sum"),
            MASUK=("MASUK", "sum"),
            KELUAR_KR=("KELUAR_KR", "sum"),
            RUSAK_BS=("RUSAK_BS", "sum"),
            PAKAI_UP=("PAKAI_UP", "sum"),
            TERJUAL=("TERJUAL", "sum"),
            STOK_AKHIR=("STOK_AKHIR", "sum"),
            PLU_NEGATIF=("STOK_AKHIR", lambda x: (x < 0).sum()),
        ).reset_index()
        return res.sort_values(["YEAR", "BULAN"]).reset_index(drop=True)

    def stats(self) -> dict:
        m = self._master
        return {
            "Bulan": len(self._months),
            "PLU Unik": int(m["PLU"].nunique()),
            "LOKASI Unik": int(m["LOKASI"].nunique()),
            "Total Baris": len(m),
            "Total Stok Akhir": int(m["STOK_AKHIR"].sum()),
            "Total Terjual": int(m["TERJUAL"].sum()),
            "Total Masuk": int(m["MASUK"].sum()),
            "Total Rusak": int(m["RUSAK_BS"].sum()),
            "PLU Stok Negatif": int(m.loc[m["STOK_AKHIR"] < 0, "PLU"].nunique()),
            "PLU Stok Habis": int(m.loc[m["STOK_AKHIR"] == 0, "PLU"].nunique()),
            "PLU Menipis (≤5)": int(m.loc[(m["STOK_AKHIR"] > 0) & (m["STOK_AKHIR"] <= 5), "PLU"].nunique()),
        }

    def export_excel(self, path: str):
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            # Satu sheet per bulan dalam format stok
            for bulan in self._months:
                bln = MONTH_NAMES.get(bulan, str(bulan))
                fs = self.format_stok(bulan)
                if len(fs) > 0:
                    fs.to_excel(writer, sheet_name=f"Stok {bln}", index=False)
            self.get_stock_card().to_excel(writer, sheet_name="Kartu Stok Detail", index=False)
            self.summarize_by_plu().to_excel(writer, sheet_name="Ringkasan per PLU", index=False)
            self.summarize_by_lokasi().to_excel(writer, sheet_name="Ringkasan per Lokasi", index=False)
            self.stock_trend().to_excel(writer, sheet_name="Trend Bulanan", index=False)
            ns = self.negative_stock()
            if len(ns) > 0:
                ns.to_excel(writer, sheet_name="Stok Negatif", index=False)
            ls = self.low_stock()
            if len(ls) > 0:
                ls.to_excel(writer, sheet_name="Stok Menipis", index=False)
            ds = self.dead_stock()
            if len(ds) > 0:
                ds.to_excel(writer, sheet_name="Dead Stock", index=False)
            st = pd.DataFrame([self.stats()]).T.reset_index()
            st.columns = ["Metrik", "Nilai"]
            st.to_excel(writer, sheet_name="Statistik", index=False)

    @staticmethod
    def cli():
        parser = argparse.ArgumentParser(description="Stock Card Analyzer")
        parser.add_argument("--sa", required=True, help="File stok awal (.xlsx)")
        parser.add_argument("--dbu", required=True, help="File DBU mutasi (.xlsx)")
        parser.add_argument("--dbks", required=True, help="File DBKS penjualan (.xlsx)")
        parser.add_argument("-o", "--output", default="stock_card_output.xlsx", help="Output Excel")
        args = parser.parse_args()

        sc = StockCard()
        print("Memuat data...")
        sc.load_data(args.sa, args.dbu, args.dbks)
        print(f"  Bulan: {sc._months}")
        print(f"  PLU: {sc._master['PLU'].nunique()}")
        print(f"  LOKASI: {sc._master['LOKASI'].nunique()}")
        print(f"  Baris: {len(sc._master)}")
        sc.export_excel(args.output)
        print(f"  Ekspor: {args.output}")
        print(f"  Stok Akhir: {int(sc._master['STOK_AKHIR'].sum()):,}")
        print(f"  Terjual: {int(sc._master['TERJUAL'].sum()):,}")
        print(f"  Baris Negatif: {len(sc.negative_stock())}")
        print(f"  Baris Menipis: {len(sc.low_stock())}")
        print(f"  Dead Stock: {len(sc.dead_stock())}")


if __name__ == "__main__":
    StockCard.cli()
