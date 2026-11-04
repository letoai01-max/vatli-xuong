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

YÊU CẦU BỔ SUNG (soạn tay, bản 04/11/2026): (1) Word xuất ra không còn khoảng trắng giữa các dòng/đoạn (giãn đoạn 0, bỏ đoạn trống);
  (2) đồ thị vẽ bằng code có mũi tên ở đầu hai trục; (3) hoạt động dùng hình SGK → dòng [[ANH_SGK]]: so sánh nội dung hoạt động với ảnh trong
  kho ảnh SGK trên Google Drive (thư mục đặt ở KHO_ANH_SGK_ID), chèn ảnh khớp + câu "Kết nối nội dung"; không có ảnh khớp thì để chỗ cho GV chèn.

Công tắc ở tab CauHinh của Kho chung: BAT_TAT_SOAN_GIAO_AN, SOAN_GIAO_AN_LOP_10 / _11 / _12 (mặc định bật).
Vòng rà soát chéo Groq dùng công tắc VONG_KIEM_TRA_THU_HAI_GROQ (xem groq_xuong.cong_tac_bat).
Biến môi trường: GOOGLE_CREDENTIALS, GEMINI_API_KEY; tuỳ chọn GROQ_API_KEY, GROQ_MODELS.
"""
import datetime as dt
import base64
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

import requests
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
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

D. SỐ THẬP PHÂN dùng dấu phẩy; công thức viết bằng LaTeX trong $...$.

E. DẤU $ VÀ CHỖ ĐIỀN TRỐNG. Dấu $ chỉ bao MỘT công thức hoàn chỉnh và sát chữ: viết $v = s/t$, không viết $ v = s/t $; không bao giờ
   kết thúc công thức bằng dấu "=" rồi mới đóng $. Chỗ trống cho học sinh điền thì chỉ đặt kí hiệu trong $, còn dấu "=" và dòng chấm nằm ngoài:
   ví dụ  $m$ = ........ kg ;  $h = s$ = ........ m ;  $t$ = ........ s.

F. GẠCH ĐẦU DÒNG THEO CHUẨN VĂN BẢN HÀNH CHÍNH. Ý liệt kê cấp 1 mở đầu bằng dấu gạch ngang "-" (dấu "+" cho ý nhỏ hơn, cấp 2); không dùng •, *, ○, ► hay số thứ tự
   thay cho gạch đầu dòng. Mỗi ý kết thúc bằng dấu chấm phẩy (;), ý cuối cùng kết thúc bằng dấu chấm (.). Trong ô của bảng, liệt kê bằng <br>- ... (mỗi ý một lần <br>)."""

QUY_DINH_HINH = """G. HÌNH ẢNH, BẢNG BIỂU, ĐỒ THỊ CHO TỪNG HOẠT ĐỘNG (bắt buộc ở MỖI hoạt động 1-4, đặt ngay sau mục b) Nội dung):
   Mỗi hoạt động có ít nhất MỘT trong ba loại minh hoạ dưới đây, đúng nội dung bài, số liệu hợp lí, KHÔNG làm lộ đáp án mà học sinh phải tự tìm:
   (1) BẢNG SỐ LIỆU: bảng Markdown thường (không phải bảng GV–HS), có dòng tên "**Bảng n. ...**" ngay phía trên, số thập phân dùng dấu phẩy.
   (2) ĐỒ THỊ: MỘT dòng riêng, JSON viết trên MỘT dòng, đúng khuôn:
       [[DO_THI: {"chuThich": "Đồ thị ...", "truc_x": "t (s)", "truc_y": "v (m/s)", "duong": [{"ten": "...", "diem": [[0,0],[1,2],[2,4]]}]}]]
       (tối đa 4 đường, mỗi đường 2-12 điểm; muốn lưới trống cho học sinh tự vẽ thì bỏ "duong" và thêm "xmax", "ymax", "luoi": true.)
   (3) HÌNH VẼ (sơ đồ lực, mặt phẳng nghiêng, vật, lò xo, mạch điện...): MỘT dòng riêng, JSON trên MỘT dòng:
       [[HINH: {"chuThich": "Sơ đồ ...", "moTa": "mô tả thật cụ thể các vật, vị trí, lực, nhãn cần vẽ"}]]
       (hình vẽ bằng code nên dựng chậm: tối đa 2 dòng [[HINH]] trong cả bài; ưu tiên bảng số liệu và đồ thị.)
   Không yêu cầu ảnh chụp thực tế; không viết tên tệp ảnh hay đường dẫn. Chú thích ghi trong "chuThich", hệ thống tự đánh số "Hình n."."""


QUY_DINH_ANH_SGK = """H. HÌNH TRONG SÁCH GIÁO KHOA (SGK Vật lí, bộ Kết nối tri thức) – KẾT NỐI VỚI KHO ẢNH SGK TRÊN GOOGLE DRIVE:
   Chỉ khi nội dung hoạt động THỰC SỰ dùng hoặc đối chiếu một hình của SGK (ví dụ "quan sát Hình 2.1 SGK", sơ đồ thí nghiệm, đồ thị, hình minh hoạ của bài),
   thêm ngay sau mục b) MỘT dòng riêng, JSON viết trên MỘT dòng, đúng khuôn:
       [[ANH_SGK: {"chuThich": "Hình ... (SGK)", "hinhSGK": "Hình 2.1", "tuKhoa": "từ khoá nội dung hình, ví dụ: thí nghiệm rơi tự do; đồ thị độ dịch chuyển – thời gian"}]]
   Hệ thống sẽ SO SÁNH nội dung hoạt động với các ảnh trong kho ảnh SGK rồi chèn ảnh khớp nhất kèm câu kết nối nội dung.
   Tối đa 3 dòng [[ANH_SGK]] trong cả bài; không bịa số hình SGK nếu không chắc chắn (bỏ trường "hinhSGK"); không dùng cho hình tự vẽ (dùng [[HINH]] hoặc [[DO_THI]]).
   Ở mục b) và trong bảng d), nêu rõ học sinh quan sát hình SGK nào và rút ra điều gì từ hình; không viết tên tệp ảnh."""


def tao_khung_giao_an_cv5512(ten_bai_hoc, lop, yeu_cau_can_dat, cac_model=None, hinh=False, anh_sgk=False):
    """
    Bước 1: Gọi Gemini tạo phần CHÍNH của Kế hoạch bài dạy (I, II, III) theo Phụ lục 1 Công văn 5512
    + yêu cầu riêng của tổ (năng lực số – AI, bảng 2 cột, tích hợp ≥ 50%). Phần Phụ lục soạn ở bước sau.
    """
    quy_dinh = QUY_DINH_BO_SUNG + (("\n\n" + QUY_DINH_HINH) if hinh else "") + (("\n\n" + QUY_DINH_ANH_SGK) if (hinh and anh_sgk) else "")
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

    {quy_dinh}
    """
    text, model = DC.goi_gemini(he, nguoi, False, cac_model or [DC.MODEL_MAC_DINH])
    _NHAT_KY["model"] = model
    return text


PHU_LUC_YEU_CAU = """Dưới đây là Kế hoạch bài dạy bài "@TEN@" (lớp @LOP@). Hãy soạn PHỤ LỤC đặt ở cuối bài, đúng cấu trúc sau
(dùng đúng các tiêu đề, không thêm lời dẫn):

