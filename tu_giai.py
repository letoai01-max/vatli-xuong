"""
tu_giai.py – XƯỞNG TỰ GIẢI HÀNG LOẠT (Python, GitHub Actions) – thay tgChay() trong TuGiai.gs của Kho chung.

GIỮ NGUYÊN QUY TẮC CỦA TuGiai.gs:
  • Chỉ giải câu ĐANG CHỜ DUYỆT (trạng thái trống / "Cần người xem" / "Chưa duyệt") CHƯA CÓ LỜI GIẢI, ô "Tự giải (AI)" còn trống,
    và không đang chờ Lọc hình (LocHinh.gs).
  • Gemini chỉ trả DỮ LIỆU (JSON: tóm tắt, các bước, đáp án); CODE ghép lời giải đúng khuôn ($...$, \\cdot, 0,05, mỗi bước một dòng),
    chuẩn hoá bằng latex_chuan.py (bản Python của ChuanLatex.gs).
  • Có đáp án gốc → lời giải phải ra ĐÚNG đáp án gốc (sai thì giải lại 1 lần; vẫn sai → không ghi, báo ⚠).
  • Chưa có đáp án gốc → 2 lời giải ĐỘC LẬP phải khớp:
        câu không hình: GIẢI BẰNG CODE (Gemini chạy Python) và GROQ (khác hãng) cùng ra một đáp án, và lời giải trình bày cũng ra
        đáp án đó; câu có hình (Groq không xem được hình): như TuGiai.gs – Gemini giải 2 lần độc lập, lệch thì lần 3 phân xử (2/3).
  • Chỉ ghi vào ô Lời giải còn trống (đọc lại ngay trước khi ghi – không bao giờ đè lời giải thầy đã viết);
    Đáp án chỉ điền khi ô đáp án còn trống. KHÔNG ĐỔI trạng thái duyệt. Ghi chú ✔ / ⚠ / ✘ vào cột "Tự giải (AI)" như cũ.
  • Lỗi tạm thời (Groq / máy giải không chạy được cả lô, hết hạn mức) → không ghi chú, lượt sau giải lại.
Khác TuGiai.gs: chạy theo lô trên GitHub (không giới hạn 6 phút, không tốn phút trigger Apps Script), tối đa TOI_DA_CAU câu mỗi lượt.
Sau khi chạy xưởng này, tắt lịch cũ bên Apps Script (Kho chung → chạy tgTatTuGiai) để hai bên không giải trùng.

Biến môi trường: GOOGLE_CREDENTIALS, GEMINI_API_KEY (_2, _3…), GROQ_API_KEY; tuỳ chọn TOI_DA_CAU (40), THOI_GIAN_TOI_DA_PHUT (60).
Ghi ra GITHUB_OUTPUT: da_ghi=<số câu đã ghi lời giải> để workflow xuất lại questions.json khi có lời giải mới.
"""
import base64, datetime as dt, json, os, re, time

import requests

import doc_de as X          # ket_noi, goi_gemini, doc_cau_hinh, HetHanMuc, bo_dau, ID_KHO_CHUNG, TZ, ghi_nhip
import duyet_cau as D       # tang4 (giải bằng code), dap_an_may, json_cuoi
import latex_chuan as L
try:
    import groq_xuong as G
except Exception:
    G = None
try:
    import quota_xuong as Q
except Exception:
    Q = None

TAB = "NganHangCauHoi"
COT_TU_GIAI, COT_LOC_HINH = "Tự giải (AI)", "Lọc hình (AI)"
CHU_MAU = "Nhập hoặc chỉnh sửa lời giải chi tiết..."
TEN_AGENT = "Xưởng tự giải (Python)"
TOI_DA_CAU = int(os.environ.get("TOI_DA_CAU", "40"))
THOI_GIAN_TOI_DA_PHUT = float(os.environ.get("THOI_GIAN_TOI_DA_PHUT", "60"))
LO = 10
SAI_SO = 0.01                  # như tgKhop_: lệch tối đa 1%
BAT_DAU = time.time()


def con_gio(du_tru=180):
    return time.time() - BAT_DAU < THOI_GIAN_TOI_DA_PHUT * 60 - du_tru


def gio():
    return dt.datetime.now(X.TZ).strftime("%H:%M %d/%m")


