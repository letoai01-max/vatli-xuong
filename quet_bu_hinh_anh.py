import os
import re
import io
import json
import base64
import mimetypes
import warnings

# Ẩn các cảnh báo phiên bản phụ không cần thiết
warnings.filterwarnings("ignore", category=FutureWarning)

import gspread
import google.auth.transport.requests
from google.auth.exceptions import RefreshError
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

try:
    import pymupdf as fitz
except ImportError:
    import fitz

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


def chuan_hoa_private_key(pk: str) -> str:
    """Làm sạch chuỗi RSA private key nếu bị lỗi định dạng khi dán vào GitHub Secrets."""
    pk = pk.strip().strip('"').strip("'").replace("\r\n", "\n").replace("\\n", "\n")
    m = re.search(r"-----BEGIN PRIVATE KEY-----(.*?)-----END PRIVATE KEY-----", pk, re.S)
    if m:
        body = re.sub(r"\s+", "", m.group(1))
        lines = [body[i:i + 64] for i in range(0, len(body), 64)]
        return "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----\n"
    return pk


def doc_thong_tin_credentials():
    """Đọc thông tin Service Account từ biến môi trường GOOGLE_CREDENTIALS."""
    raw_cred = (
        os.environ.get("GOOGLE_CREDENTIALS")
        or os.environ.get("GCP_SA_KEY")
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or ""
    ).strip()

    if raw_cred and os.path.isfile(raw_cred):
        with open(raw_cred, "r", encoding="utf-8") as f:
            raw_cred = f.read().strip()

    if not raw_cred:
        for file_name in ("credentials.json", "service_account.json", "agent-vat-li-89f2bcd49721.json"):
            if os.path.isfile(file_name):
                with open(file_name, "r", encoding="utf-8") as f:
                    raw_cred = f.read().strip()
                break

    if not raw_cred:
        raise ValueError(
            "Biến môi trường GOOGLE_CREDENTIALS đang trống! "
            "Hãy cấu hình trong Settings -> Secrets and variables -> Actions."
        )

    try:
        tt = json.loads(raw_cred, strict=False)
    except Exception:
        try:
            decoded = base64.b64decode(raw_cred).decode("utf-8")
            tt = json.loads(decoded, strict=False)
        except Exception as e:
            raise ValueError("GOOGLE_CREDENTIALS không đúng định dạng JSON hợp lệ: " + str(e))

    if "private_key" in tt:
        tt["private_key"] = chuan_hoa_private_key(tt["private_key"])

    return tt


def authenticate():
    tt = doc_thong_tin_credentials()
    key_id = str(tt.get("private_key_id", ""))[:12]
    email = tt.get("client_email", "")
    print(f"-> Đang dùng Service Account: {email} (Key ID: {key_id}...)")

    creds = Credentials.from_service_account_info(tt, scopes=SCOPES)
    try:
        creds.refresh(google.auth.transport.requests.Request())
    except RefreshError as e:
        raise RuntimeError(
            f"\n❌ LỖI XÁC THỰC GOOGLE (Invalid JWT Signature) với Key ID '{key_id}...':\n"
            f"Nguyên nhân: Khóa JSON này đã bị Google vô hiệu hóa (do bị lộ công khai) hoặc bị hỏng khi copy.\n"
            f"Cách khắc phục:\n"
            f"  1. Vào https://console.cloud.google.com/iam-admin/serviceaccounts?project=agent-vat-li\n"
            f"  2. Chọn '{email}' -> tab KEYS -> ADD KEY -> Create new key (JSON).\n"
            f"  3. Copy toàn bộ nội dung file JSON mới dán đè vào GitHub Secret 'GOOGLE_CREDENTIALS' (tuyệt đối không đẩy file JSON lên kho chứa hay gửi lên mạng)."
        ) from e
    return creds


def quet_drive_va_gan_anh(sheet_id, drive_folder_id=None):
    print("Đang xác thực tài khoản Google Drive & Sheets...")
    creds = authenticate()
    gc = gspread.authorize(creds)
    drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)

    # Mở bảng tính
    if sheet_id.startswith("http"):
        sheet = gc.open_by_url(sheet_id)
    else:
        sheet = gc.open_by_key(sheet_id)

    # Tự động chọn worksheet có chứa dữ liệu ngân hàng câu hỏi
    worksheet = None
    for ws in sheet.worksheets():
        ws_title_lower = ws.title.lower()
        if (
            "nganhang" in ws_title_lower
            or "khochung" in ws_title_lower
            or "cauhoid" in ws_title_lower
            or "câu hỏi" in ws_title_lower
        ):
            worksheet = ws
            break

    if not worksheet:
        worksheet = sheet.get_worksheet(0)

    print(f"Đã kết nối thành công tới tab: '{worksheet.title}'")
    data = worksheet.get_all_records()
    print(f"Đã tải {len(data)} câu hỏi từ ngân hàng.")

    os.makedirs("./temp_images", exist_ok=True)

    query = "mimeType = 'application/pdf' and trashed = false"
    if drive_folder_id:
        query += f" and '{drive_folder_id}' in parents"

    print("Đang quét các tệp PDF trên Google Drive...")
    results = drive_service.files().list(
        q=query,
        pageSize=100,
        fields="files(id, name)",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True
    ).execute()
    files = results.get("files", [])
    print(f"Tìm thấy {len(files)} file PDF trên Google Drive.")

    danh_sach_anh = []

    for file in files:
        file_id = file["id"]
        file_name = file["name"]
        print(f"-> Đang xử lý tài liệu: {file_name}")

        try:
            request = drive_service.files().get_media(fileId=file_id, supportsAllDrives=True)
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

                    safe_name = re.sub(r'[\\/*?:"<>|]', "_", file_name)
                    image_name = f"{safe_name}_p{page_index+1}_img{img_index+1}.{image_ext}"
                    image_path = os.path.join("./temp_images", image_name)
                    with open(image_path, "wb") as img_file:
                        img_file.write(image_bytes)
                    danh_sach_anh.append(image_path)
            pdf_document.close()
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
        has_hinh_placeholder = bool(
            re.search(r"\[(Hình|Đồ thị|Mạch điện|Sơ đồ)[^\]]*\]", noi_dung, re.IGNORECASE)
        )

        if has_hinh_placeholder and anh_idx < len(danh_sach_anh):
            local_img_path = danh_sach_anh[anh_idx]
            img_file_name = os.path.basename(local_img_path)
            mime_type = mimetypes.guess_type(local_img_path)[0] or "image/png"

            try:
                file_metadata = {"name": img_file_name}
                if drive_folder_id:
                    file_metadata["parents"] = [drive_folder_id]

                media = MediaFileUpload(local_img_path, mimetype=mime_type, resumable=True)
                uploaded_file = drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields="id",
                    supportsAllDrives=True
                ).execute()

                cloud_file_id = uploaded_file.get("id")

                try:
                    drive_service.permissions().create(
                        fileId=cloud_file_id,
                        body={"type": "anyone", "role": "reader"},
                        supportsAllDrives=True
                    ).execute()
                except Exception:
                    pass

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
    DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID") or None

    quet_drive_va_gan_anh(SHEET_ID, DRIVE_FOLDER_ID)
