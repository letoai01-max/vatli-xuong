import os
import sys
import json
import base64
import runpy

THU_MUC_GOC = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(THU_MUC_GOC, "trung_tam_dieu_phoi.json")

if os.path.isfile(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            _cfg = json.load(f)
            sheet_cfg = _cfg.get("SHEET_CONFIG", {})
            if sheet_cfg.get("SHEET_ID"):
                os.environ["SHEET_ID"] = str(sheet_cfg["SHEET_ID"])
    except Exception:
        pass

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
        print("✅ [Trung tâm]: Đã chuẩn hóa và khởi tạo credentials.json thành công.")
    except Exception as e:
        print(f"⚠️ [Trung tâm]: Lỗi xử lý GOOGLE_CREDENTIALS: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        ten_tep = os.path.basename(sys.argv[1])
        muc_tieu = os.path.join(THU_MUC_GOC, ten_tep)
        print(f"🚀 [Trung tâm]: Đang chạy file -> {ten_tep}", flush=True)
        sys.argv = [muc_tieu] + sys.argv[2:]
        runpy.run_path(muc_tieu, run_name="__main__")
    else:
        print("✅ [Trung tâm]: Khởi động thành công.")
