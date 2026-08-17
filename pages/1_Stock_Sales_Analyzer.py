"""
Stock & Sales Analyzer — Streamlit Multi-Page
==============================================
Halaman terpisah (terintegrasi via sidebar) untuk analisis file
'stock & sales all (4).xlsx' (Penjualan + DBS).

INTEGRATION:
  - Letakkan di D:\\scr\\pages\\1_Stock_Sales_Analyzer.py
  - bundle_analyzer_web.py TIDAK diubah sama sekali
  - Auth di-duplikasi (kecil, ±20 baris) supaya halaman ini berdiri sendiri
  - Session state di-share dengan halaman utama (login cukup sekali)
  - Akses via sidebar: "Stock Sales Analyzer" (muncul otomatis oleh Streamlit)

CARA PAKAI:
  1. Jalankan streamlit seperti biasa:
       streamlit run bundle_analyzer_web.py
  2. Login di halaman utama
  3. Klik "Stock_Sales_Analyzer" di sidebar
  4. Upload file 'stock  & sales all (4).xlsx'
  5. Klik "🚀 Proses Data"
  6. Explore 9 tab analisis + download Excel

DEPLOY KE STREAMLIT CLOUD:
  Push folder pages/ ini ke GitHub. Streamlit auto-detect multi-page.
"""
from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

# Tambah parent dir ke path supaya bisa import stock_sales_analyzer
# (file ini di subfolder pages/, parent = D:\scr)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from stock_sales_analyzer import StockSalesAnalyzer

# Auth terpusat (auth.py): login sekali untuk semua halaman
from auth import login_gate, render_logout

