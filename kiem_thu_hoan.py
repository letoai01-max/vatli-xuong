"""kiem_thu_hoan.py – kiểm tra cách xưởng quyết định HOÀN bao lâu khi hết hạn mức Gemini (tao_de.phan_loai_hoan / phut_den_reset_gemini).
[15/11] Lỗi gốc: thông báo HetHanMuc không chứa chữ "ngày", nên hết lượt theo NGÀY vẫn bị coi là theo phút → Apps Script gửi lại sau 3' hàng chục lần.
Chạy: python kiem_thu_hoan.py (không cần khoá thật). Sai → thoát mã khác 0."""
import sys, types, os, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for ten in ("gspread", "googleapiclient", "googleapiclient.http", "googleapiclient.discovery", "google", "google.oauth2", "google.oauth2.service_account"):
    try: __import__(ten)
    except ImportError:
        m = types.ModuleType(ten); m.MediaFileUpload = m.MediaIoBaseDownload = m.MediaIoBaseUpload = object
        m.build = lambda *a, **k: None; m.service_account = types.ModuleType("sa"); m.Credentials = object
        sys.modules[ten] = m
import tao_de as T
import doc_de as X

UTC = dt.timezone.utc
def utc(*a): return dt.datetime(*a, tzinfo=UTC)

# 1. mốc reset (0h giờ Thái Bình Dương) + 10 phút
assert T.phut_den_reset_gemini(utc(2026, 11, 15, 10, 0)) == 22 * 60 + 10, T.phut_den_reset_gemini(utc(2026, 11, 15, 10, 0))   # 02:00 PST → còn 22h
assert T.phut_den_reset_gemini(utc(2026, 11, 15, 8, 0)) == 24 * 60 + 10       # đúng 0h PST → mốc kế là 24h sau
# 2. ngày đổi giờ mùa hè (8/3/2026): hôm đó chỉ có 23 giờ
assert T.phut_den_reset_gemini(utc(2026, 3, 8, 8, 0)) == 23 * 60 + 10, T.phut_den_reset_gemini(utc(2026, 3, 8, 8, 0))
# 3. không bao giờ ngắn hơn mức cũ
assert T.phut_den_reset_gemini(utc(2026, 11, 15, 7, 59, 59)) >= T.CHO_HOAN_PHUT["ngay"]
print("OK: mốc reset Gemini")

def loi(theo_ngay, tin="HET_HAN_MUC – mọi khoá miễn phí đã hết lượt: GEMINI_API_KEY"):
    e = X.HetHanMuc(tin); e.theo_ngay = theo_ngay; return e

os.environ.pop("HOAN_THEO_MOC_RESET", None); os.environ.pop("CFG_HOAN_THEO_MOC_RESET", None)
luc = utc(2026, 11, 15, 10, 0)
# 4. theo NGÀY (thông báo không có chữ "ngày") → chờ đến reset, KHÔNG còn 3'
assert T.phan_loai_hoan(loi(True), luc) == (True, 22 * 60 + 10), T.phan_loai_hoan(loi(True), luc)
# 5. theo PHÚT → 3'
assert T.phan_loai_hoan(loi(False), luc) == (False, T.CHO_HOAN_PHUT["phut"])
# 6. ngoại lệ không có thuộc tính (lớp cũ) và thông báo không có chữ → theo phút như trước
assert T.phan_loai_hoan(Exception("HET_HAN_MUC – x"), luc) == (False, T.CHO_HOAN_PHUT["phut"])
# 7. thông báo cũ có chữ "ngày" vẫn nhận ra
assert T.phan_loai_hoan(Exception("hết lượt trong ngày"), luc)[0] is True
print("OK: phân loại theo ngày / theo phút")

# 8. công tắc tắt → y như bản cũ (3' hoặc 8', chỉ đoán theo chữ)
os.environ["HOAN_THEO_MOC_RESET"] = "0"
assert T.phan_loai_hoan(loi(True), luc) == (False, 3), T.phan_loai_hoan(loi(True), luc)
assert T.phan_loai_hoan(Exception("hết lượt trong ngày"), luc) == (True, 8)
print("OK: công tắc HOAN_THEO_MOC_RESET=0 → hành xử như bản cũ")
print("\nTẤT CẢ ĐẠT (kiem_thu_hoan)")
