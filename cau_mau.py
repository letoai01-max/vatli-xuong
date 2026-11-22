"""
cau_mau.py – CÂU MẪU HOÁ: NHÂN BẢN CÂU "AI duyệt" THÀNH BIẾN THỂ ĐỔI SỐ LIỆU – mục 1 của kế hoạch tăng kho (GitHub Actions).   [22/11/2026]

Luồng:
  1. Chọn câu NGUỒN: "AI duyệt", dạng TN / TLN, không hình, có ≥ 2 số liệu, chưa mẫu hoá. Ưu tiên câu thuộc YCCĐ đang ÍT câu nhất
     (kho đỡ lệch); mỗi YCCĐ có trần số biến thể (CAU_MAU_TOI_DA_MOI_YCCD); mỗi câu nguồn tối đa CAU_MAU_SO_BIEN_THE biến thể.
  2. Gemini viết MÃ PYTHON cho mỗi câu: GOC (số liệu đề gốc), tham_so(rng), de_bai(p), dap_an(p) [TLN] hoặc phuong_an(p, rng) [TN].
     Đáp án và phương án nhiễu do CODE tính – không gõ cứng.
  3. Chạy mã trong HỘP CÁT (tiến trình riêng, không có khoá bí mật trong môi trường, giới hạn thời gian + bộ nhớ, chỉ cho import
     math / random / fractions, mã bị duyệt cú pháp trước). Mã chỉ được dùng khi TÁI TẠO ĐÚNG câu gốc (đề giống ≥ 60%, đáp án khớp
     đáp án đã duyệt) – đây là bằng chứng mã đúng công thức.
  4. Biến thể phải: đổi số thật, đáp án khác câu gốc và khác nhau, cùng dấu/cùng bậc độ lớn, TN có 4 phương án khác nhau rõ.
  5. Ghi vào NganHangCauHoi ở trạng thái "Chưa duyệt", Mã = <mã nguồn>-BT<k>, File ID trống → duyet_cau.py chạy ĐỦ 5 tầng
     (tầng 4 giải độc lập không xem đáp án); không tự duyệt ở đây. Đánh dấu "[mẫu hoá dd/mm: …]" ở cột Kiểm tra của câu nguồn.

Chế độ CAU_MAU_CHE_DO: "thu" (mặc định) = không ghi vào kho, chỉ in + ghi cau_mau_thu.md để thầy xem mẫu; "ghi" = ghi thật.
Biến môi trường: GOOGLE_CREDENTIALS, GEMINI_API_KEY…; tuỳ chọn CAU_MAU_TOI_DA (số câu nguồn/lượt, 40), CAU_MAU_SO_BIEN_THE (3, tối đa 5),
CAU_MAU_TOI_DA_MOI_YCCD (30), CAU_MAU_DANG ("TN,TLN").
Lưu ý: giữ TRUNG_CHE_DO = "ghi_chu" (mặc định của duyet_cau.py) để biến thể "cùng dạng, khác số liệu" chỉ bị ghi chú, không bị chặn.
"""
import ast, collections, datetime as dt, json, math, os, re, subprocess, sys, tempfile, zlib

import doc_de as X
import duyet_cau as D
import cuu_nghi_van as CN
import latex_chuan as L

try:
    import quota_xuong as Q
except Exception:
    Q = None

DAU = "mẫu hoá"
CHE_DO = os.environ.get("CAU_MAU_CHE_DO", "thu").strip().lower()


def _so_nguyen(ten, mac_dinh, lo, hi):
    try:
        return max(lo, min(hi, int(float(os.environ.get(ten, mac_dinh) or mac_dinh))))
    except ValueError:
        return mac_dinh


TOI_DA_NGUON = _so_nguyen("CAU_MAU_TOI_DA", 40, 1, 500)
SO_BIEN_THE = _so_nguyen("CAU_MAU_SO_BIEN_THE", 3, 1, 5)
TOI_DA_MOI_YCCD = _so_nguyen("CAU_MAU_TOI_DA_MOI_YCCD", 30, 1, 500)
DANG_CHO_PHEP = {s.strip().upper() for s in os.environ.get("CAU_MAU_DANG", "TN,TLN").split(",")} & {"TN", "TLN"}
LO = 3                                   # số câu nguồn mỗi lượt hỏi Gemini
SINH_DU = 3                              # sinh dư để lọc biến thể không hợp lệ
RE_MA_BT = re.compile(r"-BT(\d+)$")

# ============================== 1. HỘP CÁT ==============================
CHO_PHEP_IMPORT = {"math", "random", "fractions"}
CAM_TEN = {"eval", "exec", "compile", "open", "input", "getattr", "setattr", "delattr", "globals", "locals", "vars",
           "breakpoint", "exit", "quit", "type", "object", "help", "memoryview", "classmethod", "staticmethod", "super"}
HAM_BAT_BUOC = {"TLN": {"tham_so", "de_bai", "dap_an"}, "TN": {"tham_so", "de_bai", "phuong_an"}}


