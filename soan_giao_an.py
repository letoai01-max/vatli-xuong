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

YÊU CẦU RIÊNG CỦA TỔ (bản 04/11/2026), áp cho cả hai cách chạy:
  • Mục tiêu có dòng "Năng lực số và năng lực AI" (Khung năng lực số, Thông tư 02/2025/TT-BGDĐT, 6 miền, miền 6 là Ứng dụng AI).
  • Mục d) Tổ chức thực hiện của mỗi hoạt động là BẢNG 2 CỘT: Hoạt động của giáo viên | Hoạt động của học sinh.
  • Tối thiểu 50% hoạt động tích hợp năng lực số – AI (bắt buộc HĐ2 và HĐ4), mỗi hoạt động có dòng "Tích hợp NLS – AI: Có/Không".
  • Cuối bài có PHỤ LỤC: Phiếu học tập + Rubric đánh giá năng lực số và AI.
  Soạn tay: soạn phần chính → tự kiểm cấu trúc (sửa 1 lần nếu thiếu) → Groq rà soát → soạn Phụ lục → xuất Word bằng pandoc
  (bảng và công thức thành bảng / phương trình Word thật; không có pandoc thì dùng python-docx).
  Gói việc: bổ sung các yêu cầu trên vào lời hệ thống của mọi bước (tắt bằng "boSungNLS": false trong gói), kiểm cấu trúc ở bước cuối
  và ghi cảnh báo vào mục "canhBao" của kết quả (Apps Script bỏ qua mục lạ).

Công tắc ở tab CauHinh của Kho chung: BAT_TAT_SOAN_GIAO_AN, SOAN_GIAO_AN_LOP_10 / _11 / _12 (mặc định bật).
Vòng rà soát chéo Groq dùng công tắc VONG_KIEM_TRA_THU_HAI_GROQ (xem groq_xuong.cong_tac_bat).
Biến môi trường: GOOGLE_CREDENTIALS, GEMINI_API_KEY; tuỳ chọn GROQ_API_KEY, GROQ_MODELS.
"""
import datetime as dt
import os
import re
import shutil
import subprocess
import sys
import tempfile

import requests
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

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


# ---------------- YÊU CẦU RIÊNG CỦA TỔ ----------------
QUY_DINH_BO_SUNG = """YÊU CẦU BỔ SUNG BẮT BUỘC (ngoài khung Công văn 5512):

A. NĂNG LỰC SỐ VÀ NĂNG LỰC AI TRONG MỤC TIÊU.
   Ở mục I.2 (Về năng lực), ngoài "Năng lực chung" và "Năng lực đặc thù môn Vật lí", PHẢI có dòng riêng in đậm
   "**Năng lực số và năng lực AI:**" nêu cụ thể theo Khung năng lực số cho người học (Thông tư 02/2025/TT-BGDĐT, 6 miền:
   1 Khai thác dữ liệu và thông tin; 2 Giao tiếp và hợp tác; 3 Sáng tạo nội dung số; 4 An toàn; 5 Giải quyết vấn đề;
   6 Ứng dụng trí tuệ nhân tạo). Phải nêu ít nhất một miền số (miền 1-5) và miền 6 (AI), mỗi ý là biểu hiện quan sát/đo được
   gắn với nội dung bài (ví dụ: "dùng mô phỏng PhET để thay đổi ... và ghi lại số liệu"; "viết câu lệnh cho AI, đối chiếu kết quả với SGK").

B. MỤC d) TỔ CHỨC THỰC HIỆN LÀ BẢNG 2 CỘT.
   Ở MỖI hoạt động, mục a), b), c) viết như văn bản thường; mục d) là một BẢNG Markdown đúng 2 cột:
   | HOẠT ĐỘNG CỦA GIÁO VIÊN | HOẠT ĐỘNG CỦA HỌC SINH |
   |---|---|
   gồm 4 hàng tương ứng 4 bước: Bước 1 Chuyển giao nhiệm vụ; Bước 2 Thực hiện nhiệm vụ; Bước 3 Báo cáo, thảo luận; Bước 4 Kết luận, nhận định.
   Mỗi ô nằm trên MỘT dòng của bảng; muốn xuống dòng trong ô thì viết <br>, tuyệt đối không xuống dòng thật trong ô.
   Đầu mỗi ô ghi rõ tên bước (ví dụ "**Bước 1. Chuyển giao nhiệm vụ:** ..."). Nội dung hai cột phải khớp nhau về diễn tiến.

