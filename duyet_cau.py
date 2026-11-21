"""
duyet_cau.py – XƯỞNG DUYỆT CÂU 5 TẦNG (Python, GitHub Actions) – thay duyetCauTuDong() trong DuyetCau.gs của Kho chung.

Duyệt các câu "Chưa duyệt" trong tab NganHangCauHoi theo TỪNG FILE ĐỀ GỐC, chỉ "AI duyệt" khi có ÍT NHẤT
2 BẰNG CHỨNG ĐỘC LẬP cùng khớp:
  Tầng 1 – Luật bằng code (0 lượt Gemini): trùng câu, thiếu đề, đủ phương án/4 ý, đáp án đúng dạng, mã YCCĐ hợp lệ,
           công thức $…$ đóng mở đủ, câu nhắc tới hình mà không có mô tả hình.
  Tầng 2 – Đối chiếu hướng dẫn chấm (1 lượt/file, model chính, đọc FILE GỐC): đáp án theo HDC từng câu, BẢNG ĐÁP ÁN
           đầy đủ của file để code phát hiện ghép lệch dòng; lỗi nội dung, thiếu hình, ngoài CT 2018, mã YCCĐ.
  Tầng 3 – Đọc lại đề lần hai (1 lượt/file, model NHẸ): liệt kê mọi số liệu + đơn vị của từng câu trong file gốc;
           code so với nội dung đã lưu → bắt lỗi đọc nhầm số, mất số mũ, mất dấu.
  Tầng 4 – Giải độc lập bằng code (≈1 lượt/10 câu, KHÔNG cho xem đáp án): Gemini viết và chạy Python để giải;
           kiểm tra CHỈ MỘT phương án đúng (nhiều lựa chọn), từng ý (đúng/sai), đáp số + đơn vị (trả lời ngắn, tự luận).
  Tầng 5 – Thứ nguyên (0 lượt Gemini): pint so đơn vị đáp số máy giải với đơn vị trong hướng dẫn chấm / đáp án đã ghi.
Kết quả: AI duyệt · Cần người xem (ghi rõ lí do) · Loại – cùng cột, cùng cách ghi với DuyetCau.gs.
LƯU Ý: tắt lịch duyệt cũ của Apps Script (tatDuyetTuDong trong Kho chung) để hai bên không duyệt trùng. Câu giáo viên đã chọn
(Đã duyệt, Cần sửa, Loại…) không bị đụng tới. Mỗi thứ Hai ghi 10 câu "AI duyệt" ngẫu nhiên vào tab KiemTraNgauNhien
để giáo viên kiểm tra và đo độ chính xác thật.
Dùng lại các hàm của doc_de.py (kết nối Google, tải file gốc, gọi Gemini xoay vòng khoá miễn phí).

[21/11/2026] CHẠY SONG SONG ĐỂ NHANH HƠN, GIỮ NGUYÊN 100% CÁC TẦNG VÀ LUẬT XẾP LOẠI (DUYET_SONG_SONG = "true" mặc định; "false" → chạy lần lượt y như trước):
  • Trong mỗi file, tầng 2, tầng 3, tầng 4 và Groq được gửi CÙNG LÚC (bốn việc độc lập, không cái nào cần kết quả của cái kia);
    các lô 10 câu của tầng 4 cũng giải song song (tối đa DUYET_SO_LO_SONG_SONG lô, mặc định 3). Luật quyết định (quyet_dinh), tầng 1 và tầng 5 không đổi.
  • Tầng 4 cần biết model của tầng 2 để chọn model KHÁC: khi chạy song song dùng model chính trong CauHinh làm dự kiến
    (đúng trừ khi tầng 2 phải chuyển sang model dự phòng; trường hợp đó quyet_dinh đã tự xử lí "cùng một model" và Groq vẫn là bằng chứng khác hãng).
  • Tải trước file gốc kế tiếp từ Drive trong lúc đang duyệt file hiện tại.
  • doc_de.py giữ tổng số lượt gọi Gemini cùng lúc ≤ GEMINI_SONG_SONG (mặc định 3) và khoá trạng thái khoá API bằng khoá luồng.

[29/10/2026] TẦNG 4 THÊM LỜI GIẢI KHÁC HÃNG (Groq, groq_xuong.py), cũng KHÔNG cho xem đáp án:
  • GROQ_CHE_DO = "ghi_chu" (mặc định): Groq chỉ THÊM bằng chứng. Khi máy giải Gemini không giải được hoặc chỉ có một model Gemini,
    Groq khớp thì được tính là bằng chứng độc lập thứ hai. Groq giải khác thì chỉ ghi chú vào cột Kiểm tra, không đổi kết luận.
  • GROQ_CHE_DO = "chan": Groq giải khác các bằng chứng còn lại → câu chuyển "Cần người xem".
  • Không có GROQ_API_KEY hoặc Groq lỗi → chạy y như cũ.
Mỗi lượt gọi Gemini / Groq được ghi vào tab Quota_SuDung (dòng "xưởng …").

[29/10/2026] TẦNG 1 ĐỌC CHỈ MỤC CHỐNG TRÙNG (tab ChiMucTrung do chi_muc_trung.py dựng mỗi đêm, chỉ dùng khi cập nhật trong 3 ngày):
  so câu đang duyệt với các câu ĐÃ CÓ TỪ TRƯỚC trong kho (dòng phía trên).
  • Giống chữ ≥ 90% (gần như chép lại): TRUNG_CHE_DO = "ghi_chu" (mặc định) chỉ ghi chú; "chan" → "Cần người xem".
  • Giống dạng ≥ 85% nhưng khác số liệu: luôn chỉ ghi chú "cùng dạng, khác số liệu" (câu đổi số vẫn có ích).

[21/11/2026] LUẬT XẾP LOẠI MỚI (CHE_DO_DUYET = "moi" mặc định; "cu" → chạy y như trước ngày này):
  • LOẠI NGAY ở tầng 1 (0 lượt Gemini): trắc nghiệm không đủ 4 phương án A–D, hoặc đúng/sai không đủ 4 ý a–d.
  • THIẾU HDC / ĐÁP ÁN: máy tự giải rồi duyệt luôn khi hai lời giải độc lập khớp nhau (lập luận ở tầng 2 + chạy code ở tầng 4,
    cho phép cùng một model Gemini vì hai cách giải khác nhau; Groq vẫn là bằng chứng bổ sung). Áp dụng cả tự luận và câu vận dụng cao.
    Đáp án đã ghi sai dạng được coi như thiếu đáp án → máy giải lại. "Đáp số: …" trong lời giải được hiểu là số cuối.
  • "CẦN NGƯỜI XEM" CHỈ DÀNH CHO CÂU CÓ HÌNH mà máy và các model chưa thống nhất (hoặc thiếu hình để giải).
    Câu KHÔNG hình mà chưa thống nhất: KHONG_HINH_BAT_DONG = "loai" (mặc định) → Loại, lí do ghi ở cột Kiểm tra; "xem" → như cũ.
    Việc không liên quan đáp án (mã YCCĐ, từ khoá CT cũ, công thức $ lỗi, trùng gần) vẫn để "Cần người xem".
  • Gemini không đánh giá được một câu (không phải bất đồng): giữ "Chưa duyệt", không ghi, lượt sau làm lại.
  • "Ghép lệch dòng" chỉ còn là ghi chú: từng đáp án vẫn phải qua 2 bằng chứng, khớp thì tự sửa.
"""
import datetime as dt, json, os, random, re, sys, time
from concurrent.futures import ThreadPoolExecutor

