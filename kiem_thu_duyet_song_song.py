"""
kiem_thu_duyet_song_song.py – KIỂM THỬ chạy song song của duyet_cau.py / doc_de.py (không cần khoá, không gọi mạng).

Kiểm: (1) trần lượt khoá trả phí không bị vượt khi nhiều luồng; (2) số lượt gọi Gemini cùng lúc ≤ GEMINI_SONG_SONG;
(3) tang4 song song cho KẾT QUẢ y hệt lần lượt; (4) chay_cac_tang song song = lần lượt, và lỗi được xử lí như cũ;
(5) quota_xuong đếm đủ lượt khi nhiều luồng cùng ghi.
Sai thì thoát mã khác 0 để Actions báo đỏ. Chạy: python kiem_thu_duyet_song_song.py  (cùng thư mục với duyet_cau.py, doc_de.py)
"""
import os, sys, threading, time, types

os.environ["GEMINI_SONG_SONG"] = "3"
os.environ["TOI_DA_LUOT_TRA_PHI"] = "10"
os.environ["GEMINI_API_KEY_TRA_PHI"] = "khoa-gia"
for ten in ["GEMINI_API_KEY"] + ["GEMINI_API_KEY_%d" % i for i in range(1, 6)]:
    os.environ.pop(ten, None)


def gia_lap_thieu(ten, **thuoc_tinh):          # giả lập thư viện Google/gspread/latex_chuan khi máy chưa cài
    try:
        __import__(ten)
    except ImportError:
        m = types.ModuleType(ten)
        for k, v in thuoc_tinh.items():
            setattr(m, k, v)
        sys.modules[ten] = m
        if "." in ten:
            cha, con = ten.rsplit(".", 1)
            setattr(sys.modules.setdefault(cha, types.ModuleType(cha)), con, m)


gia_lap_thieu("gspread")
gia_lap_thieu("requests", RequestException=Exception)
gia_lap_thieu("latex_chuan", chuan_hoa_latex=lambda s: s)
gia_lap_thieu("google")
gia_lap_thieu("google.oauth2")
gia_lap_thieu("google.oauth2.service_account")
gia_lap_thieu("googleapiclient")
gia_lap_thieu("googleapiclient.discovery", build=lambda *a, **k: None)
gia_lap_thieu("googleapiclient.http", MediaIoBaseDownload=object)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doc_de as X
import duyet_cau as D

loi = []


def kiem(dieu_kien, mo_ta):
    print(("✅ " if dieu_kien else "❌ ") + mo_ta, flush=True)
    if not dieu_kien:
        loi.append(mo_ta)


# ---------- (1) + (2): bộ đếm khoá trả phí và cổng song song ----------
dang_chay = {"hien": 0, "toi_da": 0}
khoa_dem = threading.Lock()


def gia_mot_khoa(payload, ds_model, key, ten=""):
    with khoa_dem:
        dang_chay["hien"] += 1
        dang_chay["toi_da"] = max(dang_chay["toi_da"], dang_chay["hien"])
    time.sleep(0.02)
    with khoa_dem:
        dang_chay["hien"] -= 1
    return {"ok": 1}, "gemini-gia"


X._goi_gemini_mot_khoa = gia_mot_khoa
X.TOI_DA_LUOT_TRA_PHI = 10
ket, het = [], []


def goi():
    try:
        ket.append(X.goi_gemini({"generationConfig": {}}, ["gemini-gia"]))
    except X.HetHanMuc:
        het.append(1)


cac = [threading.Thread(target=goi) for _ in range(60)]
[t.start() for t in cac]; [t.join() for t in cac]
kiem(len(ket) == 10 and len(het) == 50, "trần 10 lượt khoá trả phí không bị vượt khi 60 luồng cùng gọi (được %d, bị chặn %d)" % (len(ket), len(het)))
kiem(X.TRANG_THAI_KHOA["da_dung_tra_phi"] == 10, "bộ đếm lượt trả phí đúng 10")
kiem(dang_chay["toi_da"] <= X.GEMINI_SONG_SONG, "số lượt gọi cùng lúc tối đa %d ≤ %d" % (dang_chay["toi_da"], X.GEMINI_SONG_SONG))

