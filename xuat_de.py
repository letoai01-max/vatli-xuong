import os
import io
import json
import requests
import warnings
import gspread
import google.auth.transport.requests
from google.auth.exceptions import RefreshError
from google.oauth2.service_account import Credentials
from docx import Document
from docx.shared import Inches

warnings.filterwarnings("ignore", category=FutureWarning)

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
        import base64
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

def xuat_du_lieu_va_de_thi():
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
        print("Bảng tính chưa có dữ liệu.")
        return

    # 1. Tự động xuất file questions.json cho trang web hiển thị kèm ảnh cột W
    danh_sach_json = []
    for row in all_values[1:]:
        ma_cau = row[0] if len(row) > 0 else ""
        noi_dung = row[1] if len(row) > 1 else "" # Cột G
        phuong_an = row[7] if len(row) > 7 else "" # Cột H
        dap_an = row[8] if len(row) > 8 else "" # Cột I
        trang_thai = row[20] if len(row) > 20 else "" # Cột U
        link_anh = row[22].strip() if len(row) > 22 else "" # Cột W
        
        if noi_dung:
            danh_sach_json.append({
                "ma_cau": ma_cau,
                "noi_dung": noi_dung,
                "phuong_an": phuong_an,
                "dap_an": dap_an,
                "trang_thai": trang_thai,
                "link_anh": link_anh
            })

    with open("questions.json", "w", encoding="utf-8") as f:
        json.dump(danh_sach_json, f, ensure_ascii=False, indent=4)
    print("✨ Đã xuất thành công tệp 'questions.json' cho web!")

    # 2. Tự động xuất tệp Word (DeThi.docx) từ cột W
    doc = Document()
    doc.add_heading("ĐỀ KIỂM TRA VẬT LÍ", level=1)

    for idx, item in enumerate(danh_sach_json, start=1):
        doc.add_paragraph(f"Câu {idx} [{item['ma_cau']}]: {item['noi_dung']}")
        
        # Tải và chèn ảnh từ cột W nếu có
        if item["link_anh"].startswith("http"):
            try:
                res = requests.get(item["link_anh"])
                if res.status_code == 200:
                    doc.add_picture(io.BytesIO(res.content), width=Inches(3.5))
            except Exception as e:
                print(f"Không tải được ảnh câu {idx}: {e}")
                
        if item["phuong_an"]:
            doc.add_paragraph(f"Phương án: {item['phuong_an']}")

    doc.save("DeThi.docx")
    print("✨ Đã xuất thành công tệp 'DeThi.docx'!")

if __name__ == "__main__":
    xuat_du_lieu_va_de_thi()
