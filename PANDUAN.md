# 📘 PANDUAN LENGKAP SALES ANALYZER

Dokumentasi resmi untuk tools **Sales Analyzer** (versi 2.0+).
Menganalisa penjualan **paket/bundle** maupun **item satuan** (non-bundle) dari data POS.
File utama: `bundle_analyzer.py`
Executable: `dist\BundleAnalyzer.exe`

---

## 1. INSTALASI & PERSIAPAN

Pilih salah satu dari 3 versi:

### 1.A 🌐 Versi WEB (Streamlit) — Paling Direkomendasikan ⭐
**Kelebihan:** visualisasi interaktif (chart Plotly), modern, multi-user (bisa dibuka dari HP/tablet), UI paling menarik.

**Cara jalanin:**
```powershell
# 1. Install dependencies (sekali)
python -m pip install -r requirements.txt

# 2. Jalankan (paling gampang: double-click run_web.bat)
streamlit run bundle_analyzer_web.py
# atau double-click: run_web.bat
```

**Akses:** buka browser ke **http://localhost:8501**

**File:** `bundle_analyzer_web.py`, `run_web.bat`, `requirements.txt`

### 1.B 🖥️ Versi Desktop `.exe` (TANPA Python)
**Kelebihan:** single file, no install, no setup.

**Cara pakai:**
1. Double-click `BundleAnalyzer.exe`
2. GUI langsung terbuka
3. Klik **❓ Help / Panduan** untuk dokumentasi

**File:** `dist\BundleAnalyzer.exe` (~47 MB)

### 1.C 🐍 Versi Python Source (untuk developer)
**Cara pakai:**
- GUI: `python bundle_analyzer.py`
- CLI: `python bundle_analyzer.py --cli "data.xlsx" --out hasil.xlsx`
- Opsi CLI: `--min-items 2`, `--min-discount 0`

### 1.D Build `.exe` dari Source
Jalankan `build.bat` (double-click) atau:
```powershell
python -m PyInstaller --onefile --windowed --name "BundleAnalyzer" --add-data "PANDUAN.md;." --clean --noconfirm bundle_analyzer.py
```

---

## 2. FILE OUTPUT EXCEL

Setiap export Excel punya **sheet `BACA_DULU`** di posisi pertama berisi glosarium semua istilah.

**Urutan sheet pada Export utama (Tab 1-4):**
1. `BACA_DULU` — kamus istilah
2. `Summary_per_Lokasi` — ringkasan per outlet
3. `Distribusi_Discount` — sebaran diskon%
4. `Detail_Bundle` — per baris item dalam bundle
5. `Top_Kombinasi_Bundle` — 20 combo terlaris per lokasi
6. `NonBundle_Reff` — pembanding transaksi non-bundle

**Export Pencarian Item** (Tab 🔍):
- `Ringkasan` + `Detail_Paket`

**Export Perbandingan** (Tab 📊):
- `Ringkasan_VS` + `Per_Lokasi_VS`

**Export Top Produk** (Tab 🏆):
- `Top_Produk` + `Pasangan_Item` (jika ada pencarian pasangan)

**Export Margin** (Tab 💰):
- `Ringkasan` + `Per_Lokasi`

---

## 3. FORM UTAMA (BAGIAN ATAS GUI)

Setelah aplikasi terbuka, di bagian paling atas ada **5 input**:

| Field | Wajib | Fungsi | Contoh |
|---|---|---|---|
| **File Excel** | ✅ | Pilih file `.xlsx`/`.xls` lewat tombol **Browse...** | `DBKSTHN_55_2026.xlsx` |
| **Min item per bundle** | ⬜ | Ambang item minimum agar disebut bundle | `2` (default) |
| **Min discount %** | ⬜ | Filter hanya bundle dengan diskon ≥ nilai ini | `0` (semua) |
| **Filter FLOCCD** | ⬜ | Pisahkan kode lokasi dengan koma untuk analisa lokasi tertentu saja. Kosongkan = semua. | `55592, 55733` |
| **Periode / Preset** | ⬜ | Pilih dari dropdown → tanggal auto-terisi | `Bulan ini` |
| **Dari** / **Sampai** | ⬜ | Otomatis terisi dari preset. Pilih `Custom` di preset untuk isi manual (format `YYYY-MM-DD`) | `2026-01-15` |

**Tombol aksi:**
- **▶ Analisa** — proses file → muncul di tab-tab
- **💾 Export ke Excel** — simpan hasil Tab 1-4 ke file `.xlsx`
- **Bersihkan** — reset semua input

**Date Preset yang tersedia:**
- Semua data
- 7 / 14 / 30 / 90 hari terakhir
- Bulan ini / Bulan lalu
- 3 bulan / 6 bulan terakhir
- Tahun ini (YTD)
- Custom (isi tanggal sendiri)

> ⚠️ Filter di form ini (FLOCCD + Periode) **berlaku untuk semua tab** termasuk Perbandingan & Trend.

---

## 4. SEMUA TAB DI GUI

Total ada **10 tab** (kiri ke kanan):

| # | Tab | Fokus |
|---|---|---|
| 1 | 📊 Summary | Bundle per lokasi |
| 2 | 📈 Distribusi | Pola diskon bundle |
| 3 | 📋 Detail Bundle | 1 baris = 1 item di paket |
| 4 | 🏆 Top Combo | Kombinasi barang di paket |
| 5 | 🔍 Cari Paket | Cari paket by item |
| 6 | 🏆 Top Produk Bundle | Item paling sering di paket |
| 7 | 💰 Margin | Bandingkan margin bundle vs satuan |
| 8 | 📊 Perbandingan | 2 periode head-to-head |
| 9 | 📈 Trend | Grafik waktu |
| 10 | 📋 **Item Satuan** | **Non-bundle: ringkasan, detail, top item, distribusi diskon, pencarian** |

### Tab 10 — 📋 Item Satuan (Non-Bundle)
**Jawaban:** *"Bagaimana penjualan item satuan (di luar paket)?"*

Tab ini punya 5 sub-tampilan (sub-tab di web, sub-Notebook di desktop GUI):

#### 10A. Ringkasan per Lokasi
- `FLOCCD`, `FNAMA`, `TOTAL_TX`, `TOTAL_QTY`, `TOTAL_REVENUE`
- `AVG_DISC_PCT`, `AVG_ITEMS_PER_TX`

#### 10B. Detail Item Satuan
- 1 baris = 1 item yang dijual satuan (bukan di paket)
- Kolom sama dengan Detail Bundle tapi `~IS_BUNDLE`

#### 10C. Top Item Satuan
- Item paling laris dijual satuan (diurutkan by QTY)
- Kolom: `PLU`, `NAMA_BRG`, `JUMLAH_TX`, `TOTAL_QTY`, `TOTAL_REVENUE_JUMLAH`, `TOTAL_REVENUE_GROSS`, `AVG_PRICE`

