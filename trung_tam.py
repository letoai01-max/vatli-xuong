import os
import sys
import json
import base64
import runpy
import signal
import datetime

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


# ====================== ĐIỀU PHỐI PHÚT GITHUB ACTIONS (2.000 phút/tháng) ======================
# Mọi việc của xưởng đi qua đây nên đây là điểm duy nhất cần gọi quota_phut.py: TRƯỚC việc → hỏi "được chạy không, tối đa bao nhiêu phút";
# SAU việc → ghi tab Quota_Phut và báo Telegram. Công tắc CONG_TAC.DIEU_PHOI_PHUT trong trung_tam_dieu_phoi.json (hoặc QUOTA_PHUT_CHE_DO=tat).
# Mọi lỗi của phần này chỉ cảnh báo, không bao giờ làm hỏng việc chính (trừ khi hết hạn mức tháng: khi đó việc bị hoãn/từ chối có chủ ý).
class HetGio(BaseException):
    """Hết phần phút được phân bổ (BaseException để các khối `except Exception` của tệp việc không nuốt mất)."""


def _nap_dieu_phoi():
    try:
        if not _cfg.get("CONG_TAC", {}).get("DIEU_PHOI_PHUT", True):
            print("ℹ️ [Trung tâm]: DIEU_PHOI_PHUT đang tắt, chạy không giới hạn phút.", flush=True)
            return None
        import quota_phut as QP
        return None if QP.CHE_DO == "tat" else QP
    except Exception as e:
        print(f"⚠️ [Trung tâm]: Không nạp được quota_phut ({type(e).__name__}: {e}); chạy không giới hạn phút.", flush=True)
        return None


def _ghi_summary(dong):
    try:
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
                f.write("\n".join(dong) + "\n")
    except Exception:
        pass


def _ap_gioi_han(q):
    """Truyền trần phút xuống tệp việc qua biến môi trường mà các tệp việc đã đọc sẵn (chỉ HẠ, không nâng)."""
    os.environ["QUOTA_PHUT_DA_DIEU_PHOI"] = "1"
    os.environ["QUOTA_PHUT_GIOI_HAN"] = "%g" % q["phut"]
    for ten in ("THOI_GIAN_TOI_DA_PHUT", "HAN_TONG_PHUT", "HAN_CUNG_PHUT"):
        try:
            cu = float(os.environ[ten]) if os.environ.get(ten, "").strip() else None
        except ValueError:
            cu = None
        os.environ[ten] = "%g" % (min(cu, q["phut"]) if cu is not None else q["phut"])


def _bao_loi_cho_apps_script(ly_do):
    """Việc theo yêu cầu bị từ chối vì hết hạn mức tháng → ghi ket_qua = LOI để Apps Script quay về cách soạn cũ thay vì chờ."""
    kq_id = os.environ.get("KQ_ID", "").strip()
    if not (kq_id and CRED_OK):
        return
    try:
        import io
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseUpload
        cred = service_account.Credentials.from_service_account_info(
            json.loads(os.environ["GOOGLE_CREDENTIALS"]), scopes=["https://www.googleapis.com/auth/drive"])
        drive = build("drive", "v3", credentials=cred, cache_discovery=False)
        luc = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).isoformat()
        nd = {"trangThai": "LOI", "loi": ("Hết hạn mức phút GitHub Actions: " + ly_do)[:500], "luc": luc}
        drive.files().update(fileId=kq_id, media_body=MediaIoBaseUpload(
            io.BytesIO(json.dumps(nd, ensure_ascii=False).encode("utf-8")), mimetype="text/plain")).execute()
        print("ℹ️ [Trung tâm]: Đã ghi ket_qua = LOI để Apps Script soạn lại bằng đường cũ.", flush=True)
    except Exception as e:
        print(f"⚠️ [Trung tâm]: Không ghi được ket_qua LOI ({type(e).__name__}: {str(e)[:100]}).", flush=True)


