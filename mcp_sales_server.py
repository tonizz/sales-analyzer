"""
MCP Server — Sales Analyzer
============================
Tool untuk query data penjualan langsung dari file DBKSTHN.
Jalankan: python mcp_sales_server.py
Client bisa panggil tool: ringkasan_lokasi, basket_analysis, cari_produk, dll.
"""
import asyncio
import os

import pandas as pd
from mcp.server.lowlevel import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import ServerCapabilities, TextContent, Tool

DATA_FILE = r"D:\scr\DBKSTHN_55_2026.xlsx"
df: pd.DataFrame | None = None


def _load():
    global df
    if df is None and os.path.exists(DATA_FILE):
        df = pd.read_excel(DATA_FILE)
        df["FDATE"] = pd.to_datetime(df["FDATE"])
        # hitung LINE_REVENUE
        df["LINE_REVENUE"] = df["JUMLAH"]
        # deteksi bundle sederhana
        grp = df.groupby(["FLOCCD", "NOTRAN"])
        n_items = grp["NOM"].transform("count")
        disc_min = grp["DISCOUNT"].transform("min")
        disc_max = grp["DISCOUNT"].transform("max")
        df["IS_BUNDLE"] = (n_items >= 2) & ((disc_max - disc_min) <= 1.0)
        return True
    return df is not None


server = Server("sales-analyzer")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="ringkasan_lokasi",
            description="Ringkasan penjualan per lokasi",
            inputSchema={
                "type": "object",
                "properties": {
                    "lokasi": {"type": "string", "description": "Filter kode lokasi (opsional)"},
                },
            },
        ),
        Tool(
            name="basket_analysis",
            description="Analisis basket (distribusi nilai transaksi)",
            inputSchema={
                "type": "object",
                "properties": {
                    "bulan": {"type": "integer", "description": "Filter bulan 1-12 (opsional)"},
                    "lokasi": {"type": "string", "description": "Filter kode lokasi (opsional)"},
                },
            },
        ),
        Tool(
            name="cari_produk",
            description="Cari produk berdasarkan nama",
            inputSchema={
                "type": "object",
                "properties": {
                    "kata_kunci": {"type": "string", "description": "Kata kunci pencarian"},
                },
                "required": ["kata_kunci"],
            },
        ),
        Tool(
            name="top_bundle",
            description="Top kombinasi bundle terlaris",
            inputSchema={
                "type": "object",
                "properties": {
                    "top_n": {"type": "integer", "description": "Jumlah top (default 10)"},
                },
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    if not _load():
        return [TextContent(type="text", text="Data tidak ditemukan.")]

    if name == "ringkasan_lokasi":
        data = df.groupby("FLOCCD").agg(
            TOTAL_TX=("NOTRAN", "nunique"),
            TOTAL_REVENUE=("LINE_REVENUE", "sum"),
            TOTAL_QTY=("QTY", "sum"),
        ).reset_index().sort_values("TOTAL_REVENUE", ascending=False)
        if arguments and arguments.get("lokasi"):
            data = data[data["FLOCCD"].astype(str) == str(arguments["lokasi"])]
        out = data.to_string(index=False)
        return [TextContent(type="text", text=out)]

    elif name == "basket_analysis":
        d = df.copy()
        bulan = arguments.get("bulan") if arguments else None
        lokasi = arguments.get("lokasi") if arguments else None
        if bulan:
            d = d[d["FDATE"].dt.month == int(bulan)]
        if lokasi:
            d = d[d["FLOCCD"].astype(str) == str(lokasi)]
        tx = d.groupby(["FLOCCD", "NOTRAN"])["LINE_REVENUE"].sum().reset_index(name="TOTAL")
        bins = [0, 50000, 100000, 200000, 300000, 500000, 1000000, float("inf")]
        labels = ["<50rb", "50-99rb", "100-199rb", "200-299rb", "300-500rb", "500rb-1jt", ">1jt"]
        tx["BASKET"] = pd.cut(tx["TOTAL"], bins=bins, labels=labels, right=True)
        result = tx.groupby("BASKET", observed=True).agg(
            TRANSAKSI=("TOTAL", "count"),
            TOTAL_REVENUE=("TOTAL", "sum"),
        ).reset_index()
        out = result.to_string(index=False)
        return [TextContent(type="text", text=out)]

    elif name == "cari_produk":
        kw = str(arguments["kata_kunci"]).lower()
        hasil = df[df["NAMA_BRG"].str.lower().str.contains(kw, na=False)]
        hasil = hasil.drop_duplicates(subset=["PLU", "NAMA_BRG"])[["PLU", "NAMA_BRG"]]
        if hasil.empty:
            return [TextContent(type="text", text=f"Tidak ditemukan: {kw}")]
        out = hasil.head(20).to_string(index=False)
        return [TextContent(type="text", text=out)]

    elif name == "top_bundle":
        top_n = int(arguments.get("top_n", 10)) if arguments else 10
        b = df[df["IS_BUNDLE"]]
        combo = b.groupby(["FLOCCD", "NOTRAN"]).agg(
            ITEM=("NAMA_BRG", lambda x: " + ".join(sorted(x))),
            REVENUE=("LINE_REVENUE", "sum"),
        ).reset_index()
        top = combo.groupby("ITEM").agg(
            TERJUAL=("REVENUE", "count"),
            TOTAL_REVENUE=("REVENUE", "sum"),
        ).reset_index().sort_values("TERJUAL", ascending=False).head(top_n)
        out = top.to_string(index=False)
        return [TextContent(type="text", text=out)]

    raise ValueError(f"Tool '{name}' tidak dikenal")


async def main():
    _load()
    options = InitializationOptions(
        server_name="sales-analyzer",
        server_version="1.0.0",
        capabilities=ServerCapabilities(tools={}),
    )
    async with stdio_server() as (read, write):
        await server.run(read, write, options)


if __name__ == "__main__":
    asyncio.run(main())
