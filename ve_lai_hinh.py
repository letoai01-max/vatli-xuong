# -*- coding: utf-8 -*-
"""
ve_lai_hinh.py – KIỂM HÌNH GẮN VÀO CÂU, GỠ HÌNH SAI, TỰ VẼ HÌNH / ĐỒ THỊ KHỚP ĐỀ (GitHub Actions).  [24/11/2026]

BÀI TOÁN: hình gắn vào câu (cột "Link ảnh") nhiều khi không thống nhất với nội dung đề / mô tả [Hình: …] / [[DO_THI: …]].
MODULE NÀY LÀM BA VIỆC, MỖI CÂU MỘT LẦN:
  1. KIỂM hình đang gắn: model nhìn ảnh THẬT, đối chiếu từng chi tiết với đề → khớp / không khớp / không chắc.
  2. GỠ hình không khớp khỏi cột "Link ảnh" (link cũ được chép vào cột "Kiểm tra" để khôi phục được; KHÔNG xoá tệp trong kho ảnh vì
     câu khác có thể dùng chung).
  3. VẼ hình mới bằng code từ mô tả: Gemini chỉ trả BẢN MÔ TẢ DỮ LIỆU (JSON: đồ thị hoặc sơ đồ gồm đoạn, mũi tên, lò xo, điện trở…),
     matplotlib vẽ; hình mới phải qua CỔNG KHỚP TUYỆT ĐỐI gồm HAI bằng chứng độc lập mới được gắn:
       (a) Luật bằng code (0 lượt AI): mọi SỐ ghi trên hình phải có trong đề; số trong mô tả hình phải có trên hình; hình KHÔNG được
           lộ đáp án; nhãn trục / mốc / điểm đúng cấu trúc; biểu thức hàm chỉ gồm phép toán an toàn.
       (b) Model NHÌN LẠI hình vừa vẽ, đối chiếu với đề: thiếu gì, thừa gì, sai gì (khác lần soạn).
     Không khớp → vẽ lại kèm danh sách lỗi (tối đa VE_LAI_SO_LAN lần). Vẫn không khớp thì KHÔNG gắn hình lỗi.

QUY TẮC XỬ LÍ SAU CÙNG (an toàn):
  • Hình cũ KHỚP → giữ nguyên, chỉ ghi "[hình …: khớp]".
  • Hình cũ SAI / KHÔNG CHẮC + vẽ được hình mới đạt cổng → thay bằng hình mới (đẩy PNG lên repo ảnh, ghi link raw vào "Link ảnh").
  • Hình cũ SAI + KHÔNG vẽ được → gỡ hình sai, câu thành "Cần người xem" (ghi rõ lí do); hình cũ chỉ "không chắc" + không vẽ được → giữ hình cũ.
  • Câu không có đủ dữ liệu để vẽ (mô tả thiếu) → không vẽ bừa, báo "thiếu dữ liệu để vẽ".
  • Không có GITHUB_TOKEN (không đẩy được ảnh) → KHÔNG làm gì cả (không gỡ hình cũ), chỉ cảnh báo.

CÁCH CHẠY
  • Gắn trong duyet_cau.py (câu mới vào hàng chờ): đặt VE_LAI_HINH=true (cờ mặc định TẮT → duyet_cau chạy y như cũ).
  • Quét cả kho câu cũ: python ve_lai_hinh.py   (cần VE_LAI_HINH=true; mỗi lượt xử lí tối đa VE_LAI_TOI_DA_CAU câu, câu đã kiểm có dấu
    "[hình …" trong cột Kiểm tra thì bỏ qua, nên chạy lặp lại sẽ đi tiếp chứ không làm lại).

BIẾN MÔI TRƯỜNG
  VE_LAI_HINH=true         bật tính năng (mặc định false)
  VE_LAI_CHI_BAO=true      chạy thử: chỉ ghi báo cáo + lưu PNG vào thư mục ve_lai_xem_thu/, KHÔNG sửa Sheet, KHÔNG đẩy ảnh lên repo
  VE_LAI_SO_LAN=2          số lần vẽ lại sau lần vẽ đầu khi chưa khớp (mặc định 2 → tối đa 3 lần vẽ)
  VE_LAI_TOI_DA_CAU=30     số câu tối đa mỗi lượt (duyet_cau: mỗi file) – phần còn lại để lượt sau
  VE_LAI_MODEL=...         model Gemini nhìn ảnh (mặc định lấy model trong tab CauHinh; phải là model nhìn được ảnh)
  VE_LAI_CA_LOAI=true      cũng xử lí câu trạng thái "Loại" (mặc định bỏ qua)
  VE_LAI_LAI_TAT_CA=true   làm lại cả câu đã có dấu "[hình …" (mặc định bỏ qua)
  GITHUB_TOKEN             bắt buộc để đẩy PNG: workflow cần  permissions: contents: write  và  env: GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  GITHUB_REPOSITORY        mặc định tự có trong Actions (letoai01-max/vatli-xuong); VE_LAI_NHANH = nhánh (mặc định main)
  GEMINI_API_KEY, GEMINI_API_KEY_1..5   như các tệp khác của xưởng (không ghi khoá ra log)
"""
import base64
import datetime as dt
import hashlib
import io
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

_DUNG = ("true", "1", "yes", "on", "bat", "bật")
TZ = dt.timezone(dt.timedelta(hours=7))
TAB_NH = "NganHangCauHoi"
DAU_HINH = "[hình "          # dấu ghi ở cột Kiểm tra: câu đã được xử lí hình (mỗi câu một lần)
REPO_MAC_DINH = "letoai01-max/vatli-xuong"
THU_MUC_ANH = "images/ve_lai"
DPI = 200


def bat():
    return os.environ.get("VE_LAI_HINH", "false").strip().lower() in _DUNG


def _cong(ten):
    return os.environ.get(ten, "false").strip().lower() in _DUNG


def _so_nguyen(ten, mac_dinh, toi_thieu=0):
    try:
        return max(toi_thieu, int(float(os.environ.get(ten, str(mac_dinh)) or mac_dinh)))
    except ValueError:
        return mac_dinh


class HetHan(Exception):
    """Hết hạn mức / không còn khoá dùng được (duyet_cau đổi thành X.HetHanMuc)."""


# =====================================================================================================
#  A. GỌI GEMINI CÓ ẢNH (tự chứa: không phụ thuộc chữ kí của doc_de.goi_gemini)
# =====================================================================================================
def _cac_khoa():
    ks = []
    for t in ["GEMINI_API_KEY"] + ["GEMINI_API_KEY_%d" % i for i in range(1, 6)]:
        v = os.environ.get(t, "").strip()
        if v and v not in ks:
            ks.append(v)
    return ks


def _mime(b):
    if b[:8] == b"\x89PNG\r\n\x1a\n": return "image/png"
    if b[:3] == b"\xff\xd8\xff": return "image/jpeg"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP": return "image/webp"
    if b[:4] == b"GIF8": return "image/gif"
    return ""


