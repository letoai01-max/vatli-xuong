import os
import re
import gspread
from google.oauth2.service_account import Credentials

# Cấu hình quyền truy cập Google Sheets API
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def ket_noi_google_sheet(sheet_id, credentials_path="credentials.json"):
    """Kết nối với Google Sheet Kho chung"""
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id)
    return sheet

def quet_va_cap_nhat_anh_cu(sheet_id, folder_anh_goc):
    """
    Quét toàn bộ tab NganHangCauHoi, tìm các câu có chứa [Hình: ...] 
    nhưng chưa có liên kết ảnh, sau đó khớp nối với thư mục ảnh gốc.
    """
    print("Đang kết nối tới Google Sheet Kho chung...")
    sheet = ket_noi_google_sheet(sheet_id)
    worksheet = sheet.worksheet("NganHangCauHoi")
    
    data = worksheet.get_all_records()
    print(f"Đã tải {len(data)} câu hỏi từ ngân hàng.")

    if not os.path.exists(folder_anh_goc):
        print(f"⚠️ Không tìm thấy thư mục ảnh gốc: {folder_anh_goc}")
        return

    danh_sach_anh = sorted([f for f in os.listdir(folder_anh_goc) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    print(f"Tìm thấy {len(danh_sach_anh)} file ảnh trong kho tài liệu gốc.")

    anh_idx = 0
    thay_doi_count = 0

    for index, row in enumerate(data, start=2):
        noi_dung = str(row.get("Nội dung", ""))
        ghi_chu = str(row.get("Ghi chú", ""))
        
        has_hinh_placeholder = bool(re.search(r"\[(Hình|Đồ thị|Mạch điện|Sơ đồ)", noi_dung, re.IGNORECASE))
        
        if has_hinh_placeholder and anh_idx < len(danh_sach_anh):
            ten_anh = danh_sach_anh[anh_idx]
            
            moi_ghi_chu = f"{ghi_chu} | [Đã gắn ảnh bù: {ten_anh}]".strip(" |")
            
            try:
                cell_list = worksheet.findall("Ghi chú")
                if cell_list:
                    col_num = cell_list[0].col
                    worksheet.update_cell(index, col_num, moi_ghi_chu)
                    print(f"-> Đã cập nhật câu dòng {index} với ảnh: {ten_anh}")
                    thay_doi_count += 1
                    anh_idx += 1
            except Exception as e:
                print(f"Lỗi cập nhật dòng {index}: {e}")

    print(f"🎉 Hoàn thành quét bù! Đã cập nhật thành công hình ảnh cho {thay_doi_count} câu hỏi cũ.")

if __name__ == "__main__":
    SHEET_ID = "1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc"
    THU_MUC_ANH_GOC = "./extracted_images"

    quet_va_cap_nhat_anh_cu(SHEET_ID, THU_MUC_ANH_GOC)
