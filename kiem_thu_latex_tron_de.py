"""
kiem_thu_latex_tron_de.py – kiểm thử tự động cho latex_chuan.py và tron_de.py.
Không cần khóa thật, không gọi mạng, không cần thư viện Google.
Sai kết quả mong đợi → thoát mã 1 (GitHub Actions báo đỏ).
Chạy: python kiem_thu_latex_tron_de.py
"""
import copy
import random
import sys
import traceback
import types

# tron_de.py import giao_thuc ở đầu file; nếu không có (hoặc thiếu thư viện Google) thì dùng bản giả rỗng.
try:
    import giao_thuc  # noqa: F401
except Exception:
    sys.modules["giao_thuc"] = types.ModuleType("giao_thuc")

import latex_chuan as L
import tron_de as T

DANH_SACH = []
DA_BIET = []   # lỗi đã biết: chỉ báo, không làm đỏ (hiện chưa có)


def kich_ban(f):
    DANH_SACH.append(f)
    return f


def la_loi_da_biet(f):
    DA_BIET.append(f)
    return f


# ======================= latex_chuan =======================
@kich_ban
def latex_01_so_thap_phan():
    assert L.chuan_hoa_latex("$0.05$") == "$0{,}05$"
    assert L.chuan_hoa_latex("$2,7\\%$") == "$2{,}7\\%$"


@kich_ban
def latex_02_don_vi_bao_text():
    assert L.chuan_hoa_latex("$5 cm$") == "$5\\text{ cm}$"
    assert L.chuan_hoa_latex("$v = 5 m/s$") == "$v = 5\\text{ m/s}$"


@kich_ban
def latex_03_nhan_va_mu_10():
    assert L.chuan_hoa_latex("$1,6.10^{-19}$") == "$1{,}6\\cdot 10^{-19}$"
    assert L.chuan_hoa_latex("$3 × 4$") == "$3\\cdot 4$"
    assert L.chuan_hoa_latex("$10^-3$") == "$10^{-3}$"
    assert L.chuan_hoa_latex("$10⁻¹⁹ m$").startswith("$10^{-19}")


@kich_ban
def latex_04_unicode_sang_latex():
    assert L.chuan_hoa_latex("$α$") == "$\\alpha$"
    assert L.chuan_hoa_latex("$30°$") == "$30^\\circ$"
    assert L.chuan_hoa_latex("$√(2)$") == "$\\sqrt{2}$"
    out = L.chuan_hoa_latex("$μ ≈ π ≤ Δ$")
    assert not any(ord(c) > 127 for c in out), "còn Unicode: %r" % out


@kich_ban
def latex_05_bo_markdown():
    out = L.chuan_hoa_latex("**đậm** và `mã` [cite: 3] xong")
    assert "**" not in out and "`" not in out and "cite" not in out, out
    assert out == "đậm và mã xong", out
    assert L.chuan_hoa_latex("\\textbf{Chú ý} $x$") == "Chú ý $x$"


@kich_ban
def latex_06_dau_phan_cach_cong_thuc():
    assert L.chuan_hoa_latex("\\(a*b\\)") == "$a\\cdot b$"
    assert L.chuan_hoa_latex("\\[x=1\\]") == "$$x=1$$"
    assert L.chuan_hoa_latex("$$ x=1 $$ chữ") == "$$x=1$$\nchữ"


@kich_ban
def latex_07_giu_nguyen_x_sao_va_frac():
    assert L.chuan_hoa_latex("$x^*$") == "$x^*$"
    assert L.chuan_hoa_latex("$\\dfrac{1}{2}$") == "$\\frac{1}{2}$"
    assert L.chuan_hoa_latex("$\\\\alpha$") == "$\\alpha$"   # \\alpha → \alpha


@kich_ban
def latex_08_dau_vao_rong_va_none():
    assert L.chuan_hoa_latex(None) == ""
    assert L.chuan_hoa_latex("") == ""
    assert L.chuan_hoa_toan(None) == ""
    assert L.chuan_hoa_latex("Không có công thức.") == "Không có công thức."