# ============================== CỘT (giống tgCot_) ==============================
def tim_cot(td):
    C = {"maCau": 1, "yccd": 2, "noiDung": 7, "phuongAn": 8, "dapAn": 9, "loiGiai": 10, "trangThai": 21,
         "dang": 0, "linkAnh": 0, "tuGiai": 0, "locHinh": 0}
    thay = set()
    def dat(k, c):
        if k not in thay:
            C[k] = c; thay.add(k)
    for i, t in enumerate(td):
        h, c = str(t).strip().lower(), i + 1
        if "tự giải" in h:
            dat("tuGiai", c); continue
        if h == COT_LOC_HINH.lower():
            dat("locHinh", c); continue
        if h == "macau" or "mã câu" in h or h == "id" or "ma_cau" in h: dat("maCau", c)
        if h == "trangthai" or "trạng thái" in h or h == "status" or "trang_thai" in h or "duyệt" in h: C["trangThai"] = c
        if h == "loigiai" or "lời giải" in h or "hdc" in h or "loi_giai" in h: C["loiGiai"] = c
        if h == "noidung" or "nội dung" in h or "noi_dung" in h: dat("noiDung", c)
        if h == "phuongan" or "phương án" in h or "phuong_an" in h: dat("phuongAn", c)
        if h == "dapan" or "đáp án" in h or "dap_an" in h: dat("dapAn", c)
        if h == "dang" or "dạng" in h or "loại câu" in h or "loai_cau" in h: dat("dang", c)
        if "yccđ" in h or "yccd" in h: dat("yccd", c)
        if "link ảnh" in h or "linkanh" in h or "ảnh đồ thị" in h: dat("linkAnh", c)
    return C


def o(r, C, k):
    c = C.get(k) or 0
    return str(r[c - 1]).strip() if c and c - 1 < len(r) else ""


def tach_link(s):
    return list(dict.fromkeys(x.strip() for x in re.split(r"[,;\s]+", str(s or "")) if x.strip()))


def can_giai(r, C):
    """Giống tgCanGiai_."""
    if not o(r, C, "maCau") or not o(r, C, "noiDung"):
        return False
    if C.get("tuGiai") and o(r, C, "tuGiai"):
        return False
    if C.get("locHinh") and C.get("linkAnh") and not o(r, C, "locHinh") and len(tach_link(o(r, C, "linkAnh"))) >= 2:
        return False                                   # đang chờ Lọc hình chọn lại hình
    lg = o(r, C, "loiGiai")
    if lg and lg != CHU_MAU:
        return False
    tt = o(r, C, "trangThai").lower()
    return tt == "" or "cần người xem" in tt or "chưa duyệt" in tt


# ============================== DẠNG CÂU & ĐÁP ÁN (giống TuGiai.gs) ==============================
def dang_tg(dang_cot, phuong_an):
    d = re.sub(r"\s+", " ", re.sub(r"[/\-–—_|]+", " ", str(dang_cot or "").lower()))
    if "đúng sai" in d: return "ds"
    if "ngắn" in d: return "ngan"
    if "tự luận" in d: return "tuluan"
    if "nhiều lựa chọn" in d or "trắc nghiệm" in d: return "tn"
    pa = str(phuong_an or "")
    if not pa.strip(): return "ngan"
    if re.search(r"(^|\n)\s*a\s*\)", pa) and re.search(r"(^|\n)\s*b\s*\)", pa): return "ds"
    return "tn"


LOAI = {"tn": "TN", "ds": "DS", "ngan": "TLN", "tuluan": "TL"}


def chu_cai(s):
    m = re.search(r"[A-D]", str(s or "").upper())
    return m.group(0) if m else ""


def la_dung(x):
    return bool(re.match(r"^\s*(đ|đúng|true|d\b)", str(x), re.I))


def so(s):
    m = re.search(r"-?\d+(?:[.,]\d+)?", str("" if s is None else s).replace("{,}", ","))
    return float(m.group(0).replace(",", ".")) if m else None


def chuan_so_sanh(dang, s):
    """Mọi đáp án (gốc, lời giải, máy giải bằng code, Groq) về một dạng: chữ A-D / chuỗi ĐSĐS / số."""
    s = str(s or "").strip()
    if not s: return ""
    if dang == "tn": return chu_cai(s)
    if dang == "ds":
        y = D.tach_ds(s)
        if len(y) == 4: return "".join(y[k] for k in "abcd")
        x = re.sub(r"(^|[\s;,.])[A-H]\s*[).:]", " ", s.upper()).replace("ĐÚNG", "Đ").replace("SAI", "S")
        x = re.sub(r"[^ĐS]", "", x.replace("TRUE", "Đ").replace("FALSE", "S"))
        return x
    n = so(s)
    return repr(n) if n is not None else s


