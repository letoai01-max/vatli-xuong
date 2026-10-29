"""
kiem_dinh_de.py – XƯỞNG KIỂM ĐỊNH ĐỀ (Python, GitHub Actions) cho AGENT TẠO ĐỀ – dùng cong_chat_luong.py.

Cùng mẫu "gói việc" với de_cuong.py:
  Apps Script (NoiCongChatLuong.gs, dự án Tạo đề) ghi goi_<mã>.json (tên đề, toàn văn đề + đáp án) và ket_qua_<mã>.json
  vào thư mục _Xuong_Python, chia quyền sửa cho tài khoản dịch vụ, rồi gửi lệnh chạy kiem_dinh_de.yml.
  Xưởng tách phần ĐỀ và phần ĐÁP ÁN, chạy cổng chất lượng 2 bằng chứng (cong_chat_luong.kiem_dinh):
    bằng chứng 1 = đáp án của agent; bằng chứng 2 = một model khác, KHÔNG xem đáp án, giải lại bằng code.
  Kết quả ghi vào ket_qua_<mã>.json; Apps Script tự nhận, ghi tab "Kiểm định máy" và gửi mail.
CHỈ BÁO CÁO: không sửa đề, không chặn xuất đề (cổng xuất 2 lớp của agent giữ nguyên).
Biến môi trường: GOOGLE_CREDENTIALS, GEMINI_API_KEY (_2, _3), GOI_ID, KQ_ID.
"""
import datetime as dt, io, json, os, re

from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

import doc_de as X
import cong_chat_luong as CCL
try:
    import quota_xuong as Q
except Exception:
    Q = None

RE_DAP_AN = re.compile(r"(?im)^\s*(?:#+\s*)?(?:[IVX]+\.\s*|PHẦN\s+[IVX\d]+\s*[.:–-]?\s*)?"
                       r"(?:ĐÁP\s*ÁN(?:\s+VÀ\s+HƯỚNG\s+DẪN\s+(?:CHẤM|GIẢI))?|HƯỚNG\s+DẪN\s+(?:CHẤM|GIẢI)|BẢNG\s+ĐÁP\s+ÁN)\b.*$")


def doc_tep(drive, fid):
    buf = io.BytesIO()
    tai = MediaIoBaseDownload(buf, drive.files().get_media(fileId=fid))
    xong = False
    while not xong:
        _, xong = tai.next_chunk()
    return json.loads(buf.getvalue().decode("utf-8") or "{}")


def ghi_tep(drive, fid, du_lieu):
    media = MediaIoBaseUpload(io.BytesIO(json.dumps(du_lieu, ensure_ascii=False).encode("utf-8")), mimetype="text/plain")
    drive.files().update(fileId=fid, media_body=media).execute()


def tach_de_dap_an(van_ban):
    """Phần đề = trước tiêu đề "ĐÁP ÁN / HƯỚNG DẪN CHẤM" CUỐI CÙNG đứng riêng một dòng; phần sau là đáp án."""
    ds = list(RE_DAP_AN.finditer(van_ban or ""))
    if not ds:
        return van_ban, ""
    m = ds[-1] if ds[-1].start() > len(van_ban) * 0.3 else ds[0]
    return van_ban[:m.start()].strip(), van_ban[m.start():].strip()


def goi_gemini(he, nguoi, co_code, cac_model):
    """Chữ ký mà cong_chat_luong.py cần: (hệ thống, lời nhắc, có chạy code?, danh sách model) → (chữ, model)."""
    payload = {"systemInstruction": {"parts": [{"text": he}]}, "contents": [{"role": "user", "parts": [{"text": nguoi}]}],
               "generationConfig": {"temperature": 0.2, "maxOutputTokens": 30000}}
    if co_code:
        payload["tools"] = [{"code_execution": {}}]
    data, model = X.goi_gemini(payload, cac_model)
    cand = (data.get("candidates") or [{}])[0]
    return "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []) if not p.get("thought")), model


def main():
    gc, drive, sa = ket_noi_ghi()
    print("Tài khoản dịch vụ:", sa, flush=True)
    goi_id, kq_id = os.environ["GOI_ID"], os.environ["KQ_ID"]
    goi = doc_tep(drive, goi_id)
    ghi_tep(drive, kq_id, {"trangThai": "DANG_LAM", "luc": dt.datetime.now(X.TZ).isoformat()})
    try:
        cac_model = X.doc_cau_hinh(gc.open_by_key(X.ID_KHO_CHUNG))
        de, dap_an = tach_de_dap_an(goi.get("vanBan", ""))
        print("Đề: %s – %d kí tự đề, %d kí tự đáp án; model: %s" % (goi.get("ten"), len(de), len(dap_an), ", ".join(cac_model)), flush=True)
        if not dap_an:
            print("⚠️ Không thấy tiêu đề ĐÁP ÁN / HƯỚNG DẪN CHẤM – gửi toàn văn làm cả đề và đáp án.", flush=True)
            dap_an = de
        bao_cao, tom_tat, bang_chung = CCL.kiem_dinh(goi_gemini, de, dap_an, cac_model, cac_model[0])
        ghi_tep(drive, kq_id, {"trangThai": "XONG", "baoCao": bao_cao, "tomTat": tom_tat, "bangChung": bang_chung,
                               "luc": dt.datetime.now(X.TZ).isoformat()})
        print("📦 %s" % json.dumps(tom_tat, ensure_ascii=False), flush=True)
    except X.HetHanMuc as e:
        ghi_tep(drive, kq_id, {"trangThai": "HOAN", "loi": str(e)[:300], "luc": dt.datetime.now(X.TZ).isoformat()})
        print("⏸️ Hết hạn mức Gemini – Apps Script sẽ gửi lại sau:", str(e)[:150])
    except Exception as e:
        ghi_tep(drive, kq_id, {"trangThai": "LOI", "loi": str(e)[:500], "luc": dt.datetime.now(X.TZ).isoformat()})
        raise
    finally:
        if Q:
            Q.ghi_sheet()


def ket_noi_ghi():
    """Như doc_de.ket_noi nhưng có quyền SỬA tệp Drive (ghi ket_qua)."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    import gspread
    tt = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    cred = service_account.Credentials.from_service_account_info(
        tt, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(cred), build("drive", "v3", credentials=cred, cache_discovery=False), tt.get("client_email", "")


if __name__ == "__main__":
    main()
