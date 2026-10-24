import os
import re
import io
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
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
    print(f"Tìm thấy {len(files)} file PDF trên Google Drive.")

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

    # Khớp nối hình ảnh, upload lên Drive và gán link trực tiếp vào cột "Link Ảnh"
    anh_idx = 0
    thay_doi_count = 0
    
    # Lấy tiêu đề cột để xác định đúng vị trí cột "Link Ảnh"
    header_row = worksheet.row_values(1)
    link_anh_col_idx = None
    for idx, title in enumerate(header_row, start=1):
        if "link ảnh" in str(title).strip().lower():
            link_anh_col_idx = idx
            break
            
    if not link_anh_col_idx:
        print("⚠️ Không tìm thấy cột 'Link Ảnh' trên Sheet. Đang tự động thêm vào cột cuối...")
        link_anh_col_idx = len(header_row) + 1
        worksheet.update_cell(1, link_anh_col_idx, "Link Ảnh")

    for index, row in enumerate(data, start=2):
        noi_dung = str(row.get("Nội dung", ""))
        
        # Biểu thức chính quy chuẩn xác tìm thẻ [Hình: ...], [Đồ thị: ...], v.v.
        has_hinh_placeholder = bool(re.search(r"\[(Hình|Đồ thị|Mạch điện|Sơ đồ)[^\]]*\]", noi_dung, re.IGNORECASE))
        
        if has_hinh_placeholder and anh_idx < len(danh_sach_anh):
            local_img_path = danh_sach_anh[anh_idx]
            img_file_name = os.path.basename(local_img_path)
            
            try:
                # Upload ảnh đã cắt lên Google Drive
                file_metadata = {
                    'name': img_file_name,
                    'parents': [drive_folder_id] if drive_folder_id else []
                }
                media = MediaFileUpload(local_img_path, mimetype='image/png', resumable=True)
                uploaded_file = drive_service.files().create(
                    body=file_metadata, 
                    media_body=media, 
                    fields='id'
                ).execute()
                
                cloud_file_id = uploaded_file.get('id')
                # Tạo link ảnh trực tiếp dạng nhúng để web hiển thị mượt mà
                direct_img_link = f"https://lh3.googleusercontent.com/d/{cloud_file_id}"
                
                # Cập nhật link vào đúng cột "Link Ảnh" của dòng tương ứng
                worksheet.update_cell(index, link_anh_col_idx, direct_img_link)
                print(f"✅ Đã upload và gán link ảnh cho dòng {index} -> {direct_img_link}")
                thay_doi_count += 1
                anh_idx += 1
            except Exception as e:
                print(f"❌ Lỗi xử lý/upload ảnh dòng {index}: {e}")

    print(f"✨ Hoàn tất quét bù! Đã cập nhật thành công hình ảnh cho {thay_doi_count} câu hỏi từ Google Drive.")

if __name__ == "__main__":
    SHEET_ID = "1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc"
    DRIVE_FOLDER_ID = None 
    
    quet_drive_va_gan_anh(SHEET_ID, DRIVE_FOLDER_ID)
