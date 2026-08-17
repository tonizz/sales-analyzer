"""
Stock Card — Streamlit Multi-Page
==================================
Halaman untuk kartu stok per PLU per lokasi per bulan.
Input: Stok Awal + DBU (mutasi) + DBKS (penjualan).

CARA PAKAI:
  1. streamlit run bundle_analyzer_web.py
  2. Login
  3. Klik "Stock Card" di sidebar
  4. Upload 3 file
  5. Klik "🚀 Proses Kartu Stok"
  6. Explore 9 tab
"""
from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from stock_card import StockCard

# Auth terpusat (auth.py)
from auth import login_gate

# ============================================================================
# PAGE CONFIG + AUTH
# ============================================================================
st.set_page_config(page_title="Stock Card", layout="wide")
login_gate(subtitle="Stock Card", form_key="login_sc")

# ============================================================================
# JUDUL
# ============================================================================
st.title("📦 Kartu Stok Bulanan")
st.markdown("Analisa stok per PLU per lokasi per bulan dari **Stok Awal + DBU + DBKS**")

# ============================================================================
# SIDEBAR — Upload
# ============================================================================
st.sidebar.header("📂 Upload Data")
sa_file = st.sidebar.file_uploader("1. Stok Awal (.xlsx)", type=["xlsx"])
dbu_file = st.sidebar.file_uploader("2. DBU Mutasi (.xlsx)", type=["xlsx"])
dbks_file = st.sidebar.file_uploader("3. DBKS Penjualan (.xlsx)", type=["xlsx"])

sc: StockCard | None = None

if st.sidebar.button("🚀 Proses Kartu Stok"):
    missing = []
    if not sa_file: missing.append("Stok Awal")
    if not dbu_file: missing.append("DBU")
    if not dbks_file: missing.append("DBKS")
    if missing:
        st.error(f"Upload dulu: {', '.join(missing)}")
    else:
        with st.spinner("Memproses kartu stok..."):
            try:
                # Save to temp
                tmp = tempfile.mkdtemp()
                p_sa = Path(tmp) / "sa.xlsx"
                p_dbu = Path(tmp) / "dbu.xlsx"
                p_dbks = Path(tmp) / "dbks.xlsx"
                p_sa.write_bytes(sa_file.getbuffer())
                p_dbu.write_bytes(dbu_file.getbuffer())
                p_dbks.write_bytes(dbks_file.getbuffer())

                sc = StockCard()
                sc.load_data(str(p_sa), str(p_dbu), str(p_dbks))
                st.session_state["sc"] = sc
                st.success(f"✅ Selesai! {sc._master['PLU'].nunique()} PLU, {sc._master['LOKASI'].nunique()} lokasi, {len(sc._master)} baris")
            except Exception as e:
                st.error(f"Error: {e}")

if "sc" in st.session_state:
    sc = st.session_state["sc"]

if sc is None or sc._master is None:
    st.info("📤 Upload 3 file di sidebar lalu klik **🚀 Proses Kartu Stok**")
    st.stop()

# ============================================================================
# TAB
# ============================================================================
master = sc._master
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
    "📋 Kartu Stok", "📄 Format Stok", "🔢 Ringkasan PLU", "🏪 Ringkasan Lokasi",
    "📈 Trend", "⚠️ Stok Negatif", "🟡 Stok Menipis",
    "💀 Dead Stock", "🔍 Filter", "📥 Export"
])

# --- TAB 1: Kartu Stok ---
with tab1:
    st.subheader("Kartu Stok Detail")
    df = sc.get_stock_card()
    status_filter = st.multiselect("Filter Status", df["STATUS"].unique(), default=df["STATUS"].unique())
    filtered = df[df["STATUS"].isin(status_filter)]
    st.dataframe(filtered, use_container_width=True, hide_index=True)
    st.caption(f"{len(filtered)} baris dari {len(df)} total")

# --- TAB 2: Format Stok ---
with tab2:
    st.subheader("Format Stok per Bulan")
    bulan_list = sorted(master["BULAN"].unique())
    selected_month = st.selectbox("Pilih Bulan", bulan_list,
                                  format_func=lambda x: {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"Mei",6:"Jun",
                                                          7:"Jul",8:"Agu",9:"Sep",10:"Okt",11:"Nov",12:"Des"}.get(x,str(x)),
                                  index=len(bulan_list)-1)
    df_fs = sc.format_stok(int(selected_month))
    if len(df_fs) == 0:
        st.warning("Tidak ada data untuk bulan ini")
    else:
        st.dataframe(df_fs, use_container_width=True, hide_index=True)
        st.caption(f"{len(df_fs)} baris • {df_fs['LOKASI'].nunique()} lokasi • {df_fs['PLU'].nunique()} PLU")
        csv = df_fs.to_csv(index=False).encode()
        st.download_button("⬇️ Download CSV", csv, f"stok_{selected_month}.csv", "text/csv")