def khop(dang, a, b):
    if not a or not b: return False
    if dang in ("tn", "ds"): return a == b
    try:
        x, y = float(a), float(b)
        return abs(x - y) <= max(1e-9, SAI_SO * max(abs(x), abs(y)))
    except ValueError:
        return re.sub(r"\s+", "", a.lower()) == re.sub(r"\s+", "", b.lower())


def dap_an_cua_loi_giai(dang, kq):
    if dang == "tn": return chu_cai(kq.get("dapAn"))
    if dang == "ds": return "".join("Đ" if la_dung(x) else "S" for x in (kq.get("dungSai") or []))
    v = kq.get("giaTriSo")
    if isinstance(v, (int, float)): return repr(float(v))
    n = so(kq.get("dapAn"))
    return repr(n) if n is not None else str(kq.get("dapAn") or "").strip()


# ============================== GHÉP LỜI GIẢI BẰNG CODE (giống tgGhepLoiGiai_) ==============================
def sach_bt(s):
    s = str("" if s is None else s).strip()
    s = re.sub(r"^\\\(|\\\)$", "", s)
    s = re.sub(r"^\\\[|\\\]$", "", s)
    return L.chuan_hoa_toan(s.replace("$", ""))


def sach_chu(s):
    return re.sub(r"\s+", " ", L.chuan_hoa_latex("" if s is None else str(s))).strip()


def la_cau_chon(t):
    x = re.sub(r"^(kết luận|đáp án|đáp số)\s*:?\s*", "", str(t or "").strip(), flags=re.I)
    x = re.sub(r"[.\s]+$", "", x)
    return bool(re.match(r"^((do đó|vậy|vì vậy|như vậy)[,\s]+)?(ta\s+)?(chọn|đáp án( đúng)?( là)?)\s+(phương án\s+|đáp án\s+)?[A-D]$", x, re.I)
                or re.match(r"^(đúng\s+)?(là\s+)?(phương án\s+)?[A-D]$", x, re.I))


def dap_an_hien_thi(dang, kq):
    if dang == "tn": return chu_cai(kq.get("dapAn"))
    if dang == "ds":
        return "; ".join("abcdefgh"[i] + ") " + ("Đúng" if la_dung(x) else "Sai") for i, x in enumerate(kq.get("dungSai") or []))
    dv = sach_chu(re.sub(r"[\\$]", "", re.sub(r"\\text\{\s*([^{}]*)\}", r"\1", str(kq.get("donVi") or ""))))
    return re.sub(r"\.$", "", str(kq.get("dapAn") or "").strip()) + (" " + dv if dv else "")


def dap_an_ghi_cot(dang, kq):
    if dang == "tn": return chu_cai(kq.get("dapAn"))
    if dang == "ds": return dap_an_hien_thi(dang, kq)
    return str(kq.get("dapAn") or "").strip()


def ghep_loi_giai(dang, kq):
    dong = []
    tt = [x for x in (sach_bt(b) for b in (kq.get("tomTat") or []) if isinstance(kq.get("tomTat"), list)) if x]
    if tt:
        dong.append("Tóm tắt: " + "; ".join("$" + b + "$" for b in tt) + ".")
    for b in (kq.get("cacBuoc") or []) if isinstance(kq.get("cacBuoc"), list) else []:
        if not isinstance(b, dict):
            continue
        ten = re.sub(r"[:.\s]+$", "", sach_chu(b.get("ten"))); loi = sach_chu(b.get("loi")); bt = sach_bt(b.get("bieuThuc"))
        dau = ((ten + ("" if re.search(r"\)$", ten) else ":")) if ten else "") + ((" " if ten else "") + loi if loi else "")
        if not bt and la_cau_chon(dau):
            continue
        if bt and b.get("khoi"):
            if dau: dong.append(dau)
            dong.append("$$" + bt + "$$")
        elif bt:
            dong.append((dau + " " if dau else "") + "$" + bt + "$.")
        elif dau:
            dong.append(dau)
    kl = sach_chu(kq.get("ketLuan"))
    if kl and not la_cau_chon(kl):
        dong.append(kl)
    dong.append("Đáp án: " + dap_an_hien_thi(dang, kq) + ".")
    return re.sub(r"\.\.+$", ".", "\n".join(dong), flags=re.M)


