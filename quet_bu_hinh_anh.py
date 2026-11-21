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
TOI_DA_HINH_TU_DONG = 3        # [21/11] quá số này => nghi gắn dư, hạ xuống can_xem và KHÔNG ghi đè link cũ
DIEN_TICH_TOI_THIEU = 0.003    # [21/11 v2] hình nhỏ hơn 0,3% diện tích trang coi là ký hiệu/đường kẻ, bỏ
NGUONG_CHUAN = 0.9            # [21/11 v2] mức 'cao' đúng < 90% trên hinh_chuan.csv thì KHÔNG ghi Sheet (đặt EP_GHI=1 để ép)
AI_XAC_NHAN = os.environ.get("AI_XAC_NHAN", "") == "1"   # [v3] bật: Gemini nhìn hình + lời văn để HẠ mức câu nghi gắn sai
AI_TOI_DA = int(os.environ.get("AI_TOI_DA", "60"))       # [v3] số lần gọi AI tối đa mỗi lần chạy
AI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
BO_QUA_DA_DUYET = os.environ.get("QUET_CA_DA_DUYET", "") != "1"   # [v3] mặc định KHÔNG đụng câu đã duyệt / thầy đã chọn tay
TOI_DA_GHI_MOI_LAN = int(os.environ.get("TOI_DA_GHI", "300"))
RE_LOI_GIAI = re.compile(r"^\s*(H[ƯU][ỚO]NG\s*D[ẪA]N|L[ỜO]I\s*GI[ẢA]I|ĐÁP\s*ÁN|BÀI\s*GI[ẢA]I|GI[ẢA]I\s*CHI\s*TI[ẾE]T)", re.IGNORECASE)
MUC = {"cao": 0, "trung_binh": 1, "can_xem": 2}
TEN_MUC = ["cao", "trung_binh", "can_xem"]

RE_NEO = re.compile(r"^\s*C[âÂ]u\s*(\d{1,3})\s*[.:)]", re.IGNORECASE)
RE_PHAN = re.compile(r"^\s*PH[ẦẬA]N\s+(I{1,3}|IV|V|\d)\b", re.IGNORECASE)
RE_PHUONG_AN = re.compile(r"^\s*[A-Da-d]\s*[.)]")
RE_CUE_MAC_DINH = re.compile(r"Hình|Đồ thị|Mạch điện|Giản đồ|Sơ đồ|Biểu đồ|trục|vẽ|bên dưới|như sau", re.IGNORECASE)


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


def so_hinh_toi_da(noi_dung):
    """[21/11 v2] Số hình hợp lý theo lời văn: nhắc 'Hình 1, Hình 2...' hoặc hỏi 'hình nào/đồ thị nào' (đáp án là hình) thì cho nhiều hơn."""
    nd = nfc(noi_dung or "")
    nhac = len(set(re.findall(r"[Hh]ình\s*([0-9]+|[a-dA-D])\b", nd)))
    dap_an_la_hinh = 4 if re.search(r"(hình|đồ thị|sơ đồ|mạch|giản đồ)\s*nào", nd, re.IGNORECASE) else 0
    return max(TOI_DA_HINH_TU_DONG, nhac, dap_an_la_hinh)


def lay_byte_hinh(doc, h):
    """[v3] Lấy byte ảnh để gửi AI (không ghi đĩa)."""
    page = doc[h["page"]]
    if h["raster"]:
        bi = doc.extract_image(h["xrefs"][0])
        return bi["image"], "image/" + ("jpeg" if bi["ext"] in ("jpg", "jpeg") else bi["ext"])
    clip = (fitz.Rect(*h["bbox"]) + (-4, -4, 4, 4)) & page.rect
    return page.get_pixmap(clip=clip, dpi=130).tobytes("png"), "image/png"


