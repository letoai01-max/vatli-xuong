import os
import sys
import json
import base64
import runpy

THU_MUC_GOC = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(THU_MUC_GOC, "trung_tam_dieu_phoi.json")

_cfg = {}
if os.path.isfile(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            _cfg = json.load(f)
            sheet_cfg = _cfg.get("SHEET_CONFIG", {})
            if sheet_cfg.get("SHEET_ID"):
                os.environ["SHEET_ID"] = str(sheet_cfg["SHEET_ID"])
    except Exception:
        pass

CRED_OK = False
raw_cred = os.environ.get("GOOGLE_CREDENTIALS", "").strip()
if raw_cred:
    try:
        # Thử giải mã nếu là Base64, nếu không phải thì coi như chuỗi JSON thuần
        if not raw_cred.startswith("{"):
            try:
                decoded_bytes = base64.b64decode(raw_cred + "==") # Thêm padding phòng hờ
                raw_cred = decoded_bytes.decode("utf-8")
            except Exception:
                pass
        
        tt = json.loads(raw_cred, strict=False)
        if "private_key" in tt:
            tt["private_key"] = tt["private_key"].replace("\\n", "\n")
        
        clean_json = json.dumps(tt, ensure_ascii=False)
        os.environ["GOOGLE_CREDENTIALS"] = clean_json
        
        # Ghi tệp credentials.json tạm thời để các thư viện Google gọi trực tiếp an toàn
        cred_path = os.path.join(THU_MUC_GOC, "credentials.json")
        with open(cred_path, "w", encoding="utf-8") as f:
            f.write(clean_json)
        CRED_OK = True
        print("✅ [Trung tâm]: Đã chuẩn hóa và khởi tạo credentials.json thành công.")
    except Exception as e:
        print(f"⚠️ [Trung tâm]: Lỗi xử lý GOOGLE_CREDENTIALS: {e}")


def nap_cau_hinh_dong():
    """Hàng 1: tự cập nhật tham số động từ tab CauHinhDong (cột KHOA, GIA_TRI) của Kho chung.
    Mỗi khóa được đặt thành biến môi trường CFG_<KHOA> và ghi vào cau_hinh_dong.json.
    Công tắc CHE_DO_DIEU_PHOI = false trong trung_tam_dieu_phoi.json → bỏ qua bước này.
    Mọi lỗi chỉ báo cảnh báo, không làm dừng việc chạy tệp đích."""
    if not _cfg.get("CONG_TAC", {}).get("CHE_DO_DIEU_PHOI", True):
        print("ℹ️ [Trung tâm]: CHE_DO_DIEU_PHOI đang tắt, bỏ qua nạp cấu hình động.", flush=True)
        return
    sheet_id = os.environ.get("SHEET_ID", "")
    if not (CRED_OK and sheet_id):
        print("ℹ️ [Trung tâm]: Thiếu khóa Google hoặc SHEET_ID, bỏ qua nạp cấu hình động.", flush=True)
        return
    try:
        import gspread
        from google.oauth2 import service_account
        cred = service_account.Credentials.from_service_account_info(
            json.loads(os.environ["GOOGLE_CREDENTIALS"]),
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
        gc = gspread.authorize(cred)
        try:
            gc.set_timeout(60)
        except Exception:
            pass
        try:
            ws = gc.open_by_key(sheet_id).worksheet("CauHinhDong")
        except gspread.WorksheetNotFound:
            print("ℹ️ [Trung tâm]: Chưa có tab CauHinhDong ở Kho chung, dùng cấu hình tĩnh.", flush=True)
            return
        du_lieu = {}
        for dong in ws.get_all_values()[1:]:
            if len(dong) >= 2 and dong[0].strip():
                khoa = dong[0].strip()
                du_lieu[khoa] = dong[1].strip()
                os.environ["CFG_" + khoa] = dong[1].strip()
        with open(os.path.join(THU_MUC_GOC, "cau_hinh_dong.json"), "w", encoding="utf-8") as f:
            json.dump(du_lieu, f, ensure_ascii=False, indent=2)
        print(f"✅ [Trung tâm]: Đã nạp {len(du_lieu)} tham số động từ Kho chung.", flush=True)
    except Exception as e:
        print(f"⚠️ [Trung tâm]: Không nạp được cấu hình động ({type(e).__name__}: {e}). Dùng cấu hình tĩnh.", flush=True)

if __name__ == "__main__":
    nap_cau_hinh_dong()
    if len(sys.argv) > 1:
        ten_tep = os.path.basename(sys.argv[1])
        muc_tieu = os.path.join(THU_MUC_GOC, ten_tep)
        print(f"🚀 [Trung tâm]: Đang chạy file -> {ten_tep}", flush=True)
        sys.argv = [muc_tieu] + sys.argv[2:]
        runpy.run_path(muc_tieu, run_name="__main__")
    else:
        print("✅ [Trung tâm]: Khởi động thành công.")
