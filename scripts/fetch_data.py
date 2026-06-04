"""Fetch data Excel dari Google Drive (sharing link) atau URL generic.

Usage (CLI):
    python fetch_data.py --url "https://drive.google.com/file/d/XXX/view" --out data.xlsx

Usage (import):
    from fetch_data import fetch_to_file
    fetch_to_file(url, "data.xlsx")

Env vars (untuk GitHub Actions / weekly report):
    DATA_URL     URL data (Google Drive atau generic)
    OUTPUT_PATH  path output (default: data.xlsx)
"""
from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests


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


def fetch_bytes(url: str, timeout: int = 60) -> bytes:
    """Download file dari URL. Support Google Drive sharing link."""
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
            stream=True, timeout=timeout,
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
                    stream=True, timeout=timeout,
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

    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def fetch_to_file(url: str, output_path: str | Path) -> Path:
    """Fetch URL → write ke file. Return Path absolut."""
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = fetch_bytes(url)
    output_path.write_bytes(data)
    return output_path


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Fetch data Excel dari Google Drive / URL.")
    p.add_argument("--url", default=os.environ.get("DATA_URL", ""), help="URL data (atau set env DATA_URL)")
    p.add_argument("--out", default=os.environ.get("OUTPUT_PATH", "data.xlsx"), help="Output path")
    args = p.parse_args()
    if not args.url:
        print("ERROR: --url atau env DATA_URL harus diisi.", file=sys.stderr)
        return 1
    try:
        out = fetch_to_file(args.url, args.out)
        size = out.stat().st_size
        print(f"OK: {out} ({size:,} bytes)")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