# ============================== LỜI NHẮC (giống tgLenhGiai_, tgHeThong_) ==============================
def he_thong(lan):
    return ("Bạn là giáo viên Vật lí THPT giỏi (Chương trình GDPT 2018, SGK Vật lí Kết nối tri thức), giải câu hỏi để đưa lời giải vào ngân hàng đề. "
            "Giải chính xác, đúng phạm vi chương trình; tính toán cẩn thận, tự kiểm tra lại từng phép tính, đơn vị và cách làm tròn theo đúng yêu cầu của đề. "
            + ("Đây là lần giải KIỂM TRA ĐỘC LẬP: tự giải lại từ đầu, không giả định trước kết quả nào; nếu được hãy lập luận theo cách khác để đối chiếu. " if lan > 0 else "")
            + "Chỉ trả về MỘT đối tượng JSON hợp lệ, không viết chữ nào khác.")


def lenh_giai(de, co_anh):
    theo_dang = {
        "tn": 'Trắc nghiệm nhiều lựa chọn: "dapAn" là đúng MỘT chữ cái A, B, C hoặc D. Bước cuối nêu vì sao chọn phương án đó.',
        "ds": 'Đúng/Sai: mỗi ý a), b), c), d) là một bước riêng có "ten" là "Ý a)", "Ý b)"… và "loi" giải thích ngắn; '
              '"dungSai" là mảng theo đúng thứ tự các ý, mỗi phần tử là "Đúng" hoặc "Sai"; "dapAn" để trống.',
        "ngan": 'Trả lời ngắn: "dapAn" là con số cuối cùng đã làm tròn đúng yêu cầu của đề, dấu phẩy thập phân (ví dụ "8,9"); '
                '"giaTriSo" là chính số đó dạng số (8.9); "donVi" là đơn vị viết chữ thường (ví dụ "V", "rad/s"), có thể để trống.',
        "tuluan": 'Tự luận: trình bày đủ các bước; "dapAn" là kết quả cuối ngắn gọn; nếu kết quả là số thì điền "giaTriSo" và "donVi".'}[de["dang"]]
    ten_dang = {"tn": "Trắc nghiệm 4 lựa chọn", "ds": "Trắc nghiệm đúng sai", "ngan": "Trả lời ngắn", "tuluan": "Tự luận"}[de["dang"]]
    return ("DẠNG CÂU: " + ten_dang + "\n" + ("MÃ YÊU CẦU CẦN ĐẠT: " + de["yccd"] + "\n" if de["yccd"] else "")
            + "\nĐỀ BÀI:\n" + de["noi_dung"] + "\n" + ("\nPHƯƠNG ÁN / CÁC Ý:\n" + de["phuong_an"] + "\n" if de["phuong_an"] else "")
            + ("\n(Hình vẽ / đồ thị của câu được gửi kèm; đọc số liệu trên hình thật cẩn thận.)\n" if co_anh else "")
            + "\nCẤU TRÚC JSON PHẢI TRẢ VỀ:\n"
            + '{"hieuDe": true, "lyDo": "", "tomTat": ["S = 40\\\\text{ cm}^2 = 4\\\\cdot 10^{-3}\\\\text{ m}^2", "B = 0,01\\\\text{ T}"], '
            + '"cacBuoc": [{"ten": "Tần số góc", "loi": "", "bieuThuc": "\\\\omega = 2\\\\pi n = 2\\\\cdot 3,14\\\\cdot 50 = 314\\\\text{ rad/s}", "khoi": false}], '
            + '"ketLuan": "", "dapAn": "", "giaTriSo": null, "donVi": "", "dungSai": []}\n'
            + "\nQUY TẮC VIẾT:\n"
            + '- "tomTat": mỗi phần tử là MỘT dữ kiện viết bằng LaTeX (đã đổi đơn vị nếu cần), KHÔNG kèm dấu $.\n'
            + '- "cacBuoc": "ten" là tên bước bằng chữ tiếng Việt (không LaTeX); "loi" là câu giải thích ngắn bằng chữ, có thể để trống, nếu nhắc kí hiệu thì đặt trong $...$; '
            + '"bieuThuc" là LaTeX KHÔNG kèm dấu $, có thể để trống; "khoi" = true nếu là công thức chính cần đứng riêng một dòng.\n'
            + "- Trong LaTeX: dấu nhân \\cdot; số thập phân dùng dấu phẩy (0,01); đơn vị \\text{ V}; lũy thừa 4\\cdot 10^{-3}; KHÔNG dùng kí tự Unicode như ω √ ² ≈ π.\n"
            + "- Không dùng Markdown, không dùng \\textbf, \\item, \\begin, không ghi nguồn [cite].\n"
            + '- KHÔNG viết bước hay "ketLuan" kiểu "Chọn C", "Đáp án: …" – hệ thống tự thêm dòng đáp án ở cuối. Không lặp lại cùng một ý.\n'
            + '- Đề thiếu dữ kiện, cần hình mà không có hình, hoặc không chắc chắn đúng: "hieuDe" = false và ghi "lyDo".\n'
            + "\nĐÁP ÁN: " + theo_dang)


