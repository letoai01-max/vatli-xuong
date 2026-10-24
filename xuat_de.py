import json
import gspread
from google.oauth2.service_account import Credentials

# --- 1. KẾT NỐI VÀ LẤY DỮ LIỆU TỪ GOOGLE SHEET ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# Thiết lập xác thực thông qua file credentials.json hoặc biến môi trường
creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
client = gspread.authorize(creds)

# Mở Google Sheet theo ID của Kho chung Vật lí và chọn đúng tab chứa câu hỏi (NganHangCauHoi)
SPREADSHEET_ID = '1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc'
sheet = client.open_by_key(SPREADSHEET_ID).worksheet("NganHangCauHoi")

# Lấy toàn bộ dữ liệu gán vào biến all_values
all_values = sheet.get_all_values()

# --- 2. XỬ LÝ VÀ TRÍCH XUẤT DỮ LIỆU (CÓ BỘ LỌC CHẶT CHẼ DÒNG RÁC) ---
danh_sach_json = []

for row in all_values:
    # Lấy giá trị chính xác theo đúng vị trí các cột trên Google Sheet kho chung
    ma_cau = row[0].strip() if len(row) > 0 else ""       # Cột A: Mã câu
    noi_dung = row[6].strip() if len(row) > 6 else ""      # Cột G: Nội dung câu hỏi
    phuong_an = row[7].strip() if len(row) > 7 else ""     # Cột H: Phương án
    dap_an = row[8].strip() if len(row) > 8 else ""        # Cột I: Đáp án
    loi_giai = row[9].strip() if len(row) > 9 else ""      # Cột J: Lời giải / HDC
    trang_thai = row[20].strip() if len(row) > 20 else ""  # Cột U: Trạng thái
    link_anh = row[22].strip() if len(row) > 22 else ""    # Cột W: Link ảnh GitHub
    
    # BỘ LỌC CHUẨN XÁC ĐỂ LOẠI BỎ CÁC DÒNG THỐNG KÊ PHÂN PHỐI CHƯƠNG TRÌNH:
    is_valid_code = ma_cau.startswith("C-")
    is_not_stats = (
        "Tổng số tiết" not in noi_dung 
        and "Số bài kiểm tra" not in noi_dung 
        and "Số tiết:" not in noi_dung
        and "Đánh giá định kì" not in noi_dung
    )
    
    # Chỉ nhận các câu hỏi hợp lệ thực sự có nội dung
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

# --- 3. GHI KẾT QUẢ THÀNH TỆP questions.json CHO WEB ĐỌC ---
output_file = "questions.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(danh_sach_json, f, ensure_ascii=False, indent=2)

print(f"✨ Đã xuất thành công {len(danh_sach_json)} câu hỏi vào tệp {output_file}!")