def kiem_ma(code, dang):
    """None nếu mã qua duyệt cú pháp; ngược lại trả lí do (chuỗi ngắn)."""
    if not isinstance(code, str) or not code.strip(): return "mã rỗng"
    if len(code) > 12000: return "mã quá dài"
    try:
        cay = ast.parse(code)
    except SyntaxError as e:
        return "lỗi cú pháp: %s" % str(e)[:80]
    for n in ast.walk(cay):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] not in CHO_PHEP_IMPORT: return "import không cho phép: " + a.name
        elif isinstance(n, ast.ImportFrom):
            if n.level or (n.module or "").split(".")[0] not in CHO_PHEP_IMPORT: return "import không cho phép: " + str(n.module)
        elif isinstance(n, ast.Attribute) and n.attr.startswith("_"):
            return "truy cập thuộc tính gạch dưới: " + n.attr
        elif isinstance(n, ast.Name) and (n.id in CAM_TEN or n.id.startswith("__")):
            return "tên bị cấm: " + n.id
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and "__" in n.value:
            return "chuỗi chứa gạch dưới kép (nguy cơ str.format)"
        elif isinstance(n, (ast.AsyncFunctionDef, ast.Await, ast.ClassDef)):
            return "cấu trúc không cho phép"
    ham = {n.name for n in cay.body if isinstance(n, ast.FunctionDef)}
    thieu = HAM_BAT_BUOC[dang] - ham
    if thieu: return "thiếu hàm: " + ", ".join(sorted(thieu))
    if not any(isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "GOC" for t in n.targets) for n in cay.body):
        return "thiếu biến GOC"
    return None


HARNESS = r'''
import sys, json, random, builtins
d = json.loads(sys.stdin.read())
CHO = {"math", "random", "fractions"}
def _imp(ten, *a, **k):
    if ten.split(".")[0] not in CHO: raise ImportError("không cho phép: " + ten)
    return __import__(ten, *a, **k)
TEN = ("abs min max round sum len range int float str list tuple dict set enumerate zip sorted pow divmod bool isinstance any all "
       "map reversed repr iter next filter ValueError ZeroDivisionError ArithmeticError OverflowError Exception KeyError IndexError TypeError").split()
SAFE = {k: getattr(builtins, k) for k in TEN}
SAFE["__import__"] = _imp
ns = {"__builtins__": SAFE, "__name__": "cau_mau_hop_cat"}
dang, n = d["dang"], d["n"]
out = {"goc": None, "bien_the": [], "loi": ""}
def mot(p, rng):
    de = ns["de_bai"](p)
    if dang == "TN":
        pa, idx = ns["phuong_an"](p, rng)
        r = {"de": str(de), "pa": [str(x) for x in pa], "idx": int(idx)}
        if "dap_so" in ns:
            try: r["dap_so"] = float(ns["dap_so"](p))
            except Exception: r["dap_so"] = None
    else:
        r = {"de": str(de), "dap_an": float(ns["dap_an"](p))}
    r["p"] = p
    json.dumps(r)
    return r
try:
    exec(compile(d["code"], "<mau>", "exec"), ns)
    out["goc"] = mot(ns["GOC"], random.Random(0))
    rng = random.Random(d["seed"])
    for _ in range(n * 12):
        if len(out["bien_the"]) >= n: break
        try:
            out["bien_the"].append(mot(ns["tham_so"](rng), rng))
        except Exception as e:
            out["loi"] = "%s: %s" % (type(e).__name__, str(e)[:150])
except Exception as e:
    out["loi"] = "%s: %s" % (type(e).__name__, str(e)[:200])
print(json.dumps(out, ensure_ascii=False))
'''


def env_sach():
    """Môi trường tối thiểu cho tiến trình hộp cát: KHÔNG có khoá bí mật nào của workflow."""
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}


def chay_hop_cat(code, dang, n, seed, han=20):
    """(kết quả dict, '') hoặc (None, lí do). Chạy mã trong tiến trình riêng, có giới hạn thời gian + bộ nhớ, thư mục tạm, env sạch."""
    def gioi_han():
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (768 * 2 ** 20, 768 * 2 ** 20))
            resource.setrlimit(resource.RLIMIT_CPU, (han, han))
        except Exception:
            pass                                   # hệ không hỗ trợ: vẫn còn thời gian chờ + duyệt cú pháp
    with tempfile.TemporaryDirectory() as tmp:
        try:
            r = subprocess.run([sys.executable, "-I", "-c", HARNESS], input=json.dumps({"code": code, "dang": dang, "n": n, "seed": seed}),
                               capture_output=True, text=True, timeout=han, cwd=tmp, env=env_sach(),
                               preexec_fn=gioi_han if os.name == "posix" else None)
        except subprocess.TimeoutExpired:
            return None, "chạy quá %d giây" % han
    if r.returncode != 0: return None, "tiến trình lỗi: " + (r.stderr or "")[-150:]
    try:
        return json.loads(r.stdout.strip().splitlines()[-1]), ""
    except (ValueError, IndexError):
        return None, "kết quả không đọc được"