import doc_de as X   # cùng thư mục: ket_noi, chuan_bi_tep, goi_gemini, doc_cau_hinh, doc_yccd, tu_khoa_ct_cu, CT_CU_MO_TA, HetHanMuc

try:
    import groq_xuong as G      # lời giải khác hãng ở tầng 4
except Exception:
    G = None
try:
    import quota_xuong as Q
except Exception:
    Q = None
GROQ_CHE_DO = os.environ.get("GROQ_CHE_DO", "ghi_chu").strip().lower()
TRUNG_CHE_DO = os.environ.get("TRUNG_CHE_DO", "ghi_chu").strip().lower()
CHE_DO_DUYET = os.environ.get("CHE_DO_DUYET", "moi").strip().lower()                    # [21/11] "cu" = như trước
KHONG_HINH_BAT_DONG = os.environ.get("KHONG_HINH_BAT_DONG", "loai").strip().lower()    # [21/11] câu không hình mà chưa thống nhất: loai | xem
MOI = CHE_DO_DUYET != "cu"
SONG_SONG = os.environ.get("DUYET_SONG_SONG", "true").strip().lower() not in ("false", "0", "no", "off", "tat", "tắt")   # [21/11] "false" = lần lượt như trước
try:
    SO_LO_SONG_SONG = max(1, int(float(os.environ.get("DUYET_SO_LO_SONG_SONG", "3") or 3)))                              # [21/11] số lô tầng 4 giải cùng lúc
except ValueError:
    SO_LO_SONG_SONG = 3

TAB_NH, TAB_MAU = "NganHangCauHoi", "KiemTraNgauNhien"
TT = {"CHUA": "Chưa duyệt", "DANG": "Đang duyệt (Python)", "AI": "AI duyệt", "XEM": "Cần người xem", "LOAI": "Loại"}
SAI_SO_DAP_AN = 0.005     # so đáp án với HDC (như DuyetCau.gs)
SAI_SO_MAY_GIAI = 0.02    # so đáp số máy giải bằng code
LO_GIAI = 10              # số câu mỗi lượt giải độc lập
TEN_AGENT = "Xưởng duyệt câu (Python)"
THOI_GIAN_TOI_DA_PHUT = float(os.environ.get("THOI_GIAN_TOI_DA_PHUT", "150"))
BAT_DAU = time.time()


def con_gio(du_tru=240):
    return time.time() - BAT_DAU < THOI_GIAN_TOI_DA_PHUT * 60 - du_tru


# ============================== TIỆN ÍCH SO ĐÁP ÁN (giống DuyetCau.gs) ==============================
def loai_dang(d):
    t = str(d or "").lower()
    if re.search(r"đúng|sai|ds", t): return "DS"
    if re.search(r"ngắn|tln", t): return "TLN"
    if re.search(r"tự luận|^tl$", t): return "TL"
    return "TN"


def tach_ds(s):
    kq = {}
    for m in re.finditer(r"([a-d])\s*\)?\s*[:.\-]?\s*(Đúng|Sai|Đ|S)(?![A-Za-zÀ-ỹ])", str(s or ""), re.I):
        kq[m.group(1).lower()] = "Đ" if m.group(2)[0].lower() == "đ" else "S"
    return kq


def lay_so(s):
    t = str(s or "")
    ds = [d for d in re.findall(r"(?i)đáp\s*số\s*[:=]?([^\n]*)", t) if re.search(r"\d", d)]   # [21/11] lời giải dài: lấy số sau "Đáp số"
    if ds: t = ds[-1]
    m = re.search(r"[-+]?\d+(?:[.,]\d+)?", re.sub(r"\s", "", t))
    return float(m.group(0).replace(",", ".")) if m else float("nan")


def dung_dang(loai, s):
    s = str(s or "").strip()
    if not s: return False
    if loai == "TN": return bool(re.fullmatch(r"[A-D]", re.sub(r"[.\s]", "", s), re.I))
    if loai == "DS": return len(tach_ds(s)) == 4
    if loai == "TLN": return lay_so(s) == lay_so(s)
    return True


def khop(loai, a, b, sai_so=SAI_SO_DAP_AN):
    if not a or not b: return False
    if loai == "TN":
        x = re.search(r"[A-D]", str(a).upper()); y = re.search(r"[A-D]", str(b).upper())
        return bool(x and y and x.group(0) == y.group(0))
    if loai == "DS":
        x, y = tach_ds(a), tach_ds(b)
        return len(x) == 4 and all(x.get(k) == y.get(k) for k in "abcd")
    p, q = lay_so(a), lay_so(b)
    if p != p or q != q: return str(a).strip() == str(b).strip()
    return abs(p) < 1e-9 if q == 0 else abs(p - q) <= sai_so * abs(q)


def chuan(loai, s):
    s = str(s or "").strip()
    if loai == "TN":
        m = re.search(r"\b([A-D])\b", s.upper()) or re.search(r"[A-D]", s.upper())
        return (m.group(1) if m.groups() else m.group(0)) if m else s
    if loai == "DS":
        d = tach_ds(s)
        return ", ".join("%s) %s" % (k, d[k]) for k in "abcd") if len(d) == 4 else s
    if loai == "TLN":
        n = lay_so(s)
        return s if n != n else ("%g" % n).replace(".", ",")
    return s


def van_tay(nd, pa):
    s = X.bo_dau(str(nd or "") + " " + str(pa or "")).replace(" ", "")
    return s if len(s) >= 40 else ""


def cac_so(s):
    """Mọi số trong chuỗi (bỏ chữ số đánh câu kiểu 'Câu 3', bỏ số 0/1 đứng một mình hay gặp ở đáp án)."""
    s = re.sub(r"(?i)câu\s*\d+|bài\s*\d+|\b[a-d]\)", " ", str(s or ""))
    s = s.replace("−", "-").replace("–", "-")
    out = []
    for m in re.finditer(r"\d+(?:[.,]\d+)?", s):
        try:
            out.append(float(m.group(0).replace(",", ".")))
        except ValueError:
            pass
    return out


def json_cuoi(text):
    """Khối JSON cuối cùng trong câu trả lời có chạy code."""
    ds = re.findall(r"```(?:json)?\s*([\[{][\s\S]*?[\]}])\s*```", text or "")
    for t in reversed(ds):
        try: return json.loads(t)
        except ValueError: continue
    m = re.search(r"(\[\s*\{[\s\S]*\}\s*\])", text or "")
    if m:
        try: return json.loads(m.group(1))
        except ValueError: pass
    return None


# ---- thứ nguyên ----
try:
    import pint
    _U = pint.UnitRegistry()
    for _dn in ("dioptre = 1/m = dp",):
        try: _U.define(_dn)
        except Exception: pass