## PHỤ LỤC 1: HỌC LIỆU – PHIẾU HỌC TẬP
Soạn đúng 2 phiếu, mỗi phiếu vừa MỘT trang A4, bám sát đúng bài, đúng hoạt động và đúng thiết bị/công cụ đã nêu trong giáo án, vừa sức học sinh lớp @LOP@:
- **PHIẾU HỌC TẬP SỐ 1** (gắn Hoạt động 2 – hình thành kiến thức): 3-4 nhiệm vụ đánh số theo trình tự thu thập → xử lí → rút ra kết luận.
  Gồm: đọc thông tin hoặc làm thí nghiệm/mô phỏng đã nêu trong giáo án; ghi vào BẢNG SỐ LIỆU có ô trống (tiêu đề cột có đơn vị);
  vẽ đồ thị trên lưới trống; trả lời 1-2 câu rút ra nhận xét hoặc công thức.
- **PHIẾU HỌC TẬP SỐ 2** (gắn Hoạt động 3 và 4 – luyện tập, vận dụng): 3 câu trắc nghiệm ngắn (A, B, C, D), 1 bài tự luận tính toán có số liệu cụ thể,
  1 tình huống vận dụng thực tế gần gũi với học sinh THPT (đo đạc/ước lượng ở trường, ở nhà); xếp từ dễ đến khó.
- Mỗi phiếu: dòng "Họ và tên/Nhóm/Lớp: ......", tên hoạt động gắn với phiếu, nhiệm vụ đánh số; chỗ trống là dòng chấm ...... hoặc ô trống của bảng.
- Phiếu gắn hoạt động có tích hợp năng lực số – AI có MỘT bảng gọn "Kiểm chứng đầu ra của AI" gồm 3 cột
  (Câu lệnh em đã dùng | Đối chiếu SGK/thí nghiệm/tính toán | Đúng – Sai, em chỉnh lại) và 2 hàng trống.
- Cuối mỗi phiếu có mục "*Gợi ý đáp án (dành cho GV)*" 2-4 dòng, số liệu đúng.
- Được dùng MỘT dòng đồ thị/hình theo khuôn  [[DO_THI: {"chuThich": "...", "truc_x": "...", "truc_y": "...", "xmax": 10, "ymax": 20, "luoi": true}]]  (lưới trống cho học sinh vẽ)
  hoặc  [[HINH: {"chuThich": "...", "moTa": "..."}]]  khi phiếu cần hình; JSON trên một dòng.
- Chỗ điền trống viết  $m$ = ........ kg  (kí hiệu trong $, dấu "=" và dòng chấm ở ngoài $); không đặt dấu $ quanh dòng chấm; không để khoảng trắng sát dấu $.
- Liệt kê dùng gạch đầu dòng "-" (ý nhỏ hơn dùng "+"), không dùng •.

## PHỤ LỤC 2: RUBRIC ĐÁNH GIÁ NĂNG LỰC SỐ VÀ NĂNG LỰC AI
- Một bảng Markdown NGẮN GỌN, 4 cột "Tiêu chí" | "Mức 1 – Cần cố gắng" | "Mức 2 – Đạt" | "Mức 3 – Tốt", đúng 4 hàng:
  2 tiêu chí năng lực số (ghi "NLS – ...", ví dụ khai thác dữ liệu; xử lí và biểu diễn số liệu) và
  2 tiêu chí năng lực AI (ghi "AI – ...", ví dụ viết câu lệnh rõ mục đích; kiểm chứng đầu ra và dùng AI trung thực).
- Mỗi ô mô tả tối đa 15 từ, là biểu hiện quan sát được gắn với nội dung bài; mỗi ô một dòng của bảng.
- Dưới bảng chỉ MỘT dòng: Mức 1 = 1 điểm, Mức 2 = 2 điểm, Mức 3 = 3 điểm; tổng 4-6 Cần cố gắng, 7-9 Đạt, 10-12 Tốt; ai đánh giá và ở hoạt động nào.

Số thập phân dùng dấu phẩy; công thức viết bằng LaTeX trong $...$.