# ============================== 2. KIỂM TRA (hàm thuần, không mạng) ==============================
def so_trong(s):
    """Số đầu tiên trong chuỗi (hiểu {,} và 3\\cdot10^{-3}); không có → nan."""
    t = str(s or "").replace("{,}", ",").replace("$", "").replace("−", "-").replace("–", "-")
    t = re.sub(r"\\(?:times|cdot)\s*10\s*\^\s*\{?\s*(-?\d+)\s*\}?", r"e\1", t)
    t = re.sub(r"\s+", "", t)
    m = re.search(r"[-+]?\d+(?:[.,]\d+)?(?:e[-+]?\d+)?", t)
    return float(m.group(0).replace(",", ".")) if m else float("nan")


def tach_pa(pa):
    kq = {}
    for m in re.finditer(r"(?m)^\s*([A-D])\s*[.)]\s*(.+?)\s*$", str(pa or "")):
        kq[m.group(1)] = m.group(2)
    return kq


def chuan_chu(s):
    return " ".join(X.bo_dau(s).split())


def dinh_dang_so(x):
    return ("%.6g" % x).replace(".", ",")


def goc_khop(dang, g, nd_goc, pa_goc, da_goc):
    """None nếu mã tái tạo ĐÚNG câu gốc (đề giống ≥ 60%, đáp án khớp đáp án đã duyệt); ngược lại trả lí do."""
    a = set(chuan_chu(str(nd_goc)[:150]).split())
    b = set(chuan_chu(g.get("de", "")).split())
    if a and len(a & b) / len(a) < 0.6: return "đề tái tạo không giống đề gốc"
    if dang == "TLN":
        x = g.get("dap_an")
        if not isinstance(x, (int, float)) or x != x: return "không tính được đáp số gốc"
        p = so_trong(da_goc)
        if p != p: ok = D.khop("TLN", dinh_dang_so(x), da_goc, 0.01)
        else: ok = abs(x) < 1e-9 if p == 0 else abs(p - x) <= 0.01 * abs(p)
        return None if ok else "đáp số tái tạo %s khác đáp án đã duyệt %s" % (dinh_dang_so(x), da_goc)
    goc = tach_pa(pa_goc)
    m = re.search(r"[A-D]", str(da_goc).upper())
    if len(goc) < 4 or not m or m.group(0) not in goc: return "không đọc được phương án gốc"
    pa, idx = g.get("pa") or [], g.get("idx")
    if len(pa) != 4 or idx not in (0, 1, 2, 3): return "phương án tái tạo sai dạng"
    van_goc, van_moi = goc[m.group(0)], pa[idx]
    p, q = so_trong(van_goc), so_trong(van_moi)
    if p == p and q == q:
        ok = abs(q) < 1e-9 if p == 0 else abs(p - q) <= 0.01 * abs(p)
    else:
        ok = chuan_chu(van_goc) == chuan_chu(van_moi)
    return None if ok else "phương án đúng tái tạo (%s) khác đáp án đã duyệt (%s)" % (van_moi[:30], van_goc[:30])


_DIEU_KHIEN = {"\x07": "\\a", "\x08": "\\b", "\x0b": "\\v", "\x0c": "\\f", "\r": "\\r", "\t": "\\t"}


def sua_latex(t):
    """[22/11] Mã Gemini hay viết "\\text", "\\alpha", "\\frac", "\\tan" trong chuỗi Python thường → \\t, \\a, \\f thành kí tự điều khiển (TAB, BEL, FF) làm hỏng công thức.
    Trả lại thành dấu \\ + chữ. Dấu xuống dòng thật không đụng, trừ khi theo sau là lệnh LaTeX quen (\\neq, \\nu, \\nabla, \\not, \\newline)."""
    t = str(t)
    for k, v in _DIEU_KHIEN.items(): t = t.replace(k, v)
    return re.sub(r"\n(?=(?:eq|u\b|abla|ot\b|ewline))", lambda m: "\\n", t)


_DON_VI = {"mm": ("L", 1e-3), "cm": ("L", 1e-2), "dm": ("L", 1e-1), "m": ("L", 1.0), "km": ("L", 1e3),
           "mg": ("M", 1e-6), "g": ("M", 1e-3), "kg": ("M", 1.0), "ms": ("T", 1e-3), "s": ("T", 1.0),
           "mN": ("F", 1e-3), "N": ("F", 1.0), "kN": ("F", 1e3), "mJ": ("E", 1e-3), "J": ("E", 1.0), "kJ": ("E", 1e3),
           "mW": ("P", 1e-3), "W": ("P", 1.0), "kW": ("P", 1e3), "Hz": ("f", 1.0), "kHz": ("f", 1e3), "MHz": ("f", 1e6), "GHz": ("f", 1e9)}