@kich_ban
def latex_09_chay_hai_lan_khong_doi():
    mau = [
        "Một vật $m = 2 kg$ chuyển động $v = 3,5 m/s$ ($g ≈ 9.8 m/s^2$).",
        "**Giải:** \\(F = m·a\\) nên $$ F = 2 × 3 $$ rồi kết luận $1,6.10^{-19} C$.",
        "$\\text{ J}$ và $10⁻³ s$ và $0.05$.",
        "Dòng 1\n\n\n\nDòng 2   nhiều   khoảng trắng\n$$a$$\n$$b$$",
    ]
    for s in mau:
        m1 = L.chuan_hoa_latex(s)
        m2 = L.chuan_hoa_latex(m1)
        assert m1 == m2, "không bền:\n%r\n%r" % (m1, m2)


@kich_ban
def latex_10_khong_con_loi_thuong_gap():
    """Các lỗi hay bị kiểm định báo: còn ** hoặc --- Markdown, còn \\( \\)."""
    s = "**Bài 1** \\(x=1\\)\n\n\n\nHết"
    out = L.chuan_hoa_latex(s)
    for xau in ("**", "\\(", "\\)", "\n\n\n"):
        assert xau not in out, (xau, out)


# ======================= tron_de =======================
def de_mau(n1=5, n2=3, n3=4, n4=1):
    return {
        "phan1": [{"cauHoi": "q%d" % i, "A": "a%d" % i, "B": "b%d" % i, "C": "c%d" % i, "D": "d%d" % i,
                   "dapAn": "ABCD"[i % 4]} for i in range(n1)],
        "phan2": [{"cauHoi": "p2_%d" % i, "A": "A%d" % i, "B": "B%d" % i, "C": "C%d" % i, "D": "D%d" % i,
                   "dapAn": "a) Đ, b) S, c) S, d) Đ"} for i in range(n2)],
        "phan3": [{"cauHoi": "p3_%d" % i, "dapAn": str(i)} for i in range(n3)],
        "phan4": [{"cauHoi": "p4_%d" % i} for i in range(n4)],
    }


@kich_ban
def tron_01_doc_dap_an_p1():
    assert T.doc_dap_an_p1("B") == "B"
    assert T.doc_dap_an_p1("đáp án: c") == "C"
    assert T.doc_dap_an_p1("") == ""
    assert T.doc_dap_an_p1(None) == ""
    assert T.doc_dap_an_p1("123") == ""


@kich_ban
def tron_01b_doc_dap_an_p1_khong_lay_chu_trong_tu():
    """Trước đây 'Chọn B' bị đọc thành 'C' (chữ C của 'Chọn'). Nay chỉ nhận chữ cái đứng riêng."""
    assert T.doc_dap_an_p1("Chọn B") == "B"
    assert T.doc_dap_an_p1("Câu B") == "B"
    assert T.doc_dap_an_p1("Đáp án đúng là d") == "D"
    assert T.doc_dap_an_p1("B.") == "B" and T.doc_dap_an_p1("(C)") == "C" and T.doc_dap_an_p1("A) gia tốc") == "A"
    assert T.doc_dap_an_p1("Cả A và B") == ""       # hai đáp án khác nhau → coi là không đọc được
    assert T.doc_dap_an_p1("A, vì A đúng") == "A"   # lặp cùng một chữ vẫn là một đáp án
    assert T.doc_dap_an_p1("ABCD") == ""            # không có chữ đứng riêng


@kich_ban
def tron_02_doc_dap_an_p2():
    assert T.doc_dap_an_p2("a) Đ, b) S, c) Đ, d) S") == {"a": True, "b": False, "c": True, "d": False}
    assert T.doc_dap_an_p2("a. Đúng; b. Sai; c. Đúng; d. Sai") == {"a": True, "b": False, "c": True, "d": False}
    assert T.doc_dap_an_p2("a) Đ, b) S") == {}            # không đủ 4 ý
    assert T.doc_dap_an_p2("") == {} and T.doc_dap_an_p2(None) == {}


@kich_ban
def tron_03_ghi_dap_an_p2_khop_doc():
    ds = {"a": True, "b": False, "c": False, "d": True}
    assert T.ghi_dap_an_p2(ds) == "a) Đ, b) S, c) S, d) Đ"
    assert T.doc_dap_an_p2(T.ghi_dap_an_p2(ds)) == ds


