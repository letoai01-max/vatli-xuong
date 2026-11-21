"""
kiem_thu_duyet_cau.py – KIỂM THỬ luật xếp loại mới của duyet_cau.py (không cần khoá, không gọi mạng).
Chạy: python kiem_thu_duyet_cau.py   (sai một ca → thoát mã 1 để Actions báo đỏ)
"""
import os, sys, types

if "doc_de" not in sys.modules:                      # giả lập doc_de khi chạy ngoài repo xưởng
    gia = types.ModuleType("doc_de")
    gia.tu_khoa_ct_cu = lambda *a, **k: ""
    gia.bo_dau = lambda s: s
    gia.CT_CU_MO_TA = ""
    gia.TZ = None
    gia.HetHanMuc = type("HetHanMuc", (Exception,), {})
    sys.modules["doc_de"] = gia

import duyet_cau as D

LOI = []


def kiem(ten, dieu_kien):
    if not dieu_kien:
        LOI.append(ten)
    print(("✅ " if dieu_kien else "❌ ") + ten)


def cau(dang="Trắc nghiệm", nd="Một vật chuyển động thẳng đều với vận tốc 5 m/s trong 4 s. Tính quãng đường.",
        pa="A. 10 m\nB. 20 m\nC. 30 m\nD. 40 m", dap_an="", muc_do="Vận dụng", yccd=("VL10-01-1",)):
    return {"dong": 2, "ma": "C1", "dang": dang, "muc_do": muc_do, "noi_dung": nd, "phuong_an": pa, "dap_an": dap_an,
            "kiem_tra_cu": "", "ma_yccd": list(yccd), "vi_tri": "1", "loi_nang": [], "nghi_van": [], "ghi_chu": [],
            "sua": {}, "bat_dong": [], "co_hinh": False, "hoan": False}


YCCD = {"VL10-01-1": "x"}
D.MOI = True
D.KHONG_HINH_BAT_DONG = "loai"

# ---- đếm phương án ----
kiem("TN đủ 4 dòng = 4", D.dem_phuong_an("TN", "", "A. 1\nB. 2\nC. 3\nD. 4") == 4)
kiem("TN 3 dòng = 3", D.dem_phuong_an("TN", "", "A. 1\nB. 2\nC. 3") == 3)
kiem("TN 4 phương án trên một dòng = 4", D.dem_phuong_an("TN", "", "A. 1 m B. 2 m C. 3 m D. 4 m") == 4)
kiem("DS 3 ý = 3", D.dem_phuong_an("DS", "", "a) x\nb) y\nc) z") == 3)
kiem("DS 4 ý = 4", D.dem_phuong_an("DS", "", "a) x\nb) y\nc) z\nd) t") == 4)

# ---- 1. thiếu phương án / ý → Loại ngay ----
x = cau(pa="A. 10 m\nB. 20 m\nC. 30 m"); D.tang1(x, YCCD)
kiem("TN thiếu phương án → Loại", D.xep_loai(x) == D.TT["LOAI"])
x = cau(dang="Đúng/Sai", pa="a) x\nb) y\nc) z"); D.tang1(x, YCCD)
kiem("DS thiếu ý → Loại", D.xep_loai(x) == D.TT["LOAI"])
x = cau(pa="A. 10 m\nB. 20 m\nC. 30 m"); D.MOI = False; D.tang1(x, YCCD); D.MOI = True
kiem("Chế độ cũ: thiếu phương án → Cần người xem (không Loại)", (not x["loi_nang"] and bool(x["nghi_van"])))

# ---- 2. thiếu đáp án: máy giải rồi duyệt luôn ----
x = cau(); D.tang1(x, YCCD)
D.quyet_dinh(x, {"co_hdc": False, "tu_giai": "C", "loi_noi_dung": False, "ma_yccd_hop_li": True, "ngoai_ct2018": False},
             [], {"ma_cau": "C1", "phuong_an_dung": ["B"]}, "gemini-a", "gemini-a", YCCD)
kiem("TN thiếu đáp án, hai cách giải KHÁC nhau → không duyệt", D.xep_loai(x) != D.TT["AI"])
x = cau(); D.tang1(x, YCCD)
D.quyet_dinh(x, {"co_hdc": False, "tu_giai": "B", "loi_noi_dung": False, "ma_yccd_hop_li": True, "ngoai_ct2018": False},
             [], {"ma_cau": "C1", "phuong_an_dung": ["B"], "tu_tin": "cao"}, "gemini-a", "gemini-a", YCCD)