except Exception:
    _U = None


def cung_thu_nguyen(a, b):
    """True/False nếu so được; None nếu không đọc được đơn vị."""
    if not _U or not a or not b: return None
    def doi(s):
        s = str(s).strip().replace("²", "^2").replace("³", "^3").replace("°C", "degC").replace("º", "°")
        s = s.replace("Ω", "ohm").replace("μ", "u").replace("µ", "u")
        return _U.parse_expression(s)
    try:
        return doi(a).dimensionality == doi(b).dimensionality
    except Exception:
        return None


def don_vi_trong(s):
    m = re.search(r"\d\s*([A-Za-zΩμµ°/·\^\d²³]+(?:\s*/\s*[A-Za-z\^\d²³]+)?)\s*$", str(s or "").strip())
    return m.group(1) if m else ""


# ============================== [21/11] ĐẾM PHƯƠNG ÁN · CÓ HÌNH · XẾP LOẠI ==============================
RE_NHAC_HINH = re.compile(r"(?i)\b(hình vẽ|như hình|hình bên|đồ thị (như|ở) hình|hình \d)")


def dem_phuong_an(loai, noi_dung, phuong_an):
    """Số phương án (TN: A–D) / số ý (DS: a–d) đang có. Đếm theo dòng HOẶC theo nhãn (kể cả nhiều phương án trên một dòng)
    và lấy số LỚN hơn → thà bỏ sót câu thiếu còn hơn loại nhầm câu đủ."""
    pa, nd = str(phuong_an or ""), str(noi_dung or "")
    dong = len([s for s in pa.split("\n") if s.strip()])
    mau = "ABCD" if loai == "TN" else "abcd"
    nhan = set(re.findall(r"(?:^|\s)[*_$(]*([%s])[*_$)]*\s*[.):]\s*\S" % mau, pa + "\n" + nd))
    return max(dong, len(nhan))


def co_hinh(x):
    """Câu có hình: có mô tả [Hình…] / [[DO_THI…]] hoặc nhắc tới hình trong đề."""
    van = x["noi_dung"] + " " + x["phuong_an"]
    return "[Hình" in van or "[[DO_THI" in van or bool(RE_NHAC_HINH.search(x["noi_dung"]))


def bat_dong(x, ly_do):
    """Nghi vấn do máy / các model CHƯA THỐNG NHẤT (khác với nghi vấn về mã YCCĐ, công thức, trùng…)."""
    x["nghi_van"].append(ly_do)
    x["bat_dong"].append(ly_do)


def xep_loai(x):
    """Trạng thái cuối của một câu. Chế độ mới: Loại = lỗi nặng; Cần người xem = câu CÓ HÌNH mà máy/model chưa thống nhất
    (hoặc nghi vấn không liên quan đáp án); câu không hình chưa thống nhất → KHONG_HINH_BAT_DONG."""
    if x["loi_nang"]: return TT["LOAI"]
    if not x["nghi_van"]: return TT["AI"]
    if not MOI or not x["bat_dong"]: return TT["XEM"]
    if x["co_hinh"] or KHONG_HINH_BAT_DONG == "xem": return TT["XEM"]
    x["ghi_chu"].append("Loại vì máy và các model chưa thống nhất đáp án, câu không có hình (đặt KHONG_HINH_BAT_DONG=xem nếu muốn GV xem)")
    return TT["LOAI"]


# ============================== TẦNG 1: LUẬT BẰNG CODE ==============================
def tang1(x, yccd):
    loai = loai_dang(x["dang"])
    if x.get("trung_voi"): x["loi_nang"].append("Trùng hẳn câu " + x["trung_voi"])
    if len(re.sub(r"\s", "", x["noi_dung"])) < 15: x["loi_nang"].append("Nội dung câu quá ngắn / thiếu đề")
    x["co_hinh"] = co_hinh(x)
    so_pa = dem_phuong_an(loai, x["noi_dung"], x["phuong_an"]) if loai in ("TN", "DS") else 4
    thieu = x["loi_nang"] if MOI else x["nghi_van"]          # [21/11] thiếu phương án / ý → Loại ngay (chế độ cũ: Cần người xem)
    if loai == "TN" and so_pa < 4: thieu.append("Thiếu phương án (%d/4)" % so_pa)
    if loai == "DS" and so_pa < 4: thieu.append("Thiếu ý đúng/sai (%d/4)" % so_pa)
    if x["dap_an"] and not dung_dang(loai, x["dap_an"]):
        if MOI:                                              # [21/11] đáp án sai dạng = như thiếu đáp án → máy giải lại
            x["ghi_chu"].append('Đáp án đã ghi sai dạng ("%s") – bỏ, máy giải lại' % x["dap_an"])
            x["dap_an"] = ""
        else:
            x["nghi_van"].append('Đáp án không đúng dạng: "%s"' % x["dap_an"])
    if not x["ma_yccd"]: x["nghi_van"].append("Chưa gắn mã YCCĐ")
    sai = [m for m in x["ma_yccd"] if m not in yccd]
    if sai: x["nghi_van"].append("Mã không có trong YCCD: " + ", ".join(sai))
    if (x["noi_dung"] + x["phuong_an"]).count("$") % 2: x["nghi_van"].append("Công thức $…$ không đóng mở đủ")
    if RE_NHAC_HINH.search(x["noi_dung"]) and "[Hình" not in x["noi_dung"]:
        bat_dong(x, "Câu nhắc tới hình nhưng không có mô tả hình")


def doc_chi_muc(kho):
    """Tab ChiMucTrung → {mã câu: [(mã giống, % chữ, % dạng), …]}; tab thiếu hoặc cũ hơn 3 ngày → {}."""
    try:
        v = kho.worksheet("ChiMucTrung").get_all_values()[1:]
    except Exception:
        return {}
    if not v:
        return {}
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", str((v[0] + [""] * 11)[10]))
    if not m or (dt.datetime.now(X.TZ).replace(tzinfo=None) - dt.datetime(int(m[3]), int(m[2]), int(m[1]))).days > 3:
        print("Chỉ mục chống trùng chưa có hoặc đã cũ – bỏ qua.", flush=True)
        return {}
    so = lambda s: float(str(s).replace(",", ".")) if re.match(r"^\s*[\d.,]+\s*$", str(s)) else 0
    kq = {}
    for r in v:
        r = (r + [""] * 11)[:11]
        kq[r[0].strip()] = [(r[k].strip(), so(r[k + 1]), so(r[k + 2])) for k in (1, 4, 7) if r[k].strip()]
    return kq


def tang1_trung(x, chi_muc, vi_tri):
    for ma, chu, dang in chi_muc.get(x["ma"], []):
        if vi_tri.get(ma, 10 ** 9) >= x["dong"] or x.get("trung_voi") == ma:
            continue                                   # chỉ so với câu có từ trước; trùng hẳn đã xử lí ở tầng 1
        if chu >= 90:
            (x["nghi_van"] if TRUNG_CHE_DO == "chan" else x["ghi_chu"]).append("Gần như trùng câu %s (giống chữ %d%%)" % (ma, chu))
            return
        if dang >= 85:
            x["ghi_chu"].append("Cùng dạng với câu %s, khác số liệu (giống dạng %d%%)" % (ma, dang))
            return