KẾ HOẠCH BÀI DẠY:
@GIAO_AN@
"""


def tao_phu_luc(giao_an, ten_bai_hoc, lop, cac_model=None):
    """Bước 3: soạn PHỤ LỤC (2 Phiếu học tập sát bài + Rubric NLS–AI rút gọn 4 tiêu chí) dựa trên giáo án đã chốt."""
    he = ("Bạn là giáo viên Vật lí THPT giỏi, chuyên soạn học liệu và công cụ đánh giá năng lực "
          "(Công văn 5512; Khung năng lực số cho người học, Thông tư 02/2025/TT-BGDĐT).")
    nguoi = (PHU_LUC_YEU_CAU.replace("@TEN@", str(ten_bai_hoc)).replace("@LOP@", str(lop))
             .replace("@GIAO_AN@", giao_an[:40000]))
    text, model = DC.goi_gemini(he, nguoi, False, cac_model or [DC.MODEL_MAC_DINH])
    return text


# ---------------- KIỂM CẤU TRÚC GIÁO ÁN ----------------
RE_HOAT_DONG = re.compile(r"^[#*\s\d.]*Hoạt động\s+(\d+)\s*[:：.\-–—]", re.I | re.M)
RE_TICH_HOP = re.compile(r"Tích hợp\s+NLS\W+AI\W*(Có|Không)\b", re.I)


def kiem_cau_truc(md, kiem_phu_luc=False, kiem_hinh=False):
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
    if kiem_hinh:
        chinh = re.split(r"^[#*\s]*PHỤ LỤC\b", md, flags=re.I | re.M)[0]
        moc = [(m.start(), int(m.group(1))) for m in RE_HOAT_DONG.finditer(chinh)]
        for k, (vt, so_hd) in enumerate(moc):
            doan = chinh[vt: moc[k + 1][0] if k + 1 < len(moc) else len(chinh)]
            co_ma = bool(re.search(r"\[\[(HINH|DO_THI|ANH_SGK):", doan))
            bang = [kh for kh in re.split(r"\n\s*\n", doan)
                    if kh.lstrip().startswith("|") and not re.search(r"hoạt động của giáo viên", kh, re.I)]
            if not (co_ma or bang):
                loi.append("Hoạt động %d chưa có hình / bảng số liệu / đồ thị minh hoạ." % so_hd)
    if kiem_phu_luc:
        if len(set(re.findall(r"PHIẾU HỌC TẬP SỐ\s*(\d+)", md, re.I))) < 2:
            loi.append("Phụ lục chưa có đủ 2 Phiếu học tập.")
        rb = re.search(r"RUBRIC[\s\S]*", md, re.I)
        if not rb:
            loi.append("Phụ lục chưa có Rubric.")
        elif not (re.search(r"\bNLS\b|năng lực số", rb.group(0), re.I) and re.search(r"\bAI\b|trí tuệ nhân tạo", rb.group(0), re.I)):
            loi.append("Rubric chưa tách tiêu chí năng lực số và năng lực AI.")
    return loi


def sua_loi_cau_truc(noi_dung, loi, cac_model=None, hinh=False, anh_sgk=False):
    """Nhờ Gemini sửa MỘT lần các lỗi cấu trúc; trả bản mới (hoặc bản cũ nếu không cải thiện)."""
    he = "Bạn là giáo viên Vật lí THPT giỏi, đang hoàn thiện Kế hoạch bài dạy theo Công văn 5512."
    nguoi = ("Kế hoạch bài dạy dưới đây còn các lỗi cấu trúc sau, hãy sửa TẤT CẢ và trả về TOÀN BỘ giáo án hoàn chỉnh "
             "(giữ nguyên phần đã đạt, không thêm lời dẫn, không soạn Phụ lục):\n- " + "\n- ".join(loi) +
             "\n\n" + QUY_DINH_BO_SUNG + (("\n\n" + QUY_DINH_HINH) if hinh else "") + (("\n\n" + QUY_DINH_ANH_SGK) if (hinh and anh_sgk) else "")
             + "\n\nGIÁO ÁN HIỆN TẠI:\n" + noi_dung[:40000])
    try:
        moi, _ = DC.goi_gemini(he, nguoi, False, cac_model or [DC.MODEL_MAC_DINH])
    except Exception as e:
        print("⚠️ Không sửa được lỗi cấu trúc (%s) – giữ bản cũ." % type(e).__name__)
        return noi_dung
    loi_moi = kiem_cau_truc(moi, kiem_hinh=hinh)
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
        "dòng 'Tích hợp NLS – AI: Có/Không' của từng hoạt động và dòng 'Năng lực số và năng lực AI' ở mục tiêu, "
        "các dòng [[HINH: {...}]], [[DO_THI: {...}]] và [[ANH_SGK: {...}]] (giữ nguyên từng kí tự), mọi bảng số liệu, gạch đầu dòng '-' và cách viết chỗ trống '$m$ = ........ kg'. "
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
            dem_ma = lambda t: len(re.findall(r"\[\[(?:HINH|DO_THI|ANH_SGK):", t))
            if dem_ma(moi) < dem_ma(noi_dung_giao_an):
                print(f"⚠️ Bản rà soát của {model} làm mất hình / đồ thị đã chèn – giữ bản gốc.")
                continue
            if len(kiem_cau_truc(moi)) > loi_goc:
                print(f"⚠️ Bản rà soát của {model} làm mất cấu trúc yêu cầu (bảng 2 cột / tích hợp NLS–AI) – giữ bản gốc.")
                continue
            print(f"✅ Kiểm tra chéo hoàn tất ({model}).")
            return moi, True
        print(f"⚠️ Bản rà soát của {model} không đầy đủ ({ch.get('finish_reason')}, {len(moi)}/{len(noi_dung_giao_an)} kí tự) – giữ bản gốc.")
    return noi_dung_giao_an, False


# ---------------- CHUẨN DẤU $ (lỗi "$m = $ ........") ----------------
RE_TOAN = re.compile(r"(?<!\\)\$([^$\n]*?)(?<!\\)\$")


def _sua_toan(m):
    ct = m.group(1).strip()
    if not ct:
        return " "
    if ct.endswith("="):                       # "$m = $" → "$m$ ="  (dấu = nằm ngoài công thức)
        ct = ct[:-1].rstrip()
        return ("$%s$ =" % ct) if ct else "="
    return "$%s$" % ct


def _chuan_dong_toan(d):
    ra, vt = [], 0
    for m in RE_TOAN.finditer(d):
        ra.append(re.sub(r"(?<!\\)\$", r"\\$", d[vt:m.start()]))
        ra.append(_sua_toan(m))
        vt = m.end()
    ra.append(re.sub(r"(?<!\\)\$", r"\\$", d[vt:]))
    return "".join(ra)


def chuan_cong_thuc(md):
    """Bỏ khoảng trắng sát dấu $, đưa dấu '=' ra ngoài công thức ($m = $ → $m$ =), và thoát dấu $ lẻ
    để pandoc không để lộ $ thô trong Word. Khối $$...$$ giữ nguyên."""
    phan = re.split(r"(\$\$[\s\S]*?\$\$)", str(md or ""))
    for i in range(0, len(phan), 2):
        phan[i] = "\n".join(_chuan_dong_toan(d) for d in phan[i].split("\n"))
    return "".join(phan)


# ---------------- HÌNH VẼ / ĐỒ THỊ CHO CÁC HOẠT ĐỘNG ----------------
RE_MA_HINH = re.compile(r"^\s*\[\[(HINH|DO_THI|ANH_SGK):\s*(\{.*\})\s*\]\]\s*$")
MAU_DT = ["#000000", "#1f4e79", "#a61c00", "#38761d"]


def ve_do_thi_ga(spec, duong_dan):
    """Đồ thị từ số liệu bằng matplotlib: tối đa 4 đường (đường + điểm); không có đường nhưng có xmax/ymax → lưới trống cho học sinh vẽ."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    fig, ax = plt.subplots(figsize=(6.4, 4.0), dpi=150)
    co_duong = False
    for i, d in enumerate((spec.get("duong") or [])[:4]):
        diem = []
        for q in d.get("diem") or []:
            try:
                diem.append((float(q[0]), float(q[1])))
            except (TypeError, ValueError, IndexError):
                pass
        if len(diem) < 2:
            continue
        co_duong = True
        xs, ys = zip(*diem[:30])
        ax.plot(xs, ys, marker="o", ms=4, lw=1.6, color=MAU_DT[i], label=d.get("ten") or None)
    if not co_duong and not (spec.get("xmax") and spec.get("ymax")):
        plt.close(fig)
        raise ValueError("đồ thị không có đường (≥ 2 điểm) và cũng không có xmax/ymax")
    if spec.get("xmax"):
        ax.set_xlim(float(spec.get("xmin", 0)), float(spec["xmax"]))
    if spec.get("ymax"):
        ax.set_ylim(float(spec.get("ymin", 0)), float(spec["ymax"]))
    dau_phay = FuncFormatter(lambda v, _: ("%g" % v).replace(".", ","))
    ax.xaxis.set_major_formatter(dau_phay)
    ax.yaxis.set_major_formatter(dau_phay)
    ax.set_xlabel(str(spec.get("truc_x") or ""), fontsize=10)
    ax.set_ylabel(str(spec.get("truc_y") or ""), fontsize=10)
    if spec.get("tieuDe"):
        ax.set_title(str(spec["tieuDe"]), fontsize=11)
    ax.grid(True, ls=":", lw=0.7, color="#888888")
    for ten in ("top", "right"):
        ax.spines[ten].set_visible(False)
    # mũi tên ở đầu hai trục (cuối trục x bên phải, cuối trục y phía trên) – đặt theo toạ độ khung nên đúng cả khi trục không bắt đầu từ 0
    ax.plot(1, 0, ">", color="black", ms=8, transform=ax.transAxes, clip_on=False, zorder=10, scalex=False, scaley=False)
    ax.plot(0, 1, "^", color="black", ms=8, transform=ax.transAxes, clip_on=False, zorder=10, scalex=False, scaley=False)
    if any(d.get("ten") for d in (spec.get("duong") or [])[:4]):
        ax.legend(fontsize=8, frameon=False)
    fig.savefig(duong_dan, bbox_inches="tight", pad_inches=0.12, facecolor="white")
    plt.close(fig)


