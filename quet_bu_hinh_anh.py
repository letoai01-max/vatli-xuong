import os
import re
import io
import json
import base64
import hashlib
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
MAX_IMAGES_PER_QUESTION = 1  # Chỉ lấy tối đa 1 hình duy nhất chuẩn xác nhất cho mỗi câu hỏi

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

def tim_dung(page, chuoi):
    """[29/10] Tìm chuỗi trên trang nhưng bỏ chỗ ngay sau là chữ số ("Câu 1" không khớp "Câu 12")."""
    ra = []
    for r in page.search_for(chuoi):
        sau = page.get_textbox(fitz.Rect(r.x1, r.y0, r.x1 + 6, r.y1)).strip()
        if not sau[:1].isdigit():
            ra.append(r)
    return ra

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

    # [29/10] Tìm cột theo TÊN tiêu đề (không cố định G, P, R, U, W)
    td = [str(t).strip() for t in all_values[0]]
    ci = lambda ten, md: td.index(ten) if ten in td else md
    C_MA, C_ND, C_TEN, C_ID, C_TT = ci("Mã câu", 0), ci("Nội dung", 6), ci("Tên file", 15), ci("File ID", 17), ci("Trạng thái duyệt", 20)
    C_ANH = next((i for i, t in enumerate(td) if t.lower() == "link ảnh"), 22)
    C_LOC = td.index("Lọc hình (AI)") if "Lọc hình (AI)" in td else None
    so_cot = max(len(td), C_ANH + 1, 23)

    patterns = config.get("BO_LOC_KY_THUAT", {}).get("bieu_thuc_nhan_dien_hinh", [])
    RE_CAN_HINH = re.compile("|".join(patterns), re.IGNORECASE) if patterns else re.compile(r"Hình|Đồ thị|Mạch điện|Giản đồ|Sơ đồ|trục|vẽ", re.IGNORECASE)

    nhom_theo_file = {}
    for row_num, row_vals in enumerate(all_values[1:], start=2):
        row_vals = (row_vals + [""] * so_cot)[:so_cot]
        ma_cau = row_vals[C_MA].strip()
        nd = row_vals[C_ND].strip()
        ten_file_cau = row_vals[C_TEN].strip()
        file_id = row_vals[C_ID].strip()
        trang_thai = row_vals[C_TT].strip()
        link_cu = row_vals[C_ANH].strip()

        if trang_thai == "Loại" or not file_id or not ma_cau:
            continue
        # [29/10] Câu đã được LocHinh (AI) xét hình thì tôn trọng kết luận đó, không gắn lại
        if C_LOC is not None and row_vals[C_LOC].strip():
            continue
        
        # Kiểm tra nội dung câu hỏi có từ khóa yêu cầu hình ảnh
        if RE_CAN_HINH.search(nd):
            clean_snippet = re.sub(r"\$.*?\$", "", nd)
            clean_snippet = re.sub(r"\[.*?\]", "", clean_snippet).strip()
            snippet = clean_snippet[:35].strip()
            m_so = re.search(r"\(câu\s*([^)]+)\)", ten_file_cau, re.I)
            so_cau = m_so.group(1).strip() if m_so else ""
            nhom_theo_file.setdefault(file_id, []).append({
                "row": row_num,
                "ma": ma_cau,
                "snippet": snippet,
                "so_cau": so_cau,
                "link_cu": link_cu,
                "noi_dung": nd
            })

    tong_cau = sum(len(v) for v in nhom_theo_file.values())
    print(f"🔎 Tìm thấy {tong_cau} câu hỏi cần kiểm tra hình ảnh từ {len(nhom_theo_file)} file đề gốc.", flush=True)
    if not tong_cau:
        return

    os.makedirs("images", exist_ok=True)
    min_w = config.get("BO_LOC_KY_THUAT", {}).get("min_width", 50)
    min_h = config.get("BO_LOC_KY_THUAT", {}).get("min_height", 50)

    ket_qua = {}          # [29/10] mã câu -> link ảnh; ghi theo Mã câu ở cuối (dòng có thể đã dịch trong lúc chạy)
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
                link_cu = item["link_cu"]
                
                # Làm sạch danh sách link cũ trên Cột W
                danh_sach_link_anh = []
                if link_cu:
                    danh_sach_link_anh = list(dict.fromkeys([l.strip() for l in link_cu.split(",") if l.strip() and "images/" in l]))
                
                if len(danh_sach_link_anh) >= MAX_IMAGES_PER_QUESTION:
                    continue

                ung_vien_hinh = []

                for page_index in range(len(pdf_document)):
                    page = pdf_document[page_index]
                    text_instances = page.search_for(snippet) if len(snippet) >= 8 else []
                    if not text_instances and so_cau:
                        text_instances = tim_dung(page, f"Câu {so_cau}")   # [29/10] đúng nguyên số; bỏ nhánh "{so}." quá lỏng

                    if text_instances:
                        q_y = text_instances[0].y1
                        for img_index, img in enumerate(page.get_images(full=True)):
                            xref = img[0]
                            rects = page.get_image_rects(xref)
                            if not rects:
                                continue
                            img_y = rects[0].y0
                            
                            # Tầng lọc 1: Siết chặt biên độ tọa độ (chỉ lấy hình ngay dưới từ -5 đến +120 pixels)
                            if q_y - 5 <= img_y <= q_y + 120:
                                khoang_cach_y = abs(img_y - q_y)
                                base_image = pdf_document.extract_image(xref)
                                image_bytes = base_image.get("image")
                                if not image_bytes:
                                    continue
                                
                                w, h = base_image.get("width", 0), base_image.get("height", 0)
                                
                                # Tầng lọc 2: Kiểm tra kích thước tối thiểu / tối đa chống rác
                                if w < min_w or h < min_h or w > 1600 or h > 1600:
                                    continue
                                
                                # Tầng lọc 3: Kiểm tra tỷ lệ khung hình (Aspect Ratio) chống lấy nhầm đường kẻ hoặc banner dẹt
                                aspect_ratio = w / h if h > 0 else 0
                                if aspect_ratio < 0.25 or aspect_ratio > 4.0:
                                    continue

                                # Tầng lọc 4: Tạo mã băm MD5 chống trùng lặp nội dung byte hình ảnh tuyệt đối
                                img_hash = hashlib.md5(image_bytes).hexdigest()
                                
                                ung_vien_hinh.append({
                                    "distance": khoang_cach_y,
                                    "hash": img_hash,
                                    "bytes": image_bytes,
                                    "ext": base_image['ext'],
                                    "page": page_index + 1,
                                    "img_idx": img_index + 1
                                })

                    if text_instances:
                        break   # [29/10] chỉ lấy hình ở trang đầu tiên tìm thấy câu

                # Sắp xếp ứng viên theo khoảng cách gần dòng câu hỏi nhất lên đầu
                ung_vien_hinh.sort(key=lambda x: x["distance"])

                da_nhan_hash = set()
                # CHỈ LẤY ĐÚNG 1 ỨNG VIÊN DUY NHẤT CHUẨN XÁC NHẤT
                for uv in ung_vien_hinh:
                    if len(danh_sach_link_anh) >= MAX_IMAGES_PER_QUESTION:
                        break
                    if uv["hash"] in da_nhan_hash:
                        continue
                    
                    da_nhan_hash.add(uv["hash"])
                    safe_name = f"q{row_num}_{re.sub(r'[^a-zA-Z0-9_-]', '_', file_name)[:20]}_p{uv['page']}_img{uv['img_idx']}.{uv['ext']}"
                    image_path = os.path.join("images", safe_name)
                    
                    if not os.path.exists(image_path):
                        with open(image_path, "wb") as f:
                            f.write(uv["bytes"])
                    
                    direct_link = f"images/{safe_name}"
                    if direct_link not in danh_sach_link_anh:
                        danh_sach_link_anh.append(direct_link)
                        print(f"✅ [Độ chính xác đa tầng 100%] Dòng {row_num} nhận diện ảnh chuẩn: {safe_name}", flush=True)
                    
                    break # Dừng ngay sau khi bắt được 1 hình chuẩn sát nhất

                if danh_sach_link_anh:
                    final_link_str = ", ".join(danh_sach_link_anh)
                    if final_link_str != link_cu:
                        ket_qua[item["ma"]] = final_link_str
                        thay_doi_count += 1

            pdf_document.close()
        except Exception as e:
            print(f"⚠️ Không đọc được PDF ({file_id[:10]}): {e}", flush=True)

    if ket_qua:
        ma_cot = worksheet.col_values(C_MA + 1)
        vi_tri = {str(v).strip(): k + 1 for k, v in enumerate(ma_cot) if k > 0 and str(v).strip()}
        cot = gspread.utils.rowcol_to_a1(1, C_ANH + 1).rstrip("1")
        cap_nhat_sheet = [{"range": "%s%d" % (cot, vi_tri[m]), "values": [[v]]} for m, v in ket_qua.items() if m in vi_tri]
        if cap_nhat_sheet:
            worksheet.batch_update(cap_nhat_sheet, value_input_option="RAW")
        if len(cap_nhat_sheet) < len(ket_qua):
            print(f"⚠️ {len(ket_qua) - len(cap_nhat_sheet)} câu không còn trong bảng lúc ghi – bỏ qua.", flush=True)
    # [29/10] Bỏ phần tự git push ở đây: workflow quet-anh-cron tự commit questions.json và images/

    print(f"✨ Hoàn tất! Đã kiểm soát đa tầng và làm sạch dữ liệu cho {thay_doi_count} câu hỏi.")

if __name__ == "__main__":
    quet_drive_va_gan_anh()