C. TÍCH HỢP NĂNG LỰC SỐ – AI Ở ÍT NHẤT 50% SỐ HOẠT ĐỘNG.
   Bài có 4 hoạt động thì Hoạt động 2 và Hoạt động 4 BẮT BUỘC tích hợp (Hoạt động 3 nên tích hợp nếu phù hợp).
   Ngay dưới tiêu đề mỗi hoạt động có đúng một dòng, đúng khuôn:
   **Tích hợp NLS – AI:** Có – <miền năng lực, công cụ cụ thể>      hoặc      **Tích hợp NLS – AI:** Không
   Hoạt động ghi "Có" phải thể hiện rõ NGAY TRONG bảng mục d): giáo viên giao/hướng dẫn việc gì với công cụ nào, học sinh làm gì.
   Dùng công cụ thật, khả thi ở trường THPT: mô phỏng PhET, Phyphox, Tracker, Desmos/GeoGebra, Google Forms/Padlet/Jamboard,
   Canva, Google Sheets (xử lí số liệu, vẽ đồ thị); với AI: Gemini, ChatGPT, NotebookLM, Copilot. Mỗi lần học sinh dùng AI phải có:
   (i) học sinh tự viết câu lệnh (prompt) rõ mục đích, (ii) đối chiếu kết quả của AI với SGK/thí nghiệm/tính toán và nêu chỗ sai hoặc chưa chắc chắn,
   (iii) ghi nguồn đã dùng AI, không sao chép nguyên văn; giáo viên nhắc về dữ liệu cá nhân và trung thực học thuật.
   AI chỉ hỗ trợ, không thay học sinh kết luận kiến thức vật lí.

D. SỐ THẬP PHÂN dùng dấu phẩy; công thức viết bằng LaTeX trong $...$."""


def tao_khung_giao_an_cv5512(ten_bai_hoc, lop, yeu_cau_can_dat, cac_model=None):
    """
    Bước 1: Gọi Gemini tạo phần CHÍNH của Kế hoạch bài dạy (I, II, III) theo Phụ lục 1 Công văn 5512
    + yêu cầu riêng của tổ (năng lực số – AI, bảng 2 cột, tích hợp ≥ 50%). Phần Phụ lục soạn ở bước sau.
    """
    he = ("Bạn là một giáo viên môn Vật lí THPT giỏi chuyên môn tại trường THPT Thủy Sơn, thành thạo Công văn 5512, "
          "Chương trình GDPT 2018 (sách Kết nối tri thức) và Khung năng lực số cho người học (Thông tư 02/2025/TT-BGDĐT).")
    nguoi = f"""
    Hãy soạn Kế hoạch bài dạy (Giáo án) chi tiết cho bài học sau:
    - Tên bài học: {ten_bai_hoc}
    - Lớp: {lop}
    - Yêu cầu cần đạt (YCCĐ): {yeu_cau_can_dat}

    YÊU CẦU CẤU TRÚC TUYỆT ĐỐI THEO CÔNG VĂN 5512 (chỉ soạn các phần I, II, III; KHÔNG soạn Phụ lục, phần đó làm sau):
    I. MỤC TIÊU
    1. Về kiến thức
    2. Về năng lực (Năng lực chung; Năng lực đặc thù môn Vật lí; Năng lực số và năng lực AI)
    3. Về phẩm chất
    II. THIẾT BỊ DẠY HỌC VÀ HỌC LIỆU
    1. Đối với giáo viên (SGK, KHBD, thiết bị thí nghiệm, thiết bị và phần mềm số, công cụ AI)
    2. Đối với học sinh (Sách vở, chuẩn bị theo nhóm, thiết bị số cá nhân/nhóm)
    III. TIẾN TRÌNH DẠY HỌC
    Hoạt động 1: Xác định vấn đề / Khởi động
    Hoạt động 2: Hình thành kiến thức mới (chia rõ các nội dung trọng tâm, tích hợp thí nghiệm vật lí)
    Hoạt động 3: Luyện tập
    Hoạt động 4: Vận dụng
    Mỗi tiêu đề hoạt động viết trên một dòng riêng, dạng: **Hoạt động 1: Khởi động** (đánh số 1-4, theo đúng thứ tự trên).

    Trình bày rõ từng hoạt động theo 4 mục: a) Mục tiêu; b) Nội dung; c) Sản phẩm; d) Tổ chức thực hiện (d là BẢNG 2 cột).
    Công thức viết bằng LaTeX trong dấu $...$ (ví dụ $v = \\dfrac{{s}}{{t}}$), số thập phân dùng dấu phẩy.

    {QUY_DINH_BO_SUNG}
    """
    text, model = DC.goi_gemini(he, nguoi, False, cac_model or [DC.MODEL_MAC_DINH])
    _NHAT_KY["model"] = model
    return text


def tao_phu_luc(giao_an, ten_bai_hoc, lop, cac_model=None):
    """Bước 3: soạn PHỤ LỤC (Phiếu học tập + Rubric năng lực số – AI) dựa trên giáo án đã chốt."""
    he = ("Bạn là giáo viên Vật lí THPT giỏi, chuyên soạn học liệu và công cụ đánh giá năng lực "
          "(Công văn 5512; Khung năng lực số cho người học, Thông tư 02/2025/TT-BGDĐT).")
    nguoi = f"""Dưới đây là Kế hoạch bài dạy bài "{ten_bai_hoc}" (lớp {lop}). Hãy soạn PHỤ LỤC đặt ở cuối bài, đúng cấu trúc sau
