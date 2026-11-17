"""
ham_so_do_thi.py – ĐƯỜNG SIN/COS VẼ TỪ CÔNG THỨC (hàm thuần, không gọi mạng; dùng khi chuẩn hoá đề và xuất Word/đề cương/giáo án) [17/11/2026]

Bản Python của HamSoDoThi.gs (dự án Tạo đề). Chép đúng các bước của bản Apps Script:
  1. VÌ SAO: AI tự cho 8–15 điểm của đường cong, bộ vẽ nối các điểm bằng đoạn thẳng nên đồ thị dao động điều hoà / sóng
     bị gãy khúc, lệch pha, hai đỉnh không bằng nhau. Nay AI chỉ khai THAM SỐ trong trường "ham"; code tự tính 40–120 điểm
     đúng công thức, có đúng các điểm đỉnh, đáy, cắt trục, và chia trục theo chu kì (T/4, T/2, T) và biên độ (±A).
  2. AI viết trong từng đường của đồ thị, thay cho "diem":
       {"ten":"x","ham":{"loai":"dieuHoa","daiLuong":"x","bienDo":4,"chuKi":2,"pha":"-pi/3","soChuKi":2}}
       • dieuHoa : x = A·cos(2πt/T + φ); daiLuong "x" | "v" (= −Aω·sin) | "a" (= −ω²·x). v, a suy ra từ x.
       • cos|sin : y = doiY + A·cos(2πx/chuKi + pha)  (tuỳ chọn: tu, den hoặc soChuKi, doiY)
       • song    : u = A·cos(ωt ∓ 2πx/λ + φ0); truc "x" (theo toạ độ, tại t0) hoặc "t" (theo thời gian, tại x0);
                   tham số: bienDo, chuKi (T), buocSong (λ), pha, t0, x0, chieu "+" (truyền theo +x) hoặc "-".
     Pha viết số rad hoặc chữ: "pi/3", "-2pi/3", "π/6", "30°". Chu kì có thể thay bằng "tanSo" (f) hoặc "omega".
  3. Nối vào xưởng (mỗi nơi chỉ vài dòng, có công tắc):
       chuan_de.chuan_hinh_anh   → mo_rong_du_lieu: đổi "ham" thành "diem" (+ moTaHam, vachX, vachY)
       xuat_de_v2.ve_do_thi      → ap_dung_vach: vạch chia trục theo chu kì/biên độ
       xuat_word.ve_do_thi, soan_giao_an.ve_do_thi_ga → mo_rong_duong_spec (khuôn [[DO_THI: {"duong": [...]}]])
       tao_de._mo_ta_hinh        → dùng moTaHam (công thức) thay cho hàng chục điểm khi giải lại để kiểm đáp án
  4. Công tắc: biến CFG_HAM_SO_DO_THI (tab CauHinhDong) → CONG_TAC.HAM_SO_DO_THI trong trung_tam_dieu_phoi.json → mặc định bật.
     Tắt thì "ham" bị bỏ qua, hệ thống chạy y như cũ. Tham số sai thì báo lí do rõ để agent soạn lại.

Biến môi trường (tuỳ chọn): CFG_HAM_SO_DO_THI. Kiểm thử: kiem_thu_ham_so_do_thi.py (không cần khoá, không cần matplotlib).
"""
import json
import math
import os
import re
import unicodedata
from decimal import Decimal

HS_DO_THI = {
    "DIEM_MOI_CHU_KI": 20,    # số điểm lấy mẫu mỗi chu kì (lệch so với đường cong thật < 1,3% biên độ)
    "TOI_THIEU_DIEM": 40,
    "TOI_DA_DIEM": 120,
    "TOI_DA_SO_CHU_KI": 8,
    "TOI_THIEU_SO_CHU_KI": 0.25,
}
_NAN = float("nan")


