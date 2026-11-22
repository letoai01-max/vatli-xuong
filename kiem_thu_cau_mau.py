"""
kiem_thu_cau_mau.py – KIỂM THỬ cau_mau.py (hộp cát, kiểm biến thể, chọn nguồn, ghi kho giả). Không cần khoá, không gọi mạng.
Chạy: python kiem_thu_cau_mau.py   (sai một ca → thoát mã 1)
"""
import datetime as dt, json, os, re, sys, tempfile, types, unicodedata

if "doc_de" not in sys.modules:
    gia = types.ModuleType("doc_de")
    def _bo_dau(s):
        s = unicodedata.normalize("NFD", str(s or ""))
        s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "d").lower()
        return re.sub(r"[^a-z0-9]+", " ", re.sub(r"\$|\\[a-z]+", " ", s))
    gia.tu_khoa_ct_cu = lambda *a, **k: ""
    gia.bo_dau = _bo_dau
    gia.CT_CU_MO_TA = ""
    gia.TZ = dt.timezone(dt.timedelta(hours=7))
    gia.HetHanMuc = type("HetHanMuc", (Exception,), {})
    sys.modules["doc_de"] = gia

import cau_mau as C
import duyet_cau as D

LOI = []


def kiem(ten, dk):
    if not dk: LOI.append(ten)
    print(("✅ " if dk else "❌ ") + ten)


# ---------- mã mẫu ----------
TLN_OK = r'''
import math
GOC = {"h": 20.0, "g": 9.8}
def tham_so(rng):
    return {"h": float(rng.choice([5, 10, 15, 20, 25, 30, 45, 50, 80])) + rng.choice([0, 0.5]), "g": 9.8}
def so(x):
    return ("%g" % x).replace(".", "{,}")
def de_bai(p):
    return "Một vật rơi tự do từ độ cao $%s\\text{ m}$ xuống mặt đất, lấy $g = %s\\text{ m/s}^2$. Tính thời gian rơi của vật theo đơn vị giây (làm tròn đến hàng phần trăm)." % (so(p["h"]), so(p["g"]))
def dap_an(p):
    return round(math.sqrt(2 * p["h"] / p["g"]), 2)
'''
TLN_SAI_CONG_THUC = TLN_OK.replace("return round(math.sqrt(2 * p[\"h\"] / p[\"g\"]), 2)", "return round(2 * p[\"h\"], 2)")
TLN_GO_CUNG = TLN_OK.replace("return round(math.sqrt(2 * p[\"h\"] / p[\"g\"]), 2)", "return 2.02")
TN_OK = r'''
GOC = {"m": 2.0, "v": 3.0}
def tham_so(rng):
    return {"m": float(rng.randint(1, 8)), "v": float(rng.randint(3, 12))}
def so(x):
    return ("%g" % x).replace(".", "{,}")
def de_bai(p):
    return "Một vật có khối lượng $%s\\text{ kg}$ chuyển động với tốc độ $%s\\text{ m/s}$. Động năng của vật là bao nhiêu?" % (so(p["m"]), so(p["v"]))
def phuong_an(p, rng):
    dung = 0.5 * p["m"] * p["v"] ** 2
    sai = iter([p["m"] * p["v"] ** 2, 0.5 * p["m"] * p["v"], p["m"] * p["v"] + 1])
    idx = rng.randrange(4)
    pa = []
    for i in range(4):
        x = dung if i == idx else next(sai)
        pa.append("$%s\\text{ J}$" % so(x))
    return pa, idx
'''
ND_TLN = "Một vật rơi tự do từ độ cao $20\\text{ m}$ xuống mặt đất, lấy $g = 9{,}8\\text{ m/s}^2$. Tính thời gian rơi của vật theo đơn vị giây (làm tròn đến hàng phần trăm)."
ND_TN = "Một vật có khối lượng $2\\text{ kg}$ chuyển động với tốc độ $3\\text{ m/s}$. Động năng của vật là bao nhiêu?"
PA_TN = "A. $4{,}5\\text{ J}$\nB. $9\\text{ J}$\nC. $18\\text{ J}$\nD. $3\\text{ J}$"

