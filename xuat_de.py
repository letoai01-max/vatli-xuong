"""
xuat_de.py – XUẤT NGÂN HÀNG CÂU HỎI ra questions.json cho trang điều khiển (index.html).
SỬA 24/10: đọc khoá từ biến môi trường GOOGLE_CREDENTIALS (trước đọc credentials.json không có trên GitHub → lỗi);
           tìm cột theo TIÊU ĐỀ thay vì số cột cố định; bỏ câu "Loại".
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
    if os.path.isfile("credentials.json"):          # chạy trên máy cá nhân
        return gspread.authorize(Credentials.from_service_account_file("credentials.json", scopes=SCOPES))
    sys.exit("Thiếu GOOGLE_CREDENTIALS.")


def main():
    gc = ket_noi()
    d = gc.open_by_key(ID_KHO_CHUNG).worksheet("NganHangCauHoi").get_all_values()
    td = [t.strip() for t in d[0]]
    cot = lambda ten: td.index(ten) if ten in td else None
    c = {k: cot(v) for k, v in {"ma_cau": "Mã câu", "noi_dung": "Nội dung", "phuong_an": "Phương án", "dap_an": "Đáp án",
                                "loi_giai": "Lời giải / HDC", "trang_thai": "Trạng thái duyệt"}.items()}
    c["link_anh"] = cot("Link ảnh") if cot("Link ảnh") is not None else 22   # cột W nếu chưa có tiêu đề
    if c["ma_cau"] is None or c["noi_dung"] is None:
        sys.exit("Không thấy cột 'Mã câu' / 'Nội dung' trong NganHangCauHoi.")
    lay = lambda r, k: (r[c[k]].strip() if c[k] is not None and c[k] < len(r) else "")
    ds = []
    for r in d[1:]:
        ma, nd = lay(r, "ma_cau"), lay(r, "noi_dung")
        if not ma.startswith("C-") or len(nd) <= 5 or lay(r, "trang_thai") == "Loại":
            continue
        ds.append({k: lay(r, k) for k in c})
    with open("questions.json", "w", encoding="utf-8") as f:
        json.dump(ds, f, ensure_ascii=False, indent=2)
    print("✨ Đã xuất %d câu hỏi vào questions.json" % len(ds))
    if not ds:
        sys.exit("Không xuất được câu nào – kiểm tra tab NganHangCauHoi.")


if __name__ == "__main__":
    main()