@kich_ban
def tron_04_doc_cau_hinh_mac_dinh_va_tuy_chon():
    mac_dinh = T.doc_cau_hinh({})
    assert mac_dinh["tronCau"] == {1: True, 2: True, 3: True}
    assert mac_dinh["tronPhuongAn"] is True and mac_dinh["tronYPhan2"] is False
    cfg = T.doc_cau_hinh({"tuyChon": {"tronCau": {"2": False}, "tronPhuongAn": False, "tronYPhan2": True}})
    assert cfg["tronCau"] == {1: True, 2: False, 3: True}
    assert cfg["tronPhuongAn"] is False and cfg["tronYPhan2"] is True


@kich_ban
def tron_05_hoan_vi_hop_le():
    de = de_mau()
    cfg = T.doc_cau_hinh({"tuyChon": {"tronYPhan2": True}})
    for seed in range(50):
        hv, ok = T.tao_bo_hoan_vi(de, cfg, random.Random(seed), set())
        assert ok
        assert sorted(hv["thuTu"][1]) == list(range(5))
        assert sorted(hv["thuTu"][2]) == list(range(3))
        assert sorted(hv["thuTu"][3]) == list(range(4))
        assert all(sorted(v) == [0, 1, 2, 3] for v in hv["pa"].values())
        assert all(sorted(v) == [0, 1, 2, 3] for v in hv["y"].values())


@kich_ban
def tron_06_cung_seed_cung_ket_qua():
    de = de_mau()
    cfg = T.doc_cau_hinh({})
    a = T.tao_bo_hoan_vi(de, cfg, random.Random("GOI-001"), set())[0]
    b = T.tao_bo_hoan_vi(de, cfg, random.Random("GOI-001"), set())[0]
    assert a == b


@kich_ban
def tron_07_cac_ma_de_khong_trung_nhau():
    de = de_mau()
    cfg = T.doc_cau_hinh({})
    rng, da_dung, khoa = random.Random(7), set(), []
    for _ in range(10):
        hv, ok = T.tao_bo_hoan_vi(de, cfg, rng, da_dung)
        assert ok
        khoa.append(repr(hv["thuTu"]) + repr(hv["pa"]))
    assert len(set(khoa)) == 10
    assert len(da_dung) == 10


@kich_ban
def tron_08_de_qua_ngan_bao_khong_khac_duoc():
    de = {"phan1": [{"A": "1", "B": "2", "C": "3", "D": "4", "dapAn": "A"}], "phan2": [], "phan3": [], "phan4": []}
    cfg = T.doc_cau_hinh({"tuyChon": {"tronPhuongAn": False}})
    rng, da_dung = random.Random(0), set()
    kq = [T.tao_bo_hoan_vi(de, cfg, rng, da_dung)[1] for _ in range(3)]
    assert kq[0] is True and kq[1] is False and kq[2] is False


@kich_ban
def tron_09_dap_an_dung_sau_khi_tron_phan1():
    """Với 200 bộ hoán vị: nội dung phương án đúng sau trộn phải bằng nội dung phương án đúng của câu gốc."""
    de = de_mau(n1=8)
    cfg = T.doc_cau_hinh({})
    for seed in range(200):
        hv, _ = T.tao_bo_hoan_vi(de, cfg, random.Random(seed), set())
        de_moi, dap_an, anh_xa, ghi_chu = T.tron_mot_ma(de, hv, cfg)
        assert ghi_chu == []
        for k, c in enumerate(de_moi["phan1"]):
            g = anh_xa["p1"][k]["goc"] - 1
            goc = de["phan1"][g]
            assert c["cauHoi"] == goc["cauHoi"]
            dung_goc = goc[goc["dapAn"]]
            assert c[dap_an["p1"][k]] == dung_goc, (seed, k)
            assert c["dapAn"] == dap_an["p1"][k]
            assert sorted(c[x] for x in "ABCD") == sorted(goc[x] for x in "ABCD")


@kich_ban
def tron_10_anh_xa_phuong_an_khop_noi_dung():
    de = de_mau(n1=6)
    cfg = T.doc_cau_hinh({})
    hv, _ = T.tao_bo_hoan_vi(de, cfg, random.Random(3), set())
    de_moi, _, anh_xa, _ = T.tron_mot_ma(de, hv, cfg)
    for k, c in enumerate(de_moi["phan1"]):
        goc = de["phan1"][anh_xa["p1"][k]["goc"] - 1]
        for j, chu_goc in enumerate(anh_xa["p1"][k]["phuongAn"]):
            assert c["ABCD"[j]] == goc[chu_goc]


