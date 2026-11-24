"""
pt_danh_muc.py – DANH MỤC, CẤU TRÚC ĐỀ VÀ NGƯỠNG MẶC ĐỊNH CỦA HỆ THỐNG PHÂN TÍCH ĐỀ TN THPT (Vật lí).

Mọi giá trị ở đây là MẶC ĐỊNH; Apps Script có thể ghi đè bằng gói việc (goi.danhMuc, goi.cauTruc, goi.mucTieu, goi.thoiGianPhut)
đọc từ tab PT_CauHinh của Google Sheet, nên đổi chuẩn không cần sửa code Python.
"""

MUC = ("NB", "TH", "VD", "VDC")
TEN_MUC = {"NB": "Nhận biết", "TH": "Thông hiểu", "VD": "Vận dụng", "VDC": "Vận dụng cao"}
LA_MA = {1: "I", 2: "II", 3: "III", 4: "IV"}

# Chương trình GDPT 2018, sách Kết nối tri thức (khớp tên chương dùng trong Kho chung; sửa ở tab PT_CauHinh nếu cần).
DANH_MUC_MAC_DINH = [
    {"lop": 10, "ma": "10.1", "ten": "Mở đầu (sai số, đơn vị, đại lượng vật lí)"},
    {"lop": 10, "ma": "10.2", "ten": "Động học"},
    {"lop": 10, "ma": "10.3", "ten": "Động lực học"},
    {"lop": 10, "ma": "10.4", "ten": "Công, năng lượng, công suất"},
    {"lop": 10, "ma": "10.5", "ten": "Động lượng"},
    {"lop": 10, "ma": "10.6", "ten": "Chuyển động tròn"},
    {"lop": 10, "ma": "10.7", "ten": "Biến dạng của vật rắn"},
    {"lop": 11, "ma": "11.1", "ten": "Dao động"},
    {"lop": 11, "ma": "11.2", "ten": "Sóng"},
    {"lop": 11, "ma": "11.3", "ten": "Trường điện"},
    {"lop": 11, "ma": "11.4", "ten": "Dòng điện, mạch điện"},
    {"lop": 12, "ma": "12.1", "ten": "Vật lí nhiệt"},
    {"lop": 12, "ma": "12.2", "ten": "Khí lí tưởng"},
    {"lop": 12, "ma": "12.3", "ten": "Từ trường"},
    {"lop": 12, "ma": "12.4", "ten": "Vật lí hạt nhân và phóng xạ"},
    {"lop": 0, "ma": "KHAC", "ten": "Khác / liên môn / ngoài danh mục"},
]

# Cấu trúc đề tham chiếu (dạng thức thi TN THPT từ 2025): 18 TN + 4 Đúng/Sai + 6 trả lời ngắn = 10 điểm, 50 phút.
CAU_TRUC_MAC_DINH = {
    "1": {"dang": "TN", "so_cau": 18, "diem_cau": 0.25},
    "2": {"dang": "DS", "so_cau": 4, "diem_y": [0.25, 0.25, 0.25, 0.25]},   # điểm danh nghĩa mỗi ý (cách chấm thật 0,1/0,25/0,5/1 chỉ dùng khi tính điểm)
    "3": {"dang": "TLN", "so_cau": 6, "diem_cau": 0.25},
}
THOI_GIAN_PHUT_MAC_DINH = 50

# Tỉ lệ điểm mục tiêu theo mức nhận thức: chỉ để so sánh, KHÔNG phải quy định – giáo viên đặt lại ở tab PT_CauHinh.
MUC_TIEU_MAC_DINH = {"NB": 0.40, "TH": 0.30, "VD": 0.20, "VDC": 0.10}
DUNG_SAI_MUC_TIEU = 0.10        # lệch quá ngưỡng này (theo điểm) thì nhận xét

NANG_LUC = ["Nhận thức vật lí", "Tìm hiểu thế giới tự nhiên", "Vận dụng kiến thức, kĩ năng đã học"]
DANG_BAI = ["Lí thuyết – khái niệm", "Tính toán trực tiếp", "Tính toán nhiều bước", "Đồ thị – bảng số liệu",
            "Thực nghiệm – xử lí số liệu", "Tình huống thực tiễn", "Đọc hiểu – ngữ cảnh"]

TIEU_CHI_MUC = (
    "TIÊU CHÍ MỨC ĐỘ (dùng nhất quán):\n"
    "- NB (Nhận biết): nhớ / nhận ra khái niệm, định luật, đơn vị, công thức; thay số 1 bước; đọc trực tiếp một giá trị từ hình, đồ thị, bảng.\n"
    "- TH (Thông hiểu): giải thích hiện tượng, so sánh, suy luận 1–2 bước; tính toán 2 bước với công thức quen thuộc; đọc đồ thị để suy ra đại lượng khác.\n"
    "- VD (Vận dụng): giải bài toán nhiều bước (≥ 3) kết hợp ≥ 2 kiến thức; mô hình hoá tình huống thực tiễn; xử lí số liệu thí nghiệm.\n"
    "- VDC (Vận dụng cao): tổng hợp liên chương, nhiều bước (≥ 4) cần biến đổi toán học phức tạp, lập luận hoặc đề xuất phương án mới, đồ thị phức tạp.\n"
    "Câu Đúng/Sai: phân loại RIÊNG TỪNG Ý a, b, c, d (thường a, b mức thấp hơn c, d). Chọn mức theo yêu cầu tư duy thật, không theo vị trí câu trong đề."
)
