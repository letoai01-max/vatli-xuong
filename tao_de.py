"""
tao_de.py – XƯỞNG SOẠN ĐỀ THI (AGENT TỰ CHỦ chuyển từ Apps Script sang Python, chạy trên GitHub Actions)

Làm đúng quy trình agent cũ của Mã.gs, nhưng điều khiển bằng code (không còn giới hạn 6 phút / 8 lượt):
  1. Soạn từng phần I→IV theo Bản đặc tả (có tra Google Search, lỗi thì soạn không tra – như agentSoanPhan)
  2. Giải lại ĐỘC LẬP từng phần (Gemini; Groq làm ý kiến thứ hai nếu có) → câu lệch thì soạn lại (tối đa 2 lần/câu) → xác minh lại riêng câu đó
  3. Kiểm tra cấu trúc + độ dài → câu sai thì soạn lại, phần sai số câu thì soạn lại cả phần
  4. Ghi kết quả (đề dạng phan1..phan4, đúng khóa của Mã.gs) vào file kết quả trên Drive.
     Apps Script nhận → kiểm tra bổ sung (khớp chỉ báo, thực tiễn, theo khối, hình) → tạo hình → ghi Google Docs như cũ.

Đọc gói việc goi_de_<mã>.json do taoDeThiAgent (XuongTaoDe.gs) tạo. Ghi nhật ký từng bước vào trường nhatKy của file kết quả.
"""
import datetime as dt, io, json, os, re, sys, time

import gspread  # noqa: F401  (doc_de cần)
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

import doc_de as X

try:
    import groq_xuong as G
except Exception:                       # không có Groq vẫn chạy bình thường
    G = None

TZ = dt.timezone(dt.timedelta(hours=7))
T0 = time.time()
HAN_PHUT = float(os.environ.get("TD_HAN_PHUT", "75"))      # hạn cứng cho cả lượt chạy (workflow 90 phút)
SAI_SO = 0.02                                              # sai số 2% khi so đáp án số (như AGENT_DE_CFG)
SO_LAN_SOAN_LAI = 2                                        # mỗi câu soạn lại tối đa 2 lần
SO_LAN_CHO_QUOTA = 6                                       # hết hạn mức: chờ 3 phút, thử lại tối đa 6 lần
CHO_QUOTA_GIAY = 180

LENH_LATEX = r"- Dùng công thức LaTeX chuẩn: \\\\frac{tử}{mẫu}, \\\\sqrt{...}, không dùng dấu $ hay $$."
LENH_P4 = (r"- Phần IV trường 'dapAn' là lời giải mỗi bước MỘT DÒNG (ngăn cách bằng \\n, mỗi dòng bắt đầu bằng '- '), "
           r"dòng cuối '=> Đáp số: ... kèm đơn vị'.")
LENH_P4_NGAN = (r"Phần IV 'dapAn' mỗi bước một dòng (ngăn cách bằng \\n, mỗi dòng bắt đầu bằng '- ', "
                r"dòng cuối '=> Đáp số: ...').")
SYS_GIAI = ("Bạn là học sinh giỏi Vật lí. Hãy tự giải ĐỘC LẬP từng câu một cách cẩn thận "
            "(bạn không biết đáp án của người ra đề). Chỉ trả về JSON.")

# ---- trạng thái làm việc (giống st của agent cũ) ----
GOI, ST, DE = {}, {}, {"phan1": [], "phan2": [], "phan3": [], "phan4": []}
TON_DONG = {"p1": [], "p2": [], "p3": [], "p4": []}
DA_XM = {"p1": False, "p2": False, "p3": False, "p4": False}
SO_LAN = {}                     # "phan-câu" -> số lần đã soạn lại
CAC_MODEL, MODEL_CUOI = [], ""
NK = None
KHONG_TIM_KIEM = []             # các phần phải soạn không có Google Search


# ═════════════ Drive / nhật ký ═════════════
def ket_noi():
    import google.auth
    cred, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(cred), build("drive", "v3", credentials=cred, cache_discovery=False)


def doc_tep(drive, fid):
    buf = io.BytesIO()
    tai = MediaIoBaseDownload(buf, drive.files().get_media(fileId=fid))
    xong = False
    while not xong:
        _, xong = tai.next_chunk()
    return json.loads(buf.getvalue().decode("utf-8") or "{}")


def ghi_tep(drive, fid, du_lieu):
    media = MediaIoBaseUpload(io.BytesIO(json.dumps(du_lieu, ensure_ascii=False).encode("utf-8")), mimetype="text/plain")
    drive.files().update(fileId=fid, media_body=media).execute()


def bay_gio():
    return dt.datetime.now(TZ).isoformat()


def het_gio(du_tru=0):
    return (time.time() - T0) > HAN_PHUT * 60 - du_tru


