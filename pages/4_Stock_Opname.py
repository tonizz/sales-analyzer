"""
Streamlit page — Stock Opname untuk HO / Kantor Pusat.
Lihat hasil scan dari toko, cocokkan dengan stok sistem, export Excel.
"""
from __future__ import annotations

import json
import os
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen, Request

import pandas as pd
import streamlit as st

# Import StockCard untuk generate data stok on-the-fly
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from stock_card import StockCard

st.set_page_config(page_title="Stock Opname — HO", page_icon="📦", layout="wide")

# ─── Auth ───
USER_CREDENTIALS = {"admin": "admin123"}
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("## Login — Stock Opname HO")
    col1, col2 = st.columns([1, 2])
    with col1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Username / password salah")
    st.stop()

# ─── Helper ────
BASE_DIR = Path(__file__).parent.parent

@st.cache_data(show_spinner="Loading nama map...")
def load_nama_map() -> dict:
    path = BASE_DIR / "nama_map.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}

@st.cache_data(show_spinner="Loading barcode map...")
def load_barcode_count() -> int:
    path = BASE_DIR / "barcode_map.json"
    if path.exists():
        with open(path) as f:
            return len(json.load(f))
    return 0

@st.cache_data(show_spinner="Loading stock sistem...")
def load_stock_sistem() -> pd.DataFrame:
    """Load stok per PLU dari data langsung via StockCard."""
    sa_path = BASE_DIR / "stok awal januari 2026.xlsx"
    dbu_path = BASE_DIR / "DBUTHN_55_2026.xlsx"
    dbks_path = BASE_DIR / "DBKSTHN_55_2026.xlsx"
    if not sa_path.exists() or not dbu_path.exists() or not dbks_path.exists():
        st.warning("Data stok tidak lengkap di server. Jalankan stock_card.py dulu.")
        return pd.DataFrame()
    try:
        sc = StockCard()
        sc.load_data(str(sa_path), str(dbu_path), str(dbks_path))
        cards = sc.get_stock_card()  # DataFrame: semua bulan
        last_month = cards['BULAN'].max()
        last_df = cards[cards['BULAN'] == last_month]
        result = last_df.groupby('PLU').agg(
            NAMA_BRG=('NAMA_BRG', 'first'),
            STOK_SISTEM=('STOK_AKHIR', 'sum')
        ).reset_index()
        result['PLU'] = result['PLU'].astype(str).str.strip()
        result['STOK_SISTEM'] = result['STOK_SISTEM'].fillna(0).astype(int)
        return result
    except Exception as e:
        st.warning(f"Gagal generate stok sistem: {e}")
        return pd.DataFrame()

