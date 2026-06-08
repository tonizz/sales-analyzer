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
    "Bandingkan Jan–Mei 2025 vs 2026, lihat pola musiman 12 bulan penuh, "
    "forecast Jun–Des 2026."
)
st.divider()

# Upload files
# First check if files exist in D:\scr
default_2025 = str(Path(r'D:\scr\DBKSTHN_55_2025.xlsx').resolve()) if Path(r'D:\scr\DBKSTHN_55_2025.xlsx').exists() else None
default_2026 = str(Path(r'D:\scr\DBKSTHN_55_2026.xlsx').resolve()) if Path(r'D:\scr\DBKSTHN_55_2026.xlsx').exists() else None

upload_2025 = st.file_uploader("📁 File 2025 (wajib)", type=["xlsx"], key="my_25")
upload_2026 = st.file_uploader("📁 File 2026 (opsional, pakai default kalau kosong)", type=["xlsx"], key="my_26")

if st.button("🚀 Proses Multi-Tahun", type="primary", key="my_process"):
    # Save uploaded files
    tmp_2025 = None
    tmp_2026 = None
    try:
        if upload_2025 is not None:
            t = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
            t.write(upload_2025.getvalue())
            tmp_2025 = t.name
        else:
            tmp_2025 = default_2025

        if upload_2026 is not None:
            t = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
            t.write(upload_2026.getvalue())
            tmp_2026 = t.name
        else:
            tmp_2026 = default_2026

        if not tmp_2025 or not Path(tmp_2025).exists():
            st.error("❌ File 2025 wajib diupload atau harus ada di D:\\scr\\DBKSTHN_55_2025.xlsx")
            st.stop()

        with st.spinner("⏳ Load 2025 + 2026, classify, concat..."):
            m = MultiYearAnalyzer()
            m.load_multi(tmp_2025, tmp_2026 or "")
            st.session_state["my_analyzer"] = m
        st.success(f"✅ Loaded: {len(m.df_all):,} rows ({m.df_all['YEAR'].value_counts().to_dict()})")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Error: {e}")
        st.exception(e)
    finally:
        for p in (tmp_2025, tmp_2026):
            if p:
                try: Path(p).unlink()
                except: pass

if "my_analyzer" not in st.session_state:
    st.info("⬆️ Upload file 2025 untuk memulai. File 2026 optional (pakai default dari D:\\scr).")
    st.stop()

m: MultiYearAnalyzer = st.session_state["my_analyzer"]
st.caption(f"📊 {len(m.df_all):,} rows · "
           f"2025={len(m.df_all[m.df_all['YEAR']==2025]):,} · "
           f"2026={len(m.df_all[m.df_all['YEAR']==2026]):,} · "
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
])

_bulan_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Des"]

# --- TAB 1: RINGKASAN YOY ---
with tab[0]:
    st.markdown("### 📋 Jan–Mei 2025 vs 2026")
    yoy = m.yoy_summary()
    # kolom numerik
    num_cols = yoy.select_dtypes(include=np.number).columns.tolist()
    st.dataframe(yoy, use_container_width=True, hide_index=True, height=400)

    # Highlight metric
    growth_row = yoy[yoy["Metrik"] == "Revenue Gross (Rp)"]
    if not growth_row.empty:
        g = growth_row.iloc[0]["Growth %"]
        g_v = growth_row.iloc[0]["Growth (Rp)"]
        color = "🟢" if g and g > 0 else "🔴"
        st.metric(f"{color} Pertumbuhan Revenue Gross (Jan–Mei)", f"{g:+.2f}%" if g else "N/A", f"Rp {g_v:,.0f}")

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
    st.markdown("### 🔮 Forecast Jun–Des 2026")
    st.caption(
        "Metode: trend 2025→2026 (Jan–Mei) diterapkan ke pola musiman 2025 per lokasi. "
        "Forecast aggregate per lokasi."
    )
    fc = m.forecast_aggregate()
    st.dataframe(fc, use_container_width=True, hide_index=True, height=500)

    # Pivot + chart
    if not fc.empty:
        rev_fc = fc[fc["Measure"] == "Revenue"].copy()
        if not rev_fc.empty:
            # Total per bulan
            total_rev = rev_fc.groupby("Bulan").agg(
                {"2025_Actual": "sum", "2026_Forecast": "sum"}
            ).reset_index()
            total_rev["Bulan"] = pd.Categorical(
                total_rev["Bulan"], categories=_bulan_names[5:], ordered=True
            )
            total_rev = total_rev.sort_values("Bulan")
            fig = px.line(
                total_rev, x="Bulan", y=["2025_Actual", "2026_Forecast"],
                markers=True, title="Forecast Revenue (Jun–Des 2026) vs 2025 Actual",
            )
            fig.update_layout(height=400)
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