# ---------- 1. duyệt cú pháp ----------
kiem("mã TLN hợp lệ qua duyệt cú pháp", C.kiem_ma(TLN_OK, "TLN") is None)
kiem("mã TN hợp lệ qua duyệt cú pháp", C.kiem_ma(TN_OK, "TN") is None)
kiem("import os bị chặn", "import" in (C.kiem_ma("import os\n" + TLN_OK, "TLN") or ""))
kiem("from subprocess import … bị chặn", "import" in (C.kiem_ma("from subprocess import run\n" + TLN_OK, "TLN") or ""))
kiem("open() bị chặn", "open" in (C.kiem_ma(TLN_OK + "\nx = open('a')", "TLN") or ""))
kiem("thuộc tính gạch dưới bị chặn", "gạch dưới" in (C.kiem_ma(TLN_OK + "\nx = ().__class__", "TLN") or ""))
kiem("str.format đọc thuộc tính dunder bị chặn", "gạch dưới" in (C.kiem_ma(TLN_OK + "\nx = '{0.__class__}'.format(1)", "TLN") or ""))
kiem("thiếu hàm dap_an → từ chối", "thiếu hàm" in (C.kiem_ma(TLN_OK.replace("def dap_an", "def khac"), "TLN") or ""))
kiem("thiếu GOC → từ chối", "GOC" in (C.kiem_ma(TLN_OK.replace("GOC =", "GOCX ="), "TLN") or ""))
kiem("cú pháp sai → từ chối", "cú pháp" in (C.kiem_ma("def (:", "TLN") or ""))

# ---------- 2. hộp cát ----------
os.environ["GEMINI_API_KEY"] = "BI_MAT_KHONG_DUOC_LO"
kiem("môi trường hộp cát không có khoá bí mật", set(C.env_sach()) == {"PATH"})
kq, ly = C.chay_hop_cat(TLN_OK, "TLN", 5, 1)
kiem("chạy mã TLN: có số liệu gốc và 5 biến thể", kq and kq["goc"] and abs(kq["goc"]["dap_an"] - 2.02) < 1e-9 and len(kq["bien_the"]) == 5)
kq, ly = C.chay_hop_cat("import os\n" + TLN_OK, "TLN", 2, 1)
kiem("hộp cát tự chặn import os kể cả khi bỏ qua bước duyệt cú pháp", kq and kq["goc"] is None and "ImportError" in kq["loi"])
kq, ly = C.chay_hop_cat(TLN_OK.replace("return {\"h\"", "while True: pass\n    return {\"h\""), "TLN", 2, 1, han=3)
kiem("vòng lặp vô hạn bị cắt, trả lí do (không treo workflow)", kq is None and bool(ly))
t0 = dt.datetime.now()
kq, ly = C.chay_hop_cat("GOC = {}\ndef tham_so(rng):\n    while True: pass\ndef de_bai(p): return 'x'\ndef dap_an(p): return 1.0\n", "TLN", 2, 1, han=3)
kiem("vòng lặp vô hạn ở tham_so: kết thúc trong < 15 giây", (dt.datetime.now() - t0).seconds < 15)

# ---------- 3. tái tạo đúng câu gốc ----------
g = {"de": ND_TLN, "dap_an": 2.02}
kiem("TLN tái tạo đúng → qua", C.goc_khop("TLN", g, ND_TLN, "", "2,02") is None)
kiem("TLN tái tạo đúng, đáp án có đơn vị → qua", C.goc_khop("TLN", g, ND_TLN, "", "2,02 s") is None)
kiem("TLN tái tạo sai đáp số → từ chối", C.goc_khop("TLN", {"de": ND_TLN, "dap_an": 40.0}, ND_TLN, "", "2,02") is not None)
kiem("TLN tái tạo đề khác hẳn → từ chối", C.goc_khop("TLN", {"de": "Một con lắc đơn dao động điều hoà với chu kì bao nhiêu", "dap_an": 2.02}, ND_TLN, "", "2,02") is not None)
gt = {"de": ND_TN, "pa": ["$4{,}5\\text{ J}$", "$9\\text{ J}$", "$18\\text{ J}$", "$3\\text{ J}$"], "idx": 1}
kiem("TN tái tạo đúng phương án đúng → qua", C.goc_khop("TN", gt, ND_TN, PA_TN, "B") is None)
kiem("TN phương án đúng tái tạo khác đáp án gốc → từ chối", C.goc_khop("TN", dict(gt, idx=2), ND_TN, PA_TN, "B") is not None)
kiem("so_trong hiểu 1,6e-19 và 3\\cdot10^{-3}", C.so_trong("1,6e-19 C") == 1.6e-19 and abs(C.so_trong("$3\\cdot 10^{-3}\\text{ s}$") - 3e-3) < 1e-12)