def _ve_hinh_xuong(spec, duong_dan, cac_model, ten_bai, so):
    """Hình vẽ (lực, mặt phẳng nghiêng, mạch điện…) bằng bộ vẽ của xưởng (ve_hinh.py): Gemini lập sơ đồ → vẽ code → tự kiểm."""
    import ve_hinh as VH                 # nạp muộn: kéo theo thư viện Google, chỉ cần khi thật sự có [[HINH]]
    if not spec.get("moTa"):
        raise ValueError("thiếu 'moTa'")
    muc = {"cauHoi": "Bài học: %s" % ten_bai, "chuThich": spec.get("chuThich", ""), "moTa": spec["moTa"]}
    png, _ = VH.ve_mot_hinh(muc, cac_model, os.path.dirname(duong_dan), 900 + so)
    shutil.move(png, duong_dan)


# ---------------- KHO ẢNH SGK TRÊN GOOGLE DRIVE ----------------
MIME_THU_MUC = "application/vnd.google-apps.folder"
TOI_DA_ANH_KHO = 8000          # chặn kho quá lớn làm chậm lượt chạy
TOI_DA_UNG_VIEN = 4            # số ảnh ứng viên đưa cho Gemini so sánh với nội dung hoạt động
TOI_DA_ANH_SGK = 4             # số dòng [[ANH_SGK]] được xử lí trong một bài
TU_DUNG = {"cua", "cho", "cac", "mot", "nhung", "trong", "voi", "khi", "duoc", "hinh", "anh", "sgk", "bai", "vat", "ket", "noi", "tri", "thuc"}