# ============================== HÌNH ==============================
def tai_anh(drive, u):
    m = re.search(r"/file/d/([\w-]{20,})", u) or re.search(r"[?&]id=([\w-]{20,})", u) or re.search(r"googleusercontent\.com/d/([\w-]{20,})", u)
    if m:
        return X.tai_ve(drive, m.group(1)), "image/png"
    m = re.match(r"^https?://raw\.githubusercontent\.com/[^/]+/[^/]+/[^/]+/(.+)$", u, re.I)
    duong = m.group(1) if m else ("" if re.match(r"^https?://", u, re.I) else re.sub(r"^\.?/", "", u))
    if duong and os.path.isfile(duong):                     # ảnh nằm ngay trong kho (thư mục images/ đã checkout)
        with open(duong, "rb") as f:
            b = f.read()
    else:
        r = requests.get(u, timeout=60)
        r.raise_for_status()
        b = r.content
    duoi = duong.lower() if duong else u.lower()
    return b, "image/jpeg" if re.search(r"\.jpe?g$", duoi) else "image/webp" if duoi.endswith(".webp") else "image/png"


# ============================== GỌI GEMINI ==============================
def json_tg(text):
    s = re.sub(r"```\s*$", "", re.sub(r"^```(?:json)?\s*", "", str(text or ""), flags=re.I)).strip()
    try:
        return json.loads(s)
    except ValueError:
        a, b = s.find("{"), s.rfind("}")
        if a >= 0 and b > a:
            return json.loads(s[a:b + 1])
        raise ValueError("Gemini không trả về JSON hợp lệ.")


def giai_trinh_bay(de, anh, lan, ds_model):
    """Một lần Gemini giải và trả dữ liệu lời giải (JSON). Trả dict có 'so' (đáp án dạng so sánh) hoặc 'boQua'."""
    parts = [{"text": lenh_giai(de, len(anh))}] + [{"inline_data": {"mime_type": m, "data": base64.b64encode(b).decode()}} for b, m in anh]
    payload = {"systemInstruction": {"parts": [{"text": he_thong(lan)}]}, "contents": [{"role": "user", "parts": parts}],
               "generationConfig": {"temperature": 0.2 if lan == 0 else 0.7, "responseMimeType": "application/json", "maxOutputTokens": 16384}}
    data, model = X.goi_gemini(payload, ds_model)
    cand = (data.get("candidates") or [{}])[0]
    kq = json_tg("".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []) if not p.get("thought")))
    if kq.get("hieuDe") is False:
        return {"boQua": "Gemini không giải chắc chắn được: " + str(kq.get("lyDo") or "đề thiếu dữ kiện")[:150]}
    kq["so"] = dap_an_cua_loi_giai(de["dang"], kq)
    if not kq["so"]:
        raise RuntimeError("Gemini không trả đáp án đúng dạng câu.")
    kq["_model"] = model
    return kq


