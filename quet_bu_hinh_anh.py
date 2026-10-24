import os
import re
import io
import json
import base64
import subprocess
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

import gspread
import google.auth.transport.requests
from google.auth.exceptions import RefreshError
from google.oauth2.service_account import Credentials

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
    
    sheet_cfg = config.get("SHEET_CONFIG", {})
    sheet_id = sheet_cfg.get("SHEET_ID")
    tab_keywords = sheet_cfg.get("tab_chap_nhan", ["nganhang"])

    print("Đang xác thực Google Sheets...")
    creds = authenticate()
    gc = gspread.authorize(creds)

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

    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    import io

    drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)
    drive_folder_id = sheet_cfg.get("DRIVE_FOLDER_ID") or os.environ.get("DRIVE_FOLDER_ID")

    query = "mimeType = 'application/pdf' and trashed = false"
    if drive_folder_id:
        query += f" and '{drive_folder_id}' in parents"

    results = drive_service.files().list(
        q=query, pageSize=100, fields="files(id, name, parents)",
        includeItemsFromAllDrives=True, supportsAllDrives=True
    ).execute()
    files = results.get("files", [])
    print(f"Tìm thấy {len(files)} file PDF trên Google Drive.")

    os.makedirs("images", exist_ok=True)
    min_w = config.get("BO_LOC_KY_THUAT", {}).get("min_width", 40)
    min_h = config.get("BO_LOC_KY_THUAT", {}).get("min_height", 40)

    thay_doi_count = 0
    for file in files:
        if not cau_hoi_can_xu_ly:
            break
        file_id = file["id"]
        file_name = file["name"]
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
                        best_img_filename = None
                        
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

                                safe_name = f"q{row_num}_{re.sub(r'[\\/*?:\"<>| ]', '_', file_name)}_p{page_index+1}_img{img_index+1}.{base_image['ext']}"
                                image_path = os.path.join("images", safe_name)
                                with open(image_path, "wb") as f:
                                    f.write(base_image["image"])
                                best_img_filename = safe_name
                                break

                        if best_img_filename:
                            direct_link = f"https://raw.githubusercontent.com/vatli-xuong/vatli-xuong/main/images/{best_img_filename}"
                            worksheet.update_cell(row_num, link_anh_col_idx, direct_link)
                            print(f"✅ [GitHub Storage] Gán link dòng {row_num} -> {direct_link}")
                            thay_doi_count += 1
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

    if thay_doi_count > 0:
        try:
            print("Đang đồng bộ và đẩy hình ảnh lên kho GitHub...")
            subprocess.run(["git", "config", "--global", "user.name", "agent-bot"], check=True)
            subprocess.run(["git", "config", "--global", "user.email", "agent-bot@users.noreply.github.com"], check=True)
            subprocess.run(["git", "add", "images/"], check=True)
            subprocess.run(["git", "commit", "-m", f"Auto-update extracted physics question images ({thay_doi_count} images)"], check=True)
            subprocess.run(["git", "push"], check=True)
            print("✨ Đã đẩy ảnh lên GitHub thành công tuyệt đối!")
        except Exception as e:
            print(f"⚠️ Lưu ý khi push Git: {e}")

    print(f"✨ Hoàn tất! Đã cập nhật chính xác {thay_doi_count} hình ảnh vào bảng.")

if __name__ == "__main__":
    quet_drive_va_gan_anh()
