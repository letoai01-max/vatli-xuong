"""
kiem_thu_ham_so_do_thi.py – KIỂM THỬ đường sin/cos vẽ từ công thức và các chỗ nối trong xưởng (GitHub Actions: kiem_thu.yml) [17/11/2026]

Bản Python của HamSoDoThi.test.js (cùng các ca), thêm các ca nối với chuan_de, tao_de, xuat_de_v2, xuat_word, soan_giao_an.
Chạy:  python kiem_thu_ham_so_do_thi.py [thư_mục_ra_ảnh]
Không cần khoá Google, không gọi mạng; thư viện Google thiếu thì tự giả lập. Cần matplotlib cho các ca vẽ ảnh (thiếu thì bỏ qua các ca đó).
Sai kết quả mong đợi thì thoát mã khác 0 để Actions báo đỏ.
"""
import json
import math
import os
import sys
import types


class _GiaLap(types.ModuleType):
    def __getattr__(self, ten):
        if ten.startswith("__"):
            raise AttributeError(ten)
        return object


def _gia_lap(ten):
    try:
        __import__(ten)
        return
    except ImportError:
        pass
    m = _GiaLap(ten)
    sys.modules[ten] = m
    if "." in ten:
        cha, con = ten.rsplit(".", 1)
        _gia_lap(cha)
        setattr(sys.modules[cha], con, m)


for _t in ("gspread", "googleapiclient", "googleapiclient.http", "googleapiclient.discovery", "google", "google.oauth2",
           "google.oauth2.service_account", "kiem_dinh_de"):
    _gia_lap(_t)

import ham_so_do_thi as HS            # noqa: E402
import chuan_de as CD                 # noqa: E402

dat, truot = 0, 0


def ok(dung, nd):
    global dat, truot
    if dung:
        dat += 1
    else:
        truot += 1
        print("✘ " + nd)


def gan(a, b, tol, nd):
    ok(abs(a - b) <= tol, "%s (nhận %r, cần %r)" % (nd, a, b))


def isnan(x):
    return isinstance(x, float) and math.isnan(x)


ham = HS.hs_chuan_hoa_ham
mau = HS.hs_lay_mau
kiem = HS.hs_kiem_tra_mau

# ---- 1. đọc pha ----
gan(HS.hs_doc_pha("-pi/3"), -math.pi / 3, 1e-12, "pha -pi/3")
gan(HS.hs_doc_pha("2pi/3"), 2 * math.pi / 3, 1e-12, "pha 2pi/3")
gan(HS.hs_doc_pha("π/6"), math.pi / 6, 1e-12, "pha π/6")
gan(HS.hs_doc_pha("0,5pi"), math.pi / 2, 1e-12, "pha 0,5pi")
gan(HS.hs_doc_pha("30°"), math.pi / 6, 1e-12, "pha 30°")
gan(HS.hs_doc_pha("-2*pi/3"), -2 * math.pi / 3, 1e-12, "pha -2*pi/3")
gan(HS.hs_doc_pha(1.5), 1.5, 0, "pha số")
gan(HS.hs_doc_pha(""), 0, 0, "pha rỗng")
ok(isnan(HS.hs_doc_pha("abc")), "pha rác phải là NaN")
ok(isnan(HS.hs_doc_pha("pi/0")), "pha chia 0 phải là NaN")
ok(isnan(HS.hs_doc_pha(".pi/.")), "pha dấu chấm trơ trọi phải là NaN, không được ném lỗi")
ok(HS.hs_dang_pha(-math.pi / 3) == "-π/3", "dạng pha -π/3: " + HS.hs_dang_pha(-math.pi / 3))
ok(HS.hs_dang_pha(2 * math.pi / 3) == "2π/3", "dạng pha 2π/3")
ok(HS.hs_dang_pha(math.pi / 2) == "π/2", "dạng pha π/2")
ok(HS.hs_dang_pha(0) == "0", "dạng pha 0")

# ---- 2. dao động điều hoà: x, v, a ----
A, T, phi = 4, 2, -math.pi / 3
cx = ham({"loai": "dieuHoa", "daiLuong": "x", "bienDo": A, "chuKi": T, "pha": "-pi/3", "soChuKi": 2})
cv = ham({"loai": "dieuHoa", "daiLuong": "v", "bienDo": A, "chuKi": T, "pha": "-pi/3", "soChuKi": 2})
ca = ham({"loai": "dieuHoa", "daiLuong": "a", "bienDo": A, "chuKi": T, "pha": "-pi/3", "soChuKi": 2})
ok(not cx.get("loi") and not cv.get("loi") and not ca.get("loi"), "dieuHoa x/v/a hợp lệ")
w = 2 * math.pi / T


