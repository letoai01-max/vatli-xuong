import gspread
from google.oauth2.service_account import Credentials

# --- BƯỚC 1: KẾT NỐI VÀ LẤY DỮ LIỆU TỪ GOOGLE SHEET ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# Thiết lập xác thực Google Sheets API (Sử dụng thông tin xác thực sẵn có trong môi trường của Thầy)
# creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
# client = gspread.authorize(creds)

# Mở Google Sheet theo ID của Kho chung Vật lí và chọn đúng tab chứa câu hỏi (NganHangCauHoi)
SPREADSHEET_ID = '1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc'
# sheet = client.open_by_key(SPREADSHEET_ID).worksheet("NganHangCauHoi")

# Lấy toàn bộ dữ liệu gán vào biến all_values để tránh lỗi NameError
# all_values = sheet.get_all_values()


# --- BƯỚC 2: XỬ LÝ VÀ TRÍCH XUẤT DỮ LIỆU ---
danh_sach_json = []

# Duyệt qua từng dòng trong bảng tính
for row in all_values:
    # Lấy giá trị chính xác theo đúng vị trí các cột trên Google Sheet kho chung
    ma_cau = row[0].strip() if len(row) > 0 else ""       # Cột A: Mã câu
    noi_dung = row[6].strip() if len(row) > 6 else ""      # Cột G: Nội dung câu hỏi
    phuong_an = row[7].strip() if len(row) > 7 else ""     # Cột H: Phương án
    dap_an = row[8].strip() if len(row) > 8 else ""        # Cột I: Đáp án
    trang_thai = row[20].strip() if len(row) > 20 else ""  # Cột U: Trạng thái (Ai duyệt)
    link_anh = row[22].strip() if len(row) > 22 else ""    # Cột W: Link ảnh GitHub
    
    # BỘ LỌC CHUẨN XÁC: 
    # 1. Mã câu phải bắt đầu bằng 'C-'
    # 2. Loại bỏ hoàn toàn các dòng thống kê/tiêu đề (như "Số tiết:", "Tổng số tiết")
    # 3. Nội dung phải có độ dài hợp lệ
    is_valid_code = ma_cau.startswith("C-")
    is_not_stats = "Số tiết:" not in noi_dung and "Tổng số tiết" not in noi_dung
    
    if is_valid_code and is_not_stats and len(noi_dung) > 5:
        danh_sach_json.append({
            "ma_cau": ma_cau,
            "noi_dung": noi_dung,
            "phuong_an": phuong_an,
            "dap_an": dap_an,
            "trang_thai": trang_thai,
            "link_anh": link_anh
        })