_RE_DV = re.compile(r"(?<![/^\w·*])(mm|cm|dm|km|mg|kg|ms|mN|kN|mJ|kJ|mW|kW|kHz|MHz|GHz|Hz|m|g|s|N|J|W)\b\s*\}?[\s.$;,]*$")


def gia_tri_si(t):
    """(họ đại lượng, đơn vị, giá trị quy về đơn vị chuẩn) của một phương án có đơn vị đơn giản; không đọc được → None."""
    t = str(t)
    m = _RE_DV.search(t.replace("\\text", " ").replace("\\mathrm", " ").replace("{", " ").replace("}", " "))
    v = so_trong(t)
    if not m or v != v: return None
    ho, k = _DON_VI[m.group(1)]
    return ho, m.group(1), v * k


def sua_bien_the(b):
    if not isinstance(b, dict): return b
    if isinstance(b.get("de"), str): b["de"] = sua_latex(b["de"])
    if isinstance(b.get("pa"), list): b["pa"] = [sua_latex(x) for x in b["pa"]]
    return b


def kiem_bien_the(dang, b, g, da_dung):
    """None nếu biến thể dùng được; ngược lại lí do. da_dung: set khoá đã dùng (số liệu + đề) để chống trùng."""
    de = b.get("de")
    if not isinstance(de, str) or len(de.strip()) < 40: return "đề quá ngắn"
    if re.search(r"None|\bnan\b|\binf\b|%[sdf]|\{:|\{\w+\[", de): return "đề còn sót chỗ chưa thay"
    if CN.dem_dola(de) % 2: return "dấu $ lẻ"
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\t]", de) or any(re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\t]", str(t)) for t in (b.get("pa") or [])): return "còn kí tự điều khiển làm hỏng công thức"
    khoa = json.dumps(b.get("p"), sort_keys=True, ensure_ascii=False)
    if khoa == json.dumps(g.get("p"), sort_keys=True, ensure_ascii=False) or khoa in da_dung or chuan_chu(de) in da_dung:
        return "trùng số liệu"
    if chuan_chu(de) == chuan_chu(g.get("de", "")): return "đề y như câu gốc"
    if dang == "TLN":
        x, y = b.get("dap_an"), g.get("dap_an")
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (x, y)): return "đáp số không hữu hạn"
        if x == 0 or y == 0: return "đáp số bằng 0"
        if x * y < 0: return "đáp số đổi dấu"
        if not (1e-3 <= abs(x / y) <= 1e3): return "đáp số lệch bậc độ lớn quá xa"
        if not (1e-3 <= abs(x) < 1e5): return "đáp số quá nhỏ/lớn, cần kí hiệu khoa học (bộ so đáp án chưa đọc an toàn)"
        if abs(x - y) <= 0.02 * abs(y): return "đáp số trùng đáp số gốc"
        if any(abs(x - float(k.split("|")[1])) <= 0.02 * abs(x) for k in da_dung if k.startswith("dap|")): return "đáp số trùng biến thể khác"
        return None
    pa, idx = b.get("pa") or [], b.get("idx")
    if len(pa) != 4 or idx not in (0, 1, 2, 3): return "phương án sai dạng"
    if any(re.search(r"\d[.,]\d{6,}", str(t)) for t in pa): return "phương án có số lẻ dài, chưa làm tròn"
    ds_ = b.get("dap_so")
    if isinstance(ds_, (int, float)) and math.isfinite(ds_):                 # [22/11] chống định dạng cắt phần thập phân của phương án đúng
        hien = so_trong(pa[idx])
        if hien == hien and abs(hien - ds_) > 0.03 * abs(ds_) + 1e-9: return "phương án đúng hiển thị %s lệch số tính %s" % (str(pa[idx])[:20], dinh_dang_so(ds_))
    gp = g.get("pa") or []
    if len(gp) == 4 and g.get("idx") in (0, 1, 2, 3) and chuan_chu(pa[idx]) == chuan_chu(gp[g["idx"]]):
        return "phương án đúng y hệt câu gốc (đáp án không đổi theo số liệu mới)"
    si = [gia_tri_si(t) for t in pa]
    for i in range(4):
        for j in range(i + 1, 4):
            if si[i] and si[j] and si[i][0] == si[j][0] and si[i][1] != si[j][1] and abs(si[i][2] - si[j][2]) <= 0.08 * max(abs(si[i][2]), abs(si[j][2]), 1e-12):
                return "hai phương án cùng một giá trị, chỉ khác đơn vị (%s, %s)" % (str(pa[i])[:16], str(pa[j])[:16])
    ch = [chuan_chu(t) for t in pa]
    if "" in ch or len(set(ch)) < 4: return "phương án trống hoặc trùng nhau"
    if any(re.search(r"(?i)cả\s*[a-d]|không có đáp án|tất cả", t) for t in pa): return "phương án kiểu 'cả A và B'"
    so = [so_trong(t) for t in pa]
    if all(s == s for s in so):
        for i in range(4):
            for j in range(i + 1, 4):
                if abs(so[i] - so[j]) <= 0.01 * max(abs(so[i]), abs(so[j]), 1e-12): return "hai phương án quá gần nhau"
    return None