def so_sanh(c, f, ten):
    d = mau(c)
    lech = max(abs(p[1] - f(p[0])) for p in d)
    ok(lech < 1e-5 * c["A"], "%s: lệch tối đa so với công thức độc lập = %r" % (ten, lech))
    ok(kiem(c, d) == [], "%s: hs_kiem_tra_mau đạt – %s" % (ten, ", ".join(kiem(c, d))))
    return d


dx = so_sanh(cx, lambda t: A * math.cos(w * t + phi), "x(t)")
dv = so_sanh(cv, lambda t: -A * w * math.sin(w * t + phi), "v(t) = -Aω·sin")
da = so_sanh(ca, lambda t: -w * w * A * math.cos(w * t + phi), "a(t) = -ω²x")
ok(40 <= len(dx) <= 120, "số điểm x(t) = %d" % len(dx))
for p in dx:
    gan(next(q for q in da if q[0] == p[0])[1], -w * w * p[1], 1e-4, "a = -ω²x tại t=%r" % p[0])
gan(max(p[1] for p in dx), A, 1e-9, "đỉnh x = A đúng")
gan(min(p[1] for p in dx), -A, 1e-9, "đáy x = -A đúng")
gan(max(p[1] for p in dv), A * w, 1e-5, "vmax = Aω đúng")
gan(max(p[1] for p in da), A * w * w, 1e-4, "amax = Aω² đúng")
ok(dx[0][0] == 0 and abs(dx[-1][0] - 4) < 1e-9, "x chạy từ 0 đến 2T")
gan(dx[0][1], 2, 1e-5, "x(0) = A·cos(-π/3) = 2")
ok(any(abs(p[1] - A) < 1e-9 for p in dx), "có điểm đỉnh chính xác")
ok(any(abs(p[1] + A) < 1e-9 for p in dx), "có điểm đáy chính xác")
ok(any(p[1] == 0 for p in dx), "có điểm cắt trục hoành chính xác (y = 0, không phải 1e-16)")
ok(not any(math.copysign(1, p[1]) < 0 and p[1] == 0 for p in dx), "không có -0")

# ---- 3. cos / sin ----
csin = ham({"loai": "sin", "bienDo": 3, "chuKi": 0.02, "pha": 0, "soChuKi": 3})
dsin = so_sanh(csin, lambda t: 3 * math.sin(2 * math.pi * t / 0.02), "sin chu kì 0,02")
ok(any(abs(p[1] - 3) < 1e-9 for p in dsin), "sin có đỉnh = 3")
csin_pha = ham({"loai": "sin", "bienDo": 2, "chuKi": 4, "pha": "pi/6", "doiY": 1, "tu": -2, "den": 6})
so_sanh(csin_pha, lambda x: 1 + 2 * math.sin(2 * math.pi * x / 4 + math.pi / 6), "sin có pha, dịch trục, tu âm")
gan(ham({"loai": "cos", "bienDo": 1, "tanSo": 50, "soChuKi": 2})["P"], 0.02, 1e-15, "tanSo 50 Hz → chu kì 0,02")
gan(ham({"loai": "cos", "bienDo": 1, "omega": 100 * math.pi, "soChuKi": 2})["P"], 0.02, 1e-12, "omega 100π → chu kì 0,02")

# ---- 4. sóng ----
lam, Ts, Aw, t0, x0 = 4, 0.5, 2, 0.125, 1
wS, kS = 2 * math.pi / Ts, 2 * math.pi / lam


def u(x, t, s, p0):                      # công thức gốc của đề
    return Aw * math.cos(wS * t - s * kS * x + p0)


cWx = ham({"loai": "song", "truc": "x", "bienDo": Aw, "chuKi": Ts, "buocSong": lam, "pha": 0, "t0": t0})
so_sanh(cWx, lambda x: u(x, t0, 1, 0), "sóng u(x) tại t0, truyền +x")
gan(cWx["P"], lam, 0, "sóng theo x có chu kì không gian = λ")
cWt = ham({"loai": "song", "truc": "t", "bienDo": Aw, "chuKi": Ts, "buocSong": lam, "pha": 0, "x0": x0})
so_sanh(cWt, lambda t: u(x0, t, 1, 0), "sóng u(t) tại x0")
gan(cWt["P"], Ts, 0, "sóng theo t có chu kì = T")
so_sanh(ham({"loai": "song", "truc": "x", "bienDo": Aw, "chuKi": Ts, "buocSong": lam, "pha": "pi/4", "t0": 0.3, "chieu": "-"}),
        lambda x: u(x, 0.3, -1, math.pi / 4), "sóng truyền chiều âm có pha ban đầu")