@kich_ban
def tron_11_khong_sua_de_goc():
    de = de_mau()
    ban_sao = copy.deepcopy(de)
    cfg = T.doc_cau_hinh({"tuyChon": {"tronYPhan2": True}})
    hv, _ = T.tao_bo_hoan_vi(de, cfg, random.Random(5), set())
    T.tron_mot_ma(de, hv, cfg)
    assert de == ban_sao


@kich_ban
def tron_12_giu_nguyen_phan_4_va_dem_cau():
    de = de_mau()
    cfg = T.doc_cau_hinh({"tuyChon": {"tronYPhan2": True}})
    hv, _ = T.tao_bo_hoan_vi(de, cfg, random.Random(9), set())
    de_moi, dap_an, anh_xa, _ = T.tron_mot_ma(de, hv, cfg)
    assert de_moi["phan4"] == de["phan4"]
    assert dap_an["p4"] == ["(giữ nguyên)"] * len(de["phan4"])
    for p in (1, 2, 3):
        assert len(de_moi["phan%d" % p]) == len(de["phan%d" % p])
        assert len(dap_an["p%d" % p]) == len(de["phan%d" % p])
        assert sorted(x["goc"] for x in anh_xa["p%d" % p]) == list(range(1, len(de["phan%d" % p]) + 1))


@kich_ban
def tron_13_tat_tron_cau_giu_thu_tu():
    de = de_mau()
    cfg = T.doc_cau_hinh({"tuyChon": {"tronCau": {"1": False, "2": False, "3": False}}})
    hv, _ = T.tao_bo_hoan_vi(de, cfg, random.Random(2), set())
    assert hv["thuTu"][1] == list(range(5)) and hv["thuTu"][2] == list(range(3)) and hv["thuTu"][3] == list(range(4))
    de_moi, _, _, _ = T.tron_mot_ma(de, hv, cfg)
    assert [c["cauHoi"] for c in de_moi["phan1"]] == [c["cauHoi"] for c in de["phan1"]]


@kich_ban
def tron_14_tat_tron_phuong_an_giu_nguyen_dap_an():
    de = de_mau()
    cfg = T.doc_cau_hinh({"tuyChon": {"tronPhuongAn": False, "tronCau": {"1": False}}})
    hv, _ = T.tao_bo_hoan_vi(de, cfg, random.Random(4), set())
    de_moi, dap_an, _, ghi_chu = T.tron_mot_ma(de, hv, cfg)
    assert de_moi["phan1"] == de["phan1"]
    assert dap_an["p1"] == [c["dapAn"] for c in de["phan1"]]
    assert ghi_chu == []


@kich_ban
def tron_15_khong_doc_duoc_dap_an_thi_giu_nguyen_va_ghi_chu():
    de = de_mau(n1=3)
    de["phan1"][1]["dapAn"] = ""        # không đọc được
    cfg = T.doc_cau_hinh({})
    hv, _ = T.tao_bo_hoan_vi(de, cfg, random.Random(6), set())
    de_moi, dap_an, anh_xa, ghi_chu = T.tron_mot_ma(de, hv, cfg)
    assert len(ghi_chu) == 1 and "câu gốc 2" in ghi_chu[0], ghi_chu
    k = [i for i, x in enumerate(anh_xa["p1"]) if x["goc"] == 2][0]
    for chu in "ABCD":                   # phương án giữ nguyên thứ tự
        assert de_moi["phan1"][k][chu] == de["phan1"][1][chu]
    assert "phuongAn" not in anh_xa["p1"][k]


@kich_ban
def tron_16_tron_y_phan2_dap_an_di_theo_y():
    de = de_mau(n2=4)
    cfg = T.doc_cau_hinh({"tuyChon": {"tronYPhan2": True}})
    for seed in range(100):
        hv, _ = T.tao_bo_hoan_vi(de, cfg, random.Random(seed), set())
        de_moi, dap_an, anh_xa, ghi_chu = T.tron_mot_ma(de, hv, cfg)
        assert ghi_chu == []
        for k, c in enumerate(de_moi["phan2"]):
            ax = anh_xa["p2"][k]
            goc = de["phan2"][ax["goc"] - 1]
            ds_goc = T.doc_dap_an_p2(goc["dapAn"])
            ds_moi = T.doc_dap_an_p2(c["dapAn"])
            assert len(ds_moi) == 4
            for j, chu_y_goc in enumerate(ax["y"]):
                assert c["ABCD"[j]] == goc[chu_y_goc.upper()]           # nội dung ý đi theo
                assert ds_moi["abcd"[j]] == ds_goc[chu_y_goc]           # Đ/S đi theo ý
            assert dap_an["p2"][k] == c["dapAn"]


