"""
Multi-Year Analyzer
====================
Memuat data DBKSTHN 2025 + 2026, menggabungkan, dan menyediakan:
  - YoY comparison (Jan-May 2025 vs 2026)
  - Seasonal pattern (12 bulan penuh)
  - Forecasting sederhana (June-Dec 2026)
  - Export Excel multi-sheet

TIDAK mengubah bundle_analyzer.py. Import class dari sana, tambah method baru.

Cara pakai:
    from bundle_analyzer_multi import MultiYearAnalyzer
    m = MultiYearAnalyzer()
    m.load_multi("DBKSTHN_55_2025.xlsx", "DBKSTHN_55_2026.xlsx")
    m.export_excel("multi_year_analysis.xlsx")
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from bundle_analyzer import BundleAnalyzer


class MultiYearAnalyzer:
    """Analisa multi-tahun untuk data DBKSTHN."""

    def __init__(self):
        self.df_all: pd.DataFrame | None = None
        self.analyzer_2025: BundleAnalyzer | None = None
        self.analyzer_2026: BundleAnalyzer | None = None
        self.paths: dict[int, str] = {}
        self._common_locs: list | None = None  # FLOCCD yang ada di kedua tahun

    # ========================================================================
    # LOADER
    # ========================================================================
    def load_multi(
        self,
        path_2025: str,
        path_2026: str,
        min_items: int = 2,
        min_discount: float = 0.0,
    ) -> "MultiYearAnalyzer":
        """Load 2025 + 2026, classify, concat, tambah kolom YEAR & MONTH."""
        self.paths = {2025: path_2025, 2026: path_2026}

        a25 = BundleAnalyzer()
        a25.load(path_2025)
        a25.classify(min_items=min_items, min_discount=min_discount)
        a25.df["YEAR"] = 2025

        a26 = BundleAnalyzer()
        a26.load(path_2026)
        a26.classify(min_items=min_items, min_discount=min_discount)
        a26.df["YEAR"] = 2026

        self.analyzer_2025 = a25
        self.analyzer_2026 = a26

        # Gabung
        df = pd.concat([a25.df, a26.df], ignore_index=True)
        df["MONTH"] = df["FDATE"].dt.month
        df["YM"] = df["FDATE"].dt.to_period("M").astype(str)
        # JUMLAH = total net per baris (JUALAHIR*QTY - RPDISCOUNT), sudah include QTY
        # RPDISCOUNT = total diskon rupiah per baris (JUALAHIR*QTY * DISCOUNT%/100)
        df["LINE_NETT"] = df["JUMLAH"]
        self.df_all = df

        # Common locations
        locs_25 = set(a25.df["FLOCCD"].unique())
        locs_26 = set(a26.df["FLOCCD"].unique())
        self._common_locs = sorted(locs_25 & locs_26)

        return self

    @staticmethod
    def _revenue_net(df: pd.DataFrame) -> pd.Series:
        return df["JUMLAH"]  # JUMLAH sudah total net (= JUALAHIR*QTY - RPDISCOUNT)

    @staticmethod
    def _revenue_gross(df: pd.DataFrame) -> pd.Series:
        return df["JUALAHIR"] * df["QTY"]

    @staticmethod
    def _discount_rp(df: pd.DataFrame) -> pd.Series:
        return df["RPDISCOUNT"]  # total diskon dalam rupiah per baris

    # ========================================================================
    # YOY COMPARISON (Jan-May only)
    # ========================================================================
    def yoy_summary(self) -> pd.DataFrame:
        """Side-by-side Jan-May 2025 vs Jan-May 2026. SEMUA revenue = NETT (JUMLAH*QTY)."""
        self._check_loaded()
        mask = lambda df: (df["YEAR"].isin([2025, 2026])) & (df["MONTH"] <= 5)

        def _metrics(sub: pd.DataFrame, year: int) -> dict:
            b = sub[sub["IS_BUNDLE"]]
            rev_n = float(self._revenue_net(sub).sum())
            rev_g = float(self._revenue_gross(sub).sum())
            n_tx = sub["NOTRAN"].nunique()
            n_b_tx = b["NOTRAN"].nunique() if len(b) > 0 else 0
            total_disc = float(self._discount_rp(sub).sum())       # RPDISCOUNT (total rupiah)
            total_jual = float(self._revenue_gross(sub).sum())     # JUALAHIR*QTY (gross)
            return {
                "Tahun": year,
                "Revenue (NETT)": rev_n,
                "Revenue RSP (GROSS)": rev_g,
                "Discount (Rp)": total_disc,
                "Discount %": round(total_disc / total_jual * 100, 2) if total_jual > 0 else 0.0,
                "Jumlah Transaksi": n_tx,
                "Jumlah Transaksi Bundle": n_b_tx,
                "Bundle %": round(n_b_tx / n_tx * 100, 2) if n_tx > 0 else 0.0,
                "Total QTY": int(sub["QTY"].sum()),
                "Bundle Revenue (NETT)": float(self._revenue_net(b).sum()),
                "Rata-rata Item per Transaksi": round(sub.groupby("NOTRAN")["NOM"].count().mean(), 2),
            }

        data = self.df_all[mask(self.df_all)]
        rows = [_metrics(data[data["YEAR"] == y], y) for y in (2025, 2026)]
        out = pd.DataFrame(rows).set_index("Tahun").T.reset_index()

        # Growth
        out["Growth (Rp)"] = out.apply(
            lambda r: r[2026] - r[2025] if isinstance(r[2026], (int, float)) and isinstance(r[2025], (int, float)) else None,
            axis=1,
        )
        out["Growth %"] = out.apply(
            lambda r: round((r[2026] - r[2025]) / r[2025] * 100, 2)
            if isinstance(r[2026], (int, float)) and isinstance(r[2025], (int, float)) and r[2025] != 0
            else None,
            axis=1,
        )
        out = out.rename(columns={"index": "Metrik"})
        return out

    def yoy_by_location(self) -> pd.DataFrame:
        """YoY per FLOCCD (Jan-May only).
        Include FNAMA jika ada. Hitung revenue net + QTY + bundle%."""
        self._check_loaded()
        mask = (self.df_all["MONTH"] <= 5)

        def _per_loc(df: pd.DataFrame, year: int) -> pd.DataFrame:
            sub = df[df["YEAR"] == year]
            b = sub[sub["IS_BUNDLE"]]
            out = sub.groupby("FLOCCD").agg(
                Revenue=("LINE_NETT", "sum"),
                QTY=("QTY", "sum"),
                TX=("NOTRAN", "nunique"),
            )
            bv = b.groupby("FLOCCD").agg(
                Bundle_TX=("NOTRAN", "nunique"),
            ) if len(b) > 0 else pd.DataFrame({"Bundle_TX": 0}, index=out.index)
            out = out.join(bv, how="left").fillna(0)
            out["Bundle_%"] = (out["Bundle_TX"] / out["TX"] * 100).round(2)
            return out.add_suffix(f"_{year}")

        d = self.df_all[mask]
        y25 = _per_loc(d, 2025)
        y26 = _per_loc(d, 2026)
        merged = y25.join(y26, how="outer").fillna(0).reset_index()

        # Growth
        for col in ["Revenue", "QTY", "TX", "Bundle_TX", "Bundle_%"]:
            v1 = merged[f"{col}_2025"].astype(float)
            v2 = merged[f"{col}_2026"].astype(float)
            denom = v1.replace(0, float("nan"))
            merged[f"{col}_Growth_%"] = ((v2 - v1) / denom * 100).round(2)

        # Add FNAMA if available
        if "FNAMA" in self.df_all.columns:
            nama = self.df_all.groupby("FLOCCD")["FNAMA"].first().reset_index()
            merged = merged.merge(nama, on="FLOCCD", how="left")
            cols = ["FLOCCD", "FNAMA"] + [c for c in merged.columns if c not in ("FLOCCD", "FNAMA")]
            merged = merged[cols]

        return merged.sort_values("Revenue_2025", ascending=False).reset_index(drop=True)

    def yoy_top_items(self, top_n: int = 30) -> pd.DataFrame:
        """Top-selling PLU Jan-May 2025 vs 2026 (by revenue net)."""
        self._check_loaded()
        mask = (self.df_all["MONTH"] <= 5)

        def _top(sub, year):
            df = sub[sub["YEAR"] == year]
            grp = df.groupby(["PLU", "NAMA_BRG"], as_index=False).agg(
                QTY=("QTY", "sum"),
                Revenue=("LINE_NETT", "sum"),
            ).sort_values("Revenue", ascending=False).head(top_n)
            grp = grp.add_suffix(f"_{year}")
            grp = grp.rename(columns={f"PLU_{year}": "PLU", f"NAMA_BRG_{year}": "NAMA_BRG"})
            return grp

        d = self.df_all[mask]
        t25 = _top(d, 2025)
        t26 = _top(d, 2026)
        merged = pd.merge(t25, t26, on=["PLU"], how="outer", suffixes=("_2025", "_2026")).fillna(0)
        for col in ["QTY", "Revenue"]:
            v25 = merged[f"{col}_2025"].astype(float)
            v26 = merged[f"{col}_2026"].astype(float)
            denom = v25.replace(0, float("nan"))
            merged[f"{col}_Growth_%"] = ((v26 - v25) / denom * 100).round(2)

        merged = merged.sort_values("Revenue_2025", ascending=False).head(top_n).reset_index(drop=True)
        # Fill NAMA_BRG missing
        merged["NAMA_BRG"] = merged["NAMA_BRG_2025"].fillna(merged["NAMA_BRG_2026"])
        drop_cols = [c for c in merged.columns if c.startswith("NAMA_BRG_")]
        merged = merged.drop(columns=drop_cols)
        return merged

    # ========================================================================
    # SEASONAL PATTERN (full 2025)
    # ========================================================================
    def seasonal_monthly(self) -> pd.DataFrame:
        """12-month breakdown 2025 (Revenue, QTY, Transaksi, Bundle%)."""
        self._check_loaded()
        df = self.df_all[self.df_all["YEAR"] == 2025]
        monthly = df.groupby("MONTH").agg(
            Revenue=("LINE_NETT", "sum"),
            QTY=("QTY", "sum"),
            TX=("NOTRAN", "nunique"),
        ).reset_index()
        b = df[df["IS_BUNDLE"]]
        if len(b) > 0:
            bv = b.groupby("MONTH").agg(Bundle_TX=("NOTRAN", "nunique")).reset_index()
            monthly = monthly.merge(bv, on="MONTH", how="left").fillna(0)
        monthly["Bundle_%"] = (monthly["Bundle_TX"] / monthly["TX"] * 100).round(2)
        monthly["Revenue_Pct"] = (monthly["Revenue"] / monthly["Revenue"].sum() * 100).round(2)
        monthly["Seasonal_Index"] = (monthly["Revenue"] / monthly["Revenue"].mean()).round(2)
        monthly["Bulan"] = monthly["MONTH"].apply(self._month_name)
        return monthly[[
            "MONTH", "Bulan", "Revenue", "Revenue_Pct", "Seasonal_Index",
            "QTY", "TX", "Bundle_TX", "Bundle_%",
        ]]

    @staticmethod
    def _month_name(m: int) -> str:
        names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Des"]
        return names[m - 1] if 1 <= m <= 12 else "?"

    def seasonal_top_variance(self, top_n: int = 30) -> pd.DataFrame:
        """Item dengan seasonal variance tertinggi dari 2025.
        Seasonal = coefficient of variation (CV) of monthly sales.
        CV tinggi = item sangat musiman.
        """
        self._check_loaded()
        df = self.df_all[self.df_all["YEAR"] == 2025]
        monthly = df.groupby(["PLU", "NAMA_BRG", "MONTH"])["QTY"].sum().reset_index()
        cv = (
            monthly.groupby(["PLU", "NAMA_BRG"])
            .agg(
                MEAN_MONTHLY=("QTY", "mean"),
                STD_MONTHLY=("QTY", "std"),
                PEAK_MONTH=("MONTH", lambda x: x.loc[monthly.loc[x.index, "QTY"].idxmax()]),
                TOTAL_QTY=("QTY", "sum"),
            )
            .reset_index()
        )
        cv["CV"] = np.where(cv["MEAN_MONTHLY"] > 0, (cv["STD_MONTHLY"] / cv["MEAN_MONTHLY"]).round(2), 0)
        cv["PEAK_MONTH_NAME"] = cv["PEAK_MONTH"].apply(self._month_name)
        cv = cv.sort_values("CV", ascending=False).head(top_n)
        return cv[[
            "PLU", "NAMA_BRG", "CV", "PEAK_MONTH", "PEAK_MONTH_NAME",
            "MEAN_MONTHLY", "STD_MONTHLY", "TOTAL_QTY",
        ]].reset_index(drop=True)

    # ========================================================================
    # FORECAST (aggregate)
    # ========================================================================
    def forecast_aggregate(self, months_ahead: int = 6) -> pd.DataFrame:
        """Forecast revenue net + QTY per bulan (Jun-Dec 2026).
        Metode: trend dari 2025->2026 (Jan-May) diterapkan ke proyeksi 2025 (Jun-Dec).
        Per location untuk akurasi lebih baik.
        """
        self._check_loaded()
        # Hitung per FLOCCD untuk akurasi lebih baik
        results = []
        for loc in self._get_common_locs():
            sub = self.df_all[self.df_all["FLOCCD"] == loc]
            y25 = sub[sub["YEAR"] == 2025]
            y26 = sub[sub["YEAR"] == 2026]
            # Trend factor: 2026 Jan-May / 2025 Jan-May
            for measure, col in [("Revenue", "LINE_NETT"), ("QTY", "QTY")]:
                s25 = y25[y25["MONTH"] <= 5][col].sum() or 1
                s26 = y26[y26["MONTH"] <= 5][col].sum()
                trend = s26 / s25 if s25 > 0 else 1.0
                # 2025 monthly profile (Jun-Dec)
                for m in range(6, 13):
                    base = y25[y25["MONTH"] == m][col].sum()
                    forecast_val = base * trend
                    results.append({
                        "FLOCCD": loc,
                        "Bulan": self._month_name(m),
                        "MONTH": m,
                        "Measure": measure,
                        "2025_Actual": int(base),
                        "Trend_Factor": round(trend, 3),
                        "2026_Forecast": int(round(forecast_val)),
                    })
        out = pd.DataFrame(results)
        return out

    def _get_common_locs(self) -> list:
        if self._common_locs is None:
            self._check_loaded()
            l25 = set(self.df_all[self.df_all["YEAR"] == 2025]["FLOCCD"].unique())
            l26 = set(self.df_all[self.df_all["YEAR"] == 2026]["FLOCCD"].unique())
            self._common_locs = sorted(l25 & l26)
        return self._common_locs

    # ========================================================================
    # ALL DATA (monthly rollup)
    # ========================================================================
    def all_monthly(self) -> pd.DataFrame:
        """Monthly aggregation semua tahun."""
        self._check_loaded()
        monthly = self.df_all.groupby(["YEAR", "MONTH", "YM"], as_index=False).agg(
            Revenue=("LINE_NETT", "sum"),
            QTY=("QTY", "sum"),
            TX=("NOTRAN", "nunique"),
        ).sort_values(["YEAR", "MONTH"])
        monthly["Bulan"] = monthly["MONTH"].apply(self._month_name)
        b = self.df_all[self.df_all["IS_BUNDLE"]]
        if len(b) > 0:
            bv = b.groupby(["YEAR", "MONTH"]).agg(Bundle_TX=("NOTRAN", "nunique")).reset_index()
            monthly = monthly.merge(bv, on=["YEAR", "MONTH"], how="left").fillna(0)
        monthly["Bundle_%"] = (monthly["Bundle_TX"] / monthly["TX"] * 100).round(2)
        return monthly

    def all_monthly_per_loc(self) -> pd.DataFrame:
        """Monthly aggregation per FLOCCD."""
        self._check_loaded()
        grp = self.df_all.groupby(["YEAR", "MONTH", "YM", "FLOCCD"], as_index=False).agg(
            Revenue=("LINE_NETT", "sum"),
            QTY=("QTY", "sum"),
            TX=("NOTRAN", "nunique"),
        )
        grp["Bulan"] = grp["MONTH"].apply(self._month_name)
        if "FNAMA" in self.df_all.columns:
            nama = self.df_all.groupby("FLOCCD")["FNAMA"].first().reset_index()
            grp = grp.merge(nama, on="FLOCCD", how="left")
        return grp.sort_values(["YEAR", "MONTH", "FLOCCD"]).reset_index(drop=True)

    # ========================================================================
    # ADVANCED ANALYTICS
    # ========================================================================
    def calendar_heatmap(self, year: int = 2025) -> pd.DataFrame:
        """Daily revenue untuk heatmap kalender."""
        self._check_loaded()
        df = self.df_all[self.df_all["YEAR"] == year]
        daily = df.groupby("FDATE", as_index=False).agg(
            Revenue=("LINE_NETT", "sum"),
            QTY=("QTY", "sum"),
            TX=("NOTRAN", "nunique"),
        )
        daily["DAY"] = daily["FDATE"].dt.day
        daily["MONTH"] = daily["FDATE"].dt.month
        daily["DOW"] = daily["FDATE"].dt.dayofweek
        daily["WEEK"] = daily["FDATE"].dt.isocalendar().week.astype(int)
        daily["Bulan"] = daily["MONTH"].apply(self._month_name)
        return daily

    def pareto_analysis(self, year: int = 2025, top_n: int = 50) -> pd.DataFrame:
        """Pareto 80/20: top PLU vs revenue share."""
        self._check_loaded()
        df = self.df_all[self.df_all["YEAR"] == year]
        plu = df.groupby(["PLU", "NAMA_BRG"], as_index=False)["LINE_NETT"].sum()
        plu = plu.sort_values("LINE_NETT", ascending=False).head(top_n).reset_index(drop=True)
        total = plu["LINE_NETT"].sum()
        plu["Pct"] = (plu["LINE_NETT"] / total * 100).round(2) if total > 0 else 0
        plu["Cumulative_Pct"] = plu["Pct"].cumsum().round(2)
        plu["Is_Top80"] = plu["Cumulative_Pct"] <= 80
        return plu

    def cumulative_yoy(self) -> pd.DataFrame:
        """Revenue kumulatif harian Jan–May 2025 vs 2026."""
        self._check_loaded()
        mask = self.df_all["MONTH"] <= 5
        d = self.df_all[mask]
        daily = d.groupby(["YEAR", "FDATE"], as_index=False).agg(
            Revenue=("LINE_NETT", "sum"),
        ).sort_values(["YEAR", "FDATE"])
        daily["Cumulative"] = daily.groupby("YEAR")["Revenue"].cumsum()
        piv = daily.pivot(index="FDATE", columns="YEAR",
                          values=["Revenue", "Cumulative"]).fillna(0)
        piv.columns = ["Revenue_2025", "Revenue_2026",
                       "Cumulative_2025", "Cumulative_2026"]
        piv = piv.reset_index()
        piv["DOW"] = piv["FDATE"].dt.dayofweek
        piv["Hari"] = piv["DOW"].map(
            {0:"Senin",1:"Selasa",2:"Rabu",3:"Kamis",4:"Jumat",5:"Sabtu",6:"Minggu"})
        return piv

    def weekday_pattern(self, year: int = 2025) -> pd.DataFrame:
        """Rata-rata revenue per hari dalam seminggu."""
        self._check_loaded()
        df = self.df_all[self.df_all["YEAR"] == year].copy()
        df["DOW"] = df["FDATE"].dt.dayofweek
        dow = df.groupby("DOW", as_index=False).agg(
            Revenue=("LINE_NETT", "sum"),
            QTY=("QTY", "sum"),
            TX=("NOTRAN", "nunique"),
        )
        dow["Hari"] = dow["DOW"].map(
            {0:"Senin",1:"Selasa",2:"Rabu",3:"Kamis",4:"Jumat",5:"Sabtu",6:"Minggu"})
        total = dow["Revenue"].sum()
        dow["Avg_Revenue_Pct"] = (dow["Revenue"] / total * 100).round(2) if total > 0 else 0
        dow["Avg_Daily_Revenue"] = (dow["Revenue"] / 52).round(0)  # ~52 hari per DOW
        return dow[["Hari","Revenue","Avg_Daily_Revenue","Avg_Revenue_Pct","QTY","TX"]]

    def moving_average(self) -> pd.DataFrame:
        """3/6-month moving average dari all_monthly."""
        self._check_loaded()
        monthly = self.all_monthly()
        monthly["MA_3"] = monthly["Revenue"].rolling(3, min_periods=1).mean().round(0)
        monthly["MA_6"] = monthly["Revenue"].rolling(6, min_periods=1).mean().round(0)
        return monthly

    def daily_anomalies(self, year: int = 2025, z_thresh: float = 2.5) -> pd.DataFrame:
        """Deteksi outlier penjualan harian via Z-score."""
        self._check_loaded()
        df = self.df_all[self.df_all["YEAR"] == year]
        daily = df.groupby("FDATE", as_index=False)["LINE_NETT"].sum()
        daily.columns = ["FDATE", "Revenue"]
        mean_r = daily["Revenue"].mean()
        std_r = daily["Revenue"].std()
        if std_r > 0:
            daily["Z_Score"] = ((daily["Revenue"] - mean_r) / std_r).round(2)
            daily["Is_Anomaly"] = daily["Z_Score"].abs() > z_thresh
        else:
            daily["Z_Score"] = 0.0
            daily["Is_Anomaly"] = False
        daily["Bulan"] = daily["FDATE"].dt.month.apply(self._month_name)
        daily["DOW"] = daily["FDATE"].dt.dayofweek
        daily["Hari"] = daily["DOW"].map(
            {0:"Senin",1:"Selasa",2:"Rabu",3:"Kamis",4:"Jumat",5:"Sabtu",6:"Minggu"})
        return daily

    def price_qty_correlation(self, year: int = 2025, min_qty: int = 5) -> pd.DataFrame:
        """Korelasi diskon vs QTY per PLU."""
        self._check_loaded()
        df = self.df_all[self.df_all["YEAR"] == year]
        plu = df.groupby(["PLU", "NAMA_BRG"], as_index=False).agg(
            QTY=("QTY", "sum"),
            Revenue=("LINE_NETT", "sum"),
            Avg_Discount_Pct=("DISCOUNT", "mean"),
            Avg_Price=("JUALAHIR", "mean"),
        )
        plu = plu[plu["QTY"] >= min_qty].reset_index(drop=True)
        plu["Avg_Disc_Rp"] = plu["Avg_Price"] * plu["Avg_Discount_Pct"] / 100
        return plu

    def bundle_comparison(self) -> pd.DataFrame:
        """Bundle vs non-bundle per tahun."""
        self._check_loaded()
        rows = []
        for year in (2025, 2026):
            sub = self.df_all[self.df_all["YEAR"] == year]
            for label, cond in [("Bundle", "IS_BUNDLE"), ("Non-Bundle", "not IS_BUNDLE")]:
                grp = sub.query(cond)
                if len(grp) == 0:
                    continue
                disc_pct = float(grp["DISCOUNT"].mean())
                rows.append({
                    "Tahun": year, "Tipe": label,
                    "Revenue": float(self._revenue_net(grp).sum()),
                    "QTY": int(grp["QTY"].sum()),
                    "TX": int(grp["NOTRAN"].nunique()),
                    "Avg_Discount_Pct": round(disc_pct, 2),
                    "Item_Per_TX": round(grp.groupby("NOTRAN")["NOM"].count().mean(), 2),
                })
        return pd.DataFrame(rows)

    # ========================================================================
    # EXPORT
    # ========================================================================
    def export_excel(self, output_path: str = "multi_year_analysis.xlsx") -> str:
        """Export semua analisis ke 1 file Excel multi-sheet."""
        self._check_loaded()
        yoy_sum = self.yoy_summary()
        yoy_loc = self.yoy_by_location()
        yoy_items = self.yoy_top_items()
        seasonal = self.seasonal_monthly()
        top_var = self.seasonal_top_variance()
        forecast = self.forecast_aggregate()
        all_m = self.all_monthly()
        all_loc = self.all_monthly_per_loc()
        heatmap = self.calendar_heatmap(2025)
        pareto = self.pareto_analysis(2025)
        cum = self.cumulative_yoy()
        wd = self.weekday_pattern(2025)
        ma = self.moving_average()
        anom = self.daily_anomalies(2025)
        pq = self.price_qty_correlation(2025)
        bc = self.bundle_comparison()

        # Summary rows
        s25 = self.df_all[self.df_all["YEAR"] == 2025]
        s26 = self.df_all[self.df_all["YEAR"] == 2026]
        summary_rows = [
            ("METRIC", "2025", "2026"),
            ("Total baris", f"{len(s25):,}", f"{len(s26):,}"),
            ("Unique FLOCCD", f"{s25['FLOCCD'].nunique()}", f"{s26['FLOCCD'].nunique()}"),
            ("Unique PLU", f"{s25['PLU'].nunique()}", f"{s26['PLU'].nunique()}"),
            ("Periode", f"{s25['FDATE'].min().date()} → {s25['FDATE'].max().date()}",
             f"{s26['FDATE'].min().date()} → {s26['FDATE'].max().date()}"),
            ("Total Revenue (NETT)", f"{float(self._revenue_net(s25).sum()):,.0f}",
             f"{float(self._revenue_net(s26).sum()):,.0f}"),
            ("Total Discount", f"{float(self._discount_rp(s25).sum()):,.0f}",
             f"{float(self._discount_rp(s26).sum()):,.0f}"),
            ("Total QTY", f"{int(s25['QTY'].sum()):,}", f"{int(s26['QTY'].sum()):,}"),
            ("FLOCCD overlap", f"{len(self._get_common_locs())}", "-"),
        ]
        summary_df = pd.DataFrame(summary_rows[1:], columns=summary_rows[0])

        with pd.ExcelWriter(output_path, engine="openpyxl") as xw:
            summary_df.to_excel(xw, sheet_name="SUMMARY", index=False)
            yoy_sum.to_excel(xw, sheet_name="YOY_SUMMARY", index=False)
            yoy_loc.to_excel(xw, sheet_name="YOY_BY_LOCATION", index=False)
            yoy_items.to_excel(xw, sheet_name="YOY_TOP_ITEMS", index=False)
            seasonal.to_excel(xw, sheet_name="SEASONAL", index=False)
            top_var.to_excel(xw, sheet_name="SEASONAL_TOP_VARIANCE", index=False)
            forecast.to_excel(xw, sheet_name="FORECAST", index=False)
            all_m.to_excel(xw, sheet_name="ALL_MONTHLY", index=False)
            all_loc.to_excel(xw, sheet_name="ALL_MONTHLY_LOC", index=False)
            heatmap.to_excel(xw, sheet_name="HEATMAP", index=False)
            pareto.to_excel(xw, sheet_name="PARETO", index=False)
            cum.to_excel(xw, sheet_name="CUMULATIVE_YOY", index=False)
            wd.to_excel(xw, sheet_name="WEEKDAY", index=False)
            ma.to_excel(xw, sheet_name="MOVING_AVG", index=False)
            anom.to_excel(xw, sheet_name="ANOMALIES", index=False)
            pq.to_excel(xw, sheet_name="PRICE_QTY", index=False)
            bc.to_excel(xw, sheet_name="BUNDLE_COMPARE", index=False)
        return output_path

    # ========================================================================
    # HELPERS
    # ========================================================================
    def _check_loaded(self):
        if self.df_all is None:
            raise ValueError("Data belum dimuat. Panggil load_multi() dulu.")