so_sanh(ham({"loai": "song", "truc": "t", "bienDo": Aw, "chuKi": Ts, "buocSong": lam, "pha": "-pi/2", "x0": 2.5, "chieu": "-"}),
        lambda t: u(2.5, t, -1, -math.pi / 2), "sóng u(t) chiều âm")
gan(mau(ham({"loai": "song", "truc": "t", "bienDo": Aw, "chuKi": Ts, "buocSong": lam, "pha": 0, "x0": 0}))[0][1], Aw, 1e-9,
    "sóng: tại x=0,t=0 pha 0 → u = A")

# ---- 5. báo lỗi đúng chỗ ----
ok("loai" in ham({"loai": "tan", "bienDo": 1, "chuKi": 1})["loi"], "loại lạ bị từ chối")
ok("bienDo" in ham({"loai": "cos", "bienDo": -1, "chuKi": 1})["loi"], "biên độ âm bị từ chối")
ok("chuKi" in ham({"loai": "cos", "bienDo": 1})["loi"], "thiếu chu kì bị từ chối")
ok("pha" in ham({"loai": "cos", "bienDo": 1, "chuKi": 1, "pha": "xyz"})["loi"], "pha rác bị từ chối")
ok("tối đa" in ham({"loai": "cos", "bienDo": 1, "chuKi": 1, "soChuKi": 20})["loi"], "quá 8 chu kì bị từ chối")
ok("ít nhất" in ham({"loai": "cos", "bienDo": 1, "chuKi": 1, "tu": 0, "den": 0.1})["loi"], "quá ngắn bị từ chối")
ok("buocSong" in ham({"loai": "song", "bienDo": 1, "chuKi": 1})["loi"], "sóng thiếu λ bị từ chối")
ok(len(ham("abc")["loi"]) > 0 and len(ham(None)["loi"]) > 0, "ham không phải object bị từ chối")
ok("loi" not in ham({"loai": "COS", "bienDo": "4,5", "chuKi": "2", "pha": "π/2"}), "chấp nhận chữ hoa, số viết chuỗi dùng dấu phẩy")
ok("loi" not in ham({"loai": "Dao động điều hòa", "bienDo": 1, "chuKi": 1}) or True, "loại có dấu tiếng Việt không làm sập")
ok("loi" not in ham({"loai": "điều hoà", "bienDo": 1, "chuKi": 1}), "loại viết 'điều hoà' có dấu vẫn nhận ra dieuHoa")

# ---- 6. vạch chia trục ----
gan(HS.hs_buoc_theo_bien_do(4), 2, 1e-12, "bước Y cho A=4")
gan(HS.hs_buoc_theo_bien_do(3), 1.5, 1e-12, "bước Y cho A=3")
gan(HS.hs_buoc_theo_bien_do(2.5), 2.5, 1e-12, "bước Y cho A=2.5 (1,25 xấu → ±2,5)")
gan(HS.hs_buoc_theo_bien_do(0.04), 0.02, 1e-12, "bước Y cho A=0,04")
gan(HS.hs_buoc_theo_bien_do(10), 5, 1e-12, "bước Y cho A=10")


def vach(ham_obj):
    ds, loi, tt = HS.mo_rong_du_lieu([{"ten": "", "ham": ham_obj}])
    kq = {"duLieu": ds}
    HS.gan_vach(kq, tt)
    return kq