# ============================== GIẢI MỘT LÔ ==============================
def giai_lo(lo, ds_model, drive):
    """lo: danh sách câu. Trả {mã: kết quả} với kết quả = {ok, loiGiai, dapAn, ghiChu} | {ghiChu, loi} | {tam_hoan}."""
    ra, so_luot = {}, {}
    # 1. Lời giải trình bày (Gemini, JSON) cho từng câu
    for de in lo:
        if not con_gio():
            ra[de["ma"]] = {"tam_hoan": "hết giờ"}; continue
        try:
            de["anh"] = [tai_anh(drive, u) for u in de["link"][:3]]
        except Exception as e:
            ra[de["ma"]] = {"ghiChu": "Bỏ qua: không tải được hình (%s)." % str(e)[:200]}; continue
        try:
            de["k"] = [giai_trinh_bay(de, de["anh"], 0, ds_model)]
            so_luot[de["ma"]] = 1
        except X.HetHanMuc:
            raise
        except Exception as e:
            ra[de["ma"]] = {"loi": str(e)[:250]}
    con = [de for de in lo if de["ma"] not in ra]
    # 2. Câu không hình, không có đáp án gốc: giải bằng code (Gemini) và Groq theo lô
    can_hai = [de for de in con if not de["goc"] and not de["anh"] and not de["k"][0].get("boQua")]
    may, groq, model_may, model_groq = {}, {}, "", ""
    if can_hai:
        ds = [{"ma": de["ma"], "dang": {"tn": "Nhiều lựa chọn", "ds": "Đúng/sai", "ngan": "Trả lời ngắn", "tuluan": "Tự luận"}[de["dang"]],
               "noi_dung": de["noi_dung"], "phuong_an": de["phuong_an"]} for de in can_hai]
        try:
            g4, model_may = D.tang4(ds, ds_model, can_hai[0]["k"][0].get("_model", ""))
            may = {m: D.dap_an_may(LOAI[next(d["dang"] for d in can_hai if d["ma"] == m)], g) for m, g in g4.items()}
            may["__chay"] = True
        except X.HetHanMuc:
            raise
        except Exception as e:
            print("  Máy giải bằng code lỗi cả lô (lượt sau thử lại):", str(e)[:120], flush=True)
        if G and G.co_khoa():
            groq, model_groq = G.giai_lo([{"ma": x["ma"], "dang": LOAI[d["dang"]], "noi_dung": x["noi_dung"], "phuong_an": x["phuong_an"]}
                                          for x, d in zip(ds, can_hai)])
    # 3. Quyết định từng câu
    for de in con:
        dang, k1 = de["dang"], de["k"][0]
        if k1.get("boQua"):
            ra[de["ma"]] = {"ghiChu": k1["boQua"]}; continue
        def them_lan(lan):
            kq = giai_trinh_bay(de, de["anh"], lan, ds_model)
            so_luot[de["ma"]] = so_luot.get(de["ma"], 1) + 1
            return kq
        def xong(kq, ghi_chu):
            n = so_luot.get(de["ma"], 1)
            return {"ok": True, "loiGiai": ghep_loi_giai(dang, kq), "dapAn": "" if de["goc"] else dap_an_ghi_cot(dang, kq),
                    "ghiChu": ghi_chu + " (%d lượt Gemini%s%s)" % (n, ", có xem hình" if de["anh"] else "",
                                                                  ", máy giải bằng code + Groq" if de in can_hai else "")}
        try:
            if de["goc"]:                                   # Bằng chứng 1: đáp án gốc
                goc = chuan_so_sanh(dang, de["goc"])
                if khop(dang, k1["so"], goc):
                    ra[de["ma"]] = xong(k1, "Khớp đáp án gốc " + de["goc"]); continue
                k2 = them_lan(1)
                if not k2.get("boQua") and khop(dang, k2["so"], goc):
                    ra[de["ma"]] = xong(k2, "Lần 2 khớp đáp án gốc " + de["goc"]); continue
                ra[de["ma"]] = {"ghiChu": "Lệch đáp án gốc: gốc %s, AI ra %s%s. Thầy kiểm tra lại đề hoặc đáp án gốc." % (
                    de["goc"], hien(dang, k1["so"]), "" if k2.get("boQua") else " và " + hien(dang, k2["so"]))}
                continue
            if de["anh"]:                                   # Câu có hình: như TuGiai.gs – 2 lần Gemini độc lập, lệch thì lần 3
                k2 = them_lan(1)
                if k2.get("boQua"):
                    ra[de["ma"]] = {"ghiChu": k2["boQua"]}; continue
                if khop(dang, k1["so"], k2["so"]):
                    ra[de["ma"]] = xong(k1, "Hai lần giải độc lập khớp: " + hien(dang, k1["so"])); continue
                k3 = them_lan(2)
                if not k3.get("boQua") and khop(dang, k3["so"], k1["so"]):
                    ra[de["ma"]] = xong(k1, "Khớp 2/3 lần giải: " + hien(dang, k1["so"])); continue
                if not k3.get("boQua") and khop(dang, k3["so"], k2["so"]):
                    ra[de["ma"]] = xong(k2, "Khớp 2/3 lần giải: " + hien(dang, k2["so"])); continue
                ra[de["ma"]] = {"ghiChu": "Ba lần giải không thống nhất (%s). Cần thầy giải." % " / ".join(
                    hien(dang, x) for x in [k1["so"], k2["so"], "?" if k3.get("boQua") else k3["so"]])}
                continue
            # Câu không hình, chưa có đáp án gốc: giải bằng code và Groq phải khớp
            if not may.get("__chay") or not (G and G.co_khoa()) or (not groq and model_groq == ""):
                ra[de["ma"]] = {"tam_hoan": "chưa có đủ máy giải bằng code và Groq"}; continue
            m, g = chuan_so_sanh(dang, may.get(de["ma"])), chuan_so_sanh(dang, groq.get(de["ma"]))
            if not m or not g:
                ra[de["ma"]] = {"ghiChu": "Chưa đủ 2 lời giải độc lập: máy giải bằng code %s, Groq %s." % (
                    hien(dang, m) or "chưa giải được", hien(dang, g) or "chưa giải được")}; continue
            if not khop(dang, m, g):
                ra[de["ma"]] = {"ghiChu": "Hai lời giải độc lập chưa thống nhất (máy giải bằng code %s / Groq %s / lời giải %s). Cần thầy giải." % (
                    hien(dang, m), hien(dang, g), hien(dang, k1["so"]))}; continue
            if khop(dang, k1["so"], m):
                ra[de["ma"]] = xong(k1, "Máy giải bằng code và Groq (khác hãng) cùng ra %s, lời giải khớp" % hien(dang, m)); continue
            k2 = them_lan(1)
            if not k2.get("boQua") and khop(dang, k2["so"], m):
                ra[de["ma"]] = xong(k2, "Máy giải bằng code và Groq cùng ra %s, lời giải lần 2 khớp" % hien(dang, m)); continue
            ra[de["ma"]] = {"ghiChu": "Máy giải bằng code và Groq cùng ra %s nhưng lời giải trình bày ra %s – không ghi lời giải." % (
                hien(dang, m), hien(dang, k1["so"]))}
        except X.HetHanMuc:
            raise
        except Exception as e:
            ra[de["ma"]] = {"loi": str(e)[:250]}
    return ra