# ============================== TẦNG 2: HƯỚNG DẪN CHẤM ==============================
SCHEMA_T2 = {"type": "OBJECT", "properties": {
    "bang_dap_an": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
        "so_cau": {"type": "STRING"}, "dap_an": {"type": "STRING"}}, "required": ["so_cau", "dap_an"]}},
    "ket_qua": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
        "ma_cau": {"type": "STRING"}, "co_hdc": {"type": "BOOLEAN"}, "dap_an_hdc": {"type": "STRING"}, "tu_giai": {"type": "STRING"},
        "loi_noi_dung": {"type": "BOOLEAN"}, "thieu_hinh": {"type": "BOOLEAN"}, "ma_yccd_hop_li": {"type": "BOOLEAN"},
        "ma_yccd_goi_y": {"type": "STRING"}, "ngoai_ct2018": {"type": "BOOLEAN"}, "ly_do_ct": {"type": "STRING"}, "ghi_chu": {"type": "STRING"}},
        "required": ["ma_cau", "co_hdc", "loi_noi_dung", "ma_yccd_hop_li", "ngoai_ct2018"]}}},
    "required": ["bang_dap_an", "ket_qua"]}


def tang2(tep, ds, yccd, cac_model):
    du_lieu = [{"ma_cau": x["ma"], "vi_tri": x["vi_tri"], "dang": x["dang"], "muc_do": x["muc_do"], "noi_dung": x["noi_dung"][:1500],
                "phuong_an": x["phuong_an"][:800], "dap_an_da_ghi": x["dap_an"],
                "ma_yccd": [m + ": " + yccd.get(m, "(không có)") for m in x["ma_yccd"]]} for x in ds]
    loi_nhan = (
        "Bạn là giáo viên Vật lí THPT đang duyệt ngân hàng câu hỏi theo chương trình GDPT 2018 (sách Kết nối tri thức).\n"
        + ("File đính kèm là ĐỀ GỐC của các câu dưới đây (có thể kèm đáp án / hướng dẫn chấm).\n" if tep else "Không có file gốc.\n")
        + "1) bang_dap_an: chép LẠI NGUYÊN BẢNG ĐÁP ÁN / HƯỚNG DẪN CHẤM của file gốc, mọi câu theo đúng số câu trong file "
          "(nhiều lựa chọn: một chữ A-D; đúng/sai: \"a) Đ, b) S, c) Đ, d) S\"; trả lời ngắn: một con số; tự luận: đáp số cuối). "
          "File không có đáp án thì để mảng rỗng.\n"
        + "2) ket_qua: với MỖI câu bên dưới: co_hdc, dap_an_hdc (đáp án của chính câu đó theo HDC, đối chiếu NỘI DUNG chứ không chỉ số câu); "
          "tu_giai (chỉ khi không có HDC: tự giải cẩn thận rồi ghi ĐÁP ÁN CUỐI theo đúng khuôn của bang_dap_an: một chữ A-D / "
          "\"a) Đ, b) S, c) Đ, d) S\" / một con số kèm đơn vị, không viết lời giải dài); loi_noi_dung (đề chép sai/thiếu dữ kiện đến mức không giải được); "
          "thieu_hinh (CHỈ khi câu cần hình mà mô tả [Hình: …] không đủ để giải); ngoai_ct2018 (kiến thức không thuộc CT 2018, kể cả "
          "các nội dung chương trình 2006: " + X.CT_CU_MO_TA + " – ghi ly_do_ct); ma_yccd_hop_li (false nếu mã gán không khớp; "
          "ma_yccd_goi_y là MỘT mã đúng hơn nếu chắc chắn); ghi_chu tối đa 120 kí tự khi có vấn đề.\n\nCÁC CÂU:\n"
        + json.dumps(du_lieu, ensure_ascii=False))
    parts = []
    if tep:
        import base64
        parts.append({"inline_data": {"mime_type": tep["mime"], "data": base64.b64encode(tep["data"]).decode()}})
    parts.append({"text": loi_nhan})
    data, model = X.goi_gemini({"contents": [{"role": "user", "parts": parts}],
                                "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA_T2,
                                                     "temperature": 0.1, "maxOutputTokens": 30000}}, cac_model)
    j = json.loads("".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]))
    return {str(g["ma_cau"]): g for g in j.get("ket_qua", [])}, j.get("bang_dap_an", []), model


def kiem_lech_dong(ds, bang):
    """Bảng đáp án file gốc vs đáp án đã ghi (câu nhiều lựa chọn): khớp đúng số câu hay khớp hơn khi dịch ±1, ±2 câu?"""
    if len(bang) < 4: return ""
    theo_so = {}
    for b in bang:
        n = re.search(r"\d+", str(b.get("so_cau", "")))
        if n: theo_so[int(n.group(0))] = str(b.get("dap_an", ""))
    tn = [(int(re.search(r"\d+", x["vi_tri"]).group(0)), x["dap_an"]) for x in ds
          if loai_dang(x["dang"]) == "TN" and re.search(r"\d+", x["vi_tri"] or "") and x["dap_an"]]
    if len(tn) < 4: return ""
    def ti_le(lech):
        co = [(n, a) for n, a in tn if (n + lech) in theo_so]
        return (sum(khop("TN", a, theo_so[n + lech]) for n, a in co) / len(co)) if co else 0
    goc = ti_le(0)
    tot = max((ti_le(k), k) for k in (-2, -1, 1, 2))
    if goc < 0.6 and tot[0] >= 0.85:
        return "Đáp án đã ghi có vẻ GHÉP LỆCH %+d câu so với bảng đáp án gốc (khớp %d%% khi dịch, %d%% khi không dịch)" % (
            tot[1], round(tot[0] * 100), round(goc * 100))
    return ""


# ============================== TẦNG 3: ĐỌC LẠI SỐ LIỆU (MODEL NHẸ) ==============================
SCHEMA_T3 = {"type": "OBJECT", "properties": {"ket_qua": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "ma_cau": {"type": "STRING"}, "so_lieu": {"type": "ARRAY", "items": {"type": "STRING"}}}, "required": ["ma_cau", "so_lieu"]}}},
    "required": ["ket_qua"]}


