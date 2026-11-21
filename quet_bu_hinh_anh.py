"""
Quét bù hình ảnh – BẢN GÁN THEO VỊ TRÍ TRÊN TRANG PDF (thay bản cũ gán theo khoảng cách 120 px).

Ý tưởng:
  1. Tìm mọi dòng "Câu N." trong PDF (kèm cột trái/phải và số PHẦN) => mỗi hình thuộc câu đứng NGAY TRÊN nó cùng cột.
  2. Hình = ảnh raster + hình vẽ vector (đồ thị, mạch điện vẽ bằng nét) gom lại; bỏ logo/đầu-cuối trang/bảng kẻ.
  3. Khớp dòng của Sheet với "Câu N" trong PDF bằng số câu + độ trùng từ khoá nội dung (chống nhầm khi đề có PHẦN I/II/III
     đánh số lại từ 1).
  4. Mỗi câu có "độ tin cậy": cao / trung_binh / can_xem. Câu cao tự dùng, câu can_xem để người duyệt.

Chạy:
  python quet_bu_hinh_anh.py                 -> CHẠY THỬ: chỉ ghi bao_cao_hinh.csv, không đụng Sheet/images
  GHI_SHEET=1 python quet_bu_hinh_anh.py     -> ghi Link ảnh (+ "Độ tin cậy hình" nếu có cột) và lưu ảnh vào images/
  Có file hinh_chuan.csv (cột ma_cau,link_dung) -> in tỉ lệ đúng so với các câu đã xác nhận.

[21/11/2026 BỔ SUNG] CÁC GIẢI PHÁP TĂNG ĐỘ CHÍNH XÁC GẮN ẢNH (mọi phần khác giữ nguyên; chỉ THÊM, không bỏ hàm cũ):
  G1. Khoá "tay": câu có cột "Độ tin cậy hình" = tay (thầy đã chỉnh trên trang duyệt) KHÔNG bị quét ghi đè.
  G2. Đối chiếu SỐ HÌNH: đề nhắc "Hình 1, Hình 2" / "hai hình" mà PDF chỉ thấy ít hơn -> can_xem; thấy nhiều hơn -> trung_binh.
  G3. Đối chiếu TỪ GỢI Ý HÌNH ở cả Sheet lẫn đoạn chữ của câu trong PDF: cả hai đều không nhắc hình -> can_xem
      (hình trang trí, logo, hình của câu kề). Hình nằm đầu cột/đầu trang (gán cho câu trước) mà câu trước không nhắc hình -> can_xem.
  G4. Nhiều dòng Sheet cùng khớp MỘT câu trong PDF (đề đánh số lại theo PHẦN, câu trùng) -> can_xem, không đoán.
  G5. Loại PHẦN ĐÁP ÁN / HƯỚNG DẪN CHẤM của cùng file PDF: câu và hình sau tiêu đề đó không được dùng để gắn (tránh gắn hình lời giải
      hoặc nhầm "Câu N" của đáp án). Đặt LOC_DAP_AN=0 để tắt.
  G6. Không ghi đè link cũ ĐANG DÙNG ĐƯỢC bằng kết quả chưa đạt mức "cao" (giữ link cũ, chỉ đánh dấu can_xem). Link cũ HỎNG
      (tệp images/... không còn) thì vẫn thay bằng kết quả mới. Đặt GIU_LINK_CU=0 để về cách cũ (ghi đè mọi lúc).
  G7. AI xác nhận (TUỲ CHỌN, KIEM_AI=1): với câu chưa đạt "cao", Gemini nhìn NỘI DUNG câu + hình ứng viên (hình đã gán + hình câu kề)
      rồi cho biết hình nào thật sự thuộc câu. AI đồng ý -> nâng một bậc; AI không đồng ý -> can_xem; AI thấy hình thuộc câu kề ->
      chỉ ĐỀ XUẤT trong báo cáo (cột link_de_xuat), KHÔNG tự ghi. Tối đa KIEM_AI_TOI_DA lượt/lần chạy (mặc định 40).
  G8. Báo cáo thêm cột ly_do, link_de_xuat và các dòng "(không thuộc câu nào)" cho hình mồ côi (hình đứng trước "Câu" đầu tiên).
  G9. Thứ tự hình trong câu theo HÀNG rồi theo CỘT (x): phương án A,B,C,D xếp 2x2 hoặc 1x4 ra đúng thứ tự A,B,C,D.
  G10. Nhãn "Hình N" ngay trên/dưới hình: đề nhắc số hình nhưng nhãn không trùng (VD hình ghi Hình 3, câu nhắc Hình 1) -> can_xem.
  G11. Nhãn chữ NẰM TRONG hình (R1, U2, tên đại lượng...) so với nội dung câu: trùng nhiều thì coi như có liên quan (không bị G3 hạ);
       không chữ nào trùng -> hạ tối thiểu trung_binh.
  G12. Cùng một hình raster xuất hiện ở >= 2 câu khác nhau trong file (chưa đủ 3 để bị coi là logo) -> tối thiểu trung_binh.
  G13. HÌNH DÙNG CHUNG NHÓM CÂU: dòng dẫn "Sử dụng thông tin/hình sau cho câu 5 và 6" nằm TRƯỚC "Câu 5." -> hình ngay dưới dòng đó
       gắn cho mọi câu trong nhóm (trước đây bị gán nhầm cho câu đứng trước). Mức tối đa trung_binh.
  G14. Trước khi ghi: kiểm tra tệp images/... có thật trên đĩa; thiếu tệp thì KHÔNG ghi link đó.
  G15. Sao lưu: trước khi ghi Sheet, lưu sao_luu_hinh_<giờ>.json (link/mức cũ và mới của từng câu) để khôi phục khi cần.
  G16. Đọc lại Link Ảnh + Độ tin cậy hình NGAY TRƯỚC khi ghi: câu vừa bị thầy chỉnh/đặt "tay" trong lúc script đang quét thì bỏ qua.
"""
import os
import re
import io
import csv
import json
import base64
import hashlib
import unicodedata
import warnings
from urllib.parse import unquote

warnings.filterwarnings("ignore", category=FutureWarning)

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:  # cho phép import để chạy thử phần logic thuần
        fitz = None

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]
TRUNG_TAM_CONFIG = "trung_tam_dieu_phoi.json"
GHI_SHEET = os.environ.get("GHI_SHEET", "") == "1"
TIEN_TO_ANH = "fig_"          # tên tệp mới: images/fig_<md5 12 ký tự>.<đuôi> (không phụ thuộc số dòng Sheet)
TOI_DA_HINH_MOI_CAU = 6
MUC = {"cao": 0, "trung_binh": 1, "can_xem": 2}
TEN_MUC = ["cao", "trung_binh", "can_xem"]
# [21/11/2026 BỔ SUNG]
LOC_DAP_AN = os.environ.get("LOC_DAP_AN", "1") != "0"          # G5
GIU_LINK_CU = os.environ.get("GIU_LINK_CU", "1") != "0"        # G6
KIEM_AI = os.environ.get("KIEM_AI", "") == "1"                 # G7
KIEM_AI_TOI_DA = int(os.environ.get("KIEM_AI_TOI_DA", "40") or 40)

