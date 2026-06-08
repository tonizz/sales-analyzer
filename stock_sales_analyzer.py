"""
Stock & Sales Analyzer
======================
Menganalisa file 'stock & sales all (4).xlsx' (2 sheets):
  - 'Penjualan Jan-May 2026 (2)': transaksi penjualan harian
  - 'DBS'                          : snapshot stock + sales per item per lokasi

6 fitur utama:
  1. Stock coverage (days of inventory)
  2. Stockout risk detection
  3. Margin analysis dengan Cost real (bukan placeholder)
  4. Dead stock per lokasi × SPV
  5. Cross-brand bundle (INTEX + RBO + HERO KIDS)
  6. Reorder recommendations
Plus:
  7. Discount audit (anomali diskon)
  8. Anomaly detection (stock negatif, TO negatif, dll)

Output: Excel multi-sheet (satu sheet per analisis + summary + anomalies)

Cara pakai (Python):
    from stock_sales_analyzer import StockSalesAnalyzer
    a = StockSalesAnalyzer()
    a.load("stock & sales all (4).xlsx")
    a.export_excel("hasil_analisa.xlsx")

Cara pakai (CLI):
    python run_stock_sales.py "stock & sales all (4).xlsx" -o hasil_analisa.xlsx

NOTE: File ini berdiri sendiri (standalone), TIDAK mengubah bundle_analyzer.py
      atau bundle_analyzer_web.py. Aman dipakai paralel dengan analyzer lama.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


# Konstanta schema
SHEET_PENJUALAN = "Penjualan Jan-May 2026 (2)"
SHEET_DBS = "DBS"

# Batas-batas untuk klasifikasi
STOCKOUT_RISK_DAYS = 14       # < 14 hari = risiko stockout
HEALTHY_MIN_DAYS = 30         # 30-90 hari = sehat
HEALTHY_MAX_DAYS = 90
OVERSTOCK_DAYS = 180          # > 180 hari = overstock
STOP_ORDER_TO = 0.5           # TO < 0.5 = slow, stop order
URGENT_REORDER_TO = 3.0       # TO > 3 = urgent reorder
DEAD_STOCK_SALES_MAX = 0      # sales <= 0 = dead


class StockSalesAnalyzer:
    """Analyzer untuk file stock & sales 2-sheet (Penjualan + DBS)."""

    def __init__(self):
        self.sales_df: pd.DataFrame | None = None
        self.stock_df: pd.DataFrame | None = None
        self.filepath: str | None = None

    # ========================================================================
    # LOADER
    # ========================================================================
    def load(self, filepath: str) -> "StockSalesAnalyzer":
        """Load + normalize kedua sheet, attach ke self.sales_df & self.stock_df.
        Return self untuk chaining: a.load(...).export_excel(...).
        """
        self.filepath = filepath
        self.sales_df = self._load_penjualan(filepath)
        self.stock_df = self._load_dbs(filepath)
        return self

    def _load_penjualan(self, filepath: str) -> pd.DataFrame:
        raw = pd.read_excel(filepath, sheet_name=SHEET_PENJUALAN)
        raw = raw.loc[:, ~raw.columns.str.startswith("Unnamed")]
        df = pd.DataFrame({
            "FDATE": pd.to_datetime(raw["TGL"].astype(str), format="%Y%m%d"),
            "FLOCCD": raw["KODELOK"].astype(str),
            "FNAMA": raw["NAMALOK"],
            "PLU": raw["PLU"],
            "NAMA_BRG": raw["NAMA_BRG"],
            "QTY": raw["QTY"],
            "JUALAHIR": raw["SELL"],
            "DISC": raw["DISC"],
            "JUMLAH": raw["NET"],
            "NET_PPN": raw["NET - PPN"],
            "BULAN": raw["Bulan"],
            "BRAND": raw["Produk"],
            "UB": raw["UB"],
            "DIVISI": raw["Divisi"],
            "AREA": raw["Area"],
            "MARKET_TYPE": raw["Modelan Market"],
            "SPV": raw["SPV"],
            "STATUS": raw["Keterangan"],
        })
        # Derived
        df["DISC_PCT"] = np.where(
            df["JUALAHIR"] > 0,
            df["DISC"] / df["JUALAHIR"] * 100,
            0.0,
        ).round(2)
        # Proxy untuk NOTRAN: (lokasi, tanggal). 1 TX_KEY = "keranjang belanja"
        df["TX_KEY"] = (
            df["FLOCCD"].astype(str) + "_" + df["FDATE"].dt.strftime("%Y%m%d")
        )
        df["LINE_REVENUE_GROSS"] = df["JUALAHIR"] * df["QTY"]
        df["LINE_REVENUE_NET"] = df["JUMLAH"] * df["QTY"]
        return df

    def _load_dbs(self, filepath: str) -> pd.DataFrame:
        raw = pd.read_excel(filepath, sheet_name=SHEET_DBS)
        raw = raw.loc[:, ~raw.columns.str.startswith("Unnamed")]
        df = pd.DataFrame({
            "FLOCCD": raw["LOKASI"].astype(str),
            "FNAMA": raw["NAMALOK"],
            "PLU": raw["PLU"],
            "ITEM_CODE": pd.to_numeric(raw["Item"], errors="coerce"),
            "NAMA_BRG": raw["NAMA_BRG"],
            "COST": raw["Cost"],
            "RSP": raw["RSP"],
            "STOCK_AWAL": raw["Stock Awal"],
            "TR": raw["TR"],
            "KR": raw["KR"],
            "UP": raw["UP"],
            "BS": raw["BS"],
            "SALES": raw["sales"],
            "STOCK": raw["Stock"],
            "QTY_FISIK": pd.to_numeric(raw["qty Fisik"], errors="coerce"),
            "DIFF_QTY": raw["Diff QTY"],
            "T_COST": raw["T.Cost"],
            "T_RSP": raw["T.RSP"],
            "BRAND": raw["Produk"],
            "UB": raw["UB"],
            "DIVISI": raw["Divisi"],
            "WILAYAH": raw["Wilayah"],
            "MARKET_TYPE": raw["Modelan Market"],
            "SPV": raw["SPV"],
            "JAN": raw["January"],
            "FEB": raw["February"],
            "MAR": raw["March"],
            "APR": raw["April"],
            "MAY": raw["May"],
            "JUN": raw["June"],
            "SALES_JAN_JUN": raw["Sales Jan - Jun'26"],
            "AVG": raw["AVG"],
            "TO": raw["TO"],
            "T_COST_REAL": raw["T.Cost.1"],
            "STATUS": raw["Keterangan"],
        })
        return df

    # ========================================================================
    # 1+2. STOCK COVERAGE & STOCKOUT RISK
    # ========================================================================
    def stock_coverage(self) -> pd.DataFrame:
        """Days of inventory per item per lokasi.
        Coverage = Stock / (Sales / Active_Days).
        """
        self._check_loaded()
        # Hitung active days & total sales per (FLOCCD, PLU) dari sheet Penjualan
        sales_agg = self.sales_df.groupby(["FLOCCD", "PLU"], as_index=False).agg(
            ACTIVE_DAYS=("FDATE", "nunique"),
            TOTAL_QTY_SOLD=("QTY", "sum"),
        )
        merged = self.stock_df.merge(
            sales_agg, on=["FLOCCD", "PLU"], how="left"
        ).fillna({"ACTIVE_DAYS": 0, "TOTAL_QTY_SOLD": 0})
        merged["ACTIVE_DAYS"] = merged["ACTIVE_DAYS"].astype(int)
        merged["AVG_DAILY_SALES"] = np.where(
            merged["ACTIVE_DAYS"] > 0,
            merged["TOTAL_QTY_SOLD"] / merged["ACTIVE_DAYS"],
            0.0,
        ).round(3)
        merged["DAYS_OF_INVENTORY"] = np.where(
            merged["AVG_DAILY_SALES"] > 0,
            merged["STOCK"] / merged["AVG_DAILY_SALES"],
            np.inf,
        ).round(1)
        merged["COVERAGE_STATUS"] = merged["DAYS_OF_INVENTORY"].apply(
            self._classify_coverage
        )
        out = merged[[
            "FLOCCD", "FNAMA", "PLU", "NAMA_BRG", "BRAND", "UB", "DIVISI",
            "STOCK", "STOCK_AWAL", "SALES", "ACTIVE_DAYS", "AVG_DAILY_SALES",
            "DAYS_OF_INVENTORY", "COVERAGE_STATUS",
        ]].sort_values("DAYS_OF_INVENTORY").reset_index(drop=True)
        return out

    @staticmethod
    def _classify_coverage(d) -> str:
        if isinstance(d, float) and np.isinf(d):
            return "NO_SALES"
        if d < 0:
            return "NEG_STOCK"
        if d < STOCKOUT_RISK_DAYS:
            return "STOCKOUT_RISK"
        if d < HEALTHY_MIN_DAYS:
            return "LOW"
        if d <= HEALTHY_MAX_DAYS:
            return "HEALTHY"
        if d <= OVERSTOCK_DAYS:
            return "HIGH"
        return "OVERSTOCK"

    def stockout_risk(self, top_n: int = 100) -> pd.DataFrame:
        """Item berisiko stockout: coverage < 14 hari DAN ada sales velocity.
        Output diurutkan dari yang paling kritis (coverage terkecil, sales velocity tertinggi)."""
        self._check_loaded()
        cov = self.stock_coverage()
        risky = cov[
            (cov["COVERAGE_STATUS"] == "STOCKOUT_RISK")
            & (cov["AVG_DAILY_SALES"] > 0)
        ].copy()
        # Risk score: makin tinggi velocity + makin rendah coverage = makin kritis
        risky["RISK_SCORE"] = (
            risky["AVG_DAILY_SALES"] / (risky["DAYS_OF_INVENTORY"] + 1)
        ).round(3)
        return risky.sort_values(
            ["DAYS_OF_INVENTORY", "AVG_DAILY_SALES"],
            ascending=[True, False],
        ).head(top_n).reset_index(drop=True)

    # ========================================================================
    # 3. ACCURATE MARGIN (pakai Cost real dari DBS)
    # ========================================================================
    def margin_analysis_real(self) -> dict:
        """Hitung margin dengan COST REAL dari DBS (bukan placeholder).
        Returns dict: {summary, per_brand, per_divisi, per_area, per_spv}
        """
        self._check_loaded()
        # Join sales dengan cost
        cost_lookup = self.stock_df[["FLOCCD", "PLU", "COST", "RSP", "BRAND"]].drop_duplicates(
            subset=["FLOCCD", "PLU"]
        )
        merged = self.sales_df.merge(
            cost_lookup, on=["FLOCCD", "PLU"], how="left", suffixes=("", "_DBS")
        )
        # Cost bisa null jika PLU ada di sales tapi tidak ada di DBS (edge case)
        merged["EFF_COST"] = merged["COST"].fillna(merged["JUALAHIR"] * 0.7)
        merged["MARGIN_UNIT"] = merged["JUALAHIR"] - merged["EFF_COST"]
        merged["MARGIN_TOTAL"] = merged["MARGIN_UNIT"] * merged["QTY"]
        merged["MARGIN_PCT"] = np.where(
            merged["JUALAHIR"] > 0,
            merged["MARGIN_UNIT"] / merged["JUALAHIR"] * 100,
            0.0,
        ).round(2)
        merged["COVERAGE_TAG"] = np.where(
            merged["COST"].isna(), "NO_COST_DATA", "OK"
        )

        def agg(df: pd.DataFrame) -> dict:
            return {
                "Total Revenue Gross (Rp)": float((df["JUALAHIR"] * df["QTY"]).sum()),
                "Total Revenue Net (Rp)": float((df["JUMLAH"] * df["QTY"]).sum()),
                "Total Cost (Rp)": float((df["EFF_COST"] * df["QTY"]).sum()),
                "Total Margin (Rp)": float(df["MARGIN_TOTAL"].sum()),
                "Avg Margin %": round(float(df["MARGIN_PCT"].mean()), 2),
                "Total QTY": int(df["QTY"].sum()),
                "Rows w/o Cost Data": int((df["COVERAGE_TAG"] == "NO_COST_DATA").sum()),
            }

        summary = agg(merged)
        per_brand = (
            merged.groupby("BRAND", as_index=False)
            .apply(lambda g: pd.Series(agg(g)), include_groups=False)
            .sort_values("Total Margin (Rp)", ascending=False)
            .reset_index(drop=True)
        )
        per_divisi = (
            merged.groupby("DIVISI", as_index=False)
            .apply(lambda g: pd.Series(agg(g)), include_groups=False)
            .sort_values("Total Margin (Rp)", ascending=False)
            .reset_index(drop=True)
        )
        per_area = (
            merged.groupby("AREA", as_index=False)
            .apply(lambda g: pd.Series(agg(g)), include_groups=False)
            .sort_values("Total Margin (Rp)", ascending=False)
            .reset_index(drop=True)
        )
        per_spv = (
            merged.groupby("SPV", as_index=False)
            .apply(lambda g: pd.Series(agg(g)), include_groups=False)
            .sort_values("Total Margin (Rp)", ascending=False)
            .reset_index(drop=True)
        )
        per_lokasi = (
            merged.groupby(["FLOCCD", "FNAMA"], as_index=False)
            .apply(lambda g: pd.Series(agg(g)), include_groups=False)
            .sort_values("Total Margin (Rp)", ascending=False)
            .reset_index(drop=True)
        )
        return {
            "summary": summary,
            "per_brand": per_brand,
            "per_divisi": per_divisi,
            "per_area": per_area,
            "per_spv": per_spv,
            "per_lokasi": per_lokasi,
            "_raw": merged,  # untuk drill-down
        }

    # ========================================================================
    # 4. DEAD STOCK per LOKASI × SPV × BRAND
    # ========================================================================
    def dead_stock(self, sales_threshold: int = 0) -> pd.DataFrame:
        """Item dengan sales <= threshold (default 0) dalam 5 bulan.
        Dead = STOCK_AWAL=0 ATAU SALES=0 ATAU STOCK<=0.
        Output: agregat per LOKASI × SPV × BRAND dengan item list.
        """
        self._check_loaded()
        # Tentukan dead: sales 0 (atau <= threshold)
        dead_rows = self.stock_df[
            self.stock_df["SALES"] <= sales_threshold
        ].copy()
        dead_rows["DEAD_CATEGORY"] = dead_rows.apply(self._classify_dead, axis=1)
        # Map SPV dari sheet sales (bisa beda per lokasi)
        spv_map = (
            self.sales_df.groupby("FLOCCD")["SPV"]
            .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else "(unknown)")
            .reset_index()
        )
        dead_rows = dead_rows.merge(spv_map, on="FLOCCD", how="left", suffixes=("", "_SALES"))
        dead_rows["SPV_EFFECTIVE"] = dead_rows["SPV_SALES"].fillna(dead_rows["SPV"])
        # Agregat per (LOKASI, SPV, BRAND)
        agg = (
            dead_rows.groupby(
                ["FLOCCD", "FNAMA", "SPV_EFFECTIVE", "BRAND", "DEAD_CATEGORY"],
                as_index=False,
            )
            .agg(
                N_DEAD_ITEMS=("PLU", "count"),
                TOTAL_STOCK_AWAL=("STOCK_AWAL", "sum"),
                TOTAL_STOCK_CURRENT=("STOCK", "sum"),
                TOTAL_RSP_VALUE=("RSP", "sum"),
            )
            .sort_values(["N_DEAD_ITEMS", "TOTAL_RSP_VALUE"], ascending=[False, False])
            .reset_index(drop=True)
        )
        return agg

    @staticmethod
    def _classify_dead(row) -> str:
        if row["SALES"] <= 0 and row["STOCK"] <= 0:
            return "FULLY_DEAD"  # ga laku, ga ada stock
        if row["SALES"] <= 0 and row["STOCK"] > 0:
            return "STOCK_ONLY"  # ga laku tapi stock ada (slow/dead risk)
        if row["SALES"] > 0 and row["STOCK"] < 0:
            return "OVERSOLD"  # laku tapi stock minus (audit needed)
        return "OTHER"

    def dead_stock_detail(self, sales_threshold: int = 0) -> pd.DataFrame:
        """Detail per item untuk dead stock (untuk drill-down & action)."""
        self._check_loaded()
        dead_rows = self.stock_df[self.stock_df["SALES"] <= sales_threshold].copy()
        dead_rows["DEAD_CATEGORY"] = dead_rows.apply(self._classify_dead, axis=1)
        return dead_rows[[
            "FLOCCD", "FNAMA", "PLU", "NAMA_BRG", "BRAND", "UB", "DIVISI",
            "STOCK_AWAL", "SALES", "STOCK", "COST", "RSP", "T_COST", "T_RSP",
            "DEAD_CATEGORY", "STATUS",
        ]].sort_values(
            ["DEAD_CATEGORY", "RSP"], ascending=[True, False]
        ).reset_index(drop=True)

    # ========================================================================
    # 5. CROSS-BRAND BUNDLE
    # ========================================================================
    def cross_brand_bundles(self, min_items: int = 2) -> pd.DataFrame:
        """Bundle cross-brand: (LOKASI, TANGGAL) yang di keranjang ada
        item dari ≥ 2 brand berbeda (INTEX + RBO + HERO KIDS).
        Proxy untuk NOTRAN (file ini tidak punya NOTRAN).
        """
        self._check_loaded()
        # Group by TX_KEY
        grp = self.sales_df.groupby("TX_KEY")
        tx_agg = grp.agg(
            FLOCCD=("FLOCCD", "first"),
            FNAMA=("FNAMA", "first"),
            FDATE=("FDATE", "first"),
            N_ITEMS=("PLU", "count"),
            N_QTY=("QTY", "sum"),
            N_REVENUE_NET=("LINE_REVENUE_NET", "sum"),
            N_BRANDS=("BRAND", "nunique"),
            BRANDS=("BRAND", lambda x: " + ".join(sorted(set(x)))),
        ).reset_index()
        # Filter: minimal N items DAN ≥ 2 brand
        bundles = tx_agg[
            (tx_agg["N_ITEMS"] >= min_items) & (tx_agg["N_BRANDS"] >= 2)
        ].copy()
        bundles = bundles.sort_values(
            ["N_BRANDS", "N_REVENUE_NET"], ascending=[False, False]
        ).reset_index(drop=True)
        return bundles

    def cross_brand_bundle_items(self, top_n: int = 50) -> pd.DataFrame:
        """Item combination paling sering muncul di cross-brand bundle.
        1 baris = 1 combo (sorted tuple of PLU names) dengan frekuensi.
        """
        self._check_loaded()
        # Filter ke TX dengan multi-brand
        tx_brands = self.sales_df.groupby("TX_KEY")["BRAND"].nunique()
        multi_brand_tx = tx_brands[tx_brands >= 2].index
        df_multi = self.sales_df[self.sales_df["TX_KEY"].isin(multi_brand_tx)]
        # Group by TX_KEY → list of (PLU, NAMA_BRG, BRAND)
        combos = (
            df_multi.groupby("TX_KEY")
            .apply(
                lambda g: tuple(sorted(set(
                    f"{r['BRAND']}|{r['PLU']}|{r['NAMA_BRG']}" for _, r in g.iterrows()
                ))),
                include_groups=False,
            )
            .reset_index(name="ITEM_COMBO")
        )
        # Hitung frekuensi
        freq = (
            combos.groupby("ITEM_COMBO")
            .size()
            .reset_index(name="FREQUENCY")
            .sort_values("FREQUENCY", ascending=False)
            .head(top_n)
            .reset_index(drop=True)
        )
        # Expand combo ke readable string
        def combo_to_str(c):
            parts = []
            for s in c:
                brand, plu, nama = s.split("|", 2)
                parts.append(f"[{brand}] {nama}")
            return " + ".join(parts)
        freq["COMBO"] = freq["ITEM_COMBO"].apply(combo_to_str)
        freq["N_ITEMS"] = freq["ITEM_COMBO"].apply(len)
        freq["N_BRANDS"] = freq["COMBO"].str.count(r"\[")  # ada bracket [BRAND]
        return freq[["COMBO", "N_ITEMS", "N_BRANDS", "FREQUENCY"]]

    # ========================================================================
    # 6. REORDER RECOMMENDATIONS
    # ========================================================================
    def reorder_recommendations(self) -> pd.DataFrame:
        """Rekomendasi order per item per lokasi.
        STOP_ORDER : TO < 0.5 (slow moving, jangan restock)
        NORMAL     : TO 0.5-1 (reorder normal)
        BOOST      : TO 1-3 (naikkan stock, fast moving)
        URGENT     : TO > 3 (urgent reorder, cek stockout risk)
        OVERSOLD   : Stock negatif (audit koreksi)
        """
        self._check_loaded()
        cov = self.stock_coverage()
        # TO dihitung ulang: sales / stock_awal (5 bulan) → annual proxy
        cov["TO_5MO"] = np.where(
            cov["STOCK_AWAL"] > 0,
            cov["SALES"] / cov["STOCK_AWAL"],
            0.0,
        ).round(2)
        cov["RECOMMENDATION"] = cov.apply(self._reorder_action, axis=1)
        # Suggested order quantity (simple heuristic)
        # Target: stock cukup untuk 60 hari ke depan
        cov["SUGGESTED_ORDER_QTY"] = np.where(
            cov["AVG_DAILY_SALES"] > 0,
            np.maximum(0, (60 * cov["AVG_DAILY_SALES"]).astype(int) - cov["STOCK"]),
            0,
        )
        return cov[[
            "FLOCCD", "FNAMA", "PLU", "NAMA_BRG", "BRAND", "UB", "DIVISI",
            "STOCK", "STOCK_AWAL", "SALES", "AVG_DAILY_SALES",
            "DAYS_OF_INVENTORY", "TO_5MO", "RECOMMENDATION", "SUGGESTED_ORDER_QTY",
            "COVERAGE_STATUS",
        ]].sort_values(
            ["RECOMMENDATION", "AVG_DAILY_SALES"], ascending=[True, False]
        ).reset_index(drop=True)

    @staticmethod
    def _reorder_action(row) -> str:
        if row["STOCK"] < 0:
            return "OVERSOLD_AUDIT"
        if row["SALES"] == 0:
            return "STOP_ORDER"
        to = row.get("TO_5MO", 0)
        if to < STOP_ORDER_TO:
            return "STOP_ORDER"
        if to < 1.0:
            return "NORMAL"
        if to < URGENT_REORDER_TO:
            return "BOOST"
        return "URGENT_REORDER"

    # ========================================================================
    # 7. DISCOUNT AUDIT
    # ========================================================================
    def discount_audit(self) -> pd.DataFrame:
        """Flag anomali diskon dari sheet Penjualan.
        Flag:
          - DISC_NEGATIVE      : discount < 0 (markup)
          - DISC_OVER_100      : diskon > 100% (effective negative price)
          - DISC_OVER_80       : diskon 80-100% (sangat tinggi, cek)
          - NET_NEGATIVE       : NET < 0 (revenue negatif)
          - PPN_MISMATCH       : NET/1.11 ≠ NET-PPN
          - SELL_ZERO          : SELL = 0 (free item?)
        """
        self._check_loaded()
        flags = []
        df = self.sales_df.copy()
        # DISC_NEGATIVE
        m = df["DISC"] < 0
        if m.any():
            flags.append(df[m].assign(ANOMALY="DISC_NEGATIVE (markup)"))
        # DISC_OVER_100
        m = (df["DISC_PCT"] > 100) & (df["DISC"] > 0)
        if m.any():
            flags.append(df[m].assign(ANOMALY="DISC_OVER_100%"))
        # DISC_OVER_80 (warning, cek)
        m = (df["DISC_PCT"] > 80) & (df["DISC_PCT"] <= 100)
        if m.any():
            flags.append(df[m].assign(ANOMALY="DISC_OVER_80% (high)"))
        # NET_NEGATIVE
        m = df["JUMLAH"] < 0
        if m.any():
            flags.append(df[m].assign(ANOMALY="NET_NEGATIVE"))
        # SELL_ZERO
        m = df["JUALAHIR"] == 0
        if m.any():
            flags.append(df[m].assign(ANOMALY="SELL_ZERO (free?)"))
        # PPN_MISMATCH (tolerance 1 rupiah)
        m = abs(df["JUMLAH"] / 1.11 - df["NET_PPN"]) > 1
        if m.any():
            flags.append(df[m].assign(ANOMALY="PPN_MISMATCH"))
        if not flags:
            return pd.DataFrame(columns=list(df.columns) + ["ANOMALY"])
        out = pd.concat(flags, ignore_index=True)
        out = out[[
            "ANOMALY", "FDATE", "FLOCCD", "FNAMA", "PLU", "NAMA_BRG",
            "QTY", "JUALAHIR", "DISC", "DISC_PCT", "JUMLAH", "NET_PPN",
            "BRAND", "UB", "DIVISI", "SPV", "STATUS",
        ]].sort_values(["ANOMALY", "FDATE"]).reset_index(drop=True)
        return out

    # ========================================================================
    # 8. ANOMALY DETECTION (DBS-level)
    # ========================================================================
    def stock_anomalies(self) -> pd.DataFrame:
        """Anomali stock dari sheet DBS.
        Flag:
          - STOCK_NEGATIVE    : stock < 0
          - DIFF_QTY_NONZERO  : ada selisih stock opname
          - TO_NEGATIVE       : TO < 0
          - TO_EXTREME        : TO > 10 (sangat cepat, cek)
        """
        self._check_loaded()
        flags = []
        df = self.stock_df.copy()
        m = df["STOCK"] < 0
        if m.any():
            flags.append(df[m].assign(ANOMALY="STOCK_NEGATIVE"))
        m = df["DIFF_QTY"] != 0
        if m.any():
            flags.append(df[m].assign(ANOMALY="DIFF_QTY_NONZERO (stock opname)"))
        m = df["TO"] < 0
        if m.any():
            flags.append(df[m].assign(ANOMALY="TO_NEGATIVE (oversold?)"))
        m = df["TO"] > 10
        if m.any():
            flags.append(df[m].assign(ANOMALY="TO_EXTREME (>10x)"))
        if not flags:
            return pd.DataFrame(columns=list(df.columns) + ["ANOMALY"])
        out = pd.concat(flags, ignore_index=True)
        out = out[[
            "ANOMALY", "FLOCCD", "FNAMA", "PLU", "NAMA_BRG", "BRAND", "UB", "DIVISI",
            "STOCK_AWAL", "SALES", "STOCK", "DIFF_QTY", "TO", "STATUS",
        ]].sort_values(["ANOMALY", "FLOCCD"]).reset_index(drop=True)
        return out

    # ========================================================================
    # EXPORT
    # ========================================================================
    def export_excel(self, output_path: str = "stock_sales_analysis.xlsx") -> str:
        """Export semua analisis ke 1 file Excel multi-sheet.
        Sheet:
          0. SUMMARY            : key metrics + summary per kategori
          1. STOCK_COVERAGE     : days of inventory
          2. STOCKOUT_RISK      : top items berisiko stockout
          3. MARGIN_SUMMARY     : ringkasan margin overall
          4. MARGIN_PER_BRAND
          5. MARGIN_PER_DIVISI
          6. MARGIN_PER_AREA
          7. MARGIN_PER_SPV
          8. MARGIN_PER_LOKASI
          9. DEAD_STOCK         : agregat per lokasi × SPV × BRAND
          10. DEAD_STOCK_DETAIL  : detail per item
          11. CROSS_BRAND_TX     : transaksi cross-brand
          12. CROSS_BRAND_COMBOS : top item combinations
          13. REORDER            : rekomendasi order
          14. DISCOUNT_AUDIT     : anomali diskon
          15. STOCK_ANOMALIES    : anomali stock
        """
        self._check_loaded()
        cov = self.stock_coverage()
        stockout = self.stockout_risk(top_n=200)
        margin = self.margin_analysis_real()
        dead = self.dead_stock()
        dead_det = self.dead_stock_detail()
        xb_tx = self.cross_brand_bundles()
        xb_combo = self.cross_brand_bundle_items(top_n=50)
        reorder = self.reorder_recommendations()
        disc = self.discount_audit()
        stk_anom = self.stock_anomalies()

        # === SUMMARY ===
        summary_rows = [
            ("FILE", self.filepath),
            ("TOTAL SALES ROWS", f"{len(self.sales_df):,}"),
            ("TOTAL STOCK ROWS (item × lokasi)", f"{len(self.stock_df):,}"),
            ("DATE RANGE", f"{self.sales_df['FDATE'].min().date()} → {self.sales_df['FDATE'].max().date()}"),
            ("TOTAL QTY SOLD", f"{int(self.sales_df['QTY'].sum()):,}"),
            ("TOTAL REVENUE GROSS (Rp)", f"{float(self.sales_df['LINE_REVENUE_GROSS'].sum()):,.0f}"),
            ("TOTAL REVENUE NET (Rp)", f"{float(self.sales_df['LINE_REVENUE_NET'].sum()):,.0f}"),
            ("TOTAL DISCOUNT (Rp)", f"{float(self.sales_df['DISC'].sum()):,.0f}"),
            ("AVG DISCOUNT %", f"{self.sales_df['DISC_PCT'].mean():.2f}%"),
            ("", ""),
            ("UNIQUE BRANDS", ", ".join(self.sales_df['BRAND'].unique())),
            ("UNIQUE UB", ", ".join(self.sales_df['UB'].unique())),
            ("UNIQUE DIVISI", ", ".join(self.sales_df['DIVISI'].unique())),
            ("UNIQUE AREA", ", ".join(self.sales_df['AREA'].unique())),
            ("UNIQUE SPV", f"{self.sales_df['SPV'].nunique()} orang"),
            ("UNIQUE LOKASI (sales)", f"{self.sales_df['FNAMA'].nunique()}"),
            ("UNIQUE LOKASI (stock)", f"{self.stock_df['FNAMA'].nunique()}"),
            ("UNIQUE PLU (sales)", f"{self.sales_df['PLU'].nunique()}"),
            ("UNIQUE PLU (stock)", f"{self.stock_df['PLU'].nunique()}"),
            ("", ""),
            ("STOCKOUT RISK ITEMS", f"{len(stockout):,}"),
            ("DEAD ITEMS (sales=0)", f"{int((self.stock_df['SALES']==0).sum()):,}"),
            ("FULLY DEAD (stock=0 & sales=0)", f"{int(((self.stock_df['STOCK']==0) & (self.stock_df['SALES']==0)).sum()):,}"),
            ("CROSS-BRAND TX", f"{len(xb_tx):,}"),
            ("STOCK ANOMALIES", f"{len(stk_anom):,}"),
            ("DISCOUNT ANOMALIES", f"{len(disc):,}"),
            ("", ""),
            ("MARGIN (real cost)", ""),
            ("  Total Margin (Rp)", f"{margin['summary']['Total Margin (Rp)']:,.0f}"),
            ("  Avg Margin %", f"{margin['summary']['Avg Margin %']}%"),
        ]
        summary_df = pd.DataFrame(summary_rows, columns=["METRIC", "VALUE"])

        with pd.ExcelWriter(output_path, engine="openpyxl") as xw:
            summary_df.to_excel(xw, sheet_name="SUMMARY", index=False)
            cov.to_excel(xw, sheet_name="STOCK_COVERAGE", index=False)
            stockout.to_excel(xw, sheet_name="STOCKOUT_RISK", index=False)
            pd.DataFrame([margin["summary"]]).to_excel(
                xw, sheet_name="MARGIN_SUMMARY", index=False
            )
            margin["per_brand"].to_excel(xw, sheet_name="MARGIN_PER_BRAND", index=False)
            margin["per_divisi"].to_excel(xw, sheet_name="MARGIN_PER_DIVISI", index=False)
            margin["per_area"].to_excel(xw, sheet_name="MARGIN_PER_AREA", index=False)
            margin["per_spv"].to_excel(xw, sheet_name="MARGIN_PER_SPV", index=False)
            margin["per_lokasi"].to_excel(xw, sheet_name="MARGIN_PER_LOKASI", index=False)
            dead.to_excel(xw, sheet_name="DEAD_STOCK", index=False)
            dead_det.to_excel(xw, sheet_name="DEAD_STOCK_DETAIL", index=False)
            xb_tx.to_excel(xw, sheet_name="CROSS_BRAND_TX", index=False)
            xb_combo.to_excel(xw, sheet_name="CROSS_BRAND_COMBOS", index=False)
            reorder.to_excel(xw, sheet_name="REORDER", index=False)
            disc.to_excel(xw, sheet_name="DISCOUNT_AUDIT", index=False)
            stk_anom.to_excel(xw, sheet_name="STOCK_ANOMALIES", index=False)
        return output_path

    # ========================================================================
    # Helpers
    # ========================================================================
    def _check_loaded(self):
        if self.sales_df is None or self.stock_df is None:
            raise ValueError(
                "Data belum dimuat. Panggil load(filepath) dulu."
            )


# =============================================================================
# CLI
# =============================================================================
def _print_summary(a: StockSalesAnalyzer):
    """Cetak ringkasan ke stdout (untuk CLI)."""
    sales = a.sales_df
    stock = a.stock_df
    print("=" * 70)
    print(f"FILE   : {a.filepath}")
    print(f"PERIODE: {sales['FDATE'].min().date()} → {sales['FDATE'].max().date()}")
    print("=" * 70)
    print(f"Sales rows          : {len(sales):,}")
    print(f"Stock rows          : {len(stock):,}")
    print(f"Unique lokasi sales : {sales['FNAMA'].nunique()}")
    print(f"Unique lokasi stock : {stock['FNAMA'].nunique()}")
    print(f"Unique PLU sales    : {sales['PLU'].nunique()}")
    print(f"Unique PLU stock    : {stock['PLU'].nunique()}")
    print(f"Brands              : {', '.join(sales['BRAND'].unique())}")
    print(f"UB                  : {', '.join(sales['UB'].unique())}")
    print(f"Total QTY sold      : {int(sales['QTY'].sum()):,}")
    print(f"Total Revenue Gross : Rp {sales['LINE_REVENUE_GROSS'].sum():,.0f}")
    print(f"Total Discount      : Rp {sales['DISC'].sum():,.0f} "
          f"(avg {sales['DISC_PCT'].mean():.2f}%)")
    print(f"Total Revenue Net   : Rp {sales['LINE_REVENUE_NET'].sum():,.0f}")
    print()
    print("--- DEAD STOCK ---")
    print(f"  Items with 0 sales      : {int((stock['SALES']==0).sum()):,}")
    print(f"  Fully dead (stk=0&sls=0): {int(((stock['STOCK']==0) & (stock['SALES']==0)).sum()):,}")
    print(f"  Stock negative          : {int((stock['STOCK']<0).sum()):,}")
    print()
    print("--- DISCOUNT AUDIT ---")
    disc = a.discount_audit()
    if disc.empty:
        print("  (no anomalies)")
    else:
        print(f"  Total anomalies: {len(disc):,}")
        print(disc["ANOMALY"].value_counts().to_string())
    print()
    print("--- STOCK ANOMALIES ---")
    sa = a.stock_anomalies()
    if sa.empty:
        print("  (no anomalies)")
    else:
        print(f"  Total anomalies: {len(sa):,}")
        print(sa["ANOMALY"].value_counts().to_string())


def main():
    ap = argparse.ArgumentParser(
        description="Stock & Sales Analyzer - analisa file 'stock & sales all (4).xlsx'",
    )
    ap.add_argument("input", help="Path ke file Excel input")
    ap.add_argument("-o", "--output", default="stock_sales_analysis.xlsx",
                    help="Path output Excel (default: stock_sales_analysis.xlsx)")
    ap.add_argument("--no-print", action="store_true",
                    help="Skip cetak ringkasan ke stdout")
    args = ap.parse_args()

    fp = Path(args.input)
    if not fp.exists():
        print(f"❌ File tidak ditemukan: {fp}")
        return 1
    print(f"📂 Loading: {fp.name} ({fp.stat().st_size:,} bytes)...")
    a = StockSalesAnalyzer()
    a.load(str(fp))
    if not args.no_print:
        _print_summary(a)
    print(f"\n💾 Exporting to: {args.output}")
    a.export_excel(args.output)
    print(f"✅ Done! {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
