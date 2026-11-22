"""
kiem_thu_cuu_nghi_van.py – KIỂM THỬ bước cứu câu "Cần người xem" tự động (cuu_nghi_van.py + phần tầng 6 trong duyet_cau.py).
Không cần khoá, không gọi mạng. Chạy: python kiem_thu_cuu_nghi_van.py   (sai một ca → thoát mã 1)
"""
import sys, types

if "doc_de" not in sys.modules:
    gia = types.ModuleType("doc_de")
    gia.tu_khoa_ct_cu = lambda *a, **k: ""
    gia.bo_dau = lambda s: s
    gia.CT_CU_MO_TA = ""
    gia.TZ = None
    gia.HetHanMuc = type("HetHanMuc", (Exception,), {})
    sys.modules["doc_de"] = gia

import cuu_nghi_van as CN
import duyet_cau as D

LOI = []


def kiem(ten, dk):
    if not dk: LOI.append(ten)
    print(("✅ " if dk else "❌ ") + ten)


def cau(dang="Trắc nghiệm", nd="Một vật chuyển động thẳng đều với vận tốc $5 m/s$ trong $4 s$. Tính quãng đường.",
        pa="A. 10 m\nB. 20 m\nC. 30 m\nD. 40 m", dap_an="", yccd=("VL10-01-1",)):
    return {"dong": 2, "ma": "C1", "dang": dang, "muc_do": "Vận dụng", "noi_dung": nd, "phuong_an": pa, "dap_an": dap_an,
            "kiem_tra_cu": "", "ma_yccd": list(yccd), "vi_tri": "1", "loi_nang": [], "nghi_van": [], "ghi_chu": [],
            "sua": {}, "bat_dong": [], "co_hinh": False, "hoan": False}


YCCD = {"VL10-01-1": "x", "VL10-01-2": "y", "VL11-02-1": "z"}

# ---- sua_dola ----
kiem("$ chẵn giữ nguyên", CN.sua_dola("Vận tốc $v = 5$ m/s") == ("Vận tốc $v = 5$ m/s", True))
t, ok = CN.sua_dola("Quãng đường $s = 20 m"); kiem("thiếu $ đóng ở cuối → đóng lại", ok and t.endswith("$") and CN.dem_dola(t) % 2 == 0)
t, ok = CN.sua_dola("v = 5 m/s$ và gia tốc"); kiem("thiếu $ mở ở đầu (đoạn đầu là công thức ngắn) → mở lại", ok and t == "$v = 5 m/s$ và gia tốc")
t, ok = CN.sua_dola("Cho vật có v = 5 m/s$ và gia tốc a rất lớn"); kiem("$ lẻ mà không an toàn sửa → giữ nguyên, báo False", not ok and t == "Cho vật có v = 5 m/s$ và gia tốc a rất lớn")
t, ok = CN.sua_dola("Một vật chuyển động rất nhanh trên đường thẳng dài $ trong thời gian dài và nhiều chữ nữa ở cuối câu này"); kiem("đoạn cuối là câu chữ → không sửa", not ok)
kiem("\\$ không tính", CN.dem_dola(r"Giá \$5 và $x$") == 2)

