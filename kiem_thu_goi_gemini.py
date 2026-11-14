"""kiem_thu_goi_gemini.py – giả lập 429 theo phút / theo ngày, 404, phản hồi rỗng để kiểm tra de_cuong.goi_gemini. Chạy: python kiem_thu_goi_gemini.py (không cần khoá thật)."""
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
    print("\n==", ten)
    for k in list(os.environ):
        if k.startswith("GEMINI_API_KEY"): del os.environ[k]
    os.environ.update(khoa)
    X.TRANG_THAI_KHOA.update({"tra_phi": False, "da_dung_tra_phi": 0, "het": set()})
    goi = []
    def post(url, headers=None, data=None, timeout=0):
        goi.append((url.split("/models/")[1].split(":")[0], headers["x-goog-api-key"]))
        return kich_ban(goi[-1], len(goi))
    requests.post = post
    try:
        kq = DC.goi_gemini("he", "nguoi", False, list(models))
        print("   KQ:", kq)
    except Exception as e:
        print("   NÉM:", type(e).__name__, str(e)[:100])
    print("   Lượt gọi:", goi)

chay("1. 429 theo phút → chờ rồi thử lại cùng khoá",
     lambda c, n: e429("PerMinute") if n == 1 else ok("xin chào"), {"GEMINI_API_KEY": "K1"})
chay("2. khoá 1 hết NGÀY → sang khoá 2",
     lambda c, n: e429("PerDay") if c[1] == "K1" else ok("từ khoá 2"), {"GEMINI_API_KEY": "K1", "GEMINI_API_KEY_2": "K2"})
chay("3. mọi khoá miễn phí hết ngày, có khoá trả phí → dùng trả phí",
     lambda c, n: e429("PerDay") if c[1] in ("K1", "K2") else ok("trả phí"),
     {"GEMINI_API_KEY": "K1", "GEMINI_API_KEY_2": "K2", "GEMINI_API_KEY_TRA_PHI": "KP"})
chay("4. hết sạch → HetHanMuc",
     lambda c, n: e429("PerDay"), {"GEMINI_API_KEY": "K1"})
chay("5. phản hồi rỗng ở model 1 → model 2",
     lambda c, n: R(200, {"candidates": [{"content": {"parts": []}, "finishReason": "SAFETY"}]}) if c[0] == "m1" else ok("model 2"),
     {"GEMINI_API_KEY": "K1"})
chay("6. 404 model ngừng → lấy model Google gợi ý",
     lambda c, n: R(404, {"error": {"message": "models/m1 is not found. Try models/gemini-9.9-flash"}}) if c[0] == "m1" else ok("model gợi ý"),
     {"GEMINI_API_KEY": "K1"}, models=("m1",))
