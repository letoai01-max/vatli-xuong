"""
xuat_de.py – XUẤT NGÂN HÀNG CÂU HỎI ra questions.json cho trang điều khiển (index.html).
CẬP NHẬT: Chỉ xuất các câu hỏi chưa duyệt, tự động lọc bỏ các câu đã duyệt ("AI duyệt", "Đã duyệt") hoặc bị "Loại".
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
    td = [t.strip() for t in d[0]]
    cot = lambda ten: td.index(ten) if ten in td else None
    
    c = {
        "ma_cau": "Mã câu", 
        "noi_dung": "Nội dung", 
        "phuong_an": "Phương án", 
        "dap_an": "Đáp án",
        "loi_giai": "Lời giải / HDC", 
        "trang_thai": "Trạng thái duyệt"
    }
    c["link_anh"] = cot("Link ảnh") if cot("Link ảnh") is not None else 22  # Cột W nếu chưa có tiêu đề
    
    if c["ma_cau"] is None or c["noi_dung"] is None:
        sys.exit("Không thấy cột 'Mã câu' / 'Nội dung' trong NganHangCauHoi.")
        
    lay = lambda r, k: (r[c[k]].strip() if c[k] is not None and c[k] < len(r) else "")
    
    ds = []
    for r in d[1:]:
        ma = lay(r, "ma_cau")
        nd = lay(r, "noi_dung")
        trang_thai = lay(r, "trang_thai").lower()
        
        # BỘ LỌC CHẶT CHẼ:
        # 1. Mã câu phải bắt đầu bằng "C-"
        # 2. Nội dung phải hợp lệ (> 5 kí tự)
        # 3. BỎ QUA hoàn toàn các câu đã duyệt hoặc đã loại
        is_processed = "ai duyệt" in trang_thai or "đã duyệt" in trang_thai or "loại" in trang_thai
        
        if not ma.startswith("C-") or len(nd) <= 5 or is_processed:
            continue
            
        ds.append({k: lay(r, k) for k in c})
        
    with open("questions.json", "w", encoding="utf-8") as f:
        json.dump(ds, f, ensure_ascii=False, indent=2)
        
    print("✨ Đã xuất %d câu hỏi chưa duyệt vào questions.json" % len(ds))
    if not ds:
        print("ℹ️ Hiện tại không còn câu nào cần duyệt.")

if __name__ == "__main__":
    main()