def goi_gemini_anh(prompt, anh=(), models=(), timeout=150):
    """Gửi prompt + ảnh (bytes) cho Gemini, bắt trả JSON. Xoay khoá khi 429; hết cả khoá lẫn model → HetHan. Trả về chuỗi văn bản."""
    ks = _cac_khoa()
    if not ks:
        raise HetHan("Không có GEMINI_API_KEY")
    parts = [{"text": prompt}]
    for b in anh:
        parts.append({"inline_data": {"mime_type": _mime(b) or "image/png", "data": base64.b64encode(b).decode("ascii")}})
    body = json.dumps({"contents": [{"role": "user", "parts": parts}],
                       "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}}).encode("utf-8")
    ds_model = [m for m in models if m] or ["gemini-2.5-flash"]
    het = 0
    loi_cuoi = ""
    for m in ds_model:
        for k in ks:
            req = urllib.request.Request(
                "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % urllib.parse.quote(m, safe="-._"),
                data=body, headers={"Content-Type": "application/json", "x-goog-api-key": k})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    j = json.loads(r.read().decode("utf-8"))
                ung = (j.get("candidates") or [{}])[0]
                txt = "".join(p.get("text", "") for p in (ung.get("content") or {}).get("parts", []))
                if txt.strip():
                    return txt
                loi_cuoi = "trả rỗng (%s)" % ung.get("finishReason", "?")
            except urllib.error.HTTPError as e:
                if e.code in (429, 503):
                    het += 1
                    loi_cuoi = "HTTP %d" % e.code
                    continue                              # khoá khác
                if e.code in (400, 403, 404):
                    loi_cuoi = "HTTP %d (model %s)" % (e.code, m)
                    break                                 # model này không dùng được → model sau
                loi_cuoi = "HTTP %d" % e.code
            except (urllib.error.URLError, TimeoutError, ValueError) as e:
                loi_cuoi = "lỗi mạng: %s" % str(e)[:80]
    if het:
        raise HetHan("Gemini hết hạn mức (%s)" % loi_cuoi)
    raise RuntimeError("Gemini không trả được kết quả (%s)" % loi_cuoi)


GOI = goi_gemini_anh      # tách ra để test thay bằng hàm giả


def _json(txt):
    """Lấy đối tượng JSON đầu tiên trong chuỗi (chịu được ```json … ```). None nếu không đọc được."""
    t = re.sub(r"```(?:json)?", "", str(txt or "")).strip()
    for kieu in ((t,), (t[t.find("{"):t.rfind("}") + 1],)):
        try:
            v = json.loads(kieu[0])
            return v if isinstance(v, dict) else None
        except ValueError:
            continue
    return None


# =====================================================================================================
#  B. TÁCH MÔ TẢ HÌNH · SỐ TRONG ĐỀ (hàm thuần, 0 lượt AI)
# =====================================================================================================
RE_MO_TA = re.compile(r"\[Hình[^\]]*\]|\[\[DO_THI.*?\]\]", re.S)
RE_NHAC = re.compile(r"(?i)\b(hình vẽ|như hình|hình bên|đồ thị (như|ở) hình|hình \d)")
RE_SO = re.compile(r"(?<![A-Za-z_^{\\])\d+(?:[.,]\d+)?")


def mo_ta_hinh(noi_dung, phuong_an=""):
    """Danh sách mô tả hình ([Hình: …], [[DO_THI: …]]) có trong đề + phương án."""
    return [m.group(0) for m in RE_MO_TA.finditer(str(noi_dung or "") + "\n" + str(phuong_an or ""))]


def can_xu_li(noi_dung, phuong_an, co_anh):
    """Câu có đủ căn cứ để kiểm / vẽ hình: có mô tả hình, hoặc nhắc hình mà đang gắn ảnh (để kiểm ảnh)."""
    if mo_ta_hinh(noi_dung, phuong_an):
        return True
    return bool(co_anh and RE_NHAC.search(str(noi_dung or "")))


def _so(s):
    return float(str(s).replace(",", "."))


def so_trong(van):
    """Tập mọi số xuất hiện trong văn bản (cả dạng âm, cả số mũ)."""
    kq = set()
    t = str(van or "")
    for m in re.finditer(r"\d+(?:[.,]\d+)?", t):
        v = _so(m.group(0))
        kq.add(round(v, 9)); kq.add(round(-v, 9))
    return kq


def _co(v, tap):
    return round(float(v), 9) in tap or any(abs(float(v) - u) <= 1e-9 * max(1.0, abs(u)) for u in tap)


def so_tren_nhan(nhan):
    """Các số ghi trên một nhãn (bỏ chỉ số dưới / số mũ như F_1, x^2)."""
    return [_so(m.group(0)) for m in RE_SO.finditer(str(nhan or ""))]


def dinh_dang_so(v):
    v = float(v)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return ("%.6g" % v).replace(".", ",")


def _la_cua_json(o, ra):
    if isinstance(o, bool):
        return
    if isinstance(o, (int, float)):
        ra.add(round(float(o), 9)); return
    if isinstance(o, dict):
        for k, v in o.items():
            if re.search(r"(?i)font|dpi|size|width|linewidth|color|mau", str(k)): continue
            _la_cua_json(v, ra)
    elif isinstance(o, (list, tuple)):
        for v in o: _la_cua_json(v, ra)


def so_can_co_tren_hinh(mo_ta):
    """Số trong phần mô tả hình mà hình phải thể hiện (bỏ 0 và 1; [[DO_THI]] đọc theo JSON, lỗi JSON thì bỏ qua phần đó)."""
    can = set()
    for m in mo_ta:
        if m.startswith("[[DO_THI"):
            ph = m[len("[[DO_THI"):].lstrip(" :").rstrip("]").strip()
            try:
                _la_cua_json(json.loads(ph), can)
            except ValueError:
                continue
        else:
            for v in so_trong(m):
                if v > 0: can.add(v)
    return {v for v in can if abs(v) not in (0.0, 1.0)}


# =====================================================================================================
#  C. KIỂM BẢN MÔ TẢ DỮ LIỆU (spec) – bắt lỗi trước khi vẽ
# =====================================================================================================
CAC_PHAN_TU = {
    "doan": ("a", "b"), "gap_khuc": ("diem",), "da_giac": ("diem",), "mui_ten": ("a", "b"), "chu_nhat": ("tam", "rong", "cao"),
    "tron": ("tam", "r"), "cung": ("tam", "r", "g1", "g2"), "lo_xo": ("a", "b"), "dien_tro": ("a", "b"), "bien_tro": ("a", "b"),
    "nguon": ("a", "b"), "tu_dien": ("a", "b"), "den": ("tam", "r"), "dong_ho": ("tam", "r", "chu"), "khoa": ("a", "b"),
    "cuon_day": ("a", "b"), "dat": ("a", "b"), "chu": ("vt", "noi_dung"), "cong_muot": ("diem",),
}
TOI_DA_PHAN_TU, TOI_DA_DIEM, TOI_DA_NHAN = 120, 400, 60
RE_BIEU_THUC = re.compile(r"^[0-9x\s+\-*/().,^a-z_]*$")
HAM_CHO_PHEP = {"x", "sin", "cos", "tan", "exp", "log", "sqrt", "abs", "pi", "e"}


def _kt_so(v, ten):
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ValueError("%s phải là số (nhận %r)" % (ten, v))
    if not math.isfinite(f) or abs(f) > 1e9:
        raise ValueError("%s ngoài phạm vi" % ten)
    return f


def _kt_diem(p, ten):
    if not isinstance(p, (list, tuple)) or len(p) != 2:
        raise ValueError("%s phải là [x, y]" % ten)
    return [_kt_so(p[0], ten + ".x"), _kt_so(p[1], ten + ".y")]


def _nhan(s):
    return str(s if s is not None else "").strip()[:TOI_DA_NHAN]


def kiem_bieu_thuc(bt):
    """Biểu thức hàm theo x chỉ gồm số, + - * / ^ ( ) và hàm toán học cho phép. Trả về chuỗi python hoặc ném ValueError."""
    s = str(bt or "").strip()
    if not s or len(s) > 120 or not RE_BIEU_THUC.match(s):
        raise ValueError("biểu thức hàm không hợp lệ")
    for tk in re.findall(r"[a-z_]+", s):
        if tk not in HAM_CHO_PHEP:
            raise ValueError("biểu thức dùng tên không cho phép: " + tk)
    return s.replace("^", "**")


def chuan_truc(t, ten):
    if not isinstance(t, dict):
        raise ValueError(ten + " thiếu")
    lo, hi = _kt_so(t.get("min"), ten + ".min"), _kt_so(t.get("max"), ten + ".max")
    if hi <= lo:
        raise ValueError(ten + ": max phải lớn hơn min")
    moc = []
    for i, m in enumerate(t.get("cac_moc") or []):
        if not isinstance(m, dict): raise ValueError("%s.cac_moc[%d] phải là đối tượng" % (ten, i))
        v = _kt_so(m.get("v"), "%s.cac_moc[%d].v" % (ten, i))
        if not (lo - 1e-9 <= v <= hi + 1e-9): raise ValueError("%s.cac_moc[%d] nằm ngoài trục" % (ten, i))
        moc.append({"v": v, "nhan": _nhan(m.get("nhan"))})
    cd = t.get("chia_deu")
    if cd:
        b = _kt_so((cd or {}).get("buoc"), ten + ".chia_deu.buoc")
        if b <= 0 or (hi - lo) / b > 60: raise ValueError(ten + ".chia_deu.buoc không hợp lý")
        cd = {"buoc": b}
    return {"nhan": _nhan(t.get("nhan")), "min": lo, "max": hi, "cac_moc": moc[:40], "chia_deu": cd or None}


def chuan_do_thi(d):
    if not isinstance(d, dict): raise ValueError("do_thi thiếu")
    kq = {"truc_x": chuan_truc(d.get("truc_x"), "truc_x"), "truc_y": chuan_truc(d.get("truc_y"), "truc_y"),
          "luoi": bool(d.get("luoi")), "duong": [], "diem": [], "duong_doi": []}
    xs, ys = kq["truc_x"], kq["truc_y"]
    for i, dg in enumerate((d.get("duong") or [])[:12]):
        if not isinstance(dg, dict): raise ValueError("duong[%d] phải là đối tượng" % i)
        kieu = dg.get("kieu")
        o = {"kieu": kieu, "net": "dut" if dg.get("net") == "dut" else "lien", "nhan": _nhan(dg.get("nhan")), "vi_tri_nhan": None,
             "dau_mut": bool(dg.get("dau_mut"))}
        if dg.get("vi_tri_nhan") is not None: o["vi_tri_nhan"] = _kt_diem(dg["vi_tri_nhan"], "duong[%d].vi_tri_nhan" % i)
        if kieu in ("gap_khuc", "cong_muot"):
            pts = dg.get("diem")
            if not isinstance(pts, list) or not (2 <= len(pts) <= TOI_DA_DIEM): raise ValueError("duong[%d].diem cần 2..%d điểm" % (i, TOI_DA_DIEM))
            o["diem"] = [_kt_diem(p, "duong[%d].diem" % i) for p in pts]
        elif kieu == "ham":
            o["bieu_thuc"] = kiem_bieu_thuc(dg.get("bieu_thuc"))
            o["tu"] = _kt_so(dg.get("tu", xs["min"]), "duong[%d].tu" % i)
            o["den"] = _kt_so(dg.get("den", xs["max"]), "duong[%d].den" % i)
            if o["den"] <= o["tu"]: raise ValueError("duong[%d]: den phải lớn hơn tu" % i)
        else:
            raise ValueError("duong[%d].kieu phải là gap_khuc | cong_muot | ham" % i)
        kq["duong"].append(o)
    for i, p in enumerate((d.get("diem") or [])[:40]):
        if not isinstance(p, dict): raise ValueError("diem[%d] phải là đối tượng" % i)
        kq["diem"].append({"x": _kt_so(p.get("x"), "diem[%d].x" % i), "y": _kt_so(p.get("y"), "diem[%d].y" % i), "nhan": _nhan(p.get("nhan")),
                           "rong": bool(p.get("rong"))})
    for i, p in enumerate((d.get("duong_doi") or [])[:40]):
        if not isinstance(p, dict): raise ValueError("duong_doi[%d] phải là đối tượng" % i)
        kq["duong_doi"].append({"x": _kt_so(p.get("x"), "duong_doi[%d].x" % i), "y": _kt_so(p.get("y"), "duong_doi[%d].y" % i),
                                "ve_x": p.get("ve_x", True) is not False, "ve_y": p.get("ve_y", True) is not False})
    if not kq["duong"] and not kq["diem"]:
        raise ValueError("đồ thị không có đường hoặc điểm nào")
    return kq


def chuan_so_do(ds):
    if not isinstance(ds, list) or not ds: raise ValueError("so_do phải là danh sách không rỗng")
    if len(ds) > TOI_DA_PHAN_TU: raise ValueError("so_do quá %d phần tử" % TOI_DA_PHAN_TU)
    kq = []
    for i, e in enumerate(ds):
        if not isinstance(e, dict): raise ValueError("so_do[%d] phải là đối tượng" % i)
        k = e.get("k")
        if k not in CAC_PHAN_TU: raise ValueError("so_do[%d].k=%r không hợp lệ (cho phép: %s)" % (i, k, ", ".join(sorted(CAC_PHAN_TU))))
        for kh in CAC_PHAN_TU[k]:
            if kh not in e: raise ValueError("so_do[%d] (%s) thiếu khoá %s" % (i, k, kh))
        o = {"k": k, "net": "dut" if e.get("net") == "dut" else "lien", "nhan": _nhan(e.get("nhan")), "day": min(6.0, max(0.5, _kt_so(e.get("day", 1.6), "day"))),
             "to": bool(e.get("to"))}
        for kh in ("a", "b", "tam", "vt", "vi_tri_nhan"):
            if e.get(kh) is not None: o[kh] = _kt_diem(e[kh], "so_do[%d].%s" % (i, kh))
        for kh in ("rong", "cao", "r", "g1", "g2", "goc", "so_vong"):
            if e.get(kh) is not None: o[kh] = _kt_so(e[kh], "so_do[%d].%s" % (i, kh))
        if k in ("gap_khuc", "da_giac", "cong_muot"):
            pts = e.get("diem")
            if not isinstance(pts, list) or not (2 <= len(pts) <= TOI_DA_DIEM): raise ValueError("so_do[%d].diem cần 2..%d điểm" % (i, TOI_DA_DIEM))
            o["diem"] = [_kt_diem(p, "so_do[%d].diem" % i) for p in pts]
        if k == "chu": o["noi_dung"] = _nhan(e.get("noi_dung"))
        if k == "dong_ho": o["chu"] = _nhan(e.get("chu"))[:3]
        if k in ("tron", "den", "dong_ho") and o["r"] <= 0: raise ValueError("so_do[%d].r phải dương" % i)
        if k == "chu_nhat" and (o["rong"] <= 0 or o["cao"] <= 0): raise ValueError("so_do[%d]: rong, cao phải dương" % i)
        if k == "tron": o["dac"] = bool(e.get("dac"))
        kq.append(o)
    return kq


def chuan_spec(spec):
    """Bản mô tả của model → bản sạch (hoặc ValueError kèm lí do để đưa lại cho model sửa)."""
    if not isinstance(spec, dict): raise ValueError("kết quả không phải JSON đối tượng")
    loai = spec.get("loai")
    kq = {"loai": loai, "rong": min(9.0, max(2.5, _kt_so(spec.get("rong", 6), "rong"))), "cao": min(8.0, max(2.0, _kt_so(spec.get("cao", 4), "cao")))}
    if loai == "do_thi": kq["do_thi"] = chuan_do_thi(spec.get("do_thi"))
    elif loai == "so_do":
        kq["so_do"] = chuan_so_do(spec.get("so_do"))
        if spec.get("khung") is not None:
            kh = spec["khung"]
            if not isinstance(kh, (list, tuple)) or len(kh) != 4: raise ValueError("khung phải là [xmin, ymin, xmax, ymax]")
            kq["khung"] = [_kt_so(v, "khung") for v in kh]
            if kq["khung"][2] <= kq["khung"][0] or kq["khung"][3] <= kq["khung"][1]: raise ValueError("khung không hợp lệ")
    else:
        raise ValueError("loai phải là do_thi hoặc so_do")
    return kq


# =====================================================================================================
#  D. VẼ BẰNG MATPLOTLIB (spec sạch → PNG). Trả về (png_bytes, các_nhãn_đã_vẽ)
# =====================================================================================================
def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "mathtext.fontset": "dejavusans", "axes.unicode_minus": False})
    return plt