# ---- bo_phieu ----
def kh(loai, a, b, ss): return D.khop(loai, a, b, ss)
r = CN.bo_phieu("TN", {"hdc": "B", "tu": "B", "may": "C", "gq": "", "hinh": "B"}, kh, 0.02)
kiem("3 phiếu B (có hình) thắng 1 phiếu C", r is not None and r[0] == "B" and "hinh" in r[1])
kiem("hoà 2–2 → không thắng", CN.bo_phieu("TN", {"hdc": "B", "tu": "C", "may": "C", "hinh": "B"}, kh, 0.02) is None)
kiem("nhóm thắng không có phiếu hình → không thắng", CN.bo_phieu("TN", {"hdc": "B", "tu": "B", "may": "B", "hinh": "C"}, kh, 0.02) is None)
kiem("chỉ 1 phiếu → không thắng", CN.bo_phieu("TN", {"hinh": "B"}, kh, 0.02) is None)
r = CN.bo_phieu("TLN", {"hdc": "2,02", "may": "2,0201", "hinh": "2,02", "tu": "3,5"}, kh, 0.02)
kiem("số gần nhau (sai số 2%) gộp một nhóm", r is not None and len(r[1]) == 3)
r = CN.bo_phieu("DS", {"hdc": "a) Đ, b) S, c) Đ, d) S", "hinh": "a) Đ, b) S, c) Đ, d) S", "may": "a) Đ, b) Đ, c) Đ, d) S"}, kh, 0.02)
kiem("đúng/sai so cả 4 ý", r is not None and set(r[1]) == {"hdc", "hinh"})

# ---- lí do giải được ----
kiem("bất đồng đáp án giải được", CN.li_do_giai_duoc("HDC gốc B, máy giải C – cần xem"))
kiem("thiếu hình giải được", CN.li_do_giai_duoc("Thiếu dữ kiện khi không có hình gốc"))
kiem("số liệu lệch đề gốc KHÔNG giải được bằng nhìn hình", not CN.li_do_giai_duoc("Đọc lại đề gốc thấy số liệu chưa có trong bản lưu: 5 m"))

# ---- ứng viên YCCĐ ----
kiem("ứng viên theo mã bài", sorted(CN.ung_vien_yccd(YCCD, "VL10-01", "10")) == ["VL10-01-1", "VL10-01-2"])
kiem("không biết bài → theo lớp", CN.ung_vien_yccd(YCCD, "", "11") == ["VL11-02-1"])
kiem("không biết gì → rỗng", CN.ung_vien_yccd(YCCD, "", "") == [])

# ---- tang1 với TU_SUA ----
D.MOI = True
D.TU_SUA = True
x = cau(nd="Một vật chuyển động với vận tốc $v = 5 m/s trong 4 s. Tính quãng đường s."); D.tang1(x, YCCD)
kiem("TU_SUA: $ lẻ tự cân (hoặc giữ nghi vấn, không sập)", ("noi_dung" in x["sua"]) or any("$" in n for n in x["nghi_van"]))
x = cau(yccd=()); D.tang1(x, YCCD)
kiem("TU_SUA: chưa có mã → chờ gán, chưa thành nghi vấn", x.get("can_gan") and not x["nghi_van"])
x = cau(yccd=("XXX",)); D.tang1(x, YCCD)
kiem("TU_SUA: mã không có trong YCCD → chờ gán", "Mã không có" in x.get("can_gan", ""))
D.TU_SUA = False
x = cau(yccd=()); D.tang1(x, YCCD)
kiem("Cờ tắt: chưa có mã → nghi vấn như cũ", any("Chưa gắn mã" in n for n in x["nghi_van"]) and not x.get("can_gan"))
x = cau(nd="Vận tốc $v = 5 m/s trong 4 s tính quãng đường đi được"); D.tang1(x, YCCD)
kiem("Cờ tắt: $ lẻ → nghi vấn như cũ", any("$" in n for n in x["nghi_van"]) and "noi_dung" not in x["sua"])

# ---- ap_dung_phieu_hinh ----
def cau_hinh(bc, bd=("HDC gốc B, máy giải C – cần xem",), dap_an="B"):
    x = cau(dap_an=dap_an)
    x["co_hinh"] = True
    x["bat_dong"] = list(bd); x["nghi_van"] = list(bd); x["bc"] = bc
    return x