RE_NEO = re.compile(r"^\s*C[âÂ]u\s*(\d{1,3})\s*[.:)]", re.IGNORECASE)
RE_PHAN = re.compile(r"^\s*PH[ẦẬA]N\s+(I{1,3}|IV|V|\d)\b", re.IGNORECASE)
RE_PHUONG_AN = re.compile(r"^\s*[A-Da-d]\s*[.)]")
RE_CUE_MAC_DINH = re.compile(r"Hình|Đồ thị|Mạch điện|Giản đồ|Sơ đồ|Biểu đồ|trục|vẽ|bên dưới|như sau", re.IGNORECASE)
RE_TIEU_DE_DAP_AN = re.compile(r"^\s*(?:[IVX]+\s*[.)]\s*|PH[ẦẬA]N\s+[IVX\d]+\s*[.:–-]?\s*)?"
                               r"(?:ĐÁP\s*ÁN|HƯỚNG\s+DẪN\s+(?:CHẤM|GIẢI)|LỜI\s+GIẢI(?:\s+CHI\s+TIẾT)?|BẢNG\s+ĐÁP\s+ÁN)\b", re.IGNORECASE)
RE_SO_HINH = re.compile(r"H[ìi]nh\s*(?:vẽ\s*)?(\d{1,2})\b", re.IGNORECASE)
RE_CHU_SO_HINH = re.compile(r"\b(hai|ba|bốn)\s+(?:hình|đồ\s*thị|mạch|sơ\s*đồ|giản\s*đồ)", re.IGNORECASE)


def nfc(s):
    return unicodedata.normalize("NFC", s or "")


# ======================================================================
# PHẦN 1: LOGIC THUẦN (không cần PyMuPDF) – dữ liệu vào là dict thường
# ======================================================================
def phat_hien_cot(dong, pw):
    """1 hay 2 cột: nhiều dòng ngắn nằm hẳn nửa trái VÀ nửa phải."""
    ngan = [d for d in dong if (d["bbox"][2] - d["bbox"][0]) < 0.55 * pw]
    if len(dong) < 8:
        return 1
    mid = pw / 2
    trai = sum(1 for d in ngan if d["bbox"][2] <= mid + 5)
    phai = sum(1 for d in ngan if d["bbox"][0] >= mid - 5)
    rong = sum(1 for d in dong if (d["bbox"][2] - d["bbox"][0]) >= 0.6 * pw)
    if trai >= 4 and phai >= 4 and min(trai, phai) >= 0.25 * max(trai, phai) and rong < 0.4 * len(dong):
        return 2
    return 1


def cot_cua(pg, x0, x1):
    """0 = trái/đơn, 1 = phải, -1 = tràn hết trang (trên trang 2 cột)."""
    if pg["ncol"] == 1:
        return 0
    if (x1 - x0) >= 0.6 * pg["w"]:
        return -1
    return 0 if (x0 + x1) / 2 < pg["mid"] else 1


def thu_tu_doc(item):
    return (item["page"], max(item["col"], 0), item["bbox"][1])


def chu_so_huu(neo, pages, p, col, y0):
    """Câu đứng ngay TRÊN vị trí (trang p, cột col, cao độ y0). Trả (neo, mức_tin_cậy_tối_đa)."""
    neo = sorted(neo, key=thu_tu_doc)
    ung = [a for a in neo if a["page"] == p and a["bbox"][1] <= y0 + 3
           and (pages[p]["ncol"] == 1 or col == -1 or a["col"] in (col, -1))]
    if ung:
        a = max(ung, key=lambda a: a["bbox"][1])
        return a, ("can_xem" if col == -1 and pages[p]["ncol"] == 2 else "cao")
    # đầu cột/đầu trang: thuộc câu đứng ngay trước theo thứ tự đọc (câu tràn cột/trang)
    truoc = [a for a in neo if (a["page"], max(a["col"], 0)) < (p, max(col, 0))]
    if truoc:
        return truoc[-1], "trung_binh"
    return None, None


def gan_hinh_cho_cau(pages, dong, neo, hinh):
    """Trả {id_neo: {"hinh": [...], "muc": ..., "van_ban": "..."}}"""
    kq = {a["id"]: {"hinh": [], "muc": "cao", "van_ban": [], "neo": a} for a in neo}
    for d in dong:
        a, _ = chu_so_huu(neo, pages, d["page"], d["col"], d["bbox"][1])
        if a:
            kq[a["id"]]["van_ban"].append(d["text"])
    for h in sorted(hinh, key=thu_tu_doc):
        a, muc = chu_so_huu(neo, pages, h["page"], h["col"], h["bbox"][1])
        if not a:
            continue
        r = kq[a["id"]]
        r["hinh"].append(h)
        if MUC[muc] > MUC[r["muc"]]:
            r["muc"] = muc
    for r in kq.values():
        r["van_ban"] = " ".join(r["van_ban"])
        r["hinh"] = xep_hinh_trong_cau(r["hinh"])                      # [BỔ SUNG G9]
        if len(r["hinh"]) > TOI_DA_HINH_MOI_CAU:
            r["hinh"] = r["hinh"][:TOI_DA_HINH_MOI_CAU]
            r["muc"] = "can_xem"
    return kq


def tu_khoa(s):
    s = nfc(s).lower()
    s = re.sub(r"\$\$.*?\$\$|\$.*?\$|\\\(.*?\\\)|\\\[.*?\\\]", " ", s, flags=re.S)
    s = re.sub(r"\\[a-zA-Z]+", " ", s)
    s = re.sub(r"\[.*?\]", " ", s)
    return set(re.findall(r"[^\W\d_]{3,}", s))


def khop_cau(so_cau, noi_dung, neo, kq_gan):
    """Khớp 1 dòng Sheet với 1 'Câu N' trong PDF. Trả (neo_id, điểm) hoặc (None, điểm tốt nhất)."""
    tk = tu_khoa(noi_dung)

    def diem(a):
        if not tk:
            return 0.0
        tv = tu_khoa(kq_gan[a["id"]]["van_ban"])
        return len(tk & tv) / len(tk)

    cung_so = [a for a in neo if so_cau and str(a["so"]) == str(so_cau)]
    if cung_so:
        xep = sorted(((diem(a), a) for a in cung_so), key=lambda x: -x[0])
        tot, a = xep[0]
        if len(tk) < 4 and len(cung_so) == 1:
            return a["id"], 0.6                         # câu ngắn, số câu duy nhất trong file
        if tot >= 0.6 and (len(xep) == 1 or tot - xep[1][0] >= 0.1):
            return a["id"], tot
    xep = sorted(((diem(a), a) for a in neo), key=lambda x: -x[0])
    if xep and xep[0][0] >= 0.75 and (len(xep) == 1 or xep[0][0] - xep[1][0] >= 0.1):
        return xep[0][1]["id"], xep[0][0]
    return None, (xep[0][0] if xep else 0.0)


def danh_gia_hang(muc_hinh, diem_khop, co_cue):
    m = MUC[muc_hinh]
    if diem_khop < 0.75:
        m = max(m, 1)
    if not co_cue:
        m = max(m, 1)
    return TEN_MUC[m]


# ======================================================================
# [21/11/2026 BỔ SUNG LẦN 2] G9 – G16 (logic thuần, kiểm thử được không cần PyMuPDF)
# ======================================================================
RE_NHAN_HINH = re.compile(r"^\s*H[ìi]nh\s*(\d{1,2})\s*(?:[.:)–-]|$)", re.IGNORECASE)
RE_NHOM_CHUNG = re.compile(r"c[âÂ]u\s*(\d{1,3})\s*(?:đến|tới|[-–]|và|,)\s*(?:c[âÂ]u\s*)?(\d{1,3})", re.IGNORECASE)
RE_GOI_CHUNG = re.compile(r"sử\s*dụng|dùng|dựa\s*vào|căn\s*cứ|thông\s*tin|dữ\s*kiện|trả\s*lời|chung", re.IGNORECASE)