k1 = vach({"loai": "dieuHoa", "daiLuong": "x", "bienDo": 4, "chuKi": 2, "pha": "-pi/3", "soChuKi": 2})
ok(k1["vachX"]["ds"] == [0, 1, 2, 3, 4], "2 chu kì → vạch X theo T/2: %r" % k1["vachX"]["ds"])
ok(k1["vachY"]["ds"] == [-4, -2, 0, 2, 4], "vạch Y có ±A: %r" % k1["vachY"]["ds"])
ok(k1["vachY"]["max"] > 4 and k1["vachY"]["min"] < -4, "chừa khoảng trống phía trên/dưới đỉnh")
k2 = vach({"loai": "cos", "bienDo": 3, "chuKi": 2, "soChuKi": 1})
ok(k2["vachX"]["ds"] == [0, 0.5, 1, 1.5, 2], "1 chu kì → vạch X theo T/4: %r" % k2["vachX"]["ds"])
ok(k2["vachY"]["ds"] == [-3, -1.5, 0, 1.5, 3], "A=3 → ±3 và ±1,5")
k3 = vach({"loai": "cos", "bienDo": 1, "chuKi": 1, "soChuKi": 6})
ok(k3["vachX"]["buoc"] == 1, "6 chu kì → vạch X mỗi chu kì")
ok(len(k3["vachX"]["ds"]) == 7, "số vạch X hợp lí khi nhiều chu kì: %d" % len(k3["vachX"]["ds"]))
k4 = vach({"loai": "cos", "bienDo": 1, "chuKi": 2, "tu": -2, "den": 4})
ok(k4["vachX"]["ds"][0] == -2 and 0 in k4["vachX"]["ds"], "trục X có cả phần âm và vạch 0")

# ---- 7. nối với chuan_de.chuan_hinh_anh ----
h_ai = CD.chuan_hinh_anh(json.dumps({
    "loai": "dothi", "kieuDoThi": "scatter", "chuThich": "Hình 1", "nhanTrucX": "t (s)", "nhanTrucY": "x (cm)",
    "duLieu": [{"ten": "x", "ham": {"loai": "dieuHoa", "daiLuong": "x", "bienDo": 4, "chuKi": 2, "pha": "-pi/3", "soChuKi": 2}}]}))
ok(h_ai and h_ai["hopLe"], 'chuan_hinh_anh nhận hinhAnh dạng chuỗi JSON có "ham": %s' % (h_ai and h_ai["lyDo"]))
ok(h_ai["kieuDoThi"] == "line", "đường hàm số luôn được nối (line), dù AI ghi scatter")
ok(len(h_ai["duLieu"][0]["diem"]) >= 40, "đã sinh %d điểm" % len(h_ai["duLieu"][0]["diem"]))
ok(bool(h_ai.get("vachX")) and bool(h_ai.get("vachY")), "đã gắn vạch chia trục")
mo_ta = h_ai["duLieu"][0].get("moTaHam", "")
ok("cos" in mo_ta and "-π/3" in mo_ta, "mô tả cho AI giải lại có công thức và pha: " + mo_ta)
ok(CD.chuan_hinh_anh(h_ai) is h_ai, "chuẩn hoá lần hai trả về đúng đối tượng cũ (không sinh lại)")
ok(len(json.dumps(h_ai)) < 6000, "đối tượng đã chuẩn hoá gọn: %d kí tự" % len(json.dumps(h_ai)))
h_loi = CD.chuan_hinh_anh({"loai": "dothi", "duLieu": [{"ten": "x", "ham": {"loai": "cos", "bienDo": 4}}]})
ok(h_loi and h_loi["hopLe"] is False and "chuKi" in h_loi["lyDo"], "ham lỗi → hinhAnh không hợp lệ, lí do rõ để agent soạn lại: %s" % (h_loi and h_loi["lyDo"]))
h_cu = CD.chuan_hinh_anh({"loai": "dothi", "kieuDoThi": "line", "nhanTrucX": "t (s)", "nhanTrucY": "v (m/s)", "duLieu": [{"ten": "", "diem": [[0, 2], [4, 10]]}]})
ok(h_cu["hopLe"] and len(h_cu["duLieu"][0]["diem"]) == 2 and "vachX" not in h_cu and "vachY" not in h_cu, 'đồ thị có "diem" (đường thẳng) không đổi hành vi')
ok("moTaHam" not in h_cu["duLieu"][0], "đường thường không có moTaHam")
h_tron = CD.chuan_hinh_anh({"loai": "dothi", "duLieu": [{"ten": "a", "diem": [[0, 0], [1, 1]]},
                                                       {"ten": "x", "ham": {"loai": "cos", "bienDo": 1, "chuKi": 1}}]})
ok(h_tron["hopLe"] and len(h_tron["duLieu"]) == 2 and "moTaHam" not in h_tron["duLieu"][0] and "moTaHam" in h_tron["duLieu"][1],
   "một đồ thị trộn đường thẳng và đường hàm số")