# ---------- 4. kiểm biến thể ----------
gz = {"p": {"h": 20.0, "g": 9.8}, "de": ND_TLN, "dap_an": 2.02}
b_ok = {"p": {"h": 45.0, "g": 9.8}, "de": ND_TLN.replace("20", "45"), "dap_an": 3.03}
kiem("biến thể tốt → qua", C.kiem_bien_the("TLN", b_ok, gz, set()) is None)
kiem("đáp số trùng gốc → loại", C.kiem_bien_the("TLN", dict(b_ok, dap_an=2.03), gz, set()) is not None)
kiem("đáp số đổi dấu → loại", C.kiem_bien_the("TLN", dict(b_ok, dap_an=-3.03), gz, set()) is not None)
kiem("đáp số quá nhỏ cần kí hiệu khoa học → loại", C.kiem_bien_the("TLN", dict(b_ok, dap_an=3.03e-6), dict(gz, dap_an=2e-6), set()) is not None)
kiem("trùng số liệu với biến thể đã nhận → loại", C.kiem_bien_the("TLN", b_ok, gz, {json.dumps(b_ok["p"], sort_keys=True)}) is not None)
kiem("$ lẻ → loại", C.kiem_bien_the("TLN", dict(b_ok, de=b_ok["de"] + " $x"), gz, set()) is not None)
kiem("đề còn sót None → loại", C.kiem_bien_the("TLN", dict(b_ok, de=b_ok["de"] + " None"), gz, set()) is not None)
tn_ok = {"p": {"m": 4.0, "v": 5.0}, "de": ND_TN.replace("$2", "$4").replace("$3", "$5"), "pa": ["$50\\text{ J}$", "$100\\text{ J}$", "$10\\text{ J}$", "$21\\text{ J}$"], "idx": 0}
kiem("TN biến thể tốt → qua", C.kiem_bien_the("TN", tn_ok, {"p": {"m": 2.0, "v": 3.0}, "de": ND_TN}, set()) is None)
kiem("TN hai phương án trùng → loại", C.kiem_bien_the("TN", dict(tn_ok, pa=["$50\\text{ J}$", "$50\\text{ J}$", "$10\\text{ J}$", "$21\\text{ J}$"]), {"p": {}, "de": ND_TN}, set()) is not None)
kiem("TN hai phương án quá gần → loại", C.kiem_bien_the("TN", dict(tn_ok, pa=["$50\\text{ J}$", "$50{,}2\\text{ J}$", "$10\\text{ J}$", "$21\\text{ J}$"]), {"p": {}, "de": ND_TN}, set()) is not None)
kiem("TN phương án 'cả A và B' → loại", C.kiem_bien_the("TN", dict(tn_ok, pa=["$50\\text{ J}$", "Cả A và B đúng", "$10\\text{ J}$", "$21\\text{ J}$"]), {"p": {}, "de": ND_TN}, set()) is not None)

# ---------- 5. xử lí một câu nguồn ----------
s_tln = {"ma": "C-AAA-001", "loai": "TLN", "nd": ND_TLN, "pa": "", "da": "2,02", "yccd": "VL10-1-1"}
s_tn = {"ma": "C-AAA-002", "loai": "TN", "nd": ND_TN, "pa": PA_TN, "da": "B", "yccd": "VL10-1-2"}
ds, nh, ct = C.xu_ly_nguon(s_tln, TLN_OK, 3)
kiem("TLN: sinh đủ 3 biến thể khác nhau", len(ds) == 3 and len({b["dap_an"] for b in ds}) == 3 and all(b["dap_an"] != 2.02 for b in ds))
ds, nh, ct = C.xu_ly_nguon(s_tn, "```python\n" + TN_OK + "\n```", 3)
kiem("TN: sinh đủ 3 biến thể (cho phép bọc ```python)", len(ds) == 3)
kiem("TN: mỗi biến thể có 4 phương án khác nhau, chỉ số đúng 0–3", all(len(set(b["pa"])) == 4 and b["idx"] in range(4) for b in ds))
kiem("TN: đáp án đúng = 0,5·m·v² tính lại độc lập", all(abs(C.so_trong(b["pa"][b["idx"]]) - 0.5 * b["p"]["m"] * b["p"]["v"] ** 2) < 1e-6 for b in ds))
ds, nh, ct = C.xu_ly_nguon(s_tln, TLN_SAI_CONG_THUC, 3)
kiem("mã sai công thức → bị loại vì không tái tạo được câu gốc", not ds and nh == "không tái tạo đúng câu gốc")
ds, nh, ct = C.xu_ly_nguon(s_tln, TLN_GO_CUNG, 3)
kiem("mã gõ cứng đáp án → mọi biến thể bị loại", not ds and nh == "biến thể không hợp lệ")
ds, nh, ct = C.xu_ly_nguon(s_tln, "import os\n" + TLN_OK, 3)
kiem("mã import os → bị loại ngay", not ds and nh == "mã không an toàn hoặc thiếu hàm")