def khoa_dap(dang, b):
    return "dap|%r" % b["dap_an"] if dang == "TLN" else "pa|%s" % b["pa"][b["idx"]]


def xu_ly_nguon(s, code, can):
    """Một câu nguồn + mã Gemini → (danh sách biến thể hợp lệ, nhãn ngắn khi thất bại, chi tiết để in log)."""
    code = re.sub(r"^```(?:python)?\s*|\s*```\s*$", "", str(code or "").strip())
    ly = kiem_ma(code, s["loai"])
    if ly: return [], "mã không an toàn hoặc thiếu hàm", ly
    seed = zlib.crc32(s["ma"].encode("utf-8"))
    kq, ly = chay_hop_cat(code, s["loai"], can + SINH_DU, seed)
    if not kq: return [], "mã chạy lỗi", ly
    g = sua_bien_the(kq.get("goc"))
    kq["bien_the"] = [sua_bien_the(b) for b in kq.get("bien_the", [])]
    if not g: return [], "mã lỗi ở số liệu gốc", kq.get("loi", "")
    ly = goc_khop(s["loai"], g, s["nd"], s["pa"], s["da"])
    if ly: return [], "không tái tạo đúng câu gốc", ly
    ds, da_dung = [], set()
    ly_cuoi = kq.get("loi", "")
    for b in kq.get("bien_the", []):
        ly = kiem_bien_the(s["loai"], b, g, da_dung)
        if ly: ly_cuoi = ly; continue
        da_dung |= {json.dumps(b["p"], sort_keys=True, ensure_ascii=False), chuan_chu(b["de"]), khoa_dap(s["loai"], b)}
        ds.append(b)
        if len(ds) >= can: break
    return (ds, "", "") if ds else ([], "biến thể không hợp lệ", ly_cuoi)


# ============================== 3. CHỌN NGUỒN ==============================
def yccd_dau(s):
    return re.split(r"[,;\s]+", str(s or "").strip())[0] if str(s or "").strip() else "(chưa gắn)"


def co_hinh(nd):
    return "[Hình" in nd or "[[DO_THI" in nd or bool(D.RE_NHAC_HINH.search(nd))


def chon_nguon(d, toi_da=None, so_bt=None, tran=None, dang_ok=None):
    """d = toàn bộ giá trị tab (dòng đầu là tiêu đề). Trả danh sách nguồn kèm 'can' (số biến thể còn thiếu)."""
    toi_da, so_bt, tran, dang_ok = toi_da or TOI_DA_NGUON, so_bt or SO_BIEN_THE, tran or TOI_DA_MOI_YCCD, dang_ok or DANG_CHO_PHEP
    td = d[0]
    c = {t: td.index(t) for t in ("Mã câu", "Mã YCCĐ", "Dạng", "Nội dung", "Phương án", "Đáp án", "Kiểm tra", "Trạng thái duyệt") if t in td}
    c_anh = next((i for i, t in enumerate(td) if t.strip().lower() == "link ảnh"), None)
    dem_yccd, bt_yccd, bt_cua, ung = collections.Counter(), collections.Counter(), collections.Counter(), []
    for r in d[1:]:
        r = r + [""] * (len(td) - len(r))
        ma, tt, kt = r[c["Mã câu"]].strip(), r[c["Trạng thái duyệt"]].strip(), r[c["Kiểm tra"]]
        y = yccd_dau(r[c["Mã YCCĐ"]])
        if tt == D.TT["AI"]: dem_yccd[y] += 1
        m = RE_MA_BT.search(ma)
        if m:
            bt_yccd[y] += 1; bt_cua[ma[:m.start()]] += 1
        if tt != D.TT["AI"] or m or DAU in kt: continue
        loai = D.loai_dang(r[c["Dạng"]])
        nd, pa, da = r[c["Nội dung"]], r[c["Phương án"]], r[c["Đáp án"]].strip()
        if loai not in dang_ok or not da or co_hinh(nd) or (c_anh is not None and r[c_anh].strip()): continue
        if len(D.cac_so(nd)) < 2: continue
        ung.append({"ma": ma, "loai": loai, "nd": nd, "pa": pa, "da": da, "yccd": y})
    ung.sort(key=lambda s: (dem_yccd[s["yccd"]] + bt_yccd[s["yccd"]], zlib.crc32(s["ma"].encode("utf-8"))))
    kq = []
    for s in ung:
        can = so_bt - bt_cua[s["ma"]]
        if can <= 0 or bt_yccd[s["yccd"]] >= tran: continue
        can = min(can, tran - bt_yccd[s["yccd"]])
        s["can"] = can
        bt_yccd[s["yccd"]] += can
        kq.append(s)
        if len(kq) >= toi_da: break
    return kq


