"""
Stock Opname Server — untuk scan barcode via HP + kirim ke HO.

Cara pakai:
  python opname_server.py
  Buka QR code / URL di HP (WiFi yang sama)
  Untuk HTTPS: ngrok http 8000

Toko scan → data otomatis ke server → HO lihat via Streamlit.
"""
from __future__ import annotations

import json
import os
import socket
import sys
from datetime import datetime
from pathlib import Path
from io import BytesIO
import base64

import qrcode
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import pandas as pd

app = FastAPI(title="Stock Opname Server — INTEX")

BASE_DIR = Path(__file__).parent
SCAN_FILE = BASE_DIR / "opname_hasil_server.json"
DBKS_PATH = BASE_DIR / "DBKSTHN_55_2026.xlsx"
BARCODE_XLSX = BASE_DIR / "barcodexls.xlsx"
BARCODE_MAP = BASE_DIR / "barcode_map.json"
NAMA_MAP = BASE_DIR / "nama_map.json"
LOKASI_MAP = BASE_DIR / "docs" / "lokasi_map.json"


def ensure_barcode_map():
    """Generate barcode_map.json dari barcodexls.xlsx jika belum ada."""
    if BARCODE_MAP.exists():
        return
    if not BARCODE_XLSX.exists():
        print("WARNING: barcodexls.xlsx tidak ditemukan. Scanner tidak bisa lookup barcode.")
        return
    print("Generating barcode_map.json from barcodexls.xlsx...")
    import pandas as pd
    bc = pd.read_excel(BARCODE_XLSX)
    bc = bc.dropna(subset=['PLU', 'BARCODE'])
    bc['PLU'] = bc['PLU'].astype(int).astype(str)
    bc['BARCODE'] = bc['BARCODE'].astype(str).str.strip()
    bc = bc.drop_duplicates(subset=['BARCODE'])
    map_data = dict(zip(bc['BARCODE'], bc['PLU']))
    with open(BARCODE_MAP, "w") as f:
        json.dump(map_data, f, indent=2)
    print(f"  {len(map_data)} barcodes mapped -> {BARCODE_MAP.name}")


def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def load_lokasi() -> list[dict]:
    """Load daftar toko dari DBKSTHN."""
    try:
        df = pd.read_excel(DBKS_PATH)
        lokasi = df[['FLOCCD', 'NAMA']].drop_duplicates()
        lokasi.columns = ['kode', 'nama']
        lokasi = lokasi.fillna('')
        return lokasi.to_dict('records')
    except Exception as e:
        print(f"Error loading lokasi: {e}")
        return []


def load_barcode_count() -> int:
    bm = BASE_DIR / "barcode_map.json"
    if bm.exists():
        with open(bm) as f:
            return len(json.load(f))
    return 0


