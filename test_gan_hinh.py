"""Kiểm thử nhanh logic gắn hình (không cần PDF/Sheet). Chạy: python test_gan_hinh.py
Mỗi lần sửa quet_bu_hinh_anh.py hãy chạy lại để chắc không tái phát lỗi gắn sai / gắn dư."""
import quet_bu_hinh_anh as q

PAGES = [{"w": 600, "h": 800, "ncol": 1, "mid": 300}]
NEO = [{"id": 0, "so": 1, "page": 0, "col": 0, "bbox": (50, 100, 120, 112), "phan": 1},
       {"id": 1, "so": 2, "page": 0, "col": 0, "bbox": (50, 400, 120, 412), "phan": 1}]
DONG = [{"page": 0, "col": 0, "bbox": (50, 100, 300, 112), "text": "Câu 1. Cho đồ thị"},
        {"page": 0, "col": 0, "bbox": (50, 300, 300, 312), "text": "Hướng dẫn giải"},
        {"page": 0, "col": 0, "bbox": (50, 400, 300, 412), "text": "Câu 2. Mạch điện"}]


def H(b):
    return {"page": 0, "col": 0, "bbox": b, "raster": True, "ids": [], "xrefs": []}


def chay(hinh):
    r = q.gan_hinh_cho_cau(PAGES, DONG, NEO, hinh)
    return {k: len(v["hinh"]) for k, v in r.items()}, r


def test_manh_vun_lot_trong_hinh_lon():
    n, _ = chay([H((60, 150, 260, 260)), H((70, 160, 120, 200))])
    assert n[0] == 1


def test_hinh_loi_giai_khong_gan_vao_de():
    n, _ = chay([H((60, 150, 260, 260)), H((60, 320, 260, 380))])
    assert n[0] == 1


def test_hinh_qua_nho_bi_bo():
    n, _ = chay([H((60, 420, 70, 425))])
    assert n[1] == 0


def test_nhieu_hinh_bi_co_nhieu():
    _, r = chay([H((60 + 100 * i, 430, 150 + 100 * i, 470)) for i in range(4)])
    assert r[1].get("nhieu") is True


def test_so_hinh_toi_da_theo_loi_van():
    assert q.so_hinh_toi_da("Cho mạch") == 3
    assert q.so_hinh_toi_da("Hình nào sau đây đúng?") == 4
    assert q.so_hinh_toi_da("Hình 1, Hình 2, Hình 3, Hình 4, Hình 5") == 5


def test_hinh_sat_cau_sau_ha_muc():
    # hình ngay trên 'Câu 2' (cách 4pt) nhưng cách xa chữ của câu 1 => hạ can_xem
    dong = [d for d in DONG if d["text"] != "Hướng dẫn giải"]
    r = q.gan_hinh_cho_cau(PAGES, dong, NEO, [H((60, 330, 260, 396))])
    assert len(r[0]["hinh"]) == 1 and r[0]["muc"] == "can_xem"


if __name__ == "__main__":
    ok = 0
    for ten, f in list(globals().items()):
        if ten.startswith("test_"):
            f()
            ok += 1
            print("✔", ten)
    print(f"Đạt {ok} phép thử.")
