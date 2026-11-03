# -*- coding: utf-8 -*-
"""
soan_giao_an.py – XƯỞNG SOẠN GIÁO ÁN / KẾ HOẠCH BÀI DẠY CV 5512 (Python, GitHub Actions) – workflow soan_giao_an.yml.

Chỉ chạy khi được gọi (không có lịch) nên không trùng với 8 lịch soanGiaoAnLop… của dự án Apps Script giáo án.
Hai cách chạy, chọn theo biến môi trường:

  1. GÓI VIỆC (Apps Script ↔ xưởng, cùng khuôn với de_cuong.py): có GOI_ID và KQ_ID.
     Apps Script ghi goi_<mã>.json:
        {"ma": "...", "khoi": "10", "kiemTraCheo": false,
         "buoc": [{"so": 1, "he": "<lời hệ thống>", "nguoi": "<lời nhắc>", "coCode": false},
                  {"so": 2, "he": "...", "nguoi": "... {{BUOC_1}} ..."}]}
     {{BUOC_n}} được thay bằng kết quả bước n. Xưởng gọi Gemini lần lượt (model đọc từ tab CauHinh như Meta),
     rồi ghi ket_qua_<mã>.json: {"trangThai": "DANG_LAM" | "XONG" | "LOI", "model", "buoc": {"1": "...", ...}, "luc"}.
     Apps Script tự nhận kết quả và tạo Docs / Word như hiện nay.

  2. SOẠN TAY (để thử, không đụng tới Drive): có TEN_BAI (+ LOP, YCCD). Xưởng soạn một KHBD theo khung CV 5512,
     (nếu bật) nhờ Groq rà soát chéo, rồi xuất Word vào thư mục out/ → tải ở mục Artifacts của lượt chạy,
     bản Markdown hiện ở trang Summary.

Công tắc ở tab CauHinh của Kho chung: BAT_TAT_SOAN_GIAO_AN, SOAN_GIAO_AN_LOP_10 / _11 / _12 (mặc định bật).
Vòng rà soát chéo Groq dùng công tắc VONG_KIEM_TRA_THU_HAI_GROQ (xem groq_xuong.cong_tac_bat).
Biến môi trường: GOOGLE_CREDENTIALS, GEMINI_API_KEY; tuỳ chọn GROQ_API_KEY, GROQ_MODELS.
"""
import datetime as dt
import os
import re
import sys

import requests
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

import de_cuong as DC          # dùng lại: ket_noi, doc_tep, ghi_tep, ds_model, goi_gemini, HetHanMuc

try:
    import groq_xuong as G
except Exception:              # thiếu groq_xuong: vẫn soạn bình thường, chỉ bỏ vòng rà soát chéo
    G = None

# ---------------- CẤU HÌNH HỆ THỐNG ----------------
ID_KHO_CHUNG = os.environ.get("SHEET_ID") or "1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc"
TAB_CAU_HINH = "CauHinh"
TZ = dt.timezone(dt.timedelta(hours=7))
THU_MUC_RA = "out"
GROQ_MODEL_MAC_DINH = "llama-3.3-70b-versatile"
_NHAT_KY = {"model": ""}


def lay_cau_hinh_tu_sheet(sh):
    """Đọc các công tắc bật/tắt từ tab CauHinh trên Kho chung"""
    try:
        ws = sh.worksheet(TAB_CAU_HINH)
        data = ws.get_all_values()
        config = {}
        for row in data[1:]:
            if len(row) >= 2 and row[0].strip():
                key = row[0].strip()
                val = row[1].strip().lower() == "true"
                config[key] = val
        return config
    except Exception as e:
        print(f"⚠️ Lỗi đọc tab CauHinh (chạy mặc định): {e}")
        return {}