class NhatKy:
    def __init__(self, drive, kq_id):
        self.drive, self.kq_id, self.ds, self.lan_cuoi = drive, kq_id, [], 0.0

    def ghi(self, buoc, chi_tiet="", ep=False):
        self.ds.append({"luc": bay_gio(), "buoc": str(buoc)[:80], "chiTiet": str(chi_tiet)[:900]})
        print("• %s: %s" % (buoc, str(chi_tiet)[:300]), flush=True)
        if ep or time.time() - self.lan_cuoi > 20:
            self.dong_bo()

    def dong_bo(self):
        try:
            ghi_tep(self.drive, self.kq_id, {"trangThai": "DANG_LAM", "cheDo": "agent", "luc": bay_gio(),
                                             "nhatKy": self.ds[-150:]})
            self.lan_cuoi = time.time()
        except Exception as e:
            print("⚠️ Không ghi được tiến độ: %s" % str(e)[:120], flush=True)


# ═════════════ gọi Gemini ═════════════
def lay_text(data):
    cand = (data.get("candidates") or [{}])[0]
    return "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []) if not p.get("thought"))


def _sach(v):
    if isinstance(v, str):
        return v.replace("\x0c", "\\f").replace("\x08", "\\b")
    if isinstance(v, list):
        return [_sach(x) for x in v]
    if isinstance(v, dict):
        return {k: _sach(x) for k, x in v.items()}
    return v


