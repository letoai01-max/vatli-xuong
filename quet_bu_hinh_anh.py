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

TRUNG_TAM_CONFIG = "trung_tam_dieu_phoi.json"

def doc_trung_tam_config():
    if os.path.isfile(TRUNG_TAM_CONFIG):
        try:
            with open(TRUNG_TAM_CONFIG, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Không đọc được {TRUNG_TAM_CONFIG}: {e}")
    return {}

def dieu_phoi_api(config):
    api_keys_uu_tien = config.get("HE_THONG_API", {}).get("uu_tien_su_dung", ["GEMINI_API_KEY"])
    for env_name in api_keys_uu_tien:
        val = os.environ.get(env_name, "").strip()
        if val.startswith("AIza"):
            return val
    return ""

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
    creds = Credentials.from_service_account_info(tt, scopes=SCOPES)
    try:
        creds.refresh(google.auth.transport.requests.Request())
    except RefreshError as e:
        raise RuntimeError(f"Lỗi xác thực JWT: {e}") from e
    return creds

def quet_drive_va_gan_anh():
    config = doc_trung_tam_config()
    dieu_phoi_api(config)
    
    sheet_cfg = config.get("SHEET_CONFIG", {})
    sheet_id = sheet_cfg.get("SHEET_ID")
    drive_folder_id = sheet_cfg.get("DRIVE_FOLDER_ID") or os.environ.get("DRIVE_FOLDER_ID")
    tab_keywords = sheet_cfg.get("tab_chap_nhan", ["nganhang"])

    print("Đang xác thực tài khoản Google Drive & Sheets...")
    creds = authenticate()
    gc = gspread.authorize(creds)
    drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)

    sheet = gc.open_by_url(sheet_id) if sheet_id.startswith("http") else gc.open_by_key(sheet_id)

    worksheet = None
    for ws in sheet.worksheets():
        ws_title_lower = ws.title.lower()
        if any(k in ws_title_lower for k in tab_keywords):
            worksheet = ws
            break
    if not worksheet:
        worksheet = sheet.get_worksheet(0)

    print(f"Đã kết nối tab: '{worksheet.title}'")

    all_values = worksheet.get_all_values()
    if len(all_values) < 2:
        print("Bảng tính chưa có dữ liệu câu hỏi.")
        return

    link_anh_col_idx = 23
    giao_dien = config.get("GIAO_DIEN_COT", {})
    noi_dung_idx = giao_dien.get("cot_noi_dung_index", 2) - 1

    patterns = config.get("BO_LOC_KY_THUAT", {}).get("bieu_thuc_nhan_dien_hinh", [])
    RE_CAN_HINH = re.compile("|".join(patterns), re.IGNORECASE) if patterns else re.compile(r"Hình", re.IGNORECASE)

    cau_hoi_can_xu_ly = []
    for row_num, row_vals in enumerate(all_values[1:], start=2):
        nd = row_vals[noi_dung_idx] if noi_dung_idx < len(row_vals) else ""
        link_cu = row_vals[link_anh_col_idx - 1].strip() if (link_anh_col_idx - 1) < len(row_vals) else ""
        if not link_cu and RE_CAN_HINH.search(nd):
            clean_snippet = re.sub(r'\$.*?\$', '', nd).strip()
            clean_snippet = re.sub(r'\[.*?\]', '', clean_snippet).strip()
            snippet = clean_snippet[:30]
            cau_hoi_can_xu_ly.append({"row": row_num, "content": nd, "snippet": snippet})

    print(f"🔎 Tìm thấy {len(cau_hoi_can_xu_ly)} câu hỏi cần tìm hình ảnh theo tọa độ nội dung.")
    if not cau_hoi_can_xu_ly:
        print("⚠️ Không có câu hỏi nào khớp dấu hiệu cần hình ảnh!")
        return

    os.makedirs("./temp_images", exist_ok=True)
    min_w = config.get("BO_LOC_KY_THUAT", {}).get("min_width", 40)
    min_h = config.get("BO_LOC_KY_THUAT", {}).get("min_height", 40)

    query = "mimeType = 'application/pdf' and trashed = false"
    if drive_folder_id:
        query += f" and '{drive_folder_id}' in parents"

    results = drive_service.files().list(
        q=query, pageSize=100, fields="files(id, name, parents)",
        includeItemsFromAllDrives=True, supportsAllDrives=True
    ).execute()
    files = results.get("files", [])
    print(f"Tìm thấy {len(files)} file PDF trên Google Drive.")

    thay_doi_count = 0
    for file in files:
        if not cau_hoi_can_xu_ly:
            break
        file_id = file["id"]
        file_name = file["name"]
        parent_id = drive_folder_id or ((file.get("parents") or [None])[0])
        try:
            request = drive_service.files().get_media(fileId=file_id, supportsAllDrives=True)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

            fh.seek(0)
            pdf_document = fitz.open(stream=fh.read(), filetype="pdf")
            
            remain_questions = []
            for item in cau_hoi_can_xu_ly:
                matched = False
                snippet = item["snippet"]
                row_num = item["row"]

                if len(snippet) < 5:
                    remain_questions.append(item)
                    continue

                for page_index in range(len(pdf_document)):
                    page = pdf_document[page_index]
                    text_instances = page.search_for(snippet)
                    
                    if text_instances:
                        q_rect = text_instances[0]
                        q_y = q_rect.y1

                        page_images = page.get_images(full=True)
                        best_img_path = None
                        
                        for img_index, img in enumerate(page_images):
                            xref = img[0]
                            rects = page.get_image_rects(xref)
                            if not rects:
                                continue
                            img_rect = rects[0]
                            img_y = img_rect.y0

                            if q_y <= img_y <= q_y + 350:
                                base_image = pdf_document.extract_image(xref)
                                w = base_image.get("width", 100)
                                h = base_image.get("height", 100)
                                
                                if w < min_w or h < min_h or w > 1200 or h > 1500:
                                    continue

                                image_path = os.path.join("./temp_images", f"q{row_num}_{re.sub(r'[\\/*?:\"<>|]', '_', file_name)}_p{page_index+1}_img{img_index+1}.{base_image['ext']}")
                                with open(image_path, "wb") as f:
                                    f.write(base_image["image"])
                                best_img_path = image_path
                                break

                        if best_img_path:
                            try:
                                file_metadata = {"name": os.path.basename(best_img_path)}
                                if parent_id:
                                    file_metadata["parents"] = [parent_id]

                                # Truyền đầy đủ tham số hỗ trợ Shared Drive (corpora, includeItemsFromAllDrives) để né quota của service account
                                uploaded = drive_service.files().create(
                                    body=file_metadata, 
                                    media_body=MediaFileUpload(best_img_path, mimetype=mimetypes.guess_type(best_img_path)[0] or "image/png", resumable=True),
                                    fields="id", 
                                    supportsAllDrives=True
                                ).execute()

                                cloud_file_id = uploaded.get("id")

                                try:
                                    drive_service.permissions().create(
                                        fileId=cloud_file_id, body={"type": "anyone", "role": "reader"}, supportsAllDrives=True
                                    ).execute()
                                except Exception:
                                    pass

                                direct_link = f"https://lh3.googleusercontent.com/d/{cloud_file_id}"
                                worksheet.update_cell(row_num, link_anh_col_idx, direct_link)
                                print(f"✅ [Khớp tọa độ] Gán link dòng {row_num} -> {direct_link}")
                                thay_doi_count += 1
                                matched = True
                                break
                            except Exception as e:
                                print(f"❌ Lỗi upload ảnh dòng {row_num}: {e}")
                                matched = True
                                break

                    if matched:
                        break

                if not matched:
                    remain_questions.append(item)

            cau_hoi_can_xu_ly = remain_questions
            pdf_document.close()
        except Exception as e:
            print(f"Lỗi đọc file PDF {file_name}: {e}")

    print(f"✨ Hoàn tất! Đã ghép nối và cập nhật chính xác {thay_doi_count} hình ảnh vào bảng.")

if __name__ == "__main__":
    quet_drive_va_gan_anh()
