"""
Test client untuk MCP Sales Analyzer server
Jalankan: python test_sales_mcp.py
"""
import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    print("Menghubungkan ke Sales Analyzer MCP server...\n")
    params = StdioServerParameters(
        command=sys.executable,
        args=[r"D:\scr\mcp_sales_server.py"],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"Tool tersedia ({len(tools.tools)}):")
            for t in tools.tools:
                print(f"  - {t.name}: {t.description}")
            print("\n" + "=" * 50)
            # Test 1: Ringkasan lokasi
            print("\n[1] RINGKASAN LOKASI (top 5):")
            r1 = await session.call_tool("ringkasan_lokasi", {})
            baris = r1.content[0].text.split("\n")[:7]
            print("\n".join(baris))
            print("  ...")
            # Test 2: Basket analysis bulan 6
            print("\n[2] BASKET ANALYSIS (Bulan 6):")
            r2 = await session.call_tool("basket_analysis", {"bulan": 6})
            print(r2.content[0].text)
            # Test 3: Cari produk
            print("\n[3] CARI PRODUK 'POOL':")
            r3 = await session.call_tool("cari_produk", {"kata_kunci": "POOL"})
            print(r3.content[0].text)
            # Test 4: Top bundle
            print("\n[4] TOP 5 BUNDLE:")
            r4 = await session.call_tool("top_bundle", {"top_n": 5})
            print(r4.content[0].text)
            print("\n" + "=" * 50)
            print("Selesai! Server MCP Sales Analyzer berfungsi.")


if __name__ == "__main__":
    asyncio.run(main())