kiem("TN thiếu đáp án, 2 cách giải cùng model khớp → AI duyệt", D.xep_loai(x) == D.TT["AI"])
kiem("… và ghi đáp án B", x["sua"].get("dap_an") == "B")

x = cau(dang="Tự luận", pa="", muc_do="Vận dụng cao"); D.tang1(x, YCCD)
D.quyet_dinh(x, {"co_hdc": False, "tu_giai": "2,5", "loi_noi_dung": False, "ma_yccd_hop_li": True, "ngoai_ct2018": False},
             [], {"ma_cau": "C1", "dap_so": 2.5, "don_vi": "m/s", "tu_tin": "cao"}, "gemini-a", "gemini-a", YCCD)
kiem("Tự luận vận dụng cao thiếu HDC, 2 lời giải khớp → AI duyệt", D.xep_loai(x) == D.TT["AI"])
kiem("… ghi 'Đáp số: 2,5 m/s'", x["sua"].get("dap_an") == "Đáp số: 2,5 m/s")

x = cau(dap_an="AB"); D.tang1(x, YCCD)
kiem("Đáp án sai dạng được coi như thiếu (bỏ)", x["dap_an"] == "" and not x["nghi_van"])

# ---- 3. Cần người xem chỉ dành cho câu có hình ----
bat = {"co_hdc": False, "tu_giai": "C", "loi_noi_dung": False, "ma_yccd_hop_li": True, "ngoai_ct2018": False}
may = {"ma_cau": "C1", "phuong_an_dung": ["B"], "tu_tin": "cao"}
x = cau(); D.tang1(x, YCCD); D.quyet_dinh(x, dict(bat), [], dict(may), "gemini-a", "gemini-b", YCCD)
kiem("Không hình + chưa thống nhất → Loại", D.xep_loai(x) == D.TT["LOAI"])
x = cau(nd="Cho mạch điện như hình vẽ, R = 5 Ω, U = 10 V. Tính I [Hình: mạch nối tiếp]"); D.tang1(x, YCCD)
D.quyet_dinh(x, dict(bat), [], dict(may), "gemini-a", "gemini-b", YCCD)
kiem("Có hình + chưa thống nhất → Cần người xem", D.xep_loai(x) == D.TT["XEM"])
x = cau(nd="Cho mạch điện như hình vẽ, R = 5 Ω, U = 10 V. Tính cường độ dòng điện."); D.tang1(x, YCCD)
kiem("Nhắc hình mà không có mô tả → Cần người xem (không Loại)", D.xep_loai(x) == D.TT["XEM"])
D.KHONG_HINH_BAT_DONG = "xem"
x = cau(); D.tang1(x, YCCD); D.quyet_dinh(x, dict(bat), [], dict(may), "gemini-a", "gemini-b", YCCD)
kiem("KHONG_HINH_BAT_DONG=xem → không hình cũng Cần người xem", D.xep_loai(x) == D.TT["XEM"])
D.KHONG_HINH_BAT_DONG = "loai"
x = cau(yccd=()); D.tang1(x, YCCD); D.quyet_dinh(x, dict(bat, tu_giai="B"), [], dict(may), "gemini-a", "gemini-b", YCCD)
kiem("Việc không liên quan đáp án (chưa gắn YCCĐ) vẫn Cần người xem", D.xep_loai(x) == D.TT["XEM"])

# ---- 4. Gemini không đánh giá được → hoãn, không ghi ----
x = cau(); D.tang1(x, YCCD); D.quyet_dinh(x, None, [], None, "gemini-a", "gemini-a", YCCD)
kiem("Gemini không đánh giá được → hoãn (giữ Chưa duyệt)", x["hoan"] is True)

# ---- 5. lay_so hiểu 'Đáp số' ----
kiem("lay_so lấy số sau 'Đáp số'", D.lay_so("Bước 1: 3 + 4 = 7. => Đáp số: 2,5 m/s") == 2.5)
kiem("lay_so cũ vẫn đúng", D.lay_so("12,5") == 12.5)

# ---- 6. chế độ cũ giữ nguyên hành vi ----
D.MOI = False
x = cau(); D.tang1(x, YCCD)
D.quyet_dinh(x, dict(bat, tu_giai="B"), [], dict(may), "gemini-a", "gemini-a", YCCD)
kiem("Chế độ cũ: cùng một model → Cần người xem", D.xep_loai(x) == D.TT["XEM"])
D.MOI = True

if LOI:
    print("\n❌ %d ca sai: %s" % (len(LOI), "; ".join(LOI)))
    sys.exit(1)
print("\n✅ Tất cả ca đạt.")
