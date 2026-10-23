import os
import re
import io
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import fitz  # PyMuPDF để trích xuất ảnh trực tiếp từ PDF trên mây

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def authenticate(credentials_path="credentials.json"):
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    return creds

def quet_drive_va_gan_anh(sheet_id, drive_folder_id=None, credentials_path="credentials.json"):
    print("Đang xác thực tài khoản Google Drive & Sheets...")
    creds = authenticate(credentials_path)
    gc = gspread.authorize(creds)
    drive_service = build('drive', 'v3', credentials=creds)
    
    sheet = gc.open_by_key(sheet_id)
    worksheet = sheet.worksheet("NganHangCauHoi")
    data = worksheet.get_all_records()
    print(f"Đã tải {len(data)} câu hỏi từ ngân hàng.")

    os.makedirs("./temp_images", exist_ok=True)
    
    # Tìm kiếm các file PDF trên Google Drive
    query = "mimeType = 'application/pdf'"
    if drive_folder_id:
        query += f" and '{drive_folder_id}' in parents"
        
    print("Đang quét các tệp PDF trên Google Drive...")
    results = drive_service.files().list(q=query, pageSize=100, fields="files(id, name)").execute()
    files = results.get('files', [])
    print(f"Tìm thấy {len(files)} file PDF trên Google Drive của thầy.")

    danh_sach_anh = []
    
    # Tự động tải file từ Drive xuống bộ nhớ tạm và bóc tách ảnh
    for file in files:
        file_id = file['id']
        file_name = file['name']
        print(f"-> Đang xử lý tài liệu: {file_name}")
        
        try:
            request = drive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            
            fh.seek(0)
            pdf_document = fitz.open(stream=fh.read(), filetype="pdf")
            for page_index in range(len(pdf_document)):
                page = pdf_document[page_index]
                image_list = page.get_images(full=True)
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = pdf_document.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    image_name = f"{file_name}_p{page_index+1}_img{img_index+1}.{image_ext}"
                    image_path = os.path.join("./temp_images", image_name)
                    with open(image_path, "wb") as img_file:
                        img_file.write(image_bytes)
                    danh_sach_anh.append(image_path)
        except Exception as e:
            print(f"Lỗi khi đọc file {file_name}: {e}")

    print(f"🎉 Đã trích xuất tổng cộng {len(danh_sach_anh)} hình ảnh từ toàn bộ tài liệu trên Drive.")

    # Khớp nối hình ảnh với các câu hỏi cũ cần gắn bù trong Google Sheet
    anh_idx = 0
    thay_doi_count = 0
    for index, row in enumerate(data, start=2):
        noi_dung = str(row.get("Nội dung", ""))
        ghi_chu = str(row.get("Ghi chú", ""))
        
        has_hinh_placeholder = bool(re.search(r"\[(Hình|Đồ thị|Mạch điện|Sơ đồ)", noi_dung, re.IGNORECASE))
        
        if has_hinh_placeholder and anh_idx < len(danh_sach_anh):
            ten_anh = os.path.basename(danh_sach_anh[anh_idx])
            moi_ghi_chu = f"{ghi_chu} | [Drive: {ten_anh}]".strip(" |")
            
            try:
                cell_list = worksheet.findall("Ghi chú")
                if cell_list:
                    col_num = cell_list[0].col
                    worksheet.update_cell(index, col_num, moi_ghi_chu)
                    print(f"Gán thành công ảnh cho dòng {index} -> {ten_anh}")
                    thay_doi_count += 1
                    anh_idx += 1
            except Exception as e:
                print(f"Lỗi cập nhật dòng {index}: {e}")

    print(f"✨ Hoàn tất quét bù! Đã cập nhật thành công hình ảnh cho {thay_doi_count} câu hỏi cũ từ Google Drive.")

if __name__ == "__main__":
    SHEET_ID = "1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc"
    # Nếu thầy muốn quét toàn bộ Drive, cứ để trống (None). 
    # Nếu chỉ muốn quét một thư mục cụ thể trên Drive, thầy dán ID của thư mục đó vào trong dấu ngoặc kép.
    DRIVE_FOLDER_ID = None 
    
    quet_drive_va_gan_anh(SHEET_ID, DRIVE_FOLDER_ID)