def tang3(tep, ds, cac_model):
    if not tep: return {}
    nhe = [m for m in cac_model if "lite" in m] + [m for m in cac_model if "lite" not in m]
    import base64
    du_lieu = [{"ma_cau": x["ma"], "vi_tri": x["vi_tri"], "dau_cau": x["noi_dung"][:120]} for x in ds]
    loi_nhan = ("Đọc ĐỀ GỐC đính kèm. Với mỗi câu dưới đây (nhận ra bằng vị trí và phần đầu câu), liệt kê NGUYÊN VĂN mọi số liệu "
                "xuất hiện trong ĐỀ BÀI và các PHƯƠNG ÁN của câu đó, mỗi số kèm đơn vị, số mũ, dấu (ví dụ \"2,5 kg\", \"-3 μC\", "
                "\"10^-3 m\", \"30°\"). Không tính toán, không bỏ sót, không thêm số không có trong đề.\nCÁC CÂU:\n"
                + json.dumps(du_lieu, ensure_ascii=False))
    data, _ = X.goi_gemini({"contents": [{"role": "user", "parts": [
        {"inline_data": {"mime_type": tep["mime"], "data": base64.b64encode(tep["data"]).decode()}}, {"text": loi_nhan}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA_T3, "temperature": 0, "maxOutputTokens": 12000}}, nhe)
    j = json.loads("".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]))
    return {str(g["ma_cau"]): g.get("so_lieu", []) for g in j.get("ket_qua", [])}


def so_lieu_lech(x, so_lieu_goc):
    """Số trong đề gốc mà bản lưu không có (sai số 0,1%; số mũ 10^-n so cả n)."""
    luu = cac_so(x["noi_dung"] + " " + x["phuong_an"])
    thieu = []
    for s in so_lieu_goc:
        for v in cac_so(s):
            if v in (0, 1) or any(abs(v - u) <= 1e-3 * max(abs(v), 1e-9) for u in luu):
                continue
            thieu.append(s)
            break
    return thieu[:4]


# ============================== TẦNG 4: GIẢI ĐỘC LẬP BẰNG CODE ==============================
def _giai_mot_lo(lo, thu_tu):
    """Một lô ≤ LO_GIAI câu → ({mã câu: kết quả}, model đã dùng). Không đụng biến chung nên chạy song song được."""
    du_lieu = [{"ma_cau": x["ma"], "dang": x["dang"], "noi_dung": x["noi_dung"][:1500], "phuong_an": x["phuong_an"][:800]} for x in lo]
    loi_nhan = (
        "Bạn là học sinh giỏi Vật lí. GIẢI ĐỘC LẬP từng câu dưới đây. BẮT BUỘC dùng công cụ chạy code Python để tính mọi phép tính số "
        "(không tính nhẩm). Với câu nhiều lựa chọn: xét LẦN LƯỢT từng phương án A, B, C, D và ghi mọi phương án đúng vào phuong_an_dung. "
        "Với câu đúng/sai: xét từng ý a, b, c, d. Với câu trả lời ngắn / tự luận: đáp số cuối và đơn vị SI.\n"
        "CUỐI CÙNG trả về MỘT khối ```json``` là mảng: [{\"ma_cau\": \"…\", \"phuong_an_dung\": [\"B\"], "
        "\"y_ds\": {\"a\": \"Đ\", \"b\": \"S\", \"c\": \"Đ\", \"d\": \"S\"}, \"dap_so\": 2.02, \"don_vi\": \"s\", \"tu_tin\": \"cao|vừa|thấp\"}] "
        "(bỏ trường không dùng; dap_so là số, dấu chấm thập phân).\nCÁC CÂU:\n" + json.dumps(du_lieu, ensure_ascii=False))
    payload = {"contents": [{"role": "user", "parts": [{"text": loi_nhan}]}], "tools": [{"code_execution": {}}],
               "generationConfig": {"temperature": 0.2, "maxOutputTokens": 30000}}
    data, model_dung = X.goi_gemini(payload, thu_tu)
    text = "".join(p.get("text", "") for p in (data.get("candidates") or [{}])[0].get("content", {}).get("parts", []))
    return {str(g["ma_cau"]): g for g in (json_cuoi(text) or []) if isinstance(g, dict) and g.get("ma_cau")}, model_dung


def tang4(ds, cac_model, model_tang2):
    """Không cho xem đáp án. Ưu tiên model KHÁC tầng 2, không phải lite.
    [21/11] Các lô giải song song khi SONG_SONG; kết quả gộp theo đúng thứ tự lô, model_dung = model của lô cuối như trước."""
    thu_tu = sorted([m for m in cac_model if m != model_tang2], key=lambda m: "lite" in m) + [model_tang2]
    cac_lo = [ds[k:k + LO_GIAI] for k in range(0, len(ds), LO_GIAI)]
    if SONG_SONG and len(cac_lo) > 1:
        with ThreadPoolExecutor(max_workers=min(SO_LO_SONG_SONG, len(cac_lo))) as ex:
            ket_qua = list(ex.map(lambda lo: _giai_mot_lo(lo, thu_tu), cac_lo))
    else:
        ket_qua = [_giai_mot_lo(lo, thu_tu) for lo in cac_lo]
    kq, model_dung = {}, ""
    for k, m in ket_qua:
        kq.update(k)
        model_dung = m
    return kq, model_dung


def chay_cac_tang(tep, can_ai, yccd, cac_model):
    """[21/11] Chạy tầng 2, 3, 4 và Groq của MỘT file. Trả (g2, bang, model2, so_lieu, g4, model4, g5, model5).
    Lỗi xử lí đúng như bản lần lượt: tầng 2 / tầng 4 lỗi → ném lên (file để lượt sau); tầng 3 lỗi thường → bỏ qua, HetHanMuc → ném lên; Groq tự nuốt lỗi."""
    def tang3_an_toan():
        try:
            return tang3(tep, can_ai, cac_model)
        except X.HetHanMuc:
            raise
        except Exception as e:                                # phần phụ: lỗi thì cảnh báo, việc chính vẫn chạy
            print("  Tầng 3 lỗi (bỏ qua):", str(e)[:100], flush=True)
            return {}
    if not SONG_SONG:
        g2, bang, model2 = tang2(tep, can_ai, yccd, cac_model)
        so_lieu = tang3_an_toan()
        g4, model4 = tang4(can_ai, cac_model, model2)
        g5, model5 = tang4_groq(can_ai)
        return g2, bang, model2, so_lieu, g4, model4, g5, model5
    with ThreadPoolExecutor(max_workers=4) as ex:
        f2 = ex.submit(tang2, tep, can_ai, yccd, cac_model)
        f3 = ex.submit(tang3_an_toan)
        f4 = ex.submit(tang4, can_ai, cac_model, cac_model[0])      # model tầng 2 dự kiến = model chính
        f5 = ex.submit(tang4_groq, can_ai)
        g2, bang, model2 = f2.result()
        so_lieu = f3.result()
        g4, model4 = f4.result()
        g5, model5 = f5.result()
    return g2, bang, model2, so_lieu, g4, model4, g5, model5


def mo_tep_goc(drive, fid):
    """Tải file gốc (None nếu không có / bỏ qua / lỗi) – lỗi thì cảnh báo, tầng 1 + luật vẫn chạy như cũ."""
    if fid == "khong_ro":
        return None
    try:
        tep = X.chuan_bi_tep(drive, fid)
        return None if tep.get("bo_qua") else tep
    except Exception as e:
        print("  Không mở được file gốc:", str(e)[:100], flush=True)
        return None


def lay_tep_goc(fid, tep_cho, drive):
    """Lấy file gốc đã được tải trước (nếu có), không thì tải ngay."""
    f = tep_cho.pop(fid, None)
    return f.result() if f is not None else mo_tep_goc(drive, fid)