# ---------- 6. chọn nguồn ----------
TD = ["Mã câu", "Mã YCCĐ", "Mã bài", "Lớp", "Mức độ", "Dạng", "Nội dung", "Phương án", "Đáp án", "Lời giải / HDC", "Điểm", "Loại đề",
      "Đơn vị ra đề", "Năm học", "Kì thi", "Tên file", "Link file", "File ID", "Chủ đề tải", "Kiểm tra", "Trạng thái duyệt", "Thời gian"]


def hang(ma, yccd="VL10-1-1", dang="Trả lời ngắn", nd=ND_TLN, pa="", da="2,02", tt="AI duyệt", kt="[5 tầng 21/11] ok", fid="FILE1"):
    r = {t: "" for t in TD}
    r.update({"Mã câu": ma, "Mã YCCĐ": yccd, "Mã bài": "VL10-1", "Lớp": "10", "Mức độ": "Vận dụng", "Dạng": dang, "Nội dung": nd,
              "Phương án": pa, "Đáp án": da, "Loại đề": "Đề thi thử", "Năm học": "2025-2026", "Tên file": "De1.pdf (câu 3)", "File ID": fid,
              "Kiểm tra": kt, "Trạng thái duyệt": tt, "Thời gian": "01/11/2026 10:00"})
    return [r[t] for t in TD]


d = [TD,
     hang("C-1-001", yccd="VL10-A"),                                                      # chọn được
     hang("C-1-002", yccd="VL10-A", dang="Đúng/sai", nd=ND_TN, pa="a) x", da="a) Đ, b) S, c) Đ, d) S"),   # DS: bỏ
     hang("C-1-003", yccd="VL10-A", nd="Cho đồ thị $v-t$ như hình vẽ, quãng đường $s=10$ m trong $5$ s. [Hình: đồ thị]"),   # có hình: bỏ
     hang("C-1-004", yccd="VL10-A", kt="[5 tầng 21/11] ok | [mẫu hoá 22/11: sinh 3 biến thể]"),   # đã mẫu hoá: bỏ
     hang("C-1-005", yccd="VL10-A", tt="Chưa duyệt"),                                       # chưa duyệt: bỏ
     hang("C-1-006", yccd="VL10-A"),                                                        # đã đủ 3 biến thể: bỏ
     hang("C-1-006-BT1", yccd="VL10-A", tt="Chưa duyệt", kt="[mẫu hoá 22/11: …]"), hang("C-1-006-BT2", yccd="VL10-A", tt="Chưa duyệt"),
     hang("C-1-006-BT3", yccd="VL10-A", tt="Chưa duyệt"),
     hang("C-1-007", yccd="VL10-A", nd="Tính quãng đường vật đi được trong thời gian ngắn nhất."),   # < 2 số liệu: bỏ
     hang("C-1-008", yccd="VL10-B"), hang("C-1-009", yccd="VL10-B"), hang("C-1-010", yccd="VL10-B"),   # YCCĐ B đã có 3 câu
     hang("C-1-011", yccd="VL10-C"),                                                        # YCCĐ C chỉ có 1 câu → ưu tiên
     hang("C-1-012", yccd="VL10-D", dang="Nhiều lựa chọn", nd=ND_TN, pa=PA_TN, da="B"),
     ]
