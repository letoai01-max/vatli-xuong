"""
trung_tam.py – CENTRAL COORDINATOR (Trung tâm điều phối & Tự sửa lỗi - Tầng 3)
"""
import os
import re
import sys
import json
import base64
import runpy

CONFIG_FILE = "trung_tam_dieu_phoi.json"


def doc_cau_hinh():
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ [Trung tâm] Lỗi đọc {CONFIG_FILE}: {e}")
    return {}


def chuan_hoa_private_key(pk: str) -> str:
    pk = pk.strip().strip('"').strip("'").replace("\r\n", "\n").replace("\\n", "\n")
    m = re.search(r"-----BEGIN PRIVATE KEY-----(.*?)-----END PRIVATE KEY-----", pk, re.S)
    if m:
        body = re.sub(r"\s+", "", m.group(1))
        lines = [body[i:i + 64] for i in range(0, len(body), 64)]
        return "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----\n"
    return pk


def tu_sua_loi_credentials():
    """Tự động chuẩn hóa GOOGLE_CREDENTIALS để không bao giờ bị lỗi JWT hay Base64"""
    raw_cred = (
        os.environ.get("GOOGLE_CREDENTIALS")
        or os.environ.get("GCP_SA_KEY")
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or ""
    ).strip()

    if raw_cred and os.path.isfile(raw_cred):
        with open(raw_cred, "r", encoding="utf-8") as f:
            raw_cred = f.read().strip()

    if not raw_cred and os.path.isfile("credentials.json"):
        with open("credentials.json", "r", encoding="utf-8") as f:
            raw_cred = f.read().strip()

    if not raw_cred:
        return None

    try:
        tt = json.loads(raw_cred, strict=False)
    except Exception:
        decoded = base64.b64decode(raw_cred).decode("utf-8")
        tt = json.loads(decoded, strict=False)

    if "private_key" in tt:
        tt["private_key"] = chuan_hoa_private_key(tt["private_key"])

    os.environ["GOOGLE_CREDENTIALS"] = json.dumps(tt, ensure_ascii=False)
    return tt


def dieu_phoi_api(cfg):
    """Tự động kiểm tra và điều phối Key API ưu tiên"""
    api_cfg = cfg.get("HE_THONG_API", {})
    uu_tien = api_cfg.get("uu_tien_su_dung", ["GEMINI_API_KEY_TRA_PHI", "GEMINI_API_KEY"])

    if "toi_da_luot_tra_phi" in api_cfg and not os.environ.get("TOI_DA_LUOT_TRA_PHI"):
        os.environ["TOI_DA_LUOT_TRA_PHI"] = str(api_cfg["toi_da_luot_tra_phi"])

    for env_name in uu_tien:
        val = os.environ.get(env_name, "").strip()
        if val.startswith("AIza"):
            if not os.environ.get("GEMINI_API_KEY", "").strip().startswith("AIza"):
                os.environ["GEMINI_API_KEY"] = val
            print(f"🤖 [Trung tâm điều phối]: Sẵn sàng sử dụng khóa ưu tiên từ {env_name}")
            break


def tu_sua_giao_dien_cot(cfg, tt_cred):
    """Quét tiêu đề cột thực tế trên Google Sheet và tự sửa lại trung_tam_dieu_phoi.json nếu cột bị dịch chuyển"""
    if not tt_cred:
        return
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        sheet_id = cfg.get("SHEET_CONFIG", {}).get("SHEET_ID", "1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc")
        creds = Credentials.from_service_account_info(
            tt_cred, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
        )
        gc = gspread.authorize(creds)
        ws = gc.open_by_key(sheet_id).worksheet("NganHangCauHoi")
        header = ws.row_values(1)
        if not header:
            return

        gd_cot = cfg.get("GIAO_DIEN_COT", {})
        tk = gd_cot.get("tu_khoa_nhan_dien_cot", {})
        tk_nd = tk.get("noi_dung", ["nội dung", "câu hỏi"])
        tk_anh = tk.get("link_anh", ["link ảnh", "hình ảnh"])

        thay_doi = False
        for idx, col_name in enumerate(header, start=1):
            c_low = col_name.strip().lower()
            if any(k in c_low for k in tk_nd) and gd_cot.get("cot_noi_dung_index") != idx:
                gd_cot["cot_noi_dung_index"] = idx
                thay_doi = True
            elif any(k in c_low for k in tk_anh) and gd_cot.get("cot_link_anh_index") != idx:
                gd_cot["cot_link_anh_index"] = idx
                thay_doi = True

        if thay_doi:
            cfg["GIAO_DIEN_COT"] = gd_cot
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            print("🤖 [Trung tâm điều phối]: Phát hiện thay đổi cột trên Sheet -> Đã tự động cập nhật trung_tam_dieu_phoi.json!")
    except Exception as e:
        print(f"ℹ️ [Trung tâm]: Bỏ qua kiểm tra cột tự động ({e})")


_CFG = doc_cau_hinh()
_CRED = tu_sua_loi_credentials()
dieu_phoi_api(_CFG)

sheet_cfg = _CFG.get("SHEET_CONFIG", {})
SHEET_ID = sheet_cfg.get("SHEET_ID", "1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc")
DRIVE_FOLDER_ID = sheet_cfg.get("DRIVE_FOLDER_ID") or os.environ.get("DRIVE_FOLDER_ID")
os.environ["SHEET_ID"] = str(SHEET_ID)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        script_con = sys.argv[1]
        if script_con in ("quet_bu_hinh_anh.py", "doc_de.py", "duyet_cau.py"):
            tu_sua_giao_dien_cot(_CFG, _CRED)
        print(f"🚀 [Trung tâm điều phối]: Kích hoạt tác nhân '{script_con}'...")
        sys.argv = sys.argv[1:]
        runpy.run_path(script_con, run_name="__main__")
    else:
        tu_sua_giao_dien_cot(_CFG, _CRED)
        print("✅ [Trung tâm điều phối]: Kiểm tra hệ thống hoàn tất.")