@kich_ban
def tron_17_phan2_khong_du_4_y_thi_giu_nguyen():
    de = de_mau(n2=2)
    de["phan2"][0]["dapAn"] = "a) Đ, b) S"
    cfg = T.doc_cau_hinh({"tuyChon": {"tronYPhan2": True}})
    hv, _ = T.tao_bo_hoan_vi(de, cfg, random.Random(8), set())
    de_moi, _, anh_xa, ghi_chu = T.tron_mot_ma(de, hv, cfg)
    assert len(ghi_chu) == 1 and "Phần II" in ghi_chu[0]
    k = [i for i, x in enumerate(anh_xa["p2"]) if x["goc"] == 1][0]
    assert de_moi["phan2"][k]["dapAn"] == "a) Đ, b) S"


@kich_ban
def tron_18_tron_y_mac_dinh_tat():
    de = de_mau()
    cfg = T.doc_cau_hinh({})
    hv, _ = T.tao_bo_hoan_vi(de, cfg, random.Random(1), set())
    de_moi, _, anh_xa, _ = T.tron_mot_ma(de, hv, cfg)
    for k, c in enumerate(de_moi["phan2"]):
        goc = de["phan2"][anh_xa["p2"][k]["goc"] - 1]
        assert c == goc


@kich_ban
def tron_19_kiem_goi():
    de = de_mau()
    assert T.kiem_goi_tron({"maDe": [], "dich": {}}, de)
    assert any("không trùng" in x for x in T.kiem_goi_tron({"maDe": ["101", "101"], "dich": {}}, de))
    assert any("thiếu docxHS" in x for x in T.kiem_goi_tron({"maDe": ["101"], "dich": {"101": {"docxHS": "x"}}}, de))
    assert any("thiếu phan3" in x for x in T.kiem_goi_tron(
        {"maDe": ["101"], "dich": {"101": {"docxHS": "x", "docxGV": "y"}}},
        {"phan1": [], "phan2": [], "phan4": []}))
    ok = {"maDe": ["101", "102"], "dich": {m: {"docxHS": "x", "docxGV": "y"} for m in ("101", "102")}}
    assert T.kiem_goi_tron(ok, de) == []


@kich_ban
def tron_20_nhieu_ma_de_dap_an_khong_lech():
    """Mô phỏng chạy 4 mã đề liên tiếp như main(): mọi mã đều đúng đáp án và không mã nào trùng mã nào."""
    de = de_mau(n1=10, n2=5, n3=6)
    cfg = T.doc_cau_hinh({"tuyChon": {"tronYPhan2": True}})
    rng, da_dung, thu_tu = random.Random("GOI-XYZ"), set(), set()
    for _ in range(4):
        hv, ok = T.tao_bo_hoan_vi(de, cfg, rng, da_dung)
        assert ok
        de_moi, dap_an, anh_xa, _ = T.tron_mot_ma(de, hv, cfg)
        thu_tu.add(tuple(x["goc"] for x in anh_xa["p1"]) + tuple(tuple(x["phuongAn"]) for x in anh_xa["p1"]))
        for k, c in enumerate(de_moi["phan1"]):
            goc = de["phan1"][anh_xa["p1"][k]["goc"] - 1]
            assert c[dap_an["p1"][k]] == goc[goc["dapAn"]]
    assert len(thu_tu) == 4


# ======================= chạy =======================
def chay():
    dat, hong = 0, []
    for f in DANH_SACH:
        try:
            f()
            dat += 1
            print("  ĐẠT  %s" % f.__name__)
        except Exception:
            hong.append(f.__name__)
            print("  HỎNG %s" % f.__name__)
            traceback.print_exc()
    for f in DA_BIET:
        try:
            f()
            print("  (lỗi đã biết nay đã hết) %s" % f.__name__)
        except AssertionError:
            print("  (lỗi đã biết, không tính đỏ) %s" % f.__name__)
    print("\n%d/%d kịch bản đạt" % (dat, len(DANH_SACH)))
    if hong:
        print("HỎNG: " + ", ".join(hong))
        sys.exit(1)


if __name__ == "__main__":
    chay()