ns = C.chon_nguon(d, toi_da=50, so_bt=3, tran=30, dang_ok={"TN", "TLN"})
ma = [s["ma"] for s in ns]
kiem("không chọn DS, câu có hình, câu đã mẫu hoá, câu chưa duyệt, câu ít số liệu, câu đã đủ biến thể",
     not ({"C-1-002", "C-1-003", "C-1-004", "C-1-005", "C-1-006", "C-1-007"} & set(ma)))
kiem("không chọn chính các biến thể -BT", not any("-BT" in m for m in ma))
kiem("chọn câu TN và TLN hợp lệ", {"C-1-001", "C-1-012", "C-1-011"} <= set(ma))
kiem("YCCĐ ít câu được xếp trước (C, D trước B)", ma.index("C-1-011") < ma.index("C-1-008") and ma.index("C-1-012") < ma.index("C-1-008"))
ns2 = C.chon_nguon(d, toi_da=50, so_bt=3, tran=3, dang_ok={"TN", "TLN"})
kiem("trần mỗi YCCĐ: YCCĐ B chỉ nhận 3 biến thể tổng cộng", sum(s["can"] for s in ns2 if s["yccd"] == "VL10-B") <= 3)
kiem("trần số câu nguồn mỗi lượt", len(C.chon_nguon(d, toi_da=2, so_bt=3, tran=30, dang_ok={"TN", "TLN"})) == 2)

# ---------- 7. dòng ghi vào kho ----------
nguon_dong = dict(zip(TD, hang("C-1-001", yccd="VL10-A")))
r = dict(zip(TD, C.dong_bien_the(TD, nguon_dong, "C-1-001-BT1", {"de": ND_TLN, "dap_an": 3.0306, "p": {}}, "TLN", "22/11/2026 23:10", "22/11")))
kiem("dòng biến thể: mã, trạng thái Chưa duyệt, File ID trống", r["Mã câu"] == "C-1-001-BT1" and r["Trạng thái duyệt"] == "Chưa duyệt" and r["File ID"] == "")
kiem("dòng biến thể: kế thừa YCCĐ, lớp, mức độ, dạng", r["Mã YCCĐ"] == "VL10-A" and r["Lớp"] == "10" and r["Mức độ"] == "Vận dụng" and r["Dạng"] == "Trả lời ngắn")
kiem("dòng biến thể: đáp số định dạng dấu phẩy, có dấu mẫu hoá ở Kiểm tra", r["Đáp án"] == "3,0306" and r["Kiểm tra"].startswith("[mẫu hoá"))
kiem("dòng biến thể: Tên file ghi nguồn, đúng độ dài cột", "C-1-001" in r["Tên file"] and len(C.dong_bien_the(TD, nguon_dong, "x-BT1", {"de": ND_TLN, "dap_an": 1.0}, "TLN", "", "")) == len(TD))
rn = dict(zip(TD, C.dong_bien_the(TD, nguon_dong, "C-1-001-BT2", {"de": ND_TN, "pa": ["$1$", "$2$", "$3$", "$4$"], "idx": 2}, "TN", "", "")))
kiem("dòng TN: phương án có nhãn A–D, đáp án là chữ", rn["Phương án"].startswith("A. $1$") and rn["Đáp án"] == "C")

# ---------- 8. chạy trọn vẹn với bảng giả + Gemini giả ----------
class BangGia:
    def __init__(self, v): self.v = [list(r) for r in v]; self.ghi = 0
    def get_all_values(self): return [list(r) for r in self.v]
    def col_values(self, n): return [(r[n - 1] if len(r) >= n else "") for r in self.v]
    def append_rows(self, rows, **k): self.v += [list(r) for r in rows]; self.ghi += len(rows)
    def batch_update(self, cap, **k):
        for c in cap:
            m = re.match(r"([A-Z]+)(\d+)", c["range"]); cot = 0
            for ch in m.group(1): cot = cot * 26 + ord(ch) - 64
            self.v[int(m.group(2)) - 1][cot - 1] = c["values"][0][0]