(dùng đúng các tiêu đề, không thêm lời dẫn):

## PHỤ LỤC 1: HỌC LIỆU – PHIẾU HỌC TẬP
- Soạn ít nhất 2 phiếu: **PHIẾU HỌC TẬP SỐ 1** (gắn với Hoạt động 2) và **PHIẾU HỌC TẬP SỐ 2** (gắn với Hoạt động 3 hoặc 4); thêm phiếu số 3 nếu bài cần.
- Mỗi phiếu: dòng "Họ và tên/Nhóm/Lớp: ......", tên hoạt động gắn với phiếu, các nhiệm vụ đánh số, chỗ trống để học sinh ghi (dùng dòng chấm ...... hoặc bảng có ô trống).
- Các phiếu gắn với hoạt động có tích hợp năng lực số – AI phải có nhiệm vụ dùng công cụ số/AI đã nêu trong giáo án và một bảng "Kiểm chứng đầu ra của AI"
  với cột: Câu lệnh em đã dùng | AI trả lời (tóm tắt) | Đối chiếu SGK/thí nghiệm/tính toán | Đúng / Sai / Chưa chắc | Em chỉnh lại như thế nào.
- Có câu hỏi/bài tập vật lí cụ thể, số liệu cụ thể, đúng nội dung bài; có gợi ý đáp án ngắn cho giáo viên ở cuối mỗi phiếu (đặt trong mục "*Gợi ý đáp án (dành cho GV)*").

## PHỤ LỤC 2: RUBRIC ĐÁNH GIÁ NĂNG LỰC SỐ VÀ NĂNG LỰC AI
- Một bảng Markdown: cột "Tiêu chí" | "Mức 1 – Cần cố gắng" | "Mức 2 – Đạt" | "Mức 3 – Tốt" | "Điểm".
- Ít nhất 6 tiêu chí, gồm 3 tiêu chí năng lực số (ví dụ: khai thác và đánh giá thông tin/dữ liệu; hợp tác và giao tiếp trong môi trường số; sáng tạo sản phẩm số/xử lí số liệu, an toàn số)
  và 3 tiêu chí năng lực AI (ví dụ: viết câu lệnh rõ mục đích; kiểm chứng và phát hiện sai sót của AI; sử dụng AI trung thực, có trích nguồn, bảo vệ dữ liệu cá nhân).
  Cột đầu mỗi hàng ghi rõ "NLS" hoặc "AI" và tên tiêu chí gắn với miền năng lực của Khung năng lực số.
- Mô tả từng mức bằng biểu hiện quan sát được, gắn với nội dung bài, không nói chung chung. Mỗi ô một dòng của bảng, xuống dòng trong ô dùng <br>.
- Dưới bảng: thang điểm (Mức 1 = 1 điểm, Mức 2 = 2 điểm, Mức 3 = 3 điểm), cách quy đổi tổng điểm sang xếp loại, và nói rõ ai đánh giá (giáo viên, nhóm, tự đánh giá), khi nào đánh giá (hoạt động nào).

Số thập phân dùng dấu phẩy; công thức viết bằng LaTeX trong $...$.