def tang4_groq(ds):
    """Groq (khác hãng) giải độc lập, không xem đáp án. Trả ({mã câu: đáp án}, model); không có khoá / lỗi → ({}, "")."""
    if not G or not G.co_khoa():
        return {}, ""
    try:
        return G.giai_lo([{"ma": x["ma"], "dang": loai_dang(x["dang"]), "noi_dung": x["noi_dung"], "phuong_an": x["phuong_an"]} for x in ds])
    except Exception as e:
        print("  Groq lỗi (bỏ qua):", str(e)[:120], flush=True)
        return {}, ""


def dap_an_may(loai, g):
    if not g: return ""
    if loai == "TN":
        pa = [str(p).strip().upper()[:1] for p in (g.get("phuong_an_dung") or []) if str(p).strip()]
        return pa[0] if len(pa) == 1 else ""
    if loai == "DS":
        y = g.get("y_ds") or {}
        return ", ".join("%s) %s" % (k, "Đ" if str(y.get(k, "")).upper().startswith("Đ") or str(y.get(k, "")).upper().startswith("D") else "S")
                         for k in "abcd") if len(y) == 4 else ""
    v = g.get("dap_so")
    try: return ("%g" % float(v)).replace(".", ",")
    except (TypeError, ValueError): return ""


# ============================== QUYẾT ĐỊNH ==============================
def quyet_dinh(x, g2, so_lieu, g4, model2, model4, yccd, g5="", model5=""):
    loai = loai_dang(x["dang"])
    gq = chuan(loai, g5) if g5 else ""                                     # đáp án Groq (khác hãng)
    ten_g = (model5 or "groq").split("/")[-1]
    if not g2:
        if MOI:                                                            # [21/11] chưa đánh giá được ≠ bất đồng → làm lại lượt sau
            x["hoan"] = True; return
        x["nghi_van"].append("Gemini chưa đánh giá được câu này"); return
    if g2.get("loi_noi_dung"): x["loi_nang"].append("Lỗi nội dung: " + (g2.get("ghi_chu") or "đề không đọc được / thiếu dữ kiện"))
    if g2.get("ngoai_ct2018"):
        x["loi_nang"].append("Ngoài chương trình 2018" + (": " + g2["ly_do_ct"] if g2.get("ly_do_ct") else "")); return
    tk = X.tu_khoa_ct_cu(x["noi_dung"], x["phuong_an"])
    if tk: x["nghi_van"].append('Có từ khoá nội dung chương trình cũ ("%s") – GV xác nhận thuộc CT 2018' % tk)
    if g2.get("thieu_hinh"):
        x["co_hinh"] = True
        bat_dong(x, "Thiếu dữ kiện khi không có hình gốc")
    if g2.get("ma_yccd_hop_li") is False:
        gy = str(g2.get("ma_yccd_goi_y") or "").strip().upper()
        if gy and gy in yccd: x["sua"]["ma"] = gy; x["ghi_chu"].append("Sửa mã YCCĐ %s → %s" % (", ".join(x["ma_yccd"]), gy))
        else: x["nghi_van"].append("Mã YCCĐ có thể chưa đúng" + (" (%s)" % g2["ghi_chu"] if g2.get("ghi_chu") else ""))
    # tầng 3
    lech = so_lieu_lech(x, so_lieu) if so_lieu else []
    if lech: bat_dong(x, "Đọc lại đề gốc thấy số liệu chưa có trong bản lưu: " + "; ".join(lech))
    # tầng 4
    may = dap_an_may(loai, g4)
    if loai == "TN" and g4 and len(g4.get("phuong_an_dung") or []) > 1:
        bat_dong(x, "Máy giải thấy %d phương án cùng đúng: %s" % (len(g4["phuong_an_dung"]), ", ".join(g4["phuong_an_dung"])))
    if g4 and str(g4.get("tu_tin", "")).lower().startswith("thấp"): bat_dong(x, "Máy giải không chắc chắn")
    hdc = chuan(loai, g2.get("dap_an_hdc")) if g2.get("co_hdc") and g2.get("dap_an_hdc") else ""
    # tầng 5
    if loai in ("TLN", "TL") and g4 and g4.get("don_vi"):
        dv_ss = don_vi_trong(g2.get("dap_an_hdc") or x["dap_an"])
        if cung_thu_nguyen(g4["don_vi"], dv_ss) is False:
            bat_dong(x, "Đơn vị không cùng thứ nguyên: máy giải %s, đáp án ghi %s" % (g4["don_vi"], dv_ss))
    ss = SAI_SO_MAY_GIAI
    ten2 = " (%s + %s)" % (model2.replace("gemini-", ""), (model4 or "?").replace("gemini-", ""))
    def groq_khop(ref): return bool(gq and ref and khop(loai, gq, ref, ss))
    def groq_lech(ref): return bool(gq and ref and not khop(loai, gq, ref, ss))
    def ghi_groq(ref):          # gọi khi kết luận đã có đủ bằng chứng; trả False nếu chế độ "chan" phải dừng
        if groq_khop(ref):
            x["ghi_chu"].append("Groq (%s, khác hãng) cũng ra %s" % (ten_g, ref)); return True
        if groq_lech(ref):
            if GROQ_CHE_DO == "chan":
                bat_dong(x, "Groq (%s, khác hãng) giải %s, khác %s" % (ten_g, gq, ref)); return False
            x["ghi_chu"].append("Groq (%s) giải %s – chỉ ghi chú" % (ten_g, gq))
        return True
    if loai == "TL" and (hdc or not MOI):      # [21/11] chế độ mới: tự luận không HDC đi tiếp xuống nhánh "máy tự giải" như các dạng khác
        if not hdc: x["nghi_van"].append("Câu tự luận không có hướng dẫn chấm gốc"); return
        if may and khop("TLN", may, hdc, ss):
            if ghi_groq(hdc): x["ghi_chu"].append("HDC gốc và máy giải bằng code cùng đáp số" + ten2)
        elif may: bat_dong(x, "Đáp số HDC %s, máy giải %s" % (hdc, may) + (", Groq %s" % gq if gq else ""))
        elif gq and khop("TLN", gq, hdc, ss): x["ghi_chu"].append("HDC gốc và Groq (%s, khác hãng) cùng đáp số" % ten_g)
        else: bat_dong(x, "Chỉ có HDC gốc, máy chưa giải được để đối chiếu" + (" (Groq ra %s)" % gq if gq else ""))
        return
    if hdc:                                    # bằng chứng 1 = HDC gốc; bằng chứng 2 = máy giải bằng code
        if may and khop(loai, may, hdc, ss):
            if not ghi_groq(hdc): return
            if not khop(loai, hdc, x["dap_an"]):
                x["sua"]["dap_an"] = hdc
                x["ghi_chu"].append('Sửa đáp án "%s" → "%s": HDC gốc và máy giải cùng ra' % (x["dap_an"], hdc))
            else:
                x["ghi_chu"].append("Đáp án khớp HDC gốc và máy giải bằng code" + ten2)
        elif may:
            bat_dong(x, "HDC gốc %s, máy giải %s – cần xem" % (hdc, may) + (" (Groq ra %s)" % gq if gq else ""))
        elif groq_khop(hdc):                    # máy Gemini chưa giải được: Groq khác hãng là bằng chứng thứ hai
            if not khop(loai, hdc, x["dap_an"]):
                x["sua"]["dap_an"] = hdc
                x["ghi_chu"].append('Sửa đáp án "%s" → "%s": HDC gốc và Groq (%s) cùng ra' % (x["dap_an"], hdc, ten_g))
            else:
                x["ghi_chu"].append("Đáp án khớp HDC gốc và Groq (%s, khác hãng)" % ten_g)
        else:
            bat_dong(x, "Chỉ có HDC gốc (%s), máy chưa giải được để đối chiếu" % hdc + (" (Groq ra %s)" % gq if gq else ""))
        return
    # không có HDC: bằng chứng 1 = model tầng 2 tự giải (lập luận); bằng chứng 2 = máy giải bằng code (tầng 4)
    # [21/11] chế độ mới: hai cách giải khớp nhau là đủ, kể cả cùng một model Gemini; áp dụng cả tự luận
    lss = "TLN" if loai == "TL" else loai                                  # tự luận so đáp số cuối như trả lời ngắn
    tu = chuan(lss, g2.get("tu_giai"))
    cung_model = (not model4) or model4 == model2
    hai_gemini = bool(tu and may and khop(lss, tu, may, ss) and (MOI or not cung_model))
    tu_va_groq = bool(tu and groq_khop(tu) and (not may or khop(lss, tu, may, ss)))
    if hai_gemini:
        if cung_model: ten2 = " (%s: lập luận + chạy code)" % model2.replace("gemini-", "")
        if not ghi_groq(tu): return
    elif tu_va_groq:                            # Gemini tầng 2 + Groq khác hãng cùng ra (máy giải trống hoặc cùng model)
        ten2 = " (%s + groq %s)" % (model2.replace("gemini-", ""), ten_g)
    elif not (tu and may and khop(lss, tu, may, ss)):
        bat_dong(x, 'Không có HDC; hai lời giải độc lập chưa thống nhất (%s / %s%s)' % (tu or "?", may or "?", " / Groq " + gq if gq else "")); return
    else:
        bat_dong(x, "Không có HDC; chỉ kiểm được bằng một model"); return
    if not x["dap_an"]:
        if loai == "TL":                         # tự luận: ghi đáp số cuối kèm đơn vị máy giải
            dv = (g4 or {}).get("don_vi")
            x["sua"]["dap_an"] = "Đáp số: %s%s" % (tu, " " + str(dv) if dv else "")
        else:
            x["sua"]["dap_an"] = tu
        x["ghi_chu"].append('Không có đáp án gốc; 2 lời giải độc lập cùng ra "%s"%s' % (tu, ten2))
    elif khop(lss, tu, x["dap_an"], ss):
        x["ghi_chu"].append("Không có HDC; 2 lời giải độc lập khớp đáp án" + ten2)
    else:
        bat_dong(x, 'Đáp án "%s" khác 2 lời giải độc lập "%s"' % (x["dap_an"], tu)); return
    if re.search(r"(?i)cao", x["muc_do"]):
        if MOI: x["ghi_chu"].append("Câu vận dụng cao không có HDC – đáp án do máy giải, nên kiểm tra ngẫu nhiên")
        else: x["nghi_van"].append("Câu vận dụng cao không có hướng dẫn chấm")