def tao_khung_giao_an_cv5512(ten_bai_hoc, lop, yeu_cau_can_dat, cac_model=None):
    """
    Bước 1: Gọi Gemini tạo khung Kế hoạch bài dạy theo Phụ lục 1 Công văn 5512
    """
    he = "Bạn là một giáo viên môn Vật lí THPT giỏi chuyên môn tại trường THPT Thủy Sơn."
    nguoi = f"""
    Hãy soạn Kế hoạch bài dạy (Giáo án) chi tiết cho bài học sau:
    - Tên bài học: {ten_bai_hoc}
    - Lớp: {lop}
    - Yêu cầu cần đạt (YCCĐ): {yeu_cau_can_dat}

    YÊU CẦU CẤU TRÚC TUYỆT ĐỐI THEO CÔNG VĂN 5512:
    I. MỤC TIÊU
    1. Về kiến thức
    2. Về năng lực (Năng lực chung và Năng lực đặc thù môn Vật lí)
    3. Về phẩm chất
    II. THIẾT BỊ DẠY HỌC VÀ HỌC LIỆU
    1. Đối với giáo viên (SGK, KHBD, thiết bị thí nghiệm)
    2. Đối với học sinh (Sách vở, chuẩn bị theo nhóm)
    III. TIẾN TRÌNH DẠY HỌC
    1. Hoạt động 1: Xác định vấn đề / Khởi động
    2. Hoạt động 2: Hình thành kiến thức mới (chia rõ các nội dung trọng tâm, tích hợp thí nghiệm vật lí)
    3. Hoạt động 3: Luyện tập
    4. Hoạt động 4: Vận dụng

    Trình bày rõ từng hoạt động theo 4 bước: a) Mục tiêu; b) Nội dung; c) Sản phẩm; d) Tổ chức thực hiện.
    Công thức viết bằng LaTeX trong dấu $...$ (ví dụ $v = \\dfrac{{s}}{{t}}$), số thập phân dùng dấu phẩy.
    """
    text, model = DC.goi_gemini(he, nguoi, False, cac_model or [DC.MODEL_MAC_DINH])
    _NHAT_KY["model"] = model
    return text


def kiem_tra_cheo_groq(noi_dung_giao_an):
    """
    Bước 2 (Dual-AI): Dùng Groq làm vòng kiểm tra thứ 2 để rà soát tính logic, chuẩn xác kiến thức vật lí và
    định hướng sư phạm. Chỉ nhận bản rà soát khi Groq trả về ĐẦY ĐỦ (kết thúc bình thường, không ngắn hơn 80% bản gốc);
    ngược lại giữ nguyên bản của Gemini (tránh thay giáo án bằng bản bị cắt giữa chừng).
    """
    groq_api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not groq_api_key:
        print("⚠️ Không tìm thấy GROQ_API_KEY. Bỏ qua vòng kiểm tra chéo thứ 2.")
        return noi_dung_giao_an, False
    if G is not None:
        try:
            if not G.cong_tac_bat():
                print("ℹ️ Công tắc VONG_KIEM_TRA_THU_HAI_GROQ đang tắt. Bỏ qua vòng kiểm tra chéo.")
                return noi_dung_giao_an, False
        except Exception:
            pass
    cac_model = list(getattr(G, "MODELS", []) or []) or [GROQ_MODEL_MAC_DINH]

    system_prompt = (
        "Bạn là chuyên gia thẩm định chất lượng giáo án môn Vật lí. "
        "Hãy rà soát kỹ lưỡng nội dung kế hoạch bài dạy được cung cấp, phát hiện và sửa ngay "
        "các lỗi sai về mặt khoa học vật lí, logic hoạt động hoặc cấu trúc Công văn 5512. "
        "Giữ nguyên toàn bộ cấu trúc, định dạng Markdown và công thức LaTeX; chỉ sửa chỗ sai. "
        "Trả về nội dung giáo án hoàn chỉnh sau khi đã được tinh chỉnh tối ưu, không thêm lời dẫn."
    )
    print("🔍 Đang chạy vòng kiểm tra chéo Dual-AI (Groq)...")
    for model in cac_model[:3]:
        payload = {"model": model, "temperature": 0.2, "max_tokens": 12000,
                   "messages": [{"role": "system", "content": system_prompt},
                                {"role": "user", "content": noi_dung_giao_an}]}
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                              headers={"Authorization": f"Bearer {groq_api_key}", "Content-Type": "application/json"},
                              json=payload, timeout=90)
        except Exception as e:
            print(f"⚠️ Ngoại lệ khi gọi kiểm tra chéo Groq ({model}): {type(e).__name__}")
            continue
        if r.status_code != 200:
            print(f"⚠️ Lỗi API Groq {model} (HTTP {r.status_code}): {r.text[:150]}")
            continue
        ch = (r.json().get("choices") or [{}])[0]
        moi = ((ch.get("message") or {}).get("content") or "").strip()
        if ch.get("finish_reason") == "stop" and len(moi) >= 0.8 * len(noi_dung_giao_an):
            print(f"✅ Kiểm tra chéo hoàn tất ({model}).")
            return moi, True
        print(f"⚠️ Bản rà soát của {model} không đầy đủ ({ch.get('finish_reason')}, {len(moi)}/{len(noi_dung_giao_an)} kí tự) – giữ bản gốc.")
    return noi_dung_giao_an, False