def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, facecolor="white", bbox_inches="tight", pad_inches=0.12)
    import matplotlib.pyplot as plt
    plt.close(fig)
    return buf.getvalue()


def _ham(bt, tu, den):
    import numpy as np
    x = np.linspace(tu, den, 400)
    ns = {"x": x, "sin": np.sin, "cos": np.cos, "tan": np.tan, "exp": np.exp, "log": np.log, "sqrt": np.sqrt, "abs": np.abs, "pi": math.pi, "e": math.e}
    with np.errstate(all="ignore"):
        y = eval(bt, {"__builtins__": {}}, ns)          # an toàn: biểu thức đã qua kiem_bieu_thuc (chỉ số, x, phép toán, hàm toán)
    y = np.broadcast_to(np.asarray(y, dtype=float), x.shape).copy()
    y[~np.isfinite(y)] = np.nan
    if np.isnan(y).all():
        raise ValueError("biểu thức hàm không cho giá trị hữu hạn")
    y[np.abs(y) > 1e6] = np.nan
    return x, y


def _muot(pts):
    """Đường cong trơn qua các điểm (scipy PCHIP nếu có, không thì nối đoạn)."""
    import numpy as np
    xs = [p[0] for p in pts]
    if all(b > a for a, b in zip(xs, xs[1:])):
        try:
            from scipy.interpolate import PchipInterpolator
            X = np.linspace(xs[0], xs[-1], 300)
            return X, PchipInterpolator(xs, [p[1] for p in pts])(X)
        except Exception:                                # scipy thiếu → nối đoạn
            pass
    return xs, [p[1] for p in pts]