def _khong_dau(x):
    x = unicodedata.normalize("NFD", str(x or ""))
    return "".join(c for c in x if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D").lower()


def ids_kho_anh():
    """Danh sách thư mục gốc kho ảnh SGK dạng [(ID, lớp)] từ biến KHO_ANH_SGK_ID (GitHub Variables) hoặc khoá KHO_ANH_SGK_ID ở tab CauHinhDong.
    Chỉ cần ID thư mục GỐC (xưởng tự duyệt mọi thư mục con). Có thể khai nhiều thư mục gốc, cách nhau dấu phẩy, chấm phẩy hoặc xuống dòng;
    mỗi mục là ID hoặc cả đường liên kết (tự cắt '?hl=vi'…). Muốn gán lớp cho cả thư mục (khi tên thư mục không có chữ Lop10/11/12) thì viết
    '10=<ID>' (lớp 10), '11=<ID>', '12=<ID>'. Các thư mục phải được chia sẻ cho tài khoản dịch vụ."""
    v = (os.environ.get("KHO_ANH_SGK_ID") or os.environ.get("CFG_KHO_ANH_SGK_ID") or "").strip()
    ra, thay = [], set()
    for mot in re.split(r"[,;\n\r]+", v):
        mot = mot.strip()
        if not mot:
            continue
        lop = ""
        ml = re.match(r"^(?:lop|khoi)?\s*(1[0-2])\s*[=:]\s*(.+)$", mot, flags=re.I)
        if ml:
            lop, mot = ml.group(1), ml.group(2).strip()
        m = re.search(r"/folders/([\w-]+)", mot) or re.search(r"[?&]id=([\w-]+)", mot)
        x = m.group(1) if m else re.split(r"[?&#/\s]", mot)[0]
        if x and x not in thay:
            thay.add(x)
            ra.append((x, lop))
    return ra


def id_kho_anh():
    """ID thư mục gốc đầu tiên (giữ cho nơi gọi cũ); '' nếu chưa cấu hình."""
    ds = ids_kho_anh()
    return ds[0][0] if ds else ""


def nap_kho_anh(drive):
    """Liệt kê ảnh trong thư mục kho ảnh SGK (kể cả thư mục con và lối tắt Drive): [{id, ten, mo_ta, duong, mime}]. Rỗng nếu chưa cấu hình hoặc lỗi."""
    gocs = ids_kho_anh()
    if not gocs:
        print("ℹ️ Chưa cấu hình KHO_ANH_SGK_ID – bỏ qua việc kết nối hình SGK với kho ảnh.", flush=True)
        return []
    if drive is None:
        return []
    ds, hang, da, loai = [], [(g, ("Lop%s" % lp) if lp else "") for g, lp in gocs], set(), {}
    try:
        for goc, _ in gocs:
            try:
                g = drive.files().get(fileId=goc, fields="name,mimeType", supportsAllDrives=True).execute()
                print("📁 Thư mục gốc kho ảnh: '%s' (%s)" % (g.get("name"), "thư mục" if g.get("mimeType") == MIME_THU_MUC else "KHÔNG phải thư mục: " + str(g.get("mimeType"))), flush=True)
            except Exception as e:
                print("⚠️ Không mở được thư mục gốc %s… (%s) – kiểm tra ID và quyền chia sẻ." % (goc[:8], type(e).__name__), flush=True)
        while hang and len(ds) < TOI_DA_ANH_KHO:
            tm, duong = hang.pop(0)
            if tm in da:
                continue
            da.add(tm)
            tiep = None
            while True:
                r = drive.files().list(q="'%s' in parents and trashed=false" % tm, spaces="drive", pageSize=1000, pageToken=tiep,
                                       fields="nextPageToken, files(id,name,mimeType,description,shortcutDetails(targetId,targetMimeType))",
                                       supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
                for f in r.get("files", []):
                    mime, fid = str(f.get("mimeType", "")), f["id"]
                    if mime == "application/vnd.google-apps.shortcut":          # lối tắt: đi theo đích của nó
                        sd = f.get("shortcutDetails") or {}
                        mime, fid = str(sd.get("targetMimeType", "")), sd.get("targetId") or fid
                    loai[mime] = loai.get(mime, 0) + 1
                    if mime == MIME_THU_MUC:
                        hang.append((fid, (duong + "/" + f.get("name", "")).strip("/")))
                    elif mime.startswith("image/"):
                        ds.append({"id": fid, "ten": f.get("name", ""), "mo_ta": f.get("description") or "", "duong": duong, "mime": mime})
                tiep = r.get("nextPageToken")
                if not tiep:
                    break
    except Exception as e:
        print("⚠️ Không đọc được kho ảnh SGK (%s: %s) – kiểm tra ID và quyền chia sẻ cho tài khoản dịch vụ." % (type(e).__name__, str(e)[:150]), flush=True)
    chi_muc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chi_muc_anh.json")   # do gan_mo_ta_anh.py tạo (khi không ghi được mô tả lên Drive)
    if ds and os.path.isfile(chi_muc):
        try:
            cm = json.load(open(chi_muc, encoding="utf-8"))
            for f in ds:
                if not f["mo_ta"] and f["id"] in cm:
                    f["mo_ta"] = str(cm[f["id"]].get("mo_ta") or "")
        except Exception as e:
            print("⚠️ Không đọc được chi_muc_anh.json (%s)" % type(e).__name__, flush=True)
    if ds:
        print("🖼️ Kho ảnh SGK: %d ảnh." % len(ds), flush=True)
    else:
        print("⚠️ Kho ảnh SGK trống hoặc không có ảnh nào. Đã thấy trong kho (theo loại tệp): %s" % (
            ", ".join("%s × %d" % (k or "?", v) for k, v in sorted(loai.items(), key=lambda t: -t[1])[:6]) or "không thấy tệp hay thư mục nào"), flush=True)
    return ds


def _tu_khoa(x):
    return {t for t in re.findall(r"[a-z0-9]+", _khong_dau(x)) if len(t) >= 3 and t not in TU_DUNG}


def _so_hinh(x):
    """'Hình 2.1', 'hinh_2-1', 'H2.1' → '2.1' (None nếu không có)."""
    m = re.search(r"h(?:inh)?[\s_\-]*(\d+)\s*[._\-]\s*(\d+)", _khong_dau(x))
    return "%s.%s" % (m.group(1), m.group(2)) if m else None


def _lop_cua_anh(f):
    """Đoán lớp (10/11/12) của ảnh từ đường dẫn thư mục + tên tệp: 'Lop10', 'Khoi_11', 'Vat li 12', thư mục tên '10'… ('' nếu không rõ)."""
    t = _khong_dau(str(f.get("duong") or "") + "/" + str(f.get("ten") or ""))
    m = (re.search(r"(?:lop|khoi|vat\s*li|vl|sgk|cd|chuyen\s*de)[\s_\-]*(1[0-2])(?!\d)", t)
         or re.search(r"(?:^|/)(1[0-2])(?:/|$)", t))
    return m.group(1) if m else ""


def tim_ung_vien_anh(kho_ds, spec, khoi, ten_bai, loai_tru=(), lop=""):
    """Xếp hạng ảnh theo độ trùng từ khoá (tên tệp, đường dẫn thư mục, mô tả) + trùng số hình SGK; trả tối đa TOI_DA_UNG_VIEN ảnh."""
    goc = " ".join(str(spec.get(k) or "") for k in ("chuThich", "hinhSGK", "tuKhoa"))
    can = _tu_khoa(goc) | _tu_khoa(ten_bai)
    so_can = _so_hinh(str(spec.get("hinhSGK") or "") + " " + str(spec.get("chuThich") or ""))
    xep = []
    for f in kho_ds:
        if f["id"] in loai_tru:
            continue
        lop_anh = _lop_cua_anh(f)
        if lop and lop_anh and lop_anh != str(lop):          # ảnh của lớp khác: loại (cùng số hình ở các lớp rất dễ nhầm)
            continue
        diem = 0.0
        diem += 2.0 * len(can & _tu_khoa(f["ten"])) + 1.0 * len(can & _tu_khoa(f["duong"])) + 1.5 * len(can & _tu_khoa(f["mo_ta"]))
        if so_can and so_can in {_so_hinh(f["ten"]), _so_hinh(f["mo_ta"])}:
            diem += 6.0
        if diem >= 2.0:
            if lop and lop_anh == str(lop):
                diem += 1.5                                  # ảnh đúng lớp được ưu tiên
            xep.append((diem, f))
    xep.sort(key=lambda t: -t[0])
    return [f for _, f in xep[:TOI_DA_UNG_VIEN]]


def _tai_anh(drive, f, ra_png):
    """Tải ảnh từ Drive, lưu PNG (cạnh dài tối đa 1600 px) và trả bản JPEG nhỏ (base64) để Gemini so sánh."""
    from PIL import Image
    buf = io.BytesIO()
    tai = DC.MediaIoBaseDownload(buf, drive.files().get_media(fileId=f["id"], supportsAllDrives=True))
    xong = False
    while not xong:
        _, xong = tai.next_chunk()
    buf.seek(0)
    im = Image.open(buf)
    im.load()
    if im.mode in ("RGBA", "LA", "P"):
        nen = Image.new("RGB", im.size, (255, 255, 255))
        im = im.convert("RGBA")
        nen.paste(im, mask=im.split()[-1])
        im = nen
    else:
        im = im.convert("RGB")
    im.thumbnail((1600, 1600))
    im.save(ra_png, "PNG")
    nho = im.copy()
    nho.thumbnail((900, 900))
    b = io.BytesIO()
    nho.save(b, "JPEG", quality=85)
    return base64.b64encode(b.getvalue()).decode("ascii")


def so_sanh_anh_sgk(spec, khoi, ung_vien, cac_model, ten_bai):
    """Nhờ Gemini (đọc ảnh) so sánh nội dung hoạt động với từng ảnh ứng viên; trả (chỉ số ảnh 0-based, dict kết quả) hoặc (None, dict)."""
    import ve_hinh as VH                 # nạp muộn: kéo theo thư viện Google, chỉ cần khi thật sự có [[ANH_SGK]]
    phan = [{"text": (
        "Bạn là giáo viên Vật lí THPT. Dưới đây là NỘI DUNG MỘT HOẠT ĐỘNG trong Kế hoạch bài dạy bài \"%s\" và các ảnh ứng viên lấy từ kho ảnh SGK.\n"
        "Hình SGK mà hoạt động cần: %s | từ khoá: %s | chú thích dự kiến: %s\n\nNỘI DUNG HOẠT ĐỘNG:\n%s\n\n"
        "NHIỆM VỤ: so sánh từng ảnh với nội dung hoạt động. Chọn ảnh thể hiện ĐÚNG hiện tượng / thiết bị / đồ thị / số liệu mà hoạt động dùng "
        "(không chọn ảnh chỉ trùng từ khoá nhưng khác nội dung; nếu có số hình SGK thì ưu tiên ảnh đúng số hình đó). "
        "Trả về JSON: {\"chon\": số thứ tự ảnh 1..%d, hoặc 0 nếu KHÔNG ảnh nào phù hợp, \"doKhop\": \"cao\"|\"vua\"|\"thap\", "
        "\"lyDo\": \"một câu\", \"chuThich\": \"chú thích ngắn cho hình (không đánh số hình)\", "
        "\"ketNoi\": \"1-2 câu kết nối nội dung hoạt động với hình: hình thể hiện gì, học sinh quan sát chỗ nào, đối chiếu với kiến thức nào của bài; "
        "KHÔNG nêu đáp án mà học sinh phải tự tìm\"}." % (
            ten_bai, spec.get("hinhSGK") or "(không nêu)", spec.get("tuKhoa") or "", spec.get("chuThich") or "", khoi, len(ung_vien)))}]
    for i, (f, b64) in enumerate(ung_vien, 1):
        phan.append({"text": "Ảnh %d – tệp: %s | thư mục: %s | mô tả: %s" % (i, f["ten"], f["duong"] or "(gốc)", f["mo_ta"][:150])})
        phan.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})
    kq, _ = VH.goi_json(phan, cac_model, 0.1)
    try:
        chon = int(kq.get("chon") or 0)
    except (TypeError, ValueError):
        chon = 0
    if 1 <= chon <= len(ung_vien) and str(kq.get("doKhop", "")).lower() in ("cao", "vua"):
        return chon - 1, kq
    return None, kq


