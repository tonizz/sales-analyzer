"""
Unit tests untuk logika inti BundleAnalyzer (deteksi bundle) dan StockCard
(rumus kartu stok). Jalan tanpa file Excel/data riil.

Jalankan: python -m pytest tests/ -v
"""
import pandas as pd
import pytest

from bundle_analyzer import REQUIRED_COLS, BundleAnalyzer


# ---------- Fixtures ----------
def make_df(rows):
    """Buat DataFrame dengan kolom wajib POS. rows = list of tuples."""
    return pd.DataFrame(rows, columns=REQUIRED_COLS)


def analyzer_from(rows):
    a = BundleAnalyzer()
    a.df = make_df(rows)
    # load() biasanya parse FDATE -> tiru di sini
    a.df["FDATE"] = pd.to_datetime(a.df["FDATE"])
    return a


# Satu transaksi valid (NOTRAN, NOM, PLU, NAMA, QTY, DISC, JUALAHIR, JUMLAH, PRAM, KASIR)
TX_BUNDLE = [
    ("55592", "2026-01-10", "T001", 1, "0000100", "Item A", 1, 10.0, 50000, 45000, "PR1", "KS1"),
    ("55592", "2026-01-10", "T001", 2, "0000200", "Item B", 1, 10.0, 30000, 27000, "PR1", "KS1"),
]
TX_SINGLE = [
    ("55592", "2026-01-11", "T002", 1, "0000100", "Item A", 2, 0.0, 50000, 100000, "PR2", "KS1"),
]
TX_DISC_BEDA = [
    ("55593", "2026-01-12", "T003", 1, "0000100", "Item A", 1, 10.0, 50000, 45000, "PR1", "KS2"),
    ("55593", "2026-01-12", "T003", 2, "0000200", "Item B", 1, 20.0, 30000, 24000, "PR1", "KS2"),
]


# ---------- Tests: classify ----------
def test_multi_item_same_disc_is_bundle():
    a = analyzer_from(TX_BUNDLE)
    a.classify()
    assert a.df["IS_BUNDLE"].tolist() == [True, True]


def test_single_item_not_bundle():
    a = analyzer_from(TX_SINGLE)
    a.classify()
    assert a.df["IS_BUNDLE"].tolist() == [False]


def test_diff_discount_not_bundle():
    a = analyzer_from(TX_DISC_BEDA)
    a.classify()
    assert a.df["IS_BUNDLE"].tolist() == [False, False]


def test_disc_tolerance_within():
    # Selisih diskon 0.5% <= toleransi default 1.0 -> masih bundle
    rows = [
        ("55592", "2026-01-10", "T001", 1, "0000100", "Item A", 1, 10.0, 50000, 45000, "P", "K"),
        ("55592", "2026-01-10", "T001", 2, "0000200", "Item B", 1, 10.5, 30000, 27000, "P", "K"),
    ]
    a = analyzer_from(rows)
    a.classify()
    assert a.df["IS_BUNDLE"].all()


def test_disc_tolerance_exceeded():
    rows = [
        ("55592", "2026-01-10", "T001", 1, "0000100", "Item A", 1, 10.0, 50000, 45000, "P", "K"),
        ("55592", "2026-01-10", "T001", 2, "0000200", "Item B", 1, 12.0, 30000, 27000, "P", "K"),
    ]
    a = analyzer_from(rows)
    a.classify(disc_tolerance=1.0)
    assert not a.df["IS_BUNDLE"].any()


def test_min_discount_filter():
    a = analyzer_from(TX_BUNDLE + TX_SINGLE)
    a.classify(min_discount=15.0)
    # Bundle T001 punya disc 10% < 15% -> bukan bundle
    assert not a.df[a.df["NOTRAN"] == "T001"]["IS_BUNDLE"].any()


def test_min_items_3():
    a = analyzer_from(TX_BUNDLE)
    a.classify(min_items=3)
    assert not a.df["IS_BUNDLE"].any()


def test_line_revenue_equals_jumlah():
    a = analyzer_from(TX_BUNDLE)
    a.classify()
    assert (a.df["LINE_REVENUE"] == a.df["JUMLAH"]).all()


def test_summary_by_location_bundle_pct():
    a = analyzer_from(TX_BUNDLE + TX_SINGLE + TX_DISC_BEDA)
    a.classify()
    sm = a.summary_by_location()
    row = sm[sm["FLOCCD"] == "55592"].iloc[0]
    assert row["TOTAL_TX"] == 2          # T001 + T002
    assert row["BUNDLE_TX"] == 1         # hanya T001
    assert row["BUNDLE_REVENUE"] == pytest.approx(45000 + 27000)


def test_load_missing_columns_raises(tmp_path):
    df = pd.DataFrame({"A": [1]})
    f = tmp_path / "bad.xlsx"
    df.to_excel(f, index=False)
    a = BundleAnalyzer()
    with pytest.raises(ValueError, match="Kolom wajib"):
        a.load(str(f))


# ---------- Tests: auth._verify ----------
def test_auth_verify_bcrypt():
    import bcrypt
    from auth import _verify
    h = bcrypt.hashpw(b"rahasia123", bcrypt.gensalt()).decode()
    assert _verify("rahasia123", h) is True
    assert _verify("salah", h) is False
    assert _verify("apa saja", "") is False


def test_auth_verify_legacy_plaintext():
    from auth import _verify
    assert _verify("admin123", "admin123") is True
    assert _verify("lainnya", "admin123") is False
