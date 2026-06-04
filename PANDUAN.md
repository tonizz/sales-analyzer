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

Dokumentasi ini mencakup semua fitur. Jika ada pertanyaan lebih lanjut atau permintaan fitur baru, silakan hubungi saya.