def lay_anh_sgk(spec, khoi, dich_png, kho, cac_model, ten_bai):
    """Tìm - tải - so sánh - lưu ảnh SGK cho một dòng [[ANH_SGK]]; trả dict {chuThich, ketNoi}. Ném RuntimeError nếu không có ảnh khớp."""
    if not kho or not kho.get("ds"):
        raise RuntimeError("chưa cấu hình / không đọc được kho ảnh SGK (KHO_ANH_SGK_ID)")
    uv = tim_ung_vien_anh(kho["ds"], spec, khoi, ten_bai, kho["da_dung"], kho.get("lop", ""))
    if not uv:
        raise RuntimeError("kho ảnh không có ảnh trùng từ khoá (%s)" % (spec.get("hinhSGK") or spec.get("tuKhoa") or spec.get("chuThich") or "")[:60])
    tep_tam, co_anh = [], []
    thu = os.path.dirname(dich_png)
    for k, f in enumerate(uv):
        tam = os.path.join(thu, "ung_vien_%d_%d.png" % (id(spec) % 10000, k))
        try:
            co_anh.append((f, _tai_anh(kho["drive"], f, tam)))
            tep_tam.append(tam)
        except Exception as e:
            print("⚠️ Không tải được ảnh kho '%s' (%s)" % (f["ten"], type(e).__name__), flush=True)
            tep_tam.append(None)
    # giữ tương ứng chỉ số giữa danh sách tải được và tệp tạm
    hop_le = [(f, b64, t) for (f, b64), t in zip(co_anh, [t for t in tep_tam if t])]
    if not hop_le:
        raise RuntimeError("không tải được ảnh ứng viên nào từ kho")
    try:
        vt, kq = so_sanh_anh_sgk(spec, khoi, [(f, b64) for f, b64, _ in hop_le], cac_model, ten_bai)
        if vt is None:
            raise RuntimeError("so sánh nội dung: không ảnh nào khớp (%s)" % str(kq.get("lyDo") or "")[:100])
        f, _, tam = hop_le[vt]
        shutil.copyfile(tam, dich_png)
        kho["da_dung"].add(f["id"])
        print("🔗 Ảnh SGK khớp: %s (độ khớp %s)" % (f["ten"], kq.get("doKhop")), flush=True)
        return {"chuThich": str(kq.get("chuThich") or "").strip(), "ketNoi": str(kq.get("ketNoi") or "").strip(), "tep": f["ten"]}
    finally:
        for _, _, t in hop_le:
            try:
                os.remove(t)
            except OSError:
                pass


def chen_hinh(md, thu_hinh, cac_model=None, ten_bai="", kho=None):
    """Thay mỗi dòng [[DO_THI: {...}]] / [[HINH: {...}]] / [[ANH_SGK: {...}]] bằng ảnh + chú thích 'Hình n.' (tự đánh số).
    [[ANH_SGK]]: so sánh nội dung hoạt động với ảnh trong kho ảnh SGK trên Drive (kho = {drive, ds, da_dung}), chèn ảnh khớp và câu kết nối nội dung.
    Hình nào không vẽ / không tìm được thì để dòng chú thích '[… GV tự chèn …]' để giáo án vẫn đủ chỗ, và ghi vào danh sách lỗi."""
    os.makedirs(thu_hinh, exist_ok=True)
    ra, so, loi, so_sgk = [], 0, [], 0
    dong_ds = str(md or "").split("\n")
    dau_hd = [i for i, d in enumerate(dong_ds) if RE_HOAT_DONG.match(d)]

    def khoi_hd(i):                        # nội dung hoạt động chứa dòng thứ i (để so sánh với ảnh)
        truoc = max([k for k in dau_hd if k <= i] or [0])
        sau = min([k for k in dau_hd if k > i] or [len(dong_ds)])
        return re.sub(r"^\s*\[\[(?:HINH|DO_THI|ANH_SGK):.*$", "", "\n".join(dong_ds[truoc:sau]), flags=re.M)[:3500]

    for vi_tri, dong in enumerate(dong_ds):
        m = RE_MA_HINH.match(dong)
        if not m:
            ra.append(dong)
            continue
        loai, so = m.group(1), so + 1
        try:
            spec = json.loads(m.group(2))
        except ValueError as e:
            loi.append("Hình %d: JSON không đọc được (%s)" % (so, str(e)[:60]))
            ra += ["", '::: {custom-style="Chu thich hinh"}', "*[Hình %d – GV tự chèn hình/đồ thị minh hoạ]*" % so, ":::", ""]
            continue
        ten_tep = os.path.join(thu_hinh, "hinh%d.png" % so)
        ct = re.sub(r"^\s*Hình\s*\d+\s*[.:]\s*(?!\d)", "", str(spec.get("chuThich") or "")).strip()
        ket_noi = ""
        try:
            if loai == "DO_THI":
                ve_do_thi_ga(spec, ten_tep)
            elif loai == "ANH_SGK":
                so_sgk += 1
                if so_sgk > TOI_DA_ANH_SGK:
                    raise RuntimeError("vượt %d dòng [[ANH_SGK]] cho một bài" % TOI_DA_ANH_SGK)
                kq = lay_anh_sgk(spec, khoi_hd(vi_tri), ten_tep, kho, cac_model or [DC.MODEL_MAC_DINH], ten_bai)
                ct = ct or re.sub(r"^\s*Hình\s*\d+\s*[.:]\s*(?!\d)", "", kq["chuThich"]).strip()
                ket_noi = kq["ketNoi"]
            else:
                _ve_hinh_xuong(spec, ten_tep, cac_model or [DC.MODEL_MAC_DINH], ten_bai, so)
            ra += ["", '::: {custom-style="Hinh minh hoa"}', "![](%s){width=%s}" % (ten_tep, "4.2in" if loai == "DO_THI" else "4.6in"), ":::",
                   "", '::: {custom-style="Chu thich hinh"}', "*Hình %d. %s*" % (so, ct) if ct else "*Hình %d.*" % so, ":::", ""]
            if ket_noi:
                ra += ["**Kết nối nội dung:** " + ket_noi.replace("\n", " "), ""]
        except Exception as e:
            loi.append("Hình %d (%s): %s: %s" % (so, loai, type(e).__name__, str(e)[:120]))
            ra += ["", '::: {custom-style="Chu thich hinh"}',
                   ("*[Hình %d. %s – GV tự chèn %s]*" % (so, ct, "hình SGK tương ứng" if loai == "ANH_SGK" else "hình/đồ thị minh hoạ")) if ct
                   else "*[Hình %d – GV tự chèn hình/đồ thị minh hoạ]*" % so,
                   ":::", ""]
    return "\n".join(ra), so - len(loi), loi