# ============================== 4. GEMINI ==============================
SCHEMA = {"type": "OBJECT", "properties": {"ket_qua": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "ma_cau": {"type": "STRING"}, "lam_duoc": {"type": "BOOLEAN"}, "ma_python": {"type": "STRING"}, "ly_do": {"type": "STRING"}}, "required": ["ma_cau", "lam_duoc"]}}},
    "required": ["ket_qua"]}

HUONG_DAN = (
    "Bạn là giáo viên Vật lí THPT kiêm lập trình viên. Với MỖI câu dưới đây, viết MỘT đoạn mã Python để sinh các câu CÙNG DẠNG, ĐỔI SỐ LIỆU. "
    "Chỉ import math, random, fractions. Mã PHẢI có đúng các thành phần sau:\n"
    "1) GOC = {...}: dict số liệu của ĐỀ GỐC (khoá tiếng Việt không dấu, giá trị là số), đúng như đề.\n"
    "2) tham_so(rng): rng là random.Random; trả dict CÙNG KHOÁ với GOC, số liệu mới hợp lí về vật lí (cùng đơn vị, cùng cách làm tròn như đề gốc, "
    "đổi ít nhất 2 số liệu, không trùng GOC, không làm đáp số đổi dấu hay lệch quá 10 lần). Với đề cho số đo để suy ra hằng số/đại lượng đã biết (đo g bằng con lắc, đo tốc độ ánh sáng…), "
    "hãy CHỌN trước giá trị thật gần giá trị chuẩn rồi TÍNH số đo từ đó (cộng sai số nhỏ), không đổi từng số độc lập làm kết quả sai thực tế; "
    "đáp án đúng KHÔNG được trùng đáp án đề gốc.\n"
    "3) de_bai(p): trả ĐỀ BÀI đầy đủ, giữ NGUYÊN VĂN câu chữ của đề gốc, chỉ thay số liệu bằng giá trị trong p. Công thức đặt trong $…$; "
    "số thập phân dùng dấu phẩy kiểu 0{,}05; đơn vị kiểu \\text{ cm}. Tự viết hàm phụ định dạng số; hàm này KHÔNG được cắt hay làm tròn thành số nguyên "
    "khi đáp số không nguyên (tối đa 3 chữ số có nghĩa, không in số lẻ dài). Viết mọi chuỗi chứa LaTeX bằng chuỗi THÔ (tiền tố r) hoặc nhân đôi dấu gạch chéo, "
    "để \\text, \\alpha, \\frac, \\tan không bị Python hiểu thành kí tự điều khiển.\n"
    "4) Dạng TLN (trả lời ngắn): dap_an(p) trả MỘT số float, đã làm tròn đúng như đề yêu cầu, tính bằng công thức vật lí từ p.\n"
    "   Dạng TN (nhiều lựa chọn): phuong_an(p, rng) trả (danh_sach_4_chuoi, chi_so_dung). Chuỗi phương án KHÔNG kèm nhãn A. B. và có đơn vị; "
    "đáp án đúng tính bằng công thức; 3 phương án nhiễu sinh từ LỖI SAI THƯỜNG GẶP (quên đổi đơn vị, quên bình phương, nhầm công thức…); "
    "4 phương án khác nhau rõ; chi_so_dung chọn bằng rng.randrange(4); không dùng phương án kiểu 'cả A và B'. "
    "Dạng TN còn PHẢI có dap_so(p): trả số float của đáp án đúng, chưa làm tròn, CÙNG ĐƠN VỊ với phương án đúng hiển thị.\n"
    "ĐẶT lam_duoc = false (không viết mã, ghi lí do ngắn vào ly_do) nếu: câu cần hình/đồ thị, chỉ là lập luận định tính, không có công thức tính được, hoặc phụ thuộc "
    "bảng số liệu. Mã khi chạy với GOC PHẢI cho đúng đáp án trong 'dap_an_da_duyet'. Đáp án phải do code TÍNH, tuyệt đối không gõ cứng.\n"
    "CÁC CÂU:\n")


def loi_nhac(ds, loi_truoc=None):
    du_lieu = [{"ma_cau": s["ma"], "dang": s["loai"], "noi_dung": s["nd"][:1500], "phuong_an": s["pa"][:600], "dap_an_da_duyet": s["da"]} for s in ds]
    t = HUONG_DAN + json.dumps(du_lieu, ensure_ascii=False)
    if loi_truoc:
        t += "\n\nLẦN TRƯỚC các câu sau bị lỗi; hãy viết lại mã đã sửa cho đúng:\n" + json.dumps(
            {ma: {"ma_cu": code[:5000], "loi": loi[:200]} for ma, (code, loi) in loi_truoc.items()}, ensure_ascii=False)
    return t