#### 10D. Distribusi Diskon Item
- Distribusi nilai diskon (%) untuk item satuan per lokasi
- Berbeda dengan distribusi bundle: di sini setiap baris punya diskon sendiri (tidak harus sama)
- Berguna untuk lihat "berapa % diskon yang sering dipakai di item satuan"

#### 10E. Pencarian Item
- Cari baris item satuan yang mengandung kata kunci PLU/nama
- Bisa filter FLOCCD + range tanggal
- Return: ringkasan + detail per baris

**Kapan pakai tab ini:**
- Mau tahu item mana yang paling laris TANPA paket
- Mau bandingkan budaya "paket" vs "satuan" di tiap lokasi
- Mau audit transaksi non-bundle (misal: cek apakah kasir selalu kasih diskon di item satuan)

---

## 4A. PERBEDAAN PAKET vs SATUAN

| Aspek | Paket/Bundle | Item Satuan (Non-Bundle) |
|---|---|---|
| Kriteria | NOTRAN punya ≥2 item DAN semua diskon sama | NOTRAN < 2 item ATAU diskon item tidak seragam |
| Jumlah baris (data contoh) | 1.693 (10%) | 14.644 (90%) |
| Revenue | `JUALAHIR × QTY` (gross) | Sama |
| Analisa utama | Kombinasi, distribusi diskon bundle | Top item, distribusi diskon per-item |
| Cocok untuk | Promo paket, kombinasi best-seller | Audit harga satuan, litem item reguler |

### Tab 2 — 📈 Distribusi Discount
**Jawaban:** *"Diskon berapa % yang paling sering dipakai untuk bundle?"*

| Kolom | Artinya |
|---|---|
| `FLOCCD` | Lokasi |
| `BUNDLE_DISC_PCT` | Nilai diskon (%) |
| `JUMLAH_TX` | Berapa bundle pakai diskon segitu |
| `TOTAL_QTY` | Unit terjual |
| `TOTAL_REVENUE` | Uang dari diskon segitu |

**Cara baca:** cari baris dengan `JUMLAH_TX` terbesar per lokasi → itulah **pola diskon favorit**.

---

### Tab 3 — 📋 Detail Bundle
**Jawaban:** *"Apa saja isi tiap transaksi bundle? Siapa yang jual?"*

1 baris = 1 item. Sort by `NOTRAN` untuk melihat 1 transaksi utuh.
Kolom: `FLOCCD, FDATE, NOTRAN, PRAMUNIAGA, KASIR, BUNDLE_DISC_PCT, NOM, PLU, NAMA_BRG, QTY, DISCOUNT, JUALAHIR, JUMLAH, LINE_REVENUE`.

---

### Tab 4 — 🏆 Top Kombinasi Bundle
**Jawaban:** *"Kombinasi barang apa yang paling sering dijadikan bundle?"*

Kolom: `FLOCCD, BUNDLE_DISC_PCT, KOMBINASI_ITEM, JUMLAH_TX, TOTAL_REVENUE, TOTAL_QTY`.

Baris atas per lokasi = combo terlaris. Pertahankan stoknya. Baris bawah = kandidat evaluasi.

---

### Tab 5 — 🔍 Cari Paket by Item
**Jawaban:** *"Ada berapa bundle yang di dalamnya ada item X, dengan total berapa rupiah?"*

**Input:**
| Field | Isi |
|---|---|
| **Kode Lokasi** | Pilih dari dropdown (auto-isi setelah load data), atau kosongkan = semua |
| **Kode / Nama Item** | Substring (case-insensitive) dicocokkan ke **PLU** dan **NAMA_BRG** |
| **Dari / Sampai** | Periode. Format `YYYY-MM-DD`. Kosongkan = tanpa batas |

**Tombol:**
- **🔎 Cari Paket** — proses
- **Reset Pencarian** — kosongkan form & tabel
- **💾 Export Hasil Pencarian** — simpan ke Excel (2 sheet: Ringkasan + Detail_Paket)

**Output:**
- **Jumlah Paket** — berapa transaksi bundle yang mengandung item tersebut
- **Total Nilai (JUMLAH)** — rupiah, dihitung dari `SUM(JUMLAH)` per `(NOTRAN, DISCOUNT)`
- **Total QTY** — jumlah unit
- **Rata-rata Diskon %** — diskon rata-rata bundle-nya
- **Tabel detail** — 1 baris = 1 paket (NOTRAN, tanggal, daftar item, qty, total JUMLAH, kasir)

> 💡 Bedanya dengan "Top Kombinasi": Top Kombinasi mengelompokkan **combo** yang persis sama. Tab ini menghitung **semua bundle yang mengandung item tertentu**, apapun pasangannya.

---

### Tab 6 — 🏆 Top Produk Bundle
**Jawaban:** *"Item apa yang paling sering/laris masuk bundle?"*

**Bagian 1 — Top N item paling sering di-bundle:**
| Field | Isi |
|---|---|
| Lokasi | Pilih dari dropdown. Kosongkan = semua |
| Top N | 5-100, default 20 |

| Kolom Hasil | Artinya |
|---|---|
| `PLU` / `NAMA_BRG` | Identitas produk |
| `JUMLAH_BUNDLE` | Berapa bundle berbeda yang memuat item ini |
| `TOTAL_QTY` | Unit terjual via bundle |
| `TOTAL_REVENUE_JUMLAH` | Revenue (sum JUMLAH) |
| `TOTAL_REVENUE_GROSS` | Revenue (sum JUALAHIR × QTY) |
| `AVG_DISC_PCT` | Rata-rata diskon bundle-nya |

**Bagian 2 — Cari pasangan item:**
- Ketik kode/nama item → klik **🔎 Cari Pasangan**
- Hasil: item lain yang paling sering **se-bundle** dengan item tersebut
- Kolom: `CO_OCCURRENCE` (berapa kali muncul di bundle yang sama), `TOTAL_QTY`, `TOTAL_REVENUE`

**Export** ke Excel (2 sheet: `Top_Produk` + `Pasangan_Item`).

---

### Tab 7 — 💰 Analisa Margin
**Jawaban:** *"Bundle untung atau rugi dibanding jual satuan? Margin per lokasi berapa?"*

**⚠️ PERHATIAN:** Kolom `PRC_HIP` di file contoh ini berisi **100 untuk semua baris** → itu **placeholder, bukan harga modal**. Hasil margin tanpa asumsi akan tidak akurat (tampak 99%).

**Solusi:** isi **"Asumsi biaya (% dari JUALAHIR)"** dengan estimasi cost ratio Anda. Mis. `30` artinya biaya 30% dari harga jual → margin = 70%.

**Input:**
| Field | Isi |
|---|---|
| Lokasi | Pilih/kosongkan |
| Asumsi biaya | 0-100 (kosongkan = pakai PRC_HIP dari data) |

**Output:**
- **Ringkasan Bundle vs Non-Bundle**: Revenue, Cost, Margin, Margin %, QTY
- **Per Lokasi**: tabel 19 lokasi (atau sesuai filter) dengan Bundle & NonBundle: Revenue, Cost, Margin, Margin%