# ============================== CHẠY ==============================
def main():
    gc, drive, sa = X.ket_noi()
    print("Tài khoản dịch vụ:", sa, flush=True)
    kho = gc.open_by_key(X.ID_KHO_CHUNG)
    tab = kho.worksheet(TAB_NH)
    d = tab.get_all_values()
    td = d[0]
    c = {t: td.index(t) for t in ["Mã câu", "Mã YCCĐ", "Mã bài", "Lớp", "Mức độ", "Dạng", "Nội dung", "Phương án", "Đáp án",
                                   "Tên file", "File ID", "Kiểm tra", "Trạng thái duyệt"] if t in td}
    yccd = {}
    for r in kho.worksheet(X.TAB_YCCD).get_all_values()[1:]:
        if r and r[0].strip(): yccd[r[0].strip()] = (r + [""] * 7)[6][:200]
    cac_model = X.doc_cau_hinh(kho)
    print("Model:", ", ".join(cac_model), flush=True)

    da_gap, nhom = {}, {}
    chi_muc = doc_chi_muc(kho)
    vi_tri = {r[c["Mã câu"]].strip(): i for i, r in enumerate(d[1:], start=2) if len(r) > c["Mã câu"]}
    for i, r in enumerate(d[1:], start=2):
        r = r + [""] * (len(td) - len(r))
        tt = r[c["Trạng thái duyệt"]].strip() or TT["CHUA"]
        vt = van_tay(r[c["Nội dung"]], r[c["Phương án"]])
        if tt not in (TT["CHUA"], TT["DANG"]):
            if vt and tt != TT["LOAI"] and vt not in da_gap: da_gap[vt] = r[c["Mã câu"]]
            continue
        x = {"dong": i, "ma": r[c["Mã câu"]], "dang": r[c["Dạng"]], "muc_do": r[c["Mức độ"]], "noi_dung": r[c["Nội dung"]],
             "phuong_an": r[c["Phương án"]], "dap_an": r[c["Đáp án"]].strip(), "kiem_tra_cu": r[c["Kiểm tra"]],
             "ma_yccd": [m for m in re.split(r"[,;\s]+", r[c["Mã YCCĐ"]]) if m],
             "vi_tri": (re.search(r"\(câu\s*([^)]*)\)", r[c["Tên file"]]) or [None, ""])[1],
             "loi_nang": [], "nghi_van": [], "ghi_chu": [], "sua": {}, "bat_dong": [], "co_hinh": False, "hoan": False}
        if vt and vt in da_gap: x["trung_voi"] = da_gap[vt]
        elif vt: da_gap[vt] = x["ma"]
        nhom.setdefault(r[c["File ID"]] or "khong_ro", []).append(x)
    tong = sum(len(v) for v in nhom.values())
    print("Có %d câu chờ duyệt trong %d file." % (tong, len(nhom)), flush=True)

    ngay = dt.datetime.now(X.TZ).strftime("%d/%m")
    thong_ke = {"ai": 0, "xem": 0, "loai": 0, "hoan": 0}
    het_han_muc = False
    cac_file = list(nhom.items())
    tep_cho, tai_truoc, drive_tai = {}, None, None
    if SONG_SONG:                                                   # [21/11] tải trước file gốc kế tiếp bằng kết nối Drive riêng (httplib2 không an toàn đa luồng)
        try:
            _, drive_tai, _ = X.ket_noi()
            tai_truoc = ThreadPoolExecutor(max_workers=1)
        except Exception as e:
            print("  Không bật được tải trước file gốc (bỏ qua):", str(e)[:100], flush=True)

    def hen_tai(i):
        if tai_truoc and 0 <= i < len(cac_file) and cac_file[i][0] != "khong_ro" and cac_file[i][0] not in tep_cho:
            tep_cho[cac_file[i][0]] = tai_truoc.submit(mo_tep_goc, drive_tai, cac_file[i][0])

    for idx, (fid, ds) in enumerate(cac_file):
        if not con_gio():
            print("⏸️ Hết thời gian lượt này.", flush=True); break
        t0 = time.time()
        hen_tai(idx + 1)
        for x in ds:
            tang1(x, yccd)
            if chi_muc: tang1_trung(x, chi_muc, vi_tri)
        can_ai = [x for x in ds if not x["loi_nang"]]
        try:
            if can_ai:
                tep = lay_tep_goc(fid, tep_cho, drive)
                g2, bang, model2, so_lieu, g4, model4, g5, model5 = chay_cac_tang(tep, can_ai, yccd, cac_model)
                lech = kiem_lech_dong(can_ai, bang)
                if lech:
                    for x in can_ai:
                        if loai_dang(x["dang"]) == "TN": (x["ghi_chu"] if MOI else x["nghi_van"]).append(lech)   # [21/11] chỉ ghi chú
                for x in can_ai:
                    quyet_dinh(x, g2.get(x["ma"]), so_lieu.get(x["ma"], []), g4.get(x["ma"]), model2, model4, yccd,
                               g5.get(x["ma"], ""), model5)
        except X.HetHanMuc as e:
            print("⏸️ Hết hạn mức Gemini – dừng, lượt sau duyệt tiếp:", str(e)[:150], flush=True)
            het_han_muc = True
            break
        except Exception as e:
            print("⚠️ File %s lỗi, để lượt sau: %s" % (fid, str(e)[:200]), flush=True)
            continue
        # ghi kết quả file này – tìm dòng theo MÃ CÂU ngay trước khi ghi (không dùng số dòng đã nhớ từ lúc đọc)
        cap = []
        ma_cot = tab.col_values(c["Mã câu"] + 1)
        vt_hien_tai = {v.strip(): i + 1 for i, v in enumerate(ma_cot) if i > 0 and v.strip()}
        for x in ds:
            dong_hien_tai = vt_hien_tai.get(x["ma"])
            if not dong_hien_tai:
                continue
            if x["hoan"]:                                   # [21/11] Gemini chưa đánh giá được: giữ "Chưa duyệt", lượt sau làm lại
                thong_ke["hoan"] += 1
                continue
            tt = xep_loai(x)
            ghi = "; ".join(x["loi_nang"] + x["nghi_van"] + x["ghi_chu"]) or "Đạt"
            kt = (x["kiem_tra_cu"] + " | " if x["kiem_tra_cu"] else "") + "[5 tầng %s] %s" % (ngay, ghi)
            col = lambda t, dh=dong_hien_tai: gspread_a1(c[t] + 1, dh)
            cap += [{"range": col("Trạng thái duyệt"), "values": [[tt]]}, {"range": col("Kiểm tra"), "values": [[kt[:45000]]]}]
            if "dap_an" in x["sua"]: cap.append({"range": col("Đáp án"), "values": [[x["sua"]["dap_an"]]]})
            if "ma" in x["sua"]:
                m = x["sua"]["ma"]
                cap += [{"range": col("Mã YCCĐ"), "values": [[m]]}, {"range": col("Mã bài"), "values": [["-".join(m.split("-")[:2])]]},
                        {"range": col("Lớp"), "values": [[int(m[2:4])]]}]
            thong_ke["ai" if tt == TT["AI"] else "loai" if tt == TT["LOAI"] else "xem"] += 1
        if cap: tab.batch_update(cap, value_input_option="RAW")
        print("📄 File %s: %d câu (%d AI duyệt) trong %d giây" % (fid[:12], len(ds),
              sum(1 for x in ds if not x["loi_nang"] and not x["nghi_van"]), time.time() - t0), flush=True)

    if tai_truoc:
        tai_truoc.shutdown(wait=False, cancel_futures=True)
    mau_ngau_nhien(kho, d, c)
    tom = "Lượt %s: %d AI duyệt, %d cần người xem, %d loại%s." % (X.bay_gio(), thong_ke["ai"], thong_ke["xem"], thong_ke["loai"],
                                                                 (" (%d câu để lượt sau)" % thong_ke["hoan"] if thong_ke["hoan"] else "") + (" – dừng vì hết hạn mức" if het_han_muc else ""))
    print("📊 " + tom)
    if Q:
        Q.ghi_sheet(kho)
    ghi_nhip(kho, tom)


