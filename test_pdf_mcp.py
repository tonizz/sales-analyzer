"""
Test client untuk MCP PDF Server
Jalankan: python test_pdf_mcp.py
"""
import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    params = StdioServerParameters(command=sys.executable, args=[r"D:\scr\mcp_pdf_server.py"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("=== DAFTAR PDF ===")
            r1 = await session.call_tool("daftar_pdf", {})
            print(r1.content[0].text)
            print("\n=== CARI 'penjualan' DI SEMUA PDF ===")
            r2 = await session.call_tool("cari_di_pdf", {"kata_kunci": "penjualan"})
            print(r2.content[0].text)
            print("\n=== BACA PDF PERTAMA ===")
            pdfs = await session.call_tool("daftar_pdf", {})
            if "Tidak ada PDF" not in pdfs.content[0].text:
                nama = pdfs.content[0].text.split("\n")[1].replace("  - ", "").split(" ")[0]
                r3 = await session.call_tool("baca_pdf", {"nama_file": nama})
                print(r3.content[0].text[:500])
            print("\nSelesai!")


if __name__ == "__main__":
    asyncio.run(main())