def bat(mac_dinh=True):
    """Công tắc: CFG_HAM_SO_DO_THI → CONG_TAC.HAM_SO_DO_THI → mặc định."""
    v = os.environ.get("CFG_HAM_SO_DO_THI")
    if v is None:
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "trung_tam_dieu_phoi.json"), encoding="utf-8") as f:
                v = (json.load(f).get("CONG_TAC") or {}).get("HAM_SO_DO_THI")
        except (OSError, ValueError):
            v = None
    if v is None:
        return mac_dinh
    return str(v).strip().lower() not in ("false", "0", "no", "off", "tat", "tắt")


# ---------------------------------------------------------------- đọc số, đọc pha
def hs_doc_so(v):
    if isinstance(v, bool):
        return _NAN
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"\s+", "", "" if v is None else str(v)).replace(",", ".", 1)
    if re.match(r"^[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?$", s, re.I):
        return float(s)
    return _NAN


def hs_doc_pha(v):
    """Pha (rad) từ số hoặc chữ: "pi/3", "-2pi/3", "π/6", "0.5pi", "30°". Rỗng → 0. Không đọc được → NaN."""
    if v is None or v == "":
        return 0.0
    if isinstance(v, bool):
        return _NAN
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else _NAN
    s = re.sub(r"\s+", "", str(v).lower()).replace("π", "pi").replace(",", ".").replace("×", "*").replace("·", "*")
    do_do = False
    if re.search(r"(°|độ|deg)$", s):
        do_do = True
        s = re.sub(r"(°|độ|deg)$", "", s)
    m = re.match(r"^([+-]?)(\d*\.?\d*)\*?pi(?:/(\d*\.?\d+))?$", s)
    if m:
        try:
            he = 1.0 if m.group(2) == "" else float(m.group(2))
            mau = float(m.group(3)) if m.group(3) else 1.0
        except ValueError:
            return _NAN
        if not math.isfinite(he) or not math.isfinite(mau) or not mau:
            return _NAN
        return (-1 if m.group(1) == "-" else 1) * he * math.pi / mau
    so = hs_doc_so(s)
    return so * math.pi / 180 if do_do else so


def hs_dang_pha(rad):
    """Số rad → chữ dễ đọc cho AI giải lại: -π/3, 2π/3, π/2... (không khớp phân số đẹp thì ghi số)."""
    if abs(rad) < 1e-12:
        return "0"
    r = rad / math.pi
    dau, a = ("-" if r < 0 else ""), abs(r)
    for n in (1, 2, 3, 4, 6, 12):
        t = a * n
        if abs(t - round(t)) < 1e-9:
            tu = int(round(t))
            return dau + ("" if tu == 1 else str(tu)) + "π" + ("" if n == 1 else "/" + str(n))
    return _chuoi_so(round(rad, 3), False)


def _chuoi_so(v, dau_phay=True):
    """Số → chữ, tối đa 6 chữ số có nghĩa, bỏ số 0 thừa (4.0 → 4); dấu phẩy thập phân khi dau_phay."""
    v = float(v)
    if v == 0:
        return "0"
    s = format(Decimal("%.6g" % v), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",") if dau_phay else s


def hs_lay(o, khoa):
    for k in khoa:
        v = o.get(k)
        if v is not None and v != "":
            return v
    return None