**Export** ke Excel (2 sheet: `Ringkasan` + `Per_Lokasi`).

> 💡 Untuk hasil akurat, sediakan file `cost_master.xlsx` dengan kolom `PLU, COST`. Saya bisa tambahkan fitur upload cost master.

---

### Tab 8 — 📊 Perbandingan (VS)
**Jawaban:** *"Bandingkan 2 periode: bulan ini vs bulan lalu, dll."*

**Preset pembanding:**
- Bulan ini vs Bulan lalu
- 7 hari terakhir vs 7 hari sebelumnya
- 14 hari terakhir vs 14 hari sebelumnya
- 30 hari terakhir vs 30 hari sebelumnya
- Quarter ini vs Quarter lalu
- Custom (isi 4 tanggal manual)

Saat preset dipilih, 4 kolom tanggal **auto-terisi**. Bisa diedit manual.

**Output (2 sub-tab):**
1. **Ringkasan**: 8 metrik side-by-side + kolom **Perubahan % (P1 vs P2)**
   - Positif = P1 lebih tinggi dari P2 (P2 = baseline)
   - Metrik: Total Revenue, Total Transaksi, Bundle Transaksi, Bundle %, Bundle Revenue, Total QTY, Bundle QTY, Avg Diskon Bundle

2. **Per Lokasi**: tabel breakdown semua lokasi
   - Kolom: Revenue_P1, Revenue_P2, Revenue_Growth_%, Bundle_Revenue_P1/P2/Growth%, TX_P1/P2/Growth%, Bundle_TX_P1/P2/Growth%

**Export** ke Excel (2 sheet: `Ringkasan_VS` + `Per_Lokasi_VS`).

---

### Tab 9 — 📈 Trend & Chart
**Jawaban:** *"Bagaimana tren penjualan dari waktu ke waktu?"*

**Input:**
| Field | Isi |
|---|---|
| Dari / Sampai | Periode. Kosongkan = semua data (sesuai filter form utama) |
| Granularitas | **Harian** atau **Bulanan** |
| Tampilkan | **Revenue** / **Bundle Revenue** / **Transaksi** / **Bundle Transaksi** |

**Output:**
- **Chart garis** matplotlib (di-embed di GUI)
- **Tabel data** di bawah chart

---

## 5. CARA BACA OUTPUT (CONTOH KASUS)

### Contoh 1: "Lokasi mana yang harus saya perhatikan?"
→ Buka **Tab 1 (Summary)**, sort by `BUNDLE_TX_PCT` desc.
- Lokasi dengan % tinggi → budaya bundle kuat, mungkin margin tipis
- Lokasi dengan % 0% → cek apakah memang tidak ada program bundle atau ada masalah pencatatan

### Contoh 2: "Bundle yang berisi item X laku berapa?"
→ Buka **Tab 5 (Cari Paket by Item)**, isi item + lokasi + periode.
- Lihat `Jumlah Paket` → volume
- Lihat `Total Nilai (JUMLAH)` → revenue
- Buka tabel detail → tahu persis paket apa saja yang laku

### Contoh 3: "Apakah campaign bundle bulan ini berhasil dibanding bulan lalu?"
→ Buka **Tab 8 (Perbandingan)**, preset "Bulan ini vs Bulan lalu".
- Lihat `Bundle Revenue` dan `Bundle %`
- Lihat juga `Total Transaksi` → apakah TX naik/turun

### Contoh 4: "Item apa yang harus saya stok lebih banyak?"
→ Buka **Tab 6 (Top Produk Bundle)**, lihat kolom `JUMLAH_BUNDLE` dan `TOTAL_QTY`.
- Item atas = paling laris via bundle → pastikan stok cukup

### Contoh 5: "Paket ini di-bundle sama produk apa biasanya?"
→ **Tab 6**, bagian "Cari Pasangan".
- Ketik item utama → lihat pasangannya
- Berguna untuk promo silang atau bundling baru

---

## 6. ALUR KERJA YANG DIREKOMENDASIKAN

1. **Buka tools** → `python bundle_analyzer.py`
2. **Klik Browse** → pilih file Excel
3. **Pilih date preset** "Semua data" dulu (atau filter periode yang Anda mau)
4. **Klik ▶ Analisa** → cek Tab 1 untuk lihat gambaran besar
5. **Drill-down**:
   - Butuh tau item tertentu? → Tab 5 (Cari Paket)
   - Mau tau combo terlaris? → Tab 4 atau 6
   - Mau bandingkan bulan? → Tab 8
   - Mau lihat tren? → Tab 9
   - Mau hitung profit? → Tab 7 (isi asumsi biaya)
6. **Export** ke Excel untuk dilaporkan

---

## 7. TIPS & TROUBLESHOOTING

### TIPS
- 🎯 Mulai dengan Tab 1 untuk lihat "big picture" sebelum drill-down
- 🎯 Saat explore periode baru, ubah date preset di form utama dulu lalu klik Analisa ulang
- 🎯 Untuk perbandingan, **pakai preset dulu** — biasanya lebih cepat & akurat
- 🎯 Simpan beberapa export berbeda: 1 untuk summary, 1 untuk per-lokasi, dst

### FAQ

**Q: File `.xls` (bukan `.xlsx`) bisa?**
A: Bisa, tool support keduanya.

**Q: File saya 100rb baris, lambat?**
A: 16rb baris ≈ < 5 detik. 100rb ≈ 30 detik. Sabar menunggu status bar.

**Q: Hasil GUI beda dengan CLI?**
A: Sama persis, GUI hanya untuk lihat.

**Q: Bisa filter manual 1 tanggal tertentu saja?**
A: Set preset ke "Custom", isi `Dari` dan `Sampai` dengan tanggal yang sama.

**Q: Kenapa ada lokasi yang BUNDLE_TX_PCT = 0%?**
A: Bisa karena (a) memang tidak ada program bundle di sana, atau (b) data diskon tidak konsisten. Investigasi manual.

**Q: Kenapa margin tampak 99%?**
A: Karena `PRC_HIP` = 100 (placeholder). Isi asumsi biaya di Tab 7.

**Q: Bisa batch export (semua tab sekaligus)?**
A: Export di GUI = 1 file berisi beberapa sheet. CLI = otomatis semua.

**Q: Bagaimana kalau saya mau definisi "bundle" diubah?**
A: Default: multi-item + diskon seragam. Bisa custom via `Min item` dan `Min discount` di form utama.

**Q: Output Excel tidak bisa dibuka / corrupt?**
A: Pastikan Excel tidak sedang membuka file output-nya. Close dulu, lalu re-export.

---

## 8. STRUKTUR FILE

```
D:\scr\
├── DBKSTHN_55_2026.xlsx             ← file data asli (2.7 MB)
├── bundle_analyzer.py               ← source code tools (92 KB)
├── PANDUAN.md                       ← dokumentasi ini (16 KB)
├── build.bat                        ← script untuk build .exe
├── BundleAnalyzer.spec              ← PyInstaller spec
├── bundle_analysis_sample.xlsx      ← contoh output analisa
├── dist\
│   └── BundleAnalyzer.exe           ← EXECUTABLE siap distribusi (47 MB)
├── build\                           ← artifact build (boleh dihapus)
└── (hasil export Excel lainnya)     ← file Excel dari analisa
```

