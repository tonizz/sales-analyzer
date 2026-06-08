"""
Multi-Year Analyzer — Streamlit Multi-Page
===========================================
Halaman terpisah untuk analisis DBKSTHN 2025 + 2026 (YoY, seasonal, forecast).
Letakkan di pages/, import dari bundle_analyzer_multi.py.

CARA PAKAI:
  1. streamlit run bundle_analyzer_web.py
  2. Login di halaman utama
  3. Klik "YoY & Forecast" di sidebar
  4. Upload file 2025 (wajib) + file 2026 (opsional)
  5. Klik "🚀 Proses Multi-Tahun"
  6. Explore 5 tab
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bcrypt
import pandas as pd
import plotly.express as px
import streamlit as st

from bundle_analyzer_multi import MultiYearAnalyzer

# ============================================================================
# AUTH (duplikasi)
# ============================================================================
DEFAULT_USERS_MY = {
    "admin": "$2b$12$38P/ATKNv3p/d2kKebfxouS8TPeFZgSs9837E2oUSsewRe5uA7klq",
    "tonizz": "$2b$12$FKS3raeR9UZtbeNsqwvfAe5hKc6oC6LhP2Rkok6LZCjsj2BZFHVw.",
}

def _get_users_my() -> dict:
    try:
        if "users" in st.secrets:
            return dict(st.secrets["users"])
    except Exception:
        pass
    return DEFAULT_USERS_MY

def _login_gate_my():
    if st.session_state.get("logged_in"):
        return
    users = _get_users_my()
    st.markdown(
        '<div style="max-width:420px;margin:4rem auto;padding:2.5rem;background:white;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.08);">'
        '<h2 style="text-align:center;color:#1f77b4;margin:0 0 0.5rem 0;">🔐 Login</h2>'
        '<p style="text-align:center;color:#666;margin:0 0 1.5rem 0;">Multi-Year Analyzer</p></div>',
        unsafe_allow_html=True,
    )
    with st.form("login_form_my"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        submit = st.form_submit_button("Masuk", type="primary", use_container_width=True)
        if submit:
            stored = users.get(u)
            if stored and bcrypt.checkpw(p.encode(), stored.encode()):
                st.session_state.logged_in = True
                st.session_state.user = u
                st.rerun()
            else:
                st.error("❌ Salah.")
    st.stop()

# ============================================================================
# PAGE
# ============================================================================
st.set_page_config(page_title="Multi-Year Analyzer", page_icon="📅", layout="wide")
_login_gate_my()

with st.sidebar:
    st.caption(f"👤 {st.session_state.get('user','?')}")
    if st.button("🚪 Logout", key="logout_my"):
        st.session_state.logged_in = False
        st.rerun()

st.title("📅 YoY & Forecast Analyser")
st.caption(
    "Bandingkan Jan–Mei antar tahun, lihat pola musiman multi-tahun, "
    "forecast via linear regression."
)
st.divider()

# Upload files — dynamic N years
st.markdown("**Upload file Excel per tahun:**")

# Show year inputs dynamically
if "ny_upload_count" not in st.session_state:
    st.session_state.ny_upload_count = 2  # default 2

cols = st.columns([1, 1])
with cols[0]:
    st.number_input("Jumlah tahun:", 1, 10, st.session_state.ny_upload_count,
                    key="ny_n", on_change=lambda: setattr(st.session_state, "ny_upload_count",
                                                          st.session_state.ny_n))
with cols[1]:
    st.caption("Masukkan tahun & upload file untuk setiap tahun.")

uploaded = {}
default_dirs = {}
for i in range(st.session_state.ny_upload_count):
    col_a, col_b = st.columns([1, 3])
    with col_a:
        year_val = st.number_input(f"Tahun {i+1}", 2018, 2030, 2023 + i, key=f"ny_yr_{i}")
    with col_b:
        uploaded[year_val] = st.file_uploader(f"📁 File {year_val}", type=["xlsx"],
                                              key=f"ny_file_{i}")
    # check default
    default_path = Path(rf'D:\scr\DBKSTHN_55_{year_val}.xlsx')
    if default_path.exists():
        default_dirs[year_val] = str(default_path.resolve())
        st.caption(f"   (default: D:\\scr\\DBKSTHN_55_{year_val}.xlsx)")

if st.button("🚀 Proses Multi-Tahun", type="primary", key="ny_process"):
    paths = {}
    tmp_files = []
    try:
        for year_val, fobj in uploaded.items():
            if fobj is not None:
                t = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
                t.write(fobj.getvalue())
                paths[year_val] = t.name
                tmp_files.append(t.name)
            elif year_val in default_dirs:
                paths[year_val] = default_dirs[year_val]
            else:
                st.warning(f"⚠️ File {year_val} tidak diupload dan tidak ditemukan di default.")
        if len(paths) < 1:
            st.error("❌ Minimal 1 file harus tersedia.")
            st.stop()

        with st.spinner(f"⏳ Loading {len(paths)} tahun..."):
            m = MultiYearAnalyzer()
            m.load_years(paths)
            st.session_state["my_analyzer"] = m
        yr_counts = m.df_all["YEAR"].value_counts().sort_index().to_dict()
        st.success(f"✅ Loaded: {len(m.df_all):,} rows ({yr_counts})")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Error: {e}")
        st.exception(e)
    finally:
        for p in tmp_files:
            try: Path(p).unlink()
            except: pass

if "my_analyzer" not in st.session_state:
    st.info("⬆️ Upload minimal 1 file Excel untuk memulai.")
    st.stop()

m: MultiYearAnalyzer = st.session_state["my_analyzer"]
yr_info = " · ".join([f"{y}={len(m.df_all[m.df_all['YEAR']==y]):,}"
                      for y in m.years])
st.caption(f"📊 {len(m.df_all):,} rows · {yr_info} · "
           f"Lokasi={len(m._get_common_locs())} common")

# ============================================================================
# TABS
# ============================================================================
tab = st.tabs([
    "📋 Ringkasan YoY",
    "📍 YoY per Lokasi",
    "📈 Seasonal 2025",
    "🔮 Forecast 2026",
    "💾 Export",
    "🔥 Pareto & Heatmap",
    "📈 Trend (Cumul. & MA)",
    "📅 Pattern (Weekday & Bundle)",
    "⚠️ Anomaly & Price-QTY",
    "🤖 Machine Learning",
])

_bulan_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Des"]
_dow_names = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]

# --- TAB 1: RINGKASAN YOY ---
with tab[0]:
    st.markdown("### 📋 Jan–Mei 2025 vs 2026")
    yoy = m.yoy_summary()
    # kolom numerik
    num_cols = yoy.select_dtypes(include=np.number).columns.tolist()
    st.dataframe(yoy, use_container_width=True, hide_index=True, height=400)

    # Highlight metric (NETT) — cari growth column terakhir
    growth_row = yoy[yoy["Metrik"] == "Revenue (NETT)"]
    if not growth_row.empty:
        g_cols = [c for c in yoy.columns if "%" in str(c) and "Growth" in str(c)]
        rp_cols = [c for c in yoy.columns if "(Rp)" in str(c) and "Growth" in str(c)]
        g = growth_row.iloc[0][g_cols[-1]] if g_cols else None
        g_v = growth_row.iloc[0][rp_cols[-1]] if rp_cols else None
        color = "🟢" if g and g > 0 else "🔴"
        label = g_cols[-1].replace(" %","") if g_cols else "Growth"
        st.metric(f"{color} {label}", f"{g:+.2f}%" if g else "N/A", f"Rp {g_v:,.0f}" if g_v else None)

    st.divider()
    st.markdown("#### YoY Top Items")
    top = m.yoy_top_items()
    st.dataframe(top, use_container_width=True, hide_index=True, height=500)

# --- TAB 2: YOY PER LOKASI ---
with tab[1]:
    st.markdown("### 📍 YoY per Lokasi")
    loc_df = m.yoy_by_location()
    st.dataframe(loc_df, use_container_width=True, hide_index=True, height=600)

    # Chart
    if "Revenue_Growth_%" in loc_df.columns:
        fig = px.bar(
            loc_df.sort_values("Revenue_Growth_%"),
            x="Revenue_Growth_%", y="FLOCCD",
            color="Revenue_Growth_%", color_continuous_scale="RdYlGn",
            title="Revenue Growth % per Lokasi",
            text="Revenue_Growth_%",
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

# --- TAB 3: SEASONAL ---
with tab[2]:
    st.markdown("### 📈 Seasonal Pattern (2025 — 12 bulan penuh)")
    sea = m.seasonal_monthly()
    st.dataframe(sea, use_container_width=True, hide_index=True)
    st.caption("Seasonal Index: 1.0 = rata-rata, >1 = peak, <1 = off-peak")

    # Chart
    fig = px.bar(
        sea, x="Bulan", y="Seasonal_Index",
        color="Seasonal_Index", color_continuous_scale="RdYlGn",
        title="Seasonal Index per Bulan (2025)",
        text="Seasonal_Index",
    )
    fig.update_layout(height=400, yaxis_range=[0, max(sea["Seasonal_Index"].max()+0.5, 2)])
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.markdown("#### Top Seasonal Variance Items")
    top_var = m.seasonal_top_variance()
    st.dataframe(top_var, use_container_width=True, hide_index=True, height=500)

    # All monthly
    st.divider()
    st.markdown("#### All Monthly Data (2025 + 2026)")
    all_m = m.all_monthly()
    # Line chart
    all_m["Label"] = all_m["YEAR"].astype(str) + " " + all_m["Bulan"]
    fig2 = px.line(
        all_m, x="YM", y="Revenue", color="YEAR",
        markers=True, title="Revenue per Bulan",
    )
    fig2.update_layout(height=400)
    st.plotly_chart(fig2, use_container_width=True)

# --- TAB 4: FORECAST ---
with tab[3]:
    st.markdown(f"### 🔮 Forecast ({m.years[-1]}+) — Linear Regression per Lokasi")
    st.caption(
        "Metode: Linear Regression dari SEMUA tahun data per lokasi. "
        "Prediksi 6 bulan ke depan dari data terakhir."
    )
    fc = m.forecast_aggregate()
    st.dataframe(fc, use_container_width=True, hide_index=True, height=500)

    if not fc.empty:
        total_fc = fc.groupby(["Tahun", "Bulan"], as_index=False)["Forecast_Revenue"].sum()
        total_fc["Label"] = total_fc["Tahun"].astype(str) + " " + total_fc["Bulan"]
        fig = px.bar(total_fc, x="Label", y="Forecast_Revenue",
                     color="Tahun", title="Forecast Revenue per Bulan",
                     text="Forecast_Revenue")
        fig.update_layout(height=400, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

# --- TAB 5: EXPORT ---
with tab[4]:
    st.markdown("### 💾 Export Excel")
    default_fn = "multi_year_analysis.xlsx"
    fname = st.text_input("Nama file:", default_fn)
    if st.button("📥 Download Excel", type="primary"):
        with st.spinner("⏳ Generating..."):
            try:
                out = m.export_excel(fname)
                with open(out, "rb") as f:
                    st.download_button(
                        "⬇️ Download",
                        data=f.read(),
                        file_name=fname,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                try: Path(out).unlink()
                except: pass
            except Exception as e:
                st.error(f"❌ {e}")
                st.exception(e)

    st.divider()
    st.markdown("#### Sheet di Excel:")
    sheets = [
        ("SUMMARY", "Ringkasan file"),
        ("YOY_SUMMARY", "Side-by-side 2025 vs 2026"),
        ("YOY_BY_LOCATION", "YoY per lokasi"),
        ("YOY_TOP_ITEMS", "Top items YoY"),
        ("SEASONAL", "12-month seasonal pattern"),
        ("SEASONAL_TOP_VARIANCE", "Items with highest seasonality"),
        ("FORECAST", "Forecast Jun–Dec 2026"),
        ("ALL_MONTHLY", "Monthly aggregation all years"),
        ("ALL_MONTHLY_LOC", "Monthly per location"),
    ]
    for s, d in sheets:
        st.caption(f"- **{s}**: {d}")

# --- TAB 6: PARETO & HEATMAP ---
with tab[5]:
    st.markdown("### 🔥 Pareto 80/20 — Top PLU vs Revenue Share")
    col1, col2 = st.columns([1, 1])
    with col1:
        pareto_n = st.number_input("Jumlah PLU:", 10, 200, 50, key="pareto_n")
    with col2:
        pareto_yr = st.selectbox("Tahun:", m.years, key="pareto_yr")
    pareto = m.pareto_analysis(pareto_yr, pareto_n)
    st.dataframe(pareto, use_container_width=True, hide_index=True, height=400)
    # Bar chart pareto
    fig = px.bar(pareto.head(20), x="PLU", y="Pct",
                 color="Is_Top80", title=f"Top 20 PLU — Revenue Share ({pareto_yr})",
                 text="Pct", color_discrete_map={True: "#2ca02c", False: "#d62728"})
    fig.update_layout(height=400, xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
    # Find 80% threshold
    top80_count = pareto["Is_Top80"].sum()
    top80_rev = pareto[pareto["Is_Top80"]]["Pct"].sum()
    st.info(f"📌 **{top80_count} PLU** (dari {pareto_n} teratas) menyumbang **{top80_rev:.1f}%** revenue")

    st.divider()
    st.markdown("### 🔥 Calendar Heatmap — Revenue per Hari (2025)")
    try:
        heat = m.calendar_heatmap(m.years[-1])
        heat_pivot = heat.pivot_table(
            index="WEEK", columns="DOW", values="Revenue", aggfunc="sum"
        ).fillna(0)
        heat_pivot.columns = _dow_names
        fig = px.imshow(
            heat_pivot.values,
            x=_dow_names,
            y=heat_pivot.index,
            color_continuous_scale="Viridis",
            labels=dict(x="Hari", y="Minggu ke-", color="Revenue"),
            title=f"Revenue per Hari ({m.years[-1]})",
            aspect="auto",
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Heatmap error: {e}")

# --- TAB 7: TREND ---
with tab[6]:
    st.markdown("### 📈 Cumulative Revenue Jan–May — SEMUA Tahun")
    cum = m.cumulative_yoy()
    cum_cols = [f"Cumulative_{y}" for y in m.years if f"Cumulative_{y}" in cum.columns]
    rev_cols = [f"Revenue_{y}" for y in m.years if f"Revenue_{y}" in cum.columns]
    if cum_cols:
        fig = px.line(cum, x="FDATE", y=cum_cols,
                      title="Revenue Kumulatif Harian",
                      labels={"value": "Revenue", "variable": "Tahun"})
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    if rev_cols:
        fig2 = px.bar(cum, x="FDATE", y=rev_cols,
                      barmode="group", title="Revenue per Hari",
                      labels={"value": "Revenue", "variable": "Tahun"})
        fig2.update_layout(height=350)
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.markdown("### 📈 Moving Average (3 & 6 Bulan)")
    ma = m.moving_average()
    fig3 = px.line(ma, x="YM", y=["Revenue", "MA_3", "MA_6"],
                   markers=True, title="Monthly Revenue + Moving Average",
                   labels={"value": "Revenue", "variable": "Measure"})
    fig3.update_layout(height=400)
    st.plotly_chart(fig3, use_container_width=True)

# --- TAB 8: PATTERN ---
with tab[7]:
    st.markdown("### 📅 Weekday Pattern (2025)")
    wd_yr = st.selectbox("Tahun:", m.years, key="wd_yr")
    wd = m.weekday_pattern(wd_yr)
    st.dataframe(wd, use_container_width=True, hide_index=True)
    fig = px.bar(wd, x="Hari", y="Avg_Revenue_Pct",
                 color="Avg_Revenue_Pct", color_continuous_scale="Blues",
                 title=f"Distribusi Revenue per Hari ({wd_yr})",
                 text="Avg_Revenue_Pct",
                 category_orders={"Hari": _dow_names})
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.markdown("### 📅 Bundle vs Non-Bundle per Tahun")
    bc = m.bundle_comparison()
    st.dataframe(bc, use_container_width=True, hide_index=True)
    fig2 = px.bar(bc, x="Tahun", y="Revenue", color="Tipe",
                  barmode="group", title="Revenue Bundle vs Non-Bundle",
                  text="Revenue")
    fig2.update_layout(height=400)
    st.plotly_chart(fig2, use_container_width=True)
    # Pie
    for yr in m.years:
        sub = bc[bc["Tahun"] == yr]
        fig3 = px.pie(sub, values="Revenue", names="Tipe",
                      title=f"Revenue Share {yr}",
                      hole=0.4)
        fig3.update_layout(height=300)
        st.plotly_chart(fig3, use_container_width=True)

# --- TAB 9: ANOMALY & PRICE ---
with tab[8]:
    st.markdown("### ⚠️ Daily Anomalies (2025)")
    anom_yr = st.selectbox("Tahun:", m.years, key="anom_yr")
    z_th = st.slider("Z-score threshold:", 1.5, 4.0, 2.5, 0.1, key="z_th")
    anom = m.daily_anomalies(anom_yr, z_th)
    anom_only = anom[anom["Is_Anomaly"]]
    st.metric(f"Anomali ditemukan ({anom_yr})", f"{len(anom_only)} hari",
              f"dari {len(anom)} hari ({len(anom_only)/len(anom)*100:.1f}%)")
    # Scatter
    anom["Label"] = anom["Is_Anomaly"].map({True: "Anomali", False: "Normal"})
    fig = px.scatter(anom, x="FDATE", y="Revenue", color="Label",
                     size="Revenue", hover_data=["Hari", "Bulan", "Z_Score"],
                     title=f"Revenue Harian + Anomali ({anom_yr})",
                     color_discrete_map={"Anomali": "red", "Normal": "blue"})
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
    if len(anom_only) > 0:
        st.dataframe(anom_only[["FDATE","Hari","Revenue","Z_Score"]],
                     use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(f"### ⚠️ Price vs QTY Correlation ({m.years[-1]})")
    pq = m.price_qty_correlation(m.years[-1])
    fig2 = px.scatter(pq, x="Avg_Discount_Pct", y="QTY",
                      size="Revenue", color="Revenue",
                      hover_data=["PLU", "NAMA_BRG"],
                      title="Diskon vs QTY per PLU",
                      labels={"Avg_Discount_Pct": "Rata-rata Diskon (%)",
                              "QTY": "Total QTY Terjual"})
    fig2.update_layout(height=450)
    st.plotly_chart(fig2, use_container_width=True)

# --- TAB 10: MACHINE LEARNING ---
with tab[9]:
    st.markdown("## 🤖 Machine Learning Demo")
    st.caption(
        "Dua model ML sederhana untuk belajar: **K-Means Clustering** (segmentasi PLU) "
        "dan **Linear Regression** (tren revenue)."
    )
    st.divider()

    st.markdown("### 1️⃣ K-Means Clustering — Segmentasi PLU")
    st.caption(
        "**Cara kerja**: ML mencari pola tersembunyi dalam data — PLU dengan QTY, revenue, "
        "dan diskon yang mirip akan dikelompokkan dalam **cluster** yang sama. "
        "Tanpa ML, kita harus bikin aturan manual (IF QTY>X AND revenue>Y). "
        "Dengan ML, algoritma belajar sendiri mana yang mirip."
    )
    c1, c2 = st.columns([1, 1])
    with c1:
        km_year = st.selectbox("Tahun:", m.years, key="km_year")
    with c2:
        km_k = st.slider("Jumlah cluster:", 2, 6, 4, key="km_k")

    with st.spinner("⏳ K-Means clustering..."):
        try:
            plu_clust, desc_clust = m.kmeans_segmentation(km_year, km_k)
        except Exception as e:
            st.error(f"KMeans error: {e}")
            st.stop()

    st.markdown("**Ringkasan tiap cluster:**")
    st.dataframe(desc_clust, use_container_width=True, hide_index=True)

    fig = px.bar(
        desc_clust, x="Label", y="Total_QTY",
        color="Label", title="Rata-rata QTY per Cluster",
        text="Total_QTY",
    )
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Visualisasi cluster (Total QTY vs Discount):**")
    fig2 = px.scatter(
        plu_clust, x="Total_QTY", y="Avg_Discount",
        color=plu_clust["Cluster"].astype(str),
        hover_data=["PLU", "NAMA_BRG", "Total_Revenue", "Months_Active"],
        title=f"PLU Clusters ({km_year}) — QTY vs Diskon",
        labels={"Total_QTY": "Total QTY", "Avg_Discount": "Rata Diskon (%)",
                "Cluster": "Klaster"},
        opacity=0.6,
    )
    fig2.update_layout(height=450)
    st.plotly_chart(fig2, use_container_width=True)

    cnt = plu_clust["Cluster"].value_counts().sort_index()
    st.caption(f"Jumlah PLU per cluster: {dict(cnt)}")

    st.divider()

    st.markdown("### 2️⃣ Linear Regression — Tren Revenue Bulanan")
    st.caption(
        "**Cara kerja**: ML menarik **garis lurus terbaik** (best-fit line) "
        "melalui titik-titik revenue bulanan. Garis ini adalah **model** yang sudah "
        "'belajar' dari data. Slope garis = estimasi kenaikan/penurunan revenue per bulan. "
        "Model bisa memprediksi 6 bulan ke depan dengan melanjutkan garis tersebut."
    )

    with st.spinner("⏳ Linear regression..."):
        try:
            monthly_ml, fut_pred, slope = m.linear_trend()
        except Exception as e:
            st.error(f"LinReg error: {e}")
            st.stop()

    trend_sign = "📈 naik" if slope > 0 else "📉 turun"
    st.metric("Slope (perubahan revenue per bulan)",
              f"{trend_sign} Rp {abs(slope):,.0f}",
              f"{slope:+.0f}")

    import plotly.graph_objects as go
    from datetime import datetime

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=monthly_ml["YM"], y=monthly_ml["Revenue"],
        mode="lines+markers", name="Actual Revenue", line=dict(color="blue"),
    ))
    fig3.add_trace(go.Scatter(
        x=monthly_ml["YM"], y=monthly_ml["Trend"],
        mode="lines", name="Trend (Linear Regression)",
        line=dict(color="red", dash="dash"),
    ))

    last_ym = monthly_ml["YM"].iloc[-1]
    _last_dt = datetime.strptime(last_ym + "-01", "%Y-%m-%d") if "-" in last_ym else None
    if _last_dt:
        fut_ym = []
        for i in range(1, 7):
            m = _last_dt.month + i
            y = _last_dt.year + (m - 1) // 12
            m = ((m - 1) % 12) + 1
            fut_ym.append(f"{y}-{m:02d}")
    else:
        fut_ym = [f"F+{i}" for i in range(1, 7)]

    fig3.add_trace(go.Scatter(
        x=fut_ym, y=fut_pred,
        mode="lines+markers", name="Prediksi 6 bln",
        line=dict(color="green", dash="dot"),
    ))
    fig3.update_layout(
        title="Revenue Bulanan + Linear Regression Trend + Prediksi",
        height=450, xaxis_title="Bulan", yaxis_title="Revenue (NETT)",
    )
    st.plotly_chart(fig3, use_container_width=True)

    st.info(
        "💡 **Ringkasan ML**: "
        "K-Means otomatis menemukan 4 kelompok PLU dengan pola jual berbeda. "
        "Linear Regression belajar tren dari data historis dan memprediksi 6 bulan ke depan. "
        "Keduanya contoh **supervised** (regression — butuh label Y) dan "
        "**unsupervised** (clustering — tanpa label) learning."
    )