# ---------- (3): tang4 song song = lần lượt ----------
cau = [{"ma": "C%03d" % i, "dang": "Nhiều lựa chọn", "noi_dung": "n" * 20, "phuong_an": "A. 1\nB. 2\nC. 3\nD. 4"} for i in range(47)]


def gia_goi_gemini(payload, ds_model):
    text = payload["contents"][0]["parts"][0]["text"]
    ma = [m for m in __import__("re").findall(r'"ma_cau": "(C\d+)"', text)]
    time.sleep(0.02)
    j = "[" + ",".join('{"ma_cau": "%s", "phuong_an_dung": ["B"], "tu_tin": "cao"}' % m for m in ma) + "]"
    return {"candidates": [{"content": {"parts": [{"text": "```json\n%s\n```" % j}]}}]}, ds_model[0]


X.goi_gemini = gia_goi_gemini
D.SONG_SONG = False
kq_tuan_tu = D.tang4(cau, ["m-chinh", "m-lite"], "m-chinh")
D.SONG_SONG = True
kq_song_song = D.tang4(cau, ["m-chinh", "m-lite"], "m-chinh")
kiem(kq_tuan_tu == kq_song_song and len(kq_song_song[0]) == 47, "tang4: song song cho kết quả y hệt lần lượt (47 câu, 5 lô)")

# ---------- (4): chay_cac_tang ----------
vet = []
D.tang2 = lambda tep, ds, yccd, cm: ({"C000": {"co_hdc": False}}, [{"so_cau": "1", "dap_an": "A"}], "m-chinh")
D.tang3 = lambda tep, ds, cm: {"C000": ["2 kg"]}
D.tang4 = lambda ds, cm, m2: ({"C000": {"phuong_an_dung": ["A"]}}, "m-lite")
D.tang4_groq = lambda ds: ({"C000": "A"}, "llama")
D.SONG_SONG = False
a = D.chay_cac_tang(None, cau[:1], {}, ["m-chinh", "m-lite"])
D.SONG_SONG = True
b = D.chay_cac_tang(None, cau[:1], {}, ["m-chinh", "m-lite"])
kiem(a == b, "chay_cac_tang: song song = lần lượt")


def tang3_loi(tep, ds, cm):
    raise RuntimeError("loi gia")


D.tang3 = tang3_loi
for che_do in (False, True):
    D.SONG_SONG = che_do
    kq = D.chay_cac_tang(None, cau[:1], {}, ["m-chinh", "m-lite"])
    kiem(kq[3] == {}, "tầng 3 lỗi thường bị bỏ qua (SONG_SONG=%s)" % che_do)


def tang3_het(tep, ds, cm):
    raise X.HetHanMuc("het")


D.tang3 = tang3_het
for che_do in (False, True):
    D.SONG_SONG = che_do
    try:
        D.chay_cac_tang(None, cau[:1], {}, ["m-chinh", "m-lite"]); ok = False
    except X.HetHanMuc:
        ok = True
    kiem(ok, "HetHanMuc ở tầng 3 được ném lên (SONG_SONG=%s)" % che_do)

# ---------- (5): quota_xuong đếm đúng khi nhiều luồng ghi ----------
import quota_xuong as Q
Q._DEM.clear()


def ghi_nhieu():
    for _ in range(2000):
        Q.ghi_luot("xưởng gemini-gia", 200, 3, 2)


cac = [threading.Thread(target=ghi_nhieu) for _ in range(8)]
[t.start() for t in cac]; [t.join() for t in cac]
d = Q._DEM["xưởng gemini-gia"]
kiem(d["goi"] == 16000 and d["ok"] == 16000 and d["tkVao"] == 48000 and d["tkRa"] == 32000, "quota_xuong: 8 luồng × 2000 lượt đếm đủ 16000")

if loi:
    print("\n%d ca sai." % len(loi)); sys.exit(1)
print("\nTất cả ca đạt.")