# công tắc tắt → y như cũ
os.environ["CFG_HAM_SO_DO_THI"] = "false"
h_tat = CD.chuan_hinh_anh({"loai": "dothi", "duLieu": [{"ten": "x", "ham": {"loai": "cos", "bienDo": 4, "chuKi": 2}}]})
ok(h_tat and h_tat["hopLe"] is False, 'HAM_SO_DO_THI tắt → "ham" bị bỏ qua như bản cũ (không có điểm → không hợp lệ)')
ok(HS.mo_rong_duong_spec({"duong": [{"ten": "x", "ham": {"loai": "cos", "bienDo": 4, "chuKi": 2}}]})[1] is None, "công tắc tắt: khuôn [[DO_THI]] không đổi")
del os.environ["CFG_HAM_SO_DO_THI"]
ok(HS.bat() is True, "mặc định (và theo trung_tam_dieu_phoi.json) công tắc BẬT")
os.environ["CFG_HAM_SO_DO_THI"] = "0"
ok(HS.bat() is False, "CFG_HAM_SO_DO_THI=0 → tắt")
del os.environ["CFG_HAM_SO_DO_THI"]

# ---- 8. khuôn [[DO_THI: {"duong": [...]}]] của đề cương và giáo án ----
spec = {"tieuDe": "Hình 1", "x": "t (s)", "y": "x (cm)",
        "duong": [{"ten": "x", "ham": {"loai": "dieuHoa", "daiLuong": "x", "bienDo": 4, "chuKi": 2, "pha": "-pi/3", "soChuKi": 2}}]}
spec2, vach2 = HS.mo_rong_duong_spec(spec)
ok(vach2 and len(spec2["duong"][0]["diem"]) >= 40 and "ham" in spec["duong"][0], "mo_rong_duong_spec sinh điểm, không sửa spec gốc")
spec_cu = {"duong": [{"ten": "A", "diem": [[0, 0], [2, 4]]}]}
ok(HS.mo_rong_duong_spec(spec_cu) == (spec_cu, None), "spec không có ham đi qua nguyên vẹn")
try:
    HS.mo_rong_duong_spec({"duong": [{"ten": "x", "ham": {"loai": "cos", "bienDo": 1}}]})
    ok(False, "ham thiếu chu kì phải ném ValueError")
except ValueError as e:
    ok("chuKi" in str(e), "ValueError nêu rõ lí do: %s" % e)

# ---- 9. tao_de._mo_ta_hinh và hướng dẫn cho Gemini ----
try:
    import tao_de as TD
    mt = TD._mo_ta_hinh(h_ai)
    ok("cos" in mt and len(mt) < 700 and "[[" not in mt, "_mo_ta_hinh đưa công thức, không đưa hàng chục điểm (%d kí tự)" % len(mt))
    ok("[[0.0, 2.0], [4.0, 10.0]]" in TD._mo_ta_hinh(h_cu), "_mo_ta_hinh đường thường vẫn liệt kê điểm (như cũ)")
    ok('"ham"' in TD.quy_dinh_phan(1), 'quy_dinh_phan có hướng dẫn "ham" khi công tắc bật')
    os.environ["CFG_HAM_SO_DO_THI"] = "false"
    ok('"ham"' not in TD.quy_dinh_phan(1), 'công tắc tắt → không nhắc Gemini dùng "ham"')
    del os.environ["CFG_HAM_SO_DO_THI"]
except ImportError as e:
    print("⚠️ Bỏ qua ca tao_de (thiếu thư viện: %s)" % e)

# ---- 10. vẽ ảnh thật bằng các bộ vẽ của xưởng ----
ra = sys.argv[1] if len(sys.argv) > 1 else "ket_qua_kiem_thu_ham"
try:
    import matplotlib  # noqa: F401
    co_mpl = True
except ImportError:
    co_mpl = False
    print("⚠️ Không có matplotlib: bỏ qua các ca vẽ ảnh")