**Untuk distribusi ke komputer lain: cukup copy `dist\BundleAnalyzer.exe`** (1 file saja).

---

## 9. RINGKASAN FITUR (Cheat Sheet)

| Kebutuhan | Tab | Keyword |
|---|---|---|
| Lokasi paling bundle | Tab 1 | `BUNDLE_TX_PCT`, `BUNDLE_REVENUE` |
| Pola diskon favorit | Tab 2 | sort by `JUMLAH_TX` |
| Audit per transaksi | Tab 3 | sort by `NOTRAN` |
| Combo terlaris | Tab 4 | baris atas per lokasi |
| Cari item di paket | Tab 5 | ketik di "Cari Paket" |
| Item paling laris di paket | Tab 6 | sort by `JUMLAH_BUNDLE` |
| Item yang cocok di-bundle bareng | Tab 6 | "Cari Pasangan" |
| Profit bundle vs non-bundle | Tab 7 | isi asumsi biaya |
| Bandingkan 2 periode | Tab 8 | pilih preset |
| Grafik tren | Tab 9 | pilih granularitas |
| **Lokasi paling item satuan** | **Tab 10A** | sort by `TOTAL_REVENUE` |
| **Audit transaksi satuan** | **Tab 10B** | sort by `NOTRAN` |
| **Item paling laris satuan** | **Tab 10C** | sort by `TOTAL_QTY` |
| **Pola diskon item satuan** | **Tab 10D** | distribusi per-FLOCCD |
| **Cari item di satuan** | **Tab 10E** | ketik di "Cari Item" |

---

## 10. KRITERIA DETEKSI BUNDLE (SESUAI REQUIREMENT)

```
1 NOTRAN dianggap BUNDLE jika:
  ✓ Jumlah item (NOM) di NOTRAN ≥ MIN_ITEMS (default 2)
  ✓ Semua item di NOTRAN tersebut punya nilai DISCOUNT (%) yang SAMA
  ✓ DISCOUNT ≥ MIN_DISCOUNT (default 0)
```

Bisa disesuaikan via form utama atau CLI flags.

---

## 11. DISTRIBUSI EXECUTABLE

### 11.1 File yang perlu di-copy
Hanya **1 file**: `BundleAnalyzer.exe` (~47 MB)

Sudah termasuk:
- ✅ Python runtime
- ✅ Semua library (pandas, openpyxl, matplotlib, numpy)
- ✅ Dokumentasi (PANDUAN.md) — akses via tombol **❓ Help / Panduan** di GUI
- ✅ Icon (default Python)

**Tidak perlu install apa-apa di komputer tujuan** selama OS-nya **Windows 10/11 64-bit**.

### 11.2 Cara distribusi
1. Copy `BundleAnalyzer.exe` ke flashdisk / cloud / email
2. Di komputer tujuan, double-click file tersebut
3. Selesai — GUI langsung terbuka

### 11.3 Lokasi penempatan
Bebas di mana saja. Rekomendasi:
```
D:\Tools\BundleAnalyzer\        ← taruh .exe di sini
D:\Tools\BundleAnalyzer\data\   ← taruh file data Excel di sini
D:\Tools\BundleAnalyzer\output\ ← hasil export Excel akan default ke sini (jika user Save)
```

### 11.4 Catatan penting

| Hal | Keterangan |
|---|---|
| **First launch lambat** | Butuh 3-10 detik (extract ke temp). Launch berikutnya lebih cepat. |
| **Antivirus warning** | Beberapa AV (Windows Defender, Avast, dll) kadang **false-positive** flag PyInstaller exe. Klik "Allow" / "More info → Run anyway". Ini normal untuk executable PyInstaller. |
| **Tidak butuh Python** | Semua dependency sudah ter-embed. |
| **Cross-platform** | `.exe` ini hanya untuk **Windows**. Untuk Mac/Linux, perlu build di OS masing-masing. |
| **Update** | Setiap ada perubahan kode, rebuild dengan `build.bat`. |
| **File output Excel** | Tanyakan lokasi save saat klik "Export" (bisa di mana saja). |

### 11.5 Build ulang (kalau ada update kode)
```powershell
# Cara 1: double-click build.bat
build.bat

# Cara 2: manual
python -m PyInstaller --onefile --windowed --name "BundleAnalyzer" --add-data "PANDUAN.md;." --clean --noconfirm bundle_analyzer.py
```
Output baru akan menimpa yang lama di `dist\BundleAnalyzer.exe`.

### 11.6 Alternatif: pakai source code langsung (lebih ringan)
Untuk yang punya Python dan mau development:
- File `bundle_analyzer.py` cuma ~60 KB
- Install: `pip install pandas openpyxl matplotlib`
- Run: `python bundle_analyzer.py`

---

## 12. VERSI WEB (STREAMLIT)

### 12.1 Apa bedanya dengan versi desktop?
| Aspek | Desktop `.exe` | Web Streamlit |
|---|---|---|
| Interface | Tkinter (native window) | Browser (HTML + Plotly) |
| Visualisasi | Matplotlib (statis) | **Plotly (interaktif, hover, zoom)** |
| Multi-user | ❌ 1 user | ✅ bisa dibuka dari banyak device di jaringan lokal |
| Akses dari HP | ❌ | ✅ (buka browser HP) |
| Install | Double-click `.exe` | Install Python + library |
| Ukuran file | 47 MB (`.exe`) | Source code ~30 KB |

### 12.2 Cara menjalankan
**Cara paling gampang (Windows):**
1. Double-click **`run_web.bat`**
2. Tunggu ~5 detik (install library pertama kali)
3. Browser otomatis terbuka ke **http://localhost:8501**
4. Upload file Excel di sidebar → analisa

**Cara manual:**
```powershell
python -m pip install -r requirements.txt
streamlit run bundle_analyzer_web.py
```

### 12.3 Struktur file web
```
D:\scr\
├── bundle_analyzer_web.py    ← kode utama web app (Streamlit)
├── bundle_analyzer.py        ← backend analyzer (dipakai ulang)
├── requirements.txt          ← daftar library (streamlit, plotly, dll)
├── run_web.bat               ← shortcut untuk Windows
└── README.md / PANDUAN.md    ← dokumentasi
```

### 12.4 Deployment (biar bisa diakses orang lain via internet)

**Opsi 1: Streamlit Community Cloud (GRATIS, paling gampang)**
1. Push kode ke GitHub repo
2. Buka https://share.streamlit.io
3. Connect repo → otomatis deploy
4. Dapatkan URL publik: `https://[nama-app].streamlit.app`