@app.get("/", response_class=HTMLResponse)
def index():
    ip = get_local_ip()
    port = int(os.environ.get("PORT", "8000"))
    url = f"http://{ip}:{port}"
    qr = qrcode.make(url)
    buf = BytesIO()
    qr.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    bc_count = load_barcode_count()
    lokasi_count = len(load_lokasi())

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Opname Server</title>
<style>
body {{ font-family: -apple-system, sans-serif; padding: 20px; max-width: 600px; margin: 0 auto; text-align: center; }}
.card {{ background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin: 12px 0; }}
.btn {{ display: inline-block; padding: 12px 32px; font-size: 18px; background: #4CAF50; color: white; text-decoration: none; border-radius: 8px; }}
img {{ max-width: 250px; }}
.url {{ font-size: 20px; font-weight: bold; margin: 12px 0; }}
.info {{ font-size: 13px; color: #666; text-align: left; margin-top: 8px; }}
</style>
</head>
<body>
<h1>Stock Opname — INTEX</h1>
<div class="card">
  <p>Buka URL di HP untuk scan barcode / input stok:</p>
  <div class="url">{url}</div>
  <p>Atau scan QR:</p>
  <img src="data:image/png;base64,{qr_b64}" alt="QR">
  <br><br>
  <a class="btn" href="/scanner">Buka Scanner</a>
  <div class="info">
    <p>{bc_count:,} barcode terdaftar</p>
    <p>{lokasi_count} toko/lokasi</p>
  </div>
</div>
</body>
</html>"""


@app.get("/scanner", response_class=HTMLResponse)
def scanner():
    path = BASE_DIR / "opname_scanner.html"
    if path.exists():
        return HTMLResponse(path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>File scanner tidak ditemukan</h1>")


@app.get("/api/lokasi")
def api_lokasi():
    return JSONResponse(load_lokasi())


@app.post("/api/save")
def save_to_server(data: dict):
    items = data.get("items", [])
    toko = data.get("toko", "")
    if not items:
        return JSONResponse({"success": False, "error": "No items"})
    
    existing = []
    if SCAN_FILE.exists():
        with open(SCAN_FILE) as f:
            existing = json.load(f).get("items", [])
    
    merged = {}
    for item in existing:
        merged[item["plu"]] = item
    for item in items:
        merged[item["plu"]] = item
    
    result = {
        "exported": datetime.now().isoformat(),
        "toko": toko,
        "items": list(merged.values()),
    }
    with open(SCAN_FILE, "w") as f:
        json.dump(result, f, indent=2)
    return JSONResponse({"success": True, "count": len(merged)})


@app.get("/api/download")
def download_from_server():
    if SCAN_FILE.exists():
        with open(SCAN_FILE) as f:
            return JSONResponse(json.load(f))
    return JSONResponse({"exported": "", "toko": "", "items": []})


@app.get("/api/status")
def api_status():
    bc_count = load_barcode_count()
    lokasi = load_lokasi()
    saved = []
    if SCAN_FILE.exists():
        with open(SCAN_FILE) as f:
            saved = json.load(f).get("items", [])
    return JSONResponse({
        "barcode_count": bc_count,
        "lokasi_count": len(lokasi),
        "saved_item_count": len(saved),
        "lokasi": lokasi,
    })


@app.get("/barcode_map.json")
def serve_barcode_map():
    path = BASE_DIR / "barcode_map.json"
    if path.exists():
        return JSONResponse(json.loads(path.read_text(encoding="utf-8")))
    return JSONResponse({})


@app.get("/nama_map.json")
def serve_nama_map():
    path = BASE_DIR / "nama_map.json"
    if path.exists():
        return JSONResponse(json.loads(path.read_text(encoding="utf-8")))
    return JSONResponse({})


@app.get("/api/lokasi_map")
def serve_lokasi_map():
    path = LOKASI_MAP
    if path.exists():
        return JSONResponse(json.loads(path.read_text(encoding="utf-8")))
    return JSONResponse({})


if __name__ == "__main__":
    ensure_barcode_map()
    if not LOKASI_MAP.exists():
        try:
            import pandas as pd
            sa = pd.read_excel(BASE_DIR / "stok awal januari 2026.xlsx")
            lok = sa[['lokasi', 'namalokasi']].drop_duplicates()
            lok['lokasi'] = lok['lokasi'].astype(int).astype(str)
            lokasi_map = dict(zip(lok['lokasi'], lok['namalokasi']))
            LOKASI_MAP.parent.mkdir(parents=True, exist_ok=True)
            with open(LOKASI_MAP, "w") as f:
                json.dump(lokasi_map, f, indent=2)
            print(f"  Lokasi map: {len(lokasi_map)} locations")
        except Exception as e:
            print(f"  Warning: could not generate lokasi_map: {e}")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    ip = get_local_ip()
    print(f"\n  Server:  http://{ip}:{port}")
    print(f"  Scanner: http://{ip}:{port}/scanner")
    print(f"  Untuk HTTPS (kamera HP): ngrok http {port}\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