def xep_hinh_trong_cau(hs, dung_sai=14):
    """G9. Hàng trước (trên xuống), trong cùng hàng (cách nhau <= dung_sai) thì trái sang phải."""
    ds = sorted(hs, key=lambda h: (h["page"], max(h["col"], 0), h["bbox"][1]))
    ra, nhom = [], []
    for h in ds:
        if nhom and (h["page"], max(h["col"], 0)) == (nhom[0]["page"], max(nhom[0]["col"], 0)) \
                and h["bbox"][1] - nhom[0]["bbox"][1] <= dung_sai:
            nhom.append(h)
        else:
            ra.extend(sorted(nhom, key=lambda x: x["bbox"][0]))
            nhom = [h]
    ra.extend(sorted(nhom, key=lambda x: x["bbox"][0]))
    return ra


def gan_nhan_chu(hinh, dong, gap=45):
    """G10 + G11. Gắn cho mỗi hình: nhan_so (số trong nhãn 'Hình N' sát hình) và chu (các dòng chữ nằm trong khung hình)."""
    for h in hinh:
        x0, y0, x1, y1 = h["bbox"]
        chu, nhan = [], None
        for d in dong:
            if d["page"] != h["page"]:
                continue
            bx0, by0, bx1, by1 = d["bbox"]
            trong = x0 <= (bx0 + bx1) / 2 <= x1 and y0 <= (by0 + by1) / 2 <= y1
            m = RE_NHAN_HINH.match(d["text"]) if len(d["text"]) <= 60 else None
            if m and nhan is None and bx1 >= x0 - 20 and bx0 <= x1 + 20 and \
                    (trong or (y1 - 2 <= by0 <= y1 + gap) or (y0 - gap <= by1 <= y0 + 2)):
                nhan = int(m.group(1))
                continue                                          # nhãn không tính là chữ trong hình
            if trong and not RE_NEO.match(d["text"]) and not RE_PHUONG_AN.match(d["text"]):
                chu.append(d["text"])
        h["nhan_so"], h["chu"] = nhan, chu


def _chuan_nhan(s):
    s = re.sub(r"\\(?:text|mathrm|mathbf|left|right)", "", nfc(s).lower())
    return re.sub(r"[\s$\\_{}^]", "", s)


def diem_nhan_chu(dong_chu, noi_dung):
    """G11. Tỉ lệ nhãn chữ trong hình (R1, U2, từ >= 3 chữ) xuất hiện trong nội dung câu. None = hình ít chữ, không kết luận được."""
    q, toks = _chuan_nhan(noi_dung), set()
    for t in dong_chu:
        for w in re.split(r"\s+", nfc(t)):
            w = _chuan_nhan(w)
            if re.fullmatch(r"[^\W\d_]{1,3}\d{1,2}", w) or re.fullmatch(r"[^\W\d_]{3,}", w):
                toks.add(w)
    if len(toks) < 2:
        return None
    return sum(1 for w in toks if w in q) / len(toks)


def hinh_trung_giua_cau(kq_gan):
    """G12. {md5: {id câu}} cho hình raster (không tính hình đã được gắn dùng chung theo nhóm)."""
    d = {}
    for nid, r in kq_gan.items():
        for h in r["hinh"]:
            if h.get("md5") and not h.get("chung"):
                d.setdefault(h["md5"], set()).add(nid)
    return d


def tim_nhom_chung(dong, neo):
    """G13. Dòng dẫn kiểu 'Sử dụng thông tin sau cho câu 5 và câu 6' (không phải dòng 'Câu N.' đầu câu)."""
    ra = []
    for d in sorted(dong, key=thu_tu_doc):
        t = nfc(d["text"])
        if RE_NEO.match(t) or len(t) > 160:
            continue
        m = RE_NHOM_CHUNG.search(t)
        if not m or not RE_GOI_CHUNG.search(t):
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if a < b <= a + 4:
            ra.append({"tu": a, "den": b, "key": thu_tu_doc(d)})
    return ra


def ap_dung_nhom_chung(neo, dong, hinh, kq_gan):
    """G13. Chuyển hình nằm giữa dòng dẫn và 'Câu a.' (câu đầu nhóm, trong 2 câu kế tiếp) sang MỌI câu a..b. Trả số nhóm áp dụng."""
    xep, dem = sorted(neo, key=thu_tu_doc), 0
    for g in tim_nhom_chung(dong, neo):
        sau = [a for a in xep if thu_tu_doc(a) > g["key"]]
        dau = next((a for a in sau[:2] if a["so"] == g["tu"]), None)
        if dau is None:
            continue
        hk = thu_tu_doc(dau)
        figs = [h for h in hinh if g["key"] < thu_tu_doc(h) < hk]
        if not figs:
            continue
        tv, da = [], set()
        for a in xep[xep.index(dau):]:
            if g["tu"] <= a["so"] <= g["den"] and a["so"] not in da:
                tv.append(a)
                da.add(a["so"])
            else:
                break
        for r in kq_gan.values():
            r["hinh"] = [x for x in r["hinh"] if not any(x is f for f in figs)]
        for f in figs:
            f["chung"] = True
        for a in tv:
            r = kq_gan[a["id"]]
            r["hinh"] = figs + r["hinh"]
            if MUC[r["muc"]] < 1:
                r["muc"] = "trung_binh"
            r["chung"] = "%d–%d" % (g["tu"], g["den"])
        dem += 1
    return dem


def danh_gia_bo_sung(muc, r, nd_sheet, van_ban_pdf, diem_chu, md5_cau):
    """G10 + G11 + G12 + G13. Chỉ HẠ mức. Trả (mức mới, [lí do])."""
    ly, m, hs = [], MUC[muc], r["hinh"]
    nhan = {h["nhan_so"] for h in hs if h.get("nhan_so") is not None}
    neu = {int(x) for x in RE_SO_HINH.findall(nfc(nd_sheet))} or {int(x) for x in RE_SO_HINH.findall(nfc(van_ban_pdf))}
    if nhan and neu and not (nhan & neu):
        m = 2
        ly.append("nhãn hình trong PDF là Hình %s nhưng câu nhắc Hình %s" % (", ".join(map(str, sorted(nhan))), ", ".join(map(str, sorted(neu)))))
    if diem_chu is not None and diem_chu == 0:
        m = max(m, 1)
        ly.append("nhãn chữ trong hình không xuất hiện trong đề")
    for h in hs:
        if h.get("md5") and len(md5_cau.get(h["md5"], ())) > 1 and not h.get("chung"):
            m = max(m, 1)
            ly.append("cùng một hình xuất hiện ở %d câu trong file" % len(md5_cau[h["md5"]]))
            break
    if r.get("chung"):
        m = max(m, 1)
        ly.append("hình dùng chung của nhóm câu %s (theo dòng dẫn trong đề)" % r["chung"])
    return TEN_MUC[m], ly


def thieu_tep_anh(link, thu_muc="images"):
    """G14. Các đường dẫn images/... trong link mà tệp không có trên đĩa."""
    ra = []
    for x in [y for y in re.split(r"[,;\s]+", str(link or "")) if y]:
        m = re.match(r"^images/([^/?#]+)$", x)
        if m and not os.path.isfile(os.path.join(thu_muc, unquote(m.group(1)))):
            ra.append(x)
    return ra


