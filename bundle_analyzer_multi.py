"""
Multi-Year Analyzer (N-tahun)
==============================
Memuat data DBKSTHN dari N tahun (2023, 2024, 2025, 2026, ...).
Semua method otomatis menyesuaikan dengan tahun yang tersedia.

TIDAK mengubah bundle_analyzer.py.

Cara pakai:
    from bundle_analyzer_multi import MultiYearAnalyzer
    m = MultiYearAnalyzer()
    m.load_years({2023: "file2023.xlsx", 2024: "file2024.xlsx",
                  2025: "file2025.xlsx", 2026: "file2026.xlsx"})
    m.export_excel("multi_year_analysis.xlsx")
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from bundle_analyzer import BundleAnalyzer


class MultiYearAnalyzer:
    """Analisa multi-tahun untuk data DBKSTHN (N tahun dinamis)."""

    def __init__(self):
        self.df_all: pd.DataFrame | None = None
        self.paths: dict[int, str] = {}
        self._years: list[int] = []
        self._common_locs: list | None = None

    # ========================================================================
    # LOADER
    # ========================================================================
    def load_years(
        self,
        paths: dict[int, str],
        min_items: int = 2,
        min_discount: float = 0.0,
    ) -> "MultiYearAnalyzer":
        """Load N tahun dari dict {tahun: path}. Setiap file di-classify terpisah,
        lalu di-concat dengan kolom YEAR, MONTH, YM, LINE_NETT."""
        self.paths = dict(sorted(paths.items()))
        self._years = sorted(paths.keys())

        chunks = []
        for year, path in self.paths.items():
            a = BundleAnalyzer()
            a.load(path)
            a.classify(min_items=min_items, min_discount=min_discount)
            a.df["YEAR"] = year
            chunks.append(a.df)

        df = pd.concat(chunks, ignore_index=True)
        df["MONTH"] = df["FDATE"].dt.month
        df["YM"] = df["FDATE"].dt.to_period("M").astype(str)
        df["LINE_NETT"] = df["JUMLAH"]  # JUMLAH = total net per baris
        self.df_all = df
        self._common_locs = None  # reset
        return self

    def load_multi(self, path_2025: str, path_2026: str, **kw) -> "MultiYearAnalyzer":
        """Backward compat: load 2 tahun (2025, 2026)."""
        return self.load_years({2025: path_2025, 2026: path_2026}, **kw)

    @property
    def years(self) -> list[int]:
        return sorted(self.df_all["YEAR"].unique()) if self.df_all is not None else []

    @staticmethod
    def _revenue_net(df: pd.DataFrame) -> pd.Series:
        return df["JUMLAH"]

    @staticmethod
    def _revenue_gross(df: pd.DataFrame) -> pd.Series:
        return df["JUALAHIR"] * df["QTY"]

    @staticmethod
    def _discount_rp(df: pd.DataFrame) -> pd.Series:
        return df["RPDISCOUNT"]

    # ========================================================================
    # YOY — SEMUA TAHUN SIDE BY SIDE
    # ========================================================================
    def yoy_summary(self) -> pd.DataFrame:
        """Side-by-side semua tahun (Jan–May). Growth % vs tahun sebelumnya."""
        self._check_loaded()
        years = self.years
        mask = self.df_all["MONTH"] <= 5

        def _metrics(sub: pd.DataFrame) -> dict:
            b = sub[sub["IS_BUNDLE"]]
            rev_n = float(self._revenue_net(sub).sum())
            rev_g = float(self._revenue_gross(sub).sum())
            n_tx = sub["NOTRAN"].nunique()
            n_b_tx = b["NOTRAN"].nunique() if len(b) > 0 else 0
            disc = float(self._discount_rp(sub).sum())
            gross = float(self._revenue_gross(sub).sum())
            return {
                "Revenue (NETT)": rev_n,
                "Revenue RSP (GROSS)": rev_g,
                "Discount (Rp)": disc,
                "Discount %": round(disc / gross * 100, 2) if gross > 0 else 0.0,
                "Jumlah Transaksi": n_tx,
                "Jumlah Transaksi Bundle": n_b_tx,
                "Bundle %": round(n_b_tx / n_tx * 100, 2) if n_tx > 0 else 0.0,
                "Total QTY": int(sub["QTY"].sum()),
                "Bundle Revenue (NETT)": float(self._revenue_net(b).sum()),
                "Rata-rata Item per Transaksi": round(sub.groupby("NOTRAN")["NOM"].count().mean(), 2),
            }

        data = self.df_all[mask]
        rows = []
        for y in years:
            r = _metrics(data[data["YEAR"] == y])
            r["Tahun"] = y
            rows.append(r)
        out = pd.DataFrame(rows).set_index("Tahun").T.reset_index()
        # Pastikan kolom tahun jadi string
        str_years = [str(y) for y in years]
        col_map = {y: str(y) for y in years if y in out.columns}
        out = out.rename(columns=col_map)

        # Growth vs previous year
        for i in range(1, len(years)):
            prev, cur = str(years[i - 1]), str(years[i])
            out[f"Growth {prev}→{cur} (Rp)"] = out.apply(
                lambda r, p=prev, c=cur: r[c] - r[p]
                if isinstance(r.get(c), (int, float)) and isinstance(r.get(p), (int, float))
                else None, axis=1,
            )
            out[f"Growth {prev}→{cur} %"] = out.apply(
                lambda r, p=prev, c=cur: round((r[c] - r[p]) / r[p] * 100, 2)
                if isinstance(r.get(c), (int, float)) and isinstance(r.get(p), (int, float)) and r[p] != 0
                else None, axis=1,
            )
        out = out.rename(columns={"index": "Metrik"})
        return out

    def yoy_by_location(self) -> pd.DataFrame:
        """YoY per FLOCCD — semua tahun side by side."""
        self._check_loaded()
        years = self.years
        mask = self.df_all["MONTH"] <= 5
        d = self.df_all[mask]

        def _per_loc(df: pd.DataFrame, year: int) -> pd.DataFrame:
            sub = df[df["YEAR"] == year]
            b = sub[sub["IS_BUNDLE"]]
            out = sub.groupby("FLOCCD").agg(
                Revenue=("LINE_NETT", "sum"),
                QTY=("QTY", "sum"),
                TX=("NOTRAN", "nunique"),
            )
            if len(b) > 0:
                bv = b.groupby("FLOCCD").agg(Bundle_TX=("NOTRAN", "nunique"))
                out = out.join(bv, how="left").fillna(0)
            else:
                out["Bundle_TX"] = 0
            out["Bundle_%"] = (out["Bundle_TX"] / out["TX"] * 100).round(2)
            return out.add_suffix(f"_{year}")

        merged = None
        for y in years:
            yr = _per_loc(d, y)
            merged = yr if merged is None else merged.join(yr, how="outer")
        if merged is None:
            return pd.DataFrame()
        merged = merged.fillna(0).reset_index()

        # Growth vs previous year
        for i in range(1, len(years)):
            prev, cur = years[i - 1], years[i]
            for col in ["Revenue", "QTY", "TX", "Bundle_TX", "Bundle_%"]:
                k = f"{col}_Growth {prev}→{cur} %"
                v1 = merged[f"{col}_{prev}"].astype(float).replace(0, float("nan"))
                v2 = merged[f"{col}_{cur}"].astype(float)
                merged[k] = ((v2 - v1) / v1 * 100).round(2)

        if "FNAMA" in self.df_all.columns:
            nama = self.df_all.groupby("FLOCCD")["FNAMA"].first().reset_index()
            merged = merged.merge(nama, on="FLOCCD", how="left")
            cols = ["FLOCCD", "FNAMA"] + [c for c in merged.columns if c not in ("FLOCCD", "FNAMA")]
            merged = merged[cols]
        return merged.sort_values(f"Revenue_{years[-1]}", ascending=False).reset_index(drop=True)

    def yoy_top_items(self, top_n: int = 30) -> pd.DataFrame:
        """Top PLU per tahun (Jan–May)."""
        self._check_loaded()
        years = self.years
        mask = self.df_all["MONTH"] <= 5
        d = self.df_all[mask]
        by_year = {}
        for y in years:
            sub = d[d["YEAR"] == y]
            grp = sub.groupby(["PLU", "NAMA_BRG"], as_index=False).agg(
                QTY=("QTY", "sum"), Revenue=("LINE_NETT", "sum"),
            ).sort_values("Revenue", ascending=False).head(top_n)
            by_year[y] = grp

        merged = by_year[years[0]].copy()
        merged = merged.rename(columns={"QTY": f"QTY_{years[0]}", "Revenue": f"Revenue_{years[0]}"})
        for y in years[1:]:
            yr = by_year[y].rename(columns={"QTY": f"QTY_{y}", "Revenue": f"Revenue_{y}"})
            merged = pd.merge(merged, yr[["PLU", f"QTY_{y}", f"Revenue_{y}"]], on="PLU", how="outer")
        merged = merged.fillna(0)

        for y in years[1:]:
            prev = years[years.index(y) - 1]
            for col in ["QTY", "Revenue"]:
                v1 = merged[f"{col}_{prev}"].astype(float).replace(0, float("nan"))
                v2 = merged[f"{col}_{y}"].astype(float)
                merged[f"{col}_Growth {prev}→{y} %"] = ((v2 - v1) / v1 * 100).round(2)

        sort_col = f"Revenue_{years[-1]}"
        merged = merged.sort_values(sort_col, ascending=False).head(top_n).reset_index(drop=True)
        return merged

    # ========================================================================
    # SEASONAL (multi-year average)
    # ========================================================================
    def seasonal_monthly(self) -> pd.DataFrame:
        """Rata-rata pola musiman dari SEMUA tahun (bukan hanya 1 tahun).
        Seasonal Index lebih akurat karena pakai multi-year average."""
        self._check_loaded()
        monthly = self.df_all.groupby(["YEAR", "MONTH"], as_index=False).agg(
            Revenue=("LINE_NETT", "sum"),
            QTY=("QTY", "sum"),
            TX=("NOTRAN", "nunique"),
        )
        avg = monthly.groupby("MONTH", as_index=False).agg(
            Revenue=("Revenue", "mean"),
            QTY=("QTY", "mean"),
            TX=("TX", "mean"),
        )
        avg["Revenue_Pct"] = (avg["Revenue"] / avg["Revenue"].sum() * 100).round(2)
        avg["Seasonal_Index"] = (avg["Revenue"] / avg["Revenue"].mean()).round(2)
        avg["Bulan"] = avg["MONTH"].apply(self._month_name)

        # Bundle % multi-year
        b = self.df_all[self.df_all["IS_BUNDLE"]]
        if len(b) > 0:
            bm = b.groupby(["YEAR", "MONTH"]).agg(Bundle_TX=("NOTRAN", "nunique")).reset_index()
            bm = bm.groupby("MONTH")["Bundle_TX"].mean().reset_index()
            avg = avg.merge(bm, on="MONTH", how="left").fillna(0)
        else:
            avg["Bundle_TX"] = 0
        avg["Bundle_%"] = (avg["Bundle_TX"] / avg["TX"] * 100).round(2)
        return avg[[
            "MONTH", "Bulan", "Revenue", "Revenue_Pct", "Seasonal_Index",
            "QTY", "TX", "Bundle_TX", "Bundle_%",
        ]]

    @staticmethod
    def _month_name(m: int) -> str:
        names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Des"]
        return names[m - 1] if 1 <= m <= 12 else "?"

    def seasonal_top_variance(self, top_n: int = 30) -> pd.DataFrame:
        """Item dengan seasonal variance tertinggi (multi-year data)."""
        self._check_loaded()
        monthly = self.df_all.groupby(["PLU", "NAMA_BRG", "MONTH"])["QTY"].sum().reset_index()
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
    # FORECAST (multi-year linear trend)
    # ========================================================================
    def forecast_aggregate(self, months_ahead: int = 6) -> pd.DataFrame:
        """Forecast N bulan ke depan pakai Gradient Boosting dari SEMUA tahun.
        Per FLOCCD untuk akurasi lebih baik dan deteksi musiman."""
        from sklearn.ensemble import GradientBoostingRegressor

        self._check_loaded()
        results = []
        for loc in self._get_common_locs():
            sub = self.df_all[self.df_all["FLOCCD"] == loc]
            monthly = sub.groupby(["YEAR", "MONTH"], as_index=False)["LINE_NETT"].sum()
            monthly["Period"] = range(len(monthly))
            if len(monthly) < 3:
                continue
            X = monthly[["Period", "MONTH"]].values
            y = monthly["LINE_NETT"].values.astype(float)
            model = GradientBoostingRegressor(random_state=42)
            model.fit(X, y)
            last_period = int(monthly["Period"].max())
            last_ym = self._last_ym()
            for i in range(1, months_ahead + 1):
                fut_period = last_period + i
                # estimate month/year
                m = last_ym[1] + i
                yr = last_ym[0] + (m - 1) // 12
                m = ((m - 1) % 12) + 1
                pred = float(model.predict([[fut_period, m]])[0])
                # actual from last year for comparison
                prev_yr = yr - 1
                prev_actual = sub[(sub["YEAR"] == prev_yr) & (sub["MONTH"] == m)]["LINE_NETT"].sum()
                results.append({
                    "FLOCCD": loc,
                    "Bulan": self._month_name(m),
                    "Tahun": yr,
                    "Forecast_Revenue": int(round(pred)),
                    "Prev_Year_Actual": int(prev_actual),
                })
        out = pd.DataFrame(results)
        if len(out) == 0:
            return out
        out = out.sort_values(["FLOCCD", "Tahun", "Bulan"]).reset_index(drop=True)
        return out

    def _last_ym(self) -> tuple[int, int]:
        df = self.df_all
        last = df["FDATE"].max()
        return last.year, last.month

    def _get_common_locs(self) -> list:
        if self._common_locs is None:
            self._check_loaded()
            loc_sets = []
            for y in self.years:
                loc_sets.append(set(self.df_all[self.df_all["YEAR"] == y]["FLOCCD"].unique()))
            common = loc_sets[0]
            for s in loc_sets[1:]:
                common = common & s
            self._common_locs = sorted(common)
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
    def calendar_heatmap(self, year: int) -> pd.DataFrame:
        """Daily revenue untuk heatmap kalender."""
        self._check_loaded()
        df = self.df_all[self.df_all["YEAR"] == year]
        daily = df.groupby("FDATE", as_index=False).agg(
            Revenue=("LINE_NETT", "sum"), QTY=("QTY", "sum"), TX=("NOTRAN", "nunique"),
        )
        daily["DAY"] = daily["FDATE"].dt.day
        daily["MONTH"] = daily["FDATE"].dt.month
        daily["DOW"] = daily["FDATE"].dt.dayofweek
        daily["WEEK"] = daily["FDATE"].dt.isocalendar().week.astype(int)
        daily["Bulan"] = daily["MONTH"].apply(self._month_name)
        return daily

    def pareto_analysis(self, year: int, top_n: int = 50) -> pd.DataFrame:
        """Pareto 80/20."""
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
        """Revenue kumulatif harian Jan–May — SEMUA tahun."""
        self._check_loaded()
        mask = self.df_all["MONTH"] <= 5
        d = self.df_all[mask]
        daily = d.groupby(["YEAR", "FDATE"], as_index=False).agg(
            Revenue=("LINE_NETT", "sum"),
        ).sort_values(["YEAR", "FDATE"])
        daily["Cumulative"] = daily.groupby("YEAR")["Revenue"].cumsum()
        piv = daily.pivot(index="FDATE", columns="YEAR",
                          values=["Revenue", "Cumulative"]).fillna(0)
        cols = []
        for y in self.years:
            cols += [f"Revenue_{y}", f"Cumulative_{y}"]
        piv.columns = cols
        piv = piv.reset_index()
        piv["DOW"] = piv["FDATE"].dt.dayofweek
        piv["Hari"] = piv["DOW"].map({0:"Senin",1:"Selasa",2:"Rabu",3:"Kamis",4:"Jumat",5:"Sabtu",6:"Minggu"})
        return piv

    def weekday_pattern(self, year: int) -> pd.DataFrame:
        """Rata-rata revenue per hari dalam seminggu."""
        self._check_loaded()
        df = self.df_all[self.df_all["YEAR"] == year].copy()
        df["DOW"] = df["FDATE"].dt.dayofweek
        dow = df.groupby("DOW", as_index=False).agg(
            Revenue=("LINE_NETT", "sum"), QTY=("QTY", "sum"), TX=("NOTRAN", "nunique"),
        )
        dow["Hari"] = dow["DOW"].map({0:"Senin",1:"Selasa",2:"Rabu",3:"Kamis",4:"Jumat",5:"Sabtu",6:"Minggu"})
        total = dow["Revenue"].sum()
        dow["Avg_Revenue_Pct"] = (dow["Revenue"] / total * 100).round(2) if total > 0 else 0
        dow["Avg_Daily_Revenue"] = (dow["Revenue"] / 52).round(0)
        return dow[["Hari","Revenue","Avg_Daily_Revenue","Avg_Revenue_Pct","QTY","TX"]]

    def moving_average(self) -> pd.DataFrame:
        """3/6-month moving average."""
        monthly = self.all_monthly()
        monthly["MA_3"] = monthly["Revenue"].rolling(3, min_periods=1).mean().round(0)
        monthly["MA_6"] = monthly["Revenue"].rolling(6, min_periods=1).mean().round(0)
        return monthly

    def daily_anomalies(self, year: int, z_thresh: float = 2.5) -> pd.DataFrame:
        """Deteksi outlier harian via Z-score."""
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
        daily["Hari"] = daily["DOW"].map({0:"Senin",1:"Selasa",2:"Rabu",3:"Kamis",4:"Jumat",5:"Sabtu",6:"Minggu"})
        return daily

    def price_qty_correlation(self, year: int, min_qty: int = 5) -> pd.DataFrame:
        """Korelasi diskon vs QTY per PLU."""
        self._check_loaded()
        df = self.df_all[self.df_all["YEAR"] == year]
        plu = df.groupby(["PLU", "NAMA_BRG"], as_index=False).agg(
            QTY=("QTY", "sum"), Revenue=("LINE_NETT", "sum"),
            Avg_Discount_Pct=("DISCOUNT", "mean"), Avg_Price=("JUALAHIR", "mean"),
        )
        plu = plu[plu["QTY"] >= min_qty].reset_index(drop=True)
        plu["Avg_Disc_Rp"] = plu["Avg_Price"] * plu["Avg_Discount_Pct"] / 100
        return plu

    def bundle_comparison(self) -> pd.DataFrame:
        """Bundle vs non-bundle per tahun (semua tahun)."""
        self._check_loaded()
        rows = []
        for year in self.years:
            sub = self.df_all[self.df_all["YEAR"] == year]
            for label, cond in [("Bundle", "IS_BUNDLE"), ("Non-Bundle", "not IS_BUNDLE")]:
                grp = sub.query(cond)
                if len(grp) == 0:
                    continue
                rows.append({
                    "Tahun": year, "Tipe": label,
                    "Revenue": float(self._revenue_net(grp).sum()),
                    "QTY": int(grp["QTY"].sum()),
                    "TX": int(grp["NOTRAN"].nunique()),
                    "Avg_Discount_Pct": round(float(grp["DISCOUNT"].mean()), 2),
                    "Item_Per_TX": round(grp.groupby("NOTRAN")["NOM"].count().mean(), 2),
                })
        return pd.DataFrame(rows)

    # ========================================================================
    # MACHINE LEARNING
    # ========================================================================
    def kmeans_segmentation(self, year: int, n_clusters: int = 4) -> tuple[pd.DataFrame, pd.DataFrame]:
        """K-Means clustering: segmentasi PLU."""
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        self._check_loaded()
        df = self.df_all[self.df_all["YEAR"] == year]
        plu = df.groupby(["PLU", "NAMA_BRG"], as_index=False).agg(
            Total_QTY=("QTY", "sum"), Total_Revenue=("LINE_NETT", "sum"),
            Avg_Discount=("DISCOUNT", "mean"), Months_Active=("MONTH", "nunique"),
            TX_Count=("NOTRAN", "nunique"),
        )
        feat_cols = ["Total_QTY", "Total_Revenue", "Avg_Discount", "Months_Active"]
        X = plu[feat_cols].fillna(0)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        plu["Cluster"] = model.fit_predict(X_scaled).astype(int)
        desc = plu.groupby("Cluster")[feat_cols + ["TX_Count"]].mean().round(1).reset_index()

        def _label(r):
            q, rev, disc, active = r["Total_QTY"], r["Total_Revenue"], r["Avg_Discount"], r["Months_Active"]
            if q > plu["Total_QTY"].quantile(0.75) and active > 6:
                return "Fast Moving"
            if active <= 3 and q < plu["Total_QTY"].quantile(0.25):
                return "Slow Moving"
            if disc > plu["Avg_Discount"].quantile(0.75):
                return "High Diskon"
            return "Medium"
        desc["Label"] = desc.apply(_label, axis=1)
        return plu, desc

    def linear_trend(self) -> tuple[pd.DataFrame, np.ndarray, float]:
        """Gradient Boosting: tren revenue bulanan semua tahun dengan musiman."""
        from sklearn.ensemble import GradientBoostingRegressor

        self._check_loaded()
        monthly = self.all_monthly()
        monthly["Period"] = range(len(monthly))
        
        # Tambahkan fitur MONTH dari YM
        if "YM" in monthly.columns:
            monthly["MONTH"] = monthly["YM"].str.split("-").str[1].astype(int)
        else:
            monthly["MONTH"] = 1
            
        X = monthly[["Period", "MONTH"]].values
        y = monthly["Revenue"].values.astype(float)
        
        model = GradientBoostingRegressor(random_state=42)
        model.fit(X, y)
        monthly["Trend"] = model.predict(X).round(0)
        
        # Hitung effective slope
        slope = 0.0
        if len(monthly) > 1:
            slope = float(monthly["Trend"].iloc[-1] - monthly["Trend"].iloc[0]) / len(monthly)
            
        last = int(monthly["Period"].max())
        last_m = int(monthly["MONTH"].iloc[-1])
        
        fut_X = []
        for i in range(1, 7):
            fut_period = last + i
            m_next = last_m + i
            m_next = ((m_next - 1) % 12) + 1
            fut_X.append([fut_period, m_next])
            
        fut_y = model.predict(np.array(fut_X)).round(0)
        return monthly, fut_y, slope

    # ========================================================================
    # EXPORT
    # ========================================================================
    def export_excel(self, output_path: str = "multi_year_analysis.xlsx") -> str:
        """Export semua analisis ke Excel multi-sheet."""
        self._check_loaded()
        yoy_sum = self.yoy_summary()
        yoy_loc = self.yoy_by_location()
        yoy_items = self.yoy_top_items()
        seasonal = self.seasonal_monthly()
        top_var = self.seasonal_top_variance()
        forecast = self.forecast_aggregate()
        all_m = self.all_monthly()
        all_loc = self.all_monthly_per_loc()
        late_yr = self.years[-1]
        heatmap = self.calendar_heatmap(late_yr)
        pareto = self.pareto_analysis(late_yr)
        cum = self.cumulative_yoy()
        wd = self.weekday_pattern(late_yr)
        ma = self.moving_average()
        anom = self.daily_anomalies(late_yr)
        pq = self.price_qty_correlation(late_yr)
        bc = self.bundle_comparison()

        # Summary rows
        summary_rows = [("METRIC",)]
        yr_dfs = []
        for y in self.years:
            summary_rows[0] = summary_rows[0] + (str(y),)
            yr_dfs.append(self.df_all[self.df_all["YEAR"] == y])

        def _add(label, vals):
            summary_rows.append((label,) + tuple(vals))

        _add("Total baris", [f"{len(d):,}" for d in yr_dfs])
        _add("Unique FLOCCD", [f"{d['FLOCCD'].nunique()}" for d in yr_dfs])
        _add("Unique PLU", [f"{d['PLU'].nunique()}" for d in yr_dfs])
        _add("Periode", [f"{d['FDATE'].min().date()} -> {d['FDATE'].max().date()}" for d in yr_dfs])
        _add("Total Revenue (NETT)", [f"{float(self._revenue_net(d).sum()):,.0f}" for d in yr_dfs])
        _add("Total Discount", [f"{float(self._discount_rp(d).sum()):,.0f}" for d in yr_dfs])
        _add("Total QTY", [f"{int(d['QTY'].sum()):,}" for d in yr_dfs])
        _add("Lokasi overlap", [f"{len(self._get_common_locs())}"] + [""] * (len(self.years) - 1))

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
            raise ValueError("Data belum dimuat. Panggil load_years() dulu.")
