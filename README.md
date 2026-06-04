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
