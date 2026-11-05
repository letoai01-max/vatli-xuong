"""
tao_de.py (v2 – KHUNG) – XƯỞNG TẠO ĐỀ THEO GIAO THỨC "GÓI VIỆC v2" (xem giao_thuc.py).

Việc đã làm đủ ở khung này: đọc gói v2, ghi tiến độ/nhật kí, soạn từng phần theo ĐẶC TẢ + CHỈ BÁO của Apps Script, chuẩn hoá đề
($…$), kiểm công thức, xuất 2 tệp Word (HS, GV) vào tệp rỗng thầy đã tạo sẵn, hết hạn mức Gemini → HOAN (làm tiếp sau).
Chưa có (bước 4–5 sẽ thêm vào chỗ đánh dấu «BƯỚC 4/5»): luật kiểm từng câu, xác minh đáp án độc lập, soạn lại câu lệch,
hình vẽ bằng code, câu mẫu Kho chung, phiếu làm lại.
Gói cũ (phienBan 1, chỉ có các ô B…) → chạy bản cũ đã đổi tên thành tao_de_v1.py (giữ làm dự phòng).
Biến môi trường: GOOGLE_CREDENTIALS / đăng nhập WIF, GEMINI_API_KEY…, GOI_ID, KQ_ID.
"""
import json
import os
import re
import sys
import tempfile

import chuan_de as CD
import doc_de as X                      # goi_gemini (xoay khoá, model từ tab CauHinh), HetHanMuc, doc_cau_hinh
import giao_thuc as GT
import xuat_de_v2 as XD

CHO_HOAN_PHUT = {"phut": 3, "ngay": 8}   # giống ChanVongLap.gs: hết lượt theo phút chờ 3', theo ngày chờ 8'

HE_THONG = (
    "Bạn là AI Agent Khảo thí môn Vật lí THPT (Chương trình GDPT 2018, Kết nối tri thức với cuộc sống). "
    "Soạn đề TUÂN THỦ CHÍNH XÁC DANH MỤC CÂU HỎI được giao. Đáp án phải đúng về vật lí, số liệu tính toán chính xác. "
    "Công thức viết bằng LaTeX trong dấu $…$ (ví dụ $\\frac{1}{2}mv^2$, $T = 2\\pi\\sqrt{\\frac{l}{g}}$); đơn vị trong \\text{ }, "
    "ví dụ $5\\text{ cm}$, $2\\text{ μF}$; số thập phân dùng dấu phẩy trong chữ, dấu chấm trong dapAn Phần III. "
    "CHỈ trả về MỘT đối tượng JSON đúng mẫu, không bình luận, không ```.")

MAU = {
    1: '{"phan1": [{"cauHoi": "...", "A": "...", "B": "...", "C": "...", "D": "...", "dapAn": "A"}]}',
    2: '{"phan2": [{"cauHoi": "nội dung dẫn...", "A": "ý a", "B": "ý b", "C": "ý c", "D": "ý d", "dapAn": "a) Đ, b) S, c) Đ, d) S"}]}',
    3: '{"phan3": [{"cauHoi": "...", "dapAn": "12.5"}]}',
    4: '{"phan4": [{"cauHoi": "đề bài...", "dapAn": "- Bước 1...\\n- Bước 2...\\n=> Đáp số: ... kèm đơn vị"}]}',
}
LUAT = {
    1: "Mỗi câu có đúng một đáp án đúng; bốn phương án A, B, C, D ngắn gọn, phương án nhiễu hợp lí.",
    2: "Mỗi câu có đúng 4 ý a), b), c), d) (trường A, B, C, D), trong đó ĐÚNG 2 ý Đúng và 2 ý Sai; vị trí hai ý Đúng thay đổi giữa các câu.",
    3: "Trường dapAn là MỘT SỐ (ví dụ 15.2), không đơn vị, không chữ cái.",
    4: "Trường dapAn là lời giải mỗi bước MỘT DÒNG (ngăn cách bằng \\n, mỗi dòng bắt đầu '- '), dòng cuối '=> Đáp số: …' kèm đơn vị.",
}


def dung_danh_muc(t0, p):
    """Danh mục câu của một phần từ trangThai0.dm (đúng dữ liệu agent Apps Script dùng)."""
    dm = (t0.get("dm") or {}).get("p%d" % p) or []
    dong = []
    for i, m in enumerate(dm, 1):
        if p == 2:
            dong.append("Câu %d (4 ý a, b, c, d lần lượt theo):\n" % i + "\n".join("   ý %s: %s" % ("abcd"[k], y) for k, y in enumerate(m)))
        else:
            dong.append("Câu %d: %s" % (i, m))
    return "\n".join(dong)


def doc_json(text):
    s = re.sub(r"```json|```", "", str(text or "")).strip()
    a, b = s.find("{"), s.rfind("}")
    return json.loads(s[a:b + 1] if a != -1 and b > a else s)