**Opsi 2: Docker (untuk server sendiri)**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 8501
CMD ["streamlit", "run", "bundle_analyzer_web.py"]
```
Build & run:
```bash
docker build -t bundle-analyzer .
docker run -p 8501:8501 bundle-analyzer
```

**Opsi 3: Jaringan lokal (LAN)**
```powershell
streamlit run bundle_analyzer_web.py --server.address 0.0.0.0 --server.port 8501
```
Orang lain di jaringan yang sama bisa akses via `http://[IP-kamu]:8501`

### 12.5 Catatan penting
- File Excel TIDAK di-upload ke server/cloud (kalau deploy self-hosted) — tetap di komputer user
- Untuk keamanan produksi, tambahkan **autentikasi** (Streamlit punya `st.experimental_user` atau pakai reverse proxy)
- Untuk data besar (>100k baris), Plotly mungkin lambat — gunakan `use_container_width=True` dan pagination

---

## 13. AUTO-FETCH DATA DARI GOOGLE DRIVE

Versi web mendukung **auto-fetch** data dari Google Drive sharing link. Tidak perlu upload manual setiap kali.

### 13.1 Cara kerja
```
File Excel ──upload ke──▶ Google Drive
                              ↓ (share "Anyone with the link")
                         Share link
                              ↓ (paste di app)
                         App auto-fetch data terbaru
```

### 13.2 Setup 1x (5 menit)
1. Buka https://drive.google.com
2. Upload file Excel (`DBKSTHN_*.xlsx`) ke Drive
3. Klik kanan file → **Share** → **General access** → ubah ke **"Anyone with the link"** → pilih **Viewer** → **Done**
4. Klik **Copy link**
5. Di app, buka sidebar → expander **"📡 Auto-fetch dari Google Drive"**
6. Paste link di field **"Data URL"** → klik **"🔄 Refresh dari URL"**
7. App download data otomatis, proses, dan tampil di semua tab

### 13.3 Update data harian
- Update file di Google Drive (overwrite file lama, ID tetap)
- Klik **"🔄 Refresh dari URL"** di app
- Data baru termuat, semua tab re-render

### 13.4 Setup via secrets (untuk Streamlit Cloud)
Agar user tidak perlu paste URL tiap restart, simpan URL di secrets:

Di Streamlit Cloud → Settings → Secrets, tambahkan:
```toml
[data]
url = "https://drive.google.com/file/d/1ABC...XYZ/view?usp=sharing"
```

Sekarang tombol "ℹ️ Lihat info" akan muncul di app, dan URL auto-terisi.

### 13.5 Error & troubleshooting
| Gejala | Penyebab | Solusi |
|---|---|---|
| "Google Drive mengembalikan HTML" | File tidak di-share public | Ubah share ke "Anyone with the link" |
| "Tidak bisa extract file ID" | Format link salah | Gunakan link dari klik "Copy link" di Google Drive |
| "File yang didownload bukan Excel valid" | File rusak / bukan .xlsx | Cek file di Drive, pastikan format benar |
| Download lambat | File sangat besar (>50 MB) | Pertimbangkan split per bulan atau compress |

### 13.6 Fetch via command line (untuk scripting / GitHub Actions)
Gunakan helper script:
```bash
python scripts/fetch_data.py \
  --url "https://drive.google.com/file/d/XXX/view?usp=sharing" \
  --out data.xlsx
```

Atau via env var:
```bash
export DATA_URL="https://drive.google.com/file/d/XXX/view"
export OUTPUT_PATH="data.xlsx"
python scripts/fetch_data.py
```

### 13.7 URL lain (selain Google Drive)
Helper script juga support URL generic (file langsung di-host di server). Contoh:
- Dropbox public link: ubah `?dl=0` jadi `?dl=1`
- S3 / R2 presigned URL
- OneDrive / SharePoint (perlu convert ke direct link dulu)

---

## 14. STRATEGI PENJUALAN (Slow Moving, Dead Stock, Rekomendasi Promosi)

Tab ke-11 di web app (atau di desktop GUI). Membantu identifikasi **item-item yang perlu tindakan** dan **rekomendasi promosi berbasis data** untuk bulan depan.

### 14.1 🐌 Slow Moving Items

Item dengan penjualan rendah atau menurun. 3 view sekaligus:

| View | Logika | Cocok untuk |
|---|---|---|
| **Bottom Percentile** | Bottom X% item by `AVG_QTY/hari` | Identifikasi item paling lambat (default 20%) |
| **Fixed Threshold** | `AVG_QTY/hari < threshold` (default 0.5) | Bisnis dengan threshold kustom |
| **Decline** | QTY paruh-2 vs paruh-1 turun > Y% | Temukan item yang dulu laris, sekarang turun drastis |

**Output per item:** `PLU`, `NAMA_BRG`, `FLOCCD`, `TOTAL_QTY`, `AVG_DAILY_QTY`, `LAST_SALE_DATE`, `DAYS_SINCE_SALE`, `CATEGORY` (Stagnant / Very Slow / Slow).

**Cara baca:**
- `AVG_DAILY_QTY` < 0.05 → **Stagnant** (hampir tidak bergerak)
- `AVG_DAILY_QTY` 0.05-0.2 → **Very Slow**
- `AVG_DAILY_QTY` 0.2-0.5 → **Slow** (perlu perhatian)
- `DAYS_SINCE_SALE` tinggi → kandidat clearance

### 14.2 💀 Dead Stock

Item yang **TIDAK ADA transaksi dalam N hari terakhir**, tapi pernah laku sebelumnya. Kandidat kuat untuk clearance atau discontinue.

**Default: 60 hari** (bisa diatur slider 7-180 hari di web app).

**Output:** `PLU`, `NAMA_BRG`, `FLOCCD`, `URGENCY`, `LAST_SALE_DATE`, `DAYS_SINCE_SALE`, `LIFETIME_QTY`, `LIFETIME_REVENUE`.

**Urgency indicator:**
- 🔴 **Kritis** (> 90 hari) → harus segera clearance
- 🟠 **Tinggi** (60-90 hari) → pertimbangkan diskon besar
- 🟡 **Standar** (sesuai threshold) → monitor

**Cara baca:**
- Sort by `LIFETIME_REVENUE` descending → item yang dulu paling profitable tapi sekarang mati
- Item dengan `LIFETIME_QTY` tinggi + `DAYS_SINCE_SALE` tinggi → **uang yang tertahan** di inventory
- Untuk bisnis fashion/seasonal, threshold 30 hari mungkin lebih tepat. Untuk barang tahan lama, 90 hari.

### 14.3 🎯 Rekomendasi Promosi (4 Strategi)

Setiap item direkomendasikan dengan **alasan** dan **saran aksi** konkret. Asumsi biaya default 30% dari harga jual (bisa diubah di UI).

#### 🧹 Strategi 1: Clearance (slow + high margin)
- **Kriteria**: `AVG_QTY/hari ≤ 1.0` AND `margin ≥ 30%`
- **Alasan**: "Margin tinggi (30%+) tapi lambat laku"
- **Saran aksi**:
  - Margin ≥ 50% → **Diskon 15-20%** atau bundle dengan best-seller
  - Margin 35-50% → **Diskon 10-15%** atau bundle
  - Margin 30-35% → **Bundle** dengan item fast-moving