def hoi_gemini(ds, cac_model, goi, loi_truoc=None):
    """{mã câu: mã Python hoặc ''} cho các câu model có trả lời (lam_duoc=false → '')."""
    ds_model = sorted(cac_model, key=lambda m: "lite" in m)
    data, _ = goi({"contents": [{"role": "user", "parts": [{"text": loi_nhac(ds, loi_truoc)}]}],
                   "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA, "temperature": 0.3,
                                        "maxOutputTokens": 30000}}, ds_model)
    j = json.loads("".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]))
    for g in j.get("ket_qua", []):
        if not g.get("lam_duoc"): print("  ↳ %s: model từ chối mẫu hoá – %s" % (g.get("ma_cau"), str(g.get("ly_do") or "không nêu lí do")[:140]), flush=True)
    return {str(g.get("ma_cau")): (str(g.get("ma_python") or "") if g.get("lam_duoc") else "") for g in j.get("ket_qua", [])}


# ============================== 5. GHI KHO ==============================
def dong_bien_the(td, nguon_dong, ma_bt, b, loai, luc, ngay):
    """Một dòng tab theo ĐÚNG thứ tự tiêu đề td. nguon_dong: {tên cột: giá trị} của câu nguồn."""
    r = {t: "" for t in td}
    for t in ("Mã YCCĐ", "Mã bài", "Lớp", "Mức độ", "Dạng", "Điểm", "Loại đề", "Đơn vị ra đề", "Năm học", "Kì thi", "Chủ đề tải"):
        if t in r: r[t] = nguon_dong.get(t, "")
    r["Mã câu"] = ma_bt
    r["Nội dung"] = L.chuan_hoa_latex(b["de"])
    if loai == "TN":
        r["Phương án"] = L.chuan_hoa_latex("\n".join("%s. %s" % ("ABCD"[i], t) for i, t in enumerate(b["pa"])))
        r["Đáp án"] = "ABCD"[b["idx"]]
    else:
        r["Đáp án"] = dinh_dang_so(b["dap_an"])
    if "Tên file" in r: r["Tên file"] = "Mẫu hoá từ %s (câu %s)" % (nguon_dong["Mã câu"], ma_bt.rsplit("-", 1)[-1])
    r["Kiểm tra"] = "[%s %s: biến thể của %s; đề + đáp án do code tính, số liệu gốc khớp đáp án đã duyệt – chờ duyệt 5 tầng]" % (DAU, ngay, nguon_dong["Mã câu"])
    r["Trạng thái duyệt"] = D.TT["CHUA"]
    if "Thời gian" in r: r["Thời gian"] = luc
    return [r[t] for t in td]


def ghi_lo(tab, td, c, lo, ket, ngay, luc):
    """Ghi biến thể trước, đánh dấu câu nguồn sau (nếu ngắt giữa chừng: lượt sau thấy đã có -BT và chỉ bổ sung phần thiếu)."""
    da_co = {v.strip() for v in tab.col_values(c["Mã câu"] + 1)}
    dong_moi, nhan = [], {}
    for s in lo:
        ds, nh, _ = ket[s["ma"]]
        if nh is None: continue                                  # Gemini chưa trả lời câu này → để lượt sau, không đánh dấu
        k = 0
        for b in ds:
            k += 1
            while "%s-BT%d" % (s["ma"], k) in da_co: k += 1
            ma_bt = "%s-BT%d" % (s["ma"], k); da_co.add(ma_bt)
            dong_moi.append(dong_bien_the(td, s["dong"], ma_bt, b, s["loai"], luc, ngay))
        nhan[s["ma"]] = ("sinh %d biến thể" % len(ds)) if ds else ("không làm được – " + nh)
    if dong_moi: tab.append_rows(dong_moi, value_input_option="RAW", table_range="A1")
    if not nhan: return len(dong_moi)
    dong_cua = {v.strip(): i + 1 for i, v in enumerate(tab.col_values(c["Mã câu"] + 1)) if i > 0 and v.strip()}
    kt_cot = tab.col_values(c["Kiểm tra"] + 1)
    cap = []
    for ma, nh in nhan.items():
        dong = dong_cua.get(ma)
        if not dong: continue
        kt_cu = kt_cot[dong - 1] if dong - 1 < len(kt_cot) else ""
        if DAU in kt_cu: continue
        cap.append({"range": D.gspread_a1(c["Kiểm tra"] + 1, dong), "values": [[("%s | [%s %s: %s]" % (kt_cu, DAU, ngay, nh)).strip(" |")[:45000]]]})
    if cap: tab.batch_update(cap, value_input_option="RAW")
    return len(dong_moi)


