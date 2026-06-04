"""
Bundle Sales Analyzer - Web Edition (Streamlit)
================================================
Aplikasi web interaktif untuk menganalisa penjualan paket/bundle.
Jalankan:  streamlit run bundle_analyzer_web.py
Akses di:  http://localhost:8501
"""

import io
import os
import sys
import tempfile
from pathlib import Path

import bcrypt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Reuse analyzer dari file desktop
sys.path.insert(0, str(Path(__file__).parent))
from bundle_analyzer import BundleAnalyzer

# ============= PAGE CONFIG =============
st.set_page_config(
    page_title="Sales Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============= CUSTOM CSS =============
st.markdown(
    """
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }
    div[data-testid="stMetricDelta"] { font-size: 0.85rem; }
    .welcome-hero {
        text-align: center;
        padding: 2.5rem 0 1.5rem 0;
        background: linear-gradient(135deg, #1f77b4 0%, #2ca02c 100%);
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
    }
    .welcome-hero h1 { color: white; font-size: 2.8rem; margin: 0; }
    .welcome-hero p { color: #e8f5e9; font-size: 1.15rem; margin: 0.5rem 0 0 0; }
    .feature-card {
        background: #f8f9fa;
        border-left: 4px solid #1f77b4;
        padding: 1rem 1.2rem;
        border-radius: 8px;
        height: 100%;
    }
    .section-header {
        font-size: 1.4rem;
        font-weight: 600;
        color: #1f77b4;
        margin: 1rem 0 0.5rem 0;
        border-bottom: 2px solid #1f77b4;
        padding-bottom: 0.3rem;
    }
    .small-caption { color: #666; font-size: 0.85rem; }
</style>
""",
    unsafe_allow_html=True,
)

# ============= SESSION STATE =============
for _k, _v in {
    "analyzer": None,
    "data_loaded": False,
    "file_name": "",
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ============= HELPERS =============
COLOR_BUNDLE = "#9467bd"
COLOR_PRIMARY = "#1f77b4"
COLOR_SECONDARY = "#ff7f0e"
COLOR_SUCCESS = "#2ca02c"
COLOR_DANGER = "#d62728"
COLOR_NEUTRAL = "#7f7f7f"

PRESET_PERIODS = [
    "Semua data", "7 hari terakhir", "14 hari terakhir",
    "30 hari terakhir", "90 hari terakhir",
    "Bulan ini", "Bulan lalu",
    "3 bulan terakhir", "6 bulan terakhir",
    "Tahun ini (YTD)", "Custom",
]

# ============= AUTH =============
# Default fallback credentials (digunakan kalau st.secrets tidak ada).
# Untuk production, SET secrets di Streamlit Cloud dashboard!
# Format di secrets.toml:
#   [users]
#   admin = "$2b$12$..."
#   tonizz = "$2b$12$..."
DEFAULT_USERS = {
    "admin": "$2b$12$38P/ATKNv3p/d2kKebfxouS8TPeFZgSs9837E2oUSsewRe5uA7klq",
    "tonizz": "$2b$12$FKS3raeR9UZtbeNsqwvfAe5hKc6oC6LhP2Rkok6LZCjsj2BZFHVw.",
}
DEFAULT_PASSWORD_HINT = {
    "admin": "admin123",
    "tonizz": "tonizz2026",
}


def _get_users() -> dict:
    """Ambil user dict dari st.secrets (prioritas) atau fallback default."""
    try:
        if "users" in st.secrets:
            return dict(st.secrets["users"])
    except Exception:
        pass
    return DEFAULT_USERS


def _login_gate():
    """Tampilkan login form. Stop eksekusi kalau belum login."""
    if st.session_state.get("logged_in"):
        return True
    users = _get_users()
    st.markdown(
        """
<div style="max-width: 420px; margin: 4rem auto; padding: 2.5rem;
            background: white; border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);">
    <h2 style="text-align: center; color: #1f77b4; margin: 0 0 0.5rem 0;">🔐 Login</h2>
    <p style="text-align: center; color: #666; margin: 0 0 1.5rem 0;">
        Sales Analyzer — Akses Terbatas
    </p>
</div>
""",
        unsafe_allow_html=True,
    )
    with st.form("login_form", clear_on_submit=True):
        u = st.text_input("Username", placeholder="admin / tonizz")
        p = st.text_input("Password", type="password")
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            submit = st.form_submit_button("Masuk", use_container_width=True, type="primary")
        if submit:
            stored = users.get(u)
            if stored and bcrypt.checkpw(p.encode(), stored.encode()):
                st.session_state.logged_in = True
                st.session_state.user = u
                st.rerun()
            else:
                st.error("❌ Username atau password salah.")
    with st.expander("ℹ️ Info login default (dev only)"):
        for user, pw in DEFAULT_PASSWORD_HINT.items():
            st.caption(f"• **{user}** / `{pw}`")
        st.caption(
            "Untuk production, ganti dengan secrets Streamlit Cloud "
            "(Settings → Secrets)."
        )
    st.stop()
    return False


_login_gate()


def _format_rp(x) -> str:
    if pd.isna(x) or x is None:
        return "-"
    return f"Rp {x:,.0f}".replace(",", ".")


def _format_int(x) -> str:
    if pd.isna(x) or x is None:
        return "-"
    return f"{int(x):,}".replace(",", ".")


def _format_pct(x) -> str:
    if pd.isna(x) or x is None:
        return "-"
    return f"{x:.2f}%"


def process_file(uploaded, min_items, min_disc, loc_filter, date_preset, d_from, d_to):
    """Load & classify file, simpan analyzer di session_state."""
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        f.write(uploaded.getvalue())
        tmp = f.name
    try:
        a = BundleAnalyzer()
        a.load(tmp)
        a.classify(min_items=min_items, min_discount=min_disc)
        # Apply location filter
        if loc_filter and loc_filter.strip():
            locs = [x.strip() for x in loc_filter.split(",") if x.strip()]
            a.df = a.df[a.df["FLOCCD"].astype(str).isin(locs)].copy()
        # Guard: jika data kosong setelah filter lokasi, tetap lanjut dengan df kosong
        if a.df.empty:
            st.session_state.analyzer = a
            st.session_state.data_loaded = True
            st.session_state.file_name = uploaded.name
            st.warning(
                f"Tidak ada baris untuk lokasi '{loc_filter}'. Coba FLOCCD lain."
            )
            return
        # Apply date filter
        if date_preset != "Custom":
            ref = pd.to_datetime(a.df["FDATE"].max())
            start, end = BundleAnalyzer.calc_date_presets(ref).get(date_preset, (None, None))
        else:
            start, end = d_from, d_to
        if start is not None:
            a.df = a.df[a.df["FDATE"] >= pd.to_datetime(start)].copy()
        if end is not None:
            a.df = a.df[
                a.df["FDATE"] <= pd.to_datetime(end) + pd.Timedelta(hours=23, minutes=59, seconds=59)
            ].copy()
        st.session_state.analyzer = a
        st.session_state.data_loaded = True
        st.session_state.file_name = uploaded.name
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass


def to_excel_bytes(sheets: dict) -> bytes:
    """Convert dict of sheet_name -> DataFrame ke bytes Excel."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # BACA_DULU sheet
        readme_rows = [
            ["BUNDLE SALES ANALYZER - WEB EDITION", ""],
            ["", ""],
            ["Kriteria BUNDLE", "1 NOTRAN memiliki >= 2 item DAN semua item punya nilai DISCOUNT (%) yang SAMA."],
            ["", "Di-analisa per FLOCCD (kode lokasi/outlet)."],
            ["", ""],
            ["Total Revenue", "Sum dari JUALAHIR × QTY per baris"],
            ["Bundle Revenue", "Total Revenue dari transaksi yang terdeteksi sebagai bundle"],
            ["Bundle %", "Persentase bundle dari total transaksi"],
            ["LINE_REVENUE", "Pendapatan per baris (JUALAHIR × QTY)"],
            ["JUMLAH", "Subtotal per baris dari sumber data"],
        ]
        pd.DataFrame(readme_rows, columns=["Istilah", "Artinya"]).to_excel(
            writer, sheet_name="BACA_DULU", index=False
        )
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
    return output.getvalue()


# ============= SIDEBAR =============
with st.sidebar:
    st.markdown("## 📊 Sales Analyzer")
    st.caption("Web Edition · v2.0")
    st.markdown("---")
    uploaded = st.file_uploader("📁 **Upload File Excel**", type=["xlsx", "xls"])

    with st.expander("🔧 Filter & Pengaturan", expanded=True):
        min_items = st.number_input("Min item per bundle", 2, 20, 2)
        min_disc = st.number_input("Min discount %", 0.0, 100.0, 0.0, 0.5)
        loc_filter = st.text_input("FLOCCD filter (pisah koma)", placeholder="mis. 55592, 55733")
        date_preset = st.selectbox("Periode", PRESET_PERIODS)
        d_from, d_to = None, None
        if date_preset == "Custom":
            d_from = st.date_input("Dari tanggal", value=None)
            d_to = st.date_input("Sampai tanggal", value=None)

    if uploaded is not None:
        if st.button("🚀 Proses Data", type="primary", use_container_width=True):
            try:
                with st.spinner("⏳ Memuat & menganalisa data..."):
                    process_file(uploaded, min_items, min_disc, loc_filter, date_preset, d_from, d_to)
                st.success("✓ Data berhasil dimuat!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Gagal: {e}")

    if st.session_state.data_loaded:
        st.markdown("---")
        if st.button("🗑️ Reset / Upload Ulang", use_container_width=True):
            st.session_state.data_loaded = False
            st.session_state.analyzer = None
            st.session_state.file_name = ""
            st.rerun()

    st.markdown("---")
    st.caption(f"👤 Login sebagai: **{st.session_state.get('user', '?')}**")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()

    st.markdown("---")
    st.caption("💡 Tips: klik kolom tabel untuk sort, atau download Excel untuk laporan.")


# ============= MAIN AREA =============
if not st.session_state.data_loaded:
    # ---------- WELCOME SCREEN ----------
    st.markdown(
        """
<div class="welcome-hero">
    <h1>📊 Sales Analyzer</h1>
    <p>Analisa penjualan paket/bundle DAN item satuan dari data POS Anda — dengan visualisasi interaktif</p>
</div>
""",
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            '<div class="feature-card">📈 <b>10 Tab Analisa Lengkap</b><br/>'
            "Bundle, item satuan, summary, top produk, perbandingan, trend chart, dan lainnya.</div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            '<div class="feature-card">🎯 <b>Filter & Pencarian Mudah</b><br/>'
            "Preset tanggal, multi-lokasi, cari item tertentu dalam bundle.</div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            '<div class="feature-card">📥 <b>Export Excel 1-Klik</b><br/>'
            "Semua hasil analisa bisa di-download dalam format Excel (.xlsx).</div>",
            unsafe_allow_html=True,
        )
    st.markdown("")
    st.info("👈 **Upload file Excel di sidebar kiri untuk memulai.** Format yang didukung: `.xlsx` atau `.xls`")
    st.stop()


# ============= DATA LOADED =============
a: BundleAnalyzer = st.session_state.analyzer
df = a.df
b = df[df["IS_BUNDLE"]]
nb = df[~df["IS_BUNDLE"]]

# Header
st.markdown("# 📊 Sales Analyzer")
st.caption(
    f"📄 `{st.session_state.file_name}` · "
    f"{len(df):,} baris · {df['NOTRAN'].nunique():,} transaksi · "
    f"{df['FLOCCD'].nunique()} lokasi · "
    f"{int(b['IS_BUNDLE'].sum()):,} baris paket · "
    f"{b['NOTRAN'].nunique():,} transaksi paket · "
    f"{int((~df['IS_BUNDLE']).sum()):,} baris satuan"
)

# ---------- HERO METRICS ----------
total_rev = float(df["LINE_REVENUE"].sum())
bundle_rev = float(b["LINE_REVENUE"].sum())
n_tx = int(df["NOTRAN"].nunique())
n_b_tx = int(b["NOTRAN"].nunique())
bundle_pct = (n_b_tx / n_tx * 100) if n_tx > 0 else 0
avg_disc_bundle = float(b["BUNDLE_DISC_PCT"].mean()) if len(b) > 0 else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("💰 Total Revenue", _format_rp(total_rev))
m2.metric("🛒 Total Transaksi", _format_int(n_tx))
m3.metric(
    "📦 Bundle Transaksi",
    _format_int(n_b_tx),
    delta=f"{bundle_pct:.1f}% bundle",
)
m4.metric(
    "💎 Bundle Revenue",
    _format_rp(bundle_rev),
    delta=f"{bundle_rev / total_rev * 100:.1f}% dari total" if total_rev else "0%",
)

st.markdown("")

# ============= TABS =============
tabs = st.tabs(
    [
        "📊 Summary",
        "📈 Distribusi",
        "📋 Detail Bundle",
        "🏆 Top Combo",
        "🔍 Cari Paket",
        "🏆 Top Produk Bundle",
        "💰 Margin",
        "📊 Perbandingan",
        "📈 Trend",
        "📋 Item Satuan",
    ]
)

# ---------------- TAB 1: SUMMARY ----------------
with tabs[0]:
    st.markdown('<div class="section-header">📊 Ringkasan per Lokasi</div>', unsafe_allow_html=True)
    sm = a.summary_by_location()
    if sm.empty:
        st.warning("Tidak ada data.")
    else:
        # Chart: revenue by location
        fig = px.bar(
            sm.head(15),
            x="BUNDLE_REVENUE",
            y="FNAMA",
            orientation="h",
            color="BUNDLE_TX_PCT",
            color_continuous_scale="RdYlGn",
            title="Bundle Revenue per Lokasi (warna = % bundle)",
            labels={"BUNDLE_REVENUE": "Bundle Revenue (Rp)", "FNAMA": ""},
        )
        fig.update_layout(
            yaxis={"categoryorder": "total ascending"},
            height=420,
            coloraxis_colorbar=dict(title="Bundle %"),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Table
        sm_disp = sm.copy()
        st.dataframe(sm_disp, use_container_width=True, hide_index=True, height=400)

        # Download
        excel = to_excel_bytes({"Summary": sm})
        st.download_button(
            "📥 Download Summary (Excel)",
            data=excel,
            file_name="summary_lokasi.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

# ---------------- TAB 2: DISTRIBUSI DISKON ----------------
with tabs[1]:
    st.markdown('<div class="section-header">📈 Distribusi Discount Bundle</div>', unsafe_allow_html=True)
    dd = a.discount_distribution()
    if dd.empty:
        st.warning("Tidak ada data bundle.")
    else:
        # Chart: bar chart of discount% vs count
        fig = px.bar(
            dd,
            x="BUNDLE_DISC_PCT",
            y="JUMLAH_TX",
            color="FLOCCD",
            title="Distribusi Diskon Bundle per Lokasi",
            labels={"BUNDLE_DISC_PCT": "Diskon (%)", "JUMLAH_TX": "Jumlah Transaksi"},
        )
        fig.update_layout(height=450, barmode="group")
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(dd, use_container_width=True, hide_index=True, height=350)
        excel = to_excel_bytes({"Distribusi_Discount": dd})
        st.download_button(
            "📥 Download (Excel)",
            data=excel,
            file_name="distribusi_diskon.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

# ---------------- TAB 3: DETAIL BUNDLE ----------------
with tabs[2]:
    st.markdown('<div class="section-header">📋 Detail Bundle (1 baris = 1 item)</div>', unsafe_allow_html=True)
    det = a.bundle_detail()
    if det.empty:
        st.warning("Tidak ada bundle terdeteksi.")
    else:
        st.caption(f"Total {len(det):,} baris. Sort by NOTRAN untuk lihat 1 transaksi utuh.")
        st.dataframe(det, use_container_width=True, hide_index=True, height=500)
        excel = to_excel_bytes({"Detail_Bundle": det})
        st.download_button(
            "📥 Download (Excel)",
            data=excel,
            file_name="detail_bundle.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

# ---------------- TAB 4: TOP KOMBINASI ----------------
with tabs[3]:
    st.markdown('<div class="section-header">🏆 Top Kombinasi Bundle</div>', unsafe_allow_html=True)
    top_n = st.slider("Top N", 5, 50, 20, key="topcombo_n")
    tb = a.top_bundles(top_n)
    if tb.empty:
        st.warning("Tidak ada data.")
    else:
        # Chart: horizontal bar
        fig = px.bar(
            tb,
            x="JUMLAH_TX",
            y="KOMBINASI_ITEM",
            color="BUNDLE_DISC_PCT",
            orientation="h",
            title=f"Top {top_n} Kombinasi Bundle",
            color_continuous_scale="Viridis",
            labels={"JUMLAH_TX": "Jumlah Terjual", "KOMBINASI_ITEM": "Kombinasi"},
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=500)
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(tb, use_container_width=True, hide_index=True, height=400)
        excel = to_excel_bytes({"Top_Kombinasi": tb})
        st.download_button(
            "📥 Download (Excel)",
            data=excel,
            file_name="top_kombinasi.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

# ---------------- TAB 5: CARI ITEM ----------------
with tabs[4]:
    st.markdown('<div class="section-header">🔍 Cari Paket by Item</div>', unsafe_allow_html=True)
    st.caption("Ketik kode/nama item → lihat semua bundle yang mengandung item tersebut.")
    fc1, fc2, fc3, fc4 = st.columns([2, 1, 1, 1])
    with fc1:
        item_q = st.text_input("Kode / Nama Item", placeholder="mis. 64428, DURABEAM, PLAY")
    with fc2:
        search_floocd = st.text_input("FLOCCD (opsional)", placeholder="mis. 55592", key="srch_floocd")
    with fc3:
        date_from = st.date_input("Dari", value=None, key="srch_from")
    with fc4:
        date_to = st.date_input("Sampai", value=None, key="srch_to")

    if st.button("🔎 Cari Paket", type="primary") and item_q.strip():
        try:
            floocd_clean = search_floocd.strip() if search_floocd else None
            summary, packages = a.search_bundles_by_item(
                item_q.strip(),
                floocd=floocd_clean,
                date_from=str(date_from) if date_from else None,
                date_to=str(date_to) if date_to else None,
            )
            if packages.empty:
                st.warning(f"Tidak ditemukan paket yang mengandung '{item_q}'.")
            else:
                # Ringkasan metrics
                cm1, cm2, cm3, cm4 = st.columns(4)
                cm1.metric("📦 Jumlah Paket", _format_int(summary["Jumlah Paket"]))
                cm2.metric("💰 Total Nilai", _format_rp(summary["Total Nilai (Rp)"]))
                cm3.metric("📊 Total QTY", _format_int(summary["Total QTY"]))
                cm4.metric("🏷 Avg Diskon", _format_pct(summary["Rata-rata Diskon (%)"]))
                st.markdown("")
                st.dataframe(packages, use_container_width=True, hide_index=True, height=400)
                excel = to_excel_bytes({"Ringkasan": pd.DataFrame([summary]), "Detail_Paket": packages})
                st.download_button(
                    "📥 Download (Excel)",
                    data=excel,
                    file_name=f"bundle_search_{item_q.strip()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        except Exception as e:
            st.error(f"Error: {e}")

# ---------------- TAB 6: TOP PRODUK ----------------
with tabs[5]:
    st.markdown('<div class="section-header">🏆 Top Produk Bundle</div>', unsafe_allow_html=True)
    pn = st.slider("Top N", 5, 50, 20, key="topprod_n")
    tp = a.top_products_in_bundles(top_n=pn)
    if tp.empty:
        st.warning("Tidak ada data.")
    else:
        # Chart: horizontal bar
        fig = px.bar(
            tp,
            x="JUMLAH_BUNDLE",
            y="NAMA_BRG",
            orientation="h",
            color="AVG_DISC_PCT",
            color_continuous_scale="RdYlGn_r",
            title=f"Top {pn} Item Paling Sering di-Bundle",
            labels={"JUMLAH_BUNDLE": "Jumlah Bundle", "NAMA_BRG": ""},
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=500)
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(tp, use_container_width=True, hide_index=True, height=400)

        st.markdown("---")
        st.markdown("##### 🔗 Cari Pasangan Item")
        pair_q = st.text_input("Kode/Nama item", placeholder="mis. 64428", key="pair_q")
        if st.button("🔎 Cari Pasangan") and pair_q.strip():
            pairs = a.product_bundling_pairs(pair_q.strip(), top_n=pn)
            if pairs.empty:
                st.info(f"Tidak ada pasangan untuk '{pair_q}'.")
            else:
                st.dataframe(pairs, use_container_width=True, hide_index=True, height=300)
                excel = to_excel_bytes({"Top_Produk": tp, "Pasangan_Item": pairs})
                st.download_button(
                    "📥 Download (Excel)",
                    data=excel,
                    file_name="top_produk.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        else:
            excel = to_excel_bytes({"Top_Produk": tp})
            st.download_button(
                "📥 Download (Excel)",
                data=excel,
                file_name="top_produk.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

# ---------------- TAB 7: MARGIN ----------------
with tabs[6]:
    st.markdown('<div class="section-header">💰 Analisa Margin</div>', unsafe_allow_html=True)
    st.warning(
        "⚠️ Kolom `PRC_HIP` di data contoh adalah PLACEHOLDER (nilai 100). "
        "Gunakan field 'Asumsi biaya' di bawah untuk hasil yang akurat."
    )
    cost_assumption = st.number_input(
        "Asumsi biaya (% dari JUALAHIR). 0 = pakai PRC_HIP",
        min_value=0.0, max_value=100.0, value=30.0, step=1.0, key="mg_cost",
    )
    if st.button("💰 Hitung Margin", type="primary"):
        try:
            with st.spinner("Menghitung..."):
                summary, per_loc, dq = a.margin_analysis(
                    cost_pct_assumption=cost_assumption if cost_assumption > 0 else None,
                )
            if not summary or not dq.get("valid", True):
                st.error(
                    f"❌ Tidak bisa hitung margin: {dq.get('reason', 'data kosong')}. "
                    "Coba ubah filter atau upload ulang."
                )
            else:
                # KPI
                cm1, cm2, cm3 = st.columns(3)
                with cm1:
                    st.markdown("##### 📦 Bundle")
                    st.metric("Revenue", _format_rp(summary["Bundle"]["Total Revenue (Rp)"]))
                    st.metric("Margin", _format_rp(summary["Bundle"]["Total Margin (Rp)"]))
                    st.metric("Margin %", _format_pct(summary["Bundle"]["Avg Margin %"]))
                with cm2:
                    st.markdown("##### 📋 Non-Bundle")
                    st.metric("Revenue", _format_rp(summary["Non-Bundle"]["Total Revenue (Rp)"]))
                    st.metric("Margin", _format_rp(summary["Non-Bundle"]["Total Margin (Rp)"]))
                    st.metric("Margin %", _format_pct(summary["Non-Bundle"]["Avg Margin %"]))
                with cm3:
                    rev_b = summary["Bundle"]["Total Revenue (Rp)"]
                    rev_nb = summary["Non-Bundle"]["Total Revenue (Rp)"]
                    mar_b = summary["Bundle"]["Total Margin (Rp)"]
                    mar_nb = summary["Non-Bundle"]["Total Margin (Rp)"]
                    st.markdown("##### ⚖️ Perbandingan")
                    st.metric("Bundle share Revenue", _format_pct(rev_b / (rev_b + rev_nb) * 100) if (rev_b + rev_nb) else "-")
                    st.metric("Bundle share Margin", _format_pct(mar_b / (mar_b + mar_nb) * 100) if (mar_b + mar_nb) else "-")

                st.markdown("---")
                # Chart
                fig = go.Figure()
                categories = ["Bundle", "Non-Bundle"]
                fig.add_trace(go.Bar(name="Cost", x=categories, y=[
                    summary["Bundle"]["Total Cost (Rp)"], summary["Non-Bundle"]["Total Cost (Rp)"]
                ], marker_color=COLOR_DANGER))
                fig.add_trace(go.Bar(name="Margin", x=categories, y=[
                    summary["Bundle"]["Total Margin (Rp)"], summary["Non-Bundle"]["Total Margin (Rp)"]
                ], marker_color=COLOR_SUCCESS))
                fig.update_layout(barmode="stack", title="Revenue Breakdown: Cost vs Margin",
                                  yaxis_title="Rp", height=400)
                st.plotly_chart(fig, use_container_width=True)

                st.markdown("##### Per Lokasi")
                st.dataframe(per_loc, use_container_width=True, hide_index=True, height=400)

                excel = to_excel_bytes({
                    "Ringkasan": pd.DataFrame([
                        {"Kategori": k, **{kk: vv for kk, vv in v.items()}}
                        for k, v in summary.items()
                    ]),
                    "Per_Lokasi": per_loc,
                })
                st.download_button(
                    "📥 Download (Excel)",
                    data=excel,
                    file_name="margin_analysis.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        except Exception as e:
            st.error(f"Error: {e}")

# ---------------- TAB 8: PERBANDINGAN ----------------
with tabs[7]:
    st.markdown('<div class="section-header">📊 Perbandingan 2 Periode</div>', unsafe_allow_html=True)
    ref_max = pd.to_datetime(a.df["FDATE"].max())
    cmp_presets_list = list(BundleAnalyzer.calc_comparison_presets(ref_max).keys())
    preset = st.selectbox("Preset Pembanding", cmp_presets_list, index=1, key="cmp_preset")
    if preset != "Custom (isi manual)":
        p1s, p1e, p2s, p2e = BundleAnalyzer.calc_comparison_presets(ref_max)[preset]
        p1_from = pd.to_datetime(p1s).date()
        p1_to = pd.to_datetime(p1e).date()
        p2_from = pd.to_datetime(p2s).date()
        p2_to = pd.to_datetime(p2e).date()
    else:
        p1_from = p1_to = p2_from = p2_to = None

    cc1, cc2 = st.columns(2)
    with cc1:
        st.markdown("**Periode 1**")
        p1_from = st.date_input("Dari", value=p1_from, key="p1f")
        p1_to = st.date_input("Sampai", value=p1_to, key="p1t")
    with cc2:
        st.markdown("**Periode 2**")
        p2_from = st.date_input("Dari", value=p2_from, key="p2f")
        p2_to = st.date_input("Sampai", value=p2_to, key="p2t")

    if st.button("📊 Bandingkan", type="primary"):
        # Validasi tanggal
        if not all([p1_from, p1_to, p2_from, p2_to]):
            st.error("❌ Semua tanggal wajib diisi. Pilih preset atau isi manual.")
            st.stop()
        try:
            with st.spinner("Membandingkan..."):
                cmp_df = a.compare_periods(str(p1_from), str(p1_to), str(p2_from), str(p2_to))
                loc_cmp = a.compare_by_location(str(p1_from), str(p1_to), str(p2_from), str(p2_to))

            st.markdown("##### Ringkasan")
            # Bar chart side-by-side
            chart_df = cmp_df[["Metrik", "Periode 1", "Periode 2"]].copy()
            chart_df_melted = chart_df.melt(id_vars="Metrik", var_name="Periode", value_name="Nilai")
            fig = px.bar(
                chart_df_melted, x="Metrik", y="Nilai", color="Periode",
                barmode="group", title="Perbandingan Metrik",
                color_discrete_sequence=[COLOR_PRIMARY, COLOR_SECONDARY],
            )
            fig.update_layout(xaxis_tickangle=-30, height=400)
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(cmp_df, use_container_width=True, hide_index=True, height=300)

            st.markdown("##### Per Lokasi")
            # Growth chart
            growth_chart = loc_cmp.head(15).copy()
            def _growth_color(x):
                if pd.isna(x):
                    return COLOR_NEUTRAL
                return COLOR_SUCCESS if x >= 0 else COLOR_DANGER
            colors = [_growth_color(x) for x in growth_chart["Revenue_Growth_%"]]
            fig2 = go.Figure(go.Bar(
                x=growth_chart["FNAMA"].fillna(growth_chart["FLOCCD"].astype(str)),
                y=growth_chart["Revenue_Growth_%"],
                marker_color=colors,
                text=[f"{x:.1f}%" if pd.notna(x) else "-" for x in growth_chart["Revenue_Growth_%"]],
                textposition="outside",
            ))
            fig2.update_layout(
                title="Revenue Growth % per Lokasi (P1 vs P2)",
                yaxis_title="Growth %", height=400,
            )
            st.plotly_chart(fig2, use_container_width=True)
            st.dataframe(loc_cmp, use_container_width=True, hide_index=True, height=300)

            excel = to_excel_bytes({"Ringkasan_VS": cmp_df, "Per_Lokasi_VS": loc_cmp})
            st.download_button(
                "📥 Download (Excel)",
                data=excel,
                file_name="perbandingan.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.error(f"Error: {e}")

# ---------------- TAB 9: TREND ----------------
with tabs[8]:
    st.markdown('<div class="section-header">📈 Trend & Chart</div>', unsafe_allow_html=True)
    t1, t2, t3 = st.columns(3)
    with t1:
        gran = st.radio("Granularitas", ["Harian", "Bulanan"], horizontal=True)
    with t2:
        metric = st.selectbox("Metrik", ["Revenue", "Bundle Revenue", "Transaksi", "Bundle Transaksi"])
    with t3:
        show_data = st.checkbox("Tampilkan tabel", value=True)

    if st.button("📈 Generate Chart", type="primary"):
        try:
            with st.spinner("Membuat chart..."):
                if gran == "Harian":
                    trend = a.daily_trend()
                    x_col = "DATE"
                else:
                    trend = a.monthly_trend()
                    x_col = "YM"

            if trend.empty:
                st.warning("Tidak ada data pada filter aktif.")
                st.stop()

            metric_map = {
                "Revenue": ("Revenue", "Total Revenue (Rp)"),
                "Bundle Revenue": ("Bundle_Revenue", "Bundle Revenue (Rp)"),
                "Transaksi": ("TX", "Jumlah Transaksi"),
                "Bundle Transaksi": ("Bundle_TX", "Bundle Transaksi"),
            }
            y_col, y_label = metric_map[metric]
            x_vals = pd.to_datetime(trend[x_col]) if x_col == "DATE" else trend[x_col]

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=x_vals, y=trend[y_col], mode="lines+markers",
                name=y_label, line=dict(color=COLOR_PRIMARY, width=3),
                marker=dict(size=8),
                fill="tozeroy", fillcolor="rgba(31, 119, 180, 0.15)",
            ))
            fig.update_layout(
                title=f"Tren {y_label} ({gran})",
                xaxis_title="Tanggal" if x_col == "DATE" else "Bulan",
                yaxis_title=y_label,
                height=450, hovermode="x unified",
            )
            st.plotly_chart(fig, use_container_width=True)

            if show_data:
                st.dataframe(trend, use_container_width=True, hide_index=True, height=300)

            # Download button selalu tersedia (di luar if show_data)
            excel = to_excel_bytes({"Trend": trend})
            st.download_button(
                "📥 Download (Excel)",
                data=excel,
                file_name="trend.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="trend_dl",
            )
        except Exception as e:
            st.error(f"Error: {e}")

# ---------------- TAB 10: ITEM SATUAN ----------------
with tabs[9]:
    st.markdown(
        '<div class="section-header">📋 Analisa Item Satuan (Non-Bundle)</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"Total **{(~df['IS_BUNDLE']).sum():,}** baris item satuan dari **{(~df['IS_BUNDLE']).groupby(df['NOTRAN']).any().sum():,}** transaksi."
    )

    sub = st.tabs([
        "📊 Ringkasan",
        "📋 Detail",
        "🏆 Top Item",
        "📈 Dist. Diskon",
        "🔍 Cari Item",
    ])

    # ---------- Sub-tab 1: Ringkasan per Lokasi ----------
    with sub[0]:
        sm1 = a.summary_single_items()
        if sm1.empty:
            st.warning("Tidak ada data item satuan.")
        else:
            fig = px.bar(
                sm1.head(15),
                x="TOTAL_REVENUE",
                y="FNAMA" if "FNAMA" in sm1.columns else "FLOCCD",
                orientation="h",
                color="AVG_DISC_PCT",
                color_continuous_scale="RdYlGn_r",
                title="Revenue Item Satuan per Lokasi (warna = avg diskon)",
                labels={"TOTAL_REVENUE": "Revenue (Rp)"},
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=420)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(sm1, use_container_width=True, hide_index=True, height=400)
            st.download_button(
                "📥 Download Ringkasan (Excel)",
                data=to_excel_bytes({"Ringkasan_Satuan": sm1}),
                file_name="ringkasan_satuan.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_sm1",
            )

    # ---------- Sub-tab 2: Detail ----------
    with sub[1]:
        st.caption("1 baris = 1 item satuan. Sort by NOTRAN untuk lihat 1 transaksi utuh.")
        with st.spinner("Memuat detail..."):
            det1 = a.detail_single_items()
        st.dataframe(det1, use_container_width=True, hide_index=True, height=500)
        st.caption(f"Total {len(det1):,} baris.")
        st.download_button(
            "📥 Download Detail (Excel)",
            data=to_excel_bytes({"Detail_Satuan": det1}),
            file_name="detail_satuan.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_det1",
        )

    # ---------- Sub-tab 3: Top Item Satuan ----------
    with sub[2]:
        n_top = st.slider("Top N", 5, 50, 20, key="top_satuan_n")
        tp1 = a.top_single_items(top_n=n_top)
        if tp1.empty:
            st.warning("Tidak ada data.")
        else:
            fig = px.bar(
                tp1,
                x="TOTAL_QTY",
                y="NAMA_BRG",
                orientation="h",
                color="AVG_PRICE",
                color_continuous_scale="Viridis",
                title=f"Top {n_top} Item Paling Laris (Satuan)",
                labels={"TOTAL_QTY": "Total QTY", "NAMA_BRG": ""},
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=500)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(tp1, use_container_width=True, hide_index=True, height=400)
            st.download_button(
                "📥 Download (Excel)",
                data=to_excel_bytes({"Top_Item_Satuan": tp1}),
                file_name="top_item_satuan.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_tp1",
            )

    # ---------- Sub-tab 4: Distribusi Diskon Item ----------
    with sub[3]:
        dd1 = a.single_item_discount_dist()
        if dd1.empty:
            st.warning("Tidak ada data.")
        else:
            # Ambil 10 diskon teratas per lokasi untuk chart
            top_dd = dd1.sort_values("JUMLAH_TX", ascending=False).head(30)
            fig = px.bar(
                top_dd,
                x="DISCOUNT_PCT",
                y="JUMLAH_TX",
                color="FLOCCD",
                title="Distribusi Diskon Item Satuan (Top 30 by count)",
                labels={"DISCOUNT_PCT": "Diskon (%)", "JUMLAH_TX": "Jumlah Transaksi"},
            )
            fig.update_layout(height=450, barmode="group")
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"Total {len(dd1):,} kombinasi diskon×lokasi.")
            st.dataframe(dd1, use_container_width=True, hide_index=True, height=350)
            st.download_button(
                "📥 Download (Excel)",
                data=to_excel_bytes({"Dist_Diskon_Satuan": dd1}),
                file_name="dist_diskon_satuan.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_dd1",
            )

    # ---------- Sub-tab 5: Cari Item Satuan ----------
    with sub[4]:
        st.caption("Cari baris item satuan (per-item, bukan per-paket) yang mengandung keyword.")
        sc1, sc2, sc3, sc4 = st.columns([2, 1, 1, 1])
        with sc1:
            sq = st.text_input("Kode / Nama Item", placeholder="mis. 64428, DURABEAM", key="sq1")
        with sc2:
            sfloocd = st.text_input("FLOCCD (opsional)", placeholder="mis. 55592", key="sf1")
        with sc3:
            sdate_from = st.date_input("Dari", value=None, key="sdf1")
        with sc4:
            sdate_to = st.date_input("Sampai", value=None, key="sdt1")

        if st.button("🔎 Cari Item Satuan", type="primary", key="btn_sq1") and sq.strip():
            try:
                summary_s, packages_s = a.search_single_items_by_item(
                    sq.strip(),
                    floocd=sfloocd.strip() if sfloocd else None,
                    date_from=str(sdate_from) if sdate_from else None,
                    date_to=str(sdate_to) if sdate_to else None,
                )
                if packages_s.empty:
                    st.warning(f"Tidak ada item satuan cocok '{sq}'.")
                else:
                    cm1, cm2, cm3 = st.columns(3)
                    cm1.metric("📋 Jumlah Baris", _format_int(summary_s["Jumlah Baris"]))
                    cm2.metric("💰 Total Nilai", _format_rp(summary_s["Total Nilai (Rp)"]))
                    cm3.metric("📊 Total QTY", _format_int(summary_s["Total QTY"]))
                    st.dataframe(packages_s, use_container_width=True, hide_index=True, height=400)
                    st.download_button(
                        "📥 Download (Excel)",
                        data=to_excel_bytes({
                            "Ringkasan": pd.DataFrame([summary_s]),
                            "Detail": packages_s,
                        }),
                        file_name=f"cari_satuan_{sq.strip()}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_sq1",
                    )
            except Exception as e:
                st.error(f"Error: {e}")

# Footer
st.markdown("---")
st.caption(
    f"💎 Sales Analyzer · Web Edition · "
    f"Streamlit + Plotly · Data: `{st.session_state.file_name}`"
)
