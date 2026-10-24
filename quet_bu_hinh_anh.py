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
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

try:
    import pymupdf as fitz
except ImportError:
    import fitz

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly"
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

def authenticate():
    raw_cred = os.environ.get("GOOGLE_CREDENTIALS", "").strip()
    if not raw_cred and os.path.isfile("credentials.json"):
        with open("credentials.json", "r", encoding="utf-8") as f:
            raw_cred = f.read().strip()
    if not raw_cred:
        raise ValueError("Biến môi trường GOOGLE_CREDENTIALS đang trống!")
    try:
        tt = json.loads(raw_cred, strict=False)
    except Exception:
        tt = json.loads(base64.b64decode(raw_cred).decode("utf-8"), strict=False)
    if "private_key" in tt:
        tt["private_key"] = tt["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(tt, scopes=SCOPES)
    creds.refresh(google.auth.transport.requests.Request())
    return creds

def quet_drive_va_gan_anh():
    config = doc_trung_tam_config()
    sheet_cfg = config.get("SHEET_CONFIG", {})
    sheet_id = os.environ.get("SHEET_ID") or sheet_cfg.get("SHEET_ID")

    print("Đang xác thực Google Sheets & Drive...", flush=True)
    creds = authenticate()
    gc = gspread.authorize(creds)
    drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)

    sh = gc.open_by_url(sheet_id) if sheet_id.startswith("http") else gc.open_by_key(sheet_id)
    worksheet = sh.worksheet("NganHangCauHoi")
    print(f"Đã kết nối chuẩn xác tab: '{worksheet.title}'", flush=True)

    all_values = worksheet.get_all_values()
    if len(all_values) < 2:
        print("Bảng tính chưa có dữ liệu câu hỏi.")
        return

    patterns = config.get("BO_LOC_KY_THUAT", {}).get("bieu_thuc_nhan_dien_hinh", [])
    RE_CAN_HINH = re.compile("|".join(patterns), re.IGNORECASE) if patterns else re.compile(r"Hình|Đồ thị|Mạch điện", re.IGNORECASE)

    # Gom nhóm các câu cần hình theo File ID gốc ở Cột R (index 17)
    nhom_theo_file = {}
    for row_num, row_vals in enumerate(all_values[1:], start=2):
        row_vals = (row_vals + [""] * 23)[:23]
        nd = row_vals[6].strip()          # Cột G: Nội dung
        ten_file_cau = row_vals[15].strip() # Cột P: Tên file (câu X)
        file_id = row_vals[17].strip()    # Cột R: File ID gốc
        trang_thai = row_vals[20].strip() # Cột U: Trạng thái
        link_cu = row_vals[22].strip()    # Cột W: Link ảnh

        if trang_thai == "Loại" or link_cu or not file_id:
            continue
        if RE_CAN_HINH.search(nd):
            clean_snippet = re.sub(r"\$.*?\$", "", nd)
            clean_snippet = re.sub(r"\[.*?\]", "", clean_snippet).strip()
            snippet = clean_snippet[:35].strip()
            m_so = re.search(r"\(câu\s*([^)]+)\)", ten_file_cau, re.I)
            so_cau = m_so.group(1).strip() if m_so else ""
            nhom_theo_file.setdefault(file_id, []).append({
                "row": row_num,
                "snippet": snippet,
                "so_cau": so_cau
            })

    tong_cau = sum(len(v) for v in nhom_theo_file.values())
    print(f"🔎 Tìm thấy {tong_cau} câu hỏi cần trích xuất hình ảnh từ {len(nhom_theo_file)} file đề gốc.", flush=True)
    if not tong_cau:
        return

    os.makedirs("images", exist_ok=True)
    min_w = config.get("BO_LOC_KY_THUAT", {}).get("min_width", 40)
    min_h = config.get("BO_LOC_KY_THUAT", {}).get("min_height", 40)

    cap_nhat_sheet = []
    thay_doi_count = 0

    for file_id, ds_cau in nhom_theo_file.items():
        try:
            meta = drive_service.files().get(fileId=file_id, fields="name,mimeType", supportsAllDrives=True).execute()
            mime = meta.get("mimeType", "")
            file_name = meta.get("name", file_id[:8])
            if mime == "application/vnd.google-apps.document":
                req = drive_service.files().export_media(fileId=file_id, mimeType="application/pdf")
            elif mime == "application/pdf":
                req = drive_service.files().get_media(fileId=file_id, supportsAllDrives=True)
            else:
                continue

            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, req)
            done = False
            while not done:
                _, done = downloader.next_chunk()

            pdf_document = fitz.open(stream=fh.getvalue(), filetype="pdf")
            for item in ds_cau:
                row_num = item["row"]
                snippet = item["snippet"]
                so_cau = item["so_cau"]
                matched = False

                for page_index in range(len(pdf_document)):
                    page = pdf_document[page_index]
                    text_instances = page.search_for(snippet) if len(snippet) >= 8 else []
                    if not text_instances and so_cau:
                        text_instances = page.search_for(f"Câu {so_cau}")

                    if text_instances:
                        q_y = text_instances[0].y1
                        for img_index, img in enumerate(page.get_images(full=True)):
                            xref = img[0]
                            rects = page.get_image_rects(xref)
                            if not rects:
                                continue
                            img_y = rects[0].y0
                            if q_y - 30 <= img_y <= q_y + 380:
                                base_image = pdf_document.extract_image(xref)
                                w, h = base_image.get("width", 0), base_image.get("height", 0)
                                if w < min_w or h < min_h or w > 1600 or h > 1600:
                                    continue
                                safe_name = f"q{row_num}_{re.sub(r'[^a-zA-Z0-9_-]', '_', file_name)[:30]}_p{page_index+1}_img{img_index+1}.{base_image['ext']}"
                                image_path = os.path.join("images", safe_name)
                                with open(image_path, "wb") as f:
                                    f.write(base_image["image"])
                                direct_link = f"https://raw.githubusercontent.com/vatli-xuong/vatli-xuong/main/images/{safe_name}"
                                cap_nhat_sheet.append({"range": f"W{row_num}", "values": [[direct_link]]})
                                print(f"✅ Dòng {row_num} -> {direct_link}", flush=True)
                                thay_doi_count += 1
                                matched = True
                                break
                    if matched:
                        break
            pdf_document.close()
        except Exception as e:
            print(f"⚠️ Không đọc được PDF ({file_id[:10]}): {e}", flush=True)

    if cap_nhat_sheet:
        worksheet.batch_update(cap_nhat_sheet, value_input_option="RAW")

    if thay_doi_count > 0:
        try:
            subprocess.run(["git", "config", "--global", "user.name", "agent-bot"], check=True)
            subprocess.run(["git", "config", "--global", "user.email", "agent-bot@users.noreply.github.com"], check=True)
            subprocess.run(["git", "add", "images/"], check=True)
            subprocess.run(["git", "commit", "-m", f"Auto-update {thay_doi_count} extracted physics images"], check=True)
            subprocess.run(["git", "push"], check=True)
            print("✨ Đã đẩy toàn bộ ảnh mới lên GitHub thành công!")
        except Exception as e:
            print(f"⚠️ Lưu ý khi push Git: {e}")

    print(f"✨ Hoàn tất! Đã cập nhật {thay_doi_count} hình ảnh vào Cột W.")

if __name__ == "__main__":
    quet_drive_va_gan_anh()