x = cau_hinh({"hdc": "B", "tu": "B", "may": "C", "gq": ""}, dap_an="")
kiem("nhìn hình ra B, 3 phiếu B → cứu, ghi đáp án B", D.ap_dung_phieu_hinh(x, {"phuong_an_dung": ["B"], "tu_tin": "cao"}) and not x["nghi_van"] and x["sua"].get("dap_an") == "B")
kiem("   … sau khi cứu xếp loại = AI duyệt", D.xep_loai(x) == D.TT["AI"])
x = cau_hinh({"hdc": "B", "tu": "C", "may": "C", "gq": ""})
kiem("hoà 2–2 → không cứu", not D.ap_dung_phieu_hinh(x, {"phuong_an_dung": ["B"], "tu_tin": "cao"}) and x["nghi_van"])
x = cau_hinh({"hdc": "B", "tu": "B", "may": "B", "gq": ""})
kiem("nhìn hình ra C khác cả 3 → không cứu", not D.ap_dung_phieu_hinh(x, {"phuong_an_dung": ["C"], "tu_tin": "cao"}))
x = cau_hinh({"hdc": "B", "tu": "B", "may": "C", "gq": ""})
kiem("model không chắc (thấp) → không cứu", not D.ap_dung_phieu_hinh(x, {"phuong_an_dung": ["B"], "tu_tin": "thấp"}))
x = cau_hinh({"hdc": "B", "tu": "B", "may": "C", "gq": ""})
kiem("nhìn hình thấy 2 phương án đúng → không cứu", not D.ap_dung_phieu_hinh(x, {"phuong_an_dung": ["B", "C"], "tu_tin": "cao"}))
x = cau_hinh({"hdc": "B", "tu": "B", "may": "B", "gq": ""}, bd=("Đọc lại đề gốc thấy số liệu chưa có trong bản lưu: 5 m",))
kiem("lí do số liệu lệch → không cứu dù phiếu đủ", not D.ap_dung_phieu_hinh(x, {"phuong_an_dung": ["B"], "tu_tin": "cao"}))
x = cau_hinh({"hdc": "B", "tu": "B", "may": "C", "gq": ""}, dap_an="C")
kiem("đáp án đã ghi C nhưng 3 phiếu B → sửa thành B", D.ap_dung_phieu_hinh(x, {"phuong_an_dung": ["B"], "tu_tin": "cao"}) and x["sua"].get("dap_an") == "B")
x = cau_hinh({"hdc": "", "tu": "2,02", "may": "", "gq": ""}, bd=("Không có HDC; hai lời giải độc lập chưa thống nhất (2,02 / ?)",), dap_an="")
x["dang"] = "Trả lời ngắn"
kiem("TLN: lập luận 2,02 + nhìn hình 2,02 → cứu và ghi 2,02", D.ap_dung_phieu_hinh(x, {"dap_so": 2.02, "tu_tin": "cao"}) and x["sua"].get("dap_an") == "2,02")

# ---- XEM_CON_LAI ----
x = cau_hinh({"hdc": "B", "tu": "C", "may": "C", "gq": ""})
D.XEM_CON_LAI = "xem"
kiem("XEM_CON_LAI=xem: câu có hình còn bất đồng → Cần người xem", D.xep_loai(x) == D.TT["XEM"])
D.XEM_CON_LAI = "loai"
kiem("XEM_CON_LAI=loai: → Loại, có ghi lí do", D.xep_loai(x) == D.TT["LOAI"] and any("không chờ giáo viên" in g for g in x["ghi_chu"]))
x = cau(); x["nghi_van"] = ["Chưa gắn mã YCCĐ"]
kiem("XEM_CON_LAI=loai: nghi vấn không đáp án chưa gỡ → Loại", D.xep_loai(x) == D.TT["LOAI"])
x = cau()
kiem("XEM_CON_LAI=loai: câu sạch vẫn AI duyệt", D.xep_loai(x) == D.TT["AI"])
D.XEM_CON_LAI = "xem"

print()
if LOI:
    print("❌ %d ca sai: %s" % (len(LOI), "; ".join(LOI)))
    sys.exit(1)
print("✅ Tất cả ca đạt.")
