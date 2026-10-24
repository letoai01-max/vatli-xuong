import os
import re
import io
import json
import base64
import mimetypes
import warnings

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

# Nhận diện cả ký hiệu [Hình...] lẫn câu chữ thông thường trong đề thi Vật lí
RE_CAN_HINH = re.compile(
    r"(\[\s*(Hình|Đồ thị|Mạch điện|Sơ đồ|H\.)[^\]]*\]"
    r"|\[\[DO_THI"
    r"|như\s+hình\s*(vẽ|bên|dưới|\d+)?"
    r"|hình\s+vẽ\s*(bên|dưới)?"
    r"|(đồ\s+thị|mạch\s+điện|sơ\s+đồ)\s+(như\s+)?hình"
    r"|\bHình\s+\d+)",
    re.IGNORECASE
)


def chuan_hoa_private_key(pk: str) -> str:
    pk = pk.strip().strip('"').strip("'").replace("\r\n", "\n").replace("\\n", "\n")
    m = re.search(r"-----BEGIN PRIVATE KEY-----(.*?)-----END PRIVATE KEY-----", pk, re.S)
    if m:
        body = re.sub(r"\s+", "", m.group(1))
        lines = [body[i:i + 64] for i in range(0, len(body), 64)]
        return "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----\n"
    return pk


def doc_thong_tin_credentials():
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
        raise ValueError("Biến môi trường GOOGLE_CREDENTIALS đang trống!")

    try:
        tt = json.loads(raw_cred, strict=False)
    except Exception:
        decoded = base64.b64decode(raw_cred).decode("utf-8")
        tt = json.loads(decoded, strict=False)

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
        raise RuntimeError(f"Lỗi xác thực JWT với Key ID '{key_id}...': {e}") from e
    return creds