def ai_xac_nhan(noi_dung, anh):
    """[v3] Hỏi Gemini: các hình này có thuộc câu hỏi không? Trả (True/False/None, lý do). None = không hỏi được => không đổi mức.
    Chỉ dùng để HẠ mức (nghi gắn sai/dư), không bao giờ tự nâng mức."""
    import urllib.request
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key or not anh:
        return None, ""
    lenh = ("Đây là một câu hỏi Vật lí THPT và các hình được gắn vào câu này.\n--- CÂU HỎI ---\n" + (noi_dung or "")[:1800] +
            "\n--- HẾT ---\nHãy kiểm tra: (1) mỗi hình có đúng là hình minh hoạ/đồ thị/sơ đồ của CHÍNH câu này không; "
            "(2) có hình thừa hoặc thuộc câu khác không; (3) câu cần hình nhưng hình không phải hình đó không. "
            "Chỉ trả JSON một dòng: {\"khop\": true|false, \"ly_do\": \"ngắn gọn\"}. khop=true chỉ khi TẤT CẢ hình đều đúng và không thừa.")
    parts = [{"text": lenh}] + [{"inline_data": {"mime_type": m, "data": base64.b64encode(b).decode()}} for b, m in anh]
    body = json.dumps({"contents": [{"parts": parts}], "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}}).encode()
    url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s" % (AI_MODEL, key)
    try:
        rq = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(rq, timeout=60) as rs:
            kq = json.loads(rs.read().decode("utf-8"))
        txt = kq["candidates"][0]["content"]["parts"][0]["text"]
        j = json.loads(re.sub(r"^```json|```$", "", txt.strip()).strip())
        return bool(j.get("khop")), str(j.get("ly_do", ""))[:160]
    except Exception as e:
        print("   (AI xác nhận lỗi, bỏ qua: %s)" % str(e)[:100], flush=True)
        return None, ""


def _dien_tich(b):
    return max(b[2] - b[0], 0) * max(b[3] - b[1], 0)


def loc_hinh_du(hinh):
    """[21/11] Bỏ hình nằm lọt trong hình khác (mảnh vụn của cùng một hình) và hình trùng vị trí."""
    giu = []
    for i, h in enumerate(hinh):
        du = False
        for j, k in enumerate(hinh):
            if i == j or h["page"] != k["page"]:
                continue
            gt = (max(h["bbox"][0], k["bbox"][0]), max(h["bbox"][1], k["bbox"][1]),
                  min(h["bbox"][2], k["bbox"][2]), min(h["bbox"][3], k["bbox"][3]))
            ah = _dien_tich(h["bbox"])
            if ah <= 0 or gt[2] <= gt[0] or gt[3] <= gt[1]:
                continue
            tl = _dien_tich(gt) / ah
            if tl >= 0.8 and (_dien_tich(k["bbox"]) > ah or (_dien_tich(k["bbox"]) == ah and j < i)):
                du = True
                break
        if not du:
            giu.append(h)
    return giu


def hinh_trong_loi_giai(dong, neo_a, h):
    """[21/11] Hình nằm SAU dòng 'Hướng dẫn giải / Lời giải / Đáp án' (cùng cột, dưới câu chủ) là hình của lời giải, không gắn vào đề."""
    for d in dong:
        if d["page"] != h["page"] or not RE_LOI_GIAI.match(d["text"]):
            continue
        if d["col"] not in (h["col"], -1) and h["col"] != -1:
            continue
        if neo_a["bbox"][1] < d["bbox"][1] <= h["bbox"][1] + 3 and d["page"] == neo_a["page"]:
            return True
    return False


def hinh_lech_sang_cau_sau(dong, neo, a, h):
    """[v3] Hình sát ngay trên tiêu đề 'Câu N+1' nhưng cách xa chữ của câu chủ => nhiều khả năng thuộc câu sau."""
    sau = [x for x in neo if x["page"] == h["page"] and x["bbox"][1] > h["bbox"][3]
           and (x["col"] in (h["col"], -1) or h["col"] == -1)]
    if not sau:
        return False
    gap_sau = min(x["bbox"][1] for x in sau) - h["bbox"][3]
    chu_tren = [d["bbox"][3] for d in dong if d["page"] == h["page"] and d["bbox"][3] <= h["bbox"][1] + 3
                and d["col"] in (h["col"], -1) and d["bbox"][1] >= a["bbox"][1] - 1]
    gap_chu = (h["bbox"][1] - max(chu_tren)) if chu_tren else 0
    return gap_sau < 12 and gap_chu > 50


def gan_hinh_cho_cau(pages, dong, neo, hinh):
    """Trả {id_neo: {"hinh": [...], "muc": ..., "van_ban": "..."}}"""
    kq = {a["id"]: {"hinh": [], "muc": "cao", "van_ban": [], "neo": a} for a in neo}
    for d in dong:
        a, _ = chu_so_huu(neo, pages, d["page"], d["col"], d["bbox"][1])
        if a:
            kq[a["id"]]["van_ban"].append(d["text"])
    for h in sorted(loc_hinh_du(hinh), key=thu_tu_doc):
        a, muc = chu_so_huu(neo, pages, h["page"], h["col"], h["bbox"][1])
        if not a:
            continue
        if hinh_trong_loi_giai(dong, a, h):
            continue
        pg_ = pages[h["page"]]
        if _dien_tich(h["bbox"]) < DIEN_TICH_TOI_THIEU * pg_["w"] * pg_["h"]:
            continue                    # [21/11 v2] ký hiệu/đường kẻ nhỏ
        r = kq[a["id"]]
        if hinh_lech_sang_cau_sau(dong, neo, a, h):
            muc = "can_xem"             # [v3] vẫn gắn nhưng hạ mức để thầy xem
        r["hinh"].append(h)
        if MUC[muc] > MUC[r["muc"]]:
            r["muc"] = muc
    for r in kq.values():
        r["van_ban"] = " ".join(r["van_ban"])
        if len(r["hinh"]) > TOI_DA_HINH_MOI_CAU:
            r["hinh"] = r["hinh"][:TOI_DA_HINH_MOI_CAU]
            r["muc"] = "can_xem"
        elif len(r["hinh"]) > TOI_DA_HINH_TU_DONG:
            r["nhieu"] = True           # [21/11 v2] quyết định ở vòng chính, vì còn phải xét lời văn của câu
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
    if os.environ.get("TAO_CHUAN") == "1":     # [v3] sinh hinh_chuan.csv từ các câu thầy đã chọn tay / đã duyệt (chỉ link dạng _pN_imgM)
        n_ = 0
        with open("hinh_chuan.csv", "w", encoding="utf-8-sig", newline="") as f:
            w0 = csv.writer(f)
            w0.writerow(["ma_cau", "link_dung"])
            for rv in vals[1:]:
                rv = (rv + [""] * so_cot)[:so_cot]
                lk = rv[C_ANH].strip()
                if rv[C_MA].strip() and re.search(r"_p\d+_img\d+", lk) and (
                        rv[C_TT].strip() == "Đã duyệt" or (C_TIN is not None and rv[C_TIN].strip() == "tay")):
                    w0.writerow([rv[C_MA].strip(), lk])
                    n_ += 1
        print(f"📝 Đã tạo hinh_chuan.csv với {n_} câu đã xác nhận.", flush=True)
        return

    patterns = config.get("BO_LOC_KY_THUAT", {}).get("bieu_thuc_nhan_dien_hinh", [])
    RE_CUE = re.compile("|".join(patterns), re.IGNORECASE) if patterns else RE_CUE_MAC_DINH
    min_w = config.get("BO_LOC_KY_THUAT", {}).get("min_width", 50)
    min_h = config.get("BO_LOC_KY_THUAT", {}).get("min_height", 50)

    nhom = {}
    for row_num, rv in enumerate(vals[1:], start=2):
        rv = (rv + [""] * so_cot)[:so_cot]
        ma, fid = rv[C_MA].strip(), rv[C_ID].strip()
        if rv[C_TT].strip() == "Loại" or not fid or not ma:
            continue
        if BO_QUA_DA_DUYET and rv[C_ANH].strip() and (rv[C_TT].strip() == "Đã duyệt"
                                                       or (C_TIN is not None and rv[C_TIN].strip() == "tay")):
            continue                                   # [v3] đã người duyệt / thầy chọn tay: khoá, không quét đè
        if C_LOC is not None and rv[C_LOC].strip():
            continue                                   # câu đã được LocHinh (AI) xét: tôn trọng
        m = re.search(r"\(câu\s*([^)]+)\)", rv[C_TEN], re.I)
        nhom.setdefault(fid, []).append({
            "ma": ma, "nd": rv[C_ND].strip(), "so_cau": (m.group(1).strip() if m else ""),
            "link_cu": rv[C_ANH].strip(), "tin_cu": rv[C_TIN].strip() if C_TIN is not None else ""})
    print(f"🔎 {sum(len(v) for v in nhom.values())} câu từ {len(nhom)} file đề gốc.", flush=True)

    chuan = doc_hinh_chuan()
    ti_le_cao = None
    ket_qua, bao_cao = {}, []
    ai_da_goi = [0]
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
            ten_cache = {}

            md5_neo = {}        # [v3] cùng một ảnh bị gắn cho nhiều câu khác nhau trong một file => nghi
            for id_, r_ in kq_gan.items():
                for h_ in r_["hinh"]:
                    if h_.get("md5"):
                        md5_neo.setdefault(h_["md5"], set()).add(id_)
            dem_nid = {}
            for it0 in ds:      # [21/11 v2] nhiều dòng Sheet cùng khớp 1 'Câu N' => nhập nhằng
                n0, _ = khop_cau(it0["so_cau"], it0["nd"], neo, kq_gan)
                if n0 is not None:
                    dem_nid[n0] = dem_nid.get(n0, 0) + 1
            for it in ds:
                nid, diem = khop_cau(it["so_cau"], it["nd"], neo, kq_gan)
                co_cue = bool(RE_CUE.search(it["nd"]))
                dong_bc = {"ma_cau": it["ma"], "so_cau": it["so_cau"], "file": meta.get("name", ""),
                           "diem_khop": round(diem, 2), "trang": "", "muc": "", "link_cu": it["link_cu"],
                           "link_moi": "", "ghi_chu": ""}
                if nid is None:
                    dong_bc["muc"], dong_bc["ghi_chu"] = "can_xem", "không khớp được câu trong PDF – giữ nguyên"
                    bao_cao.append(dong_bc)
                    continue
                r = kq_gan[nid]
                dong_bc["trang"] = r["neo"]["page"] + 1
                if r["hinh"]:
                    ten = []
                    for h in r["hinh"]:
                        k = id(h)
                        if k not in ten_cache:
                            ten_cache[k] = luu_hinh(doc, h, GHI_SHEET)
                        ten.append(ten_cache[k])
                    link_moi = ", ".join("images/" + t for t in dict.fromkeys(ten))
                    muc = danh_gia_hang(r["muc"], diem, co_cue)
                    if r.get("nhieu") and len(r["hinh"]) > so_hinh_toi_da(it["nd"]):
                        muc = "can_xem"
                        dong_bc["ghi_chu"] = "gắn %d hình, nhiều hơn mức lời văn gợi ý – nghi gắn dư" % len(r["hinh"])
                    if dem_nid.get(nid, 0) > 1:
                        muc = "can_xem"
                        dong_bc["ghi_chu"] = "nhiều dòng Sheet cùng khớp một câu trong PDF – nghi nhầm câu"
                    if not co_cue and len(r["hinh"]) >= 2:
                        muc = "can_xem"   # câu không nhắc hình mà có ≥2 hình: gần như chắc gắn dư
                    if any(len(md5_neo.get(h_.get("md5"), ())) > 1 for h_ in r["hinh"] if h_.get("md5")):
                        muc = "can_xem"
                        dong_bc["ghi_chu"] = "cùng một ảnh bị gắn cho nhiều câu – nghi gắn nhầm"
                    if AI_XAC_NHAN and muc != "can_xem" and len(r["hinh"]) <= 4 and ai_da_goi[0] < AI_TOI_DA:
                        try:
                            anh_ai = [lay_byte_hinh(doc, h_) for h_ in r["hinh"]]
                            anh_ai = [x for x in anh_ai if len(x[0]) < 3_000_000]
                            ai_da_goi[0] += 1
                            khop_ai, ly_do = ai_xac_nhan(it["nd"], anh_ai)
                            if khop_ai is False:
                                muc = "can_xem"
                                dong_bc["ghi_chu"] = "AI: hình không khớp câu – " + ly_do
                        except Exception as e:
                            print("   (AI bỏ qua: %s)" % str(e)[:80], flush=True)
                    dong_bc["link_moi"], dong_bc["muc"] = link_moi, muc
                    dong_bc["ids_cu"] = sorted({"%d_img%d" % i for h in r["hinh"] for i in h["ids"]})
                    if link_moi != it["link_cu"]:
                        if muc == "cao" or not it["link_cu"]:
                            ket_qua[it["ma"]] = (link_moi, muc)
                        else:   # [21/11] chưa chắc: giữ link cũ, chỉ đánh dấu mức tin cậy để thầy xem
                            dong_bc["ghi_chu"] = (dong_bc["ghi_chu"] + " | " if dong_bc["ghi_chu"] else "") + "chưa chắc – giữ link cũ, hình đề xuất nằm ở link_moi"
                            if C_TIN is not None and it["tin_cu"] != muc:
                                ket_qua[it["ma"]] = (it["link_cu"], muc)
                else:
                    dong_bc["ids_cu"] = []
                    if co_cue:
                        dong_bc["muc"] = "can_xem"
                        dong_bc["ghi_chu"] = "câu nhắc hình nhưng không thấy hình trong PDF" + \
                                             (" – giữ link cũ" if it["link_cu"] else "")
                        if C_TIN is not None and it["tin_cu"] != "can_xem":
                            ket_qua[it["ma"]] = (it["link_cu"], "can_xem")
                    else:
                        dong_bc["muc"] = "cao"
                bao_cao.append(dong_bc)
            doc.close()
        except Exception as e:
            print(f"⚠️ Không xử lý được PDF ({fid[:10]}): {e}", flush=True)

    # ---- báo cáo
    cot_bc = ["ma_cau", "so_cau", "file", "trang", "diem_khop", "muc", "link_cu", "link_moi", "ghi_chu"]
    with open("bao_cao_hinh.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cot_bc, extrasaction="ignore")
        w.writeheader()
        w.writerows(bao_cao)
    ly_do_dem = {}      # [v3] thống kê lí do câu bị hạ xuống can_xem để biết sửa ở đâu
    for b in bao_cao:
        if b["muc"] == "can_xem" and b["ghi_chu"]:
            k_ = re.sub(r"\d+", "N", b["ghi_chu"].split(" | ")[0])[:60]
            ly_do_dem[k_] = ly_do_dem.get(k_, 0) + 1
    for k_, v_ in sorted(ly_do_dem.items(), key=lambda x: -x[1])[:8]:
        print(f"   · {v_:4d} câu: {k_}", flush=True)
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
        if c_tong:
            ti_le_cao = c_dung / c_tong     # [21/11 v2]
        if tong:
            print(f"🎯 Mẫu chuẩn: đúng {dung}/{tong} = {dung / tong:.0%}"
                  + (f" | riêng mức 'cao': {c_dung}/{c_tong} = {c_dung / c_tong:.0%}" if c_tong else ""), flush=True)
        print("   (chỉ so được hình raster; hình vector là hình mới, bản cũ không trích được)", flush=True)

    # ---- ghi Sheet
    if GHI_SHEET and ket_qua and ti_le_cao is not None and ti_le_cao < NGUONG_CHUAN and os.environ.get("EP_GHI") != "1":
        print(f"⛔ Mức 'cao' chỉ đúng {ti_le_cao:.0%} < {NGUONG_CHUAN:.0%} trên hinh_chuan.csv – KHÔNG ghi Sheet. "
              "Xem bao_cao_hinh.csv, chỉnh rồi chạy lại (hoặc EP_GHI=1 để ép ghi).", flush=True)
    elif GHI_SHEET and ket_qua:
        # [21/11 v2] sao lưu link cũ trước khi ghi, để hoàn tác được; ghi tối đa TOI_DA_GHI_MOI_LAN câu mỗi lần
        cu_map = {it["ma"]: (it["link_cu"], it["tin_cu"]) for ds_ in nhom.values() for it in ds_}
        ds_ghi = list(ket_qua.items())[:TOI_DA_GHI_MOI_LAN]
        ket_qua = dict(ds_ghi)
        import time as _t
        ten_sl = "sao_luu_link_anh_%s.csv" % _t.strftime("%Y%m%d_%H%M%S")
        with open(ten_sl, "w", encoding="utf-8-sig", newline="") as f:
            w_ = csv.writer(f)
            w_.writerow(["ma_cau", "link_cu", "tin_cu"])
            for ma_, _v in ds_ghi:
                w_.writerow([ma_, *cu_map.get(ma_, ("", ""))])
        print(f"💾 Đã sao lưu link cũ của {len(ds_ghi)} câu vào {ten_sl}", flush=True)
        ma_cot = ws.col_values(C_MA + 1)
        vt = {str(v).strip(): k + 1 for k, v in enumerate(ma_cot) if k > 0 and str(v).strip()}
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