# --- TAB 3: Ringkasan PLU ---
with tab3:
    st.subheader("Ringkasan per PLU")
    df_plu = sc.summarize_by_plu()
    col_sel = st.multiselect("Pilih kolom", df_plu.columns.tolist(),
                             default=["PLU", "NAMA_BRG", "STOK_AKHIR_TERAKHIR", "TOTAL_TERJUAL", "RATA2_TERJUAL", "STATUS"])
    df_plu_display = df_plu[col_sel]
    st.dataframe(df_plu_display, use_container_width=True, hide_index=True)

    # Bar chart top N by stok akhir
    st.subheader("Top 20 PLU — Stok Akhir Terbanyak")
    top20 = df_plu.sort_values("STOK_AKHIR_TERAKHIR", ascending=False).head(20)
    fig = px.bar(top20, x="PLU", y="STOK_AKHIR_TERAKHIR", hover_data=["NAMA_BRG", "TOTAL_TERJUAL"])
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Bottom 20 PLU — Stok Akhir Tersedikit")
    bot20 = df_plu[df_plu["STOK_AKHIR_TERAKHIR"] >= 0].sort_values("STOK_AKHIR_TERAKHIR", ascending=True).head(20)
    fig2 = px.bar(bot20, x="PLU", y="STOK_AKHIR_TERAKHIR", hover_data=["NAMA_BRG", "TOTAL_TERJUAL"])
    st.plotly_chart(fig2, use_container_width=True)

# --- TAB 4: Ringkasan Lokasi ---
with tab4:
    st.subheader("Ringkasan per Lokasi")
    df_lok = sc.summarize_by_lokasi()
    st.dataframe(df_lok, use_container_width=True, hide_index=True)

    fig = px.bar(df_lok, x="LOKASI", y="STOK_AKHIR", hover_data=["NAMA_LOKASI", "TOTAL_PLU", "TOTAL_TERJUAL", "PLU_NEGATIF"],
                 title="Stok Akhir per Lokasi")
    st.plotly_chart(fig, use_container_width=True)

# --- TAB 5: Trend ---
with tab5:
    st.subheader("Trend Bulanan")
    trend = sc.stock_trend()
    st.dataframe(trend, use_container_width=True, hide_index=True)

    col_chart = st.selectbox("Metrik", ["STOK_AWAL", "MASUK", "TERJUAL", "STOK_AKHIR", "RUSAK_BS", "KELUAR_KR", "PAKAI_UP"], index=3)
    fig = px.line(trend, x="BULAN_NAMA", y=col_chart, markers=True,
                  title=f"{col_chart} per Bulan", text=col_chart)
    fig.update_traces(textposition="top center")
    st.plotly_chart(fig, use_container_width=True)

    # Dual axis: stok vs terjual
    fig2 = px.line(trend, x="BULAN_NAMA", y=["STOK_AKHIR", "TERJUAL"], markers=True,
                   title="Stok Akhir vs Terjual")
    st.plotly_chart(fig2, use_container_width=True)

    # Pie chart rusak vs terjual
    total_rusak = int(master["RUSAK_BS"].sum())
    total_terjual = int(master["TERJUAL"].sum())
    total_keluar = int(master["KELUAR_KR"].sum())
    total_pakai = int(master["PAKAI_UP"].sum())
    pie_df = pd.DataFrame({
        "Kategori": ["Terjual", "Rusak", "Mutasi Keluar", "Pemakaian"],
        "QTY": [total_terjual, total_rusak, total_keluar, total_pakai]
    })
    fig3 = px.pie(pie_df, values="QTY", names="Kategori", title="Komposisi Barang Keluar")
    st.plotly_chart(fig3, use_container_width=True)

# --- TAB 6: Stok Negatif ---
with tab6:
    st.subheader("⚠️ Stok Negatif")
    ns = sc.negative_stock()
    if len(ns) == 0:
        st.success("Tidak ada stok negatif! ✅")
    else:
        st.warning(f"{len(ns)} baris dengan stok negatif")
        st.dataframe(ns[["PLU", "NAMA_BRG", "LOKASI", "BULAN_NAMA", "STOK_AWAL", "MASUK", "TERJUAL", "STOK_AKHIR"]],
                     use_container_width=True, hide_index=True)
        plu_neg = ns["PLU"].nunique()
        lok_neg = ns["LOKASI"].nunique()
        st.metric("PLU Bermasalah", plu_neg)
        st.metric("Lokasi Bermasalah", lok_neg)
        st.metric("Total Defisit", int(abs(ns["STOK_AKHIR"].sum())))