def hien(dang, s):
    """Đáp án dạng so sánh → chữ dễ đọc trong ghi chú."""
    s = str(s or "")
    if dang == "ds" and re.fullmatch(r"[ĐS]{2,8}", s):
        return ", ".join("%s) %s" % ("abcdefgh"[i], c) for i, c in enumerate(s))
    if dang in ("ngan", "tuluan"):
        try:
            return ("%g" % float(s)).replace(".", ",")
        except ValueError:
            return s
    return s


# ============================== GHI VÀO SHEET ==============================
def a1(cot, dong):
    s = ""
    while cot:
        cot, r = divmod(cot - 1, 26)
        s = chr(65 + r) + s
    return "%s%d" % (s, dong)


def ghi_ket_qua(tab, C, ket_qua):
    """Đọc lại cột Mã câu, Lời giải, Đáp án ngay trước khi ghi: không đè lời giải thầy vừa viết, không ghi nhầm dòng."""
    if not ket_qua:
        return 0
    ma = tab.col_values(C["maCau"])
    vi_tri = {str(v).strip(): i + 1 for i, v in enumerate(ma) if i > 0 and str(v).strip()}
    dong = {m: vi_tri.get(m) for m in ket_qua if vi_tri.get(m)}
    if not dong:
        return 0
    can_doc = []
    for m, d in dong.items():
        can_doc += [a1(C["loiGiai"], d), a1(C["dapAn"], d)]
    hien_tai = tab.batch_get(can_doc)
    lay = lambda k: (hien_tai[k][0][0] if hien_tai[k] and hien_tai[k][0] else "").strip()
    cap, da_ghi, k = [], 0, 0
    for m, d in dong.items():
        lg_cu, da_cu = lay(k), lay(k + 1); k += 2
        kq = ket_qua[m]
        if kq.get("ok"):
            if lg_cu and lg_cu != CHU_MAU:
                ghi = "⚠ %s Thầy đã có lời giải trong lúc agent giải, không ghi đè." % gio()
            else:
                cap.append({"range": a1(C["loiGiai"], d), "values": [[kq["loiGiai"]]]})
                if kq.get("dapAn") and not da_cu:
                    cap.append({"range": a1(C["dapAn"], d), "values": [[kq["dapAn"]]]})
                ghi = "✔ %s %s" % (gio(), kq["ghiChu"]); da_ghi += 1
        elif kq.get("loi"):
            ghi = "✘ %s Lỗi: %s" % (gio(), kq["loi"])
        else:
            ghi = "⚠ %s %s" % (gio(), kq["ghiChu"])
        cap.append({"range": a1(C["tuGiai"], d), "values": [[ghi]]})
    if cap:
        tab.batch_update(cap, value_input_option="RAW")
    return da_ghi


