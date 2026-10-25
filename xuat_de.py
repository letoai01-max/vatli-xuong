"""
xuat_de.py – XUẤT NGÂN HÀNG CÂU HỎI ra questions.json cho trang điều khiển (index.html).
CẬP NHẬT: Xử lý tìm kiếm toàn bộ chỉ số cột bằng tên tiêu đề để tránh lỗi kiểu dữ liệu, 
đồng thời lọc bỏ hoàn toàn các câu đã duyệt ("AI duyệt", "Đã duyệt") hoặc bị "Loại".
"""
import json, os, sys
import gspread
from google.oauth2.service_account import Credentials

ID_KHO_CHUNG = os.environ.get("SHEET_ID") or "1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

def ket_noi():
    raw = os.environ.get("GOOGLE_CREDENTIALS", "").strip()
    if raw:
        return gspread.authorize(Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES))
    if os.path.isfile("credentials.json"):  # Chạy trên máy cá nhân
        return gspread.authorize(Credentials.from_service_account_file("credentials.json", scopes=SCOPES))
    sys.exit("Thiếu GOOGLE_CREDENTIALS.")

def main():
    gc = ket_noi()
    d = gc.open_by_key(ID_KHO_CHUNG).worksheet("NganHangCauHoi").get_all_values()
    
    if not d or len(d) < 2:
        sys.exit("Tab NganHangCauHoi trống hoặc không đủ dữ liệu.")
        
    td = [t.strip() for t in d[0]]
    cot = lambda ten: td.index(ten) if ten in td else None
    
    # Xác định chính xác chỉ số cột dựa theo tiêu đề trên Google Sheet
    c = {
        "ma_cau": cot("Masa") if cot("Masa") is not None else cot("Mã câu"), 
        "noi_dung": cot("Nội dung"), 
        "phuong_an": cot("Phương án"), 
        "dap_an": cot("Đáp án"),
        "loi_giai": cot("Lời giải / HDC") if cot("Lời giải / HDC") is not None else cot("Lời giải"), 
        "trang_thai": cot("Trạng thái duyệt"),
        "link_anh": cot("Link ảnh") if cot("Link ảnh") is not None else 22  # Mặc định cột W (index 22) nếu chưa có tiêu đề
    }
    
    # Fallback vị trí cố định chuẩn Kho chung nếu không tìm thấy tiêu đề
    if c["ma_cau"] is None: c["ma_cau"] = 0       # Cột A
    if c["noi_dung"] is None: c["noi_dung"] = 6   # Cột G
    if c["phuong_an"] is None: c["phuong_an"] = 7 # Cột H
    if c["dap_an"] is None: c["dap_an"] = 8       # Cột I
    if c["loi_giai"] is None: c["loi_giai"] = 9   # Cột J
    if c["trang_thai"] is None: c["trang_thai"] = 20 # Cột U

    lay = lambda r, idx: (r[idx].strip() if idx is not None and idx < len(r) else "")
    
    ds = []
    for r in d[1:]:
        ma = lay(r, c["ma_cau"])
        nd = lay(r, c["noi_dung"])
        trang_thai = lay(r, c["trang_thai"]).lower()
        
        # BỘ LỌC CHẶT CHẼ:
        # 1. Mã câu phải bắt đầu bằng "C-"
        # 2. Nội dung phải hợp lệ (> 5 kí tự)
        # 3. BỎ QUA hoàn toàn các câu đã duyệt ("ai duyệt", "đã duyệt") hoặc bị "loại"
        is_processed = "ai duyệt" in trang_thai or "đã duyệt" in trang_thai or "loại" in trang_thai
        
        if not ma.startswith("C-") or len(nd) <= 5 or is_processed:
            continue
            
        ds.append({
            "ma_cau": ma,
            "noi_dung": nd,
            "phuong_an": lay(r, c["phuong_an"]),
            "dap_an": lay(r, c["dap_an"]),
            "loi_giai": lay(r, c["loi_giai"]),
            "trang_thai": lay(r, c["trang_thai"]),
            "link_anh": lay(r, c["link_anh"])
        })
        
    with open("questions.json", "w", encoding="utf-8") as f:
        json.dump(ds, f, ensure_ascii=False, indent=2)
        
    print(f"✨ Đã xuất thành công {len(ds)} câu hỏi chưa duyệt vào questions.json!")

if __name__ == "__main__":
    main()