def _ghi_dong(doc, line):
    """Một dòng Markdown → đoạn Word: bỏ dấu #, in đậm **...**."""
    muc = re.match(r"^\s*#{1,6}\s*(.*)$", line)
    dam_ca_dong = bool(muc)
    if muc:
        line = muc.group(1)
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.15
    for i, phan in enumerate(re.split(r"\*\*", line)):
        if not phan:
            continue
        run = p.add_run(phan)
        run.font.name = 'Times New Roman'
        run.font.size = Pt(13)
        run.font.bold = dam_ca_dong or (i % 2 == 1)


def xuat_file_word_giao_an(noi_dung_markdown, ten_bai_hoc, thu_muc=None):
    """
    Tự động định dạng và xuất nội dung giáo án ra file Word (.docx)
    theo chuẩn: Times New Roman, cỡ chữ 13, lề chuẩn hành chính.
    """
    doc = Document()

    for section in doc.sections:
        section.top_margin = Inches(0.79)
        section.bottom_margin = Inches(0.79)
        section.left_margin = Inches(1.18)
        section.right_margin = Inches(0.59)

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_title = p_title.add_run(f"KẾ HOẠCH BÀI DẠY: {ten_bai_hoc.upper()}")
    run_title.font.name = 'Times New Roman'
    run_title.font.size = Pt(14)
    run_title.font.bold = True

    for line in noi_dung_markdown.split('\n'):
        _ghi_dong(doc, line)

    ten_an_toan = re.sub(r"[^\w\-]+", "_", ten_bai_hoc, flags=re.UNICODE).strip("_")[:80] or "bai"
    ten_file_out = f"KHBD_{ten_an_toan}.docx"
    if thu_muc:
        os.makedirs(thu_muc, exist_ok=True)
        ten_file_out = os.path.join(thu_muc, ten_file_out)
    doc.save(ten_file_out)
    print(f"📄 Đã xuất file Word thành công: {ten_file_out}")
    return ten_file_out


# ---------------- CÁCH 1: GÓI VIỆC TỪ APPS SCRIPT ----------------
def chay_goi(drive, goi_id, kq_id, cac_model, config):
    goi = DC.doc_tep(drive, goi_id)
    khoi = str(goi.get("khoi") or goi.get("lop") or "").strip()
    if khoi in ("10", "11", "12") and not config.get(f"SOAN_GIAO_AN_LOP_{khoi}", True):
        DC.ghi_tep(drive, kq_id, {"trangThai": "LOI", "loi": f"Công tắc SOAN_GIAO_AN_LOP_{khoi} đang tắt (tab CauHinh).",
                                  "luc": dt.datetime.now(TZ).isoformat()})
        print(f"⏸️ Công tắc SOAN_GIAO_AN_LOP_{khoi} đang tắt. Đã báo lại cho Apps Script, dừng.")
        return
    buoc = [b for b in (goi.get("buoc") or []) if b]
    if not buoc:
        DC.ghi_tep(drive, kq_id, {"trangThai": "LOI", "loi": "Gói việc không có mục 'buoc'.",
                                  "luc": dt.datetime.now(TZ).isoformat()})
        raise ValueError("Gói việc không có mục 'buoc'.")
    print("Giáo án %s – lớp %s; %d bước; model: %s" % (goi.get("ma"), khoi or "?", len(buoc), ", ".join(cac_model)))
    DC.ghi_tep(drive, kq_id, {"trangThai": "DANG_LAM", "luc": dt.datetime.now(TZ).isoformat()})
    ra, model_dung, da_cheo = {}, "", False
    try:
        for b in buoc:
            so = str(b["so"])
            nguoi = re.sub(r"\{\{BUOC_(\w+)\}\}", lambda m: ra.get(m.group(1), "")[:60000], b["nguoi"])
            text, model_dung = DC.goi_gemini(b.get("he", ""), nguoi, b.get("coCode"), cac_model)
            ra[so] = text
            print("✅ Bước %s xong (%d kí tự)" % (so, len(text)))
        if goi.get("kiemTraCheo"):
            cuoi = str(buoc[-1]["so"])
            ra[cuoi], da_cheo = kiem_tra_cheo_groq(ra[cuoi])
        DC.ghi_tep(drive, kq_id, {"trangThai": "XONG", "model": model_dung, "daKiemTraCheo": da_cheo, "buoc": ra,
                                  "luc": dt.datetime.now(TZ).isoformat()})
        print("📦 Đã ghi kết quả. Apps Script sẽ nhận và tạo Docs / Word.")
    except Exception as e:
        DC.ghi_tep(drive, kq_id, {"trangThai": "LOI", "loi": str(e)[:500], "luc": dt.datetime.now(TZ).isoformat()})
        raise