def _dat_dong_ho_cung(giay):
    """Chốt chặn cuối cho việc định kì: quá trần + vài phút mà tệp việc vẫn chưa tự dừng thì ngắt (tệp việc đều lưu tiến độ từng phần)."""
    if giay <= 0 or not hasattr(signal, "SIGALRM"):
        return False
    def _het(signum, frame):
        raise HetGio()
    try:
        signal.signal(signal.SIGALRM, _het)
        signal.setitimer(signal.ITIMER_REAL, giay)
        return True
    except (ValueError, OSError):
        return False


def chay_viec(ten_tep, muc_tieu):
    QP = _nap_dieu_phoi() if ten_tep != "quota_phut.py" else None      # quota_phut.py tự ghi số liệu, không bị giới hạn
    q = None
    if QP:
        try:
            mac = float(os.environ["THOI_GIAN_TOI_DA_PHUT"]) if os.environ.get("THOI_GIAN_TOI_DA_PHUT", "").strip() else None
            q = QP.quyet_dinh(QP.viec_tu_tep(ten_tep), mac)
        except Exception as e:
            print(f"⚠️ [Trung tâm]: Lỗi điều phối phút ({type(e).__name__}: {str(e)[:100]}); chạy như cũ.", flush=True)
    if q:
        ten_loai = {"khan": "khẩn", "yeu_cau": "theo yêu cầu", "dinh_ky": "định kì"}[q["loai_hieu_luc"]]
        dong = [f"### ⏱️ Điều phối phút – việc `{q['viec']}` (mức {q['muc']}/5, {ten_loai})"]
        dong.append(("- ✅ Được chạy, tối đa **%g phút**." % q["phut"]) + ((" " + q["ly_do"]) if q["ly_do"] else "")
                    if q["cho_chay"] else "- ⏸️ **Hoãn lượt này**: " + q["ly_do"])
        if q["ke"] and q["tt"]:
            dong += ["- " + d for d in QP.tom_tat(q["tt"], q["ke"])]
        for d in dong:
            print(d.replace("### ", "⏱️ ").replace("**", ""), flush=True)
        _ghi_summary(dong)
    try:
        if q and not q["cho_chay"]:
            if q["loai_hieu_luc"] == "dinh_ky":
                print("⏸️ [Trung tâm]: Việc định kì được hoãn, sẽ tự chạy lại khi ngân sách phút cho phép.", flush=True)
                return
            _bao_loi_cho_apps_script(q["ly_do"])
            sys.exit("Hết hạn mức phút GitHub Actions: " + q["ly_do"])
        co_dong_ho = False
        if q:
            _ap_gioi_han(q)
            if q["loai_hieu_luc"] == "dinh_ky" and q["co_so_lieu"]:
                co_dong_ho = _dat_dong_ho_cung((q["phut"] + float(os.environ.get("GH_HAN_CUNG_THEM", "3"))) * 60)
        try:
            runpy.run_path(muc_tieu, run_name="__main__")
        except HetGio:
            print(f"⏱️ [Trung tâm]: {ten_tep} hết phần phút được phân bổ ({q['phut']:g} phút + dung sai) – dừng, phần dở dang làm tiếp ở lượt sau.", flush=True)
        finally:
            if co_dong_ho:
                signal.setitimer(signal.ITIMER_REAL, 0)
    finally:
        if QP:
            try:
                QP.cap_nhat()
            except Exception as e:
                print(f"⚠️ [Trung tâm]: Không cập nhật số phút ({type(e).__name__}).", flush=True)


if __name__ == "__main__":
    nap_cau_hinh_dong()
    if len(sys.argv) > 1:
        ten_tep = os.path.basename(sys.argv[1])
        muc_tieu = os.path.join(THU_MUC_GOC, ten_tep)
        print(f"🚀 [Trung tâm]: Đang chạy file -> {ten_tep}", flush=True)
        sys.argv = [muc_tieu] + sys.argv[2:]
        chay_viec(ten_tep, muc_tieu)
    else:
        print("✅ [Trung tâm]: Khởi động thành công.")