KẾ HOẠCH BÀI DẠY:
{giao_an[:40000]}
"""
    text, model = DC.goi_gemini(he, nguoi, False, cac_model or [DC.MODEL_MAC_DINH])
    return text


# ---------------- KIỂM CẤU TRÚC GIÁO ÁN ----------------
RE_HOAT_DONG = re.compile(r"^[#*\s\d.]*Hoạt động\s+(\d+)\s*[:：.\-–—]", re.I | re.M)
RE_TICH_HOP = re.compile(r"Tích hợp\s+NLS\W+AI\W*(Có|Không)\b", re.I)


def kiem_cau_truc(md, kiem_phu_luc=False):
    """Trả về danh sách lỗi cấu trúc (rỗng = đạt). Kiểm: mục tiêu có NLS–AI, mỗi hoạt động có bảng 2 cột và dòng
    'Tích hợp NLS – AI', tối thiểu 50% hoạt động tích hợp; nếu kiem_phu_luc thì kiểm cả Phiếu học tập và Rubric."""
    md = str(md or "")
    loi = []
    hd = sorted({int(m.group(1)) for m in RE_HOAT_DONG.finditer(md)})
    n = len(hd)
    if n < 4:
        loi.append("Chỉ thấy %d/4 hoạt động (Hoạt động 1-4)." % n)
    muc_tieu = re.split(r"^\W*II\.\s", md, flags=re.M)[0]
    if not re.search(r"năng lực số", muc_tieu, re.I) or not re.search(r"\bAI\b|trí tuệ nhân tạo", muc_tieu, re.I):
        loi.append("Mục tiêu (I.2) chưa có dòng 'Năng lực số và năng lực AI'.")
    so_bang = sum(1 for d in md.splitlines() if d.lstrip().startswith("|")
                  and re.search(r"hoạt động của giáo viên", d, re.I) and re.search(r"hoạt động của học sinh", d, re.I))
    if so_bang < max(n, 1):
        loi.append("Mục d) chưa đủ bảng 2 cột 'Hoạt động của giáo viên | Hoạt động của học sinh' (có %d bảng cho %d hoạt động)." % (so_bang, n))
    dong = [x.lower() for x in RE_TICH_HOP.findall(md)]
    co = dong.count("có")
    if len(dong) < n:
        loi.append("Thiếu dòng 'Tích hợp NLS – AI: Có/Không' ở %d hoạt động." % (n - len(dong)))
    if n and co * 2 < n:
        loi.append("Chỉ %d/%d hoạt động tích hợp năng lực số – AI (cần ≥ 50%%)." % (co, n))
    if kiem_phu_luc:
        if len(set(re.findall(r"PHIẾU HỌC TẬP SỐ\s*(\d+)", md, re.I))) < 2:
            loi.append("Phụ lục chưa có đủ 2 Phiếu học tập.")
        rb = re.search(r"RUBRIC[\s\S]*", md, re.I)
        if not rb:
            loi.append("Phụ lục chưa có Rubric.")
        elif not (re.search(r"\bNLS\b|năng lực số", rb.group(0), re.I) and re.search(r"\bAI\b|trí tuệ nhân tạo", rb.group(0), re.I)):
            loi.append("Rubric chưa tách tiêu chí năng lực số và năng lực AI.")
    return loi


def sua_loi_cau_truc(noi_dung, loi, cac_model=None):
    """Nhờ Gemini sửa MỘT lần các lỗi cấu trúc; trả bản mới (hoặc bản cũ nếu không cải thiện)."""
    he = "Bạn là giáo viên Vật lí THPT giỏi, đang hoàn thiện Kế hoạch bài dạy theo Công văn 5512."
    nguoi = ("Kế hoạch bài dạy dưới đây còn các lỗi cấu trúc sau, hãy sửa TẤT CẢ và trả về TOÀN BỘ giáo án hoàn chỉnh "
             "(giữ nguyên phần đã đạt, không thêm lời dẫn, không soạn Phụ lục):\n- " + "\n- ".join(loi) +
             "\n\n" + QUY_DINH_BO_SUNG + "\n\nGIÁO ÁN HIỆN TẠI:\n" + noi_dung[:40000])
    try:
        moi, _ = DC.goi_gemini(he, nguoi, False, cac_model or [DC.MODEL_MAC_DINH])
    except Exception as e:
        print("⚠️ Không sửa được lỗi cấu trúc (%s) – giữ bản cũ." % type(e).__name__)
        return noi_dung
    loi_moi = kiem_cau_truc(moi)
    if len(loi_moi) < len(loi):
        print("🛠️ Đã sửa cấu trúc: còn %d lỗi (trước đó %d)." % (len(loi_moi), len(loi)))
        return moi
    print("⚠️ Bản sửa không tốt hơn (%d lỗi so với %d) – giữ bản cũ." % (len(loi_moi), len(loi)))
    return noi_dung


def kiem_tra_cheo_groq(noi_dung_giao_an):
    """
    Bước 2 (Dual-AI): Dùng Groq làm vòng kiểm tra thứ 2 để rà soát tính logic, chuẩn xác kiến thức vật lí và
    định hướng sư phạm. Chỉ nhận bản rà soát khi Groq trả về ĐẦY ĐỦ (kết thúc bình thường, không ngắn hơn 80% bản gốc)
    VÀ vẫn giữ đủ cấu trúc theo yêu cầu của tổ (bảng 2 cột, tích hợp NLS–AI); ngược lại giữ nguyên bản của Gemini.
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
    loi_goc = len(kiem_cau_truc(noi_dung_giao_an))

    system_prompt = (
        "Bạn là chuyên gia thẩm định chất lượng giáo án môn Vật lí. "
        "Hãy rà soát kỹ lưỡng nội dung kế hoạch bài dạy được cung cấp, phát hiện và sửa ngay "
        "các lỗi sai về mặt khoa học vật lí, logic hoạt động hoặc cấu trúc Công văn 5512. "
        "GIỮ NGUYÊN: toàn bộ cấu trúc, định dạng Markdown, công thức LaTeX, các BẢNG 2 cột ở mục d) "
        "(| HOẠT ĐỘNG CỦA GIÁO VIÊN | HOẠT ĐỘNG CỦA HỌC SINH |, dùng <br> để xuống dòng trong ô), "
        "dòng 'Tích hợp NLS – AI: Có/Không' của từng hoạt động và dòng 'Năng lực số và năng lực AI' ở mục tiêu. "
        "Chỉ sửa chỗ sai, không xoá nội dung tích hợp năng lực số – AI. "
        "Trả về nội dung giáo án hoàn chỉnh sau khi đã được tinh chỉnh tối ưu, không thêm lời dẫn."
    )
    print("🔍 Đang chạy vòng kiểm tra chéo Dual-AI (Groq)...")
    for model in cac_model[:3]:
        payload = {"model": model, "temperature": 0.2, "max_tokens": 16000,
                   "messages": [{"role": "system", "content": system_prompt},
                                {"role": "user", "content": noi_dung_giao_an}]}
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                              headers={"Authorization": f"Bearer {groq_api_key}", "Content-Type": "application/json"},
                              json=payload, timeout=180)
        except Exception as e:
            print(f"⚠️ Ngoại lệ khi gọi kiểm tra chéo Groq ({model}): {type(e).__name__}")
            continue
        if r.status_code != 200:
            print(f"⚠️ Lỗi API Groq {model} (HTTP {r.status_code}): {r.text[:150]}")
            continue
        ch = (r.json().get("choices") or [{}])[0]
        moi = ((ch.get("message") or {}).get("content") or "").strip()
        if ch.get("finish_reason") == "stop" and len(moi) >= 0.8 * len(noi_dung_giao_an):
            if len(kiem_cau_truc(moi)) > loi_goc:
                print(f"⚠️ Bản rà soát của {model} làm mất cấu trúc yêu cầu (bảng 2 cột / tích hợp NLS–AI) – giữ bản gốc.")
                continue
            print(f"✅ Kiểm tra chéo hoàn tất ({model}).")
            return moi, True
        print(f"⚠️ Bản rà soát của {model} không đầy đủ ({ch.get('finish_reason')}, {len(moi)}/{len(noi_dung_giao_an)} kí tự) – giữ bản gốc.")
    return noi_dung_giao_an, False