def doc_json(text):
    s = re.sub(r"```json|```", "", str(text or "")).strip()
    vt = [x for x in (s.find("{"), s.find("[")) if x != -1]
    if not vt:
        raise ValueError("không thấy JSON trong câu trả lời")
    i = min(vt)
    j = s.rfind("}" if s[i] == "{" else "]")
    if j <= i:
        raise ValueError("JSON bị cắt dở")
    s = s[i:j + 1]
    try:
        return _sach(json.loads(s))
    except ValueError:
        return _sach(json.loads(re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", s)))


def chay_co_cho(f, *a):
    """Hết hạn mức Gemini → chờ rồi thử lại (thay cơ chế hoàn lượt + hẹn 3–8 phút của ChanVongLap)."""
    for lan in range(SO_LAN_CHO_QUOTA + 1):
        try:
            return f(*a)
        except X.HetHanMuc as e:
            if lan >= SO_LAN_CHO_QUOTA or het_gio(CHO_QUOTA_GIAY + 60):
                raise
            NK.ghi("Chờ hạn mức Gemini", "%s – chờ %d giây rồi thử lại (lần %d/%d)" % (str(e)[:150], CHO_QUOTA_GIAY, lan + 1, SO_LAN_CHO_QUOTA), ep=True)
            time.sleep(CHO_QUOTA_GIAY)
            X.TRANG_THAI_KHOA["het"].clear()


def goi_ai(prompt, he, web=False):
    """Tương đương callGemini(prompt, web, systemInstruction) của Mã.gs; trả về JSON đã đọc."""
    global MODEL_CUOI
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
               "generationConfig": {"temperature": 0.2, "maxOutputTokens": 65536}}
    if he:
        payload["systemInstruction"] = {"parts": [{"text": he}]}
    if web:
        payload["tools"] = [{"googleSearch": {}}]               # Search không đi cùng responseMimeType=json
    else:
        payload["generationConfig"]["responseMimeType"] = "application/json"
    data, MODEL_CUOI = chay_co_cho(X.goi_gemini, payload, CAC_MODEL)
    return doc_json(lay_text(data))


# ═════════════ tiện ích đáp án ═════════════
def lay_so(s):
    m = re.search(r"[-+]?\d+(?:[.,]\d+)?", str("" if s is None else s))
    return float(m.group(0).replace(",", ".")) if m else float("nan")


def so_phan4(loi_giai):
    s = str(loi_giai or "")
    i = s.lower().rfind("đáp số")
    if i >= 0:
        return lay_so(s[i + 6:])
    tc = re.findall(r"[-+]?\d+(?:[.,]\d+)?", s)
    return float(tc[-1].replace(",", ".")) if tc else float("nan")


def gan_bang(a, b):
    if a != a or b != b:
        return None
    if b == 0:
        return abs(a) <= 0.01
    return abs(a - b) <= SAI_SO * abs(b)


def tach_dung_sai(s):
    kq = {}
    for m in re.finditer(r"([a-d])\)\s*(Đúng|Sai|Đ|S)(?![A-Za-zÀ-ỹ])", str(s or ""), re.I):
        kq[m.group(1).lower()] = "Đ" if m.group(2).upper()[0] == "Đ" else "S"
    return kq


def so_khop(p, da_soan, da_giai):
    """True/False/None (None = chưa đủ cơ sở kết luận) – đúng như agentXacMinhDapAn."""
    if p == 1:
        a = (re.findall(r"[ABCD]", str(da_soan or "").upper()) or [""])[0]
        b = (re.findall(r"[ABCD]", str(da_giai or "").upper()) or [""])[0]
        return (a == b) if (a and b) else None
    if p == 2:
        a, b = tach_dung_sai(da_soan), tach_dung_sai(da_giai)
        if len(a) == 4 and len(b) == 4:
            return all(a[k] == b[k] for k in "abcd")
        return None
    if p == 3:
        return gan_bang(lay_so(da_giai), lay_so(da_soan))
    return gan_bang(lay_so(da_giai), so_phan4(da_soan))


def mo_ta_hinh(h):
    """Mô tả bảng/đồ thị/hình bằng chữ cho AI giải lại (như moTaHinhChoAI)."""
    try:
        if isinstance(h, str):
            s = re.sub(r"```json|```", "", h).strip()
            if not s.startswith(("{", "[")):
                return ""
            h = json.loads(s)
        if isinstance(h, list):
            h = h[0] if h else None
        if not isinstance(h, dict):
            return ""
        dong = h.get("dong") or h.get("rows")
        if isinstance(dong, list) and dong:
            td = h.get("tieuDeCot")
            hang = ([td] if isinstance(td, list) else []) + [r for r in dong if isinstance(r, list)]
            return "\n[Bảng kèm theo] " + " ; ".join(" | ".join(str(x) for x in r) for r in hang)
        ds = h.get("duLieu") or h.get("series")
        if isinstance(ds, list) and ds:
            ph = []
            for s in ds:
                if not isinstance(s, dict):
                    continue
                pts = s.get("diem") or s.get("data") or s.get("points") or []
                tx = ", ".join("(%s; %s)" % (p[0], p[1]) if isinstance(p, list) and len(p) > 1 else
                               "(%s; %s)" % (p.get("x"), p.get("y")) if isinstance(p, dict) else "" for p in pts)
                ph.append((s.get("ten") + ": " if s.get("ten") else "") + tx)
            return "\n[Đồ thị kèm theo, trục hoành: %s, trục tung: %s] %s" % (
                h.get("nhanTrucX", ""), h.get("nhanTrucY", ""), " ; ".join(ph))
        return "\n[Hình kèm theo] " + str(h.get("moTa") or h.get("chuThich") or "")
    except Exception:
        return ""


# ═════════════ chỉ báo hạt nhân (sắp xếp + gắn mã) ═════════════
def lay_ma(s):
    m = re.search(r"CB\d+", str(s or ""), re.I)
    return m.group(0).upper() if m else ""


def la_hoan_vi(a, b):
    return len(a) == len(b) and all(a) and len(set(a)) == len(a) and sorted(a) == sorted(b)


def sap_xep_phan(mang, p, ds_ma):
    if not ds_ma or not isinstance(mang, list):
        return mang
    kv = ds_ma.get("p%d" % p) or []
    if len(kv) != len(mang):
        return mang
    if p == 2:
        def ma_dau(c):
            y = c.get("maChiBaoY") if isinstance(c, dict) else None
            return lay_ma(y[0]) if isinstance(y, list) and y else ""
        md, kd = [ma_dau(c) for c in mang], [((n or [""])[0] or "") for n in kv]
        if la_hoan_vi(md, kd):
            mang = [mang[md.index(m)] for m in kd]
        for i, c in enumerate(mang):
            if isinstance(c, dict) and not any(lay_ma(x) for x in (c.get("maChiBaoY") or [])):
                c["maChiBaoY"] = list(kv[i] or [])
        return mang
    mh = [lay_ma(c.get("maChiBao")) if isinstance(c, dict) else "" for c in mang]
    if la_hoan_vi(mh, kv):
        mang = [mang[mh.index(m)] for m in kv]
    for i, c in enumerate(mang):
        if isinstance(c, dict) and not lay_ma(c.get("maChiBao")) and kv[i]:
            c["maChiBao"] = kv[i]
    return mang


def gan_ma_mot_cau(cau, p, so):
    ds_ma = ST.get("dsMa")
    if not ds_ma or not isinstance(cau, dict):
        return cau
    kv = (ds_ma.get("p%d" % p) or [])
    kv = kv[so - 1] if 0 < so <= len(kv) else ([] if p == 2 else "")
    if p == 2:
        if kv:
            cau["maChiBaoY"] = list(kv)
    elif kv:
        cau["maChiBao"] = kv
    return cau


# ═════════════ kiểm tra cấu trúc / độ dài (port kiemTraDeThi, kiemTraDoDaiDe) ═════════════
def rong(v):
    return v is None or str(v).strip() == ""


def kiem_tra_de(de, yc):
    loi = []
    p = {i: (de.get("phan%d" % i) if isinstance(de.get("phan%d" % i), list) else []) for i in (1, 2, 3, 4)}
    for i in (1, 2, 3, 4):
        if len(p[i]) != yc["p%d" % i]:
            loi.append("Phần %d đang có %d câu, Bản đặc tả yêu cầu ĐÚNG %d câu." % (i, len(p[i]), yc["p%d" % i]))
    for i, c in enumerate(p[1]):
        if rong(c.get("cauHoi")): loi.append("Phần 1 câu %d: thiếu nội dung câu hỏi." % (i + 1))
        for k in "ABCD":
            if rong(c.get(k)): loi.append("Phần 1 câu %d: thiếu phương án %s." % (i + 1, k))
        if not re.fullmatch(r"[ABCD]", str(c.get("dapAn") or "").strip().upper()):
            loi.append("Phần 1 câu %d: đáp án phải là đúng một chữ A, B, C hoặc D." % (i + 1))
    for i, c in enumerate(p[2]):
        if rong(c.get("cauHoi")): loi.append("Phần 2 câu %d: thiếu nội dung dẫn." % (i + 1))
        for k in "ABCD":
            if rong(c.get(k)): loi.append("Phần 2 câu %d: thiếu ý %s)." % (i + 1, k.lower()))
        if len(re.findall(r"[a-d]\)\s*(?:Đúng|Sai|Đ|S)(?![A-Za-zÀ-ỹ])", str(c.get("dapAn") or ""), re.I)) != 4:
            loi.append('Phần 2 câu %d: đáp án phải đủ 4 ý dạng "a) Đ, b) S, c) Đ, d) S".' % (i + 1))
    for i, c in enumerate(p[3]):
        if rong(c.get("cauHoi")): loi.append("Phần 3 câu %d: thiếu nội dung câu hỏi." % (i + 1))
        da = str("" if c.get("dapAn") is None else c.get("dapAn")).strip()
        if not da or lay_so(da) != lay_so(da) or not re.fullmatch(r"[-+]?[\d.,\s]+", da):
            loi.append('Phần 3 câu %d: đáp án phải là một con số (VD: 12.5), hiện là "%s".' % (i + 1, da))
    for i, c in enumerate(p[4]):
        if rong(c.get("cauHoi")): loi.append("Phần 4 câu %d: thiếu đề bài." % (i + 1))
        dong = [s for s in re.split(r"\r?\n|\\n(?![a-zA-Z])", str(c.get("dapAn") or "")) if s.strip()]
        if len(dong) < 2:
            loi.append('Phần 4 câu %d: lời giải phải chia thành nhiều bước, mỗi bước một dòng (bắt đầu bằng "- "), dòng cuối "=> Đáp số: ...".' % (i + 1))
    return loi


def lam_sach(raw, la_lua_chon):
    t = str("" if raw is None else raw).replace("\t", " ")
    t = re.sub(r"(?:Chỉ\s*báo\s*)?\[\s*CB\d+\s*\]\s*(?:\([^)]*\))?\s*[:.\-]?\s*", "", t, flags=re.I)
    t = re.sub(r"\[[^\[\]]*(?:CHỦ\s*ĐỀ|Bài\s*\d+|Chương\s*\d+)[^\[\]]*\]\s*[-:.]?\s*", "", t, flags=re.I)
    t = re.sub(r"\(\s*Mức\s*(?:biet|hieu|vanDung|biết|hiểu|vận dụng)\s*\)\s*[-:.]?\s*", "", t, flags=re.I)
    t = re.sub(r"^\s*(?:[A-Da-d]\s*[.)]\s+)+", "", t) if la_lua_chon else re.sub(r"^\s*(?:Câu\s*\d+\s*[:.)]\s*)+", "", t, flags=re.I)
    return t.strip()


def kiem_tra_do_dai(de):
    g = (GOI.get("quyDinh") or {}).get("gioiHan") or {"p1CauHoi": 200, "p1PhuongAn": 100, "p2Dan": 280, "p2Y": 200, "p3": 280, "p4": 380}
    loi = []
    d = lambda v: len(lam_sach(v, False))
    dlc = lambda v: len(lam_sach(v, True))
    mang = lambda k: de.get(k) if isinstance(de.get(k), list) else []
    for i, c in enumerate(mang("phan1")):
        if d(c.get("cauHoi")) > g["p1CauHoi"]:
            loi.append("Phần 1 câu %d: câu hỏi dài %d ký tự, cần rút gọn còn tối đa %d." % (i + 1, d(c.get("cauHoi")), g["p1CauHoi"]))
        for k in "ABCD":
            if dlc(c.get(k)) > g["p1PhuongAn"]:
                loi.append("Phần 1 câu %d: phương án %s dài %d ký tự, cần tối đa %d." % (i + 1, k, dlc(c.get(k)), g["p1PhuongAn"]))
    for i, c in enumerate(mang("phan2")):
        if d(c.get("cauHoi")) > g["p2Dan"]:
            loi.append("Phần 2 câu %d: câu dẫn dài %d ký tự, cần tối đa %d." % (i + 1, d(c.get("cauHoi")), g["p2Dan"]))
        for k in "ABCD":
            if dlc(c.get(k)) > g["p2Y"]:
                loi.append("Phần 2 câu %d: ý %s) dài %d ký tự, cần tối đa %d." % (i + 1, k.lower(), dlc(c.get(k)), g["p2Y"]))
    for i, c in enumerate(mang("phan3")):
        if d(c.get("cauHoi")) > g["p3"]:
            loi.append("Phần 3 câu %d: đề bài dài %d ký tự, cần tối đa %d." % (i + 1, d(c.get("cauHoi")), g["p3"]))
    for i, c in enumerate(mang("phan4")):
        if d(c.get("cauHoi")) > g["p4"]:
            loi.append("Phần 4 câu %d: đề bài dài %d ký tự, cần tối đa %d." % (i + 1, d(c.get("cauHoi")), g["p4"]))
    return loi


# ═════════════ danh mục / mẫu / lời nhắc ═════════════
def danh_muc(p):
    dm = ST["dm"]
    if p == 1:
        return "PHẦN I (Trắc nghiệm nhiều lựa chọn):\n" + "".join("- Câu %d: %s\n" % (i + 1, y) for i, y in enumerate(dm["p1"]))
    if p == 2:
        s = "PHẦN II (Trắc nghiệm Đúng - Sai):\n"
        for i, nhom in enumerate(dm["p2"]):
            s += "- Câu %d gồm tình huống và 4 ý sau:\n" % (i + 1)
            s += "".join("  + Ý %s: %s\n" % ("abcd"[k], y) for k, y in enumerate(nhom))
        return s
    if p == 3:
        return "PHẦN III (Trả lời ngắn - DẠNG ĐIỀN SỐ LIỆU):\n" + "".join(
            "- Câu %d: %s (Yêu cầu đáp án phải là một con số kết quả tính toán)\n" % (i + 1, y) for i, y in enumerate(dm["p3"]))
    return "PHẦN IV (Tự luận):\n" + "".join("- Câu %d: %s\n" % (i + 1, y) for i, y in enumerate(dm["p4"]))


def danh_muc_mot_cau(p, so):
    if p == 2:
        nhom = (ST["dm"]["p2"][so - 1:so] or [[]])[0]
        return "Câu %d gồm tình huống và 4 ý sau:\n" % so + "\n".join("  + Ý %s: %s" % ("abcd"[k], y) for k, y in enumerate(nhom))
    mang = ST["dm"].get("p%d" % p) or []
    return "Câu %d: %s" % (so, mang[so - 1] if so <= len(mang) else "")


def mau_json(p):
    return {
        1: '{"phan1": [ {"cauHoi": "Nội dung...", "A": "...", "B": "...", "C": "...", "D": "...", "dapAn": "A"} ]}',
        2: '{"phan2": [ {"cauHoi": "Nội dung dẫn...", "A": "Ý a...", "B": "Ý b...", "C": "Ý c...", "D": "Ý d...", "dapAn": "a) Đ, b) S, c) Đ, d) S"} ]}',
        3: '{"phan3": [ {"cauHoi": "Nội dung...", "dapAn": "12.5"} ]}',
        4: r'{"phan4": [ {"cauHoi": "Nội dung đề bài tự luận...", "dapAn": "- Bước 1...\\n- Bước 2...\\n=> Đáp số: ... kèm đơn vị"} ]}',
    }[p]


def de_day_du():
    return {"phan%d" % i: DE["phan%d" % i] for i in (1, 2, 3, 4)}


# ═════════════ công cụ 1: soạn một phần ═════════════
def soan_phan(p):
    k = "p%d" % p
    if ST["yc"][k] == 0:
        DE["phan%d" % p], DA_XM[k] = [], True
        return {"trangThai": "Phần %d không có câu nào theo Bản đặc tả, bỏ qua." % p}
    qd = GOI.get("quyDinh") or {}
    prompt = (
        "Hãy biên soạn NỘI DUNG và ĐÁP ÁN CHI TIẾT cho riêng PHẦN %d của đề kiểm tra môn %s lớp %s (%s).\n\n" % (p, GOI["subject"], GOI["grade"], GOI["textbook"])
        + "=== DANH MỤC CÂU HỎI BẮT BUỘC SOẠN ĐÚNG THEO BẢN ĐẶC TẢ ===\n" + danh_muc(p) + "\n"
        + "LỆNH BẮT BUỘC:\n"
        + "- Phân bổ câu hỏi thực tiễn: %s\n" % GOI.get("phanBoThucTien", "")
        + "- Đúng số lượng: Phần %d có %d câu.\n" % (p, ST["yc"][k])
        + "- Đáp án phải ĐÚNG về mặt vật lí, số liệu tính toán chính xác.\n"
        + str(qd.get("doDai", "")) + "\n" + str(qd.get("hinhAnh", "")) + "\n"
        + '- Phần II mỗi câu bắt buộc có 4 ý A, B, C, D (đánh giá Đúng/Sai), đáp án dạng "a) Đ, b) S, c) Đ, d) S".\n'
        + "- Phần III trường 'dapAn' phải là số liệu (VD: 15.2; 100...). Không được trả về A, B, C, D.\n"
        + LENH_P4 + "\n" + LENH_LATEX + "\n\n"
        + "NGUỒN CÂU HỎI THAM KHẢO TỪ GIÁO VIÊN:\n" + str(ST.get("nganHang") or "")[:6000] + "\n\n"
        + "Trả về JSON nghiêm ngặt theo cấu trúc:\n" + mau_json(p)
        + str((GOI.get("hau") or {}).get(str(p), "")))
    he = GOI.get("he", "")
    khong_tim = False
    try:
        kq = goi_ai(prompt, he, web=True)
    except X.HetHanMuc:
        raise
    except Exception as e:
        khong_tim = True
        NK.ghi("Tìm kiếm lỗi – soạn không tìm kiếm", "Phần %d: %s" % (p, str(e)[:200]))
        kq = goi_ai(prompt, he, web=False)
    mang = kq if isinstance(kq, list) else (kq.get("phan%d" % p) if isinstance(kq, dict) else None)
    if not isinstance(mang, list) or not mang:
        return {"error": "Gemini không trả về danh sách câu cho Phần %d." % p}
    DE["phan%d" % p] = sap_xep_phan(mang, p, ST.get("dsMa"))
    DA_XM[k], TON_DONG[k] = False, []
    if khong_tim and p not in KHONG_TIM_KIEM:
        KHONG_TIM_KIEM.append(p)
    return {"trangThai": "Đã soạn Phần %d: %d/%d câu." % (p, len(mang), ST["yc"][k])}


# ═════════════ công cụ 2: giải lại độc lập để xác minh ═════════════
def groq_giai(p, cac):
    if not (G and G.san_sang()):
        return {}
    dang = {1: "TN", 2: "DS", 3: "TLN", 4: "TL"}[p]
    ds = []
    for so, c in cac:
        pa = ("A. %s\nB. %s\nC. %s\nD. %s" % tuple(c.get(x, "") for x in "ABCD")) if p in (1, 2) else ""
        ds.append({"ma": "%d-%d" % (p, so), "dang": dang, "noi_dung": str(c.get("cauHoi", "")) + mo_ta_hinh(c.get("hinhAnh")), "phuong_an": pa})
    try:
        kq, _ = G.giai_lo(ds)
    except Exception as e:
        NK.ghi("Groq lỗi", str(e)[:150])
        return {}
    return {so: kq["%d-%d" % (p, so)] for so, _ in cac if kq.get("%d-%d" % (p, so))}


def xac_minh(p, so_chon=0):
    mang = DE["phan%d" % p]
    if not mang:
        return {"error": "Phần %d chưa được soạn." % p}
    cac = [(i + 1, c) for i, c in enumerate(mang) if not so_chon or so_chon == i + 1]
    if not cac:
        return {"error": "Không có câu số %s trong Phần %d." % (so_chon, p)}
    de_bai = ""
    for so, c in cac:
        h = mo_ta_hinh(c.get("hinhAnh"))
        if p == 1:
            de_bai += "Câu %d: %s%s\nA. %s\nB. %s\nC. %s\nD. %s\n\n" % (so, c.get("cauHoi"), h, c.get("A"), c.get("B"), c.get("C"), c.get("D"))
        elif p == 2:
            de_bai += "Câu %d: %s%s\na) %s\nb) %s\nc) %s\nd) %s\n\n" % (so, c.get("cauHoi"), h, c.get("A"), c.get("B"), c.get("C"), c.get("D"))
        else:
            de_bai += "Câu %d: %s%s\n\n" % (so, c.get("cauHoi"), h)
    yc_dang = {1: '"dapAn" là đúng một chữ cái A, B, C hoặc D.',
               2: '"dapAn" dạng "a) Đ, b) S, c) Đ, d) S" (đánh giá từng ý Đúng hay Sai).',
               3: '"dapAn" là MỘT CON SỐ kết quả cuối cùng (không kèm đơn vị).',
               4: '"dapAn" là MỘT CON SỐ là đáp số cuối cùng (không kèm đơn vị).'}[p]
    prompt = ('Giải các câu sau và trả về JSON đúng dạng {"ketQua": [ {"soCau": 1, "dapAn": "..."} ]}. Với mỗi câu: %s\n\n%s' % (yc_dang, de_bai))
    kq = goi_ai(prompt, SYS_GIAI)
    ds = kq if isinstance(kq, list) else ((kq or {}).get("ketQua") or [])
    y2 = groq_giai(p, cac)                                   # ý kiến thứ hai (hãng khác), nếu có

    lech, khong_kl = [], 0
    for so, c in cac:
        g = next((r for r in ds if isinstance(r, dict) and str(r.get("soCau")).strip() == str(so)), None)
        if not g:
            khong_kl += 1
            continue
        khop = so_khop(p, c.get("dapAn"), g.get("dapAn"))
        if khop is False and so in y2 and so_khop(p, c.get("dapAn"), y2[so]) is True:
            khop = True                                      # Groq đồng ý với đáp án đã soạn → không coi là lệch
        if khop is None:
            khong_kl += 1
        elif khop is False:
            lech.append({"soCau": so, "dapAnDaSoan": str(c.get("dapAn"))[:200], "dapAnGiaiLai": str(g.get("dapAn"))[:200]})
    k = "p%d" % p
    cu = [l for l in TON_DONG[k] if so_chon and l["soCau"] != so_chon]
    TON_DONG[k] = cu + lech
    DA_XM[k] = True if not so_chon else (DA_XM[k] or False)
    if so_chon and not TON_DONG[k]:
        DA_XM[k] = True
    return {"phan": p, "soCauDaGiaiLai": len(cac), "soCauLech": len(lech), "cacCauLech": lech, "soCauKhongDuCoSo": khong_kl}


# ═════════════ công cụ 3: soạn lại một câu ═════════════
def soan_lai_cau(p, so, ly_do, them=""):
    mang = DE["phan%d" % p]
    if not mang or so < 1 or so > len(mang):
        return {"error": "Không có câu %d trong Phần %d." % (so, p)}
    kd = "%d-%d" % (p, so)
    dem = SO_LAN.get(kd, 0)
    if dem >= SO_LAN_SOAN_LAI:
        return {"error": "Câu %d (Phần %d) đã soạn lại tối đa %d lần." % (so, p, dem)}
    qd = GOI.get("quyDinh") or {}
    hau = (GOI.get("hauMotCau") or {}).get(kd, "") + (GOI.get("hauChungMotCau") or {}).get(str(p), "")
    prompt = (
        "Hãy SOẠN LẠI DUY NHẤT 1 câu của PHẦN %d đề kiểm tra môn %s lớp %s.\n\n" % (p, GOI["subject"], GOI["grade"])
        + "YÊU CẦU THEO BẢN ĐẶC TẢ (bắt buộc bám đúng chỉ báo, mức độ):\n" + danh_muc_mot_cau(p, so) + "\n\n"
        + "LÝ DO PHẢI SOẠN LẠI: %s\n" % ly_do
        + ("THÔNG TIN BỔ SUNG: %s\n" % them if them else "") + "\n"
        + "CÂU HIỆN TẠI (đang có vấn đề):\n" + json.dumps(mang[so - 1], ensure_ascii=False) + "\n\n"
        + "LỆNH BẮT BUỘC:\n- Đáp án phải ĐÚNG về mặt vật lí, tự giải lại cẩn thận trước khi trả lời.\n"
        + str(qd.get("doDai", "")) + "\n" + str(qd.get("hinhAnh", "")) + "\n"
        + '- Phần II có 4 ý A, B, C, D, đáp án dạng "a) Đ, b) S, c) Đ, d) S". Phần III \'dapAn\' là một con số. ' + LENH_P4_NGAN + "\n"
        + LENH_LATEX + "\n"
        + "- Trả về JSON của ĐÚNG 1 câu, cùng cấu trúc với câu hiện tại, không thêm lời giải thích." + hau)
    kq = goi_ai(prompt, GOI.get("he", ""))
    if isinstance(kq, dict) and isinstance(kq.get("phan%d" % p), list) and kq["phan%d" % p]:
        kq = kq["phan%d" % p]
    cau = kq[0] if isinstance(kq, list) and kq else kq
    if not isinstance(cau, dict) or not cau.get("cauHoi"):
        return {"error": "Gemini không trả về câu hỏi hợp lệ."}
    gan_ma_mot_cau(cau, p, so)
    mang[so - 1] = cau
    SO_LAN[kd] = dem + 1
    k = "p%d" % p
    TON_DONG[k] = [l for l in TON_DONG[k] if l["soCau"] != so]
    DA_XM[k] = False
    return {"trangThai": "Đã soạn lại Câu %d (Phần %d), lần %d/%d." % (so, p, dem + 1, SO_LAN_SOAN_LAI)}


# ═════════════ vòng điều khiển ═════════════
def xac_minh_va_sua(p):
    if ST["yc"]["p%d" % p] == 0:
        return
    r = xac_minh(p)
    NK.ghi("Xác minh Phần %d" % p, "giải lại %s câu, lệch %s câu %s" % (r.get("soCauDaGiaiLai"), r.get("soCauLech"),
                                                                       [x["soCau"] for x in r.get("cacCauLech", [])]))
    for _ in range(SO_LAN_SOAN_LAI):
        lech = [dict(x) for x in TON_DONG["p%d" % p]]
        if not lech or het_gio(600):
            break
        for x in lech:
            so = x["soCau"]
            if SO_LAN.get("%d-%d" % (p, so), 0) >= SO_LAN_SOAN_LAI:
                continue
            ly = ("Đáp án đã soạn (%s) lệch với kết quả giải lại độc lập (%s). Hãy tự giải lại thật cẩn thận; nếu đề bài chưa rõ hoặc "
                  "dữ kiện mâu thuẫn thì sửa đề cho rõ ràng rồi tính lại đáp án." % (x["dapAnDaSoan"], x["dapAnGiaiLai"]))
            rr = soan_lai_cau(p, so, ly)
            NK.ghi("Soạn lại P%d-C%d" % (p, so), rr.get("trangThai") or rr.get("error"))
            if "error" not in rr:
                xac_minh(p, so)


def sua_cau_truc():
    so_lan_phan = {}
    for vong in range(3):
        de = de_day_du()
        loi = kiem_tra_de(de, ST["yc"]) + kiem_tra_do_dai(de)
        if not loi or het_gio(600):
            return loi
        NK.ghi("Kiểm tra cấu trúc (vòng %d)" % (vong + 1), "%d lỗi: %s" % (len(loi), " | ".join(loi[:5])))
        da_lam = False
        for l in loi:
            m_phan = re.match(r"Phần (\d) đang có", l)
            m_cau = re.match(r"Phần (\d) câu (\d+):", l)
            if m_phan:
                p = int(m_phan.group(1))
                if so_lan_phan.get(p, 0) >= 2:
                    continue
                so_lan_phan[p] = so_lan_phan.get(p, 0) + 1
                for kd in [k for k in SO_LAN if k.startswith("%d-" % p)]:
                    SO_LAN.pop(kd, None)
                rr = soan_phan(p)
                NK.ghi("Soạn lại cả Phần %d (sai số câu)" % p, rr.get("trangThai") or rr.get("error"))
                if "error" not in rr:
                    xac_minh_va_sua(p)
                    da_lam = True
            elif m_cau:
                p, so = int(m_cau.group(1)), int(m_cau.group(2))
                if SO_LAN.get("%d-%d" % (p, so), 0) >= SO_LAN_SOAN_LAI or so > len(DE["phan%d" % p]):
                    continue
                rr = soan_lai_cau(p, so, l)
                NK.ghi("Sửa P%d-C%d" % (p, so), rr.get("trangThai") or rr.get("error"))
                if "error" not in rr:
                    xac_minh(p, so)
                    da_lam = True
        if not da_lam:
            break
    return kiem_tra_de(de_day_du(), ST["yc"]) + kiem_tra_do_dai(de_day_du())


def main():
    global GOI, ST, CAC_MODEL, NK
    gc, drive = ket_noi()
    goi_id, kq_id = os.environ["GOI_ID"], os.environ["KQ_ID"]
    NK = NhatKy(drive, kq_id)
    NK.ghi("Bắt đầu", "Xưởng Python nhận gói việc", ep=True)
    try:
        GOI = doc_tep(drive, goi_id)
        if not GOI.get("yc") or not GOI.get("dm"):
            raise RuntimeError("Gói việc kiểu cũ (thiếu yc/dm). Hãy cập nhật XuongTaoDe.gs bên Apps Script rồi tạo lại đề.")
        ST = {"yc": GOI["yc"], "dm": GOI["dm"], "dsMa": GOI.get("dsMa"), "vtThucTien": GOI.get("vtThucTien"), "nganHang": GOI.get("nganHang", "")}
        kho = gc.open_by_key(X.ID_KHO_CHUNG)
        CAC_MODEL = X.doc_cau_hinh(kho)
        NK.ghi("Cấu hình", "lớp %s · số câu %s · model %s" % (GOI.get("grade"), ST["yc"], CAC_MODEL[:2]), ep=True)

        # 1) soạn từng phần
        for p in (1, 2, 3, 4):
            for lan in range(3):
                rr = soan_phan(p)
                NK.ghi("Soạn Phần %d" % p, rr.get("trangThai") or rr.get("error"))
                if "error" not in rr:
                    break
            else:
                raise RuntimeError("Không soạn được Phần %d sau 3 lần: %s" % (p, rr.get("error")))
        # 2) xác minh độc lập + soạn lại câu lệch
        for p in (1, 2, 3, 4):
            xac_minh_va_sua(p)
        # 3) cấu trúc + độ dài
        loi_con = sua_cau_truc()

        ton = {k: v for k, v in TON_DONG.items() if v}
        NK.ghi("Hoàn thành", "Còn %d lỗi cấu trúc/độ dài; câu lệch tồn đọng: %s" % (len(loi_con), {k: [x["soCau"] for x in v] for k, v in ton.items()}))
        canh_bao = list(loi_con)
        for k, v in ton.items():
            canh_bao.append("Phần %s còn câu lệch đáp án (giáo viên xem lại): %s" % (k[1:], [x["soCau"] for x in v]))
        for p in KHONG_TIM_KIEM:
            canh_bao.append("Phần %d soạn KHÔNG có Google Search (số liệu thực tiễn chưa tra web)." % p)
        ghi_tep(drive, kq_id, {"trangThai": "XONG", "cheDo": "agent", "model": MODEL_CUOI, "deThi": de_day_du(),
                               "canhBao": canh_bao, "tonDong": TON_DONG, "soLanSoanLai": SO_LAN,
                               "nhatKy": NK.ds[-150:], "luc": bay_gio()})
        print("✅ Xưởng Python đã soạn đề xong. Cảnh báo: %d" % len(canh_bao), flush=True)
    except Exception as e:
        err = str(e)[:500]
        print("❌ Lỗi xưởng Python: %s" % err, flush=True)
        try:
            ghi_tep(drive, kq_id, {"trangThai": "LOI", "cheDo": "agent", "loi": err, "nhatKy": (NK.ds if NK else [])[-150:], "luc": bay_gio()})
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
