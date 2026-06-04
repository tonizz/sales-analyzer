# Sales Analyzer

Alat analisa penjualan dari data POS (Point of Sale) — baik **paket/bundle** maupun **item satuan**.

Tiga cara pakai:
- 🖥️ **Desktop GUI** (Tkinter) — `python bundle_analyzer.py` atau `dist\BundleAnalyzer.exe`
- 🐍 **CLI** — `python bundle_analyzer.py --cli data.xlsx --out hasil.xlsx`
- 🌐 **Web** (Streamlit + Plotly) — `streamlit run bundle_analyzer_web.py`

Lihat [`PANDUAN.md`](./PANDUAN.md) untuk dokumentasi lengkap.

## Fitur

- Deteksi otomatis paket/bundle (NOTRAN punya ≥2 item, semua diskon sama)
- Ringkasan per lokasi, distribusi diskon, detail audit
- Top combo paket, top item di paket, pencarian item
- Analisa margin bundle vs non-bundle
- Perbandingan 2 periode (preset atau custom)
- Trend chart harian/bulanan
- **Item satuan (non-bundle)**: ringkasan, detail, top item, distribusi diskon, pencarian
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
├── PANDUAN.md                # Dokumentasi lengkap (Indonesia)
├── requirements.txt          # Dependency web
├── run_web.bat               # Shortcut Windows untuk web
├── build.bat                 # Rebuild executable
├── dist/
│   └── BundleAnalyzer.exe    # Executable Windows (75 MB)
└── .gitignore
```

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
- Repo harus **public** (sudah)
- Setiap push ke branch `main` → otomatis re-deploy
- Free tier: app tidur setelah 7 hari tidak ada访问, otomatis bangun saat ada yang akses
- Free tier: 1 GB RAM, cukup untuk data 100k+ baris

## 🔐 Autentikasi (Password Gate)

App ini diproteksi login. **Default credentials** (dev only — untuk testing):

| Username | Password |
|---|---|
| `admin` | `admin123` |
| `tonizz` | `tonizz2026` |

### Ganti password di production:

1. Generate bcrypt hash baru:
   ```python
   import bcrypt; print(bcrypt.hashpw(b"password_baru", bcrypt.gensalt()).decode())
   ```
2. Buka https://share.streamlit.io/ → klik app → **Settings** → **Secrets**
3. Isi format TOML:
   ```toml
   [users]
   admin = "$2b$12$..."
   tonizz = "$2b$12$..."
   ```
4. Save → app auto-restart, password baru aktif

### Tambah user baru:

Cukup tambah baris di secrets.toml:
```toml
[users]
admin = "$2b$12$..."
tonizz = "$2b$12$..."
user_baru = "$2b$12$..."
```

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