class Gemini:
    def __init__(self): self.dem = 0; self.ds = []
    def __call__(self, payload, ds_model):
        self.dem += 1
        lenh = payload["contents"][0]["parts"][0]["text"]
        sua = "LẦN TRƯỚC" in lenh
        ket = []
        for m in re.findall(r'"ma_cau": "([^"]+)"', lenh):
            if m == "C-1-001": ket.append({"ma_cau": m, "lam_duoc": True, "ma_python": TLN_OK})
            elif m == "C-1-012": ket.append({"ma_cau": m, "lam_duoc": True, "ma_python": TN_OK})
            elif m == "C-1-011": ket.append({"ma_cau": m, "lam_duoc": True, "ma_python": TLN_OK if sua else TLN_SAI_CONG_THUC})   # sai lần đầu, đúng sau khi được nhắc
            elif m == "C-1-008": ket.append({"ma_cau": m, "lam_duoc": False, "ma_python": ""})
            elif m == "C-1-009": ket.append({"ma_cau": m, "lam_duoc": True, "ma_python": TLN_SAI_CONG_THUC})                        # sai cả hai lần
        return {"candidates": [{"content": {"parts": [{"text": json.dumps({"ket_qua": ket}, ensure_ascii=False)}]}}]}, "gemini-x"


os.chdir(tempfile.mkdtemp())
C.TOI_DA_NGUON, C.SO_BIEN_THE, C.TOI_DA_MOI_YCCD, C.DANG_CHO_PHEP = 50, 3, 30, {"TN", "TLN"}
bang = BangGia(d)
tk = C.chay(bang, bang.get_all_values(), ["gemini-2.5-flash"], Gemini(), "thu")
kiem("chế độ thử: không ghi gì vào bảng, có báo cáo", bang.ghi == 0 and os.path.isfile("cau_mau_thu.md") and tk["biến thể hợp lệ"] > 0)

bang = BangGia(d)
tk = C.chay(bang, bang.get_all_values(), ["gemini-2.5-flash"], Gemini(), "ghi")
v = bang.get_all_values()
moi = [dict(zip(TD, r)) for r in v[len(d):]]
kiem("chế độ ghi: thêm đúng các biến thể (C-1-001, C-1-012, C-1-011 sau khi sửa; mỗi câu 3)", len(moi) == 9 and bang.ghi == 9)
kiem("mọi biến thể mới ở trạng thái Chưa duyệt, có mã -BT, File ID trống",
     all(m["Trạng thái duyệt"] == "Chưa duyệt" and "-BT" in m["Mã câu"] and m["File ID"] == "" for m in moi))
kiem("câu C-1-011 sai lần đầu → model sửa lại → có biến thể", sum(m["Mã câu"].startswith("C-1-011-BT") for m in moi) == 3)
kt = {r[0]: r[TD.index("Kiểm tra")] for r in v}
kiem("câu nguồn thành công được đánh dấu 'sinh 3 biến thể'", "[mẫu hoá" in kt["C-1-001"] and "sinh 3 biến thể" in kt["C-1-001"] and kt["C-1-001"].startswith("[5 tầng 21/11] ok"))
kiem("câu model báo không làm được / sai cả hai lần được đánh dấu để khỏi thử lại", "không làm được" in kt["C-1-008"] and "không làm được" in kt["C-1-009"])
kiem("câu model CHƯA trả lời (C-1-010) không bị đánh dấu → lượt sau hỏi lại", "[mẫu hoá" not in kt["C-1-010"])
kiem("dấu thất bại không chứa chữ làm lệch do_chat_luong (tự giải / duyệt lại / cứu Loại)", not re.search(r"tự giải|duyệt lại|cứu Loại", kt["C-1-008"] + kt["C-1-009"]))
kiem("trạng thái các câu nguồn giữ nguyên 'AI duyệt'", all(dict(zip(TD, r))["Trạng thái duyệt"] == "AI duyệt" for r in v[1:len(d)] if r[0] in ("C-1-001", "C-1-012", "C-1-011")))
g2 = Gemini()
tk2 = C.chay(bang, bang.get_all_values(), ["gemini-2.5-flash"], g2, "ghi")
kiem("chạy lần hai: chỉ còn câu chưa được trả lời, không sinh thêm dòng nào, không làm lại câu đã xong/đã đánh dấu",
     bang.ghi == 9 and tk2["câu nguồn xử lí"] == 1 and g2.dem == 1)

print()
if LOI:
    print("❌ %d ca sai:" % len(LOI)); [print("  -", t) for t in LOI]; sys.exit(1)
print("✅ Tất cả ca đạt.")