def hs_loai_ham(v):
    s = unicodedata.normalize("NFD", "" if v is None else str(v).lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn").replace("đ", "d")
    s = re.sub(r"[^a-z]", "", s)
    if s in ("cos", "cosin", "cosine"):
        return "cos"
    if s in ("sin", "sine"):
        return "sin"
    if s in ("dieuhoa", "daodongdieuhoa", "dh", "harmonic"):
        return "dieuHoa"
    if s in ("song", "songcohoc", "wave"):
        return "song"
    return ""


def hs_lay_chu_ki(o, khoa_chu_ki):
    """Chu kì từ chuKi/T, hoặc tanSo (f), hoặc omega. NaN nếu không có/không hợp lệ."""
    v = hs_lay(o, khoa_chu_ki)
    if v is not None:
        return hs_doc_so(v)
    v = hs_lay(o, ["tanSo", "f"])
    if v is not None:
        f = hs_doc_so(v)
        return 1 / f if f > 0 else _NAN
    v = hs_lay(o, ["omega", "tanSoGoc", "w"])
    if v is not None:
        w = hs_doc_so(v)
        return 2 * math.pi / w if w > 0 else _NAN
    return _NAN


def _pha_chu(pha):
    return (" + " if pha > 0 else " - ") + hs_dang_pha(abs(pha)) if pha != 0 else ""


# ---------------------------------------------------------------- chuẩn hoá một "ham": y = doiY + A·cos(2πx/P + pha)
def hs_chuan_hoa_ham(ham):
    """→ dict {A, P, pha, doiY, tu, den, moTa} hoặc {"loi": "..."}."""
    if not isinstance(ham, dict):
        return {"loi": '"ham" phải là một đối tượng JSON'}
    loai = hs_loai_ham(hs_lay(ham, ["loai", "kieu", "type"]))
    if not loai:
        return {"loi": '"ham.loai" phải là dieuHoa | cos | sin | song'}
    A = hs_doc_so(hs_lay(ham, ["bienDo", "A", "a"]))
    if not A > 0:
        return {"loi": '"ham.bienDo" phải là số dương'}
    pha = hs_doc_pha(hs_lay(ham, ["pha", "phi", "phi0"]))
    if math.isnan(pha):
        return {"loi": '"ham.pha" không đọc được (viết số rad hoặc "pi/3", "-2pi/3")'}
    doi_y = 0.0
    if loai in ("cos", "sin"):
        raw = hs_lay(ham, ["doiY", "y0"])
        doi_y = 0.0 if raw is None else hs_doc_so(raw)
    if math.isnan(doi_y):
        return {"loi": '"ham.doiY" phải là số'}

    A2, pha2, mo_ta = A, pha, ""
    if loai in ("cos", "sin"):
        P = hs_lay_chu_ki(ham, ["chuKi", "T", "P"])
        if not P > 0:
            return {"loi": '"ham.chuKi" phải là số dương (hoặc dùng tanSo / omega)'}
        if loai == "sin":
            pha2 = pha - math.pi / 2                         # sin(θ) = cos(θ − π/2)
        mo_ta = ("đường hình %s: y = %s%s·%s(2π·x/%s%s) (biên độ %s, chu kì %s)" % (
            loai, (_chuoi_so(doi_y) + " + ") if doi_y != 0 else "", _chuoi_so(A), loai, _chuoi_so(P), _pha_chu(pha), _chuoi_so(A), _chuoi_so(P)))
    elif loai == "dieuHoa":
        P = hs_lay_chu_ki(ham, ["chuKi", "T", "P"])
        if not P > 0:
            return {"loi": '"ham.chuKi" phải là số dương (hoặc dùng tanSo / omega)'}
        dl = str(hs_lay(ham, ["daiLuong", "dai", "dl"]) or "x").strip().lower()
        w = 2 * math.pi / P
        goc = "x = %s·cos(2π·t/%s%s)" % (_chuoi_so(A), _chuoi_so(P), _pha_chu(pha))
        if dl.startswith("v"):
            A2, pha2 = A * w, pha + math.pi / 2
            mo_ta = "đường vận tốc v = x' = -ω·A·sin(ωt + φ) của dao động điều hoà %s, ω = 2π/T (biên độ vận tốc Aω = %s)" % (goc, _chuoi_so(A2))
        elif dl.startswith("a"):
            A2, pha2 = A * w * w, pha + math.pi
            mo_ta = "đường gia tốc a = x'' = -ω²·x của dao động điều hoà %s, ω = 2π/T (biên độ gia tốc Aω² = %s)" % (goc, _chuoi_so(A2))
        else:
            mo_ta = "đường li độ của dao động điều hoà %s (biên độ %s, chu kì %s, pha ban đầu %s)" % (goc, _chuoi_so(A), _chuoi_so(P), hs_dang_pha(pha))
    else:  # song
        T = hs_lay_chu_ki(ham, ["chuKi", "T"])
        L = hs_doc_so(hs_lay(ham, ["buocSong", "lamda", "lambda", "L"]))
        if not T > 0:
            return {"loi": 'sóng cần "ham.chuKi" (chu kì T) là số dương'}
        if not L > 0:
            return {"loi": 'sóng cần "ham.buocSong" (bước sóng λ) là số dương'}
        chieu = hs_lay(ham, ["chieu"])
        s = -1 if re.match(r"^\s*-", str("+" if chieu is None else chieu)) else 1
        truc = "t" if re.match(r"^t", str(hs_lay(ham, ["truc"]) or "x").strip(), re.I) else "x"
        raw_t0, raw_x0 = hs_lay(ham, ["t0"]), hs_lay(ham, ["x0"])
        t0 = 0.0 if raw_t0 is None else hs_doc_so(raw_t0)
        x0 = 0.0 if raw_x0 is None else hs_doc_so(raw_x0)
        if math.isnan(t0) or math.isnan(x0):
            return {"loi": '"ham.t0" và "ham.x0" phải là số'}
        w, k = 2 * math.pi / T, 2 * math.pi / L
        if truc == "x":
            P, pha2 = L, -s * (w * t0 + pha)                 # u(x) tại t = t0: cos(kx − s·θ), θ = ωt0 + φ0
        else:
            P, pha2 = T, pha - s * k * x0                    # u(t) tại x = x0
        mo_ta = ("sóng truyền theo chiều %s trục x: u = %s·cos(2π·t/%s%s2π·x/%s%s); đồ thị li độ u theo %s (biên độ %s, chu kì %s, bước sóng %s)" % (
            "dương" if s > 0 else "âm", _chuoi_so(A), _chuoi_so(T), " - " if s > 0 else " + ", _chuoi_so(L), _pha_chu(pha),
            ("toạ độ x tại thời điểm t = " + _chuoi_so(t0)) if truc == "x" else ("thời gian t tại vị trí x = " + _chuoi_so(x0)),
            _chuoi_so(A), _chuoi_so(T), _chuoi_so(L)))

    raw_tu, so_ck = hs_lay(ham, ["tu", "xMin"]), hs_lay(ham, ["soChuKi"])
    tu = 0.0 if raw_tu is None else hs_doc_so(raw_tu)
    if math.isnan(tu):
        return {"loi": '"ham.tu" phải là số'}
    raw_den = hs_lay(ham, ["den", "xMax"])
    if raw_den is not None:
        den = hs_doc_so(raw_den)
    else:
        den = tu + (2 if so_ck is None else hs_doc_so(so_ck)) * P
    if not math.isfinite(den) or not den > tu:
        return {"loi": 'khoảng vẽ không hợp lệ: "den" phải lớn hơn "tu" (hoặc dùng "soChuKi" dương)'}
    n = (den - tu) / P
    if n > HS_DO_THI["TOI_DA_SO_CHU_KI"] + 1e-9:
        return {"loi": "khoảng vẽ dài %s chu kì, tối đa %d chu kì" % (_chuoi_so(n), HS_DO_THI["TOI_DA_SO_CHU_KI"])}
    if n < HS_DO_THI["TOI_THIEU_SO_CHU_KI"] - 1e-9:
        return {"loi": "khoảng vẽ chỉ %s chu kì, cần ít nhất %s chu kì" % (_chuoi_so(n), HS_DO_THI["TOI_THIEU_SO_CHU_KI"])}
    return {"A": A2, "P": P, "pha": pha2, "doiY": doi_y, "tu": tu, "den": den,
            "moTa": "%s; x từ %s đến %s" % (mo_ta, _chuoi_so(tu), _chuoi_so(den))}


# ---------------------------------------------------------------- lấy mẫu
def hs_gia_tri(c, x):
    return c["doiY"] + c["A"] * math.cos(2 * math.pi * x / c["P"] + c["pha"])


def _lam_tron(v, ngung):
    return 0.0 if abs(v) < ngung else float("%.7g" % v)


def hs_lay_mau(c):
    """Lưới đều (20 điểm/chu kì) + đúng các điểm đỉnh, đáy, cắt trục (pha = kπ/2) → đỉnh luôn đúng ±A."""
    rong = c["den"] - c["tu"]
    so_ck = rong / c["P"]
    n = math.ceil(so_ck * HS_DO_THI["DIEM_MOI_CHU_KI"])
    n = max(HS_DO_THI["TOI_THIEU_DIEM"], min(HS_DO_THI["TOI_DA_DIEM"], n))
    xs = [c["tu"] + rong * i / n for i in range(n + 1)]
    nua_pi = math.pi / 2

    def phi(x):
        return 2 * math.pi * x / c["P"] + c["pha"]
    k0 = math.ceil(phi(c["tu"]) / nua_pi - 1e-9)
    k1 = math.floor(phi(c["den"]) / nua_pi + 1e-9)
    k = k0
    while k <= k1 and k - k0 < 400:
        xs.append((k * nua_pi - c["pha"]) * c["P"] / (2 * math.pi))
        k += 1
    xs.sort()
    eps, diem, x_truoc = rong * 1e-9, [], None
    for x in xs:
        if x < c["tu"] - eps or x > c["den"] + eps:
            continue
        if x_truoc is not None and x - x_truoc <= eps:
            continue
        diem.append([_lam_tron(x, rong * 1e-9), _lam_tron(hs_gia_tri(c, x), c["A"] * 1e-9)])
        x_truoc = x
    return diem


def hs_kiem_tra_mau(c, diem):
    """Kiểm tra độc lập mẫu vừa sinh (không tin một nguồn): trả về danh sách lỗi, rỗng = đạt."""
    loi, so_ck, tol = [], (c["den"] - c["tu"]) / c["P"], c["A"] * 1e-6
    if len(diem) < 2:
        return ["ít hơn 2 điểm"]
    if any(not diem[i][0] > diem[i - 1][0] for i in range(1, len(diem))):
        loi.append("x không tăng dần")
    rong = abs(c["den"] - c["tu"])
    if abs(diem[0][0] - c["tu"]) > rong * 1e-6 or abs(diem[-1][0] - c["den"]) > rong * 1e-6:
        loi.append("thiếu điểm đầu/cuối")
    if so_ck >= 1:
        ys = [p[1] for p in diem]
        if abs(max(ys) - (c["doiY"] + c["A"])) > tol:
            loi.append("đỉnh không bằng doiY + A")
        if abs(min(ys) - (c["doiY"] - c["A"])) > tol:
            loi.append("đáy không bằng doiY − A")
        doi_dau = 0
        for i in range(len(diem)):
            v = diem[i][1] - c["doiY"]
            tiep = diem[i + 1][1] - c["doiY"] if i + 1 < len(diem) else 0
            if abs(v) <= c["A"] * 1e-6:
                if 0 < i < len(diem) - 1:
                    doi_dau += 1
            elif i + 1 < len(diem) and abs(tiep) > c["A"] * 1e-6 and v * tiep < 0:
                doi_dau += 1
        if doi_dau < 2 * math.floor(so_ck) - 1 or doi_dau > 2 * math.ceil(so_ck) + 1:
            loi.append("số lần cắt trục (%d) không khớp %.2f chu kì" % (doi_dau, so_ck))
    return loi


# ---------------------------------------------------------------- gắn vào chuẩn hoá hình ảnh
def mo_rong_du_lieu(ds):
    """ds: danh sách đường thô của AI. Đường có "ham" được đổi thành "diem" (kèm moTaHam).
    → (ds_moi, loi, thong_tin). loi rỗng nếu ổn; thong_tin = {"cacHam": [...]} hoặc None khi không có đường nào có "ham"."""
    ra, loi, cac_ham = [], [], []
    for i, s in enumerate(ds or []):
        if not isinstance(s, dict) or not s.get("ham"):
            ra.append(s)
            continue
        c = hs_chuan_hoa_ham(s["ham"])
        if c.get("loi"):
            loi.append("đường %d: %s" % (i + 1, c["loi"]))
            continue
        diem = hs_lay_mau(c)
        sai = hs_kiem_tra_mau(c, diem)
        if sai:
            loi.append("đường %d: %s" % (i + 1, ", ".join(sai)))
            continue
        ra.append({"ten": s.get("ten") or s.get("name") or s.get("label") or "", "diem": diem, "moTaHam": c["moTa"]})
        cac_ham.append(c)
    return (ra, ('đồ thị hàm số lỗi – %s (xem quy định trường "ham")' % "; ".join(loi)) if loi else "",
            {"cacHam": cac_ham} if cac_ham else None)


# ---------------------------------------------------------------- chia trục theo chu kì và biên độ
def hs_tao_vach(lo, hi, buoc, le):
    k0, k1 = math.floor(lo / buoc + 1e-9), math.ceil(hi / buoc - 1e-9)
    ds, k = [], k0
    while k <= k1 and len(ds) < 40:
        v = float("%.10g" % (k * buoc))
        ds.append(v if v != 0 else 0.0)
        k += 1
    return {"min": ds[0] - le, "max": ds[-1] + le, "buoc": buoc, "ds": ds}


def hs_buoc_theo_bien_do(A):
    """Bước chia trục tung: A/2 (hoặc A) sao cho ±A luôn là vạch, số đẹp (tối đa 2 chữ số có nghĩa)."""
    if not A > 0:
        return 1.0

    def chu_so(v):
        s = format(Decimal("%.6g" % v), "f").lstrip("-").replace(".", "").lstrip("0").rstrip("0")
        return len(s)
    for n in (2, 1, 3):
        b = A / n
        if chu_so(b) <= 2:
            return float("%.6g" % b)
    return float("%.6g" % A)


def gan_vach(kq, thong_tin):
    """Gắn kq["vachX"], kq["vachY"] (dạng {min, max, buoc, ds}) theo chu kì và biên độ; kq["kieuDoThi"] = "line"."""
    kq["kieuDoThi"] = "line"
    P = thong_tin["cacHam"][0]["P"]
    x_lo = x_hi = y_lo = y_hi = 0.0
    for s in kq["duLieu"]:
        for p in s["diem"]:
            x_lo, x_hi, y_lo, y_hi = min(x_lo, p[0]), max(x_hi, p[0]), min(y_lo, p[1]), max(y_hi, p[1])
    so_ck = (x_hi - x_lo) / P
    buoc_x = P / (4 if so_ck <= 1.01 else 2 if so_ck <= 3.01 else 1)     # ít vạch hơn khi nhiều chu kì để số không đè nhau
    kq["vachX"] = hs_tao_vach(x_lo, x_hi, buoc_x, 0)
    buoc_y = hs_buoc_theo_bien_do(max(abs(y_lo), abs(y_hi)))
    kq["vachY"] = hs_tao_vach(y_lo, y_hi, buoc_y, buoc_y / 2)            # chừa nửa bước phía trên/dưới cho đỉnh và đáy


# ---------------------------------------------------------------- đường dẫn dùng cho khuôn [[DO_THI: {"duong": [...]}]] (đề cương, giáo án)
def co_ham_trong_spec(spec):
    return bool(isinstance(spec, dict) and isinstance(spec.get("duong"), list) and any(isinstance(d, dict) and d.get("ham") for d in spec["duong"]))


def mo_rong_duong_spec(spec):
    """Spec đồ thị của đề cương/giáo án: đổi "ham" trong "duong" thành "diem".
    → (spec_moi, vach) với vach = {"vachX":…, "vachY":…} hoặc None (không có "ham", hoặc công tắc tắt). Tham số sai → ValueError(lí do)."""
    if not bat() or not co_ham_trong_spec(spec):
        return spec, None
    ds, loi, tt = mo_rong_du_lieu(spec["duong"][:4])
    if loi:
        raise ValueError(loi)
    moi = dict(spec)
    moi["duong"] = ds
    kq = {"duLieu": [{"diem": d["diem"]} for d in ds if isinstance(d, dict) and d.get("diem")]}
    gan_vach(kq, tt)
    return moi, {"vachX": kq["vachX"], "vachY": kq["vachY"]}


def ap_dung_vach(ax, vach_x, vach_y):
    """Đặt vạch chia và giới hạn trục theo vachX/vachY; số thập phân dùng dấu phẩy."""
    from matplotlib.ticker import FuncFormatter
    dau_phay = FuncFormatter(lambda v, _: ("%g" % (v + 0.0)).replace(".", ","))
    if vach_x:
        ax.set_xticks(vach_x["ds"])
        ax.set_xlim(vach_x["min"], vach_x["max"])
        ax.xaxis.set_major_formatter(dau_phay)
    if vach_y:
        ax.set_yticks(vach_y["ds"])
        ax.set_ylim(vach_y["min"], vach_y["max"])
        ax.yaxis.set_major_formatter(dau_phay)


def ve_mui_ten_truc(ax):
    """Mũi tên ở đầu hai trục (cuối trục x bên phải, cuối trục y phía trên), đặt theo toạ độ khung nên đúng cả khi trục không bắt đầu từ 0."""
    ax.plot(1, 0, ">", color="black", ms=8, transform=ax.transAxes, clip_on=False, zorder=10, scalex=False, scaley=False)
    ax.plot(0, 1, "^", color="black", ms=8, transform=ax.transAxes, clip_on=False, zorder=10, scalex=False, scaley=False)


def truc_qua_goc(ax, nhan_x="", nhan_y="", chi_khi_am=False):
    """[17/11/2026] Đưa trục hoành đi qua y = 0 và trục tung đi qua x = 0 khi đồ thị có phần âm (kiểu SGK Vật lí):
    mũi tên nằm ở đầu phải của trục hoành và đầu trên của trục tung; tên trục ghi cạnh mũi tên; số 0 ở trục hoành ẩn để khỏi đè số 0 của trục tung.
    Gọi SAU ap_dung_vach (cần giới hạn trục đã đặt). Trục không đi qua gốc thì vẫn nằm ở mép khung, mũi tên theo mép khung.
    chi_khi_am=True (đồ thị thường, không phải đường "ham"): chỉ làm khi dữ liệu thật sự có phần âm; không thì không đụng gì và trả về False
    để nơi gọi vẽ mũi tên theo mép khung như cũ. Có làm thì trả về True. Công tắc HAM_SO_DO_THI tắt thì cũng không làm (trả về False)."""
    from matplotlib.ticker import FuncFormatter
    if chi_khi_am:
        if not bat():
            return False
        d = ax.dataLim
        if not (d.x0 < -1e-12 or d.y0 < -1e-12):
            return False
    x_lo, x_hi = ax.get_xlim()
    y_lo, y_hi = ax.get_ylim()
    ox, oy = y_lo <= 0 <= y_hi, x_lo <= 0 <= x_hi
    if ox:
        ax.spines["bottom"].set_position(("data", 0))
    if oy:
        ax.spines["left"].set_position(("data", 0))
    for ten in ("top", "right"):
        ax.spines[ten].set_visible(False)
    for ten in ("bottom", "left"):
        ax.spines[ten].set_linewidth(1.1)
    tx_ox = ax.get_yaxis_transform() if ox else ax.transAxes          # x theo khung, y theo dữ liệu (hoặc theo khung)
    tx_oy = ax.get_xaxis_transform() if oy else ax.transAxes
    ax.plot(1, 0, ">", color="black", ms=8, transform=tx_ox, clip_on=False, zorder=10, scalex=False, scaley=False)
    ax.plot(0, 1, "^", color="black", ms=8, transform=tx_oy, clip_on=False, zorder=10, scalex=False, scaley=False)
    ax.set_xlabel("")
    ax.set_ylabel("")
    if nhan_x:
        ax.annotate(nhan_x, xy=(1, 0), xycoords=tx_ox, xytext=(0, -20), textcoords="offset points", ha="right", va="top", clip_on=False)
    if nhan_y:
        ax.annotate(nhan_y, xy=(0, 1), xycoords=tx_oy, xytext=(9, -2), textcoords="offset points", ha="left", va="top", clip_on=False)
    if ox and oy:
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: "" if abs(v) < 1e-12 else ("%g" % (v + 0.0)).replace(".", ",")))
    return True
