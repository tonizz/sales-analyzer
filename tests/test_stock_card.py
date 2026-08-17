"""
Unit tests untuk StockCard — rumus inti:
    StokAkhir = StokAwal + IN(EX+TR) - OUT(KR+BS+UP) - Terjual
dengan carry-forward antar bulan.
"""
import pandas as pd

from stock_card import StockCard


def build_sc():
    """1 PLU x 1 lokasi x 2 bulan (Jan, Feb)."""
    sc = StockCard()
    sc.sa = pd.DataFrame({
        "lokasi": [55592], "namalokasi": ["TOKO A"],
        "plu": ["0000100"], "nama_brg": ["Item A"], "qt_awal": [10],
    })
    sc.dbu = pd.DataFrame({
        "LOKASI": [55592, 55592],
        "PLU": ["0000100", "0000100"],
        "JN": ["EX", "KR"],
        "QTY": [5, 3],
        "TGL": [20260115, 20260120],
        "NAMA_BRG": ["Item A", "Item A"],
    })
    sc.dbks = pd.DataFrame({
        "FLOCCD": [55592], "PLU": ["0000100"], "QTY": [4],
        "FDATE": pd.to_datetime(["2026-01-25"]),
    })
    sc._standardize()
    sc._months = sc._detect_months()
    sc._build_master()
    return sc


def test_months_detected():
    sc = build_sc()
    assert sc._months == [1]


def test_stok_akhir_rumus_jan():
    sc = build_sc()
    card = sc.get_stock_card()
    jan = card[(card["BULAN"] == 1)].iloc[0]
    # 10 awal + 5 EX - 3 KR - 4 terjual = 8
    assert jan["STOK_AWAL"] == 10
    assert jan["MASUK"] == 5
    assert jan["KELUAR_KR"] == 3
    assert jan["TERJUAL"] == 4
    assert jan["STOK_AKHIR"] == 8
    assert jan["STATUS"] == "NORMAL"


def test_carry_forward_ke_bulan_berikut():
    sc = build_sc()
    sc._months = [1, 2]  # paksa 2 bulan
    sc._build_master()
    card = sc.get_stock_card()
    feb = card[card["BULAN"] == 2].iloc[0]
    # Feb: 8 carry-forward, tanpa mutasi -> 8
    assert feb["STOK_AWAL"] == 8
    assert feb["STOK_AKHIR"] == 8


def test_status_classification():
    c = StockCard._classify_stock
    assert c(-1) == "NEGATIF"
    assert c(0) == "HABIS"
    assert c(1) == "KRITIS"
    assert c(2) == "KRITIS"
    assert c(3) == "MENIPIS"
    assert c(5) == "MENIPIS"
    assert c(6) == "NORMAL"


def test_status_bisa_negatif():
    sc = StockCard()
    sc.sa = pd.DataFrame({
        "lokasi": [55592], "namalokasi": ["TOKO A"],
        "plu": ["0000100"], "nama_brg": ["Item A"], "qt_awal": [2],
    })
    sc.dbu = pd.DataFrame({
        "LOKASI": [], "PLU": [], "JN": [], "QTY": [], "TGL": [],
    })
    sc.dbks = pd.DataFrame({
        "FLOCCD": [55592], "PLU": ["0000100"], "QTY": [5],
        "FDATE": pd.to_datetime(["2026-02-05"]),
    })
    sc._standardize()
    sc._months = [2]
    sc._build_master()
    card = sc.get_stock_card()
    row = card[card["BULAN"] == 2].iloc[0]
    # 2 awal - 5 terjual = -3
    assert row["STOK_AKHIR"] == -3
    assert row["STATUS"] == "NEGATIF"
