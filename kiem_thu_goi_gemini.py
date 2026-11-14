"""kiem_thu_goi_gemini.py – giả lập 429 theo phút / theo ngày, 404, phản hồi rỗng, khoá hỏng (400 API_KEY_INVALID) để kiểm tra de_cuong.goi_gemini / doc_de.goi_gemini.
Chạy: python kiem_thu_goi_gemini.py (không cần khoá thật). Sai kết quả mong đợi → thoát mã khác 0 (GitHub Actions báo đỏ)."""
import sys, types, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for ten in ("gspread", "googleapiclient", "googleapiclient.http", "googleapiclient.discovery", "google", "google.oauth2", "google.oauth2.service_account"):
    try: __import__(ten)
    except ImportError:
        m = types.ModuleType(ten); m.MediaFileUpload = m.MediaIoBaseDownload = m.MediaIoBaseUpload = object
        m.build = lambda *a, **k: None; m.service_account = types.ModuleType("sa"); m.Credentials = object
        sys.modules[ten] = m
try: import sympy
except ImportError:
    sympy = types.ModuleType("sympy"); sympy.Symbol = lambda x: x; sympy.Lambda = lambda *a: None
    for n in "sqrt sin cos tan asin acos atan exp log pi E".split(): setattr(sympy, n, None)
    sys.modules["sympy"] = sympy
import requests, time
time.sleep = lambda s: print("   (ngủ %.0fs)" % s)
import doc_de as X, de_cuong as DC
assert DC.HetHanMuc is X.HetHanMuc, "khác lớp HetHanMuc"
print("OK: cùng lớp HetHanMuc")

class R:
    def __init__(s, code, body): s.status_code, s._b = code, body; s.text = json.dumps(body)
    def json(s): return s._b
def ok(t): return R(200, {"candidates": [{"content": {"parts": [{"text": t}]}, "finishReason": "STOP"}]})
def e429(kind): 
    return R(429, {"error": {"message": "Quota exceeded for metric ... %s" % kind, "details": [{"retryDelay": "3s"}]}})

def chay(ten, kich_ban, khoa, models=("m1", "m2")):
    """Chạy một kịch bản; trả (kết quả, lỗi, danh sách lượt gọi). Không tự nuốt lỗi: nơi gọi tự assert."""
    print("\n==", ten)
    for k in list(os.environ):
        if k.startswith("GEMINI_API_KEY"): del os.environ[k]
    os.environ.update(khoa)
    X.TRANG_THAI_KHOA.update({"tra_phi": False, "da_dung_tra_phi": 0, "het": set(), "hong": set()})
    goi = []
    def post(url, headers=None, data=None, timeout=0):
        goi.append((url.split("/models/")[1].split(":")[0], headers["x-goog-api-key"]))
        return kich_ban(goi[-1], len(goi))
    requests.post = post
    kq, loi = None, None
    try:
        kq = DC.goi_gemini("he", "nguoi", False, list(models))
        print("   KQ:", kq)
    except Exception as e:
        loi = e
        print("   NÉM:", type(e).__name__, str(e)[:100])
    print("   Lượt gọi:", goi)
    return kq, loi, goi

