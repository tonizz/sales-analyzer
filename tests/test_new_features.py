"""
Unit tests untuk fitur baru:
- kasir_performance, kasir_discount_anomaly (fraud detection)
- kpi_dashboard
- promo_effectiveness
- notifications.build_kpi_alert
"""
import pandas as pd
import pytest

from bundle_analyzer import REQUIRED_COLS, BundleAnalyzer


def analyzer_from(rows):
    a = BundleAnalyzer()
    a.df = pd.DataFrame(rows, columns=REQUIRED_COLS)
    a.df["FDATE"] = pd.to_datetime(a.df["FDATE"])
    return a


# rows: FLOCCD, FDATE, NOTRAN, NOM, PLU, NAMA, QTY, DISC, JUALAHIR, JUMLAH, PRAM, KASIR
ROWS = [
    # T001: kasir K1, 2 item disc sama 10% -> bundle
    ("55592", "2026-01-10", "T001", 1, "0000100", "Item A", 1, 10.0, 50000, 45000, "PR1", "K1"),
    ("55592", "2026-01-10", "T001", 2, "0000200", "Item B", 1, 10.0, 30000, 27000, "PR1", "K1"),
    # T002: kasir K2, item satuan disc 50% (anomali vs pola K1)
    ("55592", "2026-01-11", "T002", 1, "0000100", "Item A", 2, 50.0, 50000, 100000, "PR2", "K2"),
    # T003: kasir K1 lagi, item satuan tunggal disc 10%
    ("55592", "2026-01-12", "T003", 1, "0000100", "Item A", 1, 10.0, 50000, 50000, "PR1", "K1"),
]


def test_kasir_performance():
    a = analyzer_from(ROWS)
    a.classify()
    kp = a.kasir_performance()
    assert not kp.empty
    assert "TOTAL_REVENUE" in kp.columns
    assert set(kp["KASIR"]) == {"K1", "K2"}
    # total revenue semua baris
    assert kp["TOTAL_REVENUE"].sum() == pytest.approx(45000 + 27000 + 100000 + 50000)


def test_kasir_anomaly_detects_outlier():
    a = analyzer_from(ROWS)
    a.classify()
    an = a.kasir_discount_anomaly(z_thresh=1.0, min_tx=1)
    assert not an.empty
    assert set(an.columns) >= {"FLOCCD", "KASIR", "Z_SCORE", "STATUS"}
    # K2 (disc 50%) harus punya z_score/median disc > K1 (disc 10%)
    k2 = an[an["KASIR"] == "K2"].iloc[0]
    k1 = an[an["KASIR"] == "K1"].iloc[0]
    assert k2["MEDIAN_DISC_KASIR"] > k1["MEDIAN_DISC_KASIR"]


def test_kasir_anomaly_empty_df():
    a = analyzer_from([])
    a.df["IS_BUNDLE"] = pd.Series(dtype=bool)
    an = a.kasir_discount_anomaly()
    assert an.empty


def test_kpi_dashboard():
    a = analyzer_from(ROWS)
    a.classify()
    k = a.kpi_dashboard()
    assert k["latest_date"].date().isoformat() == "2026-01-12"
    assert k["today"]["tx"] == 1          # hanya T003 di hari terakhir
    assert k["today"]["qty"] == 1
    assert "revenue" in k["today"]
    assert "alerts" in k
    assert "top_items_today" in k


def test_kpi_growth_versus_yesterday():
    a = analyzer_from(ROWS)
    a.classify()
    k = a.kpi_dashboard()
    # hari terakhir revenue = 50000; kemarin (T002) = 100000 -> growth negatif
    assert k["growth"]["revenue_vs_kemarin"] == pytest.approx(-50.0)


def test_promo_effectiveness_lift():
    # Item A dijual disc 10% (normal) lalu disc 50% (promo) hari lain dgn qty lebih
    rows = [
        ("55592", "2026-01-01", "T1", 1, "0000100", "Item A", 1, 10.0, 50000, 50000, "P", "K"),
        ("55592", "2026-01-02", "T2", 1, "0000100", "Item A", 1, 10.0, 50000, 50000, "P", "K"),
        ("55592", "2026-01-03", "T3", 1, "0000100", "Item A", 5, 50.0, 50000, 250000, "P", "K"),
    ]
    a = analyzer_from(rows)
    a.classify()
    pe = a.promo_effectiveness(disc_threshold=20.0, min_rows=1)
    assert len(pe) == 1
    row = pe.iloc[0]
    # qty/hari promo (5) > qty/hari normal (1) -> lift positif -> Efektif
    assert row["QTY_LIFT_PCT"] > 0
    assert row["VERDICT"] == "🟢 Efektif"


def test_promo_effectiveness_empty():
    a = analyzer_from([])
    a.df["IS_BUNDLE"] = pd.Series(dtype=bool)
    pe = a.promo_effectiveness()
    assert pe.empty


# ---------- notifications ----------
def test_build_kpi_alert_format():
    from notifications import build_kpi_alert

    kpi = {
        "latest_date": pd.Timestamp("2026-01-12"),
        "today": {"revenue": 50000.0, "tx": 1, "qty": 1, "avg_disc_single": 10.0},
        "yesterday": {"revenue": 100000.0, "tx": 1, "qty": 2, "avg_disc_single": 50.0},
        "avg_7d": {"revenue_per_hari": 50000.0, "tx_per_hari": 1.0, "n_hari": 7},
        "avg_30d": {"revenue_per_hari": 40000.0, "tx_per_hari": 1.0, "n_hari": 30},
        "growth": {"revenue_vs_kemarin": -32.0, "revenue_vs_avg7d": 36.0,
                   "revenue_vs_avg30d": 70.0, "tx_vs_kemarin": 0.0},
        "top_items_today": pd.DataFrame([
            {"PLU": 1, "NAMA_BRG": "Item A", "TOTAL_QTY": 1, "TOTAL_REVENUE": 50000, "JUMLAH_TX": 1},
        ]),
        "alerts": {"dead_stock_count": 0},
    }
    msg = build_kpi_alert(kpi)
    assert "ALERT HARIAN" in msg
    assert "Rp 50,000" in msg
    assert "Item A" in msg


def test_build_kpi_alert_empty():
    from notifications import build_kpi_alert
    assert build_kpi_alert({}) == "(tidak ada data)"