# ---------------- XUẤT WORD ----------------
PHONG = "Times New Roman"
CO_CHU = 13
DINH_DANG_VAO = "markdown+hard_line_breaks+tex_math_dollars+pipe_tables+raw_attribute+fenced_divs-fancy_lists-implicit_figures-smart"
NGAT_TRANG_OOXML = '\n\n```{=openxml}\n<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n```\n\n'
XUONG_DONG_OOXML = '`<w:r><w:br/></w:r>`{=openxml}'
RE_GACH = re.compile(r"^\s*(?:[-*•+])\s+")
RE_NGAN_CACH = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
RE_PHU_LUC = re.compile(r"^[#*\s]*PHỤ LỤC\b", re.I)


def _so_thap_phan(m):
    """Trong công thức: 0,05 → 0{,}05 để Word không chèn khoảng trắng sau dấu phẩy thập phân."""
    return re.sub(r"(\d),(?=\d)", r"\1{,}", m.group(0))


def _chuan_markdown(md, pandoc=True):
    """Chuẩn bị Markdown cho pandoc: dòng trống trước bảng / tiêu đề / gạch đầu dòng, <br> → xuống dòng Word,
    cột bảng chia đều (2 cột 50/50; bảng nhiều cột: cột đầu hẹp hơn), ngắt trang trước Phụ lục."""
    md = re.sub(r"\$\$[\s\S]*?\$\$|\$[^$\n]+\$", _so_thap_phan, str(md or ""))
    ra, truoc, da_ngat = [], "", False
    for dong in md.split("\n"):
        la_bang = dong.lstrip().startswith("|")
        if la_bang:
            if RE_NGAN_CACH.match(dong):
                so_cot = max(1, len(dong.strip().strip("|").split("|")))
                co_diem = bool(re.search(r"điểm\s*\|?\s*$", truoc, re.I))      # cột "Điểm" cuối bảng rubric: gọn lại
                dong = "|" + "|".join("-" * (40 if so_cot <= 2 else 56 if i == 0 else 16 if (co_diem and i == so_cot - 1) else 40)
                                      for i in range(so_cot)) + "|"
            else:
                dong = re.sub(r"\s*<br\s*/?>\s*[-*•]\s+", " <br>• ", dong, flags=re.I)
                if pandoc:
                    dong = re.sub(r"<br\s*/?>", XUONG_DONG_OOXML, dong, flags=re.I)
        elif pandoc:
            dong = re.sub(r"<br\s*/?>", "  ", dong, flags=re.I)
        if RE_PHU_LUC.match(dong) and not da_ngat:
            da_ngat = True
            ra += ["", "@@NGAT_TRANG@@", ""]
        mo_bang = la_bang and not truoc.lstrip().startswith("|")
        het_bang = truoc.lstrip().startswith("|") and not la_bang and dong.strip()
        tieu_de = re.match(r"^#{1,6}\s", dong) is not None
        mo_gach = RE_GACH.match(dong) is not None and RE_GACH.match(truoc) is None and not la_bang
        het_gach = RE_GACH.match(dong) is None and RE_GACH.match(truoc) is not None and dong.strip()
        if RE_GACH.match(dong) and not la_bang:
            dong = RE_GACH.sub("- ", dong, count=1)
        if (mo_bang or het_bang or tieu_de or mo_gach or het_gach) and truoc.strip():
            ra.append("")
        ra.append(dong)
        if tieu_de:
            ra.append("")
        truoc = dong
    kq = "\n".join(ra)
    return kq.replace("@@NGAT_TRANG@@", NGAT_TRANG_OOXML.strip() if pandoc else "@@NGAT_TRANG@@")


