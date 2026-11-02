"""
tao_de.py – XƯỞNG SOẠN ĐỀ THI 45 PHÚT (Python, GitHub Actions)
Đọc gói việc goi_de_<mã>.json, gọi Gemini soạn đầy đủ 4 phần đề thi, kiểm định cấu trúc và ghi kết quả.
"""
import datetime as dt, io, json, os, re, sys, time

import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

import doc_de as X

TZ = dt.timezone(dt.timedelta(hours=7))

def ket_noi():
    import google.auth
    cred, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
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
    
    # Cập nhật trạng thái đang làm
    ghi_tep(drive, kq_id, {"trangThai": "DANG_LAM", "luc": dt.datetime.now(TZ).isoformat()})
    
    try:
        kho = gc.open_by_key(X.ID_KHO_CHUNG)
        cac_model = X.doc_cau_hinh(kho)
        
        grade = goi.get("grade", "10")
        b9 = goi.get("B9", "")
        
        system_instruction = (
            f"Bạn là AI Agent Khảo thí môn Vật lí THPT (Chương trình GDPT 2018, Kết nối tri thức). "
            f"Hãy soạn một đề kiểm tra vật lí lớp {grade} dựa trên yêu cầu cần đạt và phân bổ sau: {b9}. "
            f"Đề gồm 4 phần: Phần I (Trắc nghiệm nhiều lựa chọn), Phần II (Trắc nghiệm Đúng/Sai), "
            f"Phần III (Trả lời ngắn - kết quả là số), Phần IV (Tự luận - lời giải từng bước)."
        )
        
        prompt = "Hãy tiến hành soạn toàn bộ nội dung đề thi, các phương án lựa chọn và đáp án chi tiết theo đúng cấu trúc JSON yêu cầu."
        
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {
                "temperature": 0.3,
                "responseMimeType": "application/json",
                "maxOutputTokens": 65536
            }
        }
        
        print(f"Đang gọi Gemini soạn đề lớp {grade}...", flush=True)
        data, model = X.goi_gemini(payload, cac_model)
        cand = (data.get("candidates") or [{}])[0]
        text_res = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
        
        json_ket_qua = json.loads(text_res)
        
        # Ghi kết quả thành công vào file kết quả trên Drive
        ghi_tep(drive, kq_id, {
            "trangThai": "XONG",
            "model": model,
            "deThi": json_ket_qua,
            "luc": dt.datetime.now(TZ).isoformat()
        })
        print("✅ Xưởng Python đã soạn đề thành công!", flush=True)

    except Exception as e:
        err_msg = str(e)[:500]
        print(f"❌ Lỗi xưởng Python: {err_msg}", flush=True)
        ghi_tep(drive, kq_id, {
            "trangThai": "LOI",
            "loi": err_msg,
            "luc": dt.datetime.now(TZ).isoformat()
        })
        raise

if __name__ == "__main__":
    main()