def loc_truoc_khi_ghi(ket_qua, cu, vt, link_hien, tin_hien):
    """G16. Giữ lại các câu CHƯA bị ai đổi từ lúc đọc; trả (ghi được, [(mã, lí do bỏ)])."""
    ghi, bo = {}, []
    for ma, (link, muc) in ket_qua.items():
        dong = vt.get(ma)
        if not dong:
            continue
        h_link = str(link_hien[dong - 1]).strip() if dong - 1 < len(link_hien) else ""
        h_tin = str(tin_hien[dong - 1]).strip() if dong - 1 < len(tin_hien) else ""
        c_link = str(cu.get(ma, ("", ""))[0]).strip()
        if h_tin == "tay":
            bo.append((ma, "thầy vừa đặt 'tay'"))
        elif h_link != c_link:
            bo.append((ma, "Link Ảnh vừa bị đổi trong lúc quét"))
        else:
            ghi[ma] = (link, muc)
    return ghi, bo


def ghi_sao_luu(ghi, cu, thu_muc="."):
    """G15. Lưu sao_luu_hinh_<giờ>.json: link/mức cũ và mới của từng câu sắp ghi. Trả đường dẫn tệp."""
    import datetime as _dt
    ten = os.path.join(thu_muc, "sao_luu_hinh_%s.json" % _dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
    nd = {ma: {"link_cu": cu.get(ma, ("", ""))[0], "tin_cu": cu.get(ma, ("", ""))[1], "link_moi": l, "muc_moi": m} for ma, (l, m) in ghi.items()}
    with open(ten, "w", encoding="utf-8") as f:
        json.dump(nd, f, ensure_ascii=False, indent=1)
    return ten


# ======================================================================
# [21/11/2026 BỔ SUNG] CÁC LỚP KIỂM TRA THÊM – LOGIC THUẦN (kiểm thử được không cần PyMuPDF)
# ======================================================================
def loc_phan_dap_an(dong, neo, hinh):
    """G5. Bỏ câu / hình / dòng chữ nằm SAU tiêu đề ĐÁP ÁN – HƯỚNG DẪN CHẤM của cùng file (chỉ cắt khi trước tiêu đề đã có >= 3 câu)."""
    moc = None
    for d in sorted(dong, key=thu_tu_doc):
        if len(d["text"]) <= 70 and RE_TIEU_DE_DAP_AN.match(d["text"]):
            truoc = [a for a in neo if thu_tu_doc(a) < thu_tu_doc(d)]
            if len(truoc) >= 3:
                moc = thu_tu_doc(d)
                break
    if moc is None:
        return dong, neo, hinh, 0
    ben_trong = lambda x: thu_tu_doc(x) < moc
    bo = sum(1 for h in hinh if not ben_trong(h))
    return [d for d in dong if ben_trong(d)], [a for a in neo if ben_trong(a)], [h for h in hinh if ben_trong(h)], bo


def so_hinh_neu(noi_dung):
    """G2. Số hình mà chữ của câu nhắc tới: số 'Hình N' khác nhau, hoặc 'hai/ba/bốn hình'. 0 = không nhắc số cụ thể."""
    t = nfc(noi_dung)
    so = {int(x) for x in RE_SO_HINH.findall(t)}
    m = RE_CHU_SO_HINH.search(t)
    chu = {"hai": 2, "ba": 3, "bốn": 4}[m.group(1).lower()] if m else 0
    return max(len(so), chu)


def danh_gia_nang_cao(muc, nd_sheet, van_ban_pdf, n_hinh, co_cue_sheet, co_cue_pdf, so_dong_cung_neo, muc_gan_goc="cao"):
    """G2 + G3 + G4. Chỉ HẠ mức (không bao giờ nâng). Trả (mức mới, [lí do])."""
    ly, m = [], MUC[muc]
    n_neu = so_hinh_neu(nd_sheet) or so_hinh_neu(van_ban_pdf)
    if n_neu and n_hinh < n_neu:
        m = 2
        ly.append("đề nhắc %d hình nhưng PDF chỉ thấy %d" % (n_neu, n_hinh))
    elif n_neu and n_hinh > n_neu:
        m = max(m, 1)
        ly.append("PDF thấy %d hình, đề nhắc %d" % (n_hinh, n_neu))
    if n_hinh and not co_cue_sheet and not co_cue_pdf:
        m = 2
        ly.append("cả Sheet lẫn PDF đều không nhắc hình (có thể là hình trang trí / của câu kề)")
    if n_hinh and muc_gan_goc == "trung_binh" and not co_cue_pdf:
        m = 2
        ly.append("hình ở đầu cột/trang gán cho câu trước nhưng câu đó không nhắc hình")
    if so_dong_cung_neo > 1:
        m = 2
        ly.append("%d dòng Sheet cùng khớp một câu trong PDF" % so_dong_cung_neo)
    return TEN_MUC[m], ly


def link_con_dung(link, thu_muc="images"):
    """G6. Link cũ còn dùng được? Chỉ kiểm được dạng .../images/<tên> khi thư mục images/ có trên máy; dạng khác (Drive...) coi là dùng được."""
    ds = [x for x in re.split(r"[,;\s]+", str(link or "")) if x]
    if not ds:
        return False
    if not os.path.isdir(thu_muc):
        return True
    for x in ds:
        m = re.search(r"(?:^|/)images/([^/?#\s]+)$", x)
        if m and not os.path.isfile(os.path.join(thu_muc, unquote(m.group(1)))):
            return False
    return True


def quyet_dinh_ghi(link_cu, tin_cu, link_moi, muc_moi, thu_muc="images"):
    """G1 + G6. Trả ('ghi'|'giu'|'bo', [lí do]).
       ghi = ghi link mới + mức; giu = giữ link cũ, chỉ đánh dấu can_xem; bo = không đụng tới."""
    if str(tin_cu).strip() == "tay":
        return "bo", ["thầy đã chỉnh tay – không ghi đè"]
    if link_moi == link_cu:
        return ("ghi" if tin_cu != muc_moi else "bo"), []
    if not link_cu or not GIU_LINK_CU:
        return "ghi", []
    if not link_con_dung(link_cu, thu_muc):
        return "ghi", ["link cũ hỏng (tệp không còn) – thay bằng hình quét mới"]
    if muc_moi == "cao":
        return "ghi", []
    return "giu", ["kết quả quét mức %s chưa đủ chắc để thay link cũ đang dùng được" % muc_moi]


def chon_ung_vien(neo, kq_gan, nid, moi_ben=2, toi_da=6):
    """G7. Danh sách (hình, nhãn): hình đã gán cho câu ('dung_gan') + hình của câu đứng ngay trước ('cau_truoc') / sau ('cau_sau')."""
    xep = sorted(neo, key=thu_tu_doc)
    vt = next((i for i, a in enumerate(xep) if a["id"] == nid), None)
    ra = [(h, "dung_gan") for h in kq_gan[nid]["hinh"]]
    if vt is None:
        return ra[:toi_da]
    if vt > 0:
        ra += [(h, "cau_truoc") for h in kq_gan[xep[vt - 1]["id"]]["hinh"][-moi_ben:]]
    if vt + 1 < len(xep):
        ra += [(h, "cau_sau") for h in kq_gan[xep[vt + 1]["id"]]["hinh"][:moi_ben]]
    return ra[:toi_da]


def doc_json_ai(text):
    s = re.sub(r"```\s*$", "", re.sub(r"^```(?:json)?\s*", "", str(text or "").strip(), flags=re.I)).strip()
    a, b = s.find("{"), s.rfind("}")
    if a != -1 and b > a:
        s = s[a:b + 1]
    j = json.loads(s)
    thuoc = set()
    for x in (j.get("thuoc") or []):
        try:
            thuoc.add(int(x))
        except (TypeError, ValueError):
            pass
    return {"thuoc": thuoc, "can_hinh": bool(j.get("can_hinh", True)), "chac": str(j.get("chac_chan") or "").strip().lower(),
            "ly_do": str(j.get("ly_do") or "")[:200]}


def ap_dung_ai(muc, kq, ung_vien):
    """G7. Gộp ý kiến AI vào mức tin cậy. Trả (mức mới, [lí do], [chỉ số ứng viên (từ 1) AI đề xuất thuộc câu mà KHÔNG phải hình đã gán])."""
    ly, de_xuat = [], []
    gan = {k for k, (_, nhan) in enumerate(ung_vien, 1) if nhan == "dung_gan"}
    thuoc = set(kq.get("thuoc") or [])
    chac = "AI " + (kq.get("chac") or "?")
    if not kq.get("can_hinh", True) and not thuoc:
        if gan:
            ly.append("AI: câu không cần hình nhưng đang gắn hình (%s)" % kq.get("ly_do", ""))
            return "can_xem", ly, de_xuat
        return muc, ly, de_xuat
    if gan and thuoc == gan:
        if not kq.get("chac", "").startswith("thấp"):
            moi = TEN_MUC[max(MUC[muc] - 1, 0)]
            ly.append("AI xác nhận đúng hình (%s): %s → %s" % (kq.get("chac") or "?", muc, moi))
            return moi, ly, de_xuat
        ly.append("AI đồng ý nhưng không chắc – giữ nguyên mức")
        return muc, ly, de_xuat
    ngoai = thuoc - gan
    if ngoai:
        de_xuat = sorted(ngoai)
        ly.append("%s cho rằng hình thuộc câu kề / hình khác (%s)" % (chac, kq.get("ly_do", "")))
        return "can_xem", ly, de_xuat
    if gan and thuoc < gan:
        ly.append("%s: chỉ một phần hình đã gán thuộc câu" % chac)
        return "can_xem", ly, de_xuat
    if gan and not thuoc:
        ly.append("%s: không hình nào đã gán phù hợp với câu" % chac)
        return "can_xem", ly, de_xuat
    return muc, ly, de_xuat


# ======================================================================
# PHẦN 2: ĐỌC PDF BẰNG PyMuPDF
# ======================================================================
def _giao(a, b, gap=0):
    return not (a[2] + gap < b[0] or b[2] + gap < a[0] or a[3] + gap < b[1] or b[3] + gap < a[1])


def _hop(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _gop_cum(rects, gap):
    """Gộp các hình chữ nhật chạm nhau (cách nhau <= gap) bằng union-find. Trả danh sách (bbox, [chỉ số])."""
    n = len(rects)
    cha = list(range(n))

    def tim(i):
        while cha[i] != i:
            cha[i] = cha[cha[i]]
            i = cha[i]
        return i
    thu_tu = sorted(range(n), key=lambda i: rects[i][0])
    for a in range(n):
        i = thu_tu[a]
        for b in range(a + 1, n):
            j = thu_tu[b]
            if rects[j][0] > rects[i][2] + gap:
                break
            if _giao(rects[i], rects[j], gap):
                cha[tim(i)] = tim(j)
    cum = {}
    for i in range(n):
        cum.setdefault(tim(i), []).append(i)
    ra = []
    for ds in cum.values():
        bb = rects[ds[0]]
        for i in ds[1:]:
            bb = _hop(bb, rects[i])
        ra.append((bb, ds))
    return ra


def trich_pdf(doc, min_w=50, min_h=50):
    """Đọc cả PDF: trang, dòng chữ, các 'Câu N', các hình (raster + vector)."""
    pages, dong, neo, hinh = [], [], [], []
    phan_hien_tai = 0
    dem_md5 = {}
    for pi, page in enumerate(doc):
        pw, ph = page.rect.width, page.rect.height
        d = page.get_text("dict")
        dong_trang = []
        for b in d.get("blocks", []):
            if b.get("type") != 0:
                continue
            for ln in b.get("lines", []):
                t = nfc("".join(s.get("text", "") for s in ln.get("spans", []))).strip()
                if t:
                    dong_trang.append({"page": pi, "bbox": tuple(ln["bbox"]), "text": t})
        pg = {"w": pw, "h": ph, "ncol": phat_hien_cot(dong_trang, pw), "mid": pw / 2}
        pages.append(pg)
        for x in dong_trang:
            x["col"] = cot_cua(pg, x["bbox"][0], x["bbox"][2])
            dong.append(x)
            if RE_PHAN.match(x["text"]):
                phan_hien_tai += 1
            m = RE_NEO.match(x["text"])
            if m:
                neo.append({"id": len(neo), "so": int(m.group(1)), "page": pi, "col": x["col"],
                            "bbox": x["bbox"], "phan": phan_hien_tai})
        tu = page.get_text("words")
        dem_chu = lambda bb: sum(1 for w in tu if _giao(bb, w[:4]) and
                                 (w[0] + w[2]) / 2 >= bb[0] and (w[0] + w[2]) / 2 <= bb[2] and
                                 (w[1] + w[3]) / 2 >= bb[1] and (w[1] + w[3]) / 2 <= bb[3])

        # --- hình raster
        cac = []   # mỗi phần tử: {"bbox","ids","xrefs","raster":bool}
        xrefs = [im[0] for im in page.get_images(full=True)]
        for info in page.get_image_info(xrefs=True):
            xr, bb = info.get("xref", 0), tuple(info["bbox"])
            if (bb[2] - bb[0]) < 20 or (bb[3] - bb[1]) < 20:
                continue
            if info.get("width", 0) < min_w or info.get("height", 0) < min_h:
                continue
            ar = (bb[2] - bb[0]) / max(bb[3] - bb[1], 1e-6)
            if ar < 0.125 or ar > 8:
                continue
            if (bb[2] - bb[0]) * (bb[3] - bb[1]) > 0.6 * pw * ph:
                continue
            cac.append({"bbox": bb, "ids": [(pi + 1, xrefs.index(xr) + 1)] if xr in xrefs else [],
                        "xrefs": [xr], "raster": True})

        # --- hình vector (đồ thị, mạch điện vẽ bằng nét)
        vr, thongtin = [], []
        for dr in page.get_drawings():
            r = dr.get("rect")
            if r is None or r.is_empty and (r.width < 0.01 and r.height < 0.01):
                continue
            bb = (r.x0, r.y0, r.x1, r.y1)
            w, h = bb[2] - bb[0], bb[3] - bb[1]
            if w > 0.8 * pw and h < 3:
                continue                                  # đường kẻ ngang trang
            if w * h > 0.6 * pw * ph:
                continue                                  # nền
            if bb[3] < 0.05 * ph or bb[1] > 0.95 * ph:
                continue                                  # đầu/cuối trang
            vr.append(bb)
            thongtin.append(dr.get("items", []))
        for bb, ds in _gop_cum(vr, 4) if vr else []:
            w, h = bb[2] - bb[0], bb[3] - bb[1]
            n_item = sum(len(thongtin[i]) for i in ds)
            if w < 25 or h < 25 or n_item < 3:
                continue
            ngang = doc_ = cong = 0
            nghieng = False
            for i in ds:
                for it in thongtin[i]:
                    if it[0] == "c":
                        cong += 1
                    elif it[0] == "l":
                        dx, dy = abs(it[2].x - it[1].x), abs(it[2].y - it[1].y)
                        if dy < 0.5:
                            ngang += 1
                        elif dx < 0.5:
                            doc_ += 1
                        else:
                            nghieng = True
            la_bang = (cong == 0 and not nghieng and ngang >= 3 and doc_ >= 3 and dem_chu(bb) >= 8)
            if la_bang:
                continue
            cac.append({"bbox": bb, "ids": [], "xrefs": [], "raster": False})

        # --- gộp raster + vector chồng nhau, hút nhãn chữ ngắn quanh hình (R1, trục x, ...)
        if cac:
            for bb, ds in _gop_cum([c["bbox"] for c in cac], 3):
                hop = {"bbox": bb, "ids": [], "xrefs": [], "raster": all(cac[i]["raster"] for i in ds)}
                for i in ds:
                    hop["ids"] += cac[i]["ids"]
                    hop["xrefs"] += cac[i]["xrefs"]
                for x in dong_trang:
                    ngan = len(x["text"].split()) <= 4 and (x["bbox"][2] - x["bbox"][0]) < 0.25 * pw
                    if ngan and not RE_NEO.match(x["text"]) and not RE_PHUONG_AN.match(x["text"]) \
                            and _giao(hop["bbox"], x["bbox"], 8):
                        hop["bbox"] = _hop(hop["bbox"], x["bbox"])
                if hop["bbox"][3] < 0.05 * ph or hop["bbox"][1] > 0.95 * ph:
                    continue
                hop["page"] = pi
                hop["col"] = cot_cua(pg, hop["bbox"][0], hop["bbox"][2])
                hop["raster"] = hop["raster"] and len(hop["xrefs"]) == 1 and dem_chu(hop["bbox"]) == 0
                hinh.append(hop)
                if hop["raster"]:
                    try:
                        md = hashlib.md5(doc.extract_image(hop["xrefs"][0])["image"]).hexdigest()
                        dem_md5[md] = dem_md5.get(md, 0) + 1
                        hop["md5"] = md
                    except Exception:
                        pass
    # bỏ logo / hình lặp lại trên >= 3 trang
    hinh = [h for h in hinh if not (h.get("md5") and dem_md5.get(h["md5"], 0) >= 3)]
    if LOC_DAP_AN:                                                     # [BỔ SUNG G5]
        dong, neo, hinh, so_bo = loc_phan_dap_an(dong, neo, hinh)
        if so_bo:
            print("   (bỏ %d hình thuộc phần ĐÁP ÁN / HƯỚNG DẪN CHẤM của file)" % so_bo, flush=True)
    gan_nhan_chu(hinh, dong)                                           # [BỔ SUNG G10, G11]
    return pages, dong, neo, hinh


def luu_hinh(doc, h, ghi):
    """Trả tên tệp trong images/. Hình raster thuần: lưu nguyên byte gốc; còn lại: cắt vùng từ trang ở 200 dpi."""
    page = doc[h["page"]]
    if h["raster"]:
        bi = doc.extract_image(h["xrefs"][0])
        data, ext = bi["image"], bi["ext"]
    else:
        clip = fitz.Rect(*h["bbox"]) + (-4, -4, 4, 4)
        clip = clip & page.rect
        data, ext = page.get_pixmap(clip=clip, dpi=200).tobytes("png"), "png"
    ten = "%s%s.%s" % (TIEN_TO_ANH, hashlib.md5(data).hexdigest()[:12], ext)
    if ghi:
        os.makedirs("images", exist_ok=True)
        duong = os.path.join("images", ten)
        if not os.path.exists(duong):
            with open(duong, "wb") as f:
                f.write(data)
    return ten


def byte_hinh(doc, h):
    """[BỔ SUNG G7] Byte + mime của hình (không lưu tệp) để gửi cho AI."""
    page = doc[h["page"]]
    if h["raster"]:
        bi = doc.extract_image(h["xrefs"][0])
        if bi.get("ext") in ("png", "jpeg", "jpg", "webp"):
            return bi["image"], "image/" + ("jpeg" if bi["ext"] in ("jpg", "jpeg") else bi["ext"])
    clip = (fitz.Rect(*h["bbox"]) + (-4, -4, 4, 4)) & page.rect
    return page.get_pixmap(clip=clip, dpi=150).tobytes("png"), "image/png"


def ai_xac_nhan(doc, noi_dung, ung_vien, ai):
    """[BỔ SUNG G7] Hỏi Gemini hình nào thuộc câu. ai = {'goi','model','con'}; hết lượt / lỗi / hết hạn mức -> None (không làm hỏng lượt quét)."""
    if not ai.get("goi") or ai.get("con", 0) <= 0 or not ung_vien:
        return None
    chi = ("Dưới đây là NỘI DUNG một câu hỏi Vật lí và các HÌNH ỨNG VIÊN cắt từ đề gốc (đánh số từ 1). Chỉ dựa vào nội dung câu hỏi "
           "(dữ kiện, tên đại lượng, nhãn trên hình, số liệu) để xác định hình nào THẬT SỰ thuộc câu này (cần để giải hoặc được câu nhắc tới). "
           "Hình của câu khác, logo, hình trang trí thì KHÔNG thuộc. Câu không cần hình nào thì can_hinh = false.\n"
           "Chỉ trả về JSON: {\"thuoc\": [số thứ tự hình thuộc câu], \"can_hinh\": true|false, \"chac_chan\": \"cao|vừa|thấp\", \"ly_do\": \"ngắn gọn\"}\n\n"
           "NỘI DUNG CÂU:\n" + str(noi_dung)[:3000])
    parts = [{"text": chi}]
    try:
        for k, (h, _) in enumerate(ung_vien, 1):
            b, mime = byte_hinh(doc, h)
            parts += [{"text": "HÌNH %d:" % k}, {"inline_data": {"mime_type": mime, "data": base64.b64encode(b).decode()}}]
        ai["con"] -= 1
        data, _ = ai["goi"]({"contents": [{"role": "user", "parts": parts}],
                             "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json", "maxOutputTokens": 2048}}, ai["model"])
        cand = (data.get("candidates") or [{}])[0]
        text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []) if not p.get("thought"))
        return doc_json_ai(text)
    except Exception as e:
        ai["con"] = 0
        print("   [AI] dừng xác nhận hình: %s" % str(e)[:120], flush=True)
        return None


