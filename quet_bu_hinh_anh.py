import os
import re
import io
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import fitz  # PyMuPDF để trích xuất ảnh trực tiếp từ PDF

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
    
    # Mở bảng tính bằng URL hoặc Key, tự động quét tìm tab chứa câu hỏi
    try:
        sheet = gc.open_by_key(sheet_id)
    except Exception:
        sheet = gc.open_by_url(f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
        
    # Tự động chọn worksheet có chứa dữ liệu ngân hàng câu hỏi mà không phụ thuộc cứng tên tab
    worksheet = None
    for ws in sheet.worksheets():
        ws_title_lower = ws.title.lower()
        if "nganhang" in ws_title_lower or "khochung" in ws_title_lower or "cauhoid" in ws_title_lower or "câu hỏi" in ws_title_lower:
            worksheet = ws
            break
    
    if not worksheet:
        worksheet = sheet.get_worksheet(0) # Mặc định lấy tab đầu tiên nếu không khớp tên
        
    print(f"Đã kết nối thành công tới tab: '{worksheet.title}'")
    data = worksheet.get_all_records()
    print(f"Đã tải {len(data)} câu hỏi từ ngân hàng.")

    os.makedirs("./temp_images", exist_ok=True)
    
    query = "mimeType = 'application/pdf'"
    if drive_folder_id:
        query += f" and '{drive_folder_id}' in parents"
        
    print("Đang quét các tệp PDF trên Google Drive...")
    results = drive_service.files().list(q=query, pageSize=100, fields="files(id, name)").execute()
    files = results.get('files', [])
    print(f"Tìm thấy {len(files)} file PDF trên Google Drive.")

    danh_sach_anh = []
    
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

    print(f"🎉 Đã trích xuất tổng cộng {len(danh_sach_anh)} hình ảnh từ tài liệu.")

    anh_idx = 0
    thay_doi_count = 0
    
    header_row = worksheet.row_values(1)
    link_anh_col_idx = None
    for idx, title in enumerate(header_row, start=1):
        if "link ảnh" in str(title).strip().lower():
            link_anh_col_idx = idx
            break
            
    if not link_anh_col_idx:
        link_anh_col_idx = len(header_row) + 1
        worksheet.update_cell(1, link_anh_col_idx, "Link Ảnh")

    for index, row in enumerate(data, start=2):
        noi_dung = str(row.get("Nội dung", ""))
        has_hinh_placeholder = bool(re.search(r"\[(Hình|Đồ thị|Mạch điện|Sơ đồ)[^\]]*\]", noi_dung, re.IGNORECASE))
        
        if has_hinh_placeholder and anh_idx < len(danh_sach_anh):
            local_img_path = danh_sach_anh[anh_idx]
            img_file_name = os.path.basename(local_img_path)
            
            try:
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
                direct_img_link = f"https://lh3.googleusercontent.com/d/{cloud_file_id}"
                
                worksheet.update_cell(index, link_anh_col_idx, direct_img_link)
                print(f"✅ Đã upload và gán link ảnh cho dòng {index} -> {direct_img_link}")
                thay_doi_count += 1
                anh_idx += 1
            except Exception as e:
                print(f"❌ Lỗi xử lý/upload ảnh dòng {index}: {e}")

    print(f"✨ Hoàn tất quét bù! Đã cập nhật thành công hình ảnh cho {thay_doi_count} câu hỏi.")

if __name__ == "__main__":
    SHEET_ID = "1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc"
    DRIVE_FOLDER_ID = None 
    
    quet_drive_va_gan_anh(SHEET_ID, DRIVE_FOLDER_ID)