def ve_do_thi(spec):
    plt = _plt()
    d = spec["do_thi"]
    tx, ty = d["truc_x"], d["truc_y"]
    nhan_ve = []
    fig, ax = plt.subplots(figsize=(spec["rong"], spec["cao"]))
    rx, ry = tx["max"] - tx["min"], ty["max"] - ty["min"]
    ax.set_xlim(tx["min"] - 0.06 * rx, tx["max"] + 0.20 * rx)
    ax.set_ylim(ty["min"] - 0.06 * ry, ty["max"] + 0.10 * ry)
    ax.axis("off")
    hy = 0.0 if ty["min"] < 0 < ty["max"] else ty["min"]       # trục hoành nằm ở y = hy
    vx = 0.0 if tx["min"] < 0 < tx["max"] else tx["min"]       # trục tung nằm ở x = vx
    mui = dict(arrowstyle="-|>", color="black", lw=1.4, shrinkA=0, shrinkB=0, mutation_scale=14)
    ax.annotate("", xy=(tx["max"] + 0.05 * rx, hy), xytext=(tx["min"] - 0.02 * rx if tx["min"] < 0 else tx["min"], hy), arrowprops=mui)
    ax.annotate("", xy=(vx, ty["max"] + 0.06 * ry), xytext=(vx, ty["min"] - 0.02 * ry if ty["min"] < 0 else ty["min"]), arrowprops=mui)
    if tx["nhan"]:
        ax.annotate(tx["nhan"], xy=(tx["max"] + 0.05 * rx, hy), xytext=(8, -4), textcoords="offset points", fontsize=12, ha="left", va="center"); nhan_ve.append(tx["nhan"])
    if ty["nhan"]:
        ax.annotate(ty["nhan"], xy=(vx, ty["max"] + 0.06 * ry), xytext=(8, -2), textcoords="offset points", fontsize=12, ha="left"); nhan_ve.append(ty["nhan"])
    if tx["min"] <= 0 <= tx["max"] and ty["min"] <= 0 <= ty["max"] and abs(vx) < 1e-12 and abs(hy) < 1e-12:
        ax.annotate("O", xy=(0, 0), xytext=(-12, -14), textcoords="offset points", fontsize=12)
    if d["luoi"]:
        for v in _chia(tx): ax.plot([v, v], [ty["min"], ty["max"]], color="#cccccc", lw=0.6, zorder=0)
        for v in _chia(ty): ax.plot([tx["min"], tx["max"]], [v, v], color="#cccccc", lw=0.6, zorder=0)

    def moc_x(v, nhan):
        ax.plot([v, v], [hy - 0.012 * ry, hy + 0.012 * ry], color="black", lw=1.2)
        ax.annotate(nhan, xy=(v, hy), xytext=(0, -15), textcoords="offset points", fontsize=11, ha="center"); nhan_ve.append(nhan)

    def moc_y(v, nhan):
        ax.plot([vx - 0.012 * rx, vx + 0.012 * rx], [v, v], color="black", lw=1.2)
        ax.annotate(nhan, xy=(vx, v), xytext=(-6, -4), textcoords="offset points", fontsize=11, ha="right"); nhan_ve.append(nhan)

    daf = set()
    for v in _chia(tx):
        if abs(v - vx) > 1e-9: moc_x(v, dinh_dang_so(v)); daf.add(("x", round(v, 9)))
    for v in _chia(ty):
        if abs(v - hy) > 1e-9: moc_y(v, dinh_dang_so(v)); daf.add(("y", round(v, 9)))
    for m in tx["cac_moc"]:
        if ("x", round(m["v"], 9)) not in daf and abs(m["v"] - vx) > 1e-9: moc_x(m["v"], m["nhan"] or dinh_dang_so(m["v"]))
    for m in ty["cac_moc"]:
        if ("y", round(m["v"], 9)) not in daf and abs(m["v"] - hy) > 1e-9: moc_y(m["v"], m["nhan"] or dinh_dang_so(m["v"]))
    for dg in d["duong"]:
        ls = "--" if dg["net"] == "dut" else "-"
        if dg["kieu"] == "ham":
            X, Y = _ham(dg["bieu_thuc"], dg["tu"], dg["den"])
        elif dg["kieu"] == "cong_muot":
            X, Y = _muot(dg["diem"])
        else:
            X, Y = [p[0] for p in dg["diem"]], [p[1] for p in dg["diem"]]
        ax.plot(X, Y, ls, color="black", lw=1.8, solid_capstyle="round")
        if dg["nhan"]:
            px, py = dg["vi_tri_nhan"] or [X[-1], Y[-1]]
            ax.annotate(dg["nhan"], xy=(px, py), xytext=(6, 6), textcoords="offset points", fontsize=12); nhan_ve.append(dg["nhan"])
    for p in d["duong_doi"]:
        if p["ve_x"]: ax.plot([p["x"], p["x"]], [hy, p["y"]], "--", color="black", lw=0.9)
        if p["ve_y"]: ax.plot([vx, p["x"]], [p["y"], p["y"]], "--", color="black", lw=0.9)
    for p in d["diem"]:
        ax.plot([p["x"]], [p["y"]], "o", ms=5.5, mfc="white" if p["rong"] else "black", mec="black", zorder=5)
        if p["nhan"]:
            ax.annotate(p["nhan"], xy=(p["x"], p["y"]), xytext=(6, 5), textcoords="offset points", fontsize=12); nhan_ve.append(p["nhan"])
    return _png(fig), nhan_ve


def _chia(t):
    """Các mốc chia đều của một trục (không gồm điểm giao trục)."""
    if not t["chia_deu"]: return []
    b, v, kq = t["chia_deu"]["buoc"], math.ceil(t["min"] / t["chia_deu"]["buoc"] - 1e-9) * t["chia_deu"]["buoc"], []
    while v <= t["max"] + 1e-9 and len(kq) < 80:
        kq.append(round(v, 9)); v += b
    return kq