if co_mpl:
    os.makedirs(ra, exist_ok=True)
    import xuat_de_v2 as X
    import xuat_word as XW
    d1 = os.path.join(ra, "de_thi_x.png")
    X.ve_do_thi(h_ai, d1)
    ok(os.path.getsize(d1) > 5000, "xuat_de_v2.ve_do_thi vẽ được đồ thị x(t) từ công thức")
    for ten, dl in (("v", "v"), ("a", "a")):
        h = CD.chuan_hinh_anh({"loai": "dothi", "nhanTrucX": "t (s)", "nhanTrucY": ten,
                               "duLieu": [{"ten": ten, "ham": {"loai": "dieuHoa", "daiLuong": dl, "bienDo": 4, "chuKi": 2, "pha": "-pi/3", "soChuKi": 2}}]})
        X.ve_do_thi(h, os.path.join(ra, "de_thi_%s.png" % ten))
    h_song = CD.chuan_hinh_anh({"loai": "dothi", "nhanTrucX": "x (m)", "nhanTrucY": "u (cm)",
                                "duLieu": [{"ten": "t = 0,125 s", "ham": {"loai": "song", "truc": "x", "bienDo": 2, "chuKi": 0.5, "buocSong": 4, "pha": 0, "t0": 0.125}}]})
    X.ve_do_thi(h_song, os.path.join(ra, "de_thi_song.png"))
    ok(os.path.getsize(os.path.join(ra, "de_thi_song.png")) > 5000, "xuat_de_v2 vẽ được sóng u(x)")
    X.ve_do_thi(h_cu, os.path.join(ra, "de_thi_duong_thang.png"))
    ok(os.path.getsize(os.path.join(ra, "de_thi_duong_thang.png")) > 3000, "xuat_de_v2 đường thẳng cũ vẫn vẽ được")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.plot([0, 4], [-4, 4])
    HS.ap_dung_vach(ax, {"ds": [0, 1, 2, 3, 4], "min": 0, "max": 4}, {"ds": [-4, 0, 4], "min": -5, "max": 5})
    HS.truc_qua_goc(ax, "t (s)", "x (cm)")
    ok(ax.spines["bottom"].get_position() == ("data", 0), "trục hoành đi qua y = 0 khi đồ thị có phần âm")
    ok(ax.spines["left"].get_position() == ("data", 0), "trục tung đi qua x = 0")
    fig2, ax2 = plt.subplots()
    ax2.plot([0, 4], [1, 4])
    HS.ap_dung_vach(ax2, {"ds": [0, 4], "min": 0, "max": 4}, {"ds": [1, 4], "min": 1, "max": 4.5})
    HS.truc_qua_goc(ax2, "t", "y")
    ok(ax2.spines["bottom"].get_position() != ("data", 0), "đồ thị không chứa y = 0 thì trục hoành ở mép khung")
    plt.close("all")
    d2 = os.path.join(ra, "de_cuong_x.png")
    XW.ve_do_thi(json.dumps(spec), d2)
    ok(os.path.getsize(d2) > 5000, "xuat_word.ve_do_thi (đề cương) vẽ được đường có ham")
    d3 = os.path.join(ra, "de_cuong_cu.png")
    XW.ve_do_thi(json.dumps({"tieuDe": "Hình 2", "x": "t (s)", "y": "v (m/s)", "duong": [{"ten": "A", "diem": [[0, 0], [2, 4], [4, 8]]}]}), d3)
    ok(os.path.getsize(d3) > 3000, "xuat_word.ve_do_thi đường thẳng cũ vẫn vẽ được (và có mũi tên)")
    try:
        XW.ve_do_thi(json.dumps({"duong": [{"ten": "x", "ham": {"loai": "cos", "bienDo": 1}}]}), os.path.join(ra, "loi.png"))
        ok(False, "xuat_word: ham thiếu chu kì phải ném lỗi")
    except ValueError as e:
        ok("chuKi" in str(e), "xuat_word báo rõ lí do khi ham sai (không vẽ hình sai)")
    try:
        import soan_giao_an as GA
        d4 = os.path.join(ra, "giao_an_x.png")
        GA.ve_do_thi_ga(spec, d4)
        ok(os.path.getsize(d4) > 5000, "soan_giao_an.ve_do_thi_ga vẽ được đường có ham")
        GA.ve_do_thi_ga({"truc_x": "t", "truc_y": "v", "duong": [{"ten": "A", "diem": [[0, 0], [1, 2]]}]}, os.path.join(ra, "giao_an_cu.png"))
        ok(os.path.getsize(os.path.join(ra, "giao_an_cu.png")) > 3000, "soan_giao_an đường thẳng cũ vẫn vẽ được")
    except ImportError as e:
        print("⚠️ Bỏ qua ca soan_giao_an (thiếu thư viện: %s)" % e)

print("✔ Đạt tất cả %d kiểm tra." % dat if truot == 0 else "✘ %d kiểm tra trượt, %d đạt." % (truot, dat))
sys.exit(0 if truot == 0 else 1)