def an_ma_hinh(md):
    """Cho trang Summary: dòng [[HINH/DO_THI: {...}]] hiện gọn thành '[Hình/đồ thị: chú thích]' (không để lộ JSON)."""
    def gon(m):
        try:
            return "*[%s: %s]*" % ({"DO_THI": "Đồ thị", "ANH_SGK": "Ảnh SGK"}.get(m.group(1), "Hình"), json.loads(m.group(2)).get("chuThich", ""))
        except ValueError:
            return "*[Hình/đồ thị]*"
    return "\n".join(RE_MA_HINH.sub(gon, d) if RE_MA_HINH.match(d) else d for d in str(md or "").split("\n"))


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
    md = re.sub(r"\$\$[\s\S]*?\$\$|\$[^$\n]+\$", _so_thap_phan, chuan_cong_thuc(md))
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
                dong = re.sub(r"\s*<br\s*/?>\s*[-*•+]\s+", " <br>- ", dong, flags=re.I)
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
        if RE_GACH.match(dong) and not la_bang:       # gạch đầu dòng chuẩn: cấp 1 "-", cấp 2 "+" (chỉ khi ngay sau một gạch đầu dòng)
            cap2 = RE_GACH.match(truoc) is not None and (dong.lstrip().startswith("+") or len(dong) - len(dong.lstrip()) >= 2)
            dong = ("    - " if cap2 else "- ") + RE_GACH.sub("", dong, count=1)
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


def _gach_dau_dong(d):
    """Đổi dấu đầu dòng của pandoc thành gạch đầu dòng chuẩn văn bản: cấp 1 "-", cấp 2 "+", phông Times New Roman, thụt lề treo."""
    try:
        goc = d.part.numbering_part.element
    except Exception:
        return
    for lvl in goc.iter(qn("w:lvl")):
        nf = lvl.find(qn("w:numFmt"))
        if nf is None or nf.get(qn("w:val")) != "bullet":
            continue
        cap = int(lvl.get(qn("w:ilvl")) or 0)
        lt = lvl.find(qn("w:lvlText"))
        if lt is None:
            continue
        lt.set(qn("w:val"), "-" if cap % 2 == 0 else "+")
        for cu in lvl.findall(qn("w:rPr")):
            lvl.remove(cu)
        rpr = OxmlElement("w:rPr")
        rf = OxmlElement("w:rFonts")
        for k in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rf.set(qn(k), PHONG)
        rpr.append(rf)
        lvl.append(rpr)
        ppr = lvl.find(qn("w:pPr"))
        if ppr is None:
            ppr = OxmlElement("w:pPr")
            lvl.insert(0, ppr)
        for cu in ppr.findall(qn("w:ind")):
            ppr.remove(cu)
        ind = OxmlElement("w:ind")
        ind.set(qn("w:left"), str(567 + 425 * cap))
        ind.set(qn("w:hanging"), "283")
        ppr.append(ind)


def _la_doan_trong(p):
    """Đoạn không chữ, không ảnh, không công thức, không ngắt dòng/trang."""
    if p.text.strip():
        return False
    x = p._p.xml
    return not any(t in x for t in ("<w:drawing", "<w:pict", "<w:br", "<m:oMath", "<w:sectPr", "<w:object", "<w:fldChar"))


def _bo_khoang_trang(d):
    """Bỏ khoảng trắng giữa các dòng: giãn đoạn trước/sau = 0 và giãn dòng đơn ở mọi đoạn (kể cả trong bảng),
    xoá đoạn trống, ngắt trang bằng 'bắt đầu trang mới' thay cho đoạn chứa dấu ngắt (khỏi thừa một dòng trống đầu trang).
    Đoạn trống nằm giữa hai bảng liền nhau được thu thành đường 1pt để Word không dồn hai bảng làm một."""
    def chuan(p):
        pf = p.paragraph_format
        pf.space_before, pf.space_after, pf.line_spacing = Pt(0), Pt(0), 1.0

    def xoa(p):
        p._p.getparent().remove(p._p)

    for st in d.styles:
        if st.type == 1:
            pf = st.paragraph_format
            pf.space_before, pf.space_after, pf.line_spacing = Pt(0), Pt(0), 1.0
    ps = list(d.paragraphs)
    for i, p in enumerate(ps):
        if p.text.strip():
            continue
        if 'w:type="page"' in p._p.xml and i + 1 < len(ps):
            ps[i + 1].paragraph_format.page_break_before = True
            xoa(p)
        elif _la_doan_trong(p):
            truoc, sau = p._p.getprevious(), p._p.getnext()
            giua_hai_bang = (truoc is not None and sau is not None and truoc.tag == qn("w:tbl") and sau.tag == qn("w:tbl"))
            if giua_hai_bang:
                p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
                p.paragraph_format.line_spacing = Pt(1)
            else:
                xoa(p)
    for tbl in d.tables:
        for hang in tbl.rows:
            for o in hang.cells:
                ds = list(o.paragraphs)
                for p in ds:
                    if len(o.paragraphs) > 1 and _la_doan_trong(p):
                        xoa(p)
    for p in d.paragraphs:
        chuan(p)
    for tbl in d.tables:
        for hang in tbl.rows:
            for o in hang.cells:
                for p in o.paragraphs:
                    chuan(p)