def _bo_phong(style):
    """Ép phông Times New Roman (cả ascii/hAnsi/cs/eastAsia), bỏ thuộc tính theme đang ghi đè."""
    style.font.name = PHONG
    rpr = style.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.insert(0, rf)
    for k in list(rf.attrib):
        if "Theme" in k:
            del rf.attrib[k]
    for k in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(k), PHONG)


def _chen_truoc(cha, con, ten_sau):
    """Chèn phần tử `con` vào `cha` trước phần tử đầu tiên thuộc `ten_sau` (giữ đúng thứ tự schema của Word)."""
    for ten in ten_sau:
        m = cha.find(qn(ten))
        if m is not None:
            m.addprevious(con)
            return
    cha.append(con)


def _dinh_dang_word(duong_dan):
    """Sau pandoc: Times New Roman 13, lề hành chính, tiêu đề đen, bảng có viền + dòng tiêu đề tô nền, bảng rộng hết khổ."""
    d = Document(duong_dan)
    for s in d.sections:
        s.top_margin, s.bottom_margin = Inches(0.79), Inches(0.79)
        s.left_margin, s.right_margin = Inches(1.18), Inches(0.59)
    for st in d.styles:
        if st.type != 1:          # chỉ kiểu đoạn văn
            continue
        _bo_phong(st)
        ten = st.name or ""
        if ten in ("Normal", "Body Text", "First Paragraph", "Compact", "Block Text", "Table Caption"):
            st.font.size = Pt(CO_CHU)
        if ten.startswith("Heading") or ten in ("Title", "Subtitle"):
            st.font.size = Pt(14 if ten == "Title" else CO_CHU)
            st.font.bold = True
            st.font.italic = False
            st.font.color.rgb = RGBColor(0, 0, 0)
        if ten == "Title":
            st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for tbl in d.tables:
        tpr = tbl._tbl.tblPr
        for ten in ("w:tblW", "w:tblBorders", "w:tblLayout"):
            for cu in tpr.findall(qn(ten)):
                tpr.remove(cu)
        rong = OxmlElement("w:tblW"); rong.set(qn("w:type"), "pct"); rong.set(qn("w:w"), "5000")
        _chen_truoc(tpr, rong, ("w:jc", "w:tblCellSpacing", "w:tblInd", "w:shd", "w:tblCellMar", "w:tblLook"))
        vien = OxmlElement("w:tblBorders")
        for ten in ("top", "left", "bottom", "right", "insideH", "insideV"):
            e = OxmlElement("w:" + ten)
            e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "4"); e.set(qn("w:space"), "0"); e.set(qn("w:color"), "000000")
            vien.append(e)
        _chen_truoc(tpr, vien, ("w:shd", "w:tblLayout", "w:tblCellMar", "w:tblLook"))
        if tbl.rows:
            for o in tbl.rows[0].cells:
                tcpr = o._tc.get_or_add_tcPr()
                for cu in tcpr.findall(qn("w:shd")):
                    tcpr.remove(cu)
                nen = OxmlElement("w:shd"); nen.set(qn("w:val"), "clear"); nen.set(qn("w:color"), "auto"); nen.set(qn("w:fill"), "D9E2F3")
                _chen_truoc(tcpr, nen, ("w:noWrap", "w:tcMar", "w:textDirection", "w:tcFitText", "w:vAlign", "w:hideMark"))
                for p in o.paragraphs:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for r in p.runs:
                        r.font.bold = True
    d.save(duong_dan)


def _xuat_pandoc(md, tieu_de, ra):
    with tempfile.TemporaryDirectory() as tam:
        vao = os.path.join(tam, "giao_an.md")
        phan_dau = '::: {custom-style="Title"}\n' + tieu_de + "\n:::\n\n"
        with open(vao, "w", encoding="utf-8") as f:
            f.write(phan_dau + _chuan_markdown(md, pandoc=True) + "\n")
        kq = subprocess.run(["pandoc", vao, "-f", DINH_DANG_VAO, "-t", "docx", "-o", ra],
                            capture_output=True, text=True, timeout=180)
        if kq.returncode != 0 or not os.path.isfile(ra):
            raise RuntimeError("pandoc lỗi: " + (kq.stderr or "")[:300])
    _dinh_dang_word(ra)


