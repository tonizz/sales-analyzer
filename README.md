# Sales Analyzer

Alat analisa penjualan dari data POS (Point of Sale) — baik **paket/bundle** maupun **item satuan**.

Tiga cara pakai:
- 🖥️ **Desktop GUI** (Tkinter) — `python bundle_analyzer.py` atau `dist\BundleAnalyzer.exe`
- 🐍 **CLI** — `python bundle_analyzer.py --cli data.xlsx --out hasil.xlsx`
- 🌐 **Web** (Streamlit + Plotly) — `streamlit run bundle_analyzer_web.py`

Lihat [`PANDUAN.md`](./PANDUAN.md) untuk dokumentasi lengkap.

## Fitur

Web app 14 tab + 4 halaman multi-page:

- Deteksi otomatis paket/bundle (NOTRAN punya ≥2 item, semua diskon sama)
- Ringkasan per lokasi, distribusi diskon, detail audit
- Top combo paket, top item di paket, pencarian item
- Analisa margin bundle vs non-bundle (+ Master Cost & Data Stok)
- Perbandingan 2 periode (preset atau custom)
- Trend chart harian/bulanan
- **Item satuan (non-bundle)**: ringkasan, detail, top item, distribusi diskon, pencarian
- Strategi penjualan: slow moving, dead stock, rekomendasi promo
- Basket analysis (nilai keranjang per lokasi)
- **⚡ KPI Harian** — snapshot hari terakhir vs rata-rata 7/30 hari, top item, alert stok
- **📤 Notifikasi** — kirim ringkasan KPI ke Telegram Bot / Webhook
- **🧑‍💼 Performa Kasir** — ranking penjualan kasir + deteksi anomali diskon (fraud detection)
- **🏷️ Efektivitas Promo** — perbandingan volume item saat promo vs normal
- **📅 YoY & Forecast** (halaman) — multi-tahun, seasonal, GradientBoosting forecast
  + **🎯 validasi backtest MAPE** (ukur akurasi forecast)
- **📦 Stock Card** (halaman) — kartu stok per PLU/lokasi/bulan
- **🧮 Stock Opname** (halaman + scanner barcode GitHub Pages)
- Export ke Excel multi-sheet

## Quick start

### Versi Web (direkomendasikan)
```powershell
pip install -r requirements.txt
streamlit run bundle_analyzer_web.py
```
Akses: http://localhost:8501

### Versi Desktop (Windows, tanpa Python)
Double-click `dist\BundleAnalyzer.exe`.

### Versi Source (developer)
```powershell
pip install pandas openpyxl matplotlib
python bundle_analyzer.py
```

## Struktur file

```
.
├── bundle_analyzer.py        # Source code utama (analyzer + GUI + CLI)
├── bundle_analyzer_web.py    # Web app (Streamlit + Plotly)
├── auth.py                   # Modul login terpusat (bcrypt + secrets)
├── notifications.py          # Kirim alert ke Telegram / Webhook
├── pages/                    # Halaman multi-page Streamlit
│   ├── 1_Stock_Sales_Analyzer.py
│   ├── 2_YoY_Forecast.py
│   ├── 3_Stock_Card.py
│   └── 4_Stock_Opname.py
├── tests/                    # Unit tests (pytest)
├── .github/workflows/ci.yml  # CI: test otomatis setiap push
├── PANDUAN.md                # Dokumentasi lengkap (Indonesia)
├── requirements.txt          # Dependency web (pinned range)
├── run_web.bat               # Shortcut Windows untuk web
├── build.bat                 # Rebuild executable
└── .gitignore
```
> 📥 Executable desktop `BundleAnalyzer.exe` tidak ikut di git —
> download dari **GitHub Releases**:
> https://github.com/tonizz/sales-analyzer/releases

## Lisensi

Internal tool.

---

## 🚀 Deploy ke Streamlit Cloud (GRATIS)

Aplikasi web bisa di-deploy gratis ke **Streamlit Community Cloud** agar bisa diakses dari mana saja via internet.

### Langkah deploy (5 menit):

1. **Buka https://share.streamlit.io** (login dengan akun GitHub `tonizz`)
2. Klik **"New app"**
3. Isi form:
   - **Repository**: `tonizz/sales-analyzer`
   - **Branch**: `main`
   - **Main file path**: `bundle_analyzer_web.py`
   - **App URL**: pilih subdomain (mis. `sales-analyzer-tonizz`)
