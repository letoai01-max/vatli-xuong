"""
xuat_de.py – XUẤT NGÂN HÀNG CÂU HỎI ra questions.json (TỰ ĐỘNG LỌC TẬN GỐC)
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
    if os.path.isfile("credentials.json"):
        return gspread.authorize(Credentials.from_service_account_file("credentials.json", scopes=SCOPES))
    sys.exit("Thiếu GOOGLE_CREDENTIALS.")

def main():
    gc = ket_noi()
    d = gc.open_by_key(ID_KHO_CHUNG).worksheet("NganHangCauHoi").get_all_values()
    
    if not d or len(d) < 2:
        sys.exit("Tab NganHangCauHoi trống hoặc không đủ dữ liệu.")
        
    td = [t.strip() for t in d[0]]
    cot = lambda ten: td.index(ten) if ten in td else None
    
    c = {
        "ma_cau": cot("Mã câu") if cot("Mã câu") is not None else 0,
        "noi_dung": cot("Nội dung") if cot("Nội dung") is not None else 6,
        "phuong_an": cot("Phương án") if cot("Phương án") is not None else 7,
        "dap_an": cot("Đáp án") if cot("Đáp án") is not None else 8,
        "loi_giai": cot("Lời giải / HDC") if cot("Lời giải / HDC") is not None else 9,
        "trang_thai": cot("Trạng thái duyệt") if cot("Trạng thái duyệt") is not None else 20,
        "link_anh": cot("Link ảnh") if cot("Link ảnh") is not None else 22
    }

    lay = lambda r, idx: (r[idx].strip() if idx is not None and idx < len(r) else "")
    
    ds = []
    for r in d[1:]:
        ma = lay(r, c["ma_cau"])
        nd = lay(r, c["noi_dung"])
        trang_thai = lay(r, c["trang_thai"]).lower()
        
        # 💡 ĐIỀU KIỆN LỌC TẬN GỐC:
        # Chỉ lấy các câu bắt đầu bằng "C-" VÀ trạng thái phải là CHƯA DUYỆT 
        # (nghĩa là bỏ qua mọi câu đã có chữ "ai duyệt", "đã duyệt" hoặc "loại").
        is_da_duyet = "ai duyệt" in trang_thai or "đã duyệt" in trang_thai or "loại" in trang_thai
        
        if not ma.startswith("C-") or len(nd) <= 5 or is_da_duyet:
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
