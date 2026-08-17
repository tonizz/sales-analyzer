"""
Bundle Sales Analyzer - Web Edition (Streamlit)
================================================
Aplikasi web interaktif untuk menganalisa penjualan paket/bundle.
Jalankan:  streamlit run bundle_analyzer_web.py
Akses di:  http://localhost:8501
"""

import io
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
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
# Autentikasi terpusat di auth.py (login sekali untuk semua halaman,
# tanpa hint password di UI; production pakai Streamlit Cloud Secrets).
from auth import login_gate, render_logout
from notifications import build_kpi_alert, send_telegram, send_webhook


def _get_secret(section: str, key: str) -> str:
    """Ambil nilai Streamlit Secrets secara aman; return '' jika tidak ada."""
    try:
        if section in st.secrets:
            return str(st.secrets[section].get(key, "") or "")
    except Exception:
        pass
    return ""


login_gate(subtitle="Sales Analyzer", form_key="login_main")


# ============= FETCH FROM URL =============
def extract_gdrive_id(url: str) -> str | None:
    """Extract file ID dari Google Drive sharing URL."""
    patterns = [
        r"/file/d/([a-zA-Z0-9_-]+)",
        r"[?&]id=([a-zA-Z0-9_-]+)",
        r"/d/([a-zA-Z0-9_-]+)",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def fetch_from_url(url: str) -> bytes:
    """Download file dari URL. Saat ini support Google Drive sharing link
    (format: https://drive.google.com/file/d/FILE_ID/view?usp=sharing).
    Return file content as bytes. Raise on error.
    """
    if not url or not url.strip():
        raise ValueError("URL kosong")
    url = url.strip()
    parsed = urlparse(url)
    if "drive.google.com" in parsed.netloc or "docs.google.com" in parsed.netloc:
        file_id = extract_gdrive_id(url)
        if not file_id:
            raise ValueError(f"Tidak bisa extract file ID dari URL: {url}")
        session = requests.Session()
        dl_url = "https://drive.google.com/uc"
        resp = session.get(
            dl_url, params={"id": file_id, "export": "download"},
            stream=True, timeout=60,
        )
        ct = resp.headers.get("content-type", "")
        if "text/html" in ct:
            confirm = None
            for key, value in resp.cookies.items():
                if key.startswith("download_warning"):
                    confirm = value
                    break
            if confirm:
                resp = session.get(
                    dl_url, params={"id": file_id, "confirm": confirm},
                    stream=True, timeout=60,
                )
            else:
                raise ValueError(
                    "Google Drive mengembalikan HTML. Pastikan file di-share "
                    "'Anyone with the link' dan link benar."
                )
        buf = io.BytesIO()
        for chunk in resp.iter_content(32768):
            if chunk:
                buf.write(chunk)
        data = buf.getvalue()
        if data[:2] != b"PK":
            raise ValueError(
                f"File yang didownload bukan Excel valid (header: {data[:8]!r})."
            )
        return data
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def get_data_url() -> str:
    """Ambil URL data dari secrets (prioritas) atau kosong."""
    try:
        if "data" in st.secrets and "url" in st.secrets["data"]:
            return str(st.secrets["data"]["url"])
    except Exception:
        pass
    return ""


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


def process_file(uploaded, min_items, min_disc, loc_filter, date_preset, d_from, d_to,
                 disc_tol=1.0):
    """Load & classify file, simpan analyzer di session_state.
    `uploaded` bisa Streamlit UploadedFile, BytesIO, atau path string.
    """
    fname = getattr(uploaded, "name", None) or "data.xlsx"
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        if hasattr(uploaded, "getvalue"):
            f.write(uploaded.getvalue())
        elif isinstance(uploaded, (bytes, bytearray)):
            f.write(uploaded)
        else:
            f.write(Path(uploaded).read_bytes())
        tmp = f.name
    try:
        a = BundleAnalyzer()
        a.load(tmp)
        a.classify(min_items=min_items, min_discount=min_disc, disc_tolerance=disc_tol)
        # Apply location filter
        if loc_filter and loc_filter.strip():
            locs = [x.strip() for x in loc_filter.split(",") if x.strip()]
            a.df = a.df[a.df["FLOCCD"].astype(str).isin(locs)].copy()
        # Guard: jika data kosong setelah filter lokasi, tetap lanjut dengan df kosong
        if a.df.empty:
            st.session_state.analyzer = a
            st.session_state.data_loaded = True
            st.session_state.file_name = fname
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
        st.session_state.file_name = fname
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass


# MIME type Excel untuk download_button
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


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
            ["Total Revenue", "Sum dari JUMLAH per baris (sudah nett)"],
            ["Bundle Revenue", "Total Revenue dari transaksi yang terdeteksi sebagai bundle"],
            ["Bundle %", "Persentase bundle dari total transaksi"],
            ["LINE_REVENUE", "Pendapatan per baris (sama dengan JUMLAH, sudah nett)"],
            ["JUMLAH", "Total nett per baris (sudah × QTY + diskon)"],
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
        DISC_TOL_DEFAULT = 1.0
        if st.button("↺ Reset slider", key="reset_disc_tol", help="Kembalikan ke 1.0"):
            st.session_state["disc_tol_key"] = DISC_TOL_DEFAULT
            st.rerun()
        disc_tol = st.slider("Toleransi selisih DISCOUNT %", 0.1, 5.0, DISC_TOL_DEFAULT, 0.1,
                             key="disc_tol_key",
                             help="Beda diskon antar item dalam 1 NOTRAN ≤ nilai ini masih dianggap bundle")
        loc_filter = st.text_input("FLOCCD filter (pisah koma)", placeholder="mis. 55592, 55733")
        date_preset = st.selectbox("Periode", PRESET_PERIODS)
        d_from, d_to = None, None
        if date_preset == "Custom":
            d_from = st.date_input("Dari tanggal", value=None)
            d_to = st.date_input("Sampai tanggal", value=None)

    with st.expander("📡 Auto-fetch dari Google Drive", expanded=False):
        st.caption(
            "Setup 1x: upload file ke Google Drive → Share → 'Anyone with the link' "
            "→ paste link di bawah. App akan auto-fetch data terbaru."
        )
        default_url = get_data_url() or st.session_state.get("data_url", "")
        data_url = st.text_input(
            "Data URL (Google Drive share link)",
            value=default_url,
            placeholder="https://drive.google.com/file/d/.../view?usp=sharing",
            key="data_url_input",
        )
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🔄 Refresh dari URL", use_container_width=True, key="fetch_url"):
                if not data_url or not data_url.strip():
                    st.warning("⚠️ Isi URL terlebih dahulu.")
                else:
                    try:
                        with st.spinner("⏳ Download data dari Google Drive..."):
                            data_bytes = fetch_from_url(data_url)
                        st.session_state["data_url"] = data_url.strip()
                        with st.spinner("⏳ Memuat & menganalisa data..."):
                            process_file(
                                io.BytesIO(data_bytes), min_items, min_disc,
                                loc_filter, date_preset, d_from, d_to, disc_tol,
                            )
                        st.success(f"✓ Data ter-fetch! ({len(data_bytes):,} bytes)")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Gagal fetch: {e}")
        with col_b:
            if default_url and st.button("ℹ️ Lihat info", use_container_width=True, key="fetch_info"):
                st.info(f"URL default dari secrets: `{default_url[:60]}...`")

    if uploaded is not None:
        if st.button("🚀 Proses Data", type="primary", use_container_width=True):
            try:
                with st.spinner("⏳ Memuat & menganalisa data..."):
                    process_file(uploaded, min_items, min_disc, loc_filter, date_preset, d_from, d_to, disc_tol)
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
    render_logout(key="logout_main")

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
        "📋 Top & Satuan",
        "📦 Strategi Penjualan",
        "🧺 Basket",
        "⚡ KPI Harian",
        "🧑‍💼 Kasir",
        "🏷️ Efektivitas Promo",
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

        # --- Monthly by Location ---
        st.markdown('<div class="section-header">📅 Ringkasan per Lokasi per Bulan</div>', unsafe_allow_html=True)
        msl = a.monthly_summary_by_location()
        if not msl.empty:
            st.dataframe(msl, use_container_width=True, hide_index=True)
            # Pivot chart: stacked bar QTY paket vs satuan per bulan
            pivot = msl.groupby(["TAHUN", "BULAN"])[["TOTAL QTY PAKET", "TOTAL QTY SATUAN"]].sum().reset_index()
            pivot["Bulan"] = pivot["TAHUN"].astype(str) + "-" + pivot["BULAN"].astype(str).str.zfill(2)
            fig_msl = px.bar(pivot, x="Bulan", y=["TOTAL QTY PAKET", "TOTAL QTY SATUAN"],
                             title="QTY Paket vs Satuan per Bulan", barmode="group")
            st.plotly_chart(fig_msl, use_container_width=True)

        # --- Monthly bundle detail ---
        with st.expander("📦 Detail Bundle per Lokasi per Bulan", expanded=False):
            mbd = a.monthly_bundle_detail()
            if not mbd.empty:
                lok_list = sorted(mbd["KODE LOKASI"].unique())
                lok_filt = st.selectbox("Filter Kode Lokasi", ["Semua"] + lok_list)
                if lok_filt != "Semua":
                    mbd = mbd[mbd["KODE LOKASI"] == lok_filt]
                st.dataframe(mbd, use_container_width=True, hide_index=True)
                top_combo = mbd.groupby("ITEM_BUNDLE")["QTY_TERJUAL"].sum().sort_values(ascending=False).head(15).reset_index()
                fig_mbd = px.bar(top_combo, x="QTY_TERJUAL", y="ITEM_BUNDLE", orientation="h",
                                 title="Top 15 Kombinasi Bundle")
                st.plotly_chart(fig_mbd, use_container_width=True)

        # Download (multi-sheet)
        try:
            sheets = {"Summary_Lokasi": sm, "Ringkasan_Bulan_Lokasi": msl}
            if not mbd.empty:
                sheets["Detail_Bundle"] = mbd
            excel_bytes = to_excel_bytes(sheets)
            st.download_button(
                "📥 Download Summary (Excel)",
                data=excel_bytes,
                file_name="summary_lokasi.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.caption(f"⚠️ Excel download tidak tersedia: {e}")

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
        "Gunakan Master Cost atau Asumsi biaya di bawah untuk hasil yang akurat."
    )
    
    st.markdown("#### Master Cost (Opsional)")
    cost_file = st.file_uploader(
        "Upload file Excel Master Cost (wajib ada kolom PLU dan COST). Jika diisi, 'Asumsi Biaya' di bawah akan diabaikan (kecuali untuk barang yang tidak ada di master).",
        type=["xlsx", "xls"],
        key="cost_uploader",
    )
    if cost_file is not None:
        try:
            df_c = pd.read_excel(cost_file)
            a.load_master_cost(df_c)
            st.success(f"✅ Master Cost dimuat ({len(df_c):,} baris).")
        except Exception as e:
            st.error(f"Gagal memuat Master Cost: {e}")

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
        "🏆 Top Item Satuan",
        "🏆 Top Keseluruhan",
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

    # ---------- Sub-tab 4: Top Keseluruhan ----------
    with sub[3]:
        st.caption("Item Paling Laris Gabungan (Bundle + Satuan).")
        n_top_all = st.slider("Top N Keseluruhan", 5, 50, 20, key="top_all_n")
        top_all = a.top_all_items(top_n=n_top_all)
        if top_all.empty:
            st.warning("Tidak ada data.")
        else:
            fig_all = px.bar(
                top_all,
                x="TOTAL_QTY",
                y="NAMA_BRG",
                orientation="h",
                color="TOTAL_REVENUE_GROSS",
                color_continuous_scale="Plasma",
                title=f"Top {n_top_all} Item Keseluruhan",
                labels={"TOTAL_QTY": "Total QTY", "NAMA_BRG": ""},
            )
            fig_all.update_layout(yaxis={"categoryorder": "total ascending"}, height=500)
            st.plotly_chart(fig_all, use_container_width=True)
            st.dataframe(top_all, use_container_width=True, hide_index=True, height=400)
            st.download_button(
                "📥 Download Top Keseluruhan (Excel)",
                data=to_excel_bytes({"Top_Keseluruhan": top_all}),
                file_name="top_keseluruhan.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_top_all",
            )

    # ---------- Sub-tab 5: Distribusi Diskon Item ----------
    with sub[4]:
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

    # ---------- Sub-tab 6: Cari Item Satuan ----------
    with sub[5]:
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

# ---------------- TAB 11: STRATEGI PENJUALAN ----------------
with tabs[10]:
    st.markdown(
        '<div class="section-header">📦 Strategi Penjualan</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Identifikasi **slow moving**, **dead stock**, dan dapatkan **rekomendasi promosi** "
        "berbasis data untuk bulan depan."
    )
    
    st.markdown("#### Data Stok (Opsional)")
    stock_file = st.file_uploader(
        "Upload file Excel Stok (wajib ada kolom FLOCCD, PLU, dan SISA_STOK). Jika diisi, kolom STOCK_COVER_DAYS akan muncul di analisa di bawah.",
        type=["xlsx", "xls"],
        key="stock_uploader",
    )
    if stock_file is not None:
        try:
            df_s = pd.read_excel(stock_file)
            a.load_stock_data(df_s)
            st.success(f"✅ Data Stok dimuat ({len(df_s):,} baris).")
        except Exception as e:
            st.error(f"Gagal memuat Data Stok: {e}")

    strat_tabs = st.tabs([
        "🐌 Slow Moving",
        "💀 Dead Stock",
        "🎯 Rekomendasi Promosi",
    ])

    # ---------- Sub-tab 1: Slow Moving ----------
    with strat_tabs[0]:
        st.caption(
            "Item dengan penjualan rendah/menurun. "
            "Tersedia 3 view: bottom percentile, threshold tetap, dan penurunan drastis."
        )
        sm_col1, sm_col2, sm_col3 = st.columns(3)
        with sm_col1:
            sm_bottom = st.number_input(
                "Bottom percentile (%)", 5, 50, 20, 5, key="sm_pct"
            )
        with sm_col2:
            sm_threshold = st.number_input(
                "Fixed threshold (qty/hari)", 0.01, 5.0, 0.5, 0.1,
                key="sm_thr", format="%.2f"
            )
        with sm_col3:
            sm_decline = st.number_input(
                "Decline threshold (%)", 10, 90, 50, 10, key="sm_dec"
            )
        sm_top = st.slider("Tampilkan top N", 5, 200, 30, 5, key="sm_top")

        with st.spinner("⏳ Menghitung slow moving items..."):
            try:
                sm_data = a.slow_moving_items(
                    view="all",
                    bottom_pct=sm_bottom,
                    fixed_threshold=sm_threshold,
                    decline_pct=sm_decline,
                    top_n=sm_top,
                )
            except Exception as e:
                st.error(f"❌ Error di slow_moving_items: {type(e).__name__}: {e}")
                import traceback
                with st.expander("🔍 Detail traceback"):
                    st.code(traceback.format_exc())
                st.stop()
        sm_view = st.radio(
            "Pilih view:",
            ["bottom_pct", "fixed_threshold", "decline"],
            format_func=lambda x: {
                "bottom_pct": f"📊 Bottom {sm_bottom}% (AVG qty/hari paling rendah)",
                "fixed_threshold": f"🎯 Fixed threshold <{sm_threshold} qty/hari",
                "decline": f"📉 Penurunan >{sm_decline}% vs paruh pertama",
            }[x],
            horizontal=True,
            key="sm_view",
        )
        sm_df = sm_data.get(sm_view, pd.DataFrame())
        st.markdown(f"**{len(sm_df)} item** terdeteksi slow moving ({sm_view}).")
        if not sm_df.empty:
            st.dataframe(sm_df, use_container_width=True, hide_index=True, height=400)
            # Visualisasi: distribusi qty/hari (jika ada kolom itu)
            if "AVG_DAILY_QTY" in sm_df.columns:
                fig = px.histogram(
                    sm_df, x="AVG_DAILY_QTY", nbins=20,
                    title="Distribusi AVG QTY/hari (item slow moving)",
                    labels={"AVG_DAILY_QTY": "AVG QTY/hari"},
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
            st.download_button(
                "📥 Download Slow Moving (Excel)",
                data=to_excel_bytes({
                    "Bottom_Percentile": sm_data.get("bottom_pct", pd.DataFrame()),
                    "Fixed_Threshold": sm_data.get("fixed_threshold", pd.DataFrame()),
                    "Decline": sm_data.get("decline", pd.DataFrame()),
                }),
                file_name="slow_moving_items.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_slow",
            )

    # ---------- Sub-tab 2: Dead Stock ----------
    with strat_tabs[1]:
        st.caption(
            "Item yang **tidak ada transaksi dalam N hari terakhir**, "
            "tapi pernah laku sebelumnya. Kandidat kuat untuk clearance / discontinue."
        )
        ds_days = st.slider(
            "Threshold 'tidak ada transaksi' (hari)",
            7, 180, 60, 7, key="ds_days",
            help="Default 60 hari. Bisa diatur sesuai karakter bisnis Anda."
        )
        ds_top = st.slider("Tampilkan top N", 10, 500, 100, 10, key="ds_top")
        with st.spinner(f"⏳ Mencari item yang tidak laku {ds_days} hari..."):
            try:
                ds_df = a.dead_stock_items(days=ds_days, top_n=ds_top)
            except Exception as e:
                st.error(f"❌ Error di dead_stock_items: {type(e).__name__}: {e}")
                import traceback
                with st.expander("🔍 Detail traceback"):
                    st.code(traceback.format_exc())
                st.stop()
        st.markdown(f"**{len(ds_df)} item** terdeteksi dead stock (> {ds_days} hari tidak laku).")
        if not ds_df.empty:
            # Metric cards
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Total item", f"{len(ds_df):,}")
            with c2:
                st.metric("Total QTY (lifetime)", f"{int(ds_df['LIFETIME_QTY'].sum()):,}")
            with c3:
                st.metric("Total Revenue (lifetime)", _format_rp(ds_df['LIFETIME_REVENUE'].sum()))
            with c4:
                urgent = (ds_df['DAYS_SINCE_SALE'] > 90).sum()
                st.metric("🔴 Kritis (>90h)", f"{urgent:,}")
            st.dataframe(ds_df, use_container_width=True, hide_index=True, height=400)
            # Distribusi days_since_sale
            fig = px.histogram(
                ds_df, x="DAYS_SINCE_SALE", nbins=20,
                title=f"Distribusi hari sejak transaksi terakhir (threshold = {ds_days} hari)",
                labels={"DAYS_SINCE_SALE": "Hari sejak transaksi terakhir"},
            )
            fig.add_vline(x=ds_days, line_dash="dash", line_color="red", annotation_text=f"Threshold {ds_days}h")
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
            st.download_button(
                "📥 Download Dead Stock (Excel)",
                data=to_excel_bytes({"Dead_Stock": ds_df}),
                file_name=f"dead_stock_{ds_days}h.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_dead",
            )
        else:
            st.info(f"🎉 Tidak ada dead stock (> {ds_days} hari tidak laku). Semua item masih aktif!")

    # ---------- Sub-tab 3: Rekomendasi Promosi ----------
    with strat_tabs[2]:
        st.caption(
            "4 strategi promosi berbasis data. Setiap item direkomendasikan dengan "
            "**alasan** dan **saran aksi** konkret."
        )
        pr_col1, pr_col2, pr_col3 = st.columns(3)
        with pr_col1:
            pr_margin = st.number_input(
                "Min margin % (clearance)", 10.0, 90.0, 30.0, 5.0, key="pr_mar"
            )
        with pr_col2:
            pr_qty = st.number_input(
                "Max qty/hari (clearance)", 0.1, 5.0, 1.0, 0.1, key="pr_qty", format="%.1f"
            )
        with pr_col3:
            pr_momentum = st.number_input(
                "Min kenaikan % (momentum)", 10, 500, 50, 10, key="pr_mom"
            )
        pr_top = st.slider("Tampilkan top N per strategi", 5, 100, 20, 5, key="pr_top")
        pr_cost_pct = st.number_input(
            "Asumsi biaya (% dari harga jual, untuk hitung margin)",
            10, 80, 30, 5, key="pr_cost",
            help="Default 30%. Sesuaikan dengan bisnis Anda."
        )
        with st.spinner("⏳ Menganalisa 4 strategi promosi..."):
            try:
                pr_data = a.promo_recommendations(
                    cost_pct_assumption=pr_cost_pct,
                    clearance_min_margin_pct=pr_margin,
                    clearance_max_avg_daily_qty=pr_qty,
                    momentum_increase_pct=pr_momentum,
                    top_n_per_strategy=pr_top,
                )
            except Exception as e:
                st.error(f"❌ Error di promo_recommendations: {type(e).__name__}: {e}")
                import traceback
                with st.expander("🔍 Detail traceback"):
                    st.code(traceback.format_exc())
                st.stop()
        promo_tabs = st.tabs([
            "🧹 Clearance (slow + high margin)",
            "🚀 Momentum (trending up)",
            "🛒 Cross-sell (market basket)",
            "📅 Musiman (seasonal)",
        ])
        strat_titles = {
            "clearance": "Clearance: slow-moving + margin tinggi → Diskon / Bundle",
            "momentum": "Momentum: QTY naik signifikan → Pertahankan + tambah stok",
            "basket": "Cross-sell: item komplementer best-seller → Bundle combo",
            "seasonal": "Musiman: pola peak/off months → Stok + promo terjadwal",
        }
        for i, strat in enumerate(["clearance", "momentum", "basket", "seasonal"]):
            with promo_tabs[i]:
                df = pr_data.get(strat, pd.DataFrame())
                st.markdown(f"**{strat_titles[strat]}**")
                st.markdown(f"**{len(df)} item** masuk strategi ini.")
                if df.empty:
                    st.info("Tidak ada item yang memenuhi kriteria strategi ini.")
                else:
                    st.dataframe(df, use_container_width=True, hide_index=True, height=400)
        st.markdown("---")
        # Download semua strategi dalam 1 file Excel
        sheets_to_dl = {f"{s}_{strat_titles[s].split(':')[0]}": pr_data.get(s, pd.DataFrame())
                        for s in ["clearance", "momentum", "basket", "seasonal"]}
        st.download_button(
            "📥 Download Semua Rekomendasi (1 Excel, 4 sheet)",
            data=to_excel_bytes(sheets_to_dl),
            file_name="rekomendasi_promosi.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_promo",
        )

# ---------------- TAB 12: BASKET ANALYSIS ----------------
with tabs[11]:
    st.markdown('<div class="section-header">🧺 Analisis Basket Transaksi</div>', unsafe_allow_html=True)
    st.caption("Distribusi nilai transaksi berdasarkan total nett per NOTRAN.")
    _df_b = a.df if a is not None and hasattr(a, "df") and a.df is not None and not a.df.empty and "FDATE" in a.df.columns else None
    if _df_b is None:
        st.warning("Data kosong setelah filter. Penyebab paling umum: **filter FLOCCD** di sidebar kiri terlalu ketat (kosongkan jika ragu). Upload ulang & klik **🚀 Proses Data**.")
    else:
        locs = sorted(_df_b["FLOCCD"].unique().tolist())
        bulan_list = sorted(_df_b["FDATE"].dt.month.unique().tolist())
        col1, col2, col3, col4 = st.columns([2, 1, 2, 1])
        with col1:
            bl = st.selectbox("Filter Lokasi", ["Semua"] + locs, key="bsk_loc")
            floocd_val = None if bl == "Semua" else bl
        with col2:
            bulan_terpilih = st.multiselect("Filter Bulan", bulan_list, default=bulan_list, key="bsk_bln")
            bulan_val = bulan_terpilih if bulan_terpilih and len(bulan_terpilih) < len(bulan_list) else None
        with col3:
            lokasi_pilihan = st.multiselect("Pilih Lokasi pembanding", locs, key="bsk_loks")
        with col4:
            st.markdown("<br>", unsafe_allow_html=True)
            run_bsk = st.button("🔄 Proses Basket", type="primary", use_container_width=True)
        if run_bsk:
            try:
                basket_df = a.basket_analysis(floocd=floocd_val, bulan=bulan_val)
                if basket_df.empty:
                    st.warning("Tidak ada data.")
                else:
                    basket_df["TOTAL NETT"] = basket_df["TOTAL NETT"].round(0).astype(int)
                    basket_df["RATA-RATA BASKET"] = basket_df["RATA-RATA BASKET"].round(0).astype(int)
                    st.subheader("📊 Distribusi Basket")
                    cola, colb = st.columns([3, 2])
                    with cola:
                        fig1 = px.bar(basket_df, x="BASKET", y="JUMLAH TRANSAKSI",
                                      title="Jumlah Transaksi per Basket", text_auto=True,
                                      color="% TRANSAKSI", color_continuous_scale="Blues")
                        fig1.update_layout(xaxis_title="Range Basket", yaxis_title="Transaksi")
                        st.plotly_chart(fig1, use_container_width=True)
                    with colb:
                        fig2 = px.pie(basket_df, values="% REVENUE", names="BASKET",
                                      title="Kontribusi Revenue per Basket")
                        fig2.update_traces(textposition="inside", textinfo="label+percent")
                        st.plotly_chart(fig2, use_container_width=True)
                    st.subheader("📋 Tabel Basket")
                    fmt = {"TOTAL NETT": "Rp{:,.0f}", "RATA-RATA BASKET": "Rp{:,.0f}"}
                    st.dataframe(basket_df.style.format(fmt), use_container_width=True, hide_index=True, height=350)
                    if lokasi_pilihan:
                        st.subheader("🏪 Perbandingan per Lokasi")
                        by_loc = a.basket_by_location(lokasi_pilihan, bulan=bulan_val)
                        if not by_loc.empty:
                            st.dataframe(by_loc, use_container_width=True, hide_index=True, height=300)
                            fig3 = px.bar(by_loc.melt(id_vars="BASKET", var_name="LOKASI", value_name="TRANSAKSI"),
                                          x="BASKET", y="TRANSAKSI", color="LOKASI", barmode="group",
                                          title="Perbandingan Basket per Lokasi")
                            st.plotly_chart(fig3, use_container_width=True)
                    csv = basket_df.to_csv(index=False).encode()
                    st.download_button("⬇️ Download CSV", csv, "basket_analysis.csv", "text/csv")
            except Exception as e:
                st.error(f"Error: {e}")

# Footer
st.markdown("---")
st.caption(
    f"💎 Sales Analyzer · Web Edition · "
    f"Streamlit + Plotly · Data: `{st.session_state.file_name}`"
)


# ---------------- TAB 13: KPI HARIAN ----------------
with tabs[12]:
    st.markdown('<div class="section-header">⚡ Dashboard KPI Harian</div>', unsafe_allow_html=True)
    st.caption(
        "Snapshot hari terakhir data vs kemarin vs rata-rata 7 & 30 hari terakhir. "
        "Termasuk item terlaris hari terakhir + alert dead stock / stok menipis."
    )

    # loc_filter sudah diterapkan saat load (process_file), df sudah ter-filter
    kpi = a.kpi_dashboard()
    if not kpi:
        st.info("Tidak ada data untuk filter ini.")
    else:
        st.markdown(f"**📅 Hari terakhir data:** `{kpi['latest_date'].date()}`")
        st.markdown("")

        # --- Metrik utama ---
        today, yest, a7, a30, growth = (
            kpi["today"], kpi["yesterday"], kpi["avg_7d"], kpi["avg_30d"], kpi["growth"],
        )

        def _delta(g):
            if g is None:
                return None
            return f"{g:+.1f}%"

        c1, c2, c3 = st.columns(3)
        c1.metric(
            "💰 Revenue Hari Terakhir", _format_rp(today["revenue"]),
            delta=_delta(growth["revenue_vs_kemarin"]) or "vs kemarin",
        )
        c2.metric("🧾 Transaksi", f"{today['tx']:,}", delta=_delta(growth["tx_vs_kemarin"]) or "vs kemarin")
        c3.metric("📦 Total QTY", f"{today['qty']:,}")

        st.markdown("")
        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("Revenue vs rata-rata 7 hari", _format_rp(today["revenue"]),
                   delta=_delta(growth["revenue_vs_avg7d"]) or "vs avg 7d")
        cc2.metric("Revenue vs rata-rata 30 hari", _format_rp(today["revenue"]),
                   delta=_delta(growth["revenue_vs_avg30d"]) or "vs avg 30d")
        cc3.metric("Diskon rata-rata (item satuan)", f"{today['avg_disc_single']:.1f}%")

        st.markdown("")
        st.caption(
            f"Rata-rata harian 7 hari: {_format_rp(a7['revenue_per_hari'])}/hari "
            f"({a7['tx_per_hari']:.0f} tx/hari, {a7['n_hari']} hari aktif) · "
            f"Rata-rata 30 hari: {_format_rp(a30['revenue_per_hari'])}/hari"
        )
        st.markdown("---")

        # --- Top items hari terakhir ---
        st.markdown("#### 🏆 Top Item Hari Terakhir (by QTY)")
        top_today = kpi["top_items_today"]
        if not top_today.empty:
            st.dataframe(
                top_today, use_container_width=True, hide_index=True,
                column_config={
                    "TOTAL_QTY": st.column_config.NumberColumn("QTY", format="%d"),
                    "TOTAL_REVENUE": st.column_config.NumberColumn("Revenue (Rp)", format="%,.0f"),
                },
            )
        else:
            st.info("Tidak ada transaksi di hari terakhir filter ini.")
        st.markdown("---")

        # --- Alerts ---
        alerts = kpi["alerts"]
        st.markdown("#### 🚨 Alert Stok")
        col_l, col_r = st.columns(2)

        with col_l:
            ds_count = alerts.get("dead_stock_count", 0)
            if ds_count > 0:
                st.error(f"💀 **Dead stock**: {ds_count} item tidak terjual 60 hari terakhir")
                ds_val = alerts.get("dead_stock_value", 0)
                if ds_val:
                    st.caption(f"Potensi revenue idle: {_format_rp(ds_val)}")
                ds_top = alerts.get("dead_stock_top")
                if ds_top is not None and not ds_top.empty:
                    st.dataframe(ds_top, use_container_width=True, hide_index=True, height=220)
            else:
                st.success("✅ Tidak ada dead stock (60 hari).")

        with col_r:
            low = alerts.get("low_stock_count")
            if low is None:
                st.info("ℹ️ Upload **Data Stok** di tab Strategi Penjualan untuk deteksi stok menipis.")
            elif low > 0:
                st.warning(f"⚠️ **Stok menipis**: {low} item ≤ 2 unit")
                ls_top = alerts.get("low_stock_top")
                if ls_top is not None and not ls_top.empty:
                    st.dataframe(ls_top, use_container_width=True, hide_index=True, height=220)
            else:
                st.success("✅ Tidak ada stok kritis (≤2 unit).")

        # --- Kirim Notifikasi ---
        st.markdown("---")
        st.markdown("#### 📤 Kirim Ringkasan sebagai Notifikasi")
        with st.expander("⚙️ Kirim ke Telegram / Webhook"):
            st.caption(
                "Isi konfigurasi di bawah, atau set di **Streamlit Cloud > Secrets** agar tersimpan permanen:\n"
                "`[telegram]` → `bot_token` + `chat_id`, atau `[webhook]` → `url`"
            )
            notif_tab = st.tabs(["📨 Telegram", "🪝 Webhook"])
            msg_preview = None
            with notif_tab[0]:
                tg_token = st.text_input("Bot token", type="password", key="nt_token",
                                          value=_get_secret("telegram", "bot_token"))
                tg_chat = st.text_input("Chat ID", key="nt_chat",
                                         value=_get_secret("telegram", "chat_id"))
                if st.button("📨 Kirim ke Telegram", key="btn_nt_tg"):
                    if not tg_token or not tg_chat:
                        st.warning("Bot token dan chat ID wajib diisi.")
                    else:
                        msg = build_kpi_alert(
                            kpi, app_url="https://sales-analyzer-itx.streamlit.app")
                        try:
                            res = send_telegram(tg_token, tg_chat, msg)
                            if res.get("ok"):
                                st.success("✅ Notifikasi terkirim ke Telegram!")
                            else:
                                st.error(f"❌ Gagal: {res.get('description', 'unknown')}")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
            with notif_tab[1]:
                wh_url = st.text_input("Webhook URL", key="nt_wh",
                                        value=_get_secret("webhook", "url"))
                if st.button("🪝 Kirim ke Webhook", key="btn_nt_wh"):
                    if not wh_url:
                        st.warning("URL webhook wajib diisi.")
                    else:
                        msg = build_kpi_alert(kpi)
                        try:
                            res = send_webhook(wh_url, msg)
                            if res.get("ok"):
                                st.success("✅ Notifikasi terkirim ke webhook!")
                            else:
                                st.error(f"❌ Gagal: {res.get('description', '')}")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
            with st.expander("👀 Preview pesan"):
                st.code(build_kpi_alert(kpi), language="text")


# ---------------- TAB 14: KASIR ----------------
with tabs[13]:
    st.markdown('<div class="section-header">🧑‍💼 Performa Kasir & Deteksi Anomali</div>', unsafe_allow_html=True)
    st.caption(
        "Ranking penjualan per kasir + deteksi **anomali pola diskon** per kasir "
        "(fraud detection). Diskon dibandingkan terhadap pola seluruh lokasi; "
        "kasir yang selalu memberi diskon di luar pola ditandai ANOMALI."
    )

    kasir_tab = st.tabs(["📊 Performa Kasir", "🚨 Anomali Diskon"])

    with kasir_tab[0]:
        kp = a.kasir_performance()
        if kp.empty:
            st.info("Tidak ada data.")
        else:
            col_n, col_rev, col_tx = st.columns(3)
            col_n.metric("Kasir aktif", f"{kp['KASIR'].nunique():,}")
            col_rev.metric("Total Revenue", _format_rp(kp['TOTAL_REVENUE'].sum()))
            col_tx.metric("Total Transaksi", f"{int(kp['JUMLAH_TX'].sum()):,}")

            top_kasir = kp.sort_values("TOTAL_REVENUE", ascending=False)
            st.markdown("#### 🏆 Top Kasir by Revenue")
            st.dataframe(
                top_kasir.head(50), use_container_width=True, hide_index=True,
                column_config={
                    "JUMLAH_TX": st.column_config.NumberColumn("Tx", format="%d"),
                    "TOTAL_QTY": st.column_config.NumberColumn("QTY", format="%d"),
                    "TOTAL_REVENUE": st.column_config.NumberColumn("Revenue (Rp)", format="%,.0f"),
                    "AVG_DISC_PCT": st.column_config.NumberColumn("Avg Disc %", format="%.2f"),
                    "BUNDLE_TX": st.column_config.NumberColumn("Bundle Tx", format="%d"),
                    "AVG_REVENUE_PER_TX": st.column_config.NumberColumn("Rev/Tx (Rp)", format="%,.0f"),
                },
            )
            if not top_kasir.empty:
                fig_k = px.bar(
                    top_kasir.head(15), x="TOTAL_REVENUE", y="KASIR",
                    orientation="h", color="TOTAL_REVENUE",
                    color_continuous_scale="Blues",
                    title="Top 15 Kasir by Revenue",
                )
                fig_k.update_layout(height=480, coloraxis_showscale=False, yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_k, use_container_width=True)
            with st.expander("📥 Download full performa kasir"):
                st.download_button(
                    "💾 Download Excel — Performa Kasir",
                    to_excel_bytes({"Performa_Kasir": kp}),
                    file_name="performa_kasir.xlsx",
                    mime=XLSX_MIME,
                )

    with kasir_tab[1]:
        st.markdown("#### 🚨 Deteksi Anomali Diskon per Kasir")
        st.caption(
            "Menganalisa item **satuan** (non-bundle) saja, karena bundle selalu punya "
            "diskon seragam (by design). Nilai Z-score tinggi = diskon kasir jauh "
            "di luar pola normal lokasi tersebut."
        )
        z_th = st.slider("Threshold Z-score (anomali)", 1.5, 5.0, 2.5, 0.1, key="kt_z")
        min_tx = st.slider("Min transaksi kasir", 5, 100, 20, 5, key="kt_mintx")
        if st.button("🔍 Analisa Anomali", type="primary", key="btn_anomali"):
            with st.spinner("⏳ Menghitung pola diskon per kasir..."):
                st.session_state["anom_df"] = a.kasir_discount_anomaly(
                    z_thresh=z_th, min_tx=min_tx,
                )
            st.rerun()

        if "anom_df" in st.session_state:
            an = st.session_state["anom_df"]
            if an.empty:
                st.info("Tidak ada data item satuan untuk analisa.")
            else:
                n_anom = int((an["STATUS"] == "ANOMALI").sum())
                st.metric("Kasir terdeteksi ANOMALI", n_anom,
                          "🟢 Aman" if n_anom == 0 else "🔴 Perlu review")
                if n_anom:
                    st.error(
                        f"⚠️ {n_anom} kasir punya pola diskon tidak wajar. "
                        "Review kolom `MEDIAN_DISC_KASIR` vs `MEDIAN_DISC_LOKASI`."
                    )
                st.dataframe(
                    an, use_container_width=True, hide_index=True,
                    column_config={
                        "Z_SCORE": st.column_config.NumberColumn("Z-Score", format="%.2f"),
                        "MEDIAN_DISC_KASIR": st.column_config.NumberColumn("Disc Kasir %", format="%.2f"),
                        "MEDIAN_DISC_LOKASI": st.column_config.NumberColumn("Disc Lokasi %", format="%.2f"),
                    },
                )
                with st.expander("📥 Download hasil anomali"):
                    st.download_button(
                        "💾 Download Excel — Anomali Kasir",
                        to_excel_bytes({"Anomali_Kasir": an}),
                        file_name="anomali_kasir.xlsx",
                        mime=XLSX_MIME,
                    )
        else:
            st.info("Klik **🔍 Analisa Anomali** untuk mulai.")



# ---------------- TAB 15: EFEKTIVITAS PROMO ----------------
with tabs[14]:
    st.markdown('<div class="section-header">🏷️ Efektivitas Promo (Price Elasticity)</div>', unsafe_allow_html=True)
    st.caption(
        "Membandingkan penjualan item saat **diskon tinggi** vs **diskon rendah/normal**. "
        "Membantu memutuskan item mana yang promo-nya benar-benar mendorong volume, "
        "dan mana yang hanya menggerus margin tanpa menaikkan penjualan."
    )

    st.markdown(
        "Item satuan diklasifikasikan ke 2 kelompok berdasarkan besarnya diskon: "
        "**Promo** (diskon ≥ threshold) dan **Normal** (di bawahnya). "
        "Kemudian dibandingkan volume & revenue per hari di tiap kelompok."
    )

    disc_th = st.slider("Batas 'promo' (% diskon)", 5.0, 80.0, 20.0, 1.0, key="pe_disc")

    pe = a.promo_effectiveness(disc_threshold=disc_th)
    if pe is None or getattr(pe, "empty", True):
        st.info("Tidak ada data item satuan untuk analisa promo.")
    else:
        st.markdown("#### Ringkasan per Item (Promo vs Normal)")
        st.dataframe(
            pe, use_container_width=True, hide_index=True, height=450,
            column_config={
                "PROMO_QTY": st.column_config.NumberColumn("Promo QTY", format="%d"),
                "NORMAL_QTY": st.column_config.NumberColumn("Normal QTY", format="%d"),
                "PROMO_REVENUE": st.column_config.NumberColumn("Promo Rev (Rp)", format="%,.0f"),
                "NORMAL_REVENUE": st.column_config.NumberColumn("Normal Rev (Rp)", format="%,.0f"),
                "QTY_LIFT_PCT": st.column_config.NumberColumn("Lift QTY %", format="%+.1f"),
            },
        )
        with st.expander("📥 Download"):
            st.download_button(
                "💾 Download Excel — Efektivitas Promo",
                to_excel_bytes({"Efektivitas_Promo": pe}),
                file_name="efektivitas_promo.xlsx",
                mime=XLSX_MIME,
            )

        st.markdown("#### 📈 Scatter: Diskon vs Volume (semua item)")
        fig_pe = px.scatter(
            pe, x="AVG_DISC_PCT", y="TOTAL_QTY",
            size="TOTAL_QTY", color="AVG_DISC_PCT",
            color_continuous_scale="RdYlGn",
            hover_data=["PLU", "NAMA_BRG", "TOTAL_REVENUE"],
            title="Diskon (%) vs Total QTY Terjual",
            labels={"AVG_DISC_PCT": "Rata-rata Diskon (%)", "TOTAL_QTY": "Total QTY"},
        )
        fig_pe.update_layout(height=480)
        st.plotly_chart(fig_pe, use_container_width=True)