# --- TAB 7: Stok Menipis ---
with tab7:
    st.subheader("🟡 Stok Menipis")
    threshold = st.number_input("Batas stok menipis (unit)", min_value=1, value=5)
    ls = sc.low_stock(threshold=int(threshold))
    if len(ls) == 0:
        st.success("Tidak ada stok menipis ✅")
    else:
        st.warning(f"{len(ls)} baris dengan stok ≤ {threshold}")
        st.dataframe(ls[["PLU", "NAMA_BRG", "LOKASI", "BULAN_NAMA", "STOK_AWAL", "TERJUAL", "STOK_AKHIR"]],
                     use_container_width=True, hide_index=True)

# --- TAB 8: Dead Stock ---
with tab8:
    st.subheader("💀 Dead Stock")
    min_months = st.number_input("Minimal bulan tanpa penjualan", min_value=1, value=3)
    ds = sc.dead_stock(min_months=int(min_months))
    if len(ds) == 0:
        st.success(f"Tidak ada dead stock ({min_months} bulan tanpa terjual) ✅")
    else:
        st.warning(f"{len(ds)} item dead stock (stok > 0 tapi 0 terjual {min_months} bulan terakhir)")
        st.dataframe(ds[["PLU", "NAMA_BRG", "LOKASI", "BULAN_NAMA", "STOK_AKHIR", "TERJUAL"]],
                     use_container_width=True, hide_index=True)
        fig = px.bar(ds.head(30), x="PLU", y="STOK_AKHIR", color="LOKASI",
                     hover_data=["NAMA_BRG", "BULAN_NAMA"], title="Top 30 Dead Stock")
        st.plotly_chart(fig, use_container_width=True)

# --- TAB 9: Filter ---
with tab9:
    st.subheader("🔍 Filter & Cari")
    col1, col2 = st.columns(2)
    with col1:
        filt_plu = st.text_input("Cari PLU (pisah koma untuk multiple)")
    with col2:
        filt_lokasi = st.text_input("Cari LOKASI")
    filt_status = st.multiselect("Status", master["STATUS"].unique(), default=[])
    filt_bulan = st.multiselect("Bulan", sorted(master["BULAN"].unique()), format_func=lambda x: {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"Mei",6:"Jun",7:"Jul",8:"Agu",9:"Sep",10:"Okt",11:"Nov",12:"Des"}.get(x,str(x)))
    min_stok = st.number_input("Min STOK_AKHIR", value=-999999, step=100)
    max_stok = st.number_input("Max STOK_AKHIR", value=999999, step=100)

    df = sc.get_stock_card()
    if filt_plu:
        plu_list = [p.strip() for p in filt_plu.split(",")]
        df = df[df["PLU"].astype(str).isin(plu_list)]
    if filt_lokasi:
        df = df[df["LOKASI"].astype(str).str.contains(filt_lokasi)]
    if filt_status:
        df = df[df["STATUS"].isin(filt_status)]
    if filt_bulan:
        df = df[df["BULAN"].isin(filt_bulan)]
    df = df[(df["STOK_AKHIR"] >= min_stok) & (df["STOK_AKHIR"] <= max_stok)]

    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"{len(df)} baris")

# --- TAB 10: Export ---
with tab10:
    st.subheader("📥 Export Excel")
    if st.button("📥 Download Excel"):
        with st.spinner("Membuat Excel..."):
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            try:
                sc.export_excel(tmp.name)
                with open(tmp.name, "rb") as f:
                    st.download_button(
                        label="⬇️ Klik Download",
                        data=f.read(),
                        file_name="stock_card.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                st.success("✅ Siap di-download")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                Path(tmp.name).unlink(missing_ok=True)

    st.subheader("📊 Statistik")
    stats = sc.stats()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("PLU", stats["PLU Unik"])
        st.metric("LOKASI", stats["LOKASI Unik"])
    with col2:
        st.metric("Stok Akhir", f"{stats['Total Stok Akhir']:,}")
        st.metric("Terjual", f"{stats['Total Terjual']:,}")
    with col3:
        st.metric("Masuk", f"{stats['Total Masuk']:,}")
        st.metric("Rusak", f"{stats['Total Rusak']:,}")
    with col4:
        st.metric("PLU Negatif", stats["PLU Stok Negatif"])
        st.metric("PLU Menipis", stats["PLU Menipis (≤5)"])
