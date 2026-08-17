"""
Client MCP sederhana untuk test server contoh_mcp_server.py
Jalankan: python test_mcp_client.py
"""
import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    print("Menghubungkan ke MCP server...")
    params = StdioServerParameters(
        command=sys.executable,
        args=[r"D:\scr\contoh_mcp_server.py"],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Terhubung!")
            tools = await session.list_tools()
            print(f"\nTool tersedia ({len(tools.tools)}):")
            for t in tools.tools:
                print(f"  - {t.name}: {t.description}")
            print("\n--- Test hitung_kata ---")
            hasil = await session.call_tool("hitung_kata", {"teks": "Halo dunia apa kabar"})
            print(f"Hasil: {hasil.content[0].text}")
            print("\n--- Test baca_file ---")
            try:
                test_path = __file__
            except NameError:
                test_path = r"D:\scr\test_mcp_client.py"
            hasil2 = await session.call_tool("baca_file", {"path": test_path})
            print(f"Hasil (10 baris pertama):")
            baris = hasil2.content[0].text.split("\n")[:10]
            for b in baris:
                print(f"  {b}")
    print("\nSelesai! Server MCP berfungsi.")


if __name__ == "__main__":
    asyncio.run(main())
