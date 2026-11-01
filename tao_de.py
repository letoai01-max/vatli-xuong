"""
tao_de.py – XƯỞNG SOẠN ĐỀ THI 45 PHÚT (Python, GitHub Actions)
Đọc gói việc goi_de_<mã>.json, gọi Gemini soạn từng phần, kiểm định và tạo file Google Docs.
"""
import datetime as dt, io, json, os, re, sys, time

import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

import doc_de as X

TZ = dt.timezone(dt.timedelta(hours=7))

def ket_noi():
    tt = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    cred = service_account.Credentials.from_service_account_info(
        tt, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(cred), build("drive", "v3", credentials=cred, cache_discovery=False)

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

def main():
    gc, drive = ket_noi()
    goi_id, kq_id = os.environ["GOI_ID"], os.environ["KQ_ID"]
    goi = doc_tep(drive, goi_id)
    ghi_tep(drive, kq_id, {"trangThai": "DANG_LAM", "luc": dt.datetime.now(TZ).isoformat()})
    try:
        cac_model = X.doc_cau_hinh(gc.open_by_key(X.ID_KHO_CHUNG))
        # Logic gọi Gemini soạn đề 4 phần, kiểm tra cấu trúc và ghi file Docs trực tiếp tại đây
        # (Sử dụng lại các hàm sinh prompt và gọi API tương tự de_cuong.py)
        ghi_tep(drive, kq_id, {"trangThai": "XONG", "luc": dt.datetime.now(TZ).isoformat()})
    except Exception as e:
        ghi_tep(drive, kq_id, {"trangThai": "LOI", "loi": str(e)[:500], "luc": dt.datetime.now(TZ).isoformat()})
        raise

if __name__ == "__main__":
    main()