def _pt(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _rot(p, o, ang):
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    return (o[0] + (p[0] - o[0]) * c - (p[1] - o[1]) * s, o[1] + (p[0] - o[0]) * s + (p[1] - o[1]) * c)


def _tren_day(a, b, doan):
    """Chuỗi điểm [(t, offset_vuông_góc)] dọc đoạn a→b → toạ độ thật."""
    L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1e-9
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    return [(a[0] + ux * L * t - uy * off, a[1] + uy * L * t + ux * off) for t, off in doan], L, (ux, uy)


def _vuong(a, b, kc=None):
    """Vị trí nhãn: trung điểm a–b, dịch theo phương vuông góc (bên trái chiều a→b) để không đè lên dây."""
    L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1e-9
    d = kc if kc is not None else 0.22 * L + 0.4
    return ((a[0] + b[0]) / 2 - (b[1] - a[1]) / L * d, (a[1] + b[1]) / 2 + (b[0] - a[0]) / L * d)


def ve_so_do(spec):
    plt = _plt()
    from matplotlib.patches import Arc, Circle, Polygon, Rectangle
    fig, ax = plt.subplots(figsize=(spec["rong"], spec["cao"]))
    ax.set_aspect("equal")
    ax.axis("off")
    nhan_ve = []
    tat_ca = []

    def ghi(*ps):
        tat_ca.extend(ps)

    def day_net(e):
        return e["day"], ("--" if e["net"] == "dut" else "-")

    def gan_nhan(e, mac_dinh, off=(6, 6)):
        if not e["nhan"]: return
        p = e.get("vi_tri_nhan") or mac_dinh
        ax.annotate(e["nhan"], xy=p, xytext=off if not e.get("vi_tri_nhan") else (0, 0), textcoords="offset points", fontsize=12, ha="center")
        ghi(p); nhan_ve.append(e["nhan"])

    for e in spec["so_do"]:
        k, lw, ls = e["k"], e["day"], ("--" if e["net"] == "dut" else "-")
        if k == "doan":
            ax.plot([e["a"][0], e["b"][0]], [e["a"][1], e["b"][1]], ls, color="black", lw=lw, solid_capstyle="round"); ghi(e["a"], e["b"]); gan_nhan(e, _pt(e["a"], e["b"], 0.5))
        elif k in ("gap_khuc", "da_giac", "cong_muot"):
            pts = e["diem"]; ghi(*pts)
            if k == "da_giac":
                ax.add_patch(Polygon(pts, closed=True, fill=e["to"], fc="#dddddd" if e["to"] else "none", ec="black", lw=lw, ls=ls))
            elif k == "cong_muot":
                X, Y = _muot(pts); ax.plot(X, Y, ls, color="black", lw=lw)
            else:
                ax.plot([p[0] for p in pts], [p[1] for p in pts], ls, color="black", lw=lw)
            gan_nhan(e, pts[len(pts) // 2])
        elif k == "mui_ten":
            ax.annotate("", xy=e["b"], xytext=e["a"], arrowprops=dict(arrowstyle="-|>", color="black", lw=lw, shrinkA=0, shrinkB=0, mutation_scale=14, ls=ls)); ghi(e["a"], e["b"])
            m = _pt(e["a"], e["b"], 0.5); gan_nhan(e, m, (8, 8))
        elif k == "chu_nhat":
            ang = e.get("goc", 0.0)
            c = e["tam"]; w, h = e["rong"], e["cao"]
            goc = [_rot((c[0] + sx * w / 2, c[1] + sy * h / 2), c, ang) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            ax.add_patch(Polygon(goc, closed=True, fill=e["to"], fc="#dddddd" if e["to"] else "white", ec="black", lw=lw, ls=ls, zorder=3)); ghi(*goc)
            if e["nhan"]:
                ax.annotate(e["nhan"], xy=c, ha="center", va="center", fontsize=12, zorder=4); nhan_ve.append(e["nhan"])
        elif k in ("tron", "den", "dong_ho"):
            c, r = e["tam"], e["r"]
            ax.add_patch(Circle(c, r, fill=True, fc="black" if (k == "tron" and e.get("dac", False)) else "white", ec="black", lw=lw, zorder=4)); ghi((c[0] - r, c[1] - r), (c[0] + r, c[1] + r))
            if k == "den":
                d = r / math.sqrt(2); ax.plot([c[0] - d, c[0] + d], [c[1] - d, c[1] + d], color="black", lw=lw, zorder=5); ax.plot([c[0] - d, c[0] + d], [c[1] + d, c[1] - d], color="black", lw=lw, zorder=5)
            if k == "dong_ho":
                ax.annotate(e["chu"], xy=c, ha="center", va="center", fontsize=13, zorder=5); nhan_ve.append(e["chu"])
            if e["nhan"] and k != "dong_ho":
                gan_nhan(e, (c[0], c[1] + r), (0, 8))
        elif k == "cung":
            c, r = e["tam"], e["r"]
            ax.add_patch(Arc(c, 2 * r, 2 * r, theta1=e["g1"], theta2=e["g2"], ec="black", lw=lw, ls=ls)); ghi((c[0] - r, c[1] - r), (c[0] + r, c[1] + r))
            am = math.radians((e["g1"] + e["g2"]) / 2); gan_nhan(e, (c[0] + r * 1.18 * math.cos(am), c[1] + r * 1.18 * math.sin(am)), (0, 0))
        elif k == "lo_xo":
            a, b = e["a"], e["b"]; n = int(e.get("so_vong", 8)); n = min(max(n, 2), 30)
            doan = [(0, 0), (0.12, 0)] + [(0.12 + 0.76 * (i + 0.5) / n, 0.18 * (1 if i % 2 == 0 else -1) * 1.0) for i in range(n)] + [(0.88, 0), (1, 0)]
            L = math.hypot(b[0] - a[0], b[1] - a[1]); pts, _, _ = _tren_day(a, b, [(t, o * min(L, 3) * 0.6) for t, o in doan])
            ax.plot([p[0] for p in pts], [p[1] for p in pts], color="black", lw=lw); ghi(a, b); gan_nhan(e, _vuong(a, b), (0, 0))
        elif k in ("dien_tro", "bien_tro"):
            a, b = e["a"], e["b"]; L = math.hypot(b[0] - a[0], b[1] - a[1]); h = 0.09 * L if L > 0 else 0.1
            p, _, (ux, uy) = _tren_day(a, b, [(0, 0), (0.3, 0), (0.3, h), (0.7, h), (0.7, -h), (0.3, -h), (0.3, 0)])
            ax.plot([q[0] for q in p[:2]], [q[1] for q in p[:2]], color="black", lw=lw)
            ax.add_patch(Polygon(_tren_day(a, b, [(0.3, -h), (0.7, -h), (0.7, h), (0.3, h)])[0], closed=True, fill=True, fc="white", ec="black", lw=lw, zorder=3))
            q2 = _tren_day(a, b, [(0.7, 0), (1, 0)])[0]; ax.plot([q[0] for q in q2], [q[1] for q in q2], color="black", lw=lw); ghi(a, b)
            if k == "bien_tro":
                m1, m2 = _tren_day(a, b, [(0.2, -2.4 * h), (0.8, 2.4 * h)])[0]
                ax.annotate("", xy=m2, xytext=m1, arrowprops=dict(arrowstyle="-|>", color="black", lw=1.2, shrinkA=0, shrinkB=0)); ghi(m1, m2)
            gan_nhan(e, _vuong(a, b), (0, 0))
        elif k == "nguon":
            a, b = e["a"], e["b"]; L = math.hypot(b[0] - a[0], b[1] - a[1]); h1, h2 = 0.22 * L, 0.13 * L
            for t, hh, w in ((0.46, h1, lw), (0.54, h2, lw * 2.2)):
                q = _tren_day(a, b, [(t, -hh), (t, hh)])[0]; ax.plot([r[0] for r in q], [r[1] for r in q], color="black", lw=w)
            for q in (_tren_day(a, b, [(0, 0), (0.46, 0)])[0], _tren_day(a, b, [(0.54, 0), (1, 0)])[0]): ax.plot([r[0] for r in q], [r[1] for r in q], color="black", lw=lw)
            ghi(a, b); gan_nhan(e, _vuong(a, b), (0, 0))
        elif k == "tu_dien":
            a, b = e["a"], e["b"]; L = math.hypot(b[0] - a[0], b[1] - a[1]); hh = 0.2 * L
            for t in (0.46, 0.54):
                q = _tren_day(a, b, [(t, -hh), (t, hh)])[0]; ax.plot([r[0] for r in q], [r[1] for r in q], color="black", lw=lw * 1.4)
            for q in (_tren_day(a, b, [(0, 0), (0.46, 0)])[0], _tren_day(a, b, [(0.54, 0), (1, 0)])[0]): ax.plot([r[0] for r in q], [r[1] for r in q], color="black", lw=lw)
            ghi(a, b); gan_nhan(e, _vuong(a, b), (0, 0))
        elif k == "khoa":
            a, b = e["a"], e["b"]; L = math.hypot(b[0] - a[0], b[1] - a[1])
            p, _, _ = _tren_day(a, b, [(0, 0), (0.3, 0), (0.7, 0.28), (0.7, 0), (1, 0)])
            ax.plot([p[0][0], p[1][0]], [p[0][1], p[1][1]], color="black", lw=lw); ax.plot([p[1][0], p[2][0]], [p[1][1], p[2][1]], color="black", lw=lw)
            ax.plot([p[3][0], p[4][0]], [p[3][1], p[4][1]], color="black", lw=lw)
            for q in (p[1], p[3]): ax.plot([q[0]], [q[1]], "o", color="black", ms=4)
            ghi(a, b); gan_nhan(e, _vuong(a, b), (0, 0))
        elif k == "cuon_day":
            a, b = e["a"], e["b"]; n = min(max(int(e.get("so_vong", 6)), 2), 30)
            pts = []
            for i in range(n):
                for j in range(13):
                    t = (i + j / 12.0) / n
                    ang = math.pi * (1 - j / 12.0)
                    pts.append((t, 0.5 / n * math.sin(ang) * 2.4))
            p, _, _ = _tren_day(a, b, [(0, 0)] + pts + [(1, 0)])
            ax.plot([q[0] for q in p], [q[1] for q in p], color="black", lw=lw); ghi(a, b); gan_nhan(e, _vuong(a, b), (0, 0))
        elif k == "dat":
            a, b = e["a"], e["b"]; ax.plot([a[0], b[0]], [a[1], b[1]], color="black", lw=lw)
            L = math.hypot(b[0] - a[0], b[1] - a[1]); n = max(3, int(L / 0.25 + 0.5))
            ux, uy = ((b[0] - a[0]) / L, (b[1] - a[1]) / L) if L else (1, 0)
            for i in range(n + 1):
                p = _pt(a, b, i / n); ax.plot([p[0], p[0] - 0.2 * ux - 0.2 * uy * 1.0], [p[1], p[1] - 0.2 * uy + 0.2 * ux * 1.0], color="black", lw=0.8)
            ghi(a, b)
        elif k == "chu":
            ax.annotate(e["noi_dung"], xy=e["vt"], ha="center", va="center", fontsize=12); ghi(e["vt"]); nhan_ve.append(e["noi_dung"])
    if spec.get("khung"):
        x0, y0, x1, y1 = spec["khung"]
    else:
        xs, ys = [p[0] for p in tat_ca], [p[1] for p in tat_ca]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        mx, my = max(0.25, 0.1 * (x1 - x0)), max(0.25, 0.1 * (y1 - y0))
        x0, x1, y0, y1 = x0 - mx, x1 + mx, y0 - my, y1 + my
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    fig.set_size_inches(spec["rong"], max(2.0, spec["rong"] * (y1 - y0) / max(1e-9, (x1 - x0))))
    return _png(fig), nhan_ve


def ve(spec):
    """spec (đã chuan_spec) → (PNG bytes, nhãn đã vẽ)."""
    return ve_do_thi(spec) if spec["loai"] == "do_thi" else ve_so_do(spec)


# =====================================================================================================
#  E. CỔNG KHỚP BẰNG CODE (bằng chứng 1) · MODEL NHÌN LẠI (bằng chứng 2)
# =====================================================================================================
def kiem_luat(spec, nhan_ve, noi_dung, phuong_an, dap_an, mo_ta):
    """(lỗi cứng, cảnh báo mềm). Lỗi cứng → không được gắn hình. 0 lượt AI."""
    loi, canh_bao = [], []
    van = str(noi_dung or "") + "\n" + str(phuong_an or "")
    co_trong_de = so_trong(van)
    # 1. mọi số ghi trên hình phải có trong đề (chặn bịa số / lộ đáp án)
    for nh in nhan_ve:
        for v in so_tren_nhan(nh):
            if not _co(v, co_trong_de):
                loi.append("Hình ghi số %s không có trong đề (nhãn \"%s\")" % (dinh_dang_so(v), nh))
    # 1b. mốc đề cho tự sinh số: kiểm riêng các mốc / điểm có số gắn nhãn tự động
    if spec["loai"] == "do_thi":
        d = spec["do_thi"]
        deu = {id(t): bool(t["chia_deu"]) for t in (d["truc_x"], d["truc_y"])}
        for t in (d["truc_x"], d["truc_y"]):
            for m in t["cac_moc"]:
                if not m["nhan"] and not _co(m["v"], co_trong_de) and not deu[id(t)]:
                    loi.append("Mốc %s trên trục không có trong đề" % dinh_dang_so(m["v"]))
        for p in d["duong_doi"]:
            for v in (p["x"], p["y"]):
                if abs(v) > 1e-12 and not _co(v, co_trong_de):
                    canh_bao.append("Đường dóng tới giá trị %s chưa thấy trong đề" % dinh_dang_so(v))
        for dg in d["duong"]:
            for p in dg.get("diem", []):
                for v in p:
                    if abs(v) > 1e-12 and not _co(v, co_trong_de):
                        canh_bao.append("Điểm vẽ có toạ độ %s chưa thấy trong đề (có thể suy ra từ dữ kiện)" % dinh_dang_so(v)); break
                else:
                    continue
                break
    # 2. không lộ đáp án
    for v in set(so_tren_nhan(dap_an)):
        if abs(v) not in (0.0, 1.0) and not _co(v, co_trong_de) and any(_co(v, set(so_trong(n))) for n in nhan_ve):
            loi.append("Hình lộ đáp án (số %s)" % dinh_dang_so(v))
    # 3. số trong mô tả phải có trên hình (nhãn / mốc / toạ độ)
    tren_hinh = set()
    for nh in nhan_ve:
        for v in so_tren_nhan(nh): tren_hinh.add(round(v, 9)); tren_hinh.add(round(-v, 9))
    if spec["loai"] == "do_thi":
        d = spec["do_thi"]
        for t in (d["truc_x"], d["truc_y"]):
            for m in t["cac_moc"]: tren_hinh.add(round(m["v"], 9)); tren_hinh.add(round(-m["v"], 9))
            if t["chia_deu"]:
                b = t["chia_deu"]["buoc"]; v = math.ceil(t["min"] / b - 1e-9) * b
                while v <= t["max"] + 1e-9: tren_hinh.add(round(v, 9)); tren_hinh.add(round(-v, 9)); v += b
        for dg in d["duong"]:
            for p in dg.get("diem", []):
                for v in p: tren_hinh.add(round(v, 9)); tren_hinh.add(round(-v, 9))
        for p in d["diem"] + d["duong_doi"]:
            for v in (p["x"], p["y"]): tren_hinh.add(round(v, 9)); tren_hinh.add(round(-v, 9))
    else:
        for e in spec["so_do"]:
            for kh in ("a", "b", "tam", "vt"):
                for v in e.get(kh, []): tren_hinh.add(round(v, 9))
    can = so_can_co_tren_hinh(mo_ta)
    if spec["loai"] == "do_thi":                                     # đồ thị: số trong mô tả phải là mốc / toạ độ / nhãn
        thieu = sorted(v for v in can if not _co(v, tren_hinh))
        if thieu:
            loi.append("Mô tả hình có số %s mà hình chưa thể hiện" % ", ".join(dinh_dang_so(v) for v in thieu[:8]))
    else:                                                            # sơ đồ: số trong mô tả là số liệu (kích thước, độ lớn…) → phải ghi thành nhãn
        thieu = sorted(v for v in can if not _co(v, tren_hinh))
        if thieu:
            canh_bao.append("Mô tả hình có số %s chưa thấy ghi thành nhãn trên sơ đồ" % ", ".join(dinh_dang_so(v) for v in thieu[:8]))
    return loi, list(dict.fromkeys(canh_bao))[:6]


GIAI_THICH_SPEC = r"""
Bạn trả về MỘT đối tượng JSON (không văn bản khác) mô tả hình cần vẽ. Chương trình sẽ vẽ bằng code; bạn KHÔNG vẽ ảnh.
{
 "du_du_lieu": true,            // false nếu đề + mô tả KHÔNG đủ dữ kiện để vẽ đúng (khi đó thêm "ly_do_thieu": "…" và dừng)
 "loai": "do_thi" | "so_do",
 "rong": 6, "cao": 4,           // kích thước ảnh (inch)
 // ---- loai = do_thi ----
 "do_thi": {
   "truc_x": {"nhan": "t (s)", "min": 0, "max": 10, "cac_moc": [{"v": 4}], "chia_deu": null},      // chia_deu: {"buoc": 2} → ghi số đều trên trục
   "truc_y": {"nhan": "v (m/s)", "min": 0, "max": 12, "cac_moc": [{"v": 6}], "chia_deu": null},
   "duong": [ {"kieu": "gap_khuc", "diem": [[0,2],[4,6],[10,6]], "net": "lien", "nhan": "", "vi_tri_nhan": null},
              {"kieu": "cong_muot", "diem": [[0,0],[2,3],[4,4]]},
              {"kieu": "ham", "bieu_thuc": "2*sin(pi*x/2)", "tu": 0, "den": 4} ],
   "diem": [{"x": 4, "y": 6, "nhan": "M", "rong": false}],
   "duong_doi": [{"x": 4, "y": 6}],            // đường nét đứt dóng từ điểm xuống hai trục
   "luoi": false
 },
 // ---- loai = so_do (toạ độ tự do, y hướng lên; 1 đơn vị ≈ 1 ô) ----
 "so_do": [ {"k": "<loại>", ...}, ... ],
 "khung": [xmin, ymin, xmax, ymax]            // tuỳ chọn
}
Các phần tử của so_do (k): doan{a,b} · gap_khuc{diem} · da_giac{diem,to} · cong_muot{diem} · mui_ten{a,b,nhan} · chu_nhat{tam,rong,cao,goc,nhan,to}
 · tron{tam,r,dac,nhan} · cung{tam,r,g1,g2 (độ),nhan} · lo_xo{a,b,so_vong} · cuon_day{a,b,so_vong} · dien_tro{a,b,nhan} · bien_tro{a,b,nhan}
 · nguon{a,b,nhan} (bản dài = cực dương, ở phía a) · tu_dien{a,b,nhan} · den{tam,r,nhan} · dong_ho{tam,r,chu:"A"|"V"|"G"} · khoa{a,b,nhan}
 · dat{a,b} (mặt đất/ giá đỡ có gạch chéo) · chu{vt,noi_dung}.   Mọi phần tử có thể thêm "net":"dut", "day":số, "vi_tri_nhan":[x,y].
Nhãn có thể dùng mathtext: "$\\vec{F}$", "$\\alpha$", "$R_1$", "$30^\\circ$".
QUY TẮC BẮT BUỘC:
 1. Vẽ ĐÚNG và ĐỦ những gì đề + mô tả nói; KHÔNG thêm chi tiết đề không nêu; số liệu trên hình lấy NGUYÊN từ đề.
 2. TUYỆT ĐỐI không ghi đáp án, không ghi đại lượng đề yêu cầu tính (dùng kí hiệu hoặc dấu "?" nếu đề có dùng).
 3. Đồ thị: mốc trên trục chỉ là các giá trị đề cho; đường thẳng/gấp khúc/cong đúng dạng đề mô tả (đi qua gốc? song song trục? dốc lên hay xuống? đoạn nét đứt?).
 4. Mạch điện: đúng cách mắc nối tiếp / song song, đúng vị trí ampe kế (mắc nối tiếp) và vôn kế (mắc song song), đúng cực nguồn, đúng khoá.
 5. Hình lực / véc-tơ: mũi tên đúng phương, chiều, điểm đặt; độ dài tương xứng độ lớn nếu đề cho số liệu.
 6. Nếu đề có nhiều hình nhỏ (a), (b), (c)… vẽ TẤT CẢ trong một ảnh, đặt cạnh nhau, có nhãn (a), (b)…
"""


def _loi_ve_hinh_phan_hoi(spec_loi):
    return "\n".join("- " + l for l in spec_loi)


def tao_spec(x, mo_ta, cac_model, phan_hoi=""):
    """Gemini → spec (dict thô). Chữ kí x: dict có noi_dung, phuong_an."""
    van = "ĐỀ (nội dung):\n%s\n\nPHƯƠNG ÁN:\n%s\n\nMÔ TẢ HÌNH TRONG ĐỀ:\n%s\n" % (x["noi_dung"], x.get("phuong_an", ""), "\n".join(mo_ta) or "(không có – chỉ dựa vào nội dung đề)")
    p = ("Bạn là giáo viên Vật lí THPT, vẽ hình minh hoạ cho đề thi. Hãy lập BẢN MÔ TẢ DỮ LIỆU của hình sao cho KHỚP TUYỆT ĐỐI với đề.\n" + GIAI_THICH_SPEC +
         "\n" + van + ("\nLẦN VẼ TRƯỚC BỊ LỖI, SỬA HẾT CÁC LỖI SAU:\n" + phan_hoi + "\n" if phan_hoi else ""))
    return _json(GOI(p, (), cac_model))


def nhin_lai(x, mo_ta, png, cac_model):
    """Bằng chứng 2: model NHÌN hình vừa vẽ, đối chiếu với đề. Trả {'dat': bool, 'loi': [..]}."""
    p = ("Bạn là người kiểm tra hình minh hoạ đề thi Vật lí. Đối chiếu ẢNH với ĐỀ và MÔ TẢ HÌNH, từng chi tiết: số liệu, đơn vị, chiều mũi tên, "
         "cách mắc mạch, vị trí điểm, dạng đồ thị (đi qua gốc? tăng/giảm? nét đứt?), nhãn trục, mốc.\n"
         "Trả JSON: {\"khop\": true|false, \"sai_lech\": [\"…\"], \"thua\": [\"chi tiết hình có mà đề không nêu\"], \"thieu\": [\"chi tiết đề nêu mà hình thiếu\"], "
         "\"lo_dap_an\": true|false}.  khop=true CHỈ KHI sai_lech, thua, thieu đều rỗng và hình không ghi đáp án mà đề yêu cầu tính. Không chắc → khop=false.\n\n"
         "ĐỀ:\n%s\n\nPHƯƠNG ÁN:\n%s\n\nMÔ TẢ HÌNH:\n%s\n" % (x["noi_dung"], x.get("phuong_an", ""), "\n".join(mo_ta) or "(không có)"))
    j = _json(GOI(p, (png,), cac_model))
    if not j:
        return {"dat": False, "loi": ["model không trả kết quả đọc được"]}
    loi = [str(v) for k in ("sai_lech", "thua", "thieu") for v in (j.get(k) or [])]
    if j.get("lo_dap_an"): loi.append("hình lộ đáp án")
    return {"dat": bool(j.get("khop")) and not loi, "loi": loi[:8]}


def kiem_anh_cu(x, mo_ta, anh_cu, cac_model):
    """Hình đang gắn có khớp đề không. Trả ('khop'|'khong_khop'|'khong_chac', lí do)."""
    if not anh_cu:
        return "khong_chac", "không tải được ảnh đang gắn"
    p = ("Bạn là người kiểm tra hình minh hoạ đề thi Vật lí. Các ảnh đính kèm là hình đang GẮN vào câu hỏi dưới đây. Đối chiếu từng chi tiết "
         "(số liệu, đơn vị, chiều véc-tơ, cách mắc mạch, vị trí điểm, dạng đồ thị, nhãn). Trả JSON: "
         "{\"ket_luan\": \"khop\"|\"khong_khop\"|\"khong_chac\", \"ly_do\": \"…ngắn gọn, nêu chi tiết lệch\"}.\n"
         "khop: mọi chi tiết đề nêu đều thể hiện đúng trên ảnh và ảnh không có chi tiết mâu thuẫn.  khong_khop: có ít nhất một chi tiết SAI hoặc ảnh "
         "thuộc câu khác.  khong_chac: ảnh mờ / thiếu / không đủ căn cứ để kết luận.\n\n"
         "ĐỀ:\n%s\n\nPHƯƠNG ÁN:\n%s\n\nMÔ TẢ HÌNH:\n%s\n" % (x["noi_dung"], x.get("phuong_an", ""), "\n".join(mo_ta) or "(không có – chỉ dựa vào nội dung đề)"))
    j = _json(GOI(p, anh_cu, cac_model))
    if not j or j.get("ket_luan") not in ("khop", "khong_khop", "khong_chac"):
        return "khong_chac", "model không kết luận được"
    return j["ket_luan"], str(j.get("ly_do", ""))[:200]


def ve_va_kiem(x, mo_ta, cac_model, so_lan=None):
    """Vòng: Gemini lập spec → code kiểm + vẽ → model nhìn lại; lỗi thì vẽ lại kèm lỗi. Trả (png|None, ghi_chú, thieu_du_lieu: bool)."""
    so_lan = _so_nguyen("VE_LAI_SO_LAN", 2) if so_lan is None else so_lan
    phan_hoi, lich_su = "", []
    for lan in range(1 + so_lan):
        spec_tho = tao_spec(x, mo_ta, cac_model, phan_hoi)
        if not spec_tho:
            lich_su.append("lần %d: model không trả JSON" % (lan + 1)); phan_hoi = "Hãy trả đúng một đối tượng JSON theo mẫu."; continue
        if spec_tho.get("du_du_lieu") is False:
            return None, "thiếu dữ liệu để vẽ: %s" % str(spec_tho.get("ly_do_thieu", ""))[:200], True
        try:
            spec = chuan_spec(spec_tho)
            png, nhan_ve = ve(spec)
        except (ValueError, KeyError, TypeError) as e:
            lich_su.append("lần %d: %s" % (lan + 1, str(e)[:120])); phan_hoi = "Bản mô tả không vẽ được: %s" % str(e)[:200]; continue
        loi, canh_bao = kiem_luat(spec, nhan_ve, x["noi_dung"], x.get("phuong_an", ""), x.get("dap_an", ""), mo_ta)
        if loi:
            lich_su.append("lần %d: luật code: %s" % (lan + 1, "; ".join(loi)[:160])); phan_hoi = _loi_ve_hinh_phan_hoi(loi); continue
        nl = nhin_lai(x, mo_ta, png, cac_model)
        if not nl["dat"]:
            lich_su.append("lần %d: nhìn lại: %s" % (lan + 1, "; ".join(nl["loi"])[:160])); phan_hoi = _loi_ve_hinh_phan_hoi(nl["loi"]); continue
        ghi = "đạt ở lần vẽ %d (luật code + nhìn lại)" % (lan + 1) + ("; lưu ý: " + "; ".join(canh_bao) if canh_bao else "")
        return png, ghi, False
    return None, "vẽ %d lần vẫn chưa khớp (%s)" % (1 + so_lan, " | ".join(lich_su)[:400]), False


# =====================================================================================================
#  F. TẢI ẢNH ĐANG GẮN · ĐẨY ẢNH MỚI LÊN REPO
# =====================================================================================================
def tach_link(cell):
    return [u for u in re.split(r"[\s,;|]+", str(cell or "")) if u.lower().startswith("http")]


def _url_tai(u):
    m = re.match(r"https?://github\.com/([^/]+/[^/]+)/blob/(.+)$", u)
    if m: return "https://raw.githubusercontent.com/%s/%s" % (m.group(1), m.group(2))
    return u


def tai_anh(cell, drive=None, toi_da=4):
    """Tải các ảnh trong ô Link ảnh (GitHub raw / blob, Drive). Lỗi từng ảnh thì bỏ qua. Trả list bytes."""
    ra = []
    for u in tach_link(cell)[:toi_da]:
        try:
            m = re.search(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:[^#]*&)?id=)([\w-]+)", u)
            if m and drive is not None:
                b = drive.files().get_media(fileId=m.group(1)).execute()
            else:
                rq = urllib.request.Request(_url_tai(u), headers={"User-Agent": "vatli-xuong"})
                with urllib.request.urlopen(rq, timeout=40) as r:
                    b = r.read(8_000_001)
            if b and len(b) <= 8_000_000 and _mime(b):
                ra.append(b)
        except Exception as e:                          # phần phụ: một ảnh lỗi không làm hỏng câu
            print("    Không tải được ảnh (%s): %s" % (u[:60], str(e)[:80]), flush=True)
    return ra


def _gh(method, url, tok, data=None):
    rq = urllib.request.Request(url, data=json.dumps(data).encode("utf-8") if data is not None else None, method=method,
                                headers={"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json", "User-Agent": "vatli-xuong",
                                         "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(rq, timeout=60) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def day_len_repo(png, ma_cau):
    """Đẩy PNG vào images/ve_lai/<mã>_<băm>.png bằng GitHub Contents API. Trả link raw hoặc None (không có token / lỗi)."""
    tok = os.environ.get("GITHUB_TOKEN", "").strip()
    if not tok:
        return None
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip() or REPO_MAC_DINH
    nhanh = os.environ.get("VE_LAI_NHANH", "").strip() or "main"
    ten = "%s_%s.png" % (re.sub(r"[^A-Za-z0-9_-]", "_", str(ma_cau))[:60] or "cau", hashlib.sha1(png).hexdigest()[:8])
    duong = "%s/%s" % (THU_MUC_ANH, ten)
    api = "https://api.github.com/repos/%s/contents/%s" % (repo, urllib.parse.quote(duong))
    body = {"message": "ve_lai_hinh: hình cho câu %s" % ma_cau, "content": base64.b64encode(png).decode("ascii"), "branch": nhanh}
    try:
        try:
            _gh("PUT", api, tok, body)
        except urllib.error.HTTPError as e:
            if e.code not in (409, 422): raise
            cu = _gh("GET", api + "?ref=" + urllib.parse.quote(nhanh), tok)       # đã có tệp cùng tên → ghi đè theo sha
            body["sha"] = cu.get("sha", "")
            _gh("PUT", api, tok, body)
    except (urllib.error.URLError, ValueError, OSError) as e:
        print("    Không đẩy được ảnh lên repo: %s" % str(e)[:120], flush=True)
        return None
    return "https://raw.githubusercontent.com/%s/%s/%s" % (repo, nhanh, urllib.parse.quote(duong))


# =====================================================================================================
#  G. XỬ LÍ MỘT CÂU · NỐI VÀO duyet_cau · CHẠY ĐỘC LẬP TOÀN KHO
# =====================================================================================================
def ngay_nay():
    return dt.datetime.now(TZ).strftime("%d/%m")


def xu_li_cau(x, drive, cac_model, chi_bao=False):
    """x: {ma, noi_dung, phuong_an, dap_an, link_anh}. Trả dict:
       hanh_dong: bo_qua | khop | da_ve_lai | go_hinh | giu_cu | khong_ve_duoc | khong_lam_gi | se_ve_lai (chỉ báo)
       link_moi: chuỗi mới cho ô Link ảnh (None = không đổi) · ghi: chú thích cho cột Kiểm tra (có dấu "[hình …")."""
    mo_ta = mo_ta_hinh(x["noi_dung"], x.get("phuong_an", ""))
    link_cu = str(x.get("link_anh") or "").strip()
    if not can_xu_li(x["noi_dung"], x.get("phuong_an", ""), bool(tach_link(link_cu))):
        return {"hanh_dong": "bo_qua", "link_moi": None, "ghi": ""}
    ngay = ngay_nay()
    anh_cu = tai_anh(link_cu, drive) if tach_link(link_cu) else []
    if tach_link(link_cu):
        kl, ly = kiem_anh_cu(x, mo_ta, anh_cu, cac_model)
    else:
        kl, ly = "khong_co", ""
    if kl == "khop":
        return {"hanh_dong": "khop", "link_moi": None, "ghi": "[hình %s: hình đang gắn khớp đề]" % ngay}
    if not chi_bao and not os.environ.get("GITHUB_TOKEN", "").strip():
        print("    ⚠️ Thiếu GITHUB_TOKEN → không đẩy được hình mới, không đổi gì (cần permissions: contents: write).", flush=True)
        return {"hanh_dong": "khong_lam_gi", "link_moi": None, "ghi": ""}
    png, ghi, thieu = ve_va_kiem(x, mo_ta, cac_model)
    tinh_trang = {"khong_khop": "hình cũ KHÔNG khớp đề (%s)" % ly, "khong_chac": "hình cũ không kiểm chứng được (%s)" % ly, "khong_co": "chưa có hình"}[kl]
    if png:
        if chi_bao:
            os.makedirs("ve_lai_xem_thu", exist_ok=True)
            tep = os.path.join("ve_lai_xem_thu", re.sub(r"[^A-Za-z0-9_-]", "_", str(x["ma"])) + ".png")
            with open(tep, "wb") as f: f.write(png)
            return {"hanh_dong": "se_ve_lai", "link_moi": None, "ghi": "[hình %s: CHẠY THỬ – %s; hình mới %s, đã lưu %s]" % (ngay, tinh_trang, ghi, tep)}
        link = day_len_repo(png, x["ma"])
        if not link:
            return {"hanh_dong": "khong_lam_gi", "link_moi": None, "ghi": ""}
        return {"hanh_dong": "da_ve_lai", "link_moi": link,
                "ghi": "[hình %s: đã vẽ lại – %s; hình mới %s%s]" % (ngay, tinh_trang, ghi, ("; link hình cũ: " + link_cu) if link_cu else "")}
    if kl == "khong_khop" and not chi_bao:
        return {"hanh_dong": "go_hinh", "link_moi": "",
                "ghi": "[hình %s: đã GỠ hình không khớp đề (%s); chưa vẽ lại được: %s; link hình cũ: %s]" % (ngay, ly, ghi, link_cu)}
    if kl == "khong_chac":
        return {"hanh_dong": "giu_cu", "link_moi": None, "ghi": "[hình %s: giữ hình cũ (%s) vì %s]" % (ngay, ly, ghi)}
    return {"hanh_dong": "khong_ve_duoc", "link_moi": None, "ghi": "[hình %s: %s; chưa vẽ lại được: %s]" % (ngay, tinh_trang, ghi)}


def xu_li_ds(ds, drive, cac_model, chi_bao=None):
    """Nối vào duyet_cau: ds = các câu của một file (dict của duyet_cau). Gắn kết quả vào x (ghi_chu, nghi_van, sua["link_anh"]).
    HetHan được ném lên cho nơi gọi xử lí. Trả số câu đã đổi hình."""
    chi_bao = _cong("VE_LAI_CHI_BAO") if chi_bao is None else chi_bao
    toi_da, lai = _so_nguyen("VE_LAI_TOI_DA_CAU", 30, 1), _cong("VE_LAI_LAI_TAT_CA")
    dem = doi = 0
    for x in ds:
        if x.get("loi_nang") or (DAU_HINH in str(x.get("kiem_tra_cu", "")) and not lai):
            continue
        if not can_xu_li(x["noi_dung"], x.get("phuong_an", ""), bool(tach_link(x.get("link_anh")))):
            continue
        if dem >= toi_da:
            print("  Vẽ lại hình: đủ %d câu cho lượt này, phần còn lại để lượt sau." % toi_da, flush=True); break
        dem += 1
        kq = xu_li_cau(x, drive, cac_model, chi_bao)
        if kq["hanh_dong"] in ("bo_qua", "khong_lam_gi"):
            continue
        if kq["ghi"]: x["ghi_chu"].append(kq["ghi"])
        if kq["link_moi"] is not None:
            x["sua"]["link_anh"] = kq["link_moi"]; x["link_anh"] = kq["link_moi"]; doi += 1
            if kq["hanh_dong"] == "da_ve_lai": x["hinh_ve_lai"] = True                 # hình do máy vẽ từ mô tả → tầng 6 "nhìn hình" không còn là bằng chứng độc lập
            if kq["hanh_dong"] == "go_hinh": x["nghi_van"].append("Hình gắn không khớp đề đã bị gỡ, chưa vẽ lại được – cần người xem")
    print("  Vẽ lại hình: xử lí %d câu, đổi hình %d câu." % (dem, doi), flush=True)
    return doi


def _a1(cot, dong):
    s = ""
    while cot:
        cot, r = divmod(cot - 1, 26)
        s = chr(65 + r) + s
    return "%s%d" % (s, dong)


def main():
    """Quét cả kho: python ve_lai_hinh.py (cần VE_LAI_HINH=true)."""
    if not bat():
        print("VE_LAI_HINH chưa bật (đặt VE_LAI_HINH=true) – không làm gì."); return
    import doc_de as X
    gc, drive, sa = X.ket_noi()
    print("Tài khoản dịch vụ:", sa, flush=True)
    kho = gc.open_by_key(X.ID_KHO_CHUNG)
    tab = kho.worksheet(TAB_NH)
    d = tab.get_all_values()
    td = [t.strip() for t in d[0]]
    c = {t: td.index(t) for t in ("Mã câu", "Nội dung", "Phương án", "Đáp án", "Kiểm tra", "Trạng thái duyệt") if t in td}
    c_anh = next((i for i, t in enumerate(td) if t.lower() == "link ảnh"), None)
    if c_anh is None or "Mã câu" not in c or "Nội dung" not in c:
        print("Thiếu cột Mã câu / Nội dung / Link ảnh – dừng."); return
    cac_model = [m for m in ([os.environ.get("VE_LAI_MODEL", "").strip()] or []) if m] or list(X.doc_cau_hinh(kho))
    chi_bao, lai, ca_loai = _cong("VE_LAI_CHI_BAO"), _cong("VE_LAI_LAI_TAT_CA"), _cong("VE_LAI_CA_LOAI")
    toi_da = _so_nguyen("VE_LAI_TOI_DA_CAU", 30, 1)
    gio_max = float(os.environ.get("THOI_GIAN_TOI_DA_PHUT", "150") or 150) * 60
    t0 = time.time()
    ung = []
    for i, r in enumerate(d[1:], start=2):
        r = r + [""] * (len(td) - len(r))
        tt = r[c["Trạng thái duyệt"]].strip() if "Trạng thái duyệt" in c else ""
        if tt == "Loại" and not ca_loai: continue
        if "Kiểm tra" in c and DAU_HINH in r[c["Kiểm tra"]] and not lai: continue
        link = r[c_anh].strip()
        if not can_xu_li(r[c["Nội dung"]], r[c["Phương án"]] if "Phương án" in c else "", bool(tach_link(link))): continue
        ung.append((i, r, tt))
    print("Có %d câu cần kiểm hình (xử lí tối đa %d câu lượt này)%s." % (len(ung), toi_da, " – CHẠY THỬ" if chi_bao else ""), flush=True)
    thong_ke = {}
    cap, xong = [], 0
    for i, r, tt in ung[:toi_da]:
        if time.time() - t0 > gio_max - 300:
            print("⏸️ Hết thời gian lượt này.", flush=True); break
        x = {"ma": r[c["Mã câu"]], "noi_dung": r[c["Nội dung"]], "phuong_an": r[c["Phương án"]] if "Phương án" in c else "",
             "dap_an": r[c["Đáp án"]] if "Đáp án" in c else "", "link_anh": r[c_anh]}
        try:
            kq = xu_li_cau(x, drive, cac_model, chi_bao)
        except HetHan as e:
            print("⏸️ Hết hạn mức Gemini – dừng, lượt sau làm tiếp:", str(e)[:120], flush=True); break
        except Exception as e:
            print("  ⚠️ Câu %s lỗi, bỏ qua: %s" % (x["ma"], str(e)[:150]), flush=True); continue
        thong_ke[kq["hanh_dong"]] = thong_ke.get(kq["hanh_dong"], 0) + 1
        print("  %s → %s" % (x["ma"], kq["hanh_dong"]), flush=True)
        if kq["hanh_dong"] in ("bo_qua", "khong_lam_gi") or chi_bao and not kq["ghi"]:
            continue
        xong += 1
        kt_cu = r[c["Kiểm tra"]] if "Kiểm tra" in c else ""
        if not chi_bao and "Kiểm tra" in c:
            cap.append((x["ma"], "Kiểm tra", ((kt_cu + " | ") if kt_cu else "") + kq["ghi"]))
            if kq["link_moi"] is not None: cap.append((x["ma"], "Link ảnh", kq["link_moi"]))
            if kq["hanh_dong"] == "go_hinh" and tt == "AI duyệt" and "Trạng thái duyệt" in c:
                cap.append((x["ma"], "Trạng thái duyệt", "Cần người xem"))
        if len(cap) >= 12:
            _ghi(tab, c, c_anh, cap); cap = []
    if cap: _ghi(tab, c, c_anh, cap)
    print("📊 Vẽ lại hình: %s" % (", ".join("%s %d" % (k, v) for k, v in sorted(thong_ke.items())) or "không có câu nào"), flush=True)


def _ghi(tab, c, c_anh, cap):
    """Ghi theo MÃ CÂU tìm ngay lúc ghi (không dùng số dòng đã nhớ)."""
    ma_cot = tab.col_values(c["Mã câu"] + 1)
    vt = {v.strip(): i + 1 for i, v in enumerate(ma_cot) if i > 0 and v.strip()}
    ds = []
    for ma, ten, gt in cap:
        dong = vt.get(ma)
        if not dong: continue
        cot = c_anh if ten == "Link ảnh" else c[ten]
        ds.append({"range": _a1(cot + 1, dong), "values": [[gt[:45000]]]})
    if ds: tab.batch_update(ds, value_input_option="RAW")


if __name__ == "__main__":
    main()