def bao_cao_thu(mau, thong_ke):
    ra = ["# Câu mẫu hoá – chạy THỬ (không ghi vào kho)\n", "Thống kê: " + "; ".join("%s = %d" % kv for kv in thong_ke.items()) + "\n"]
    for s, ds in mau[:12]:
        ra += ["\n## %s (%s, YCCĐ %s)\n" % (s["ma"], s["loai"], s["yccd"]),
               "**Gốc:** " + s["nd"][:400].replace("\n", " "), "Đáp án đã duyệt: " + s["da"] + "\n"]
        for b in ds[:2]:
            ra.append("- **Biến thể:** " + b["de"][:400].replace("\n", " "))
            if s["loai"] == "TN":
                ra.append("  - " + " | ".join("%s. %s" % ("ABCD"[i], t) for i, t in enumerate(b["pa"])) + "  → đúng: " + "ABCD"[b["idx"]]
                          + ("  (số tính: %s)" % dinh_dang_so(b["dap_so"]) if isinstance(b.get("dap_so"), (int, float)) else "  (THIẾU dap_so)"))
            else:
                ra.append("  - đáp số: " + dinh_dang_so(b["dap_an"]))
    return "\n".join(ra)


# ============================== 6. CHẠY ==============================
def chay(tab, d, cac_model, goi, che_do):
    td = d[0]
    c = {t: td.index(t) for t in ("Mã câu", "Kiểm tra") if t in td}
    nguon = chon_nguon(d)
    dong_cua = {}
    for r in d[1:]:
        r = r + [""] * (len(td) - len(r))
        dong_cua[r[td.index("Mã câu")].strip()] = {t: r[i] for i, t in enumerate(td)}
    for s in nguon: s["dong"] = dong_cua[s["ma"]]
    print("Chọn %d câu nguồn (trần %d, mỗi câu tối đa %d biến thể, dạng %s). Chế độ: %s." % (
        len(nguon), TOI_DA_NGUON, SO_BIEN_THE, "/".join(sorted(DANG_CHO_PHEP)), che_do), flush=True)
    tk, mau = collections.Counter(), []
    ngay = dt.datetime.now(X.TZ).strftime("%d/%m")
    luc = dt.datetime.now(X.TZ).strftime("%d/%m/%Y %H:%M")
    for k in range(0, len(nguon), LO):
        if not D.con_gio(): print("⏸️ Hết thời gian lượt này.", flush=True); break
        lo = nguon[k:k + LO]
        try:
            code_cua = hoi_gemini(lo, cac_model, goi)
            ket = {}
            for s in lo:
                if s["ma"] not in code_cua: ket[s["ma"]] = ([], None, "model không trả lời câu này"); continue
                ket[s["ma"]] = xu_ly_nguon(s, code_cua[s["ma"]], s["can"]) if code_cua[s["ma"]] else ([], "model báo không mẫu hoá được", "")
            loi = {m: (code_cua[m], r[2]) for m, r in ket.items() if r[1] in ("mã chạy lỗi", "mã lỗi ở số liệu gốc", "không tái tạo đúng câu gốc",
                                                                         "mã không an toàn hoặc thiếu hàm", "biến thể không hợp lệ") and code_cua.get(m)}
            if loi:                                                  # cho model sửa MỘT lần
                s2 = [s for s in lo if s["ma"] in loi]
                code2 = hoi_gemini(s2, cac_model, goi, loi)
                for s in s2:
                    if code2.get(s["ma"]):
                        moi = xu_ly_nguon(s, code2[s["ma"]], s["can"])
                        if moi[0] or not ket[s["ma"]][0]: ket[s["ma"]] = moi
        except X.HetHanMuc as e:
            print("⏸️ Hết hạn mức Gemini – dừng, làm tiếp lượt sau:", str(e)[:150], flush=True); break
        except Exception as e:
            print("⚠️ Lô %d lỗi, để lượt sau: %s" % (k // LO + 1, str(e)[:150]), flush=True); continue
        for s in lo:
            ds, nh, ct = ket[s["ma"]]
            tk["câu nguồn xử lí"] += 1
            tk["có biến thể"] += bool(ds); tk["biến thể hợp lệ"] += len(ds)
            if not ds: tk["thất bại: " + str(nh or "chưa trả lời")] += 1; print("  ✗ %s: %s %s" % (s["ma"], nh or "model chưa trả lời", ct[:100]), flush=True)
            else: print("  ✓ %s: %d biến thể" % (s["ma"], len(ds)), flush=True)
            if ds: mau.append((s, ds))
        if che_do == "ghi":
            n = ghi_lo(tab, td, c, lo, ket, ngay, luc)
            tk["dòng đã ghi"] += n
    if che_do != "ghi":
        s = bao_cao_thu(mau, tk)
        print(s)
        open("cau_mau_thu.md", "w", encoding="utf-8").write(s)
    print("📊 Mẫu hoá: " + "; ".join("%s = %d" % kv for kv in tk.items()), flush=True)
    return tk


def main():
    gc, _drive, _sa = X.ket_noi()
    kho = gc.open_by_key(X.ID_KHO_CHUNG)
    tab = kho.worksheet(D.TAB_NH)
    d = tab.get_all_values()
    cac_model = X.doc_cau_hinh(kho)
    chay(tab, d, cac_model, X.goi_gemini, CHE_DO)
    if Q: Q.ghi_sheet(kho)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if Q: Q.ghi_sheet()
        raise