# ---------------- CÁCH 2: SOẠN TAY ----------------
def soan_tay(lop, ten_bai, yccd, cac_model):
    print(f"✍️ Soạn tay: {ten_bai} (lớp {lop})")
    noi_dung = tao_khung_giao_an_cv5512(ten_bai, lop, yccd or "(theo Chương trình GDPT 2018, sách Kết nối tri thức)", cac_model)
    noi_dung, da_cheo = kiem_tra_cheo_groq(noi_dung)
    tep = xuat_file_word_giao_an(noi_dung, ten_bai, THU_MUC_RA)
    tom_tat = os.environ.get("GITHUB_STEP_SUMMARY")
    if tom_tat:
        with open(tom_tat, "a", encoding="utf-8") as f:
            f.write("# KHBD: %s (lớp %s)\n\nModel soạn: `%s` · Rà soát chéo Groq: %s\n\nBản Word: tải ở mục **Artifacts** (%s).\n\n---\n\n%s\n"
                    % (ten_bai, lop, _NHAT_KY["model"], "đã áp dụng" if da_cheo else "không áp dụng", os.path.basename(tep), noi_dung))
    return tep


def main():
    print("--- BẮT ĐẦU CHẠY XƯỞNG SOẠN GIÁO ÁN (DUAL-AI) ---")
    if not os.environ.get("GOOGLE_CREDENTIALS"):
        sys.exit("❌ Chưa thiết lập biến môi trường GOOGLE_CREDENTIALS.")
    goi_id, kq_id = os.environ.get("GOI_ID", "").strip(), os.environ.get("KQ_ID", "").strip()
    ten_bai = os.environ.get("TEN_BAI", "").strip()
    if goi_id and not kq_id:
        sys.exit("❌ Có GOI_ID mà thiếu KQ_ID (File ID kết quả).")
    if not goi_id and not ten_bai:
        sys.exit("❌ Không có việc để làm: cần GOI_ID + KQ_ID (Apps Script ra lệnh) hoặc TEN_BAI (soạn tay).")

    gc, drive = DC.ket_noi()
    sh = gc.open_by_key(ID_KHO_CHUNG)
    print("✅ Đã kết nối thành công với Kho chung trên Google Drive!")
    config = lay_cau_hinh_tu_sheet(sh)

    if not config.get("BAT_TAT_SOAN_GIAO_AN", True):
        print("⏸️ Công tắc tổng BAT_TAT_SOAN_GIAO_AN đang tắt. Dừng thực thi.")
        if goi_id:
            DC.ghi_tep(drive, kq_id, {"trangThai": "LOI", "loi": "Công tắc BAT_TAT_SOAN_GIAO_AN đang tắt (tab CauHinh).",
                                      "luc": dt.datetime.now(TZ).isoformat()})
        return

    cac_model = DC.ds_model(gc)
    if goi_id:
        chay_goi(drive, goi_id, kq_id, cac_model, config)
        return

    lop = os.environ.get("LOP", "10").strip()
    if lop not in ("10", "11", "12"):
        sys.exit("❌ LOP phải là 10, 11 hoặc 12.")
    if not config.get(f"SOAN_GIAO_AN_LOP_{lop}", True):
        print(f"⏸️ Công tắc SOAN_GIAO_AN_LOP_{lop} đang tắt. Dừng thực thi.")
        return
    soan_tay(f"Lớp {lop}", ten_bai, os.environ.get("YCCD", "").strip(), cac_model)


if __name__ == "__main__":
    main()