# --- dự phòng khi máy không có pandoc: python-docx (bảng thật, công thức giữ dạng $...$) ---
def _ghi_run(p, chu, dam=False, in_dam=False):
    """Ghi chữ có **đậm** và <br> vào đoạn p."""
    for dong_i, doan in enumerate(re.split(r"<br\s*/?>", chu, flags=re.I)):
        if dong_i:
            p.add_run().add_break()
        for i, phan in enumerate(re.split(r"\*\*", doan)):
            if not phan:
                continue
            run = p.add_run(phan)
            run.font.name = PHONG
            run.font.size = Pt(CO_CHU)
            run.font.bold = dam or (i % 2 == 1)


def _ghi_dong(doc, line):
    """Một dòng Markdown → đoạn Word: bỏ dấu #, in đậm **...**."""
    muc = re.match(r"^\s*#{1,6}\s*(.*)$", line)
    dam_ca_dong = bool(muc)
    if muc:
        line = muc.group(1)
    line = RE_GACH.sub("• ", line, count=1)
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.15
    _ghi_run(p, line, dam=dam_ca_dong)


def _ghi_bang(doc, dong_bang):
    hang = [[c.strip() for c in d.strip().strip("|").split("|")] for d in dong_bang if not RE_NGAN_CACH.match(d)]
    if not hang:
        return
    so_cot = max(len(h) for h in hang)
    tbl = doc.add_table(rows=len(hang), cols=so_cot)
    tbl.style = "Table Grid"
    for i, h in enumerate(hang):
        for j in range(so_cot):
            o = tbl.cell(i, j)
            o.paragraphs[0].text = ""
            _ghi_run(o.paragraphs[0], h[j] if j < len(h) else "", dam=(i == 0))
            if i == 0:
                nen = OxmlElement("w:shd"); nen.set(qn("w:val"), "clear"); nen.set(qn("w:color"), "auto"); nen.set(qn("w:fill"), "D9E2F3")
                o._tc.get_or_add_tcPr().append(nen)
    doc.add_paragraph()


def _xuat_python_docx(md, tieu_de, ra):
    doc = Document()
    for section in doc.sections:
        section.top_margin = Inches(0.79)
        section.bottom_margin = Inches(0.79)
        section.left_margin = Inches(1.18)
        section.right_margin = Inches(0.59)
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_title = p_title.add_run(tieu_de)
    run_title.font.name = PHONG
    run_title.font.size = Pt(14)
    run_title.font.bold = True
    dong_ds, i = _chuan_markdown(md, pandoc=False).split("\n"), 0
    while i < len(dong_ds):
        d = dong_ds[i]
        if d.lstrip().startswith("|"):
            khoi = []
            while i < len(dong_ds) and dong_ds[i].lstrip().startswith("|"):
                khoi.append(dong_ds[i]); i += 1
            _ghi_bang(doc, khoi)
            continue
        if d.strip() == "@@NGAT_TRANG@@":
            doc.add_page_break()
        elif d.strip():
            _ghi_dong(doc, d)
        i += 1
    doc.save(ra)


