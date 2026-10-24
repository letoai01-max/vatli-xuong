import json
import gspread
from google.oauth2.service_account import Credentials

# --- 1. KẾT NỐI VÀ LẤY DỮ LIỆU TỪ GOOGLE SHEET ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# Đọc trực tiếp từ tệp credentials.json vừa được workflow sinh ra tự động
creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
client = gspread.authorize(creds)

SPREADSHEET_ID = '1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc'
sheet = client.open_by_key(SPREADSHEET_ID).worksheet("NganHangCauHoi")
all_values = sheet.get_all_values()

# --- 2. XỬ LÝ VÀ TRÍCH XUẤT DỮ LIỆU (CÓ BỘ LỌC CHẶT CHẼ DÒNG RÁC) ---
danh_sach_json = []

for row in all_values:
    ma_cau = row[0].strip() if len(row) > 0 else ""       # Cột A: Mã câu
    noi_dung = row[6].strip() if len(row) > 6 else ""      # Cột G: Nội dung
    phuong_an = row[7].strip() if len(row) > 7 else ""     # Cột H: Phương án
    dap_an = row[8].strip() if len(row) > 8 else ""        # Cột I: Đáp án
    loi_giai = row[9].strip() if len(row) > 9 else ""      # Cột J: Lời giải
    trang_thai = row[20].strip() if len(row) > 20 else ""  # Cột U: Trạng thái
    link_anh = row[22].strip() if len(row) > 22 else ""    # Cột W: Link ảnh
    
    # Bộ lọc loại bỏ dòng thống kê phân phối chương trình
    is_valid_code = ma_cau.startswith("C-")
    is_not_stats = (
        "Tổng số tiết" not in noi_dung 
        and "Số bài kiểm tra" not in noi_dung 
        and "Số tiết:" not in noi_dung
        and "Đánh giá định kì" not in noi_dung
    )
    
    if is_valid_code and is_not_stats and len(noi_dung) > 5:
        danh_sach_json.append({
            "ma_cau": ma_cau,
            "noi_dung": noi_dung,
            "phuong_an": phuong_an,
            "dap_an": dap_an,
            "loi_giai": loi_giai,
            "trang_thai": trang_thai,
            "link_anh": link_anh
        })

# --- 3. GHI KẾT QUẢ THÀNH TỆP questions.json ---
with open("questions.json", "w", encoding="utf-8") as f:
    json.dump(danh_sach_json, f, ensure_ascii=False, indent=2)

print(f"✨ Đã xuất thành công {len(danh_sach_json)} câu hỏi vào questions.json!")