def _dinh_dang_word(duong_dan):
    """Sau pandoc: Times New Roman 13, lề hành chính, tiêu đề đen, bảng có viền + dòng tiêu đề tô nền, bảng rộng hết khổ."""
    d = Document(duong_dan)
    _gach_dau_dong(d)
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
        if ten in ("Hinh minh hoa", "Chu thich hinh"):      # ảnh và chú thích hình: căn giữa, chú thích nghiêng cỡ 12
            st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
            st.paragraph_format.keep_with_next = (ten == "Hinh minh hoa")
            if ten == "Chu thich hinh":
                st.font.size, st.font.italic, st.font.bold = Pt(12), True, False
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
    _bo_khoang_trang(d)          # chạy cuối cùng để không bị phần định dạng phía trên ghi đè
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
    line = RE_GACH.sub("- ", line, count=1)
    p = doc.add_paragraph()
    p.paragraph_format.space_before, p.paragraph_format.space_after, p.paragraph_format.line_spacing = Pt(0), Pt(0), 1.0
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
            for p in o.paragraphs:
                p.paragraph_format.space_before, p.paragraph_format.space_after, p.paragraph_format.line_spacing = Pt(0), Pt(0), 1.0


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
    dong_ds, i, cho_ngat_trang = _chuan_markdown(md, pandoc=False).split("\n"), 0, False
    while i < len(dong_ds):
        d = dong_ds[i]
        if d.lstrip().startswith("|"):
            khoi = []
            while i < len(dong_ds) and dong_ds[i].lstrip().startswith("|"):
                khoi.append(dong_ds[i]); i += 1
            _ghi_bang(doc, khoi)
            j = i
            while j < len(dong_ds) and not dong_ds[j].strip():
                j += 1
            if j < len(dong_ds) and dong_ds[j].lstrip().startswith("|"):      # hai bảng liền nhau: chèn đoạn 1pt để Word không dồn làm một
                p_ngan = doc.add_paragraph()
                p_ngan.paragraph_format.space_before = p_ngan.paragraph_format.space_after = Pt(0)
                p_ngan.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
                p_ngan.paragraph_format.line_spacing = Pt(1)
            continue
        if d.strip() == "@@NGAT_TRANG@@":
            cho_ngat_trang = True
        elif d.strip().startswith(":::"):
            pass
        elif re.match(r"^\s*!\[\]\((.+?)\)", d):
            try:
                doc.add_picture(re.match(r"^\s*!\[\]\((.+?)\)", d).group(1), width=Inches(4.4))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            except Exception as e:
                print("⚠️ Không chèn được ảnh vào bản python-docx:", str(e)[:100])
        elif re.match(r"^\s*\*\[?Hình\b", d):
            p_ct = doc.add_paragraph()
            p_ct.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r_ct = p_ct.add_run(d.strip().strip("*"))
            r_ct.italic, r_ct.font.name, r_ct.font.size = True, PHONG, Pt(12)
        elif d.strip():
            _ghi_dong(doc, d)
            if cho_ngat_trang:                         # ngắt trang bằng "bắt đầu trang mới" ở đoạn kế tiếp, không để dòng trống
                doc.paragraphs[-1].paragraph_format.page_break_before = True
                cho_ngat_trang = False
        i += 1
    for p in doc.paragraphs:                           # mọi đoạn (kể cả tiêu đề, ảnh, chú thích): không giãn đoạn
        p.paragraph_format.space_before, p.paragraph_format.space_after = Pt(0), Pt(0)
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
            ra[so] = chuan_cong_thuc(text)
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
def soan_tay(lop, ten_bai, yccd, cac_model, drive=None):
    print(f"✍️ Soạn tay: {ten_bai} (lớp {lop})")
    kho_ds = nap_kho_anh(drive)                    # kho ảnh SGK trên Drive (rỗng nếu chưa cấu hình KHO_ANH_SGK_ID)
    kho = {"drive": drive, "ds": kho_ds, "da_dung": set(), "lop": lop} if kho_ds else None
    yccd = yccd or "(theo Chương trình GDPT 2018, sách Kết nối tri thức)"
    # 1. Phần chính (I–III, có hình/bảng/đồ thị cho từng hoạt động) + tự kiểm cấu trúc, sửa tối đa một lần
    noi_dung = tao_khung_giao_an_cv5512(ten_bai, lop, yccd, cac_model, hinh=True, anh_sgk=bool(kho))
    loi = kiem_cau_truc(noi_dung, kiem_hinh=True)
    if loi:
        print("⚠️ Cấu trúc chưa đạt: " + " | ".join(loi))
        noi_dung = sua_loi_cau_truc(noi_dung, loi, cac_model, hinh=True, anh_sgk=bool(kho))
    # 2. Groq rà soát chéo (chỉ nhận nếu giữ đủ cấu trúc và đủ hình/đồ thị)
    noi_dung, da_cheo = kiem_tra_cheo_groq(noi_dung)
    # 3. Phụ lục: 2 Phiếu học tập + Rubric NLS–AI rút gọn (soạn từ giáo án đã chốt)
    print("📎 Đang soạn Phụ lục (Phiếu học tập + Rubric NLS–AI)...")
    try:
        phu_luc = tao_phu_luc(noi_dung, ten_bai, lop, cac_model)
    except Exception as e:
        print(f"⚠️ Không soạn được Phụ lục: {type(e).__name__}: {str(e)[:200]}")
        phu_luc = ""
    toan_bai = noi_dung.rstrip() + ("\n\n" + phu_luc.strip() if phu_luc.strip() else "")
    canh_bao = kiem_cau_truc(toan_bai, kiem_phu_luc=True, kiem_hinh=True)
    for c in canh_bao:
        print("⚠️ Cấu trúc còn thiếu: " + c)
    if not canh_bao:
        print("✅ Cấu trúc đạt: mục tiêu NLS–AI, bảng 2 cột, ≥ 50% hoạt động tích hợp, mỗi hoạt động có hình/bảng/đồ thị, có Phiếu học tập và Rubric.")
    # 4. Vẽ đồ thị / hình và ghép vào bài, rồi xuất Word
    thu_hinh = tempfile.mkdtemp(prefix="hinh_")
    try:
        toan_bai_hinh, so_hinh_ok, loi_hinh = chen_hinh(toan_bai, thu_hinh, cac_model, ten_bai, kho)
        for c in loi_hinh:
            print("⚠️ " + c)
        print("🖼️ Đã ghép %d hình/đồ thị vào bài%s." % (so_hinh_ok, (", %d hình phải để chỗ cho GV chèn" % len(loi_hinh)) if loi_hinh else ""))
        tep = xuat_file_word_giao_an(toan_bai_hinh, ten_bai, THU_MUC_RA, lop)
    finally:
        shutil.rmtree(thu_hinh, ignore_errors=True)
    tom_tat = os.environ.get("GITHUB_STEP_SUMMARY")
    if tom_tat:
        tat_ca = canh_bao + loi_hinh
        with open(tom_tat, "a", encoding="utf-8") as f:
            f.write("# KHBD: %s (lớp %s)\n\nModel soạn: `%s` · Rà soát chéo Groq: %s · Hình/đồ thị ghép: %d · Ảnh kho SGK khớp: %d\n\nBản Word: tải ở mục **Artifacts** (%s).\n\n"
                    % (ten_bai, lop, _NHAT_KY["model"], "đã áp dụng" if da_cheo else "không áp dụng", so_hinh_ok, len(kho["da_dung"]) if kho else 0, os.path.basename(tep)))
            f.write(("**Kiểm cấu trúc:** " + ("đạt ✅" if not tat_ca else "còn thiếu ⚠️ – " + " | ".join(tat_ca))) + "\n\n---\n\n%s\n" % an_ma_hinh(toan_bai))
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
    soan_tay(lop, ten_bai, os.environ.get("YCCD", "").strip(), cac_model, drive)


if __name__ == "__main__":
    main()