- **Tujuan**: Pulihkan cash flow dari inventory yang tidak bergerak

#### 🚀 Strategi 2: Momentum (trending up)
- **Kriteria**: QTY paruh-2 vs paruh-1 naik ≥ 50%
- **Alasan**: "QTY naik 50%+ di paruh kedua periode"
- **Saran aksi**: **Pertahankan momentum, tambah stok, featured display**
- **Tujuan**: Capitalize momentum, jangan sampai kehabisan stok

#### 🛒 Strategi 3: Cross-sell (market basket)
- **Kriteria**: Item yang paling sering muncul dalam NOTRAN yang sama dengan top best-sellers
- **Alasan**: "Sering dibeli bersama best-seller dalam 1 transaksi"
- **Saran aksi**: **Bundle/diskon combo: A + B**
- **Tujuan**: Naikkan AOV (Average Order Value) dengan cross-sell
- **Cara baca**: Lihat `CO_OCCURRENCE` (jumlah transaksi di mana A dan B dibeli bareng). Semakin tinggi, semakin kuat afiliasi.

#### 📅 Strategi 4: Musiman (seasonal)
- **Kriteria**: Item dengan pola peak/off months yang jelas dalam 6 bulan terakhir
- **Alasan**: "Pola musiman: peak di [bulan]"
- **Saran aksi**: "Stok lebih banyak di [bulan peak], promo ringan 1-2 minggu sebelum"
- **Catatan**: Untuk prediksi tahun depan, perlu data historis 1+ tahun. Saat ini pakai pola intra-tahun dari 6 bulan terakhir sebagai proxy.

### 14.4 Workflow yang direkomendasikan

```
[1] Buka tab "Strategi Penjualan"
        ↓
[2] Cek "Slow Moving" → identifikasi item lambat
        ↓
[3] Cek "Dead Stock" → identifikasi item mati
        ↓
[4] Buka "Rekomendasi Promosi" → dapat 4 list siap-eksekusi:
    - Clearance  → diskon bulan ini
    - Momentum   → restock / featured
    - Cross-sell → bundle promo
    - Musiman    → planning bulan depan
        ↓
[5] Download semua strategi dalam 1 file Excel (4 sheet)
        ↓
[6] Share ke tim merchandising / sales
```

### 14.5 Limitasi & catatan

- **Data cost**: Margin dihitung dengan asumsi biaya (default 30% dari harga jual). Jika Anda punya data `PRC_HIP` yang valid, method `margin_analysis()` existing sudah handle itu.
- **Pola musiman**: Untuk prediksi bulan depan yang akurat, idealnya ada data historis 1 tahun. Dengan data 6 bulan, hanya bisa deteksi pola paruh-tahun.
- **Item bundle vs satuan**: Semua analisa strategi hanya untuk **item satuan (non-bundle)**. Untuk bundle, sudah ada di tab bundle existing.
- **Threshold default**: 60 hari untuk dead stock, 30% margin minimum untuk clearance, 50% kenaikan untuk momentum. Semua bisa diubah di UI.

### 14.6 Penggunaan via Python (untuk scripting)

```python
from bundle_analyzer import BundleAnalyzer

a = BundleAnalyzer()
a.load("data.xlsx")
a.classify(min_items=2)

# Slow moving
sm = a.slow_moving_items(view="all", bottom_pct=20, fixed_threshold=0.5)
print(sm["bottom_pct"].head(10))

# Dead stock
ds = a.dead_stock_items(days=60)
print(ds.head(10))

# Promo recs
pr = a.promo_recommendations(cost_pct_assumption=30.0)
for strat in ["clearance", "momentum", "basket", "seasonal"]:
    print(f"\n=== {strat} ===")
    print(pr[strat].head(5))
```

---

---

## 15. MULTI-YEAR ANALYZER (YoY, Seasonal, Forecast)

Tools analisa multi-tahun untuk data DBKSTHN. File terpisah: `bundle_analyzer_multi.py`. Halaman Streamlit: `pages/2_YoY_Forecast.py` (muncul di sidebar setelah deploy).

### 15.1 Cara pakai di web

1. Buka sidebar → klik **"YoY & Forecast"**
2. Set **"Jumlah tahun"** sesuai data yang dimiliki (2-4 tahun)
3. Upload file Excel per tahun (atau biarkan default dari `D:\scr`)
4. Klik **"🚀 Proses Multi-Tahun"**
5. Explore **9 tab** analisa (lihat 15.3)

### 15.2 Cara pakai Python

```python
from bundle_analyzer_multi import MultiYearAnalyzer

# N tahun (2023 s.d. 2026)
m = MultiYearAnalyzer()
m.load_years({
    2023: "DBKSTHN_55_2023.xlsx",
    2024: "DBKSTHN_55_2024.xlsx",
    2025: "DBKSTHN_55_2025.xlsx",
    2026: "DBKSTHN_55_2026.xlsx",
})

# Export semua analisa ke 1 Excel (17 sheets)
m.export_excel("multi_year_analysis.xlsx")
```

Backward compat: `m.load_multi("2025.xlsx", "2026.xlsx")` masih jalan.

### 15.3 Semua Tab (9 tab)

| # | Tab | Metode | Fungsi |
|---|---|---|---|
| 1 | 📋 Ringkasan YoY | `yoy_summary()` | Side-by-side semua tahun (Jan–May) + Growth % |
| 2 | 📍 YoY per Lokasi | `yoy_by_location()` | Growth per FLOCCD untuk semua tahun |
| 3 | 📈 Seasonal | `seasonal_monthly()` | Seasonal Index rata-rata multi-tahun |
| 4 | 🔮 Forecast | `forecast_aggregate()` | Linear Regression per lokasi, prediksi 6 bln |
| 5 | 💾 Export | `export_excel()` | Download 17-sheet Excel |
| 6 | 🔥 Pareto & Heatmap | `pareto_analysis()`, `calendar_heatmap()` | 80/20 PLU + heatmap revenue harian |
| 7 | 📈 Trend | `cumulative_yoy()`, `moving_average()` | Revenue kumulatif + MA 3/6 bln |
| 8 | 📅 Pattern | `weekday_pattern()`, `bundle_comparison()` | Weekday analysis + bundle vs non-bundle |
| 9 | ⚠️ Anomaly & Price | `daily_anomalies()`, `price_qty_correlation()` | Z-score outlier + diskon vs QTY |

### 15.4 Revenue NETT (JUMLAH)

Semua revenue di Multi-Year Analyzer menggunakan **NETT** (`JUMLAH`), yaitu `JUALAHIR × QTY − RPDISCOUNT`. JUMLAH sudah merupakan **total net per baris** (bukan per-unit).

| Kolom | Rumus | Keterangan |
|---|---|---|
| `LINE_NETT` | `JUMLAH` | Revenue NETT per baris (sudah termasuk QTY) |
| `LINE_REVENUE` | `JUALAHIR × QTY` | Revenue GROSS (RSP) |
| `RPDISCOUNT` | `JUALAHIR×QTY × DISCOUNT%/100` | Total diskon dalam rupiah |
| `DISCOUNT` | (persen) | Diskon dalam persen, bukan rupiah |

