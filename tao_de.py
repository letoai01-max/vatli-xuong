"""
tao_de.py – XƯỞNG SOẠN ĐỀ THI 45 PHÚT (Python, GitHub Actions)
Đọc gói việc goi_de_<mã>.json, gọi Gemini soạn đầy đủ 4 phần đề thi, kiểm định cấu trúc và ghi kết quả.
[Sửa] Nêu rõ cấu trúc JSON cho Gemini (đúng các khóa mà NhanKetQuaXuong.gs đọc), kiểm tra cấu trúc trước khi ghi,
      đưa toàn bộ gói việc vào lời nhắc để không mất yêu cầu nào của Apps Script.
"""
import datetime as dt, io, json, os, re, sys, time

import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

import doc_de as X

TZ = dt.timezone(dt.timedelta(hours=7))

MAU_JSON = """{
  "mon_hoc": "Vật lí 10",
  "noi_dung": "tên đề / nội dung kiểm tra",
  "phan_I_trac_nghiem_nhieu_lua_chon": [
    {"cau": 1, "cau_hoi": "...", "lua_chon": {"A": "...", "B": "...", "C": "...", "D": "..."}, "dap_an": "B", "huong_dan_giai": "..."}
  ],
  "phan_II_trac_nghiem_dung_sai": [
    {"cau": 1, "noi_dung_dan": "...", "menh_de": {"a": "...", "b": "...", "c": "...", "d": "..."},
     "dap_an": {"a": true, "b": false, "c": true, "d": false}, "huong_dan_giai": "..."}
  ],
  "phan_III_tra_loi_ngan": [
    {"cau": 1, "cau_hoi": "...", "dap_an": "2,5", "huong_dan_giai": "..."}
  ],
  "phan_IV_tu_luan": [
    {"cau": 1, "cau_hoi": "...", "dap_an_chi_tiet": ["Bước 1: ...", "Bước 2: ..."]}
  ]
}"""


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


def kiem_tra_cau_truc(de):
    """Trả về (danh sách lỗi nặng – không dùng được, danh sách cảnh báo)."""
    nang, nhe = [], []
    if not isinstance(de, dict):
        return ["kết quả không phải một đối tượng JSON"], []
    p1, p2 = de.get("phan_I_trac_nghiem_nhieu_lua_chon"), de.get("phan_II_trac_nghiem_dung_sai")
    p3, p4 = de.get("phan_III_tra_loi_ngan"), de.get("phan_IV_tu_luan")
    for ten, v in (("phan_I_trac_nghiem_nhieu_lua_chon", p1), ("phan_II_trac_nghiem_dung_sai", p2),
                   ("phan_III_tra_loi_ngan", p3), ("phan_IV_tu_luan", p4)):
        if not isinstance(v, list):
            nang.append("thiếu mảng " + ten)
    for i, c in enumerate(p1 if isinstance(p1, list) else []):
        if not isinstance(c, dict) or not isinstance(c.get("lua_chon"), dict) or len(c["lua_chon"]) < 4 or not c.get("dap_an"):
            nang.append("Phần I câu %d thiếu lua_chon (đủ 4) hoặc dap_an" % (i + 1))
    for i, c in enumerate(p2 if isinstance(p2, list) else []):
        if not isinstance(c, dict) or not isinstance(c.get("menh_de"), dict) or not isinstance(c.get("dap_an"), dict) \
                or len(c["menh_de"]) < 4 or len(c["dap_an"]) < 4:
            nang.append("Phần II câu %d thiếu menh_de / dap_an đủ 4 ý" % (i + 1))
        elif sum(1 for v in c["dap_an"].values() if v is True) != 2:
            nhe.append("Phần II câu %d không đủ 2 Đúng – 2 Sai" % (i + 1))
    for i, c in enumerate(p3 if isinstance(p3, list) else []):
        if not isinstance(c, dict) or not str(c.get("dap_an", "")).strip():
            nang.append("Phần III câu %d thiếu dap_an" % (i + 1))
    for i, c in enumerate(p4 if isinstance(p4, list) else []):
        if not isinstance(c, dict) or not c.get("cau_hoi"):
            nang.append("Phần IV câu %d thiếu cau_hoi" % (i + 1))
    return nang, nhe


def doc_json(text):
    s = re.sub(r"```json|```", "", str(text or "")).strip()
    a, b = s.find("{"), s.rfind("}")
    if a != -1 and b > a:
        s = s[a:b + 1]
    return json.loads(s)


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
            f"Phần III (Trả lời ngắn - kết quả là số), Phần IV (Tự luận - lời giải từng bước). "
            f"Số câu mỗi phần theo đúng phân bổ ở trên. Phần II: mỗi câu có ĐÚNG 2 ý Đúng (true) và 2 ý Sai (false). "
            f"Phần I mỗi câu có đúng một đáp án đúng. Công thức viết bằng LaTeX trong dấu $...$. "
            f"CHỈ trả về MỘT đối tượng JSON, đúng tên khóa và đúng cấu trúc của mẫu sau (không thêm khóa khác, không bình luận):\n{MAU_JSON}"
        )

        goi_gon = json.dumps(goi, ensure_ascii=False)[:30000]
        prompt = ("Hãy tiến hành soạn toàn bộ nội dung đề thi, các phương án lựa chọn và đáp án chi tiết theo đúng cấu trúc JSON ở hướng dẫn hệ thống.\n"
                  "Toàn bộ yêu cầu của giáo viên (gói việc):\n" + goi_gon)

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
        json_ket_qua, model, canh_bao = None, "", []
        loi_cuoi = ""
        for lan in (1, 2):                      # cấu trúc sai thì cho soạn lại 1 lần, kèm danh sách lỗi
            data, model = X.goi_gemini(payload, cac_model)
            cand = (data.get("candidates") or [{}])[0]
            text_res = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []) if not p.get("thought"))
            try:
                de = doc_json(text_res)
            except ValueError as e:
                loi_cuoi = "JSON không đọc được (%s)" % str(e)[:100]
                print("⚠️ Lần %d: %s" % (lan, loi_cuoi), flush=True)
                continue
            nang, nhe = kiem_tra_cau_truc(de)
            if not nang:
                json_ket_qua, canh_bao = de, nhe
                break
            loi_cuoi = "; ".join(nang[:8])
            print("⚠️ Lần %d sai cấu trúc: %s" % (lan, loi_cuoi), flush=True)
            payload["contents"].append({"role": "model", "parts": [{"text": text_res[:20000]}]})
            payload["contents"].append({"role": "user", "parts": [{"text": "Cấu trúc chưa đạt: " + loi_cuoi +
                                                                  ". Soạn lại TOÀN BỘ đề, đúng mẫu JSON."}]})
        if json_ket_qua is None:
            raise RuntimeError("Gemini trả đề sai cấu trúc sau 2 lần: " + loi_cuoi)

        # Ghi kết quả thành công vào file kết quả trên Drive
        ghi_tep(drive, kq_id, {
            "trangThai": "XONG",
            "model": model,
            "deThi": json_ket_qua,
            "canhBao": canh_bao,
            "luc": dt.datetime.now(TZ).isoformat()
        })
        print("✅ Xưởng Python đã soạn đề thành công!" + (" Cảnh báo: " + "; ".join(canh_bao) if canh_bao else ""), flush=True)

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