def load_scan_from_server(server_url: str) -> dict | None:
    """Ambil data scan dari server."""
    try:
        req = Request(f"{server_url}/api/download", headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        st.warning(f"Gagal ambil data dari server: {e}")
        return None

def match_stok(scan_df: pd.DataFrame, sistem_df: pd.DataFrame) -> pd.DataFrame:
    """Cocokkan hasil scan vs stok sistem."""
    merged = scan_df.merge(sistem_df, on='PLU', how='left')
    merged['STOK_SISTEM'] = merged['STOK_SISTEM'].fillna(0).astype(int)
    merged['SELISIH'] = merged['QTY'] - merged['STOK_SISTEM']
    merged['STATUS'] = merged['SELISIH'].apply(
        lambda x: 'SESUAI' if x == 0 else ('LEBIH' if x > 0 else 'KURANG'))
    merged['NAMA'] = merged.get('NAMA_BRG_y', merged.get('NAMA', ''))
    cols = ['PLU', 'NAMA', 'STOK_SISTEM', 'QTY', 'SELISIH', 'STATUS', 'TOKO', 'TS']
    avail = [c for c in cols if c in merged.columns]
    return merged[avail].sort_values('SELISIH')

# ─── UI ────
st.title("📦 Stock Opname — Kantor Pusat")
st.markdown(f"**Database:** {load_barcode_count():,} barcode | {len(load_nama_map())} PLU")

tab1, tab2, tab3 = st.tabs(["📥 Ambil Data dari Server", "📤 Upload File Scan", "🔍 Cocokkan Stok"])

# ─── Tab 1: Ambil dari Server ────
with tab1:
    st.subheader("Ambil data scan dari server toko")
    server_url = st.text_input("URL Server (contoh: http://192.168.1.10:8000)",
                               help="Masukkan URL server opname_server.py yang jalan di toko")
    st.info("Butuh ngrok jika server tidak satu jaringan. Contoh: https://xxxx.ngrok-free.app")
    
    if st.button("Ambil Data", type="primary") and server_url:
        data = load_scan_from_server(server_url)
        if data and data.get("items"):
            st.success(f"Berhasil ambil {len(data['items'])} item dari toko: {data.get('toko', '-')}")
            st.session_state['scan_data_server'] = data
        else:
            st.warning("Tidak ada data scan di server. Pastikan toko sudah scan & kirim.")

    if 'scan_data_server' in st.session_state:
        data = st.session_state['scan_data_server']
        df = pd.DataFrame(data['items'])
        df.columns = df.columns.str.upper().str.strip()
        if 'PLU' in df.columns:
            df['PLU'] = df['PLU'].astype(str).str.strip()
        st.dataframe(df, use_container_width=True)
        st.download_button(
            "⬇ Download JSON", json.dumps(data, indent=2),
            "opname_hasil.json", "application/json"
        )

# ─── Tab 2: Upload File ────
with tab2:
    st.subheader("Upload file hasil scan dari toko")
    uploaded = st.file_uploader("Upload file JSON / CSV hasil scan", type=["json", "csv"])
    
    if uploaded:
        ext = Path(uploaded.name).suffix.lower()
        if ext == ".json":
            data = json.loads(uploaded.read())
            items = data.get("items", data) if isinstance(data, dict) else data
            df = pd.DataFrame(items)
            st.session_state['scan_data_upload'] = df
        else:
            df = pd.read_csv(uploaded)
            st.session_state['scan_data_upload'] = df
        
        df.columns = df.columns.str.upper().str.strip()
        st.success(f"Loaded {len(df)} items")
        st.dataframe(df, use_container_width=True)

# ─── Tab 3: Cocokkan ────
with tab3:
    st.subheader("Cocokkan hasil scan dengan stok sistem")
    
    # Pilih sumber data
    src = st.radio("Sumber data:", ["Dari Server", "Upload File", "Session Saat Ini"])
    
    scan_df = None
    if src == "Dari Server" and 'scan_data_server' in st.session_state:
        scan_df = pd.DataFrame(st.session_state['scan_data_server']['items'])
    elif src == "Upload File" and 'scan_data_upload' in st.session_state:
        scan_df = st.session_state['scan_data_upload']
    else:
        # Session — data dari scan sebelumnya atau sample
        if 'merged_result' in st.session_state:
            st.info("Gunakan data hasil matching sebelumnya. Upload/ambil data baru untuk update.")
    
    if scan_df is not None:
        scan_df.columns = scan_df.columns.str.upper().str.strip()
        rename_map = {}
        if 'PLU' not in scan_df.columns:
            for c in scan_df.columns:
                if 'PLU' in c.upper():
                    rename_map[c] = 'PLU'
                    break
        if 'QTY' not in scan_df.columns and 'STOK' in scan_df.columns:
            rename_map['STOK_FISIK'] = 'QTY'
            rename_map['STOK'] = 'QTY'
        if 'QTY' not in scan_df.columns:
            # cari kolom numerik selain PLU
            for c in scan_df.columns:
                if c not in ['PLU', 'NAMA', 'TOKO', 'TS', 'TANGGAL'] and scan_df[c].dtype in ['int64', 'float64']:
                    rename_map[c] = 'QTY'
                    break
        if 'TOKO' not in scan_df.columns:
            scan_df['TOKO'] = ''
        if 'TS' not in scan_df.columns:
            scan_df['TS'] = ''
        
        if rename_map:
            scan_df = scan_df.rename(columns=rename_map)
        
        if 'PLU' in scan_df.columns:
            scan_df['PLU'] = scan_df['PLU'].astype(str).str.strip()
            if 'QTY' in scan_df.columns:
                scan_df['QTY'] = pd.to_numeric(scan_df['QTY'], errors='coerce').fillna(0).astype(int)
        
        st.write(f"**Data scan:** {len(scan_df)} item, {scan_df['TOKO'].iloc[0] if 'TOKO' in scan_df.columns and scan_df['TOKO'].iloc[0] else 'tanpa toko'}")
        
        if st.button("Cocokkan dengan Stok Sistem", type="primary"):
            with st.spinner("Mencocokkan..."):
                sistem = load_stock_sistem()
                if sistem.empty:
                    st.error("File stock_card_output.xlsx tidak ditemukan. Jalankan stock_card.py dulu.")
                else:
                    result = match_stok(scan_df, sistem)
                    st.session_state['merged_result'] = result
                    
                    # Ringkasan
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Scan", len(result))
                    col2.metric("Sesuai", len(result[result['STATUS']=='SESUAI']))
                    col3.metric("Tidak Sesuai", len(result[result['STATUS']!='SESUAI']))
                    col4.metric("Selisih Total", f"{result['SELISIH'].sum():,}")
                    
                    st.subheader("Hasil Selisih")
                    st.dataframe(result, use_container_width=True, height=400)
                    
                    # Excel
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        result.to_excel(writer, sheet_name='Selisih', index=False)
                        result[result['STATUS']!='SESUAI'].to_excel(writer, sheet_name='Tidak Sesuai', index=False)
                        summary = result['STATUS'].value_counts().reset_index()
                        summary.columns = ['Status', 'Jumlah']
                        summary.to_excel(writer, sheet_name='Ringkasan', index=False)
                    st.download_button(
                        "⬇ Download Excel",
                        output.getvalue(),
                        "opname_selisih.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
    
    if 'merged_result' in st.session_state:
        result = st.session_state['merged_result']
        filter_status = st.selectbox("Filter status:", ["Semua", "SESUAI", "KURANG", "LEBIH"])
        filtered = result if filter_status == "Semua" else result[result['STATUS'] == filter_status]
        st.dataframe(filtered, use_container_width=True, height=300)

st.markdown("---")
st.caption("INTEX Stock Opname System — v1.0")