def gspread_a1(cot, dong):
    s = ""
    while cot:
        cot, r = divmod(cot - 1, 26)
        s = chr(65 + r) + s
    return "%s%d" % (s, dong)


def mau_ngau_nhien(kho, d, c):
    """Thứ Hai: ghi 10 câu AI duyệt ngẫu nhiên để giáo viên kiểm tra (đo độ chính xác thật)."""
    bay = dt.datetime.now(X.TZ)
    if bay.weekday() != 0: return
    import gspread
    try: tab = kho.worksheet(TAB_MAU)
    except gspread.WorksheetNotFound:
        tab = kho.add_worksheet(TAB_MAU, rows=500, cols=8)
        tab.update(range_name="A1", values=[["Tuần", "Mã câu", "Tên file", "Đáp án AI duyệt", "Kiểm tra", "GV kết luận (Đúng/Sai)", "Ghi chú GV"]])
    tuan = bay.strftime("%Y-W%V")
    if tuan in tab.col_values(1): return
    ung = [r for r in d[1:] if len(r) > c["Trạng thái duyệt"] and r[c["Trạng thái duyệt"]] == TT["AI"]]
    chon = random.sample(ung, min(10, len(ung)))
    if chon:
        tab.append_rows([[tuan, r[c["Mã câu"]], r[c["Tên file"]], r[c["Đáp án"]], r[c["Kiểm tra"]][-300:], "", ""] for r in chon],
                        value_input_option="RAW", table_range="A1")
        print("🎯 Đã chọn %d câu AI duyệt ngẫu nhiên vào tab %s." % (len(chon), TAB_MAU))


def ghi_nhip(kho, ghi_chu):
    try:
        tab = kho.worksheet(X.TAB_AGENT)
        ten = tab.col_values(1)
        luc = dt.datetime.now(X.TZ).strftime("%d/%m/%Y %H:%M")
        if TEN_AGENT in ten: dong = ten.index(TEN_AGENT) + 1
        else:
            dong = len(ten) + 1
            tab.update(range_name="A%d:D%d" % (dong, dong), values=[[TEN_AGENT, "Miễn phí", "", 26]], value_input_option="USER_ENTERED")
        tab.update(range_name="E%d" % dong, values=[[luc]], value_input_option="USER_ENTERED")
        tab.update(range_name="G%d" % dong, values=[[ghi_chu[:300]]], value_input_option="RAW")
    except Exception as e:
        print("Không ghi được nhịp chạy:", e)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if Q:
            Q.ghi_sheet()
        raise
