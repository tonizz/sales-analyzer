"""
MCP Server Sederhana — Contoh untuk belajar.
Menyediakan tool untuk membaca file + hitung karakter.
"""
import asyncio

from mcp.server.models import InitializationOptions
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    ServerCapabilities,
    TextContent,
    Tool,
)

server = Server("contoh-server")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="baca_file",
            description="Baca isi file teks",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path file"},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="hitung_kata",
            description="Hitung jumlah kata dalam teks",
            inputSchema={
                "type": "object",
                "properties": {
                    "teks": {"type": "string", "description": "Teks input"},
                },
                "required": ["teks"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[TextContent]:
    if name == "baca_file":
        path = arguments["path"]
        try:
            with open(path, encoding="utf-8") as f:
                isi = f.read()
            return [TextContent(type="text", text=isi)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    elif name == "hitung_kata":
        teks = arguments["teks"]
        jumlah = len(teks.split())
        return [TextContent(type="text", text=f"Jumlah kata: {jumlah}")]

    raise ValueError(f"Tool '{name}' tidak dikenal")


async def main():
    options = InitializationOptions(
        server_name="contoh-server",
        server_version="1.0.0",
        capabilities=ServerCapabilities(tools={}),
    )
    async with stdio_server() as (read, write):
        await server.run(read, write, options)


if __name__ == "__main__":
    asyncio.run(main())
