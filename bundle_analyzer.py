"""
Bundle Sales Analyzer
=====================
Mendeteksi & menganalisa penjualan paket/bundle.

Kriteria BUNDLE (sesuai requirement):
  - 1 NOTRAN memiliki >= MIN_ITEMS item
  - Semua item di NOTRAN tersebut punya nilai DISCOUNT (%) yang sama

Output dikelompokkan per FLOCCD (lokasi).

Cara pakai:
  - GUI (default) : python bundle_analyzer.py
  - CLI           : python bundle_analyzer.py --cli FILE.xlsx --out hasil.xlsx
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# Kolom wajib yang harus ada di file input
REQUIRED_COLS = [
    "FLOCCD", "FDATE", "NOTRAN", "NOM", "PLU", "NAMA_BRG",
    "QTY", "DISCOUNT", "JUALAHIR", "JUMLAH", "PRAMUNIAGA", "KASIR",
]


class BundleAnalyzer:
    def __init__(self):
        self.df: pd.DataFrame | None = None
        self.filepath: str | None = None

    # ---------- LOAD ----------
    def load(self, filepath: str) -> pd.DataFrame:
        self.filepath = filepath
        self.df = pd.read_excel(filepath)
        missing = [c for c in REQUIRED_COLS if c not in self.df.columns]
        if missing:
            raise ValueError(f"Kolom wajib tidak ada di file: {missing}")
        if "FDATE" in self.df.columns:
            self.df["FDATE"] = pd.to_datetime(self.df["FDATE"])
        return self.df

    # ---------- CLASSIFY ----------
    def classify(self, min_items: int = 2, min_discount: float = 0.0,
                 disc_tolerance: float = 1.0) -> pd.DataFrame:
        """
        Klasifikasi bundle.

        Args:
            min_items: Minimal item per NOTRAN untuk dianggap bundle.
            min_discount: Minimal diskon (%).
            disc_tolerance: Toleransi selisih DISCOUNT (%) antar item dalam satu NOTRAN.
                           Default 1.0 artinya beda ≤1% masih dianggap bundle.
        """
        if self.df is None:
            raise ValueError("Data belum dimuat. Panggil load() dulu.")
        grp = self.df.groupby(["FLOCCD", "NOTRAN"])
        n_items = grp["NOM"].transform("count")
        disc_min = grp["DISCOUNT"].transform("min")
        disc_max = grp["DISCOUNT"].transform("max")
        same_disc = (disc_max - disc_min) <= disc_tolerance
        self.df["BUNDLE_DISC_PCT"] = grp["DISCOUNT"].transform("first").round(2)
        self.df["IS_BUNDLE"] = (
            (n_items >= min_items)
            & same_disc
            & (self.df["BUNDLE_DISC_PCT"] >= min_discount)
        )
        # revenue per baris
        self.df["LINE_REVENUE"] = self.df["JUMLAH"]
        return self.df

    # ---------- SUMMARIES ----------
    def summary_by_location(self) -> pd.DataFrame:
        b = self.df[self.df["IS_BUNDLE"]]
        all_tx = self.df.groupby("FLOCCD")["NOTRAN"].nunique().rename("TOTAL_TX")
        b_tx = b.groupby("FLOCCD")["NOTRAN"].nunique().rename("BUNDLE_TX")
        b_rev = b.groupby("FLOCCD")["LINE_REVENUE"].sum().rename("BUNDLE_REVENUE")
        b_qty = b.groupby("FLOCCD")["QTY"].sum().rename("BUNDLE_QTY")
        b_size = (
            b.groupby(["FLOCCD", "NOTRAN"])
            .size()
            .groupby("FLOCCD")
            .mean()
            .rename("AVG_ITEMS_PER_BUNDLE")
        )
        b_disc = (
            b.groupby("FLOCCD")["BUNDLE_DISC_PCT"]
            .agg(["mean", "min", "max"])
            .round(2)
        )
        b_disc.columns = [
            "AVG_BUNDLE_DISC_PCT",
            "MIN_BUNDLE_DISC_PCT",
            "MAX_BUNDLE_DISC_PCT",
        ]
        sm = pd.concat([all_tx, b_tx, b_disc, b_rev, b_qty, b_size], axis=1).fillna(0)
        sm["BUNDLE_TX_PCT"] = (sm["BUNDLE_TX"] / sm["TOTAL_TX"] * 100).round(2)
        sm = sm.reset_index()
        # ambil nama lokasi (FNAMA) kalau ada, biar mudah dibaca
        if "FNAMA" in self.df.columns:
            nama = (
                self.df.groupby("FLOCCD")["FNAMA"].first().reset_index()
            )
            sm = sm.merge(nama, on="FLOCCD", how="left")
            cols = [
                "FLOCCD", "FNAMA", "TOTAL_TX", "BUNDLE_TX", "BUNDLE_TX_PCT",
                "AVG_BUNDLE_DISC_PCT", "MIN_BUNDLE_DISC_PCT", "MAX_BUNDLE_DISC_PCT",
                "BUNDLE_REVENUE", "BUNDLE_QTY", "AVG_ITEMS_PER_BUNDLE",
            ]
        else:
            cols = [
                "FLOCCD", "TOTAL_TX", "BUNDLE_TX", "BUNDLE_TX_PCT",
                "AVG_BUNDLE_DISC_PCT", "MIN_BUNDLE_DISC_PCT", "MAX_BUNDLE_DISC_PCT",
                "BUNDLE_REVENUE", "BUNDLE_QTY", "AVG_ITEMS_PER_BUNDLE",
            ]
        return sm[cols].sort_values("BUNDLE_REVENUE", ascending=False)

    def discount_distribution(self) -> pd.DataFrame:
        b = self.df[self.df["IS_BUNDLE"]]
        return (
            b.groupby(["FLOCCD", "BUNDLE_DISC_PCT"])
            .agg(
                JUMLAH_TX=("NOTRAN", "nunique"),
                TOTAL_QTY=("QTY", "sum"),
                TOTAL_REVENUE=("LINE_REVENUE", "sum"),
            )
            .reset_index()
            .sort_values(["FLOCCD", "BUNDLE_DISC_PCT"])
        )

    def bundle_detail(self) -> pd.DataFrame:
        b = self.df[self.df["IS_BUNDLE"]].copy()
        cols = [
            "FLOCCD", "FDATE", "NOTRAN", "PRAMUNIAGA", "KASIR",
            "BUNDLE_DISC_PCT", "NOM", "PLU", "NAMA_BRG", "QTY",
            "DISCOUNT", "JUALAHIR", "JUMLAH", "LINE_REVENUE",
        ]
        return b[cols].sort_values(["FLOCCD", "FDATE", "NOTRAN", "NOM"])

    def top_bundles(self, top_n: int = 20) -> pd.DataFrame:
        b = self.df[self.df["IS_BUNDLE"]]
        grp = b.groupby(["FLOCCD", "NOTRAN", "BUNDLE_DISC_PCT"])
        combo = (
            grp.apply(lambda g: " + ".join(sorted(g["NAMA_BRG"].astype(str).tolist())))
            .reset_index(name="KOMBINASI_ITEM")
        )
        rev = grp["LINE_REVENUE"].sum().reset_index(name="BUNDLE_REVENUE")
        qty = grp["QTY"].sum().reset_index(name="BUNDLE_QTY")
        merged = combo.merge(rev, on=["FLOCCD", "NOTRAN", "BUNDLE_DISC_PCT"]).merge(
            qty, on=["FLOCCD", "NOTRAN", "BUNDLE_DISC_PCT"]
        )
        top = (
            merged.groupby(["FLOCCD", "BUNDLE_DISC_PCT", "KOMBINASI_ITEM"])
            .agg(
                JUMLAH_TX=("NOTRAN", "count"),
                TOTAL_REVENUE=("BUNDLE_REVENUE", "sum"),
                TOTAL_QTY=("BUNDLE_QTY", "sum"),
            )
            .reset_index()
            .sort_values(["FLOCCD", "JUMLAH_TX"], ascending=[True, False])
        )
        return top.groupby("FLOCCD").head(top_n).reset_index(drop=True)

    def non_bundle_summary(self) -> pd.DataFrame:
        nb = self.df[~self.df["IS_BUNDLE"]]
        return (
            nb.groupby("FLOCCD")
            .agg(
                NON_BUNDLE_TX=("NOTRAN", "nunique"),
                NON_BUNDLE_REVENUE=("LINE_REVENUE", "sum"),
            )
            .reset_index()
        )

    # ---------- PENCARIAN PAKET BY ITEM ----------
    def search_bundles_by_item(
        self,
        item_query: str,
        floocd: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ):
        """
        Cari paket/bundle yang di dalamnya ada item dengan PLU atau NAMA_BRG
        mengandung `item_query` (case-insensitive substring).
        Hanya transaksi bundle yang memenuhi kriteria.

        Parameter:
          item_query : kata kunci (mis. "64428" atau "DURABEAM")
          floocd     : kode lokasi (None/'' = semua lokasi)
          date_from  : tanggal mulai (str, YYYY-MM-DD) - None = tanpa batas
          date_to    : tanggal akhir (str, YYYY-MM-DD) - None = tanpa batas

        Return:
          summary : dict {Jumlah Paket, Total Nilai (Rp), Total QTY, Rata-rata Diskon (%)}
          packages: DataFrame per paket (1 baris = 1 paket)
                    kolom: FLOCCD, NOTRAN, FDATE, BUNDLE_DISC_PCT, N_ITEM,
                           TOTAL_QTY, TOTAL_JUMLAH, DAFTAR_ITEM, KASIR, PRAMUNIAGA
        """
        if self.df is None:
            raise ValueError("Data belum dimuat")
        q = str(item_query).strip()
        if not q:
            raise ValueError("Kata kunci item wajib diisi")

        df = self.df[self.df["IS_BUNDLE"]].copy()

        if floocd and str(floocd).strip():
            df = df[df["FLOCCD"].astype(str) == str(floocd).strip()]

        if date_from:
            d1 = pd.to_datetime(date_from)
            df = df[df["FDATE"] >= d1]
        if date_to:
            d2 = pd.to_datetime(date_to) + pd.Timedelta(hours=23, minutes=59, seconds=59)
            df = df[df["FDATE"] <= d2]

        # Cari NOTRAN yang punya baris dengan PLU/NAMA_BRG match
        mask = (
            df["PLU"].astype(str).str.contains(q, case=False, na=False)
            | df["NAMA_BRG"].astype(str).str.contains(q, case=False, na=False)
        )
        matched_notrans = df.loc[mask, "NOTRAN"].unique()
        df_pkg = df[df["NOTRAN"].isin(matched_notrans)].copy()

        empty_cols = [
            "FLOCCD", "NOTRAN", "FDATE", "BUNDLE_DISC_PCT", "N_ITEM",
            "TOTAL_QTY", "TOTAL_JUMLAH", "DAFTAR_ITEM", "KASIR", "PRAMUNIAGA",
        ]
        if df_pkg.empty:
            return (
                {
                    "Jumlah Paket": 0,
                    "Total Nilai (Rp)": 0.0,
                    "Total QTY": 0,
                    "Rata-rata Diskon (%)": 0.0,
                    "Periode Dari": date_from or "-",
                    "Periode Sampai": date_to or "-",
                    "Lokasi": floocd or "(semua)",
                    "Kata Kunci": q,
                },
                pd.DataFrame(columns=empty_cols),
            )

        # Group per paket: (NOTRAN, BUNDLE_DISC_PCT) ⇒ 1 paket
        grp = df_pkg.groupby(
            ["FLOCCD", "NOTRAN", "FDATE", "BUNDLE_DISC_PCT"], as_index=False
        )
        packages = grp.agg(
            N_ITEM=("NOM", "count"),
            TOTAL_QTY=("QTY", "sum"),
            TOTAL_JUMLAH=("JUMLAH", "sum"),
            KASIR=("KASIR", "first"),
            PRAMUNIAGA=("PRAMUNIAGA", "first"),
        )

        # Daftar item per paket
        items = (
            df_pkg.sort_values("NOM")
            .groupby("NOTRAN")["NAMA_BRG"]
            .apply(lambda x: " | ".join(x.tolist()))
            .reset_index(name="DAFTAR_ITEM")
        )
        packages = packages.merge(items, on="NOTRAN", how="left")
        packages = packages.sort_values(["FDATE", "NOTRAN"]).reset_index(drop=True)
        packages = packages[empty_cols]

        summary = {
            "Jumlah Paket": int(len(packages)),
            "Total Nilai (Rp)": float(packages["TOTAL_JUMLAH"].sum()),
            "Total QTY": int(packages["TOTAL_QTY"].sum()),
            "Rata-rata Diskon (%)": round(float(packages["BUNDLE_DISC_PCT"].mean()), 2),
            "Periode Dari": date_from or "-",
            "Periode Sampai": date_to or "-",
            "Lokasi": floocd or "(semua lokasi)",
            "Kata Kunci": q,
        }
        return summary, packages

    # ===== DATE PRESETS & PERIOD COMPARISON =====
    @staticmethod
    def calc_date_presets(ref_date):
        """Hitung date range preset relatif ke ref_date."""
        ref = pd.to_datetime(ref_date)
        p = {}
        p["Semua data"] = (None, None)
        p["7 hari terakhir"] = (ref - pd.Timedelta(days=6), ref)
        p["14 hari terakhir"] = (ref - pd.Timedelta(days=13), ref)
        p["30 hari terakhir"] = (ref - pd.Timedelta(days=29), ref)
        p["90 hari terakhir"] = (ref - pd.Timedelta(days=89), ref)
        last_month_end = ref.replace(day=1) - pd.Timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        p["Bulan lalu"] = (last_month_start, last_month_end)
        p["Bulan ini"] = (ref.replace(day=1), ref)
        p["3 bulan terakhir"] = (
            (ref - pd.DateOffset(months=2)).replace(day=1), ref,
        )
        p["6 bulan terakhir"] = (
            (ref - pd.DateOffset(months=5)).replace(day=1), ref,
        )
        p["Tahun ini (YTD)"] = (ref.replace(month=1, day=1), ref)
        return p

    @staticmethod
    def calc_comparison_presets(ref_date):
        """Preset untuk tab Perbandingan: tiap item = (P1_start, P1_end, P2_start, P2_end, label)."""
        ref = pd.to_datetime(ref_date)
        p = {}
        # Custom → user isi manual
        p["Custom (isi manual)"] = (None, None, None, None)
        # Bulan ini vs Bulan lalu
        last_month_end = ref.replace(day=1) - pd.Timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        p["Bulan ini vs Bulan lalu"] = (
            ref.replace(day=1), ref, last_month_start, last_month_end,
        )
        # 30 hari vs 30 hari sebelumnya
        p["30 hari terakhir vs 30 hari sebelumnya"] = (
            ref - pd.Timedelta(days=29), ref,
            ref - pd.Timedelta(days=59), ref - pd.Timedelta(days=30),
        )
        # 7 hari vs 7 hari sebelumnya
        p["7 hari terakhir vs 7 hari sebelumnya"] = (
            ref - pd.Timedelta(days=6), ref,
            ref - pd.Timedelta(days=13), ref - pd.Timedelta(days=7),
        )
        # 14 hari vs 14 hari sebelumnya
        p["14 hari terakhir vs 14 hari sebelumnya"] = (
            ref - pd.Timedelta(days=13), ref,
            ref - pd.Timedelta(days=27), ref - pd.Timedelta(days=14),
        )
        # Quarter ini vs Quarter lalu
        cur_q_start = ref - pd.DateOffset(months=(ref.month - 1) % 3)
        cur_q_start = cur_q_start.replace(day=1)
        prev_q_end = cur_q_start - pd.Timedelta(days=1)
        prev_q_start = prev_q_end.replace(day=1) - pd.DateOffset(months=2)
        prev_q_start = prev_q_start.replace(day=1)
        p["Quarter ini vs Quarter lalu"] = (
            cur_q_start, ref, prev_q_start, prev_q_end,
        )
        return p

    def filter_df(self, start=None, end=None, floocd=None):
        """Kembalikan copy df yang sudah difilter tanggal + lokasi."""
        df = self.df
        if start is not None:
            df = df[df["FDATE"] >= pd.to_datetime(start)]
        if end is not None:
            df = df[df["FDATE"] <= pd.to_datetime(end) + pd.Timedelta(hours=23, minutes=59, seconds=59)]
        if floocd and str(floocd).strip():
            df = df[df["FLOCCD"].astype(str) == str(floocd).strip()]
        return df.copy()

    def _period_metrics(self, start=None, end=None, floocd=None):
        """Hitung metrik utama untuk satu periode."""
        df = self.filter_df(start, end, floocd)
        b = df[df["IS_BUNDLE"]]
        n_tx = int(df["NOTRAN"].nunique())
        n_b_tx = int(b["NOTRAN"].nunique()) if len(b) > 0 else 0
        return {
            "Total Revenue (Rp)": float(df["LINE_REVENUE"].sum()),
            "Total Transaksi": n_tx,
            "Bundle Transaksi": n_b_tx,
            "Bundle %": round(n_b_tx / n_tx * 100, 2) if n_tx > 0 else 0.0,
            "Bundle Revenue (Rp)": float(b["LINE_REVENUE"].sum()),
            "Total QTY": int(df["QTY"].sum()),
            "Bundle QTY": int(b["QTY"].sum()),
            "Avg Diskon Bundle (%)": round(float(b["BUNDLE_DISC_PCT"].mean()), 2) if len(b) > 0 else 0.0,
        }

    def compare_periods(self, p1_start, p1_end, p2_start, p2_end, floocd=None):
        """Bandingkan 2 periode, kembalikan DataFrame metrik side-by-side + perubahan %.
        Growth = (P1 - P2) / P2 * 100  →  positif = P1 lebih tinggi dari P2.
        """
        p1 = self._period_metrics(p1_start, p1_end, floocd)
        p2 = self._period_metrics(p2_start, p2_end, floocd)
        rows = []
        for metric in p1.keys():
            v1, v2 = p1[metric], p2[metric]
            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                if v2 == 0:
                    growth = None
                else:
                    growth = round((v1 - v2) / v2 * 100, 2)
            else:
                growth = None
            rows.append({
                "Metrik": metric,
                "Periode 1": v1,
                "Periode 2": v2,
                "Perubahan % (P1 vs P2)": growth,
            })
        return pd.DataFrame(rows)

    def compare_by_location(
        self, p1_start, p1_end, p2_start, p2_end,
    ):
        """Per-location comparison 2 periode."""
        def per_loc(start, end):
            df = self.filter_df(start, end)
            b = df[df["IS_BUNDLE"]]
            a = df.groupby("FLOCCD").agg(
                Revenue=("LINE_REVENUE", "sum"),
                TX=("NOTRAN", "nunique"),
                QTY=("QTY", "sum"),
            )
            bv = b.groupby("FLOCCD").agg(
                Bundle_Revenue=("LINE_REVENUE", "sum"),
                Bundle_TX=("NOTRAN", "nunique"),
            )
            return a.join(bv, how="left").fillna(0)

        p1 = per_loc(p1_start, p1_end).add_suffix("_P1")
        p2 = per_loc(p2_start, p2_end).add_suffix("_P2")
        merged = p1.join(p2, how="outer").fillna(0).reset_index()
        if "FNAMA" in self.df.columns:
            nama = (
                self.df.groupby("FLOCCD")["FNAMA"].first().reset_index()
            )
            merged = merged.merge(nama, on="FLOCCD", how="left")
        # growth columns: (P1 - P2) / P2
        for col in ["Revenue", "Bundle_Revenue", "TX", "Bundle_TX"]:
            v1 = merged[f"{col}_P1"].astype(float)
            v2 = merged[f"{col}_P2"].astype(float)
            denom = v2.replace(0, float("nan"))
            growth = (v1 - v2) / denom * 100
            merged[f"{col}_Growth_%"] = growth.round(2)
        # susun ulang kolom
        if "FNAMA" in merged.columns:
            base = ["FLOCCD", "FNAMA"]
        else:
            base = ["FLOCCD"]
        p1_cols = [c for c in merged.columns if c.endswith("_P1")]
        p2_cols = [c for c in merged.columns if c.endswith("_P2")]
        g_cols = [c for c in merged.columns if c.endswith("_Growth_%")]
        merged = merged[base + p1_cols + p2_cols + g_cols]
        return merged.sort_values("Revenue_P1", ascending=False).reset_index(drop=True)

    def daily_trend(self, start=None, end=None, floocd=None):
        df = self.filter_df(start, end, floocd)
        b = df[df["IS_BUNDLE"]]
        df = df.assign(DATE=df["FDATE"].dt.normalize())
        b = b.assign(DATE=b["FDATE"].dt.normalize())
        a = df.groupby("DATE").agg(
            Revenue=("LINE_REVENUE", "sum"),
            TX=("NOTRAN", "nunique"),
        ).reset_index()
        bv = b.groupby("DATE").agg(
            Bundle_Revenue=("LINE_REVENUE", "sum"),
            Bundle_TX=("NOTRAN", "nunique"),
        ).reset_index()
        out = a.merge(bv, on="DATE", how="left").fillna(0)
        return out.sort_values("DATE").reset_index(drop=True)

    def monthly_trend(self, start=None, end=None, floocd=None):
        df = self.filter_df(start, end, floocd).copy()
        b = df[df["IS_BUNDLE"]].copy()
        df["YM"] = df["FDATE"].dt.to_period("M").astype(str)
        b["YM"] = b["FDATE"].dt.to_period("M").astype(str)
        a = df.groupby("YM").agg(
            Revenue=("LINE_REVENUE", "sum"),
            TX=("NOTRAN", "nunique"),
        ).reset_index()
        bv = b.groupby("YM").agg(
            Bundle_Revenue=("LINE_REVENUE", "sum"),
            Bundle_TX=("NOTRAN", "nunique"),
        ).reset_index()
        return a.merge(bv, on="YM", how="left").fillna(0)

    def monthly_summary_by_location(self, start=None, end=None, floocd=None):
        """
        Ringkasan per (Lokasi, Tahun, Bulan):
          KODE LOKASI | NAMA LOKASI | TAHUN | BULAN | TOTAL QTY PAKET | TOTAL QTY SATUAN
        """
        df = self.filter_df(start, end, floocd).copy()
        if df.empty:
            return pd.DataFrame(columns=["KODE LOKASI", "NAMA LOKASI", "TAHUN", "BULAN",
                                          "TOTAL QTY PAKET", "TOTAL QTY SATUAN"])
        df["TAHUN"] = df["FDATE"].dt.year
        df["BULAN"] = df["FDATE"].dt.month
        b = df[df["IS_BUNDLE"]].copy()
        nb = df[~df["IS_BUNDLE"]].copy()
        bq = b.groupby(["FLOCCD", "FNAMA", "TAHUN", "BULAN"])["QTY"].sum().reset_index(name="TOTAL QTY PAKET")
        nbq = nb.groupby(["FLOCCD", "FNAMA", "TAHUN", "BULAN"])["QTY"].sum().reset_index(name="TOTAL QTY SATUAN")
        result = bq.merge(nbq, on=["FLOCCD", "FNAMA", "TAHUN", "BULAN"], how="outer").fillna(0)
        result["TOTAL QTY PAKET"] = result["TOTAL QTY PAKET"].astype(int)
        result["TOTAL QTY SATUAN"] = result["TOTAL QTY SATUAN"].astype(int)
        result = result.rename(columns={"FLOCCD": "KODE LOKASI", "FNAMA": "NAMA LOKASI"})
        return result.sort_values(["KODE LOKASI", "TAHUN", "BULAN"]).reset_index(drop=True)

    def monthly_bundle_detail(self, start=None, end=None, floocd=None):
        """
        Detail bundle per (Lokasi, Tahun, Bulan):
          KODE LOKASI | TAHUN | BULAN | NAMA LOKASI | ITEM BUNDLE | HARGA PER PAKET
        """
        df = self.filter_df(start, end, floocd).copy()
        if df.empty:
            return pd.DataFrame(columns=["KODE LOKASI", "TAHUN", "BULAN", "NAMA LOKASI",
                                          "ITEM BUNDLE", "QTY TERJUAL", "HARGA PER PAKET"])
        b = df[df["IS_BUNDLE"]].copy()
        if b.empty:
            return pd.DataFrame(columns=["KODE LOKASI", "TAHUN", "BULAN", "NAMA LOKASI",
                                          "ITEM BUNDLE", "QTY TERJUAL", "HARGA PER PAKET"])
        b["TAHUN"] = b["FDATE"].dt.year
        b["BULAN"] = b["FDATE"].dt.month
        # Group items in each NOTRAN to form bundle combo
        combo = b.groupby(["FLOCCD", "FNAMA", "TAHUN", "BULAN", "NOTRAN"]).agg(
            ITEM_BUNDLE=("NAMA_BRG", lambda x: " + ".join(sorted(x))),
            HARGA_PER_PAKET=("LINE_REVENUE", "sum"),
            QTY_PAKET=("QTY", "sum"),
        ).reset_index()
        # Aggregate unique combos per location per month
        detail = combo.groupby(["FLOCCD", "TAHUN", "BULAN", "FNAMA", "ITEM_BUNDLE"]).agg(
            QTY_TERJUAL=("QTY_PAKET", "sum"),
            HARGA_PER_PAKET=("HARGA_PER_PAKET", "mean"),
        ).reset_index()
        detail["HARGA_PER_PAKET"] = detail["HARGA_PER_PAKET"].round(0).astype(int)
        detail["QTY_TERJUAL"] = detail["QTY_TERJUAL"].astype(int)
        detail = detail.rename(columns={"FLOCCD": "KODE LOKASI", "FNAMA": "NAMA LOKASI"})
        return detail.sort_values(["KODE LOKASI", "TAHUN", "BULAN", "QTY_TERJUAL"],
                                   ascending=[True, True, True, False]).reset_index(drop=True)

    # ===== TOP PRODUK BUNDLE =====
    def top_products_in_bundles(self, top_n: int = 20, floocd=None, start=None, end=None):
        """Item paling sering muncul di dalam bundle."""
        df = self.filter_df(start, end, floocd)
        b = df[df["IS_BUNDLE"]]
        if b.empty:
            return pd.DataFrame(columns=[
                "PLU", "NAMA_BRG", "JUMLAH_BUNDLE", "TOTAL_QTY",
                "TOTAL_REVENUE_JUMLAH", "TOTAL_REVENUE_GROSS",
                "AVG_DISC_PCT",
            ])
        grp = b.groupby(["PLU", "NAMA_BRG"], as_index=False).agg(
            JUMLAH_BUNDLE=("NOTRAN", "nunique"),
            TOTAL_QTY=("QTY", "sum"),
            TOTAL_REVENUE_JUMLAH=("JUMLAH", "sum"),
        )
        grp["TOTAL_REVENUE_GROSS"] = (
            b.assign(GROSS=b["JUALAHIR"] * b["QTY"])
             .groupby(["PLU", "NAMA_BRG"])["GROSS"].sum()
             .values
        )
        grp["AVG_DISC_PCT"] = (
            b.groupby(["PLU", "NAMA_BRG"])["BUNDLE_DISC_PCT"].mean().round(2).values
        )
        grp = grp.sort_values("JUMLAH_BUNDLE", ascending=False).head(top_n)
        return grp.reset_index(drop=True)

    def product_bundling_pairs(self, query: str, top_n: int = 10,
                                floocd=None, start=None, end=None):
        """Item yang paling sering di-bundle bersama item `query`."""
        df = self.filter_df(start, end, floocd)
        b = df[df["IS_BUNDLE"]]
        if b.empty:
            return pd.DataFrame(columns=[
                "PLU", "NAMA_BRG", "CO_OCCURRENCE",
                "TOTAL_QTY", "TOTAL_REVENUE_JUMLAH",
            ])
        q = str(query).strip()
        if not q:
            return pd.DataFrame()
        mask_q = (
            b["PLU"].astype(str).str.contains(q, case=False, na=False)
            | b["NAMA_BRG"].astype(str).str.contains(q, case=False, na=False)
        )
        query_notrans = b.loc[mask_q, "NOTRAN"].unique()
        if len(query_notrans) == 0:
            return pd.DataFrame()
        # Pasangan: item lain dalam NOTRAN yang sama (exclude item query sendiri)
        pairs = b[(b["NOTRAN"].isin(query_notrans)) & (~mask_q)]
        if pairs.empty:
            return pd.DataFrame()
        grp = pairs.groupby(["PLU", "NAMA_BRG"], as_index=False).agg(
            CO_OCCURRENCE=("NOTRAN", "nunique"),
            TOTAL_QTY=("QTY", "sum"),
            TOTAL_REVENUE_JUMLAH=("JUMLAH", "sum"),
        ).sort_values("CO_OCCURRENCE", ascending=False).head(top_n)
        return grp.reset_index(drop=True)

    # ===== ANALISA ITEM SATUAN (NON-BUNDLE) =====
    def summary_single_items(self, floocd=None, start=None, end=None) -> pd.DataFrame:
        """Ringkasan penjualan item satuan (non-bundle) per lokasi."""
        df = self.filter_df(start, end, floocd)
        nb = df[~df["IS_BUNDLE"]]
        base_cols = [
            "FLOCCD", "TOTAL_TX", "TOTAL_QTY",
            "TOTAL_REVENUE", "AVG_DISC_PCT", "AVG_ITEMS_PER_TX",
        ]
        if nb.empty:
            return pd.DataFrame(columns=base_cols)
        sm = nb.groupby("FLOCCD").agg(
            TOTAL_TX=("NOTRAN", "nunique"),
            TOTAL_QTY=("QTY", "sum"),
            TOTAL_REVENUE=("LINE_REVENUE", "sum"),
            AVG_DISC_PCT=("DISCOUNT", "mean"),
        ).round(2).reset_index()
        avg_items = (
            nb.groupby("FLOCCD")
            .apply(lambda g: round(g.groupby("NOTRAN").size().mean(), 2), include_groups=False)
            .rename("AVG_ITEMS_PER_TX")
            .reset_index()
        )
        sm = sm.merge(avg_items, on="FLOCCD", how="left")
        if "FNAMA" in self.df.columns:
            nama = self.df.groupby("FLOCCD")["FNAMA"].first().reset_index()
            sm = sm.merge(nama, on="FLOCCD", how="left")
            cols = ["FLOCCD", "FNAMA"] + [c for c in base_cols if c != "FLOCCD"]
        else:
            cols = base_cols
        return sm[cols].sort_values("TOTAL_REVENUE", ascending=False).reset_index(drop=True)

    def detail_single_items(self, floocd=None, start=None, end=None) -> pd.DataFrame:
        """Detail setiap baris item satuan (non-bundle). 1 baris = 1 item."""
        df = self.filter_df(start, end, floocd)
        nb = df[~df["IS_BUNDLE"]].copy()
        cols = [
            "FLOCCD", "FDATE", "NOTRAN", "PRAMUNIAGA", "KASIR",
            "NOM", "PLU", "NAMA_BRG", "QTY",
            "DISCOUNT", "JUALAHIR", "JUMLAH", "LINE_REVENUE",
        ]
        return nb[cols].sort_values(["FLOCCD", "FDATE", "NOTRAN", "NOM"]).reset_index(drop=True)

    def top_single_items(
        self, top_n: int = 20, floocd=None, start=None, end=None,
    ) -> pd.DataFrame:
        """Item paling laris dijual satuan (di luar paket/bundle)."""
        df = self.filter_df(start, end, floocd)
        nb = df[~df["IS_BUNDLE"]]
        out_cols = [
            "PLU", "NAMA_BRG", "JUMLAH_TX", "TOTAL_QTY",
            "TOTAL_REVENUE_JUMLAH", "TOTAL_REVENUE_GROSS", "AVG_PRICE",
        ]
        if nb.empty:
            return pd.DataFrame(columns=out_cols)
        grp = nb.groupby(["PLU", "NAMA_BRG"], as_index=False).agg(
            JUMLAH_TX=("NOTRAN", "nunique"),
            TOTAL_QTY=("QTY", "sum"),
            TOTAL_REVENUE_JUMLAH=("JUMLAH", "sum"),
            AVG_PRICE=("JUALAHIR", "mean"),
        ).round(2)
        grp["TOTAL_REVENUE_GROSS"] = (
            nb.assign(GROSS=nb["JUALAHIR"] * nb["QTY"])
              .groupby(["PLU", "NAMA_BRG"])["GROSS"].sum()
              .values
        )
        return (
            grp.sort_values("TOTAL_QTY", ascending=False)
            .head(top_n)
            .reset_index(drop=True)
        )

    def single_item_discount_dist(
        self, floocd=None, start=None, end=None,
    ) -> pd.DataFrame:
        """Distribusi nilai diskon (%) untuk item satuan per lokasi."""
        df = self.filter_df(start, end, floocd)
        nb = df[~df["IS_BUNDLE"]]
        out_cols = [
            "FLOCCD", "DISCOUNT_PCT", "JUMLAH_TX", "TOTAL_QTY", "TOTAL_REVENUE",
        ]
        if nb.empty:
            return pd.DataFrame(columns=out_cols)
        nb = nb.copy()
        nb["DISCOUNT_PCT"] = nb["DISCOUNT"].round(2)
        return (
            nb.groupby(["FLOCCD", "DISCOUNT_PCT"])
            .agg(
                JUMLAH_TX=("NOTRAN", "nunique"),
                TOTAL_QTY=("QTY", "sum"),
                TOTAL_REVENUE=("LINE_REVENUE", "sum"),
            )
            .reset_index()
            .sort_values(["FLOCCD", "DISCOUNT_PCT"])
            .reset_index(drop=True)
        )

    def search_single_items_by_item(
        self,
        item_query: str,
        floocd: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ):
        """Cari baris item satuan (non-bundle) yang mengandung keyword di PLU/NAMA_BRG.
        Return (summary_dict, detail_df) per baris (bukan per paket seperti bundle).
        """
        if self.df is None:
            raise ValueError("Data belum dimuat")
        q = str(item_query).strip()
        if not q:
            raise ValueError("Kata kunci item wajib diisi")

        empty_cols = [
            "FLOCCD", "FDATE", "NOTRAN", "PRAMUNIAGA", "KASIR",
            "PLU", "NAMA_BRG", "QTY", "DISCOUNT",
            "JUALAHIR", "JUMLAH", "LINE_REVENUE",
        ]
        empty_summary = {
            "Jumlah Baris": 0,
            "Total Nilai (Rp)": 0.0,
            "Total QTY": 0,
            "Periode Dari": date_from or "-",
            "Periode Sampai": date_to or "-",
            "Lokasi": floocd or "(semua)",
            "Kata Kunci": q,
        }
        df = self.df[~self.df["IS_BUNDLE"]].copy()
        if floocd and str(floocd).strip():
            df = df[df["FLOCCD"].astype(str) == str(floocd).strip()]
        if date_from:
            d1 = pd.to_datetime(date_from)
            df = df[df["FDATE"] >= d1]
        if date_to:
            d2 = pd.to_datetime(date_to) + pd.Timedelta(hours=23, minutes=59, seconds=59)
            df = df[df["FDATE"] <= d2]
        if df.empty:
            return empty_summary, pd.DataFrame(columns=empty_cols)

        mask = (
            df["PLU"].astype(str).str.contains(q, case=False, na=False)
            | df["NAMA_BRG"].astype(str).str.contains(q, case=False, na=False)
        )
        matches = df[mask].copy()
        if matches.empty:
            return empty_summary, pd.DataFrame(columns=empty_cols)
        if "NOM" not in matches.columns:
            matches = matches.sort_values(["FDATE", "NOTRAN"])
        else:
            matches = matches.sort_values(["FDATE", "NOTRAN", "NOM"])
        summary = {
            "Jumlah Baris": int(len(matches)),
            "Total Nilai (Rp)": float(matches["JUMLAH"].sum()),
            "Total QTY": int(matches["QTY"].sum()),
            "Periode Dari": date_from or "-",
            "Periode Sampai": date_to or "-",
            "Lokasi": floocd or "(semua lokasi)",
            "Kata Kunci": q,
        }
        return summary, matches[empty_cols].reset_index(drop=True)

    # ===== ANALISA MARGIN =====
    def margin_analysis(
        self, start=None, end=None, floocd=None, cost_pct_assumption: float | None = None,
    ):
        """
        Hitung margin (revenue - cost).
        cost_pct_assumption: jika diisi (0-100), maka cost = cost_pct% * JUALAHIR.
                            Jika None, gunakan kolom PRC_HIP dari data.
        Mengembalikan:
          summary      : dict ringkasan bundle vs non-bundle
          per_location : DataFrame margin per lokasi
          data_quality : dict info kualitas data cost
        """
        df = self.filter_df(start, end, floocd).copy()
        if df.empty:
            return {}, pd.DataFrame(), {"valid": False, "reason": "no data"}
        # Cek kualitas PRC_HIP
        ph = df["PRC_HIP"].fillna(0)
        unique_vals = ph.unique()
        n_unique = len(unique_vals)
        is_placeholder = (n_unique <= 2) and (
            (set(unique_vals) <= {0, 100}) or (set(unique_vals) <= {0})
        )
        data_quality = {
            "valid": not is_placeholder or cost_pct_assumption is not None,
            "placeholder_detected": is_placeholder,
            "unique_cost_values": n_unique,
            "using_assumption": cost_pct_assumption is not None,
            "cost_pct_assumption": cost_pct_assumption,
        }
        if cost_pct_assumption is not None:
            df["EFF_COST"] = df["JUALAHIR"] * (cost_pct_assumption / 100.0)
        else:
            df["EFF_COST"] = ph
        df["MARGIN_UNIT"] = df["JUALAHIR"] - df["EFF_COST"]
        df["MARGIN_TOTAL"] = df["MARGIN_UNIT"] * df["QTY"]
        df["MARGIN_PCT"] = df.apply(
            lambda r: (r["MARGIN_UNIT"] / r["JUALAHIR"] * 100) if r["JUALAHIR"] > 0 else 0,
            axis=1,
        )
        df["LINE_REVENUE"] = df["JUMLAH"]
        b = df[df["IS_BUNDLE"]]
        nb = df[~df["IS_BUNDLE"]]

        def agg(sub):
            if sub.empty:
                return {
                    "Total Revenue (Rp)": 0.0,
                    "Total Cost (Rp)": 0.0,
                    "Total Margin (Rp)": 0.0,
                    "Avg Margin %": 0.0,
                    "Total QTY": 0,
                }
            return {
                "Total Revenue (Rp)": float((sub["JUALAHIR"] * sub["QTY"]).sum()),
                "Total Cost (Rp)": float((sub["EFF_COST"] * sub["QTY"]).sum()),
                "Total Margin (Rp)": float(sub["MARGIN_TOTAL"].sum()),
                "Avg Margin %": round(float(sub["MARGIN_PCT"].mean()), 2),
                "Total QTY": int(sub["QTY"].sum()),
            }

        summary = {"Bundle": agg(b), "Non-Bundle": agg(nb)}

        def per_loc(sub, prefix):
            return {
                f"{prefix}_Revenue": float((sub["JUALAHIR"] * sub["QTY"]).sum()),
                f"{prefix}_Cost": float((sub["EFF_COST"] * sub["QTY"]).sum()),
                f"{prefix}_Margin": float(sub["MARGIN_TOTAL"].sum()),
                f"{prefix}_Margin_Pct": (
                    round(float(sub["MARGIN_PCT"].mean()), 2) if len(sub) > 0 else 0.0
                ),
            }

        per_loc_df = (
            df.groupby("FLOCCD")
            .apply(lambda g: pd.Series({
                **per_loc(g[g["IS_BUNDLE"]], "Bundle"),
                **per_loc(g[~g["IS_BUNDLE"]], "NonBundle"),
            }))
            .reset_index()
        )
        if "FNAMA" in self.df.columns:
            nama = self.df.groupby("FLOCCD")["FNAMA"].first().reset_index()
            per_loc_df = per_loc_df.merge(nama, on="FLOCCD", how="left")
            cols = ["FLOCCD", "FNAMA"] + [c for c in per_loc_df.columns if c not in ("FLOCCD", "FNAMA")]
            per_loc_df = per_loc_df[cols]
        per_loc_df = per_loc_df.sort_values("Bundle_Margin", ascending=False).reset_index(drop=True)
        return summary, per_loc_df, data_quality

    # ===== STRATEGI PENJUALAN =====
    def slow_moving_items(
        self,
        view: str = "all",
        floocd: str | None = None,
        start=None, end=None,
        bottom_pct: float = 20.0,
        fixed_threshold: float = 0.5,
        decline_pct: float = 50.0,
        min_total_qty: int = 1,
        top_n: int = 50,
    ) -> dict:
        """
        3 view sekaligus untuk identifikasi slow moving items.
        View: 'bottom_pct' | 'fixed_threshold' | 'decline' | 'all'
        Return: dict {view_name: DataFrame}
        """
        if self.df is None:
            raise ValueError("Data belum dimuat")
        df = self.filter_df(start, end, floocd)
        nb = df[~df["IS_BUNDLE"]].copy()
        if nb.empty:
            empty = pd.DataFrame(columns=[
                "PLU", "NAMA_BRG", "FLOCCD", "TOTAL_QTY", "AVG_DAILY_QTY",
                "LAST_SALE_DATE", "DAYS_SINCE_SALE", "CATEGORY",
            ])
            return {v: empty.copy() for v in ("bottom_pct", "fixed_threshold", "decline")}
        # Hitung per item per lokasi
        date_max = nb["FDATE"].max()
        date_min = nb["FDATE"].min()
        n_days = max((date_max - date_min).days + 1, 1)
        grp = nb.groupby(["PLU", "NAMA_BRG", "FLOCCD"], as_index=False).agg(
            TOTAL_QTY=("QTY", "sum"),
            TOTAL_REVENUE=("LINE_REVENUE", "sum"),
            LAST_SALE_DATE=("FDATE", "max"),
            FIRST_SALE_DATE=("FDATE", "min"),
        )
        # Defensive: pastikan kolom tanggal jadi datetime (beberapa pandas version
        # return object dtype setelah groupby agg, sehingga .dt.days error)
        grp["LAST_SALE_DATE"] = pd.to_datetime(grp["LAST_SALE_DATE"])
        grp["FIRST_SALE_DATE"] = pd.to_datetime(grp["FIRST_SALE_DATE"])
        grp["AVG_DAILY_QTY"] = (grp["TOTAL_QTY"] / n_days).round(3)
        grp["DAYS_SINCE_SALE"] = (date_max - grp["LAST_SALE_DATE"]).dt.days
        grp = grp[grp["TOTAL_QTY"] >= min_total_qty].copy()
        result = {}
        # View 1: bottom_pct
        if view in ("bottom_pct", "all"):
            try:
                if not grp.empty:
                    cutoff = grp["AVG_DAILY_QTY"].quantile(bottom_pct / 100.0)
                    v1 = grp[grp["AVG_DAILY_QTY"] <= cutoff].copy()
                    v1["CATEGORY"] = v1["AVG_DAILY_QTY"].apply(
                        lambda x: "Stagnant" if x < 0.05
                        else "Very Slow" if x < 0.2
                        else "Slow"
                    )
                    v1 = v1.sort_values("AVG_DAILY_QTY").head(top_n)
                    v1["LAST_SALE_DATE"] = v1["LAST_SALE_DATE"].dt.strftime("%Y-%m-%d")
                    result["bottom_pct"] = v1.reset_index(drop=True)
                else:
                    result["bottom_pct"] = pd.DataFrame()
            except Exception:
                result["bottom_pct"] = pd.DataFrame()
        # View 2: fixed_threshold
        if view in ("fixed_threshold", "all"):
            try:
                if not grp.empty:
                    v2 = grp[grp["AVG_DAILY_QTY"] < fixed_threshold].copy()
                    v2["CATEGORY"] = v2["AVG_DAILY_QTY"].apply(
                        lambda x: "Stagnant" if x < 0.05
                        else "Very Slow" if x < 0.2
                        else "Slow"
                    )
                    v2 = v2.sort_values("AVG_DAILY_QTY").head(top_n)
                    v2["LAST_SALE_DATE"] = v2["LAST_SALE_DATE"].dt.strftime("%Y-%m-%d")
                    result["fixed_threshold"] = v2.reset_index(drop=True)
                else:
                    result["fixed_threshold"] = pd.DataFrame()
            except Exception:
                result["fixed_threshold"] = pd.DataFrame()
        # View 3: decline (butuh minimal 2 periode: paruh pertama vs paruh kedua)
        if view in ("decline", "all"):
            try:
                if not grp.empty and n_days >= 14:
                    mid_date = date_min + pd.Timedelta(days=n_days // 2)
                    nb2 = nb.copy()
                    # Pastikan FDATE datetime (defensive untuk pandas version berbeda)
                    nb2["FDATE"] = pd.to_datetime(nb2["FDATE"])
                    nb2["PERIOD"] = np.where(nb2["FDATE"] <= mid_date, "P1", "P2")
                    pivot = nb2.groupby(
                        ["PLU", "NAMA_BRG", "FLOCCD", "PERIOD"]
                    )["QTY"].sum().unstack(fill_value=0)
                    # Pastikan kedua kolom ada
                    if "P1" not in pivot.columns: pivot["P1"] = 0
                    if "P2" not in pivot.columns: pivot["P2"] = 0
                    pivot = pivot.reset_index()
                    pivot["CHANGE_PCT"] = np.where(
                        pivot["P1"] > 0,
                        (pivot["P2"] - pivot["P1"]) / pivot["P1"] * 100,
                        np.nan,
                    )
                    # hanya tampilkan yang P1>0 (pernah laku) dan turun > threshold
                    v3 = pivot[
                        (pivot["P1"] > 0) & (pivot["CHANGE_PCT"] < -decline_pct)
                    ].copy()
                    v3 = v3.merge(
                        grp[["PLU", "NAMA_BRG", "FLOCCD", "TOTAL_QTY",
                             "AVG_DAILY_QTY", "LAST_SALE_DATE", "DAYS_SINCE_SALE"]],
                        on=["PLU", "NAMA_BRG", "FLOCCD"], how="left",
                    )
                    v3 = v3.rename(columns={"P1": "QTY_P1", "P2": "QTY_P2"})
                    v3["LAST_SALE_DATE"] = pd.to_datetime(v3["LAST_SALE_DATE"]).dt.strftime("%Y-%m-%d")
                    v3["CHANGE_PCT"] = v3["CHANGE_PCT"].round(2)
                    v3 = v3.sort_values("CHANGE_PCT").head(top_n)
                    v3 = v3[[
                        "PLU", "NAMA_BRG", "FLOCCD", "TOTAL_QTY", "AVG_DAILY_QTY",
                        "QTY_P1", "QTY_P2", "CHANGE_PCT", "LAST_SALE_DATE", "DAYS_SINCE_SALE",
                    ]]
                    result["decline"] = v3.reset_index(drop=True)
                else:
                    result["decline"] = pd.DataFrame()
            except Exception:
                result["decline"] = pd.DataFrame()
                result["decline"] = pd.DataFrame()
        return result

    def dead_stock_items(
        self,
        days: int = 60,
        floocd: str | None = None,
        start=None, end=None,
        min_lifetime_qty: int = 1,
        top_n: int = 100,
    ) -> pd.DataFrame:
        """
        Item yang TIDAK ADA transaksi dalam `days` hari terakhir,
        tapi pernah laku sebelumnya.
        Asumsi: gunakan reference date = max(FDATE) di seluruh data
                (bukan hari ini), supaya konsisten untuk data historis.
        """
        if self.df is None:
            raise ValueError("Data belum dimuat")
        df = self.filter_df(start, end, floocd)
        nb = df[~df["IS_BUNDLE"]].copy()
        if nb.empty:
            return pd.DataFrame(columns=[
                "PLU", "NAMA_BRG", "FLOCCD",
                "LAST_SALE_DATE", "DAYS_SINCE_SALE",
                "LIFETIME_QTY", "LIFETIME_REVENUE",
            ])
        ref_date = nb["FDATE"].max()
        cutoff = ref_date - pd.Timedelta(days=days)
        # Lifetime aggregate (seluruh sejarah)
        lifetime = nb.groupby(["PLU", "NAMA_BRG", "FLOCCD"], as_index=False).agg(
            LIFETIME_QTY=("QTY", "sum"),
            LIFETIME_REVENUE=("LINE_REVENUE", "sum"),
            LAST_SALE_DATE=("FDATE", "max"),
            FIRST_SALE_DATE=("FDATE", "min"),
        )
        lifetime["LAST_SALE_DATE"] = pd.to_datetime(lifetime["LAST_SALE_DATE"])
        lifetime["FIRST_SALE_DATE"] = pd.to_datetime(lifetime["FIRST_SALE_DATE"])
        # Hanya yang terakhir jual di LUAR window (dead stock)
        dead = lifetime[
            (lifetime["LAST_SALE_DATE"] < cutoff) & (lifetime["LIFETIME_QTY"] >= min_lifetime_qty)
        ].copy()
        dead["DAYS_SINCE_SALE"] = (ref_date - dead["LAST_SALE_DATE"]).dt.days
        dead["URGENCY"] = dead["DAYS_SINCE_SALE"].apply(
            lambda x: "🔴 Kritis (>90h)" if x > 90
            else "🟠 Tinggi (60-90h)" if x > days
            else f"🟡 {days}h"
        )
        dead = dead.sort_values("DAYS_SINCE_SALE", ascending=False).head(top_n)
        dead["LAST_SALE_DATE"] = dead["LAST_SALE_DATE"].dt.strftime("%Y-%m-%d")
        dead["FIRST_SALE_DATE"] = dead["FIRST_SALE_DATE"].dt.strftime("%Y-%m-%d")
        dead["LIFETIME_REVENUE"] = dead["LIFETIME_REVENUE"].round(0)
        return dead[[
            "PLU", "NAMA_BRG", "FLOCCD", "URGENCY",
            "LAST_SALE_DATE", "DAYS_SINCE_SALE",
            "FIRST_SALE_DATE", "LIFETIME_QTY", "LIFETIME_REVENUE",
        ]].reset_index(drop=True)

    def market_basket_pairs(
        self,
        top_n_bestsellers: int = 20,
        top_n_pairs_per_item: int = 5,
        floocd: str | None = None,
        start=None, end=None,
    ) -> pd.DataFrame:
        """
        Untuk setiap top-N best-seller item, cari item PALING SERING
        muncul dalam NOTRAN yang sama (cross-sell candidates).
        Hanya menghitung item non-bundle di NOTRAN yang ada item best-seller tsb.
        Return: 1 baris = (best_seller, paired_item) dengan co-occurrence count.
        """
        if self.df is None:
            raise ValueError("Data belum dimuat")
        df = self.filter_df(start, end, floocd)
        nb = df[~df["IS_BUNDLE"]].copy()
        if nb.empty:
            return pd.DataFrame(columns=[
                "BESTSELLER_PLU", "BESTSELLER_NAME",
                "PAIR_PLU", "PAIR_NAME",
                "CO_OCCURRENCE", "PAIR_TOTAL_QTY",
            ])
        # Tentukan top-N bestsellers
        top = (
            nb.groupby(["PLU", "NAMA_BRG"], as_index=False)
            .agg(QTY=("QTY", "sum"))
            .sort_values("QTY", ascending=False)
            .head(top_n_bestsellers)
        )
        all_notrans = set()
        for _, row in top.iterrows():
            mask = (
                (nb["PLU"].astype(str) == str(row["PLU"]))
                & (nb["NAMA_BRG"] == row["NAMA_BRG"])
            )
            all_notrans.update(nb.loc[mask, "NOTRAN"].unique().tolist())
        if not all_notrans:
            return pd.DataFrame(columns=[
                "BESTSELLER_PLU", "BESTSELLER_NAME",
                "PAIR_PLU", "PAIR_NAME",
                "CO_OCCURRENCE", "PAIR_TOTAL_QTY",
            ])
        candidates = nb[nb["NOTRAN"].isin(all_notrans)].copy()
        # Untuk setiap best-seller, hitung pair
        results = []
        for _, row in top.iterrows():
            mask_bs = (
                (candidates["PLU"].astype(str) == str(row["PLU"]))
                & (candidates["NAMA_BRG"] == row["NAMA_BRG"])
            )
            bs_notrans = candidates.loc[mask_bs, "NOTRAN"].unique()
            # Ambil item lain (bukan best-seller) dalam NOTRAN yang sama
            pair_mask = (
                candidates["NOTRAN"].isin(bs_notrans)
                & ~mask_bs
            )
            if not pair_mask.any():
                continue
            pair_agg = (
                candidates[pair_mask]
                .groupby(["PLU", "NAMA_BRG"], as_index=False)
                .agg(
                    CO_OCCURRENCE=("NOTRAN", "nunique"),
                    PAIR_TOTAL_QTY=("QTY", "sum"),
                )
                .sort_values("CO_OCCURRENCE", ascending=False)
                .head(top_n_pairs_per_item)
            )
            pair_agg["BESTSELLER_PLU"] = row["PLU"]
            pair_agg["BESTSELLER_NAME"] = row["NAMA_BRG"]
            results.append(pair_agg)
        if not results:
            return pd.DataFrame(columns=[
                "BESTSELLER_PLU", "BESTSELLER_NAME",
                "PAIR_PLU", "PAIR_NAME",
                "CO_OCCURRENCE", "PAIR_TOTAL_QTY",
            ])
        out = pd.concat(results, ignore_index=True)
        out = out.rename(columns={"PLU": "PAIR_PLU", "NAMA_BRG": "PAIR_NAME"})
        out = out[[
            "BESTSELLER_PLU", "BESTSELLER_NAME",
            "PAIR_PLU", "PAIR_NAME",
            "CO_OCCURRENCE", "PAIR_TOTAL_QTY",
        ]].sort_values(
            ["BESTSELLER_PLU", "CO_OCCURRENCE"], ascending=[True, False]
        ).reset_index(drop=True)
        return out

    def seasonal_pattern(
        self,
        floocd: str | None = None,
        start=None, end=None,
        top_n: int = 30,
        min_months_active: int = 2,
    ) -> pd.DataFrame:
        """
        Deteksi pola musiman (peak vs off months) per item.
        Menggunakan agregasi QTY per bulan dalam data yang ada.
        Untuk data 6 bulan: deteksi pola intra-tahun (Q1, Q2, dst).
        Untuk data >=12 bulan: bisa deteksi pola YoY.
        Return: DataFrame dengan kolom PEAK_MONTHS, OFF_MONTHS, dll.
        """
        if self.df is None:
            raise ValueError("Data belum dimuat")
        df = self.filter_df(start, end, floocd)
        nb = df[~df["IS_BUNDLE"]].copy()
        if nb.empty:
            return pd.DataFrame(columns=[
                "PLU", "NAMA_BRG", "FLOCCD",
                "ACTIVE_MONTHS", "PEAK_MONTHS", "PEAK_QTY",
                "OFF_MONTHS", "TOTAL_QTY", "AVG_MONTHLY_QTY",
            ])
        nb["YEAR_MONTH"] = nb["FDATE"].dt.to_period("M")
        grp = nb.groupby(
            ["PLU", "NAMA_BRG", "FLOCCD", "YEAR_MONTH"], as_index=False
        )["QTY"].sum()
        # Untuk setiap item, cari bulan dengan QTY tertinggi (peak)
        idxmax = grp.groupby(["PLU", "NAMA_BRG", "FLOCCD"])["QTY"].idxmax()
        peaks = grp.loc[idxmax].copy()
        peaks = peaks.rename(columns={
            "YEAR_MONTH": "PEAK_MONTH",
            "QTY": "PEAK_QTY",
        })
        # Hitung total & avg per bulan
        agg = grp.groupby(["PLU", "NAMA_BRG", "FLOCCD"], as_index=False).agg(
            TOTAL_QTY=("QTY", "sum"),
            ACTIVE_MONTHS=("QTY", "count"),
        )
        agg["AVG_MONTHLY_QTY"] = (agg["TOTAL_QTY"] / agg["ACTIVE_MONTHS"]).round(2)
        # Peak month string list (grouped)
        def peak_month_str(g):
            if g.empty or g["QTY"].max() <= 0:
                return "(tidak ada)"
            peak = g.loc[g["QTY"].idxmax(), "YEAR_MONTH"]
            return str(peak)
        peak_str = (
            grp.groupby(["PLU", "NAMA_BRG", "FLOCCD"])
            .apply(peak_month_str, include_groups=False)
            .reset_index(name="PEAK_MONTHS")
        )
        # Off months: bulan dengan QTY <= 25% dari peak
        def off_months(g):
            if g.empty:
                return ""
            mx = g["QTY"].max()
            if mx == 0:
                return ""
            threshold = mx * 0.25
            off = g[g["QTY"] <= threshold]["YEAR_MONTH"].astype(str).tolist()
            return ", ".join(off) if off else "(tidak ada)"
        off_str = (
            grp.groupby(["PLU", "NAMA_BRG", "FLOCCD"])
            .apply(off_months, include_groups=False)
            .reset_index(name="OFF_MONTHS")
        )
        # Merge
        out = agg.merge(
            peak_str, on=["PLU", "NAMA_BRG", "FLOCCD"], how="left"
        ).merge(
            off_str, on=["PLU", "NAMA_BRG", "FLOCCD"], how="left"
        )
        out["PEAK_MONTHS"] = out["PEAK_MONTHS"].fillna("(tidak ada)")
        out["OFF_MONTHS"] = out["OFF_MONTHS"].fillna("(tidak ada)")
        out = out[out["ACTIVE_MONTHS"] >= min_months_active]
        out = out[out["TOTAL_QTY"] >= 10]
        out = out.sort_values("TOTAL_QTY", ascending=False).head(top_n)
        return out[[
            "PLU", "NAMA_BRG", "FLOCCD", "ACTIVE_MONTHS",
            "PEAK_MONTHS", "OFF_MONTHS", "TOTAL_QTY", "AVG_MONTHLY_QTY",
        ]].reset_index(drop=True)

    def promo_recommendations(
        self,
        floocd: str | None = None,
        start=None, end=None,
        cost_pct_assumption: float | None = 30.0,
        clearance_min_margin_pct: float = 30.0,
        clearance_max_avg_daily_qty: float = 1.0,
        momentum_increase_pct: float = 50.0,
        top_n_per_strategy: int = 20,
    ) -> dict:
        """
        4 strategi rekomendasi promosi:
        1. clearance    : slow-moving + margin tinggi → diskon/bundle
        2. momentum     : trending up → pertahankan
        3. basket       : complementary best-sellers (top pairs)
        4. seasonal     : pola musiman, stok bulan depan
        Return: dict {strategy: DataFrame, 'meta': {...}}
        """
        result = {"meta": {"strategies": ["clearance", "momentum", "basket", "seasonal"]}}
        if self.df is None:
            raise ValueError("Data belum dimuat")
        df = self.filter_df(start, end, floocd)
        nb = df[~df["IS_BUNDLE"]].copy()
        if nb.empty:
            empty_cols = ["PLU", "NAMA_BRG", "FLOCCD", "REASON", "SUGGESTED_ACTION"]
            return {
                "clearance": pd.DataFrame(columns=empty_cols),
                "momentum": pd.DataFrame(columns=empty_cols),
                "basket": pd.DataFrame(columns=empty_cols),
                "seasonal": pd.DataFrame(columns=empty_cols),
                "meta": result["meta"],
            }
        date_max = nb["FDATE"].max()
        date_min = nb["FDATE"].min()
        n_days = max((date_max - date_min).days + 1, 1)
        # Hitung margin per baris
        if cost_pct_assumption is not None:
            nb["EFF_COST"] = nb["JUALAHIR"] * (cost_pct_assumption / 100.0)
        elif "PRC_HIP" in nb.columns:
            nb["EFF_COST"] = nb["PRC_HIP"].fillna(nb["JUALAHIR"] * 0.7)
        else:
            nb["EFF_COST"] = nb["JUALAHIR"] * 0.7
        nb["MARGIN_PCT"] = np.where(
            nb["JUALAHIR"] > 0,
            (nb["JUALAHIR"] - nb["EFF_COST"]) / nb["JUALAHIR"] * 100,
            0,
        )
        # Aggregasi per item per lokasi
        agg = nb.groupby(
            ["PLU", "NAMA_BRG", "FLOCCD"], as_index=False
        ).agg(
            TOTAL_QTY=("QTY", "sum"),
            TOTAL_REVENUE=("LINE_REVENUE", "sum"),
            AVG_MARGIN_PCT=("MARGIN_PCT", "mean"),
            LAST_SALE_DATE=("FDATE", "max"),
        )
        agg["LAST_SALE_DATE"] = pd.to_datetime(agg["LAST_SALE_DATE"])
        agg["AVG_DAILY_QTY"] = (agg["TOTAL_QTY"] / n_days).round(3)
        agg["DAYS_SINCE_SALE"] = (date_max - agg["LAST_SALE_DATE"]).dt.days
        agg["AVG_MARGIN_PCT"] = agg["AVG_MARGIN_PCT"].round(2)
        # STRATEGY 1: clearance
        clearance = agg[
            (agg["AVG_DAILY_QTY"] <= clearance_max_avg_daily_qty)
            & (agg["AVG_MARGIN_PCT"] >= clearance_min_margin_pct)
            & (agg["TOTAL_QTY"] > 0)
        ].copy()
        clearance["REASON"] = (
            f"Margin tinggi ({clearance_min_margin_pct}%+) tapi lambat laku "
            f"(<{clearance_max_avg_daily_qty} qty/hari)"
        )
        clearance["SUGGESTED_ACTION"] = clearance["AVG_MARGIN_PCT"].apply(
            lambda m: f"Diskon 15-20% / bundle dengan best-seller" if m >= 50
            else f"Diskon 10-15% / bundle dengan best-seller" if m >= 35
            else "Bundle dengan item fast-moving"
        )
        clearance = clearance.sort_values("AVG_MARGIN_PCT", ascending=False).head(top_n_per_strategy)
        result["clearance"] = clearance[[
            "PLU", "NAMA_BRG", "FLOCCD", "REASON", "SUGGESTED_ACTION",
            "TOTAL_QTY", "AVG_DAILY_QTY", "AVG_MARGIN_PCT",
        ]].reset_index(drop=True)
        # STRATEGY 2: momentum (perubahan QTY P2 vs P1 > threshold)
        if n_days >= 14:
            mid_date = date_min + pd.Timedelta(days=n_days // 2)
            nb2 = nb.copy()
            nb2["PERIOD"] = np.where(nb2["FDATE"] <= mid_date, "P1", "P2")
            pivot = nb2.groupby(
                ["PLU", "NAMA_BRG", "FLOCCD", "PERIOD"]
            )["QTY"].sum().unstack(fill_value=0)
            if "P1" not in pivot.columns: pivot["P1"] = 0
            if "P2" not in pivot.columns: pivot["P2"] = 0
            pivot = pivot.reset_index()
            pivot["CHANGE_PCT"] = np.where(
                pivot["P1"] > 0,
                (pivot["P2"] - pivot["P1"]) / pivot["P1"] * 100,
                np.where(pivot["P2"] > 0, 999.0, 0.0),
            )
            momentum = pivot[pivot["CHANGE_PCT"] >= momentum_increase_pct].copy()
            momentum = momentum.merge(
                agg[["PLU", "NAMA_BRG", "FLOCCD", "TOTAL_REVENUE",
                     "AVG_MARGIN_PCT", "LAST_SALE_DATE", "DAYS_SINCE_SALE"]],
                on=["PLU", "NAMA_BRG", "FLOCCD"], how="left",
            )
            momentum["REASON"] = (
                f"QTY naik {momentum_increase_pct:.0f}%+ di paruh kedua periode"
            )
            momentum["SUGGESTED_ACTION"] = "Pertahankan momentum, tambah stok, featured display"
            momentum = momentum.rename(columns={"P1": "QTY_P1", "P2": "QTY_P2"})
            momentum = momentum.sort_values("CHANGE_PCT", ascending=False).head(top_n_per_strategy)
            momentum["LAST_SALE_DATE"] = momentum["LAST_SALE_DATE"].dt.strftime("%Y-%m-%d")
            momentum["CHANGE_PCT"] = momentum["CHANGE_PCT"].round(2)
            result["momentum"] = momentum[[
                "PLU", "NAMA_BRG", "FLOCCD", "REASON", "SUGGESTED_ACTION",
                "QTY_P1", "QTY_P2", "CHANGE_PCT", "TOTAL_REVENUE", "AVG_MARGIN_PCT",
            ]].reset_index(drop=True)
        else:
            result["momentum"] = pd.DataFrame(columns=[
                "PLU", "NAMA_BRG", "FLOCCD", "REASON", "SUGGESTED_ACTION",
                "QTY_P1", "QTY_P2", "CHANGE_PCT", "TOTAL_REVENUE", "AVG_MARGIN_PCT",
            ])
        # STRATEGY 3: basket
        try:
            mb = self.market_basket_pairs(
                top_n_bestsellers=20, top_n_pairs_per_item=3,
                floocd=floocd, start=start, end=end,
            )
            if not mb.empty:
                mb["REASON"] = (
                    "Sering dibeli bersama best-seller dalam 1 transaksi"
                )
                mb["SUGGESTED_ACTION"] = (
                    "Bundle/diskon combo: " + mb["BESTSELLER_NAME"].astype(str) + " + " + mb["PAIR_NAME"].astype(str)
                )
                result["basket"] = mb.head(top_n_per_strategy).reset_index(drop=True)
            else:
                result["basket"] = pd.DataFrame(columns=[
                    "PLU", "NAMA_BRG", "FLOCCD", "REASON", "SUGGESTED_ACTION",
                    "BESTSELLER_NAME", "PAIR_NAME", "CO_OCCURRENCE",
                ])
        except Exception:
            result["basket"] = pd.DataFrame(columns=[
                "PLU", "NAMA_BRG", "FLOCCD", "REASON", "SUGGESTED_ACTION",
                "BESTSELLER_NAME", "PAIR_NAME", "CO_OCCURRENCE",
            ])
        # STRATEGY 4: seasonal
        try:
            ss = self.seasonal_pattern(
                floocd=floocd, start=start, end=end, top_n=top_n_per_strategy,
            )
            if not ss.empty:
                ss["REASON"] = "Pola musiman: peak di " + ss["PEAK_MONTHS"].astype(str)
                ss["SUGGESTED_ACTION"] = ss["PEAK_MONTHS"].apply(
                    lambda p: f"Stok lebih banyak di {p.split(',')[0].strip()}, promo ringan 1-2 minggu sebelum"
                )
                ss = ss.rename(columns={"TOTAL_QTY": "LIFETIME_QTY"})
                result["seasonal"] = ss.reset_index(drop=True)
            else:
                result["seasonal"] = pd.DataFrame(columns=[
                    "PLU", "NAMA_BRG", "FLOCCD", "REASON", "SUGGESTED_ACTION",
                    "PEAK_MONTHS", "OFF_MONTHS", "LIFETIME_QTY",
                ])
        except Exception:
            result["seasonal"] = pd.DataFrame(columns=[
                "PLU", "NAMA_BRG", "FLOCCD", "REASON", "SUGGESTED_ACTION",
                "PEAK_MONTHS", "OFF_MONTHS", "LIFETIME_QTY",
            ])
        return result

    # ---------- EXPORT ----------
    def export(self, output_path: str, top_n: int = 20) -> str:
        with pd.ExcelWriter(output_path, engine="openpyxl") as w:
            self._write_readme(w)
            self.summary_by_location().to_excel(
                w, sheet_name="Summary_per_Lokasi", index=False
            )
            self.discount_distribution().to_excel(
                w, sheet_name="Distribusi_Discount", index=False
            )
            self.bundle_detail().to_excel(w, sheet_name="Detail_Bundle", index=False)
            self.top_bundles(top_n).to_excel(
                w, sheet_name="Top_Kombinasi_Bundle", index=False
            )
            self.non_bundle_summary().to_excel(
                w, sheet_name="NonBundle_Reff", index=False
            )
        return output_path

    @staticmethod
    def _write_readme(writer):
        """Tulis sheet 'BACA_DULU' berisi glosarium kolom."""
        rows = [
            ["BUNDLE SALES ANALYZER - PETA FILE OUTPUT", ""],
            ["", ""],
            ["Kriteria BUNDLE", "1 NOTRAN memiliki >= 2 item DAN semua item punya nilai DISCOUNT (%) yang SAMA."],
            ["Lokasi dianalisa per FLOCCD (kode lokasi/outlet).", ""],
            ["", ""],
            ["=== Sheet: Summary_per_Lokasi ===", "Lokasi mana yang paling banyak bundle?"],
            ["FLOCCD", "Kode lokasi/outlet"],
            ["FNAMA", "Nama lokasi/outlet"],
            ["TOTAL_TX", "Jumlah SEMUA transaksi di lokasi ini"],
            ["BUNDLE_TX", "Jumlah transaksi yang BUNDLE"],
            ["BUNDLE_TX_PCT", "% bundle dari total. Makin tinggi = makin sering pakai paket"],
            ["AVG_BUNDLE_DISC_PCT", "Rata-rata diskon (%) pada transaksi bundle"],
            ["MIN_BUNDLE_DISC_PCT", "Diskon terkecil di bundle lokasi ini"],
            ["MAX_BUNDLE_DISC_PCT", "Diskon terbesar di bundle lokasi ini"],
            ["BUNDLE_REVENUE", "Total uang (Rp) dari penjualan bundle"],
            ["BUNDLE_QTY", "Total unit barang terjual lewat bundle"],
            ["AVG_ITEMS_PER_BUNDLE", "Rata-rata jumlah barang dalam 1 transaksi bundle"],
            ["", ""],
            ["=== Sheet: Distribusi_Discount ===", "Pola diskon (%) favorit per lokasi"],
            ["FLOCCD", "Kode lokasi"],
            ["BUNDLE_DISC_PCT", "Nilai diskon (%)"],
            ["JUMLAH_TX", "Berapa transaksi bundle pakai diskon segitu"],
            ["TOTAL_QTY", "Total unit terjual di diskon segitu"],
            ["TOTAL_REVENUE", "Total uang (Rp) di diskon segitu"],
            ["", ""],
            ["=== Sheet: Detail_Bundle ===", "1 baris = 1 item dalam transaksi bundle"],
            ["FDATE", "Tanggal transaksi"],
            ["NOTRAN", "Nomor transaksi (sama = 1 transaksi yg sama)"],
            ["PRAMUNIAGA", "Nama SPG/pramuniaga"],
            ["KASIR", "Nama kasir"],
            ["BUNDLE_DISC_PCT", "Diskon bundle untuk transaksi ini"],
            ["NOM", "No urut item dalam 1 transaksi"],
            ["PLU", "Kode produk"],
            ["NAMA_BRG", "Nama barang/produk"],
            ["QTY", "Jumlah unit"],
            ["DISCOUNT", "Diskon per baris (sama dgn BUNDLE_DISC_PCT untuk bundle)"],
            ["JUALAHIR", "Harga jual akhir per unit"],
            ["JUMLAH", "Total nett per baris (JUMLAH = LINE_NETT, sudah × QTY + diskon)"],
            ["LINE_REVENUE", "Pendapatan baris (sama dengan JUMLAH, sudah nett)"],
            ["", ""],
            ["=== Sheet: Top_Kombinasi_Bundle ===", "Kombinasi barang yg paling sering dijadikan paket"],
            ["FLOCCD", "Kode lokasi"],
            ["BUNDLE_DISC_PCT", "Diskon combo ini"],
            ["KOMBINASI_ITEM", "Daftar barang dalam paket (pemisah: +)"],
            ["JUMLAH_TX", "Berapa kali kombinasi ini terjual"],
            ["TOTAL_REVENUE", "Total uang (Rp) dari kombinasi ini"],
            ["TOTAL_QTY", "Total unit terjual"],
            ["", ""],
            ["=== Sheet: NonBundle_Reff ===", "Pembanding: transaksi NON-bundle per lokasi"],
            ["FLOCCD", "Kode lokasi"],
            ["NON_BUNDLE_TX", "Jumlah transaksi yg BUKAN bundle"],
            ["NON_BUNDLE_REVENUE", "Total uang (Rp) dari non-bundle"],
            ["", ""],
            ["TIPS BACA", "1) Mulai dari 'Summary_per_Lokasi' untuk lihat gambaran besar."],
            ["", "2) Lihat 'BUNDLE_TX_PCT' = lokasi paling sering pakai paket."],
            ["", "3) Lihat 'BUNDLE_REVENUE' = lokasi dgn revenue bundle terbesar."],
            ["", "4) Buka 'Top_Kombinasi_Bundle' untuk tau combo apa yg laris."],
            ["", "5) Buka 'Detail_Bundle' untuk audit per transaksi (sort by NOTRAN)."],
        ]
        df = pd.DataFrame(rows, columns=["Istilah / Kolom", "Artinya (bahasa sederhana)"])
        df.to_excel(writer, sheet_name="BACA_DULU", index=False)


# =====================================================================
# CLI MODE
# =====================================================================
def run_cli(input_path: str, output_path: str, min_items: int, min_discount: float):
    a = BundleAnalyzer()
    a.load(input_path)
    a.classify(min_items=min_items, min_discount=min_discount)
    out = a.export(output_path)
    sm = a.summary_by_location()
    print("=" * 70)
    print(f"File input   : {input_path}")
    print(f"Min items    : {min_items}")
    print(f"Min discount : {min_discount}%")
    print("=" * 70)
    print(sm.to_string(index=False))
    print("=" * 70)
    n_bundle = a.df["IS_BUNDLE"].sum()
    n_tx_bundle = a.df[a.df["IS_BUNDLE"]]["NOTRAN"].nunique()
    print(f"Total baris       : {len(a.df)}")
    print(f"Total transaksi   : {a.df['NOTRAN'].nunique()}")
    print(f"Baris bundle      : {n_bundle}")
    print(f"Transaksi bundle  : {n_tx_bundle}")
    print(f"Hasil disimpan di : {out}")
    return out


# =====================================================================
# GUI MODE
# =====================================================================
def run_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import os
    import sys

    def resource_path(rel: str) -> str:
        """Ambil path resource. Handle PyInstaller --add-data."""
        if getattr(sys, "frozen", False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, rel)

    class App:
        def __init__(self, root):
            self.root = root
            self.root.title("Bundle Sales Analyzer")
            self.root.geometry("1200x750")
            self.analyzer = BundleAnalyzer()
            self.current_dfs: dict[str, pd.DataFrame] = {}
            self._build()

        def _build(self):
            style = ttk.Style()
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass

            # ====== TOP BAR : file & opsi ======
            top = ttk.LabelFrame(self.root, text="Input & Pengaturan", padding=10)
            top.pack(fill="x", padx=10, pady=(10, 5))

            ttk.Label(top, text="File Excel:").grid(row=0, column=0, sticky="w")
            self.file_var = tk.StringVar()
            ttk.Entry(top, textvariable=self.file_var, width=80).grid(
                row=0, column=1, padx=5, sticky="we"
            )
            ttk.Button(top, text="Browse...", command=self._browse).grid(
                row=0, column=2, padx=2
            )

            ttk.Label(top, text="Min item per bundle:").grid(
                row=1, column=0, sticky="w", pady=(8, 0)
            )
            self.min_items_var = tk.IntVar(value=2)
            ttk.Spinbox(
                top, from_=2, to=20, textvariable=self.min_items_var, width=8
            ).grid(row=1, column=1, sticky="w", padx=5, pady=(8, 0))

            ttk.Label(top, text="Min discount %:").grid(
                row=1, column=1, sticky="e", padx=(0, 80), pady=(8, 0)
            )
            self.min_disc_var = tk.DoubleVar(value=0.0)
            ttk.Entry(top, textvariable=self.min_disc_var, width=8).grid(
                row=1, column=1, sticky="e", pady=(8, 0)
            )

            ttk.Label(top, text="Filter FLOCCD (opsional):").grid(
                row=2, column=0, sticky="w", pady=(8, 0)
            )
            self.loc_var = tk.StringVar()
            ttk.Entry(
                top,
                textvariable=self.loc_var,
                width=40,
            ).grid(row=2, column=1, sticky="w", padx=5, pady=(8, 0))
            ttk.Label(
                top,
                text="(kosongkan = semua lokasi; pisahkan dengan koma)",
                foreground="gray",
            ).grid(row=2, column=1, sticky="e", padx=(0, 30), pady=(8, 0))

            # Baris 3: preset tanggal + date range
            ttk.Label(top, text="Periode / Preset:").grid(
                row=3, column=0, sticky="w", pady=(8, 0)
            )
            self.date_preset_var = tk.StringVar(value="Semua data")
            self.date_preset_combo = ttk.Combobox(
                top, textvariable=self.date_preset_var,
                values=["Semua data", "7 hari terakhir", "14 hari terakhir",
                        "30 hari terakhir", "90 hari terakhir",
                        "Bulan ini", "Bulan lalu", "3 bulan terakhir",
                        "6 bulan terakhir", "Tahun ini (YTD)", "Custom"],
                state="readonly", width=25,
            )
            self.date_preset_combo.grid(row=3, column=1, sticky="w", padx=5, pady=(8, 0))
            self.date_preset_combo.bind("<<ComboboxSelected>>", lambda e: self._on_preset_change())

            ttk.Label(top, text="Dari:").grid(
                row=4, column=0, sticky="e", pady=(4, 0)
            )
            self.date_from_var = tk.StringVar()
            ttk.Entry(top, textvariable=self.date_from_var, width=15).grid(
                row=4, column=1, sticky="w", padx=5, pady=(4, 0)
            )
            ttk.Label(top, text="Sampai:").grid(
                row=4, column=1, sticky="e", padx=(0, 200), pady=(4, 0)
            )
            self.date_to_var = tk.StringVar()
            ttk.Entry(top, textvariable=self.date_to_var, width=15).grid(
                row=4, column=1, sticky="e", padx=(0, 130), pady=(4, 0)
            )
            ttk.Label(
                top, text="(format YYYY-MM-DD)", foreground="gray",
            ).grid(row=4, column=2, sticky="w", pady=(4, 0))

            top.columnconfigure(1, weight=1)

            # ====== ACTION BUTTONS ======
            act = ttk.Frame(self.root, padding=(10, 0, 10, 5))
            act.pack(fill="x")
            ttk.Button(act, text="▶ Analisa", command=self._analyze).pack(
                side="left", padx=2
            )
            ttk.Button(act, text="💾 Export ke Excel", command=self._export).pack(
                side="left", padx=2
            )
            ttk.Button(act, text="Bersihkan", command=self._clear).pack(
                side="left", padx=2
            )
            ttk.Button(act, text="❓ Help / Panduan", command=self._show_help).pack(
                side="right", padx=2
            )

            # ====== NOTEBOOK (TAB HASIL) ======
            self.nb = ttk.Notebook(self.root)
            self.nb.pack(fill="both", expand=True, padx=10, pady=5)

            self.tab_frames: dict[str, ttk.Frame] = {}
            self.tab_trees: dict[str, ttk.Treeview] = {}
            for name in [
                "Summary per Lokasi",
                "Distribusi Discount",
                "Detail Bundle",
                "Top Kombinasi Bundle",
            ]:
                f = ttk.Frame(self.nb)
                self.nb.add(f, text=name)
                self.tab_frames[name] = f

            # Tab khusus: Cari Paket by Item
            self.search_frame = ttk.Frame(self.nb)
            self.nb.add(self.search_frame, text="🔍 Cari Paket by Item")
            self._build_search_tab(self.search_frame)

            # Tab khusus: Perbandingan (VS)
            self.compare_frame = ttk.Frame(self.nb)
            self.nb.add(self.compare_frame, text="📊 Perbandingan (VS)")
            self._build_compare_tab(self.compare_frame)

            # Tab khusus: Trend / Chart
            self.trend_frame = ttk.Frame(self.nb)
            self.nb.add(self.trend_frame, text="📈 Trend & Chart")
            self._build_trend_tab(self.trend_frame)

            # Tab khusus: Top Produk Bundle
            self.topprod_frame = ttk.Frame(self.nb)
            self.nb.add(self.topprod_frame, text="🏆 Top Produk Bundle")
            self._build_topprod_tab(self.topprod_frame)

            # Tab khusus: Analisa Margin
            self.margin_frame = ttk.Frame(self.nb)
            self.nb.add(self.margin_frame, text="💰 Analisa Margin")
            self._build_margin_tab(self.margin_frame)

            # Tab khusus: Item Satuan (non-bundle)
            self.satuan_frame = ttk.Frame(self.nb)
            self.nb.add(self.satuan_frame, text="📋 Item Satuan")
            self._build_satuan_tab(self.satuan_frame)

            # ====== STATUS BAR ======
            self.status = tk.StringVar(value="Siap. Pilih file Excel lalu klik Analisa.")
            ttk.Label(
                self.root, textvariable=self.status, relief="sunken", anchor="w"
            ).pack(fill="x", side="bottom")

        # ---------- helpers ----------
        def _browse(self):
            p = filedialog.askopenfilename(
                title="Pilih file Excel",
                filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")],
            )
            if p:
                self.file_var.set(p)

        def _show_df(self, df: pd.DataFrame, frame: ttk.Frame, name: str):
            for w in frame.winfo_children():
                w.destroy()
            if df is None or df.empty:
                ttk.Label(frame, text="(tidak ada data)").pack(pady=20)
                return
            tv = ttk.Treeview(
                frame, columns=list(df.columns), show="headings", height=20
            )
            for c in df.columns:
                tv.heading(c, text=str(c))
                tv.column(c, width=130, anchor="w", stretch=False)
            # numeric format
            for _, r in df.iterrows():
                vals = []
                for v in r.values:
                    if pd.isna(v):
                        vals.append("")
                    elif isinstance(v, float):
                        vals.append(f"{v:,.2f}")
                    elif isinstance(v, pd.Timestamp):
                        vals.append(v.strftime("%Y-%m-%d"))
                    else:
                        vals.append(str(v))
                tv.insert("", "end", values=vals)
            vsb = ttk.Scrollbar(frame, orient="vertical", command=tv.yview)
            hsb = ttk.Scrollbar(frame, orient="horizontal", command=tv.xview)
            tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
            tv.grid(row=0, column=0, sticky="nsew")
            vsb.grid(row=0, column=1, sticky="ns")
            hsb.grid(row=1, column=0, sticky="we")
            frame.rowconfigure(0, weight=1)
            frame.columnconfigure(0, weight=1)
            self.tab_trees[name] = tv

        def _parse_loc_filter(self) -> list | None:
            txt = self.loc_var.get().strip()
            if not txt:
                return None
            return [x.strip() for x in txt.split(",") if x.strip()]

        def _on_preset_change(self):
            """Saat preset dipilih, auto-fill kolom tanggal (kecuali Custom)."""
            if self.analyzer.df is None:
                messagebox.showinfo(
                    "Info", "Pilih & load file Excel dulu sebelum pakai preset tanggal."
                )
                self.date_preset_combo.set("Semua data")
                return
            preset = self.date_preset_var.get()
            if preset == "Custom":
                return
            ref = pd.to_datetime(self.analyzer.df["FDATE"].max())
            presets = BundleAnalyzer.calc_date_presets(ref)
            start, end = presets.get(preset, (None, None))
            if start is None:
                self.date_from_var.set("")
                self.date_to_var.set("")
            else:
                self.date_from_var.set(pd.to_datetime(start).strftime("%Y-%m-%d"))
                self.date_to_var.set(pd.to_datetime(end).strftime("%Y-%m-%d"))

        def _get_date_range(self):
            """Ambil date range dari form. None = tanpa batas."""
            p = self.date_preset_var.get()
            if self.analyzer.df is not None and p != "Custom":
                ref = pd.to_datetime(self.analyzer.df["FDATE"].max())
                presets = BundleAnalyzer.calc_date_presets(ref)
                return presets.get(p, (None, None))
            # Custom: baca dari entry
            d1 = self.date_from_var.get().strip() or None
            d2 = self.date_to_var.get().strip() or None
            return (d1, d2)

        # ---------- actions ----------
        def _analyze(self):
            path = self.file_var.get().strip()
            if not path or not Path(path).exists():
                messagebox.showerror("Error", "File Excel tidak ditemukan.")
                return
            try:
                self.status.set("⏳ Memuat & menganalisa...")
                self.root.update_idletasks()

                self.analyzer.load(path)
                self.analyzer.classify(
                    min_items=self.min_items_var.get(),
                    min_discount=float(self.min_disc_var.get()),
                )
                self._populate_loc_combo()

                locs = self._parse_loc_filter()
                if locs:
                    self.analyzer.df = self.analyzer.df[
                        self.analyzer.df["FLOCCD"].astype(str).isin(locs)
                    ].copy()

                # Apply date filter
                d1, d2 = self._get_date_range()
                if d1 is not None:
                    self.analyzer.df = self.analyzer.df[
                        self.analyzer.df["FDATE"] >= pd.to_datetime(d1)
                    ].copy()
                if d2 is not None:
                    self.analyzer.df = self.analyzer.df[
                        self.analyzer.df["FDATE"]
                        <= pd.to_datetime(d2) + pd.Timedelta(hours=23, minutes=59, seconds=59)
                    ].copy()

                dfs = {
                    "Summary per Lokasi": self.analyzer.summary_by_location(),
                    "Distribusi Discount": self.analyzer.discount_distribution(),
                    "Detail Bundle": self.analyzer.bundle_detail(),
                    "Top Kombinasi Bundle": self.analyzer.top_bundles(20),
                }
                self.current_dfs = dfs
                for name, df in dfs.items():
                    self._show_df(df, self.tab_frames[name], name)

                n_b = int(self.analyzer.df["IS_BUNDLE"].sum())
                n_tx = int(
                    self.analyzer.df[self.analyzer.df["IS_BUNDLE"]]["NOTRAN"].nunique()
                )
                n_loc = self.analyzer.df["FLOCCD"].nunique()
                self.status.set(
                    f"✓ Selesai. {len(self.analyzer.df)} baris · "
                    f"{n_tx} transaksi bundle · {n_b} baris bundle · {n_loc} lokasi"
                )
            except Exception as e:
                messagebox.showerror("Error", f"Gagal analisa:\n{e}")
                self.status.set("✗ Error")

        def _export(self):
            if not self.current_dfs:
                messagebox.showwarning(
                    "Peringatan", "Belum ada hasil. Klik Analisa dulu."
                )
                return
            default_name = "bundle_analysis.xlsx"
            if self.file_var.get():
                default_name = (
                    Path(self.file_var.get()).stem + "_bundle_analysis.xlsx"
                )
            p = filedialog.asksaveasfilename(
                title="Simpan hasil analisa",
                defaultextension=".xlsx",
                initialfile=default_name,
                filetypes=[("Excel files", "*.xlsx")],
            )
            if not p:
                return
            try:
                with pd.ExcelWriter(p, engine="openpyxl") as w:
                    BundleAnalyzer._write_readme(w)
                    for name, df in self.current_dfs.items():
                        sheet = name.replace(" ", "_")[:31]
                        df.to_excel(w, sheet_name=sheet, index=False)
                self.status.set(f"✓ Tersimpan: {p}")
                messagebox.showinfo("Sukses", f"Hasil tersimpan di:\n{p}")
            except Exception as e:
                messagebox.showerror("Error", f"Gagal export:\n{e}")

        def _clear(self):
            self.file_var.set("")
            self.loc_var.set("")
            self.current_dfs = {}
            for f in self.tab_frames.values():
                for w in f.winfo_children():
                    w.destroy()
                ttk.Label(f, text="(belum ada data)").pack(pady=20)
            self.status.set("Siap.")

        def _show_help(self):
            """Buka window berisi PANDUAN.md (ter-embed di .exe)."""
            help_path = resource_path("PANDUAN.md")
            if not os.path.exists(help_path):
                messagebox.showerror(
                    "Error",
                    f"File PANDUAN.md tidak ditemukan di:\n{help_path}",
                )
                return
            try:
                with open(help_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                messagebox.showerror("Error", f"Gagal baca panduan:\n{e}")
                return
            win = tk.Toplevel(self.root)
            win.title("Panduan Bundle Sales Analyzer")
            win.geometry("900x650")
            txt = tk.Text(win, wrap="word", font=("Consolas", 10))
            vsb = ttk.Scrollbar(win, orient="vertical", command=txt.yview)
            txt.configure(yscrollcommand=vsb.set)
            txt.pack(side="left", fill="both", expand=True)
            vsb.pack(side="right", fill="y")
            txt.insert("1.0", content)
            txt.configure(state="disabled")

        # ===== TAB: CARI PAKET BY ITEM =====
        def _build_search_tab(self, parent):
            self.search_results_df: pd.DataFrame | None = None
            self.search_results_summary: dict | None = None

            # --- Form filter ---
            frm = ttk.LabelFrame(parent, text="Filter Pencarian Paket Bundle", padding=10)
            frm.pack(fill="x", padx=10, pady=10)

            ttk.Label(frm, text="Kode Lokasi (FLOCCD):").grid(row=0, column=0, sticky="w")
            self.search_loc_var = tk.StringVar()
            self.search_loc_combo = ttk.Combobox(
                frm, textvariable=self.search_loc_var, width=35
            )
            self.search_loc_combo.grid(row=0, column=1, sticky="w", padx=5)
            ttk.Label(
                frm,
                text="(ketik/kosongkan = semua lokasi)",
                foreground="gray",
            ).grid(row=0, column=2, sticky="w")

            ttk.Label(frm, text="Kode / Nama Item:").grid(
                row=1, column=0, sticky="w", pady=(8, 0)
            )
            self.search_item_var = tk.StringVar()
            ttk.Entry(frm, textvariable=self.search_item_var, width=40).grid(
                row=1, column=1, sticky="we", padx=5, pady=(8, 0)
            )
            ttk.Label(
                frm,
                text="(contoh: 64428, 'DURABEAM', 'PLAY')",
                foreground="gray",
            ).grid(row=1, column=2, sticky="w", pady=(8, 0))

            ttk.Label(frm, text="Dari Tanggal:").grid(
                row=2, column=0, sticky="w", pady=(8, 0)
            )
            self.search_date_from_var = tk.StringVar()
            ttk.Entry(frm, textvariable=self.search_date_from_var, width=15).grid(
                row=2, column=1, sticky="w", padx=5, pady=(8, 0)
            )
            ttk.Label(
                frm,
                text="(YYYY-MM-DD, kosongkan = tanpa batas awal)",
                foreground="gray",
            ).grid(row=2, column=2, sticky="w", pady=(8, 0))

            ttk.Label(frm, text="Sampai Tanggal:").grid(
                row=3, column=0, sticky="w", pady=(8, 0)
            )
            self.search_date_to_var = tk.StringVar()
            ttk.Entry(frm, textvariable=self.search_date_to_var, width=15).grid(
                row=3, column=1, sticky="w", padx=5, pady=(8, 0)
            )
            ttk.Label(
                frm,
                text="(YYYY-MM-DD, kosongkan = tanpa batas akhir)",
                foreground="gray",
            ).grid(row=3, column=2, sticky="w", pady=(8, 0))

            frm.columnconfigure(1, weight=1)

            # --- Tombol aksi ---
            btn_frm = ttk.Frame(parent, padding=(10, 0))
            btn_frm.pack(fill="x")
            ttk.Button(
                btn_frm, text="🔎 Cari Paket", command=self._do_search
            ).pack(side="left", padx=2)
            ttk.Button(
                btn_frm, text="Reset Pencarian", command=self._reset_search
            ).pack(side="left", padx=2)
            ttk.Button(
                btn_frm, text="💾 Export Hasil Pencarian", command=self._export_search
            ).pack(side="left", padx=2)

            # --- Ringkasan ---
            sum_frm = ttk.LabelFrame(parent, text="Ringkasan Hasil", padding=10)
            sum_frm.pack(fill="x", padx=10, pady=(10, 5))
            self.search_summary_var = tk.StringVar(
                value="Belum ada pencarian. Isi filter di atas lalu klik 'Cari Paket'."
            )
            ttk.Label(
                sum_frm,
                textvariable=self.search_summary_var,
                font=("Segoe UI", 10),
                justify="left",
            ).pack(anchor="w")

            # --- Tabel detail ---
            ttk.Label(
                parent,
                text="Detail Paket (1 baris = 1 paket, total JUMLAH = harga 1 paket):",
                padding=(10, 5, 0, 0),
            ).pack(anchor="w")

            tree_frm = ttk.Frame(parent)
            tree_frm.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            self.search_tree = ttk.Treeview(tree_frm, show="headings", height=15)
            vsb = ttk.Scrollbar(tree_frm, orient="vertical", command=self.search_tree.yview)
            hsb = ttk.Scrollbar(
                tree_frm, orient="horizontal", command=self.search_tree.xview
            )
            self.search_tree.configure(
                yscrollcommand=vsb.set, xscrollcommand=hsb.set
            )
            self.search_tree.grid(row=0, column=0, sticky="nsew")
            vsb.grid(row=0, column=1, sticky="ns")
            hsb.grid(row=1, column=0, sticky="we")
            tree_frm.rowconfigure(0, weight=1)
            tree_frm.columnconfigure(0, weight=1)

        def _ensure_loaded(self):
            """Pastikan data sudah dimuat (auto-load dari file_var jika perlu)."""
            if self.analyzer.df is not None:
                return True
            path = self.file_var.get().strip()
            if not path or not Path(path).exists():
                messagebox.showwarning(
                    "Peringatan",
                    "Belum ada data. Klik 'Browse' pilih file Excel dulu,\n"
                    "lalu klik 'Cari Paket' lagi.",
                )
                return False
            try:
                self.status.set("⏳ Memuat data...")
                self.root.update_idletasks()
                self.analyzer.load(path)
                self.analyzer.classify(
                    min_items=self.min_items_var.get(),
                    min_discount=float(self.min_disc_var.get()),
                )
                self._populate_loc_combo()
                self.status.set(
                    f"✓ Data dimuat ({len(self.analyzer.df)} baris)"
                )
                return True
            except Exception as e:
                messagebox.showerror("Error", f"Gagal load data:\n{e}")
                self.status.set("✗ Error")
                return False

        def _populate_loc_combo(self):
            if self.analyzer.df is None:
                return
            grouped = (
                self.analyzer.df.groupby("FLOCCD")["FNAMA"]
                .first()
                .reset_index()
                if "FNAMA" in self.analyzer.df.columns
                else None
            )
            opts = []
            if grouped is not None:
                for _, r in grouped.iterrows():
                    opts.append(f"{r['FLOCCD']}  -  {r['FNAMA']}")
            else:
                opts = [str(x) for x in self.analyzer.df["FLOCCD"].unique()]
            self.search_loc_combo["values"] = opts
            # Top Produk & Margin juga butuh combo lokasi
            if hasattr(self, "tp_loc_combo"):
                self.tp_loc_combo["values"] = opts
            if hasattr(self, "mg_loc_combo"):
                self.mg_loc_combo["values"] = opts

        def _parse_combo_loc(self) -> str | None:
            """Ambil FLOCCD dari combobox '55573 - Nama' → '55573'. None jika kosong."""
            raw = self.search_loc_var.get().strip()
            if not raw:
                return None
            # ambil token pertama sebelum tanda '-'
            return raw.split("-")[0].strip()

        def _do_search(self):
            if not self._ensure_loaded():
                return
            item = self.search_item_var.get().strip()
            if not item:
                messagebox.showerror("Error", "Kode/Nama item wajib diisi.")
                return
            loc = self._parse_combo_loc()
            d_from = self.search_date_from_var.get().strip() or None
            d_to = self.search_date_to_var.get().strip() or None
            # Validasi tanggal
            for d, label in [(d_from, "Dari"), (d_to, "Sampai")]:
                if d:
                    try:
                        pd.to_datetime(d)
                    except Exception:
                        messagebox.showerror(
                            "Error",
                            f"Format {label} tanggal salah.\nGunakan YYYY-MM-DD, mis. 2026-01-15.",
                        )
                        return

            try:
                self.status.set("⏳ Mencari paket...")
                self.root.update_idletasks()
                summary, packages = self.analyzer.search_bundles_by_item(
                    item, loc, d_from, d_to
                )
            except Exception as e:
                messagebox.showerror("Error", f"Pencarian gagal:\n{e}")
                self.status.set("✗ Error")
                return

            self.search_results_df = packages
            self.search_results_summary = summary
            self._render_search_results(summary, packages)
            self.status.set(
                f"✓ Pencarian selesai: {summary['Jumlah Paket']} paket, "
                f"total Rp {summary['Total Nilai (Rp)']:,.0f}"
            )

        def _render_search_results(self, summary: dict, packages: pd.DataFrame):
            # Ringkasan
            text = (
                f"📦 Jumlah Paket Bundle   : {summary['Jumlah Paket']:,} paket\n"
                f"💰 Total Nilai (JUMLAH)  : Rp {summary['Total Nilai (Rp)']:,.0f}\n"
                f"📊 Total QTY             : {summary['Total QTY']:,} unit\n"
                f"🏷  Rata-rata Diskon     : {summary['Rata-rata Diskon (%)']:.2f}%\n"
                f"📍 Lokasi filter         : {summary['Lokasi']}\n"
                f"📅 Periode               : {summary['Periode Dari']}  s.d.  {summary['Periode Sampai']}\n"
                f"🔎 Kata kunci            : '{summary['Kata Kunci']}'"
            )
            self.search_summary_var.set(text)

            # Tabel
            self.search_tree.delete(*self.search_tree.get_children())
            if packages.empty:
                self.search_tree["columns"] = ("Info",)
                self.search_tree.heading("Info", text="Info")
                self.search_tree.column("Info", width=400, anchor="w")
                self.search_tree.insert(
                    "", "end", values=("Tidak ada paket bundle yang cocok.",)
                )
                return

            cols = list(packages.columns)
            self.search_tree["columns"] = cols
            for c in cols:
                self.search_tree.heading(c, text=str(c))
                # kolom daftar item butuh lebar lebih
                w = 350 if c == "DAFTAR_ITEM" else 130
                self.search_tree.column(c, width=w, anchor="w", stretch=(c == "DAFTAR_ITEM"))
            for _, r in packages.iterrows():
                vals = []
                for v in r.values:
                    if pd.isna(v):
                        vals.append("")
                    elif isinstance(v, float):
                        vals.append(f"{v:,.2f}")
                    elif isinstance(v, (pd.Timestamp,)):
                        vals.append(v.strftime("%Y-%m-%d"))
                    else:
                        vals.append(str(v))
                self.search_tree.insert("", "end", values=vals)

        def _reset_search(self):
            self.search_item_var.set("")
            self.search_date_from_var.set("")
            self.search_date_to_var.set("")
            # tidak reset FLOCCD Combo (supaya tidak perlu pilih ulang)
            self.search_results_df = None
            self.search_results_summary = None
            self.search_summary_var.set(
                "Belum ada pencarian. Isi filter di atas lalu klik 'Cari Paket'."
            )
            self.search_tree.delete(*self.search_tree.get_children())
            self.search_tree["columns"] = ("Info",)
            self.search_tree.heading("Info", text="Info")
            self.search_tree.column("Info", width=400, anchor="w")
            self.search_tree.insert("", "end", values=("(kosong)",))
            self.status.set("Pencarian di-reset.")

        def _export_search(self):
            if self.search_results_df is None or self.search_results_df.empty:
                messagebox.showwarning(
                    "Peringatan", "Belum ada hasil pencarian. Klik 'Cari Paket' dulu."
                )
                return
            default_name = "bundle_search.xlsx"
            if self.search_item_var.get():
                slug = "".join(
                    c if c.isalnum() else "_"
                    for c in self.search_item_var.get().strip()
                )[:20]
                default_name = f"bundle_search_{slug}.xlsx"
            p = filedialog.asksaveasfilename(
                title="Simpan hasil pencarian",
                defaultextension=".xlsx",
                initialfile=default_name,
                filetypes=[("Excel files", "*.xlsx")],
            )
            if not p:
                return
            try:
                with pd.ExcelWriter(p, engine="openpyxl") as w:
                    # sheet ringkasan
                    if self.search_results_summary:
                        sm_df = pd.DataFrame(
                            list(self.search_results_summary.items()),
                            columns=["Metrik", "Nilai"],
                        )
                        sm_df.to_excel(w, sheet_name="Ringkasan", index=False)
                    self.search_results_df.to_excel(
                        w, sheet_name="Detail_Paket", index=False
                    )
                messagebox.showinfo("Sukses", f"Hasil tersimpan di:\n{p}")
                self.status.set(f"✓ Tersimpan: {p}")
            except Exception as e:
                messagebox.showerror("Error", f"Gagal export:\n{e}")

        # ===== TAB: PERBANDINGAN (VS) =====
        def _build_compare_tab(self, parent):
            self.compare_results: dict | None = None

            # Preset
            ttk.Label(parent, text="Preset Pembanding:").pack(
                anchor="w", padx=10, pady=(10, 2)
            )
            self.cmp_preset_var = tk.StringVar(value="Bulan ini vs Bulan lalu")
            self.cmp_preset_combo = ttk.Combobox(
                parent,
                textvariable=self.cmp_preset_var,
                values=[
                    "Bulan ini vs Bulan lalu",
                    "30 hari terakhir vs 30 hari sebelumnya",
                    "14 hari terakhir vs 14 hari sebelumnya",
                    "7 hari terakhir vs 7 hari sebelumnya",
                    "Quarter ini vs Quarter lalu",
                    "Custom (isi manual)",
                ],
                state="readonly", width=45,
            )
            self.cmp_preset_combo.pack(anchor="w", padx=10)
            self.cmp_preset_combo.bind("<<ComboboxSelected>>", lambda e: self._on_cmp_preset_change())

            # Frame untuk 2 periode
            pfrm = ttk.LabelFrame(parent, text="Periode (format YYYY-MM-DD)", padding=10)
            pfrm.pack(fill="x", padx=10, pady=10)

            ttk.Label(pfrm, text="Periode 1:").grid(row=0, column=0, sticky="w")
            ttk.Label(pfrm, text="Dari:").grid(row=0, column=1, sticky="e", padx=(20, 2))
            self.cmp_p1_from_var = tk.StringVar()
            ttk.Entry(pfrm, textvariable=self.cmp_p1_from_var, width=14).grid(row=0, column=2, sticky="w")
            ttk.Label(pfrm, text="Sampai:").grid(row=0, column=3, sticky="e", padx=(20, 2))
            self.cmp_p1_to_var = tk.StringVar()
            ttk.Entry(pfrm, textvariable=self.cmp_p1_to_var, width=14).grid(row=0, column=4, sticky="w")

            ttk.Label(pfrm, text="Periode 2:").grid(row=1, column=0, sticky="w", pady=(6, 0))
            ttk.Label(pfrm, text="Dari:").grid(row=1, column=1, sticky="e", padx=(20, 2), pady=(6, 0))
            self.cmp_p2_from_var = tk.StringVar()
            ttk.Entry(pfrm, textvariable=self.cmp_p2_from_var, width=14).grid(row=1, column=2, sticky="w", pady=(6, 0))
            ttk.Label(pfrm, text="Sampai:").grid(row=1, column=3, sticky="e", padx=(20, 2), pady=(6, 0))
            self.cmp_p2_to_var = tk.StringVar()
            ttk.Entry(pfrm, textvariable=self.cmp_p2_to_var, width=14).grid(row=1, column=4, sticky="w", pady=(6, 0))

            # Tombol
            btn_frm = ttk.Frame(parent, padding=(10, 0))
            btn_frm.pack(fill="x")
            ttk.Button(btn_frm, text="📊 Bandingkan", command=self._do_compare).pack(
                side="left", padx=2
            )
            ttk.Button(btn_frm, text="💾 Export Hasil", command=self._export_compare).pack(
                side="left", padx=2
            )

            # Subtabs untuk result
            self.cmp_nb = ttk.Notebook(parent)
            self.cmp_nb.pack(fill="both", expand=True, padx=10, pady=10)

            self.cmp_tab_summary = ttk.Frame(self.cmp_nb)
            self.cmp_nb.add(self.cmp_tab_summary, text="Ringkasan")
            self.cmp_summary_tree = ttk.Treeview(
                self.cmp_tab_summary, show="headings", height=10
            )
            vsb1 = ttk.Scrollbar(self.cmp_tab_summary, orient="vertical", command=self.cmp_summary_tree.yview)
            self.cmp_summary_tree.configure(yscrollcommand=vsb1.set)
            self.cmp_summary_tree.pack(side="left", fill="both", expand=True)
            vsb1.pack(side="right", fill="y")

            self.cmp_tab_lokasi = ttk.Frame(self.cmp_nb)
            self.cmp_nb.add(self.cmp_tab_lokasi, text="Per Lokasi")
            self.cmp_lokasi_tree = ttk.Treeview(
                self.cmp_tab_lokasi, show="headings", height=10
            )
            vsb2 = ttk.Scrollbar(self.cmp_tab_lokasi, orient="vertical", command=self.cmp_lokasi_tree.yview)
            hsb2 = ttk.Scrollbar(self.cmp_tab_lokasi, orient="horizontal", command=self.cmp_lokasi_tree.xview)
            self.cmp_lokasi_tree.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)
            self.cmp_lokasi_tree.pack(side="left", fill="both", expand=True)
            vsb2.pack(side="right", fill="y")

        def _on_cmp_preset_change(self):
            if self.analyzer.df is None:
                messagebox.showinfo("Info", "Load file Excel dulu.")
                self.cmp_preset_combo.set("Custom (isi manual)")
                return
            preset = self.cmp_preset_var.get()
            if preset == "Custom (isi manual)":
                return
            ref = pd.to_datetime(self.analyzer.df["FDATE"].max())
            presets = BundleAnalyzer.calc_comparison_presets(ref)
            v = presets.get(preset, (None, None, None, None))
            p1s, p1e, p2s, p2e = v
            if p1s is None:
                return
            self.cmp_p1_from_var.set(pd.to_datetime(p1s).strftime("%Y-%m-%d"))
            self.cmp_p1_to_var.set(pd.to_datetime(p1e).strftime("%Y-%m-%d"))
            self.cmp_p2_from_var.set(pd.to_datetime(p2s).strftime("%Y-%m-%d"))
            self.cmp_p2_to_var.set(pd.to_datetime(p2e).strftime("%Y-%m-%d"))

        def _do_compare(self):
            if not self._ensure_loaded():
                return
            # validate dates
            for var, label in [
                (self.cmp_p1_from_var, "P1 dari"),
                (self.cmp_p1_to_var, "P1 sampai"),
                (self.cmp_p2_from_var, "P2 dari"),
                (self.cmp_p2_to_var, "P2 sampai"),
            ]:
                if not var.get().strip():
                    messagebox.showerror("Error", f"{label} wajib diisi (pilih preset atau isi manual).")
                    return
                try:
                    pd.to_datetime(var.get().strip())
                except Exception:
                    messagebox.showerror("Error", f"Format {label} salah. Gunakan YYYY-MM-DD.")
                    return
            p1 = (self.cmp_p1_from_var.get().strip(), self.cmp_p1_to_var.get().strip())
            p2 = (self.cmp_p2_from_var.get().strip(), self.cmp_p2_to_var.get().strip())
            try:
                self.status.set("⏳ Membandingkan periode...")
                self.root.update_idletasks()
                summary_df = self.analyzer.compare_periods(*p1, *p2)
                lokasi_df = self.analyzer.compare_by_location(*p1, *p2)
            except Exception as e:
                messagebox.showerror("Error", f"Gagal bandingkan:\n{e}")
                self.status.set("✗ Error")
                return
            self.compare_results = {"summary": summary_df, "by_location": lokasi_df, "p1": p1, "p2": p2}
            self._render_compare(summary_df, lokasi_df)
            self.status.set("✓ Perbandingan selesai.")

        def _render_compare(self, summary_df, lokasi_df):
            # Summary tree
            self.cmp_summary_tree.delete(*self.cmp_summary_tree.get_children())
            cols = list(summary_df.columns)
            self.cmp_summary_tree["columns"] = cols
            for c in cols:
                self.cmp_summary_tree.heading(c, text=str(c))
                self.cmp_summary_tree.column(c, width=180, anchor="w")
            for _, r in summary_df.iterrows():
                vals = []
                for v in r.values:
                    if pd.isna(v):
                        vals.append("-")
                    elif isinstance(v, float):
                        vals.append(f"{v:,.2f}")
                    else:
                        vals.append(str(v))
                self.cmp_summary_tree.insert("", "end", values=vals)
            # Lokasi tree
            self.cmp_lokasi_tree.delete(*self.cmp_lokasi_tree.get_children())
            cols2 = list(lokasi_df.columns)
            self.cmp_lokasi_tree["columns"] = cols2
            for c in cols2:
                self.cmp_lokasi_tree.heading(c, text=str(c))
                self.cmp_lokasi_tree.column(c, width=130, anchor="w")
            for _, r in lokasi_df.iterrows():
                vals = []
                for v in r.values:
                    if pd.isna(v):
                        vals.append("-")
                    elif isinstance(v, float):
                        vals.append(f"{v:,.2f}")
                    else:
                        vals.append(str(v))
                self.cmp_lokasi_tree.insert("", "end", values=vals)

        def _export_compare(self):
            if not self.compare_results:
                messagebox.showwarning("Peringatan", "Belum ada hasil. Klik 'Bandingkan' dulu.")
                return
            p = filedialog.asksaveasfilename(
                title="Simpan hasil perbandingan",
                defaultextension=".xlsx",
                initialfile="bundle_comparison.xlsx",
                filetypes=[("Excel files", "*.xlsx")],
            )
            if not p:
                return
            try:
                with pd.ExcelWriter(p, engine="openpyxl") as w:
                    self.compare_results["summary"].to_excel(
                        w, sheet_name="Ringkasan_VS", index=False
                    )
                    self.compare_results["by_location"].to_excel(
                        w, sheet_name="Per_Lokasi_VS", index=False
                    )
                messagebox.showinfo("Sukses", f"Hasil tersimpan di:\n{p}")
                self.status.set(f"✓ Tersimpan: {p}")
            except Exception as e:
                messagebox.showerror("Error", f"Gagal export:\n{e}")

        # ===== TAB: TREND & CHART =====
        def _build_trend_tab(self, parent):
            frm = ttk.LabelFrame(parent, text="Pengaturan Chart", padding=10)
            frm.pack(fill="x", padx=10, pady=10)

            ttk.Label(frm, text="Dari:").grid(row=0, column=0, sticky="e", padx=(0, 2))
            self.tr_from_var = tk.StringVar()
            ttk.Entry(frm, textvariable=self.tr_from_var, width=14).grid(row=0, column=1, sticky="w")
            ttk.Label(frm, text="Sampai:").grid(row=0, column=2, sticky="e", padx=(20, 2))
            self.tr_to_var = tk.StringVar()
            ttk.Entry(frm, textvariable=self.tr_to_var, width=14).grid(row=0, column=3, sticky="w")

            ttk.Label(frm, text="Granularitas:").grid(row=0, column=4, sticky="e", padx=(30, 2))
            self.tr_gran_var = tk.StringVar(value="Harian")
            ttk.Combobox(
                frm, textvariable=self.tr_gran_var,
                values=["Harian", "Bulanan"], state="readonly", width=12,
            ).grid(row=0, column=5, sticky="w")

            ttk.Label(frm, text="Tampilkan:").grid(row=1, column=0, sticky="e", pady=(8, 0), padx=(0, 2))
            self.tr_metric_var = tk.StringVar(value="Revenue")
            ttk.Combobox(
                frm, textvariable=self.tr_metric_var,
                values=["Revenue", "Bundle Revenue", "Transaksi", "Bundle Transaksi"],
                state="readonly", width=18,
            ).grid(row=1, column=1, sticky="w", pady=(8, 0))

            ttk.Button(frm, text="📈 Generate Chart", command=self._do_trend).grid(
                row=1, column=5, sticky="e", padx=5, pady=(8, 0)
            )

            ttk.Label(
                frm, text="(kosongkan tanggal = semua data; sesuai filter di form utama)",
                foreground="gray",
            ).grid(row=2, column=0, columnspan=6, sticky="w", pady=(8, 0))

            # Container chart
            self.trend_chart_frame = ttk.Frame(parent)
            self.trend_chart_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

            # Tabel ringkasan di bawah chart
            ttk.Label(parent, text="Data Tabel:", padding=(10, 0)).pack(anchor="w")
            self.trend_tree_frame = ttk.Frame(parent)
            self.trend_tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            self.trend_tree = ttk.Treeview(
                self.trend_tree_frame, show="headings", height=6
            )
            trvsb = ttk.Scrollbar(self.trend_tree_frame, orient="vertical", command=self.trend_tree.yview)
            trhsb = ttk.Scrollbar(self.trend_tree_frame, orient="horizontal", command=self.trend_tree.xview)
            self.trend_tree.configure(yscrollcommand=trvsb.set, xscrollcommand=trhsb.set)
            self.trend_tree.pack(side="left", fill="both", expand=True)
            trvsb.pack(side="right", fill="y")

        def _do_trend(self):
            if not self._ensure_loaded():
                return
            d1 = self.tr_from_var.get().strip() or None
            d2 = self.tr_to_var.get().strip() or None
            for d, label in [(d1, "Dari"), (d2, "Sampai")]:
                if d:
                    try:
                        pd.to_datetime(d)
                    except Exception:
                        messagebox.showerror("Error", f"Format {label} salah.")
                        return
            gran = self.tr_gran_var.get()
            try:
                self.status.set("⏳ Generate chart...")
                self.root.update_idletasks()
                if gran == "Harian":
                    df = self.analyzer.daily_trend(d1, d2)
                    x_col, x_label = "DATE", "Tanggal"
                else:
                    df = self.analyzer.monthly_trend(d1, d2)
                    x_col, x_label = "YM", "Bulan"
            except Exception as e:
                messagebox.showerror("Error", f"Gagal generate:\n{e}")
                self.status.set("✗ Error")
                return
            if df.empty:
                messagebox.showinfo("Info", "Tidak ada data pada filter ini.")
                return
            self._render_trend_chart(df, x_col, x_label)
            self._render_trend_table(df)
            self.status.set(f"✓ Chart dibuat ({len(df)} titik data)")

        def _render_trend_chart(self, df, x_col, x_label):
            # bersihkan chart lama
            for w in self.trend_chart_frame.winfo_children():
                w.destroy()
            metric = self.tr_metric_var.get()
            metric_map = {
                "Revenue": ("Revenue", "Total Revenue (Rp)"),
                "Bundle Revenue": ("Bundle_Revenue", "Bundle Revenue (Rp)"),
                "Transaksi": ("TX", "Jumlah Transaksi"),
                "Bundle Transaksi": ("Bundle_TX", "Bundle Transaksi"),
            }
            y_col, y_label = metric_map.get(metric, ("Revenue", "Revenue"))
            fig = Figure(figsize=(10, 4), dpi=100)
            ax = fig.add_subplot(111)
            x_vals = pd.to_datetime(df[x_col]) if x_col == "DATE" else df[x_col]
            ax.plot(x_vals, df[y_col], marker="o", linewidth=2, color="#1f77b4", label=y_label)
            ax.fill_between(x_vals, df[y_col], alpha=0.2, color="#1f77b4")
            ax.set_title(f"Tren {y_label}", fontsize=12, fontweight="bold")
            ax.set_xlabel(x_label)
            ax.set_ylabel(y_label)
            ax.grid(True, alpha=0.3)
            ax.legend()
            if x_col == "DATE":
                fig.autofmt_xdate()
            fig.tight_layout()
            canvas = FigureCanvasTkAgg(fig, master=self.trend_chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)

        def _render_trend_table(self, df):
            self.trend_tree.delete(*self.trend_tree.get_children())
            cols = list(df.columns)
            self.trend_tree["columns"] = cols
            for c in cols:
                self.trend_tree.heading(c, text=str(c))
                self.trend_tree.column(c, width=130, anchor="w")
            for _, r in df.iterrows():
                vals = []
                for v in r.values:
                    if pd.isna(v):
                        vals.append("-")
                    elif isinstance(v, float):
                        vals.append(f"{v:,.2f}")
                    elif isinstance(v, pd.Timestamp):
                        vals.append(v.strftime("%Y-%m-%d"))
                    else:
                        vals.append(str(v))
                self.trend_tree.insert("", "end", values=vals)

        # ===== TAB: TOP PRODUK BUNDLE =====
        def _build_topprod_tab(self, parent):
            ttk.Label(parent, text="Item yang paling sering muncul di dalam bundle.",
                      padding=(10, 10, 0, 5)).pack(anchor="w")

            frm = ttk.LabelFrame(parent, text="Pengaturan", padding=10)
            frm.pack(fill="x", padx=10, pady=5)

            ttk.Label(frm, text="Lokasi (FLOCCD):").grid(row=0, column=0, sticky="w")
            self.tp_loc_var = tk.StringVar()
            self.tp_loc_combo = ttk.Combobox(frm, textvariable=self.tp_loc_var, width=35)
            self.tp_loc_combo.grid(row=0, column=1, sticky="w", padx=5)
            ttk.Label(frm, text="(kosongkan = semua)", foreground="gray").grid(
                row=0, column=2, sticky="w"
            )

            ttk.Label(frm, text="Top N:").grid(row=1, column=0, sticky="w", pady=(8, 0))
            self.tp_n_var = tk.IntVar(value=20)
            ttk.Spinbox(frm, from_=5, to=100, textvariable=self.tp_n_var, width=8).grid(
                row=1, column=1, sticky="w", padx=5, pady=(8, 0)
            )

            btn_frm = ttk.Frame(parent, padding=(10, 5))
            btn_frm.pack(fill="x")
            ttk.Button(
                btn_frm, text="🏆 Tampilkan Top Produk", command=self._do_topprod
            ).pack(side="left", padx=2)
            ttk.Button(
                btn_frm, text="💾 Export", command=self._export_topprod
            ).pack(side="left", padx=2)

            # Tabel utama: top produk
            ttk.Label(parent, text="Top Produk Bundle:", padding=(10, 5, 0, 0)).pack(anchor="w")
            tree_frm1 = ttk.Frame(parent)
            tree_frm1.pack(fill="both", expand=True, padx=10, pady=(0, 5))
            self.tp_tree = ttk.Treeview(tree_frm1, show="headings", height=10)
            tv1 = ttk.Scrollbar(tree_frm1, orient="vertical", command=self.tp_tree.yview)
            th1 = ttk.Scrollbar(tree_frm1, orient="horizontal", command=self.tp_tree.xview)
            self.tp_tree.configure(yscrollcommand=tv1.set, xscrollcommand=th1.set)
            self.tp_tree.grid(row=0, column=0, sticky="nsew")
            tv1.grid(row=0, column=1, sticky="ns")
            th1.grid(row=1, column=0, sticky="we")
            tree_frm1.rowconfigure(0, weight=1)
            tree_frm1.columnconfigure(0, weight=1)

            # Pencarian pasangan item
            ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=5)
            ttk.Label(
                parent,
                text="Cari item yang sering di-bundle bersama item tertentu:",
                padding=(10, 5, 0, 0),
            ).pack(anchor="w")

            pfrm = ttk.Frame(parent, padding=(10, 0, 10, 5))
            pfrm.pack(fill="x")
            ttk.Label(pfrm, text="Kode/Nama Item:").pack(side="left")
            self.tp_pair_var = tk.StringVar()
            ttk.Entry(pfrm, textvariable=self.tp_pair_var, width=30).pack(
                side="left", padx=5
            )
            ttk.Button(
                pfrm, text="🔎 Cari Pasangan", command=self._do_topprod_pair
            ).pack(side="left", padx=2)

            ttk.Label(parent, text="Item yang sering di-bundle bersama:", padding=(10, 0)).pack(
                anchor="w"
            )
            tree_frm2 = ttk.Frame(parent)
            tree_frm2.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            self.tp_pair_tree = ttk.Treeview(tree_frm2, show="headings", height=8)
            tv2 = ttk.Scrollbar(tree_frm2, orient="vertical", command=self.tp_pair_tree.yview)
            self.tp_pair_tree.configure(yscrollcommand=tv2.set)
            self.tp_pair_tree.pack(side="left", fill="both", expand=True)
            tv2.pack(side="right", fill="y")

            self.tp_results: pd.DataFrame | None = None
            self.tp_pair_results: pd.DataFrame | None = None

        def _do_topprod(self):
            if not self._ensure_loaded():
                return
            loc = self.tp_loc_var.get().strip() or None
            if loc and "-" in loc:
                loc = loc.split("-")[0].strip()
            try:
                self.status.set("⏳ Menghitung top produk...")
                self.root.update_idletasks()
                df = self.analyzer.top_products_in_bundles(
                    top_n=self.tp_n_var.get(), floocd=loc,
                )
            except Exception as e:
                messagebox.showerror("Error", f"Gagal:\n{e}")
                self.status.set("✗ Error")
                return
            self.tp_results = df
            self._render_tree(df, self.tp_tree)
            self.status.set(
                f"✓ Top {len(df)} produk bundle "
                f"(lokasi: {loc or 'semua'})"
            )

        def _do_topprod_pair(self):
            if not self._ensure_loaded():
                return
            q = self.tp_pair_var.get().strip()
            if not q:
                messagebox.showerror("Error", "Isi kode/nama item dulu.")
                return
            loc = self.tp_loc_var.get().strip() or None
            if loc and "-" in loc:
                loc = loc.split("-")[0].strip()
            try:
                self.status.set("⏳ Mencari pasangan item...")
                self.root.update_idletasks()
                df = self.analyzer.product_bundling_pairs(
                    q, top_n=self.tp_n_var.get(), floocd=loc,
                )
            except Exception as e:
                messagebox.showerror("Error", f"Gagal:\n{e}")
                self.status.set("✗ Error")
                return
            self.tp_pair_results = df
            self._render_tree(df, self.tp_pair_tree)
            if df.empty:
                self.status.set(f"Tidak ditemukan pasangan untuk '{q}'.")
            else:
                self.status.set(
                    f"✓ Ditemukan {len(df)} pasangan untuk '{q}'"
                )

        def _render_tree(self, df, tree):
            tree.delete(*tree.get_children())
            if df is None or df.empty:
                tree["columns"] = ("Info",)
                tree.heading("Info", text="Info")
                tree.column("Info", width=400, anchor="w")
                tree.insert("", "end", values=("(tidak ada data)",))
                return
            cols = list(df.columns)
            tree["columns"] = cols
            for c in cols:
                tree.heading(c, text=str(c))
                w = 320 if c in ("NAMA_BRG",) else 130
                tree.column(c, width=w, anchor="w")
            for _, r in df.iterrows():
                vals = []
                for v in r.values:
                    if pd.isna(v):
                        vals.append("-")
                    elif isinstance(v, float):
                        vals.append(f"{v:,.2f}")
                    elif isinstance(v, pd.Timestamp):
                        vals.append(v.strftime("%Y-%m-%d"))
                    else:
                        vals.append(str(v))
                tree.insert("", "end", values=vals)

        def _export_topprod(self):
            if (self.tp_results is None or self.tp_results.empty) and \
               (self.tp_pair_results is None or self.tp_pair_results.empty):
                messagebox.showwarning("Peringatan", "Belum ada hasil.")
                return
            p = filedialog.asksaveasfilename(
                title="Simpan top produk",
                defaultextension=".xlsx",
                initialfile="top_produk_bundle.xlsx",
                filetypes=[("Excel files", "*.xlsx")],
            )
            if not p:
                return
            try:
                with pd.ExcelWriter(p, engine="openpyxl") as w:
                    if self.tp_results is not None and not self.tp_results.empty:
                        self.tp_results.to_excel(w, sheet_name="Top_Produk", index=False)
                    if self.tp_pair_results is not None and not self.tp_pair_results.empty:
                        self.tp_pair_results.to_excel(w, sheet_name="Pasangan_Item", index=False)
                messagebox.showinfo("Sukses", f"Hasil tersimpan di:\n{p}")
                self.status.set(f"✓ Tersimpan: {p}")
            except Exception as e:
                messagebox.showerror("Error", f"Gagal export:\n{e}")

        def _populate_topprod_loc(self):
            """Populate the Top Produk tab's location combo (reuse analyzer data)."""
            if self.analyzer.df is None:
                return
            opts = []
            if "FNAMA" in self.analyzer.df.columns:
                grouped = self.analyzer.df.groupby("FLOCCD")["FNAMA"].first()
                for code, nama in grouped.items():
                    opts.append(f"{code}  -  {nama}")
            else:
                opts = [str(x) for x in self.analyzer.df["FLOCCD"].unique()]
            self.tp_loc_combo["values"] = opts

        # ===== TAB: ANALISA MARGIN =====
        def _build_margin_tab(self, parent):
            ttk.Label(
                parent,
                text=("Hitung profit/margin penjualan. "
                      "Catatan: kolom PRC_HIP di file ini kemungkinan PLACEHOLDER, "
                      "gunakan asumsi biaya di bawah untuk hasil yang lebih akurat."),
                padding=(10, 10, 0, 5), foreground="gray", wraplength=1100,
            ).pack(anchor="w")

            frm = ttk.LabelFrame(parent, text="Pengaturan Margin", padding=10)
            frm.pack(fill="x", padx=10, pady=5)

            ttk.Label(frm, text="Lokasi (FLOCCD):").grid(row=0, column=0, sticky="w")
            self.mg_loc_var = tk.StringVar()
            self.mg_loc_combo = ttk.Combobox(frm, textvariable=self.mg_loc_var, width=35)
            self.mg_loc_combo.grid(row=0, column=1, sticky="w", padx=5)
            ttk.Label(frm, text="(kosongkan = semua)", foreground="gray").grid(
                row=0, column=2, sticky="w"
            )

            ttk.Label(frm, text="Asumsi biaya (% dari JUALAHIR):").grid(
                row=1, column=0, sticky="w", pady=(8, 0)
            )
            self.mg_cost_var = tk.StringVar()
            ttk.Entry(frm, textvariable=self.mg_cost_var, width=10).grid(
                row=1, column=1, sticky="w", padx=5, pady=(8, 0)
            )
            ttk.Label(
                frm,
                text="(kosongkan = pakai PRC_HIP; isi 30 artinya biaya 30% dari harga jual)",
                foreground="gray",
            ).grid(row=1, column=2, sticky="w", pady=(8, 0))

            btn_frm = ttk.Frame(parent, padding=(10, 5))
            btn_frm.pack(fill="x")
            ttk.Button(
                btn_frm, text="💰 Hitung Margin", command=self._do_margin
            ).pack(side="left", padx=2)
            ttk.Button(
                btn_frm, text="💾 Export", command=self._export_margin
            ).pack(side="left", padx=2)

            # Summary box
            self.mg_summary_var = tk.StringVar(value="Belum dihitung.")
            sum_frm = ttk.LabelFrame(parent, text="Ringkasan Bundle vs Non-Bundle", padding=10)
            sum_frm.pack(fill="x", padx=10, pady=5)
            ttk.Label(
                sum_frm, textvariable=self.mg_summary_var,
                font=("Segoe UI", 10), justify="left",
            ).pack(anchor="w")

            # Per lokasi table
            ttk.Label(parent, text="Per Lokasi:", padding=(10, 5, 0, 0)).pack(anchor="w")
            tree_frm = ttk.Frame(parent)
            tree_frm.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            self.mg_tree = ttk.Treeview(tree_frm, show="headings", height=12)
            mv = ttk.Scrollbar(tree_frm, orient="vertical", command=self.mg_tree.yview)
            mh = ttk.Scrollbar(tree_frm, orient="horizontal", command=self.mg_tree.xview)
            self.mg_tree.configure(yscrollcommand=mv.set, xscrollcommand=mh.set)
            self.mg_tree.grid(row=0, column=0, sticky="nsew")
            mv.grid(row=0, column=1, sticky="ns")
            mh.grid(row=1, column=0, sticky="we")
            tree_frm.rowconfigure(0, weight=1)
            tree_frm.columnconfigure(0, weight=1)

            self.mg_summary = None
            self.mg_per_loc = None
            self.mg_dq = None

        def _do_margin(self):
            if not self._ensure_loaded():
                return
            loc = self.mg_loc_var.get().strip() or None
            if loc and "-" in loc:
                loc = loc.split("-")[0].strip()
            cost_str = self.mg_cost_var.get().strip()
            cost_assumption = None
            if cost_str:
                try:
                    cost_assumption = float(cost_str)
                    if not (0 <= cost_assumption <= 100):
                        raise ValueError
                except ValueError:
                    messagebox.showerror("Error", "Asumsi biaya harus angka 0-100.")
                    return
            try:
                self.status.set("⏳ Menghitung margin...")
                self.root.update_idletasks()
                summary, per_loc, dq = self.analyzer.margin_analysis(
                    floocd=loc, cost_pct_assumption=cost_assumption,
                )
            except Exception as e:
                messagebox.showerror("Error", f"Gagal:\n{e}")
                self.status.set("✗ Error")
                return
            self.mg_summary = summary
            self.mg_per_loc = per_loc
            self.mg_dq = dq
            # Render summary
            warn = ""
            if dq.get("placeholder_detected") and not dq.get("using_assumption"):
                warn = "\n⚠️  PRC_HIP di data terlihat PLACEHOLDER — hasil margin mungkin tidak akurat."
            b = summary.get("Bundle", {})
            nb = summary.get("Non-Bundle", {})
            text = (
                f"📦 BUNDLE\n"
                f"   Revenue   : Rp {b.get('Total Revenue (Rp)', 0):,.0f}\n"
                f"   Cost      : Rp {b.get('Total Cost (Rp)', 0):,.0f}\n"
                f"   Margin    : Rp {b.get('Total Margin (Rp)', 0):,.0f}  ({b.get('Avg Margin %', 0):.2f}%)\n"
                f"   QTY       : {b.get('Total QTY', 0):,}\n\n"
                f"📋 NON-BUNDLE\n"
                f"   Revenue   : Rp {nb.get('Total Revenue (Rp)', 0):,.0f}\n"
                f"   Cost      : Rp {nb.get('Total Cost (Rp)', 0):,.0f}\n"
                f"   Margin    : Rp {nb.get('Total Margin (Rp)', 0):,.0f}  ({nb.get('Avg Margin %', 0):.2f}%)\n"
                f"   QTY       : {nb.get('Total QTY', 0):,}\n"
                f"{warn}"
            )
            self.mg_summary_var.set(text)
            self._render_tree(per_loc, self.mg_tree)
            self.status.set("✓ Margin dihitung.")

        def _export_margin(self):
            if self.mg_per_loc is None:
                messagebox.showwarning("Peringatan", "Belum ada hasil.")
                return
            p = filedialog.asksaveasfilename(
                title="Simpan analisa margin",
                defaultextension=".xlsx",
                initialfile="margin_analysis.xlsx",
                filetypes=[("Excel files", "*.xlsx")],
            )
            if not p:
                return
            try:
                with pd.ExcelWriter(p, engine="openpyxl") as w:
                    if self.mg_summary:
                        rows = []
                        for label, m in self.mg_summary.items():
                            for k, v in m.items():
                                rows.append({"Kategori": label, "Metrik": k, "Nilai": v})
                        sm_df = pd.DataFrame(rows)
                        sm_df.to_excel(w, sheet_name="Ringkasan", index=False)
                    self.mg_per_loc.to_excel(w, sheet_name="Per_Lokasi", index=False)
                messagebox.showinfo("Sukses", f"Hasil tersimpan di:\n{p}")
                self.status.set(f"✓ Tersimpan: {p}")
            except Exception as e:
                messagebox.showerror("Error", f"Gagal export:\n{e}")

        # ===== TAB: ITEM SATUAN (NON-BUNDLE) =====
        def _build_satuan_tab(self, parent):
            frm = ttk.LabelFrame(parent, text="Pengaturan", padding=10)
            frm.pack(fill="x", padx=10, pady=10)

            ttk.Label(frm, text="Lokasi (FLOCCD):").grid(row=0, column=0, sticky="w")
            self.sn_loc_var = tk.StringVar()
            self.sn_loc_combo = ttk.Combobox(frm, textvariable=self.sn_loc_var, width=35)
            self.sn_loc_combo.grid(row=0, column=1, sticky="w", padx=5)
            ttk.Label(frm, text="(kosongkan = semua)", foreground="gray").grid(
                row=0, column=2, sticky="w"
            )

            ttk.Label(frm, text="Top N (untuk Top Item):").grid(
                row=1, column=0, sticky="w", pady=(8, 0)
            )
            self.sn_n_var = tk.IntVar(value=20)
            ttk.Spinbox(frm, from_=5, to=100, textvariable=self.sn_n_var, width=8).grid(
                row=1, column=1, sticky="w", padx=5, pady=(8, 0)
            )

            btn_frm = ttk.Frame(parent, padding=(10, 0))
            btn_frm.pack(fill="x")
            ttk.Button(
                btn_frm, text="📊 Tampilkan Semua", command=self._do_satuan_all
            ).pack(side="left", padx=2)
            ttk.Button(
                btn_frm, text="🔍 Cari Item", command=self._do_satuan_search
            ).pack(side="left", padx=2)
            ttk.Button(
                btn_frm, text="💾 Export", command=self._export_satuan
            ).pack(side="left", padx=2)

            # Frame ringkasan kecil di atas
            self.sn_summary_var = tk.StringVar(
                value="Klik 'Tampilkan Semua' untuk analisa item satuan."
            )
            sum_frm = ttk.LabelFrame(parent, text="Ringkasan", padding=10)
            sum_frm.pack(fill="x", padx=10, pady=(10, 5))
            ttk.Label(
                sum_frm, textvariable=self.sn_summary_var,
                font=("Segoe UI", 10), justify="left",
            ).pack(anchor="w")

            # Sub-tabs pakai Notebook
            self.sn_nb = ttk.Notebook(parent)
            self.sn_nb.pack(fill="both", expand=True, padx=10, pady=10)

            self.sn_tabs = {
                "Ringkasan per Lokasi": ttk.Frame(self.sn_nb),
                "Detail": ttk.Frame(self.sn_nb),
                "Top Item": ttk.Frame(self.sn_nb),
                "Dist. Diskon": ttk.Frame(self.sn_nb),
                "Pencarian": ttk.Frame(self.sn_nb),
            }
            for name, fr in self.sn_tabs.items():
                self.sn_nb.add(fr, text=name)

            # Masing-masing sub-tab punya tree
            self.sn_trees = {}
            for name, fr in self.sn_tabs.items():
                tv = ttk.Treeview(fr, show="headings", height=15)
                vsb = ttk.Scrollbar(fr, orient="vertical", command=tv.yview)
                hsb = ttk.Scrollbar(fr, orient="horizontal", command=tv.xview)
                tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
                tv.grid(row=0, column=0, sticky="nsew")
                vsb.grid(row=0, column=1, sticky="ns")
                hsb.grid(row=1, column=0, sticky="we")
                fr.rowconfigure(0, weight=1)
                fr.columnconfigure(0, weight=1)
                self.sn_trees[name] = tv

            # Search input area di tab "Pencarian"
            sfrm = ttk.Frame(self.sn_tabs["Pencarian"], padding=10)
            sfrm.grid(row=0, column=0, columnspan=2, sticky="we")
            ttk.Label(sfrm, text="Cari kode/nama item:").grid(row=0, column=0, sticky="w")
            self.sn_search_item_var = tk.StringVar()
            ttk.Entry(sfrm, textvariable=self.sn_search_item_var, width=30).grid(
                row=0, column=1, sticky="w", padx=5
            )

            # Container hasil
            self.sn_results = {
                "ringkasan": None,
                "detail": None,
                "top": None,
                "dist": None,
                "search": None,
            }

        def _parse_satuan_loc(self) -> str | None:
            raw = self.sn_loc_var.get().strip()
            if not raw:
                return None
            if "-" in raw:
                return raw.split("-")[0].strip()
            return raw

        def _do_satuan_all(self):
            if not self._ensure_loaded():
                return
            loc = self._parse_satuan_loc()
            try:
                self.status.set("⏳ Menghitung item satuan...")
                self.root.update_idletasks()
                sm = self.analyzer.summary_single_items(floocd=loc)
                det = self.analyzer.detail_single_items(floocd=loc)
                top = self.analyzer.top_single_items(
                    top_n=self.sn_n_var.get(), floocd=loc,
                )
                dist = self.analyzer.single_item_discount_dist(floocd=loc)
            except Exception as e:
                messagebox.showerror("Error", f"Gagal:\n{e}")
                self.status.set("✗ Error")
                return
            self.sn_results.update({
                "ringkasan": sm, "detail": det, "top": top, "dist": dist,
            })
            for name, df in [
                ("Ringkasan per Lokasi", sm),
                ("Detail", det),
                ("Top Item", top),
                ("Dist. Diskon", dist),
            ]:
                self._render_tree(df, self.sn_trees[name])

            n_tx = sm["TOTAL_TX"].sum() if not sm.empty else 0
            n_qty = sm["TOTAL_QTY"].sum() if not sm.empty else 0
            n_rev = sm["TOTAL_REVENUE"].sum() if not sm.empty else 0
            self.sn_summary_var.set(
                f"📊 {len(sm)} lokasi · {n_tx:,} transaksi satuan · "
                f"{n_qty:,} QTY · Rp {n_rev:,.0f} revenue"
            )
            self.status.set(f"✓ Item satuan: {len(det):,} baris")

        def _do_satuan_search(self):
            if not self._ensure_loaded():
                return
            q = self.sn_search_item_var.get().strip()
            if not q:
                messagebox.showerror("Error", "Isi kode/nama item dulu.")
                return
            loc = self._parse_satuan_loc()
            try:
                self.status.set("⏳ Mencari item satuan...")
                self.root.update_idletasks()
                summary, packages = self.analyzer.search_single_items_by_item(q, floocd=loc)
            except Exception as e:
                messagebox.showerror("Error", f"Gagal:\n{e}")
                self.status.set("✗ Error")
                return
            self.sn_results["search"] = packages
            self._render_tree(packages, self.sn_trees["Pencarian"])
            self.sn_nb.select(self.sn_tabs["Pencarian"])
            if packages.empty:
                self.status.set(f"Tidak ada item satuan cocok '{q}'.")
            else:
                self.status.set(f"✓ Ditemukan {len(packages)} baris untuk '{q}'")

        def _export_satuan(self):
            non_empty = {
                k: v for k, v in self.sn_results.items() if v is not None and not v.empty
            }
            if not non_empty:
                messagebox.showwarning(
                    "Peringatan", "Belum ada hasil. Klik 'Tampilkan Semua' dulu."
                )
                return
            p = filedialog.asksaveasfilename(
                title="Simpan analisa item satuan",
                defaultextension=".xlsx",
                initialfile="item_satuan_analysis.xlsx",
                filetypes=[("Excel files", "*.xlsx")],
            )
            if not p:
                return
            try:
                with pd.ExcelWriter(p, engine="openpyxl") as w:
                    sheet_map = {
                        "ringkasan": "Ringkasan_Satuan",
                        "detail": "Detail_Satuan",
                        "top": "Top_Item_Satuan",
                        "dist": "Dist_Diskon_Satuan",
                        "search": "Pencarian_Item",
                    }
                    for k, df in non_empty.items():
                        df.to_excel(w, sheet_name=sheet_map[k], index=False)
                messagebox.showinfo("Sukses", f"Hasil tersimpan di:\n{p}")
                self.status.set(f"✓ Tersimpan: {p}")
            except Exception as e:
                messagebox.showerror("Error", f"Gagal export:\n{e}")

    root = tk.Tk()
    App(root)
    root.mainloop()


# =====================================================================
# ENTRYPOINT
# =====================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Bundle Sales Analyzer - deteksi & analisa penjualan paket."
    )
    parser.add_argument("--cli", metavar="FILE", help="Jalankan mode CLI dengan file ini")
    parser.add_argument("--out", default="bundle_analysis.xlsx", help="File output Excel")
    parser.add_argument("--min-items", type=int, default=2, help="Min item per bundle")
    parser.add_argument(
        "--min-discount", type=float, default=0.0, help="Min discount %% (default 0)"
    )
    args = parser.parse_args()

    if args.cli:
        run_cli(args.cli, args.out, args.min_items, args.min_discount)
    else:
        run_gui()
