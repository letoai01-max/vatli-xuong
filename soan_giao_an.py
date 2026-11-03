import os
import json
import io
import datetime as dt
import gspread
from google.oauth2 import service_account
import google.generativeai as genai
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

# ---------------- CẤU HÌNH HỆ THỐNG ----------------
ID_KHO_CHUNG = "1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc"
TAB_CAU_HINH = "CauHinh"
TZ = dt.timezone(dt.timedelta(hours=7))

def khoi_tao_gemini():
    """Khởi tạo kết nối Gemini API theo chuẩn xưởng"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Chưa thiết lập biến môi trường GEMINI_API_KEY.")
    genai.configure(api_key=api_key)
    # Sử dụng mô hình chủ lực của xưởng
    return genai.GenerativeModel("gemini-1.5-pro")

def lay_cau_hinh_tu_sheet(sh):
    """Đọc các công tắc bật/tắt từ tab CauHinh trên Kho chung"""
    try:
        ws = sh.worksheet(TAB_CAU_HINH)
        data = ws.get_all_values()
        config = {}
        for row in data[1:]: # Bỏ qua dòng tiêu đề
            if len(row) >= 2:
                key = row[0].strip()
                val = row[1].strip().lower() == "true"
                config[key] = val
        return config
    except Exception as e:
        print(f"⚠️ Lỗi đọc tab CauHinh (chạy mặc định): {e}")
        return {}

def tao_khung_giao_an_cv5512(ten_bai_hoc, lop, yeu_cau_can_dat):
    """
    Hàm gọi AI tạo kế hoạch bài dạy tuân thủ tuyệt đối Phụ lục 1 Công văn 5512
    """
    model = khoi_tao_gemini()
    
    prompt = f"""
    Bạn là một giáo viên môn Vật lí THPT giỏi chuyên môn tại trường THPT Thủy Sơn.
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
    """
    
    response = model.generate_content(prompt)
    return response.text

def xuat_file_word_giao_an(noi_dung_markdown, ten_bai_hoc):
    """
    Tự động định dạng và xuất nội dung giáo án ra file Word (.docx) 
    theo chuẩn: Times New Roman, cỡ chữ 13, lề chuẩn hành chính.
    """
    doc = Document()
    
    # Thiết lập lề trang giấy (Trên: ~2cm, Dưới: ~2cm, Trái: ~3cm, Phải: ~1.5cm)
    for section in doc.sections:
        section.top_margin = Inches(0.79)
        section.bottom_margin = Inches(0.79)
        section.left_margin = Inches(1.18)
        section.right_margin = Inches(0.59)

    # Tiêu đề bài học
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_title = p_title.add_run(f"KẾ HOẠCH BÀI DẠY: {ten_bai_hoc.upper()}")
    run_title.font.name = 'Times New Roman'
    run_title.font.size = Pt(14)
    run_title.font.bold = True
    
    # Thêm nội dung chi tiết vào tệp Word
    for line in noi_dung_markdown.split('\n'):
        p = doc.add_paragraph()
        run = p.add_run(line)
        run.font.name = 'Times New Roman'
        run.font.size = Pt(13)  # Cỡ chữ chuẩn 13
        p.paragraph_format.line_spacing = 1.15

    # Lưu tệp
    ten_file_out = f"KHBD_{ten_bai_hoc.replace(' ', '_')}.docx"
    doc.save(ten_file_out)
    print(f"📄 Đã xuất file Word thành công: {ten_file_out}")
    return ten_file_out

def main():
    print("--- BẮT ĐẦU CHẠY MODULE SOẠN GIÁO ÁN TỰ ĐỘNG ---")
    if "GOOGLE_CREDENTIALS" not in os.environ:
        print("❌ Lỗi: Chưa thiết lập biến môi trường GOOGLE_CREDENTIALS.")
        return
        
    tt = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    cred = service_account.Credentials.from_service_account_info(
        tt, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    gc = gspread.authorize(cred)
    sh = gc.open_by_key(ID_KHO_CHUNG)
    print("✅ Đã kết nối thành công với Kho chung trên Google Drive!")

    # Đọc cấu hình từ tab CauHinh
    config = lay_cau_hinh_tu_sheet(sh)
    bat_tat_tong = config.get("BAT_TAT_SOAN_GIAO_AN", True)
    
    if not bat_tat_tong:
        print("⏸️ Công tắc tổng BAT_TAT_SOAN_GIAO_AN đang tắt. Dừng thực thi.")
        return

    print("🚀 Hệ thống sẵn sàng xử lý soạn giáo án theo cấu hình thời gian thực.")

if __name__ == "__main__":
    main()
