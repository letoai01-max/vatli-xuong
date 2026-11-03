import os
import json
import datetime as dt
import gspread
from google.oauth2 import service_account
import google.generativeai as genai

# Cấu hình kết nối Google Sheets & Kho chung
ID_KHO_CHUNG = "1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc"
TAB_GIAO_AN = "GiaoAn"  # Tab lưu dữ liệu hoặc yêu cầu soạn giáo án

def khoi_tao_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    # Sử dụng model chủ lực theo chuẩn xưởng
    return genai.GenerativeModel("gemini-1.5-pro") # hoặc gemini-3.8-flash tùy cấu hình hiện tại

def tao_khung_giao_an_cv5512(ten_bai_hoc, lop, yeu_cau_can_dat):
    """
    Hàm gọi AI tạo kế hoạch bài dạy tuân thủ tuyệt đối Phụ lục 1 Công văn 5512
    """
    model = khoi_tao_gemini()
    
    prompt = f"""
    Bạn là một giáo viên môn Vật lí THPT giỏi chuyên môn, giàu kinh nghiệm tại trường THPT Thủy Sơn.
    Hãy soạn Kế hoạch bài dạy (Giáo án) chi tiết cho bài học sau đây:
    - Tên bài học: {ten_bai_hoc}
    - Lớp: {lop}
    - Yêu cầu cần đạt (YCCĐ): {yeu_cau_can_dat}
    
    YÊU CẦU CẤU TRÚC TUYỆT ĐỐI TUÂN THỦ CÔNG VĂN 5512:
    I. MỤC TIÊU
    1. Về kiến thức
    2. Về năng lực (Năng lực chung và Năng lực đặc thù môn Vật lí)
    3. Về phẩm chất
    II. THIẾT BỊ DẠY HỌC VÀ HỌC LIỆU
    1. Đối với giáo viên (SGK, kế hoạch bài dạy, thí nghiệm mô phỏng nếu có)
    2. Đối với học sinh (Sách vở, chuẩn bị theo nhóm)
    III. TIẾN TRÌNH DẠY HỌC
    1. Hoạt động 1: Xác định vấn đề / Khởi động
    2. Hoạt động 2: Hình thành kiến thức mới (chia rõ các nội dung trọng tâm, tích hợp thí nghiệm vật lí / kỹ thuật số mozaweb)
    3. Hoạt động 3: Luyện tập
    4. Hoạt động 4: Vận dụng
    
    Lưu ý trình bày rõ ràng từng hoạt động theo 4 bước: a) Mục tiêu; b) Nội dung; c) Sản phẩm; d) Tổ chức thực hiện (Giao nhiệm vụ, Thực hiện, Báo cáo thảo luận, Kết luận nhận định).
    """
    
    response = model.generate_content(prompt)
    return response.text

def thuc_hien_soan_giao_an_tu_dong():
    print("--- BẮT ĐẦU CHẠY MODULE SOẠN GIÁO ÁN TỰ ĐỘNG TRÊN PYTHON ---")
    # Kết nối Google Sheets lấy danh sách bài cần soạn
    tt = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    cred = service_account.Credentials.from_service_account_info(
        tt, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    gc = gspread.authorize(cred)
    sh = gc.open_by_key(ID_KHO_CHUNG)
    
    # Đọc dữ liệu từ bảng điều khiển hoặc tab phân công chuyên môn
    print("Đã kết nối thành công với Kho chung trên Google Drive.")
    # (Thực hiện logic đọc danh sách bài học và vòng lặp gọi hàm tao_khung_giao_an_cv5512 ở đây)

if __name__ == "__main__":
    thuc_hien_soan_giao_an_tu_dong()