def quet_drive_va_gan_anh(sheet_id, drive_folder_id=None):
    print("Đang xác thực tài khoản Google Drive & Sheets...")
    creds = authenticate()
    gc = gspread.authorize(creds)
    drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)

    sheet = gc.open_by_url(sheet_id) if sheet_id.startswith("http") else gc.open_by_key(sheet_id)

    worksheet = None
    for ws in sheet.worksheets():
        ws_title_lower = ws.title.lower()
        if any(k in ws_title_lower for k in ("nganhang", "khochung", "cauhoid", "câu hỏi")):
            worksheet = ws
            break
    if not worksheet:
        worksheet = sheet.get_worksheet(0)

    print(f"Đã kết nối thành công tới tab: '{worksheet.title}'")

    # Đọc toàn bộ bảng dưới dạng danh sách 2 chiều để tránh lệch tên cột
    all_values = worksheet.get_all_values()
    if len(all_values) < 2:
        print("Bảng tính chưa có dữ liệu câu hỏi.")
        return

    header_row = all_values[0]
    print(f"Các cột trong bảng: {header_row}")

    # Tìm vị trí cột Nội dung, Phương án và cột Link Ảnh (tính từ 0)
    noi_dung_idx = None
    phuong_an_idx = None
    link_anh_col_idx = None  # tính từ 1 cho gspread update_cell

    for idx, title in enumerate(header_row):
        t_low = str(title).strip().lower()
        if t_low in ("nội dung", "noi dung", "câu hỏi", "cau hoi") or "nội dung" in t_low:
            noi_dung_idx = idx
        elif "phương án" in t_low or "phuong an" in t_low:
            phuong_an_idx = idx
        elif "link ảnh" in t_low or "link anh" in t_low:
            link_anh_col_idx = idx + 1

    if noi_dung_idx is None:
        # Dự phòng: cột C (index 2) thường là cột Nội dung trong NganHangCauHoi
        noi_dung_idx = 2
        print(f"⚠️ Không tìm thấy tên cột 'Nội dung', dùng mặc định cột số {noi_dung_idx + 1}")

    if not link_anh_col_idx:
        link_anh_col_idx = len(header_row) + 1
        worksheet.update_cell(1, link_anh_col_idx, "Link Ảnh")

    # Lọc trước các dòng câu hỏi cần hình ảnh (chưa có Link Ảnh)
    dong_can_hinh = []
    for row_num, row_vals in enumerate(all_values[1:], start=2):
        nd = row_vals[noi_dung_idx] if noi_dung_idx < len(row_vals) else ""
        pa = row_vals[phuong_an_idx] if (phuong_an_idx is not None and phuong_an_idx < len(row_vals)) else ""
        link_cu = row_vals[link_anh_col_idx - 1].strip() if (link_anh_col_idx - 1) < len(row_vals) else ""
        if not link_cu and RE_CAN_HINH.search(f"{nd} {pa}"):
            dong_can_hinh.append(row_num)

    print(f"🔎 Tìm thấy {len(dong_can_hinh)} câu hỏi cần gắn hình ảnh (ở các dòng: {dong_can_hinh[:20]}...)")
    if not dong_can_hinh:
        print("⚠️ Không có câu hỏi nào khớp dấu hiệu cần hình ảnh! Kết thúc sớm.")
        return

    os.makedirs("./temp_images", exist_ok=True)

    query = "mimeType = 'application/pdf' and trashed = false"
    if drive_folder_id:
        query += f" and '{drive_folder_id}' in parents"

    print("Đang quét các tệp PDF trên Google Drive...")
    results = drive_service.files().list(
        q=query,
        pageSize=100,
        fields="files(id, name, parents)",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True
    ).execute()
    files = results.get("files", [])
    print(f"Tìm thấy {len(files)} file PDF trên Google Drive.")

    # Lưu kèm thư mục cha của PDF để upload ảnh vào đúng thư mục đó (tránh lỗi 0GB quota của Service Account)
    danh_sach_anh = []  # mỗi phần tử: (local_path, parent_folder_id)

    for file in files:
        file_id = file["id"]
        file_name = file["name"]
        parent_id = drive_folder_id or ((file.get("parents") or [None])[0])
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
                    # Bỏ qua các ảnh rác/icon quá nhỏ (< 40x40 px)
                    if base_image.get("width", 100) < 40 or base_image.get("height", 100) < 40:
                        continue
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]

                    safe_name = re.sub(r'[\\/*?:"<>|]', "_", file_name)
                    image_name = f"{safe_name}_p{page_index+1}_img{img_index+1}.{image_ext}"
                    image_path = os.path.join("./temp_images", image_name)
                    with open(image_path, "wb") as img_file:
                        img_file.write(image_bytes)
                    danh_sach_anh.append((image_path, parent_id))
            pdf_document.close()
        except Exception as e:
            print(f"Lỗi khi đọc file {file_name}: {e}")

        # Nếu đã gom đủ số ảnh cho số câu hỏi cần hình thì dừng quét PDF để tiết kiệm thời gian
        if len(danh_sach_anh) >= len(dong_can_hinh):
            break

    print(f"🎉 Đã trích xuất tổng cộng {len(danh_sach_anh)} hình ảnh hợp lệ.")

    thay_doi_count = 0
    for anh_idx, row_num in enumerate(dong_can_hinh):
        if anh_idx >= len(danh_sach_anh):
            break
        local_img_path, target_folder_id = danh_sach_anh[anh_idx]
        img_file_name = os.path.basename(local_img_path)
        mime_type = mimetypes.guess_type(local_img_path)[0] or "image/png"

        try:
            file_metadata = {"name": img_file_name}
            if target_folder_id:
                file_metadata["parents"] = [target_folder_id]

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
            worksheet.update_cell(row_num, link_anh_col_idx, direct_img_link)
            print(f"✅ Đã upload và gán link ảnh cho dòng {row_num} -> {direct_img_link}")
            thay_doi_count += 1
        except Exception as e:
            print(f"❌ Lỗi xử lý/upload ảnh dòng {row_num}: {e}")

    print(f"✨ Hoàn tất quét bù! Đã cập nhật thành công hình ảnh cho {thay_doi_count} câu hỏi.")


if __name__ == "__main__":
    SHEET_ID = "1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc"
    DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID") or None

    quet_drive_va_gan_anh(SHEET_ID, DRIVE_FOLDER_ID)
