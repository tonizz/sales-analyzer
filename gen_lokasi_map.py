import json
import pandas as pd

# Dari stok awal
sa = pd.read_excel(r"D:\scr\stok awal januari 2026.xlsx")
lokasi = sa[['lokasi', 'namalokasi']].drop_duplicates()
lokasi['lokasi'] = lokasi['lokasi'].astype(int).astype(str)
lokasi_map = dict(zip(lokasi['lokasi'], lokasi['namalokasi']))

# Fallback dari DBKSTHN untuk yang tidak ada di stok awal
dbks = pd.read_excel(r"D:\scr\DBKSTHN_55_2026.xlsx")
dbks_lok = dbks[['FLOCCD', 'NAMA']].drop_duplicates()
dbks_lok['FLOCCD'] = dbks_lok['FLOCCD'].astype(int).astype(str)
for _, r in dbks_lok.iterrows():
    kode = r['FLOCCD']
    nama = str(r['NAMA']).strip()
    if kode not in lokasi_map and nama and nama != 'nan':
        lokasi_map[kode] = nama

print(f"Total lokasi: {len(lokasi_map)}")
for k in sorted(lokasi_map.keys()):
    print(f"  {k} -> {lokasi_map[k]}")

# Simpan
with open(r"D:\scr\docs\lokasi_map.json", "w") as f:
    json.dump(lokasi_map, f, indent=2)
print(f"\nSaved to docs/lokasi_map.json")