def e400_khoa():
    return R(400, {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT",
                             "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "API_KEY_INVALID"}]}})

kq, loi, goi = chay("1. 429 theo phút → chờ rồi thử lại cùng khoá",
     lambda c, n: e429("PerMinute") if n == 1 else ok("xin chào"), {"GEMINI_API_KEY": "K1"})
assert kq == ("xin chào", "m1") and goi == [("m1", "K1"), ("m1", "K1")], (kq, goi)

kq, loi, goi = chay("2. khoá 1 hết NGÀY → sang khoá 2",
     lambda c, n: e429("PerDay") if c[1] == "K1" else ok("từ khoá 2"), {"GEMINI_API_KEY": "K1", "GEMINI_API_KEY_2": "K2"})
assert kq == ("từ khoá 2", "m1") and goi[-1] == ("m1", "K2"), (kq, goi)

kq, loi, goi = chay("3. mọi khoá miễn phí hết ngày, có khoá trả phí → dùng trả phí",
     lambda c, n: e429("PerDay") if c[1] in ("K1", "K2") else ok("trả phí"),
     {"GEMINI_API_KEY": "K1", "GEMINI_API_KEY_2": "K2", "GEMINI_API_KEY_TRA_PHI": "KP"})
assert kq == ("trả phí", "m1") and goi[-1] == ("m1", "KP"), (kq, goi)

kq, loi, goi = chay("4. hết sạch → HetHanMuc",
     lambda c, n: e429("PerDay"), {"GEMINI_API_KEY": "K1"})
assert isinstance(loi, X.HetHanMuc), loi

kq, loi, goi = chay("5. phản hồi rỗng ở model 1 → model 2",
     lambda c, n: R(200, {"candidates": [{"content": {"parts": []}, "finishReason": "SAFETY"}]}) if c[0] == "m1" else ok("model 2"),
     {"GEMINI_API_KEY": "K1"})
assert kq == ("model 2", "m2"), (kq, goi)

kq, loi, goi = chay("6. 404 model ngừng → lấy model Google gợi ý",
     lambda c, n: R(404, {"error": {"message": "models/m1 is not found. Try models/gemini-9.9-flash"}}) if c[0] == "m1" else ok("model gợi ý"),
     {"GEMINI_API_KEY": "K1"}, models=("m1",))
assert kq == ("model gợi ý", "gemini-9.9-flash"), (kq, goi)

kq, loi, goi = chay("7. khoá 1 HỎNG (400 API_KEY_INVALID) → bỏ khoá, sang khoá 2, không thử model 2 bằng khoá hỏng",
     lambda c, n: e400_khoa() if c[1] == "K1" else ok("từ khoá 2"), {"GEMINI_API_KEY": "K1", "GEMINI_API_KEY_2": "K2"})
assert kq == ("từ khoá 2", "m1") and goi == [("m1", "K1"), ("m1", "K2")], (kq, loi, goi)
assert X.TRANG_THAI_KHOA["hong"] == {"GEMINI_API_KEY"}, X.TRANG_THAI_KHOA

n0 = len(goi)
X.goi_gemini({"contents": [], "generationConfig": {}}, ["m1", "m2"])
assert goi[n0:] == [("m1", "K2")], "lượt gọi sau vẫn đụng khoá hỏng: %s" % goi[n0:]
print("\nOK 8: lượt gọi sau không đụng lại khoá hỏng")

kq, loi, goi = chay("9. mọi khoá miễn phí hỏng, không có khoá trả phí → KhoaHong (không giả làm hết hạn mức)",
     lambda c, n: e400_khoa(), {"GEMINI_API_KEY": "K1", "GEMINI_API_KEY_2": "K2"})
assert isinstance(loi, X.KhoaHong) and not isinstance(loi, X.HetHanMuc), repr(loi)

kq, loi, goi = chay("10. khoá miễn phí hỏng + khoá 2 hết NGÀY → dùng khoá trả phí",
     lambda c, n: e400_khoa() if c[1] == "K1" else (e429("PerDay") if c[1] == "K2" else ok("trả phí")),
     {"GEMINI_API_KEY": "K1", "GEMINI_API_KEY_2": "K2", "GEMINI_API_KEY_TRA_PHI": "KP"})
assert kq == ("trả phí", "m1") and goi[-1] == ("m1", "KP"), (kq, goi)

kq, loi, goi = chay("11. 400 KHÔNG liên quan khoá (thinking) vẫn xử lý như cũ, không đánh dấu khoá hỏng",
     lambda c, n: R(400, {"error": {"message": "Thinking config is not supported for this model"}}) if n == 1 else ok("đã bỏ thinking"),
     {"GEMINI_API_KEY": "K1"})
assert kq == ("đã bỏ thinking", "m1") and not X.TRANG_THAI_KHOA["hong"], (kq, X.TRANG_THAI_KHOA)
assert X.la_loi_khoa(400, "API key not valid") and X.la_loi_khoa(403, "Your API key was reported as leaked.")
assert not X.la_loi_khoa(400, "Thinking config") and not X.la_loi_khoa(429, "API key")

kq, loi, goi = chay("12. đọc đủ GEMINI_API_KEY_1 … _5, bỏ khoá trùng giá trị",
     lambda c, n: e429("PerDay") if c[1] in ("K0", "K1", "K2") else ok("từ khoá 4"),
     {"GEMINI_API_KEY": "K0", "GEMINI_API_KEY_1": "K1", "GEMINI_API_KEY_2": "K2", "GEMINI_API_KEY_3": "K0", "GEMINI_API_KEY_4": "K4", "GEMINI_API_KEY_5": "K5"}, models=("m1",))
assert [k for _, k in X.ds_khoa_mien_phi()] == ["K0", "K1", "K2", "K4", "K5"], X.ds_khoa_mien_phi()
assert kq == ("từ khoá 4", "m1"), (kq, goi)

print("\nTẤT CẢ ĐẠT (12 kịch bản gọi Gemini)")