def soan_phan(goi, p, cac_model, ghi_chu_loi=""):
    ch, t0 = goi["cauHinh"], goi["trangThai0"]
    n = t0["yc"]["p%d" % p]
    nguoi = ("Soạn riêng PHẦN %d của đề kiểm tra môn %s lớp %s (%s).\n\n=== DANH MỤC CÂU HỎI BẮT BUỘC ===\n%s\n\n"
             "ĐÚNG %d câu. %s\n\nNGUỒN CÂU HỎI THAM KHẢO TỪ GIÁO VIÊN:\n%s\n\nMẫu JSON:\n%s%s") % (
        p, ch.get("subject", "Vật lí"), ch.get("grade"), ch.get("textbook", ""), dung_danh_muc(t0, p), n, LUAT[p],
        (t0.get("nganHang") or "")[:6000], MAU[p], ("\n\nLƯU Ý SỬA LỖI LẦN TRƯỚC: " + ghi_chu_loi) if ghi_chu_loi else "")
    payload = {"contents": [{"role": "user", "parts": [{"text": nguoi}]}], "systemInstruction": {"parts": [{"text": HE_THONG}]},
               "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json", "maxOutputTokens": 32768}}
    data, model = X.goi_gemini(payload, cac_model)
    cand = (data.get("candidates") or [{}])[0]
    text = "".join(x.get("text", "") for x in (cand.get("content") or {}).get("parts", []) if not x.get("thought"))
    kq = doc_json(text)
    mang = kq.get("phan%d" % p) if isinstance(kq, dict) else kq
    return (mang if isinstance(mang, list) else []), model


def main():
    import google.auth
    import gspread
    from googleapiclient.discovery import build
    cred, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    gc, drive = gspread.authorize(cred), build("drive", "v3", credentials=cred, cache_discovery=False)
    goi_id, kq_id = os.environ["GOI_ID"], os.environ["KQ_ID"]
    goi = GT.doc_json_drive(drive, goi_id)
    if goi.get("phienBan", 1) == 1:
        import tao_de_v1                      # bản cũ, giữ làm dự phòng
        return tao_de_v1.main()
    loi_goi = GT.kiem_goi(goi)
    ph = GT.Phien(drive, kq_id, goi)
    if loi_goi:
        ph.loi("Gói việc không hợp lệ: " + "; ".join(loi_goi))
        raise SystemExit(1)
    cu = GT.doc_json_drive(drive, kq_id)      # lần chạy lại sau HOAN: dùng tiếp phần đã soạn
    de = {k: v for k, v in (cu.get("deThi") or {}).items() if k in ("phan1", "phan2", "phan3", "phan4")}
    ph.luot = int(cu.get("luot", 0) or 0) + 1
    ph.tien_do("đọc gói", 3, "loại %s · khối %s · lượt %d" % (goi["loai"], goi["cauHinh"]["grade"], ph.luot))
    t0 = goi["trangThai0"]
    try:
        cac_model = X.doc_cau_hinh(gc.open_by_key(X.ID_KHO_CHUNG))
        model, ghi_chu = "", {}
        for p in (1, 2, 3, 4):
            n = t0["yc"]["p%d" % p]
            if n == 0:
                de["phan%d" % p] = []
                continue
            if len(de.get("phan%d" % p) or []) == n:
                ph.ghi_nhat_ky("bỏ qua phần %d" % p, "đã soạn đủ từ lượt trước")
                continue
            for lan in (1, 2):                # đủ số câu thì nhận; thiếu thì soạn lại 1 lần
                ph.tien_do("soạn phần %d" % p, 10 + 18 * p, "lần %d, cần %d câu" % (lan, n))
                mang, model = soan_phan(goi, p, cac_model, ghi_chu.get(p, ""))
                if len(mang) == n:
                    break
                ghi_chu[p] = "lần trước chỉ có %d/%d câu; phải trả ĐỦ %d câu." % (len(mang), n, n)
            de["phan%d" % p] = mang
            if len(mang) != n:
                ph.them_canh_bao("Phần %d có %d/%d câu sau 2 lần soạn." % (p, len(mang), n))
            # --- BƯỚC 4/5: luật từng câu, xác minh đáp án độc lập, soạn lại câu lệch (hiện chỉ lưu phần đã soạn) ---
            ph.extra["deThi"] = de
        ph.tien_do("chuẩn hoá và kiểm công thức", 80)
        de, ghi = CD.chuan_hoa_de(de)
        for l in CD.kiem_tra_latex(de):
            ph.them_canh_bao(l)
        ph.tien_do("xuất Word HS và GV", 88)
        thu = tempfile.mkdtemp()
        kq = XD.xuat_de(de, goi["cauHinh"], thu, ten_goc="De")
        for c in kq["canhBao"]:
            ph.them_canh_bao(c)
        GT.ghi_docx_vao_tep(drive, goi["dich"]["docxHS"], kq["hs"])
        GT.ghi_docx_vao_tep(drive, goi["dich"]["docxGV"], kq["gv"])
        ph.xong(de, tep=goi["dich"], tom_tat=kq["thongKe"], model=model)
        print("✅ Xong đề %s: %s" % (goi["ma"], json.dumps(kq["thongKe"], ensure_ascii=False)), flush=True)
    except X.HetHanMuc as e:
        theo_ngay = bool(re.search(r"ngày|day|RPD", str(e), re.I))
        ph.hoan(str(e), CHO_HOAN_PHUT["ngay" if theo_ngay else "phut"], de_dang_soan=de)
        print("⏸️ Hết hạn mức Gemini – Apps Script sẽ gửi lại:", str(e)[:150], flush=True)
    except Exception as e:
        ph.loi(str(e))
        for k in ("docxHS", "docxGV"):
            GT.danh_dau_loi_tep(drive, goi["dich"].get(k, ""), str(e))
        raise


if __name__ == "__main__":
    main()