# ============================================================================
# PAGE CONFIG + AUTH
# ============================================================================
st.set_page_config(
    page_title="Stock & Sales Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

login_gate(subtitle="Stock & Sales Analyzer", form_key="login_ssa")

# Sidebar: info user + link kembali + logout
with st.sidebar:
    st.markdown("---")
    render_logout(key="logout_ssa")
    st.markdown("---")

# ============================================================================
# HEADER
# ============================================================================
st.title("📊 Stock & Sales Analyzer")
st.caption(
    "Analisa file `stock & sales all (4).xlsx` (sheet **Penjualan** + sheet **DBS**) "
    "— multi-brand, multi-lokasi, multi-dimensi. "
    "9 analisis: stock coverage, dead stock, margin real, reorder, cross-brand bundle, "
    "discount audit, anomaly detection."
)
st.caption(
    "🔒 **Isolasi**: kode ini **100% terpisah** dari `bundle_analyzer_web.py`. "
    "File logic ada di `stock_sales_analyzer.py`."
)
st.divider()

# ============================================================================
# FILE UPLOAD
# ============================================================================
uploaded = st.file_uploader(
    "📁 Upload file Excel `stock & sales` (2 sheets: Penjualan + DBS)",
    type=["xlsx"],
    key="ssa_upload",
    help="File yang sama dengan 'stock & sales all (4).xlsx'",
)

SSA_KEY = "ssa_analyzer"  # session_state key untuk analyzer instance


def _load_ssa(uploaded_file) -> StockSalesAnalyzer:
    """Load uploaded file → StockSalesAnalyzer instance."""
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        f.write(uploaded_file.getvalue())
        tmp = f.name
    a = StockSalesAnalyzer()
    a.load(tmp)
    try:
        Path(tmp).unlink()
    except OSError:
        pass
    return a


if uploaded is not None:
    if st.button("🚀 Proses Data", type="primary", key="ssa_process"):
        with st.spinner("⏳ Membaca & normalisasi 2 sheet..."):
            try:
                st.session_state[SSA_KEY] = _load_ssa(uploaded)
                st.session_state["ssa_fname"] = getattr(uploaded, "name", "data.xlsx")
            except Exception as e:
                st.error(f"❌ Gagal load file: {e}")
                st.exception(e)
                st.stop()
        st.success(
            f"✅ Data loaded: {len(st.session_state[SSA_KEY].sales_df):,} baris sales, "
            f"{len(st.session_state[SSA_KEY].stock_df):,} baris stock"
        )
        st.rerun()

# ============================================================================
# ANALISIS (hanya render kalau data sudah loaded)
# ============================================================================
if SSA_KEY not in st.session_state:
    st.info("⬆️ Upload file Excel untuk mulai. Format yang diharapkan: sheet `Penjualan Jan-May 2026 (2)` + sheet `DBS`.")
    st.stop()

a: StockSalesAnalyzer = st.session_state[SSA_KEY]
fname = st.session_state.get("ssa_fname", "data.xlsx")
st.success(f"📂 Loaded: **{fname}**")

# Pre-compute semua hasil (cache di session_state biar gak hitung ulang tiap rerun)
SSA_RES = "ssa_results"


def _compute_all():
    """Hitung semua analisis & simpan di session_state."""
    if SSA_RES in st.session_state:
        return st.session_state[SSA_RES]
    results = {}
    results["cov"] = a.stock_coverage()
    results["risk"] = a.stockout_risk(top_n=200)
    results["margin"] = a.margin_analysis_real()
    results["dead"] = a.dead_stock()
    results["dead_det"] = a.dead_stock_detail()
    results["xb_tx"] = a.cross_brand_bundles()
    results["xb_combo"] = a.cross_brand_bundle_items(top_n=50)
    results["reorder"] = a.reorder_recommendations()
    results["disc"] = a.discount_audit()
    results["stk_anom"] = a.stock_anomalies()
    st.session_state[SSA_RES] = results
    return results


with st.spinner("⏳ Menghitung 9 analisis..."):
    R = _compute_all()

# ============================================================================
# 9 TABS
# ============================================================================
tab_names = [
    "📋 Ringkasan",
    "📦 Stock Coverage",
    "⚠️ Stockout Risk",
    "💰 Margin Real",
    "💀 Dead Stock",
    "🔗 Cross-Brand",
    "📊 Reorder",
    "🔍 Audit",
    "💾 Export",
]
tabs = st.tabs(tab_names)


def _format_rp(n: float) -> str:
    if pd.isna(n) or n == 0:
        return "Rp 0"
    if abs(n) >= 1e9:
        return f"Rp {n/1e9:.2f}M"
    if abs(n) >= 1e6:
        return f"Rp {n/1e6:.2f}jt"
    if abs(n) >= 1e3:
        return f"Rp {n/1e3:.1f}rb"
    return f"Rp {n:,.0f}"


# --- TAB 1: RINGKASAN ---
with tabs[0]:
    st.markdown("### 📋 Ringkasan File")
    s = a.sales_df
    stk = a.stock_df
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Sales rows", f"{len(s):,}")
        st.metric("Stock rows (item×lokasi)", f"{len(stk):,}")
    with c2:
        st.metric("Lokasi (sales)", f"{s['FNAMA'].nunique()}")
        st.metric("Lokasi (stock)", f"{stk['FNAMA'].nunique()}")
    with c3:
        st.metric("PLU terjual", f"{s['PLU'].nunique()}")
        st.metric("PLU di stock", f"{stk['PLU'].nunique()}")
    with c4:
        st.metric("Brand", f"{s['BRAND'].nunique()}")
        st.metric("UB", f"{s['UB'].nunique()}")
    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total QTY Sold", f"{int(s['QTY'].sum()):,}")
        st.metric("Periode", f"{s['FDATE'].min().date()} → {s['FDATE'].max().date()}")
    with c2:
        st.metric(
            "Total Revenue Gross",
            _format_rp(s["LINE_REVENUE_GROSS"].sum()),
        )
        st.metric(
            "Total Revenue Net",
            _format_rp(s["LINE_REVENUE_NET"].sum()),
        )
    with c3:
        st.metric("Total Discount", _format_rp(s["DISC"].sum()))
        st.metric("Avg Discount %", f"{s['DISC_PCT'].mean():.2f}%")
    st.divider()
    sm = R["margin"]["summary"]
    st.markdown("### 💰 Margin (real cost)")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Cost", _format_rp(sm["Total Cost (Rp)"]))
    with c2:
        st.metric("Total Margin", _format_rp(sm["Total Margin (Rp)"]))
    with c3:
        st.metric("Avg Margin %", f"{sm['Avg Margin %']}%")
    with c4:
        st.metric("Total QTY", f"{sm['Total QTY']:,}")
    st.divider()
    st.markdown("### ⚠️ Quick Alerts")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(
            "Stockout Risk Items",
            f"{len(R['risk']):,}",
            help="Coverage < 14 hari",
        )
    with c2:
        n_dead = int((stk["SALES"] == 0).sum())
        st.metric(
            "Dead Items (sales=0)",
            f"{n_dead:,}",
            help="Item di stock tapi tidak laku 5 bulan",
        )
    with c3:
        st.metric(
            "Stock Anomalies",
            f"{len(R['stk_anom']):,}",
            help="Stock negatif, TO negatif, dll",
        )


# --- TAB 2: STOCK COVERAGE ---
with tabs[1]:
    st.markdown("### 📦 Stock Coverage (Days of Inventory)")
    st.caption("Coverage = Stock / (Sales / Active_Days). < 14 hari = STOCKOUT_RISK.")
    cov = R["cov"]
    # Status counts
    status_counts = cov["COVERAGE_STATUS"].value_counts()
    cols = st.columns(len(status_counts))
    for i, (status, count) in enumerate(status_counts.items()):
        with cols[i]:
            color = {
                "STOCKOUT_RISK": "🔴",
                "NEG_STOCK": "⚠",
                "LOW": "🟠",
                "HEALTHY": "🟢",
                "HIGH": "🟡",
                "OVERSTOCK": "🔵",
                "NO_SALES": "⚫",
            }.get(status, "")
            st.metric(f"{color} {status}", f"{count:,}")
    st.divider()
    f1, f2 = st.columns(2)
    with f1:
        status_filter = st.multiselect(
            "Filter status:",
            options=cov["COVERAGE_STATUS"].unique().tolist(),
            default=["STOCKOUT_RISK", "NEG_STOCK", "NO_SALES", "LOW"],
        )
    with f2:
        loc_filter = st.multiselect(
            "Filter lokasi:",
            options=sorted(cov["FNAMA"].unique().tolist()),
            default=None,
        )
    filtered = cov.copy()
    if status_filter:
        filtered = filtered[filtered["COVERAGE_STATUS"].isin(status_filter)]
    if loc_filter:
        filtered = filtered[filtered["FNAMA"].isin(loc_filter)]
    st.dataframe(filtered, use_container_width=True, hide_index=True, height=500)
    st.download_button(
        "📥 Download Stock Coverage (CSV)",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name="stock_coverage.csv",
        mime="text/csv",
    )


# --- TAB 3: STOCKOUT RISK ---
with tabs[2]:
    st.markdown("### ⚠️ Stockout Risk (Top 200)")
    st.caption("Item berisiko stockout: coverage < 14 hari DAN ada sales velocity.")
    risk = R["risk"]
    st.metric("Total items at risk", f"{len(risk):,}")
    st.dataframe(risk, use_container_width=True, hide_index=True, height=500)
    if not risk.empty and "AVG_DAILY_SALES" in risk.columns:
        fig = px.bar(
            risk.head(30),
            x="DAYS_OF_INVENTORY",
            y="NAMA_BRG",
            color="FNAMA",
            orientation="h",
            title="Top 30 paling kritis (coverage terkecil)",
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=600)
        st.plotly_chart(fig, use_container_width=True)
    st.download_button(
        "📥 Download Stockout Risk (CSV)",
        data=risk.to_csv(index=False).encode("utf-8"),
        file_name="stockout_risk.csv",
        mime="text/csv",
    )


# --- TAB 4: MARGIN REAL ---
with tabs[3]:
    st.markdown("### 💰 Margin Analysis (Real Cost)")
    st.caption("Margin dihitung dengan COST real dari sheet DBS (bukan placeholder).")
    margin = R["margin"]
    sm = margin["summary"]
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Revenue Gross", _format_rp(sm["Total Revenue Gross (Rp)"]))
    with c2:
        st.metric("Revenue Net", _format_rp(sm["Total Revenue Net (Rp)"]))
    with c3:
        st.metric("Total Cost", _format_rp(sm["Total Cost (Rp)"]))
    with c4:
        st.metric("Total Margin", _format_rp(sm["Total Margin (Rp)"]))
    with c5:
        st.metric("Avg Margin %", f"{sm['Avg Margin %']}%")
    st.divider()
    m_tabs = st.tabs([
        "Per Brand",
        "Per Divisi",
        "Per Area",
        "Per SPV",
        "Per Lokasi",
    ])
    for tab, key, label in zip(
        m_tabs,
        ["per_brand", "per_divisi", "per_area", "per_spv", "per_lokasi"],
        ["Brand", "Divisi", "Area", "SPV", "Lokasi"],
    ):
        with tab:
            df = margin[key]
            st.dataframe(df, use_container_width=True, hide_index=True, height=400)
            if "Total Margin (Rp)" in df.columns and len(df) > 1:
                fig = px.bar(
                    df,
                    x=df.columns[0],
                    y="Total Margin (Rp)",
                    color="Avg Margin %",
                    color_continuous_scale="RdYlGn",
                    title=f"Margin {label}",
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            st.download_button(
                f"📥 Margin {label} (CSV)",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name=f"margin_{key}.csv",
                mime="text/csv",
                key=f"dl_{key}",
            )


# --- TAB 5: DEAD STOCK ---
with tabs[4]:
    st.markdown("### 💀 Dead Stock")
    st.caption(
        "FULLY_DEAD = stock=0 & sales=0 | STOCK_ONLY = sales=0 (slow) | "
        "OVERSOLD = stock negatif (audit needed)"
    )
    dead = R["dead"]
    st.metric("Total agregat groups", f"{len(dead):,}")
    st.dataframe(dead, use_container_width=True, hide_index=True, height=400)
    st.divider()
    st.markdown("#### 📋 Detail per Item (drill-down)")
    dead_det = R["dead_det"]
    f1, f2 = st.columns(2)
    with f1:
        cat_filter = st.multiselect(
            "Kategori dead:",
            options=dead_det["DEAD_CATEGORY"].unique().tolist(),
            default=dead_det["DEAD_CATEGORY"].unique().tolist(),
        )
    with f2:
        brand_filter = st.multiselect(
            "Brand:",
            options=dead_det["BRAND"].unique().tolist(),
            default=dead_det["BRAND"].unique().tolist(),
        )
    fdf = dead_det[
        dead_det["DEAD_CATEGORY"].isin(cat_filter)
        & dead_det["BRAND"].isin(brand_filter)
    ]
    st.metric("Filtered items", f"{len(fdf):,}")
    st.dataframe(fdf, use_container_width=True, hide_index=True, height=500)
    st.download_button(
        "📥 Download Dead Stock Detail (CSV)",
        data=fdf.to_csv(index=False).encode("utf-8"),
        file_name="dead_stock_detail.csv",
        mime="text/csv",
    )


# --- TAB 6: CROSS-BRAND ---
with tabs[5]:
    st.markdown("### 🔗 Cross-Brand Bundle Analysis")
    st.caption(
        "Bundle cross-brand = (LOKASI, TANGGAL) dengan item dari ≥ 2 brand berbeda. "
        "Proxy untuk NOTRAN (file ini tidak punya NOTRAN)."
    )
    xb_tx = R["xb_tx"]
    xb_combo = R["xb_combo"]
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Cross-brand transactions", f"{len(xb_tx):,}")
    with c2:
        st.metric("Unique item combinations", f"{len(xb_combo):,}")
    st.divider()
    st.markdown("#### 📋 Cross-Brand Transactions")
    st.dataframe(xb_tx, use_container_width=True, hide_index=True, height=400)
    st.divider()
    st.markdown("#### 🏆 Top Item Combinations (cross-brand)")
    st.dataframe(xb_combo, use_container_width=True, hide_index=True, height=400)
    if not xb_combo.empty and "FREQUENCY" in xb_combo.columns:
        fig = px.bar(
            xb_combo.head(20),
            x="FREQUENCY",
            y="COMBO",
            orientation="h",
            color="N_BRANDS",
            title="Top 20 kombinasi item cross-brand",
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=600)
        st.plotly_chart(fig, use_container_width=True)


# --- TAB 7: REORDER ---
with tabs[6]:
    st.markdown("### 📊 Reorder Recommendations")
    st.caption(
        "STOP_ORDER: TO < 0.5 (slow) | NORMAL: 0.5-1 | BOOST: 1-3 | URGENT: >3 | "
        "OVERSOLD_AUDIT: stock negatif"
    )
    reorder = R["reorder"]
    rec_counts = reorder["RECOMMENDATION"].value_counts()
    cols = st.columns(len(rec_counts))
    for i, (rec, count) in enumerate(rec_counts.items()):
        with cols[i]:
            color = {
                "STOP_ORDER": "🛑",
                "NORMAL": "🟢",
                "BOOST": "🟡",
                "URGENT_REORDER": "🔴",
                "OVERSOLD_AUDIT": "⚠",
            }.get(rec, "")
            st.metric(f"{color} {rec}", f"{count:,}")
    st.divider()
    f1, f2 = st.columns(2)
    with f1:
        rec_filter = st.multiselect(
            "Filter rekomendasi:",
            options=reorder["RECOMMENDATION"].unique().tolist(),
            default=["URGENT_REORDER", "OVERSOLD_AUDIT", "BOOST"],
        )
    with f2:
        loc_filter_r = st.multiselect(
            "Filter lokasi:",
            options=sorted(reorder["FNAMA"].unique().tolist()),
            default=None,
            key="reorder_loc",
        )
    rf = reorder[reorder["RECOMMENDATION"].isin(rec_filter)]
    if loc_filter_r:
        rf = rf[rf["FNAMA"].isin(loc_filter_r)]
    st.metric("Filtered items", f"{len(rf):,}")
    st.dataframe(rf, use_container_width=True, hide_index=True, height=500)
    st.download_button(
        "📥 Download Reorder (CSV)",
        data=rf.to_csv(index=False).encode("utf-8"),
        file_name="reorder_recommendations.csv",
        mime="text/csv",
    )


# --- TAB 8: AUDIT (Discount + Stock Anomalies) ---
with tabs[7]:
    st.markdown("### 🔍 Audit (Discount + Stock Anomalies)")
    a_tabs = st.tabs(["💸 Discount Audit", "🚨 Stock Anomalies"])
    with a_tabs[0]:
        st.caption(
            "Flag: DISC_NEGATIVE (markup), DISC_OVER_100%, DISC_OVER_80% (high), "
            "NET_NEGATIVE, SELL_ZERO, PPN_MISMATCH"
        )
        disc = R["disc"]
        if disc.empty:
            st.success("✅ Tidak ada anomali diskon terdeteksi.")
        else:
            st.metric("Total anomalies", f"{len(disc):,}")
            st.dataframe(
                disc["ANOMALY"].value_counts().reset_index().rename(
                    columns={"index": "ANOMALY", "ANOMALY": "Count"}
                ),
                use_container_width=True,
                hide_index=True,
            )
            f1, f2 = st.columns(2)
            with f1:
                anom_filter = st.multiselect(
                    "Filter anomali:",
                    options=disc["ANOMALY"].unique().tolist(),
                    default=disc["ANOMALY"].unique().tolist(),
                    key="disc_filter",
                )
            with f2:
                st.metric(
                    "Anomali paling serius",
                    disc[disc["ANOMALY"].isin(["DISC_OVER_100%", "DISC_NEGATIVE (markup)"])].shape[0]
                    if any(
                        x in disc["ANOMALY"].unique()
                        for x in ["DISC_OVER_100%", "DISC_NEGATIVE (markup)"]
                    )
                    else 0,
                )
            df = disc[disc["ANOMALY"].isin(anom_filter)]
            st.dataframe(df, use_container_width=True, hide_index=True, height=500)
            st.download_button(
                "📥 Download Discount Audit (CSV)",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name="discount_audit.csv",
                mime="text/csv",
            )
    with a_tabs[1]:
        st.caption(
            "Flag: STOCK_NEGATIVE, DIFF_QTY_NONZERO (stock opname), "
            "TO_NEGATIVE (oversold), TO_EXTREME (>10x)"
        )
        sa = R["stk_anom"]
        if sa.empty:
            st.success("✅ Tidak ada anomali stock terdeteksi.")
        else:
            st.metric("Total anomalies", f"{len(sa):,}")
            st.dataframe(
                sa["ANOMALY"].value_counts().reset_index().rename(
                    columns={"index": "ANOMALY", "ANOMALY": "Count"}
                ),
                use_container_width=True,
                hide_index=True,
            )
            st.dataframe(sa, use_container_width=True, hide_index=True, height=500)
            st.download_button(
                "📥 Download Stock Anomalies (CSV)",
                data=sa.to_csv(index=False).encode("utf-8"),
                file_name="stock_anomalies.csv",
                mime="text/csv",
            )


# --- TAB 9: EXPORT ---
with tabs[8]:
    st.markdown("### 💾 Export ke Excel (multi-sheet)")
    st.caption(
        "Export semua 9 analisis + summary jadi 1 file Excel dengan 16 sheet. "
        "Cocok untuk dishare ke tim/management."
    )
    default_fname = fname.replace(".xlsx", "_analysis.xlsx")
    output_name = st.text_input("Nama file output:", value=default_fname)
    if st.button("📥 Generate & Download Excel", type="primary", key="ssa_export"):
        with st.spinner("⏳ Generating 16-sheet Excel..."):
            try:
                a.export_excel(output_name)
                with open(output_name, "rb") as f:
                    bytes_data = f.read()
                st.download_button(
                    label=f"⬇️ Download {output_name}",
                    data=bytes_data,
                    file_name=output_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                try:
                    Path(output_name).unlink()
                except OSError:
                    pass
                st.success(f"✅ Excel generated: {len(bytes_data):,} bytes")
            except Exception as e:
                st.error(f"❌ Gagal export: {e}")
                st.exception(e)
    st.divider()
    st.markdown("#### 📊 Ringkasan Sheet yang akan di-export")
    sheets_info = [
        ("SUMMARY", "Key metrics + summary per kategori"),
        ("STOCK_COVERAGE", "Days of inventory per item per lokasi"),
        ("STOCKOUT_RISK", "Top 200 item berisiko stockout"),
        ("MARGIN_SUMMARY", "Ringkasan margin overall"),
        ("MARGIN_PER_BRAND", "Margin per brand (INTEX/RBO/HERO KIDS)"),
        ("MARGIN_PER_DIVISI", "Margin per divisi (STAND/COUNTER/ONLINE/TC)"),
        ("MARGIN_PER_AREA", "Margin per area (JABODETABEK/BALI/dst)"),
        ("MARGIN_PER_SPV", "Margin per SPV"),
        ("MARGIN_PER_LOKASI", "Margin per lokasi"),
        ("DEAD_STOCK", "Dead stock agregat per Lokasi × SPV × Brand"),
        ("DEAD_STOCK_DETAIL", "Detail per item (10K+ rows)"),
        ("CROSS_BRAND_TX", "Transaksi cross-brand"),
        ("CROSS_BRAND_COMBOS", "Top 50 item combinations"),
        ("REORDER", "Rekomendasi order + suggested qty"),
        ("DISCOUNT_AUDIT", "Anomali diskon"),
        ("STOCK_ANOMALIES", "Anomali stock (3K+ rows)"),
    ]
    for s, d in sheets_info:
        st.markdown(f"- **{s}** — {d}")
