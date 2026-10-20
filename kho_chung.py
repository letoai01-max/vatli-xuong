import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai

# 1. Cấu hình Gemini API từ biến môi trường của GitHub Secrets
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-pro')

# 2. Kết nối Google Sheets qua tài khoản dịch vụ
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_path = "credentials.json"
creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
client = gspread.authorize(creds)

# Mở file Google Sheets quản lý Kho chung của thầy (Thầy nhớ đổi tên sheet cho khớp với file của mình)
sheet_name = "Kho chung"  
sheet = client.open(sheet_name).worksheet("DocDe") 

def xu_ly_kho_chung():
    print("Đang quét dữ liệu từ Kho chung...")
    data = sheet.get_all_records()
    
    for index, row in enumerate(data, start=2):
        trang_thai = row.get("TrangThai")
        noi_dung_de = row.get("NoiDungDe")
        
        if trang_thai == "Chờ xử lý":
            print(f"Đang xử lý dòng {index}...")
            
            # Gửi cho Gemini bóc tách, phân loại và chuẩn hóa câu hỏi Vật lý
            prompt = f"Hãy bóc tách, phân loại và chuẩn hóa các câu hỏi Vật lý sau đây sang định dạng chuẩn, rõ ràng: {noi_dung_de}"
            response = model.generate_content(prompt)
            ket_qua = response.text
            
            # Ghi kết quả trả lại Google Sheets
            sheet.update_cell(index, 3, "Đã hoàn thành")
            sheet.update_cell(index, 4, ket_qua)
            print(f"Đã xử lý xong dòng {index}!")

if __name__ == "__main__":
    xu_ly_kho_chung()