def ai_buoc(doc, noi_dung, neo, kq_gan, nid, muc, ai):
    """[BỔ SUNG G7] Một bước AI cho một câu. Trả (mức mới, [lí do], [tên tệp đề xuất])."""
    ung = chon_ung_vien(neo, kq_gan, nid)
    kq = ai_xac_nhan(doc, noi_dung, ung, ai)
    if not kq:
        return muc, [], []
    muc2, ly, dx = ap_dung_ai(muc, kq, ung)
    return muc2, ly, ["images/" + luu_hinh(doc, ung[k - 1][0], False) for k in dx if 1 <= k <= len(ung)]


# ======================================================================
# PHẦN 3: GOOGLE SHEET / DRIVE
# ======================================================================
def doc_trung_tam_config():
    if os.path.isfile(TRUNG_TAM_CONFIG):
        try:
            with open(TRUNG_TAM_CONFIG, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Không đọc được {TRUNG_TAM_CONFIG}: {e}")
    return {}


def authenticate():
    import google.auth.transport.requests
    from google.oauth2.service_account import Credentials
    raw_cred = os.environ.get("GOOGLE_CREDENTIALS", "").strip()
    if not raw_cred and os.path.isfile("credentials.json"):
        with open("credentials.json", "r", encoding="utf-8") as f:
            raw_cred = f.read().strip()
    if not raw_cred:
        raise ValueError("Biến môi trường GOOGLE_CREDENTIALS đang trống!")
    try:
        tt = json.loads(raw_cred, strict=False)
    except Exception:
        tt = json.loads(base64.b64decode(raw_cred).decode("utf-8"), strict=False)
    if "private_key" in tt:
        tt["private_key"] = tt["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(tt, scopes=SCOPES)
    creds.refresh(google.auth.transport.requests.Request())
    return creds


def doc_hinh_chuan(duong="hinh_chuan.csv"):
    """hinh_chuan.csv: ma_cau,link_dung (tên tệp ảnh cũ dạng ..._p7_img3.png, nhiều ảnh cách nhau dấu phẩy; trống = câu không có hình)."""
    if not os.path.isfile(duong):
        return {}
    kq = {}
    with open(duong, "r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            ma = (r.get("ma_cau") or "").strip()
            if ma:
                kq[ma] = set(re.findall(r"_p(\d+)_img(\d+)", r.get("link_dung") or ""))
    return kq


def quet_drive_va_gan_anh():
    import gspread
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    config = doc_trung_tam_config()
    sheet_cfg = config.get("SHEET_CONFIG", {})
    sheet_id = os.environ.get("SHEET_ID") or sheet_cfg.get("SHEET_ID")
    print("Chế độ:", "GHI vào Sheet + images/" if GHI_SHEET else "CHẠY THỬ (chỉ báo cáo, không ghi)", flush=True)

    creds = authenticate()
    gc = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    sh = gc.open_by_url(sheet_id) if sheet_id.startswith("http") else gc.open_by_key(sheet_id)
    ws = sh.worksheet("NganHangCauHoi")
    vals = ws.get_all_values()
    if len(vals) < 2:
        print("Bảng tính chưa có dữ liệu câu hỏi.")
        return

    td = [str(t).strip() for t in vals[0]]
    ci = lambda ten, md: td.index(ten) if ten in td else md
    C_MA, C_ND, C_TEN, C_ID, C_TT = ci("Mã câu", 0), ci("Nội dung", 6), ci("Tên file", 15), ci("File ID", 17), ci("Trạng thái duyệt", 20)
    C_ANH = next((i for i, t in enumerate(td) if t.lower() == "link ảnh"), 22)
    C_LOC = td.index("Lọc hình (AI)") if "Lọc hình (AI)" in td else None
    C_TIN = td.index("Độ tin cậy hình") if "Độ tin cậy hình" in td else None
    so_cot = max(len(td), C_ANH + 1, 23)

    patterns = config.get("BO_LOC_KY_THUAT", {}).get("bieu_thuc_nhan_dien_hinh", [])
    RE_CUE = re.compile("|".join(patterns), re.IGNORECASE) if patterns else RE_CUE_MAC_DINH
    min_w = config.get("BO_LOC_KY_THUAT", {}).get("min_width", 50)
    min_h = config.get("BO_LOC_KY_THUAT", {}).get("min_height", 50)

    nhom, so_tay = {}, 0
    for row_num, rv in enumerate(vals[1:], start=2):
        rv = (rv + [""] * so_cot)[:so_cot]
        ma, fid = rv[C_MA].strip(), rv[C_ID].strip()
        if rv[C_TT].strip() == "Loại" or not fid or not ma:
            continue
        if C_LOC is not None and rv[C_LOC].strip():
            continue                                   # câu đã được LocHinh (AI) xét: tôn trọng
        if C_TIN is not None and rv[C_TIN].strip() == "tay":
            so_tay += 1                                # [BỔ SUNG G1] thầy đã chỉnh hình trên trang duyệt: khoá
            continue
        m = re.search(r"\(câu\s*([^)]+)\)", rv[C_TEN], re.I)
        nhom.setdefault(fid, []).append({
            "ma": ma, "nd": rv[C_ND].strip(), "so_cau": (m.group(1).strip() if m else ""),
            "link_cu": rv[C_ANH].strip(), "tin_cu": rv[C_TIN].strip() if C_TIN is not None else ""})
    print(f"🔎 {sum(len(v) for v in nhom.values())} câu từ {len(nhom)} file đề gốc."
          + (f" (bỏ qua {so_tay} câu thầy đã chỉnh tay)" if so_tay else ""), flush=True)
    cu = {it["ma"]: (it["link_cu"], it["tin_cu"]) for ds_ in nhom.values() for it in ds_}   # [BỔ SUNG G15, G16]
    ai = {"goi": None, "model": [], "con": 0}                  # [BỔ SUNG G7]
    if KIEM_AI:
        try:
            import doc_de as X
            ai.update(goi=X.goi_gemini, model=X.doc_cau_hinh(sh), con=KIEM_AI_TOI_DA)
            print(f"🤖 AI xác nhận hình: BẬT (tối đa {KIEM_AI_TOI_DA} lượt), model: {', '.join(ai['model'])}", flush=True)
        except Exception as e:
            print(f"⚠️ Không bật được AI xác nhận hình ({str(e)[:100]}) – chạy không có AI.", flush=True)

    chuan = doc_hinh_chuan()
    ket_qua, bao_cao = {}, []
    for fid, ds in nhom.items():
        try:
            meta = drive.files().get(fileId=fid, fields="name,mimeType", supportsAllDrives=True).execute()
            mime = meta.get("mimeType", "")
            if mime == "application/vnd.google-apps.document":
                req = drive.files().export_media(fileId=fid, mimeType="application/pdf")
            elif mime == "application/pdf":
                req = drive.files().get_media(fileId=fid, supportsAllDrives=True)
            else:
                continue
            fh = io.BytesIO()
            dl = MediaIoBaseDownload(fh, req)
            xong = False
            while not xong:
                _, xong = dl.next_chunk()
            doc = fitz.open(stream=fh.getvalue(), filetype="pdf")
            pages, dong, neo, hinh = trich_pdf(doc, min_w, min_h)
            if not neo:
                print(f"⚠️ {meta.get('name')}: không thấy dòng 'Câu N.' (PDF scan hoặc định dạng khác) – bỏ qua.", flush=True)
                doc.close()
                continue
            kq_gan = gan_hinh_cho_cau(pages, dong, neo, hinh)
            n_nhom = ap_dung_nhom_chung(neo, dong, hinh, kq_gan)              # [BỔ SUNG G13]
            if n_nhom:
                print("   (%d nhóm câu dùng chung hình)" % n_nhom, flush=True)
            md5_cau = hinh_trung_giua_cau(kq_gan)                              # [BỔ SUNG G12]
            ten_cache = {}

            for h in hinh:                                   # [BỔ SUNG G8] hình mồ côi
                if chu_so_huu(neo, pages, h["page"], h["col"], h["bbox"][1])[0] is None:
                    bao_cao.append({"ma_cau": "(không thuộc câu nào)", "so_cau": "", "file": meta.get("name", ""), "diem_khop": "",
                                    "trang": h["page"] + 1, "muc": "can_xem", "link_cu": "",
                                    "link_moi": "images/" + luu_hinh(doc, h, False),
                                    "ghi_chu": "hình đứng trước 'Câu' đầu tiên – không gán cho câu nào"})
            khop_ds = [(it,) + khop_cau(it["so_cau"], it["nd"], neo, kq_gan) for it in ds]
            dem_neo = {}                                     # [BỔ SUNG G4]
            for _it, _nid, _d in khop_ds:
                if _nid is not None:
                    dem_neo[_nid] = dem_neo.get(_nid, 0) + 1

            for it, nid, diem in khop_ds:
                co_cue = bool(RE_CUE.search(it["nd"]))
                dong_bc = {"ma_cau": it["ma"], "so_cau": it["so_cau"], "file": meta.get("name", ""),
                           "diem_khop": round(diem, 2), "trang": "", "muc": "", "link_cu": it["link_cu"],
                           "link_moi": "", "ghi_chu": "", "ly_do": "", "link_de_xuat": ""}
                if nid is None:
                    dong_bc["muc"], dong_bc["ghi_chu"] = "can_xem", "không khớp được câu trong PDF – giữ nguyên"
                    bao_cao.append(dong_bc)
                    continue
                r = kq_gan[nid]
                dong_bc["trang"] = r["neo"]["page"] + 1
                so_cung = dem_neo.get(nid, 0)
                co_cue_pdf = bool(RE_CUE.search(r["van_ban"]))
                diem_chu = diem_nhan_chu([t for h in r["hinh"] for t in h.get("chu", [])], it["nd"])   # [BỔ SUNG G11]
                if (diem_chu is not None and diem_chu >= 0.5) or r.get("chung"):
                    co_cue_pdf = True                              # nhãn trong hình khớp đề / dòng dẫn nhóm: có liên quan
                ly_do = []
                if r["hinh"]:
                    ten = []
                    for h in r["hinh"]:
                        k = id(h)
                        if k not in ten_cache:
                            ten_cache[k] = luu_hinh(doc, h, GHI_SHEET)
                        ten.append(ten_cache[k])
                    link_moi = ", ".join("images/" + t for t in dict.fromkeys(ten))
                    muc = danh_gia_hang(r["muc"], diem, co_cue)
                    muc, ly = danh_gia_nang_cao(muc, it["nd"], r["van_ban"], len(r["hinh"]), co_cue, co_cue_pdf, so_cung, r["muc"])
                    ly_do += ly
                    muc, ly = danh_gia_bo_sung(muc, r, it["nd"], r["van_ban"], diem_chu, md5_cau)   # [BỔ SUNG G10-G13]
                    ly_do += ly
                    if muc != "cao":                                      # [BỔ SUNG G7]
                        muc, ly, dx = ai_buoc(doc, it["nd"], neo, kq_gan, nid, muc, ai)
                        ly_do += ly
                        dong_bc["link_de_xuat"] = ", ".join(dx)
                    dong_bc["link_moi"], dong_bc["muc"] = link_moi, muc
                    dong_bc["ids_cu"] = sorted({"%d_img%d" % i for h in r["hinh"] for i in h["ids"]})
                    hd, ly = quyet_dinh_ghi(it["link_cu"], it["tin_cu"], link_moi, muc)
                    ly_do += ly
                    if hd == "ghi" and (link_moi != it["link_cu"] or C_TIN is not None):
                        ket_qua[it["ma"]] = (link_moi, muc)
                    elif hd == "giu" and C_TIN is not None and it["tin_cu"] != "can_xem":
                        ket_qua[it["ma"]] = (it["link_cu"], "can_xem")
                        dong_bc["muc"] = "can_xem"
                else:
                    dong_bc["ids_cu"] = []
                    if co_cue:
                        dong_bc["muc"] = "can_xem"
                        dong_bc["ghi_chu"] = "câu nhắc hình nhưng không thấy hình trong PDF" + \
                                             (" – giữ link cũ" if it["link_cu"] else "")
                        if C_TIN is not None and it["tin_cu"] != "can_xem":
                            ket_qua[it["ma"]] = (it["link_cu"], "can_xem")
                        _, ly, dx = ai_buoc(doc, it["nd"], neo, kq_gan, nid, "can_xem", ai)   # [BỔ SUNG G7] tìm ở câu kề
                        ly_do += ly
                        dong_bc["link_de_xuat"] = ", ".join(dx)
                    else:
                        dong_bc["muc"] = "cao"
                dong_bc["ly_do"] = "; ".join(ly_do)
                bao_cao.append(dong_bc)
            doc.close()
        except Exception as e:
            print(f"⚠️ Không xử lý được PDF ({fid[:10]}): {e}", flush=True)

    # ---- báo cáo
    cot_bc = ["ma_cau", "so_cau", "file", "trang", "diem_khop", "muc", "link_cu", "link_moi", "ghi_chu", "ly_do", "link_de_xuat"]
    with open("bao_cao_hinh.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cot_bc, extrasaction="ignore")
        w.writeheader()
        w.writerows(bao_cao)
    dem = {m: sum(1 for b in bao_cao if b["muc"] == m) for m in TEN_MUC}
    print(f"📋 bao_cao_hinh.csv: {len(bao_cao)} câu – cao {dem['cao']}, trung_binh {dem['trung_binh']}, can_xem {dem['can_xem']}", flush=True)

    # ---- chấm trên mẫu đã xác nhận
    if chuan:
        tong = dung = c_tong = c_dung = 0
        for b in bao_cao:
            if b["ma_cau"] not in chuan:
                continue
            du_doan = set(re.findall(r"(\d+)_img(\d+)", " ".join(b.get("ids_cu", []))))
            ok = du_doan == chuan[b["ma_cau"]]
            tong += 1
            dung += ok
            if b["muc"] == "cao":
                c_tong += 1
                c_dung += ok
        if tong:
            print(f"🎯 Mẫu chuẩn: đúng {dung}/{tong} = {dung / tong:.0%}"
                  + (f" | riêng mức 'cao': {c_dung}/{c_tong} = {c_dung / c_tong:.0%}" if c_tong else ""), flush=True)
        print("   (chỉ so được hình raster; hình vector là hình mới, bản cũ không trích được)", flush=True)

    # ---- ghi Sheet
    if GHI_SHEET and ket_qua:
        ma_cot = ws.col_values(C_MA + 1)
        vt = {str(v).strip(): k + 1 for k, v in enumerate(ma_cot) if k > 0 and str(v).strip()}
        link_hien = ws.col_values(C_ANH + 1)                                  # [BỔ SUNG G16] đọc lại ngay trước khi ghi
        tin_hien = ws.col_values(C_TIN + 1) if C_TIN is not None else []
        ket_qua, bo = loc_truoc_khi_ghi(ket_qua, cu, vt, link_hien, tin_hien)
        for ma, ly in bo:
            print(f"⏭️ Bỏ qua {ma}: {ly}.", flush=True)
        for ma, (link, muc) in list(ket_qua.items()):                          # [BỔ SUNG G14]
            if link != str(cu.get(ma, ("", ""))[0]).strip():
                ms = thieu_tep_anh(link)
                if ms:
                    print(f"⚠️ Không ghi {ma}: thiếu tệp ảnh {', '.join(ms)}", flush=True)
                    del ket_qua[ma]
        if ket_qua:
            print(f"💾 Sao lưu trước khi ghi: {ghi_sao_luu(ket_qua, cu)}", flush=True)   # [BỔ SUNG G15]
        col_anh = gspread.utils.rowcol_to_a1(1, C_ANH + 1).rstrip("1")
        cap = []
        for ma, (link, muc) in ket_qua.items():
            if ma not in vt:
                continue
            cap.append({"range": "%s%d" % (col_anh, vt[ma]), "values": [[link]]})
            if C_TIN is not None:
                col_tin = gspread.utils.rowcol_to_a1(1, C_TIN + 1).rstrip("1")
                cap.append({"range": "%s%d" % (col_tin, vt[ma]), "values": [[muc]]})
        if cap:
            ws.batch_update(cap, value_input_option="RAW")
        print(f"✨ Đã ghi {len(ket_qua)} câu vào Sheet.", flush=True)
    elif ket_qua:
        print(f"ℹ️ Chạy thử: sẽ có {len(ket_qua)} câu thay đổi. Đặt GHI_SHEET=1 để ghi thật.", flush=True)


if __name__ == "__main__":
    quet_drive_va_gan_anh()