4. Klik **"Deploy!"** 🚀
5. Tunggu 2-5 menit (build & install dependencies)
6. Aplikasi live di: `https://[subdomain].streamlit.app`

### File yang dibutuhkan (sudah ada):
- ✅ `bundle_analyzer_web.py` — main file
- ✅ `requirements.txt` — Python dependencies
- ✅ `runtime.txt` — Python version (3.11)
- ✅ `.streamlit/config.toml` — theme & server config

### Catatan:
- Repo saat ini **public** (tahap pengembangan). ⚠️ Jika suatu saat bos minta private: ubah visibility, Pages scanner toko akan mati (Pages gratis hanya untuk repo public) — alternatif: serve scanner via `opname_server.py` atau pindah ke Cloudflare Pages
- Setiap push ke branch `main` → otomatis re-deploy
- Free tier: app tidur setelah 7 hari tidak ada akses, otomatis bangun saat ada yang akses
- Free tier: 1 GB RAM, cukup untuk data 100k+ baris

## 🔐 Autentikasi (Password Gate)

Semua halaman memakai login terpusat di `auth.py` (bcrypt, login sekali
untuk semua halaman).

**Setup production (WAJIB di Streamlit Cloud):**
1. Generate bcrypt hash:
   ```python
   import bcrypt; print(bcrypt.hashpw(b"password_baru", bcrypt.gensalt()).decode())
   ```
2. https://share.streamlit.io/ → klik app → **Settings** → **Secrets**:
   ```toml
   [users]
   admin = "$2b$12$..."
   tonizz = "$2b$12$..."
   ```
3. Save → app auto-restart. Jika secrets kosong, fallback dev dipakai
   (akan muncul warning di halaman login).

Tidak ada hint password yang ditampilkan di UI. ⚠️ File data penjualan
(`DBKSTHN_*.xlsx` dll) ikut di-track di repo ini. Selama repo public,
data tersebut bisa dilihat publik — pertimbangkan private jika data sensitif.

## 📡 Auto-fetch dari Google Drive (opsional)

App bisa **auto-fetch data** dari Google Drive sharing link. Tidak perlu upload manual.

### Setup:
1. Upload `DBKSTHN_*.xlsx` ke Google Drive
2. Share → "Anyone with the link" → Copy link
3. Di app, buka sidebar → "📡 Auto-fetch dari Google Drive" → paste link → klik "🔄 Refresh dari URL"

### Default URL via secrets:
Tambahkan di Streamlit Secrets:
```toml
[data]
url = "https://drive.google.com/file/d/1ABC...XYZ/view?usp=sharing"
```

Update file di Drive = klik refresh = data baru. Detail lengkap: lihat [PANDUAN.md](./PANDUAN.md) section 13.

## 📤 Notifikasi Alert (Telegram / Webhook)

Tab **⚡ KPI Harian** bisa mengirim ringkasan (revenue hari terakhir, top item,
dead stock, stok menipis) ke **Telegram Bot** atau **Webhook** generik (Slack dll).

### Setup Telegram Bot (2 menit):
1. Chat [@BotFather](https://t.me/BotFather) di Telegram → `/newbot` → beri nama → copy **token** (format `123456:ABC...`)
2. Tambahkan bot ke grup/channel, atau chat bot lalu kunjungi
   `https://api.telegram.org/bot<TOKEN>/getUpdates` untuk dapat **chat_id**
3. Isi di app (tab KPI → kirim notifikasi), **atau** simpan permanen di
   **Streamlit Cloud > Secrets**:
   ```toml
   [telegram]
   bot_token = "123456:ABC-def..."
   chat_id   = "-1001234567890"

   [webhook]            # opsional, untuk Slack/endpoint custom
   url = "https://hooks.slack.com/services/..."
   ```
4. Buka tab **⚡ KPI Harian** → **📤 Kirim Ringkasan** → pilih Telegram / Webhook.

> Logic ada di `notifications.py`. Bisa juga dipanggil dari script lain:
> ```python
> from notifications import build_kpi_alert, send_telegram
> msg = build_kpi_alert(kpi_dict)
> send_telegram(token, chat_id, msg)
> ```