Konsistensi: `LINE_NETT = LINE_REVENUE − RPDISCOUNT`

### 15.5 YoY Summary

Membandingkan metrik **Januari–Mei** untuk setiap tahun yang tersedia. Growth dihitung untuk setiap pasangan tahun berurutan.

| Metrik | Rumus |
|---|---|
| Revenue (NETT) | `SUM(JUMLAH)` |
| Revenue RSP (GROSS) | `SUM(JUALAHIR × QTY)` |
| Discount (Rp) | `SUM(RPDISCOUNT)` |
| Discount % | `SUM(RPDISCOUNT) / SUM(JUALAHIR×QTY) × 100` |
| Jumlah Transaksi | `NOTRAN.nunique()` |
| Bundle % | `Bundle_TX / Total_TX × 100` |
| Rata-rata Item per TX | `mean(count(NOM) per NOTRAN)` |
| Growth % | `(tahun_ini − tahun_lalu) / tahun_lalu × 100` |

### 15.6 Seasonal Pattern (Multi-Year Average)

Tidak seperti versi sebelumnya yang cuma pakai 2025, sekarang **seasonal index = rata-rata dari SEMUA tahun**. Misal 4 tahun data → seasonal index bulan Jan = rata-rata revenue Jan 2023, 2024, 2025, 2026.

```
Seasonal Index = Revenue(bulan) / Rata-rata Revenue (12 bulan)
```

- Index > 1.0 = peak season
- Index < 1.0 = off-peak

### 15.7 Forecast (Linear Regression)

Menggantikan metode ratio sederhana dengan **Linear Regression** (scikit-learn). Untuk setiap lokasi:

- Input: semua bulan dari semua tahun yang tersedia
- Model: garis lurus `Revenue = a + b × Period`
- Output: prediksi 6 bulan ke depan + Prev Year Actual

### 15.8 File output Excel

Export menghasilkan 17 sheets:
`SUMMARY`, `YOY_SUMMARY`, `YOY_BY_LOCATION`, `YOY_TOP_ITEMS`, `SEASONAL`, `SEASONAL_TOP_VARIANCE`, `FORECAST`, `ALL_MONTHLY`, `ALL_MONTHLY_LOC`, `HEATMAP`, `PARETO`, `CUMULATIVE_YOY`, `WEEKDAY`, `MOVING_AVG`, `ANOMALIES`, `PRICE_QTY`, `BUNDLE_COMPARE`.

---

## 16. STOCK & SALES ANALYZER (Multi-Brand)

Tools terpisah untuk menganalisa file **`stock & sales all (4).xlsx`**. File ini punya format berbeda dari DBKSTHN (2 sheet: Penjualan + DBS). File terpisah: `stock_sales_analyzer.py`. Halaman Streamlit: `pages/1_Stock_Sales_Analyzer.py`.

> ⚠️ **TIDAK bisa digabung dengan analyzer utama** (format file beda). Tools ini stand-alone.

### 16.1 Fitur (10 method)

| Method | Fungsi |
|---|---|
| `stock_coverage()` | Cakupan stok per lokasi: days of supply, stockout risk |
| `stockout_risk()` | Deteksi item dengan stok rendah vs rata-rata penjualan |
| `margin_with_real_cost()` | Margin real dari data COST di sheet DBS |
| `dead_stock_per_location()` | Dead stock per lokasi × SPV × Brand |
| `cross_brand_analysis()` | Cross-brand bundle (INTEX + RBO + HERO KIDS) |
| `reorder_recommendations()` | Item yang perlu re-stock |
| `discount_audit()` | Audit diskon tidak wajar |
| `stock_anomalies()` | Anomali stok (negatif, cost negatif, dll) |
| `export_excel()` | Export 16-sheet Excel |

### 16.2 Data

| Sheet | Baris | Kolom | Brand |
|---|---|---|---|
| Penjualan | 18.438 | 20 | INTEX (99,5%), RBO, HERO KIDS |
| DBS (Stock) | 11.875 | 43 | INTEX, RBO, HERO KIDS |

- **59 lokasi** sales, **123 lokasi** stock
- **477 PLU** (sales), **750 PLU** (stock)
- Revenue gross: Rp 210 M (`SELL × QTY`)
- Cost real: COST mean Rp 168K, RSP mean Rp 797K

### 16.3 Cara pakai

```python
from stock_sales_analyzer import StockSalesAnalyzer
s = StockSalesAnalyzer()
s.load("stock & sales all (4).xlsx")
s.export_excel("stock_sales_analysis.xlsx")  # 16 sheets
```

---

## 17. MACHINE LEARNING (Demo)

Dua model ML sederhana untuk pembelajaran. Ada di tab ke-10 YoY & Forecast (`main_ml` → `pages/2_YoY_Forecast.py`).

### 17.1 K-Means Clustering

**Unsupervised learning**: algoritma mencari pola tersembunyi dalam data tanpa diberi tahu jawabannya.

**Cara kerja:**
1. Pilih fitur: `Total_QTY`, `Total_Revenue`, `Avg_Discount`, `Months_Active`
2. StandardScaler → normalisasi (semua fitur punya skala sama)
3. KMeans `n_clusters=4` → bagi PLU ke 4 kelompok berdasarkan kemiripan
4. Setiap PLU dapat label cluster (0-3)

**Hasil pada data (2025, 599 PLU):**

| Cluster | Label | Jumlah PLU | Karakteristik |
|---|---|---|---|
| 0 | Fast Moving | ~231 | QTY tinggi, aktif >6 bulan |
| 1 | Medium | ~199 | QTY sedang |
| 2 | High Diskon | ~159 | Diskon rata-rata tinggi |
| 3 | Slow Moving | ~10 | QTY rendah, aktif ≤3 bulan |

### 17.2 Linear Regression

**Supervised learning**: model belajar dari data historis untuk memprediksi masa depan.

**Cara kerja:**
1. Input: revenue bulanan dari semua tahun (Period = 0, 1, 2, ...)
2. Target: Revenue per bulan
3. Model: `Revenue = a + b × Period` (garis lurus)
4. Slope (b) = perubahan revenue per bulan (positif = naik, negatif = turun)
5. Prediksi: lanjutkan garis untuk 6 bulan ke depan

**Output di UI:**
- Metric **Slope**: Rp X/bln (naik/turun)
- Chart: actual revenue + trend line + prediksi 6 bulan
- Intersep + koefisien: bisa dilihat dari slope

### 17.3 Supervised vs Unsupervised

| Aspek | Supervised (Regression) | Unsupervised (Clustering) |
|---|---|---|
| Butuh label? | ✅ (target = Revenue) | ❌ (tidak ada label) |
| Tujuan | Prediksi angka | Kelompokkan data mirip |
| Contoh | Linear Regression | K-Means |
| Di app | Tren + forecast | Segmentasi PLU |

---

