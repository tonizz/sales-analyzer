"""
notifications.py — Kirim alert KPI & stok ke Telegram / Webhook generik.

Sumber alert diambil dari BundleAnalyzer.kpi_dashboard():
- Ringkasan revenue hari terakhir vs rata-rata
- Item terlaris
- Dead stock & stok menipis

Konfigurasi token/chat disimpan di Streamlit Cloud Secrets (optional):
    [telegram]
    bot_token = "123456:ABC-..."
    chat_id = "-1001234567890"   # atau chat ID grup/channel
Cara pakai (manual):
    from notifications import send_telegram, build_kpi_alert
    send_telegram(token, chat_id, build_kpi_alert(kpi_dict))
"""
from __future__ import annotations

import requests


def _rp(v) -> str:
    try:
        return f"Rp {float(v):,.0f}"
    except Exception:
        return str(v)


def build_kpi_alert(kpi: dict, app_url: str | None = None) -> str:
    """Format dict hasil kpi_dashboard() menjadi pesan teks (kompatibel
    Telegram plain text / webhook JSON)."""
    if not kpi:
        return "(tidak ada data)"
    today = kpi["today"]
    growth = kpi["growth"]
    a7 = kpi["avg_7d"]
    alerts = kpi.get("alerts", {})

    g_y = growth.get("revenue_vs_kemarin")
    g7 = growth.get("revenue_vs_avg7d")

    lines = [
        "📊 SALES ANALYZER — ALERT HARIAN",
        f"📅 Data terakhir: {kpi['latest_date'].date()}",
        "",
        f"💰 Revenue: {_rp(today['revenue'])}"
        + (f" ({g_y:+.1f}% vs kemarin)" if g_y is not None else ""),
        f"🧾 Transaksi: {today['tx']:,}   📦 QTY: {today['qty']:,}",
        f"📈 Avg 7d: {_rp(a7['revenue_per_hari'])}/hari"
        + (f" ({g7:+.1f}% hari ini)" if g7 is not None else ""),
    ]

    top = kpi.get("top_items_today")
    if top is not None and not top.empty:
        lines.append("")
        lines.append("🏆 Top item:")
        for _, r in top.head(5).iterrows():
            lines.append(f"  • {r['NAMA_BRG']} — {int(r['TOTAL_QTY'])} pcs")

    ds = alerts.get("dead_stock_count", 0)
    if ds:
        lines.append("")
        lines.append(f"💀 DEAD STOCK: {ds} item tidak terjual 60 hari")
        ds_top = alerts.get("dead_stock_top")
        if ds_top is not None and not ds_top.empty:
            for _, r in ds_top.head(5).iterrows():
                lines.append(f"  ⏱ {r['DAYS_SINCE_SALE']} hari — {r['NAMA_BRG']}")

    low = alerts.get("low_stock_count")
    if low:
        lines.append("")
        lines.append(f"⚠️ STOK MENIPIS: {low} item ≤ 2 unit")
        low_top = alerts.get("low_stock_top")
        if low_top is not None and not low_top.empty:
            for _, r in low_top.head(5).iterrows():
                nama = r.get("NAMA_BRG", r.get("PLU", ""))
                sisa = r.get("SISA_STOK", "?")
                lines.append(f"  📉 {nama} — sisa {sisa}")

    if app_url:
        lines.append("")
        lines.append(f"🔗 Detail: {app_url}")
    return "\n".join(lines)


def send_telegram(bot_token: str, chat_id: str, text: str, timeout: int = 15) -> dict:
    """Kirim pesan ke Telegram via Bot API. Return dict {ok, description}."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=timeout,
    )
    try:
        data = resp.json()
    except Exception:
        data = {"ok": False, "description": resp.text}
    if resp.status_code != 200 or not data.get("ok"):
        data.setdefault("ok", False)
    return data


def send_webhook(url: str, text: str, timeout: int = 15) -> dict:
    """POST pesan ke webhook generik (Slack incoming webhook / custom endpoint).
    Payload: {"text": ...} — format yang diterima Slack & kebanyakan endpoint."""
    resp = requests.post(url, json={"text": text}, timeout=timeout)
    return {"ok": resp.status_code < 400, "description": f"HTTP {resp.status_code}"}
