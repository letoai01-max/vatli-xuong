import gspread
from google.oauth2.service_account import Credentials

# 1. Cấu hình kết nối Google Sheets (Thầy thay thế thông tin xác thực nếu dùng phương pháp khác)
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
# Nếu Thầy dùng tệp JSON service account hoặc biến môi trường, hãy trỏ phù hợp:
# credentials = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
# gc = gspread.authorize(credentials)

# Mở Google Sheet theo Link hoặc Key của Thầy
SPREADSHEET_ID = '1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc'
# sheet = gc.open_by_key(SPREADSHEET_ID).worksheet("NganHangCauHoi") # Trỏ đúng tab chứa ngân hàng câu hỏi
# all_values = sheet.get_all_values()

# (Nếu Thầy đang dùng phương thức đọc file Excel/CSV cục bộ, Thầy thay thế đoạn trên bằng lệnh đọc file tương ứng vào biến all_values)

danh_sach_json = []

# 2. Duyệt qua từng dòng trong bảng tính để trích xuất dữ liệu
for row in all_values:
    # Lấy giá trị chính xác theo đúng vị trí các cột trên Google Sheet
    ma_cau = row[0].strip() if len(row) > 0 else ""       # Cột A: Mã câu
    noi_dung = row[6].strip() if len(row) > 6 else ""      # Cột G: Nội dung câu hỏi
    phuong_an = row[7].strip() if len(row) > 7 else ""     # Cột H: Phương án
    dap_an = row[8].strip() if len(row) > 8 else ""        # Cột I: Đáp án
    trang_thai = row[20].strip() if len(row) > 20 else ""  # Cột U: Trạng thái (Ai duyệt)
    link_anh = row[22].strip() if len(row) > 22 else ""    # Cột W: Link ảnh GitHub
    
    # BỘ LỌC CHUẨN XÁC: 
    # 1. Mã câu phải bắt đầu bằng 'C-'
    # 2. Nội dung bắt buộc phải tồn tại và có độ dài hợp lệ
    if ma_cau.startswith("C-") and len(noi_dung) > 5:
        danh_sach_json.append({
            "ma_cau": ma_cau,
            "noi_dung": noi_dung,
            "phuong_an": phuong_an,
            "dap_an": dap_an,
            "trang_thai": trang_thai,
            "link_anh": link_anh
        })
