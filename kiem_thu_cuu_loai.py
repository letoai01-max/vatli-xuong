"""
kiem_thu_cuu_loai.py – KIỂM THỬ cuu_loai.py (chọn câu Loại do lỗi tách đề + kiểm bản tách lại). Không cần khoá, không gọi mạng.
Chạy: python kiem_thu_cuu_loai.py   (sai một ca → thoát mã 1)
"""
import sys, types

if "doc_de" not in sys.modules:
    gia = types.ModuleType("doc_de")
    gia.tu_khoa_ct_cu = lambda *a, **k: ""
    gia.bo_dau = lambda s: str(s).lower()
    gia.CT_CU_MO_TA = ""
    gia.TZ = None
    gia.HetHanMuc = type("HetHanMuc", (Exception,), {})
    sys.modules["doc_de"] = gia

import cuu_loai as L

LOI = []


def kiem(ten, dk):
    if not dk: LOI.append(ten)
    print(("✅ " if dk else "❌ ") + ten)


ND = "Một vật chuyển động thẳng đều với vận tốc $5 m/s$ trong $4 s$. Tính quãng đường vật đi được."
PA = "A. 10 m\nB. 20 m\nC. 30 m\nD. 40 m"

kiem("Loại vì thiếu phương án, chưa cứu → chọn", L.la_loai_do_tach("[5 tầng 21/11] Thiếu phương án (3/4)"))
kiem("Loại vì bản lưu thiếu số liệu so với đề gốc → chọn", L.la_loai_do_tach("[5 tầng 22/11] Đọc lại đề gốc thấy số liệu chưa có trong bản lưu: 2,5 kg"))
kiem("Loại vì lỗi nội dung → chọn", L.la_loai_do_tach("[5 tầng 21/11] Lỗi nội dung: đề chép thiếu dữ kiện"))
kiem("đã có dấu cứu Loại → không chọn lại", not L.la_loai_do_tach("[5 tầng 21/11] Thiếu phương án (3/4) | [cứu Loại 22/11: không cứu được – x]"))
kiem("Loại vì trùng → không chọn", not L.la_loai_do_tach("[5 tầng 21/11] Trùng hẳn câu C9"))
kiem("Loại do giáo viên (không có dấu máy) → không chọn", not L.la_loai_do_tach("GV loại: sai đề"))
kiem("Thiếu phương án nhưng cũng ngoài CT → không chọn", not L.la_loai_do_tach("[5 tầng 21/11] Thiếu phương án (3/4); Ngoài chương trình 2018"))

nd, pa, ly = L.hop_le_day_du("Trắc nghiệm", ND, ND, PA)
kiem("bản tách lại đủ 4 phương án, giống câu cũ → dùng được", ly is None and nd == ND and pa == PA)
nd, pa, ly = L.hop_le_day_du("Trắc nghiệm", ND, ND, "A. 10 m\nB. 20 m\nC. 30 m")
kiem("vẫn thiếu phương án → không dùng", nd is None and "thiếu phương án" in ly)
nd, pa, ly = L.hop_le_day_du("Trắc nghiệm", ND, "Một thấu kính hội tụ có tiêu cự 20 cm, vật đặt cách thấu kính 30 cm. Tính ảnh.", PA)
kiem("tách nhầm sang câu khác → không dùng", nd is None and "không giống" in ly)
nd, pa, ly = L.hop_le_day_du("Trắc nghiệm", ND, "Ngắn", PA)
kiem("đề quá ngắn → không dùng", nd is None and "quá ngắn" in ly)
nd, pa, ly = L.hop_le_day_du("Đúng/Sai", ND, ND, "a) x\nb) y\nc) z\nd) t")
kiem("đúng/sai đủ 4 ý → dùng được", ly is None)
ND2 = "Một vật chuyển động thẳng đều. Tính quãng đường vật đi được trong 4 s, biết $v = 5 m/s"
nd, pa, ly = L.hop_le_day_du("Trắc nghiệm", ND2, ND2, PA)
kiem("$ lẻ ở cuối công thức ngắn → cân được, dùng được", ly is None and nd.count("$") % 2 == 0 and nd.endswith("$"))
nd, pa, ly = L.hop_le_day_du("Trắc nghiệm", ND, ND.replace("$4 s$", "$4 s"), PA)
kiem("$ lẻ giữa câu chữ → không dám sửa, không dùng", nd is None and "$" in ly)
nd, pa, ly = L.hop_le_day_du("Trả lời ngắn", ND, ND, "")
kiem("trả lời ngắn không cần phương án → dùng được", ly is None)

print()
if LOI:
    print("❌ %d ca sai: %s" % (len(LOI), "; ".join(LOI))); sys.exit(1)
print("✅ Tất cả ca đạt.")