def xuat_file_word_giao_an(noi_dung_markdown, ten_bai_hoc, thu_muc=None, lop=""):
    """
    Xuất giáo án ra Word (.docx): Times New Roman 13, lề chuẩn hành chính, bảng 2 cột có viền,
    công thức thành phương trình Word (khi có pandoc).
    """
    tieu_de = ("KẾ HOẠCH BÀI DẠY: %s" % ten_bai_hoc.upper()) + (" – VẬT LÍ %s" % lop if lop else "")
    ten_an_toan = re.sub(r"[^\w\-]+", "_", ten_bai_hoc, flags=re.UNICODE).strip("_")[:80] or "bai"
    ten_file_out = f"KHBD_{ten_an_toan}.docx"
    if thu_muc:
        os.makedirs(thu_muc, exist_ok=True)
        ten_file_out = os.path.join(thu_muc, ten_file_out)
    if shutil.which("pandoc"):
        try:
            _xuat_pandoc(noi_dung_markdown, tieu_de, ten_file_out)
            print(f"📄 Đã xuất file Word (pandoc: bảng + phương trình Word): {ten_file_out}")
            return ten_file_out
        except Exception as e:
            print(f"⚠️ Xuất bằng pandoc lỗi ({str(e)[:200]}) – chuyển sang python-docx.")
    else:
        print("ℹ️ Máy không có pandoc – dùng python-docx (công thức giữ nguyên dạng $...$).")
    _xuat_python_docx(noi_dung_markdown, tieu_de, ten_file_out)
    print(f"📄 Đã xuất file Word (python-docx): {ten_file_out}")
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
    bo_sung = goi.get("boSungNLS", True) is not False      # bổ sung yêu cầu NLS–AI vào lời hệ thống (tắt: "boSungNLS": false)
    try:
        for b in buoc:
            so = str(b["so"])
            nguoi = re.sub(r"\{\{BUOC_(\w+)\}\}", lambda m: ra.get(m.group(1), "")[:60000], b["nguoi"])
            he = b.get("he", "") + ("\n\n" + QUY_DINH_BO_SUNG if bo_sung else "")
            text, model_dung = DC.goi_gemini(he, nguoi, b.get("coCode"), cac_model)
            ra[so] = text
            print("✅ Bước %s xong (%d kí tự)" % (so, len(text)))
        if goi.get("kiemTraCheo"):
            cuoi = str(buoc[-1]["so"])
            ra[cuoi], da_cheo = kiem_tra_cheo_groq(ra[cuoi])
        canh_bao = kiem_cau_truc("\n\n".join(ra[k] for k in sorted(ra, key=lambda x: int(x) if x.isdigit() else 0)), kiem_phu_luc=True) if bo_sung else []
        for c in canh_bao:
            print("⚠️ Cấu trúc: " + c)
        DC.ghi_tep(drive, kq_id, {"trangThai": "XONG", "model": model_dung, "daKiemTraCheo": da_cheo, "buoc": ra,
                                  "canhBao": canh_bao, "luc": dt.datetime.now(TZ).isoformat()})
        print("📦 Đã ghi kết quả. Apps Script sẽ nhận và tạo Docs / Word.")
    except Exception as e:
        DC.ghi_tep(drive, kq_id, {"trangThai": "LOI", "loi": str(e)[:500], "luc": dt.datetime.now(TZ).isoformat()})
        raise


# ---------------- CÁCH 2: SOẠN TAY ----------------
def soan_tay(lop, ten_bai, yccd, cac_model):
    print(f"✍️ Soạn tay: {ten_bai} (lớp {lop})")
    yccd = yccd or "(theo Chương trình GDPT 2018, sách Kết nối tri thức)"
    # 1. Phần chính (I–III) + tự kiểm cấu trúc, sửa tối đa một lần
    noi_dung = tao_khung_giao_an_cv5512(ten_bai, lop, yccd, cac_model)
    loi = kiem_cau_truc(noi_dung)
    if loi:
        print("⚠️ Cấu trúc chưa đạt: " + " | ".join(loi))
        noi_dung = sua_loi_cau_truc(noi_dung, loi, cac_model)
    # 2. Groq rà soát chéo (chỉ nhận nếu giữ đủ cấu trúc)
    noi_dung, da_cheo = kiem_tra_cheo_groq(noi_dung)
    # 3. Phụ lục: Phiếu học tập + Rubric năng lực số – AI (soạn từ giáo án đã chốt)
    print("📎 Đang soạn Phụ lục (Phiếu học tập + Rubric NLS–AI)...")
    try:
        phu_luc = tao_phu_luc(noi_dung, ten_bai, lop, cac_model)
    except Exception as e:
        print(f"⚠️ Không soạn được Phụ lục: {type(e).__name__}: {str(e)[:200]}")
        phu_luc = ""
    toan_bai = noi_dung.rstrip() + ("\n\n" + phu_luc.strip() if phu_luc.strip() else "")
    canh_bao = kiem_cau_truc(toan_bai, kiem_phu_luc=True)
    for c in canh_bao:
        print("⚠️ Cấu trúc còn thiếu: " + c)
    if not canh_bao:
        print("✅ Cấu trúc đạt: mục tiêu NLS–AI, bảng 2 cột, ≥ 50% hoạt động tích hợp, có Phiếu học tập và Rubric.")
    tep = xuat_file_word_giao_an(toan_bai, ten_bai, THU_MUC_RA, lop)
    tom_tat = os.environ.get("GITHUB_STEP_SUMMARY")
    if tom_tat:
        with open(tom_tat, "a", encoding="utf-8") as f:
            f.write("# KHBD: %s (lớp %s)\n\nModel soạn: `%s` · Rà soát chéo Groq: %s\n\nBản Word: tải ở mục **Artifacts** (%s).\n\n"
                    % (ten_bai, lop, _NHAT_KY["model"], "đã áp dụng" if da_cheo else "không áp dụng", os.path.basename(tep)))
            f.write(("**Kiểm cấu trúc:** " + ("đạt ✅" if not canh_bao else "còn thiếu ⚠️ – " + " | ".join(canh_bao))) + "\n\n---\n\n%s\n" % toan_bai)
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
    soan_tay(lop, ten_bai, os.environ.get("YCCD", "").strip(), cac_model)


if __name__ == "__main__":
    main()