## 18. ADVANCED ANALYTICS (Detail)

### 18.1 Pareto 80/20

**Method:** `pareto_analysis(year, top_n=50)`

Sortir PLU by revenue descending → hitung persen kumulatif → tandai PLU yang masuk 80% revenue.

**Cara baca:**
- `Cumulative_Pct` = akumulasi revenue share
- `Is_Top80` = True jika cumulative ≤ 80%
- Contoh: dari 50 PLU teratas, mungkin hanya 10-15 yang menyumbang 80% revenue

### 18.2 Calendar Heatmap

**Method:** `calendar_heatmap(year)`

Visualisasi grid: baris = minggu ke-, kolom = hari (Senin-Minggu), warna = revenue.

### 18.3 Cumulative YoY

**Method:** `cumulative_yoy()`

Revenue kumulatif harian untuk semua tahun (Jan–May). Bandingkan pace penjualan: apakah tahun ini lebih cepat mencapai revenue tertentu?

### 18.4 Weekday Pattern

**Method:** `weekday_pattern(year)`

Revenue per hari dalam seminggu. Membantu scheduling: hari apa penjualan tertinggi → staf dan stok lebih banyak.

### 18.5 Moving Average

**Method:** `moving_average()`

3-bulan dan 6-bulan rata-rata bergerak. Menghaluskan noise bulanan untuk melihat tren jangka panjang.

### 18.6 Daily Anomalies

**Method:** `daily_anomalies(year, z_thresh=2.5)`

Z-score outlier detection: `Z = (revenue_hari − mean) / std`. Hari dengan `|Z| > 2.5` = anomali (penjualan jauh di atas/bawah normal).

### 18.7 Price vs QTY Correlation

**Method:** `price_qty_correlation(year, min_qty=5)`

Scatter plot: sumbu X = rata-rata diskon (%), sumbu Y = total QTY. Besar titik = revenue. Apakah diskon tinggi bikin item laku lebih banyak?

### 18.8 Bundle Comparison

**Method:** `bundle_comparison()`

Perbandingan bundle vs non-bundle untuk setiap tahun: Revenue, QTY, TX, Avg Discount, Item per TX.

---

## 19. STOCK CARD (Kartu Stok Bulanan)

Analisa stok per PLU per lokasi per bulan dengan rumus:
```
StokAkhir = StokAwal + IN(EX+TR) - OUT(KR+BS+UP) - Terjual(DBKS.QTY)
```

**Sumber data (3 file):**
1. **Stok Awal** — file seperti `stok awal januari 2026.xlsx` (kolom: `lokasi, namalokasi, plu, nama_brg, qt_awal`)
2. **DBU** — file mutasi seperti `DBUTHN_55_2026.xlsx` (kolom: `LOKASI, PLU, JN, QTY, TGL, ...`)
   - `EX/TR` = barang masuk (stok +)
   - `KR/BS/UP` = barang keluar (stok -)
3. **DBKS** — file penjualan seperti `DBKSTHN_55_2026.xlsx` (kolom: `FLOCCD, PLU, QTY, FDATE, ...`)

**Klasifikasi stok:**
| STOK_AKHIR | STATUS |
|---|---|
| < 0 | ⚠️ NEGATIF |
| = 0 | 🔴 HABIS |
| 1-2 | 🟠 KRITIS |
| 3-5 | 🟡 MENIPIS |
| > 5 | ✅ NORMAL |

**Alerts:**
- **Stok Negatif** — perlu transfer dari lokasi lain
- **Stok Menipis** — perlu reorder (threshold diatur di UI)
- **Dead Stock** — stok > 0 tapi 0 penjualan di N bulan terakhir

**Cara pakai CLI:**
```powershell
python stock_card.py --sa "stok awal januari 2026.xlsx" --dbu "DBUTHN_55_2026.xlsx" --dbks "DBKSTHN_55_2026.xlsx" -o hasil.xlsx
```

**Cara pakai Web:**
1. Buka Streamlit → "Stock Card" di sidebar
2. Upload 3 file
3. Klik "Proses Kartu Stok"

**File:** `stock_card.py`, `pages\3_Stock_Card.py`

---

## 20. FILE STRUCTURE (Lengkap)

```
D:\scr\
├── bundle_analyzer.py              ← Main analyzer class (28 method) — TIDAK disentuh
├── bundle_analyzer_web.py          ← Streamlit web app (11 tab utama) — TIDAK disentuh
├── stock_sales_analyzer.py         ← Stand-alone stock & sales analyzer (BARU, 32 KB)
├── bundle_analyzer_multi.py        ← Multi-year analyzer (N tahun) (BARU, 550+ baris)
├── stock_card.py                   ← Stock card analyzer (BARU)
├── pages/
│   ├── 1_Stock_Sales_Analyzer.py   ← Streamlit page: Stock Sales (BARU)
│   ├── 2_YoY_Forecast.py           ← Streamlit page: Multi-Year 9 tab (BARU)
│   └── 3_Stock_Card.py             ← Streamlit page: Stock Card (BARU)
├── scripts/
│   └── fetch_data.py               ← CLI auto-fetch Google Drive
├── .streamlit/
│   └── config.toml                 ← Theme + server config
├── DBKSTHN_55_2025.xlsx            ← Data 2025 (51.955 rows, 33 FLOCCD) (BARU)
├── DBKSTHN_55_2026.xlsx            ← Data 2026 (16.337 rows, 19 FLOCCD)
├── DBKSTHN_55_2024.xlsx            ← Data 2024 (jika ada)
├── DBKSTHN_55_2023.xlsx            ← Data 2023 (jika ada)
├── DBUTHN_55_2026.xlsx             ← DBU mutasi stok (BARU, 38.656 rows)
├── stok awal januari 2026.xlsx     ← Stok awal per PLU per lokasi (BARU, 4.445 rows)
├── stock & sales all (4).xlsx      ← Multi-brand stock & sales (BARU, 5.6 MB)
├── PANDUAN.md                      ← Dokumentasi ini
├── requirements.txt                ← Dependencies
├── .gitignore
└── run_web.bat                     ← Shortcut Streamlit
```

### Deployed URLs
- **GitHub:** `https://github.com/tonizz/sales-analyzer`
- **Streamlit Cloud:** `https://sales-analyzer-itx.streamlit.app`
- **Streamlit di lokal:** `http://localhost:8501`

### Catatan penting
- `bundle_analyzer.py` dan `bundle_analyzer_web.py` TIDAK BOLEH disentuh (0 diff)
- Semua kode baru di file terpisah (multi-page via `pages/`)
- Setiap halaman baru punya auth duplikasi minimal (~20 baris)
- Untuk problem session cache di Streamlit Cloud: **push saja tidak cukup**, harus **reboot app** (⋮ → Reboot) di https://share.streamlit.io/
- `scikit-learn` ditambahkan ke requirements.txt untuk ML

---

Dokumentasi ini mencakup semua fitur. Jika ada pertanyaan lebih lanjut atau permintaan fitur baru, silakan hubungi saya.
