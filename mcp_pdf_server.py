"""
MCP Server — Baca & Cari PDF
=============================
Scan folder, baca PDF, cari teks di dalamnya.
Jalankan: python mcp_pdf_server.py
"""
import asyncio
import os
from pathlib import Path

from pypdf import PdfReader
from mcp.server.lowlevel import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import ServerCapabilities, TextContent, Tool

# ========== KONFIGURASI ==========
FOLDER_IZIN = r"D:\scr"
# =================================

server = Server("pdf-reader")


def _baca_pdf(path: str) -> str:
    reader = PdfReader(path)
    teks = []
    for h in reader.pages:
        t = h.extract_text()
        if t:
            teks.append(t)
    return "\n".join(teks)


def _daftar_pdf() -> list[dict]:
    hasil = []
    for f in Path(FOLDER_IZIN).rglob("*.pdf"):
        hasil.append({"nama": f.name, "path": str(f)})
    return sorted(hasil, key=lambda x: x["nama"])


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="daftar_pdf",
            description="Daftar semua file PDF di folder",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="baca_pdf",
            description="Baca isi teks dari file PDF",
            inputSchema={
                "type": "object",
                "properties": {
                    "nama_file": {"type": "string", "description": "Nama file PDF"},
                },
                "required": ["nama_file"],
            },
        ),
        Tool(
            name="cari_di_pdf",
            description="Cari kata/kalimat di semua PDF dalam folder",
            inputSchema={
                "type": "object",
                "properties": {
                    "kata_kunci": {"type": "string", "description": "Kata yang dicari"},
                },
                "required": ["kata_kunci"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    if name == "daftar_pdf":
        pdfs = _daftar_pdf()
        if not pdfs:
            return [TextContent(type="text", text=f"Tidak ada PDF di {FOLDER_IZIN}")]
        teks = f"Ditemukan {len(pdfs)} file PDF:\n"
        for p in pdfs:
            uk = os.path.getsize(p["path"]) / 1024
            teks += f"  - {p['nama']} ({uk:.0f} KB)\n"
        return [TextContent(type="text", text=teks)]

    elif name == "baca_pdf":
        cocok = [p for p in _daftar_pdf() if p["nama"].lower() == arguments["nama_file"].lower()]
        if not cocok:
            return [TextContent(type="text", text=f"File '{arguments['nama_file']}' tidak ditemukan")]
        isi = _baca_pdf(cocok[0]["path"])
        if len(isi) > 3000:
            isi = isi[:3000] + "\n\n...(dipotong)"
        return [TextContent(type="text", text=isi)]

    elif name == "cari_di_pdf":
        kw = arguments["kata_kunci"].lower()
        hasil = []
        for p in _daftar_pdf():
            isi = _baca_pdf(p["path"]).lower()
            if kw in isi:
                hasil.append(f"  - {p['nama']} ({isi.count(kw)}x ditemukan)")
        if not hasil:
            return [TextContent(type="text", text=f"'{kw}' tidak ditemukan")]
        return [TextContent(type="text", text=f"Ditemukan di {len(hasil)} file:\n" + "\n".join(hasil))]

    raise ValueError(f"Tool '{name}' tidak dikenal")


async def main():
    options = InitializationOptions(
        server_name="pdf-reader",
        server_version="1.0.0",
        capabilities=ServerCapabilities(tools={}),
    )
    async with stdio_server() as (read, write):
        await server.run(read, write, options)


if __name__ == "__main__":
    asyncio.run(main())