# ============================== CHẠY ==============================
def main():
    gc, drive, sa = X.ket_noi()
    print("Tài khoản dịch vụ:", sa, flush=True)
    kho = gc.open_by_key(X.ID_KHO_CHUNG)
    tab = kho.worksheet(TAB)
    d = tab.get_all_values()
    C = tim_cot(d[0])
    if not C["tuGiai"]:                                       # như tgCot_: chưa có cột "Tự giải (AI)" thì tạo ở cuối
        C["tuGiai"] = len(d[0]) + 1
        if tab.col_count < C["tuGiai"]:
            tab.add_cols(C["tuGiai"] - tab.col_count)
        tab.update(range_name=a1(C["tuGiai"], 1), values=[[COT_TU_GIAI]], value_input_option="RAW")
    ds_model = X.doc_cau_hinh(kho)
    print("Model:", ", ".join(ds_model), "· Groq:", "có" if (G and G.co_khoa()) else "CHƯA CÓ KHOÁ (câu không có đáp án gốc sẽ để lượt sau)", flush=True)

    cho = []
    for r in d[1:]:
        r = r + [""] * (len(d[0]) + 2 - len(r))
        if not can_giai(r, C):
            continue
        cho.append({"ma": o(r, C, "maCau"), "noi_dung": o(r, C, "noiDung"), "phuong_an": o(r, C, "phuongAn"),
                    "goc": o(r, C, "dapAn"), "yccd": o(r, C, "yccd"), "dang": dang_tg(o(r, C, "dang"), o(r, C, "phuongAn")),
                    "link": tach_link(o(r, C, "linkAnh")), "anh": [], "k": []})
    if not (G and G.co_khoa()):                                # chưa có Groq: câu không hình, không đáp án gốc để lượt sau (không tốn lượt Gemini)
        bo = [x for x in cho if not x["goc"] and not x["link"]]
        cho = [x for x in cho if x["goc"] or x["link"]]
        if bo:
            print("⚠️ Chưa có GROQ_API_KEY: tạm bỏ qua %d câu chưa có đáp án gốc (cần máy giải bằng code + Groq)." % len(bo), flush=True)
    cho.sort(key=lambda x: 0 if not x["goc"] else 1)          # ưu tiên câu chưa có đáp án gốc
    print("Có %d câu chờ giải; lượt này giải tối đa %d câu." % (len(cho), TOI_DA_CAU), flush=True)
    cho = cho[:TOI_DA_CAU]

    tk = {"ghi": 0, "xem": 0, "loi": 0, "hoan": 0}
    het_han_muc = False
    for k in range(0, len(cho), LO):
        if not con_gio():
            print("⏸️ Hết thời gian lượt này.", flush=True); break
        lo = cho[k:k + LO]
        try:
            kq = giai_lo(lo, ds_model, drive)
        except X.HetHanMuc as e:
            print("⏸️ Hết hạn mức Gemini – dừng, lượt sau giải tiếp:", str(e)[:150], flush=True)
            het_han_muc = True
            break
        ghi = {m: v for m, v in kq.items() if not v.get("tam_hoan")}
        tk["hoan"] += len(kq) - len(ghi)
        tk["loi"] += sum(1 for v in ghi.values() if v.get("loi"))
        tk["xem"] += sum(1 for v in ghi.values() if not v.get("ok") and not v.get("loi"))
        tk["ghi"] += ghi_ket_qua(tab, C, ghi)
        print("📄 Lô %d: %d câu → %d ghi lời giải, %d cần thầy xem, %d để lượt sau" % (
            k // LO + 1, len(lo), sum(1 for v in ghi.values() if v.get("ok")),
            sum(1 for v in ghi.values() if not v.get("ok")), len(kq) - len(ghi)), flush=True)

    tom = "Lượt %s: %d câu ghi lời giải, %d cần thầy xem, %d lỗi, %d để lượt sau%s." % (
        X.bay_gio(), tk["ghi"], tk["xem"], tk["loi"], tk["hoan"], " – dừng vì hết hạn mức" if het_han_muc else "")
    print("📊 " + tom, flush=True)
    if Q:
        Q.ghi_sheet(kho)
    nhip(kho, tom)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write("da_ghi=%d\n" % tk["ghi"])


def nhip(kho, ghi_chu):
    try:
        t = kho.worksheet(X.TAB_AGENT)
        ten = t.col_values(1)
        luc = dt.datetime.now(X.TZ).strftime("%d/%m/%Y %H:%M")
        if TEN_AGENT in ten:
            dong = ten.index(TEN_AGENT) + 1
        else:
            dong = len(ten) + 1
            t.update(range_name="A%d:D%d" % (dong, dong), values=[[TEN_AGENT, "Miễn phí", "", 26]], value_input_option="USER_ENTERED")
        t.update(range_name="E%d" % dong, values=[[luc]], value_input_option="USER_ENTERED")
        t.update(range_name="G%d" % dong, values=[[ghi_chu[:300]]], value_input_option="RAW")
    except Exception as e:
        print("Không ghi được nhịp chạy:", e)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if Q:
            Q.ghi_sheet()
        raise
