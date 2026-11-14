"""
tai_tai_lieu.py – XƯỞNG TÌM & LỌC TÀI LIỆU (Python, chạy trên GitHub Actions) – thay phần "chạy ngầm" của Agent tải tài liệu.

Hướng A (Gmail cá nhân): Python làm phần NẶNG, Apps Script chỉ làm bước CUỐI NHẸ là tải từng file vào Drive.

  Python (file này):
    1. Chọn 1 chủ đề trong tab ChuDe (xoay vòng theo "Lần thử cuối", giống chayNgam).
    2. Tìm kiếm, quét các trang kết quả lấy link file.
    3. Lọc phạm vi (HSG_B / TN / HL / KT), loại môn khác, loại chương trình cũ, loại link đã tải (tab DaTai).
    4. Kiểm tra từng link: không phải HTML, đủ lớn, đúng định dạng (PDF/Word/Excel/PPT/ZIP...), tên không phải file mẫu.
    5. Ghi các link đạt vào tab SanSangTai (trạng thái "Chờ"), cập nhật ChuDe và NhatKyChay.
  Apps Script (TaiTuSanSang.gs): đọc SanSangTai, gọi download_document_ (giữ nguyên chống trùng MD5, DaTai, thư mục nhóm).

Biến môi trường (GitHub Secrets): GOOGLE_CREDENTIALS (như doc_de.py).
  Không cần khoá Gemini. Tìm kiếm dùng tim_kiem.py (DuckDuckGo qua thư viện ddgs; có BRAVE_API_KEY thì thêm Brave).
  Workflow phải cài: gspread google-auth google-api-python-client requests ddgs (cùng bộ với workflow của tim_kiem.py và doc_de.py).
  THOI_GIAN_TOI_DA_PHUT (mặc định 20), SO_FILE_TOI_DA (mặc định 25).

LƯU Ý QUYỀN: tài khoản dịch vụ phải là NGƯỜI CHỈNH SỬA (Editor) của sheet "Download Agent - Quản lý",
vì file này ghi vào ChuDe, NhatKyChay và tạo tab SanSangTai.
"""
import datetime as dt
import os
import re
import time
import unicodedata
from urllib.parse import unquote, urljoin

import requests

import doc_de as D   # dùng chung ID_BANG_DOWNLOAD, ket_noi(), TZ
import tim_kiem as TK   # xưởng tìm kiếm có sẵn (cần pip install ddgs)

# ---------------- CẤU HÌNH ----------------
TAB_CHU_DE, TAB_DA_TAI, TAB_NHAT_KY, TAB_SAN_SANG = "ChuDe", "DaTai", "NhatKyChay", "SanSangTai"
COT_SS = ["Thời gian", "URL", "Tên file", "Chủ đề", "Loại", "Thư mục", "Kích thước (byte)", "Trạng thái", "Số lần thử", "Ghi chú"]

# Bảng tính của Agent tải tài liệu = bảng mà Apps Script mở (thuộc tính KHOA_BANG), tên "Download Agent - Quản lý".
# ID này KHÁC ID_BANG_DOWNLOAD trong doc_de.py. Nếu sai, lấy ID trong địa chỉ của sheet (giữa /d/ và /edit) hoặc đặt biến môi trường ID_BANG_TAI.
ID_BANG_TAI = os.environ.get("ID_BANG_TAI", "").strip() or "1GhOqNxqIeXrPYRFLJiZtoS7zr_u-EPVE_O38KMa-dAw"

THOI_GIAN_TOI_DA_PHUT = float(os.environ.get("THOI_GIAN_TOI_DA_PHUT", "20"))
SO_FILE_TOI_DA = int(os.environ.get("SO_FILE_TOI_DA", "25"))   # tối đa link xếp hàng mỗi lượt
SO_FILE_MOI_TRANG = 10          # tối đa link lấy từ một trang
SO_LINK_QUET_TOI_DA = 30        # tối đa link file đọc từ một trang
SO_TRANG_QUET_TOI_DA = 8        # tối đa trang quét mỗi lượt
SO_KET_QUA_TIM = 10
SO_TRUY_VAN_TOI_DA = 4          # số truy vấn thử tối đa mỗi lượt
KICH_THUOC_TOI_THIEU = 20 * 1024            # giống Mã.gs
KICH_THUOC_TOI_DA = 45 * 1024 * 1024        # UrlFetchApp của Apps Script tối đa ~50 MB
NAM_HOC_TOI_DA = 4
VONG_NAM_HOC = [0, 1, 0, 2, 0, 1, 3]
BAT_DAU = time.time()
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "vi-VN,vi;q=0.9"}

THU_MUC_NHOM = {"HSG_B": "1. De HSG bang B", "TN": "2. De tot nghiep THPT", "HL": "3. Hoc lieu", "KT": "4. De kiem tra"}


def con_thoi_gian(du_tru=0):
    return time.time() - BAT_DAU < THOI_GIAN_TOI_DA_PHUT * 60 - du_tru


def bay_gio_so():
    """Ngày-giờ hiện tại (giờ VN) dạng số ngày của Google Sheets, để ô luôn là ngày thật chứ không phải chữ."""
    bay_gio = dt.datetime.now(D.TZ).replace(tzinfo=None)
    return (bay_gio - dt.datetime(1899, 12, 30)).total_seconds() / 86400.0


DINH_DANG_NGAY = {"numberFormat": {"type": "DATE_TIME", "pattern": "dd/MM/yyyy HH:mm:ss"}}


def bay_gio_iso():
    # ISO được Google Sheets nhận là ngày-giờ ở mọi ngôn ngữ/vùng
    return dt.datetime.now(D.TZ).strftime("%Y-%m-%d %H:%M:%S")


# ---------------- BỘ LỌC (chuyển từ Mã.gs, so trên chuỗi đã bỏ dấu) ----------------
def bo_dau(s):
    t = str(s or "")
    try:
        t = unquote(t)
    except Exception:
        pass
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.replace("đ", "d").replace("Đ", "d").lower()
    t = re.sub(r"[_\-./+=&?%]+", " ", t)
    return re.sub(r"\s+", " ", t)


def _re(ds):
    return re.compile(r"\b(" + "|".join(ds) + r")\b")


RE_NGOAI_PHAM_VI = _re(["bang a", "thpt chuyen", "truong chuyen", "lop chuyen", "he chuyen", "doi tuyen", "chon doi tuyen",
                        "olympic", "olympiad", "30 ?4", "duyen hai", "trai he hung vuong", "hsg quoc gia", "hsgqg",
                        "hoc sinh gioi quoc gia", "vpho", "ipho", "apho"])
RE_NGOAI_TN = _re(["hsg", "hoc sinh gioi", "olympic", "olympiad", "doi tuyen", "giua ki", "giua ky", "giua hk",
                   "cuoi ki", "cuoi ky", "cuoi hk", "kiem tra 15", "kiem tra 1 tiet"])
RE_NGOAI_HOC_LIEU = _re(["olympic", "olympiad", "doi tuyen", "hsg quoc gia", "hsgqg", "hoc sinh gioi quoc gia",
                         "bai giang", "slide", "pptx?", "powerpoint", "giao an", "ke hoach bai day", "khbd"])
RE_DE_KHAC_KT = re.compile(r"\b(hsg|hoc sinh gioi|tot nghiep|thi thu|thpt quoc gia)\b")
RE_MON_KHAC = re.compile(r"\b(toan hoc|mon toan|de toan|toan 1[0-2]|hoa hoc|mon hoa|hoa 1[0-2]|sinh hoc|mon sinh|sinh 1[0-2]|ngu van|mon van|tieng anh|anh van|lich su|dia li|dia ly|gdcd|giao duc cong dan|tin hoc|cong nghe|ktpl|kinh te va phap luat)\b")
RE_VAT_LI = re.compile(r"\b(vat li|vat ly|vatli|vatly|ly|ly 1[0-2]|li 1[0-2]|mon ly|mon li)\b")
RE_CT_CU = _re(["chuong trinh 2006", "chuong trinh cu", "sgk co ban", "sach co ban", "nang cao 1[0-2]", "vat li 1[0-2] nang cao",
                "vat ly 1[0-2] nang cao", "song anh sang", "luong tu anh sang", "mach dao dong", "dao dong dien tu",
                "dong dien trong cac moi truong", "mat va cac dung cu quang", "thau kinh mong", "lang kinh",
                "phan xa toan phan", "khuc xa anh sang", "thuyet tuong doi", "tu vi mo den vi mo",
                "cuc dai giao thoa anh sang", "quang pho", "tia x", "tia ron ghen"])
RE_TEN_MAU = re.compile(r"(dummy|sample|lorem|placeholder|example)", re.I)
RE_DUOI_FILE = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|zip|rar|7z)(\?|#|$)", re.I)


def la_sach_khac(t):
    return bool(re.search(r"\b(canh dieu|chan troi( sang tao)?|ctst)\b", t)) and not re.search(r"\b(ket noi|kntt)\b", t)


PHAM_VI = {
    "HSG_B": {"ten": "HSG bảng B", "loai_tru": RE_NGOAI_PHAM_VI},
    "TN": {"ten": "Tốt nghiệp THPT", "loai_tru": RE_NGOAI_TN},
    "HL": {"ten": "Học liệu Kết nối tri thức", "kiem_tra": lambda t: bool(RE_NGOAI_HOC_LIEU.search(t)) or la_sach_khac(t)},
    "KT": {"ten": "Đề kiểm tra Kết nối tri thức",
           "kiem_tra": lambda t: bool(RE_NGOAI_HOC_LIEU.search(t) or RE_DE_KHAC_KT.search(t)) or la_sach_khac(t)},
}


def la_ngoai_pham_vi(loai, *chuoi):
    pv = PHAM_VI.get(loai)
    if not pv:
        return False
    t = bo_dau(" ".join(str(c or "") for c in chuoi))
    if RE_CT_CU.search(t):
        return True
    if "kiem_tra" in pv:
        return pv["kiem_tra"](t)
    return bool(pv["loai_tru"].search(t))


def la_mon_khac(*chuoi):
    t = bo_dau(" ".join(str(c or "") for c in chuoi))
    return bool(RE_MON_KHAC.search(t)) and not RE_VAT_LI.search(t)


def doc_loai(ten_chu_de, gia_tri_cot):
    loai = str(gia_tri_cot or "").strip().upper()
    if loai in PHAM_VI:
        return loai
    t = bo_dau(ten_chu_de)
    if re.search(r"tot nghiep|thpt quoc gia|thi thu", t):
        return "TN"
    if re.search(r"hoc sinh gioi|\bhsg\b", t):
        return "HSG_B"
    if re.search(r"kiem tra|giua ki|cuoi ki|giua hk|cuoi hk", t):
        return "KT"
    return "HL"


def lam_sach_ten(ten):
    if not ten:
        return ""
    s = unquote(str(ten).strip())
    s = re.split(r"[\\/]", s)[-1]
    s = re.sub(r'[<>:"|?*\x00-\x1f]', "_", s)
    return s[:200]


def duong_dan_thu_muc(chu_de, loai):
    cap = []
    if THU_MUC_NHOM.get(loai):
        cap.append(THU_MUC_NHOM[loai])
    if loai == "HL":
        m = re.search(r"\b(?:vat li|vat ly|lop)\s*(10|11|12)\b", bo_dau(chu_de))
        if m:
            cap.append("Lop " + m.group(1))
    cap.append(lam_sach_ten(chu_de))
    return "/".join(cap)


def chuan_hoa_url(u):
    """Giống chuanHoaUrl_ trong Mã.gs để so trùng với cột URL nguồn của tab DaTai."""
    u = str(u or "").strip().split("#")[0]
    u = re.sub(r"([?&])utm_[^&]*&?", r"\1", u, flags=re.I)
    u = re.sub(r"[?&]$", "", u)
    u = re.sub(r"/$", "", u)
    return u.lower()


def chuyen_link_tai_truc_tiep(url):
    m = re.search(r"drive\.google\.com/file/d/([\w-]+)", url) or re.search(r"drive\.google\.com/open\?id=([\w-]+)", url)
    if m:
        return "https://drive.google.com/uc?export=download&id=" + m.group(1)
    m = re.search(r"docs\.google\.com/(document|spreadsheets|presentation)/d/([\w-]+)", url)
    if m:
        dinh_dang = {"document": "docx", "spreadsheets": "xlsx", "presentation": "pptx"}[m.group(1)]
        return "https://docs.google.com/%s/d/%s/export?format=%s" % (m.group(1), m.group(2), dinh_dang)
    return url


def la_link_file(url):
    return bool(RE_DUOI_FILE.search(url) or re.search(r"drive\.google\.com/uc\?", url) or "/export?format=" in url)


# ---------------- NĂM HỌC (chuyển từ thongTinNamHoc_) ----------------
def nam_hoc_hien_tai(ngay=None):
    d = ngay or dt.datetime.now(D.TZ)
    return d.year if d.month >= 8 else d.year - 1


def thong_tin_nam_hoc(chu_de, loai, lan):
    hien_tai = nam_hoc_hien_tai()
    m = re.search(r"\b(?:vat li|vat ly|lop)\s*(10|11|12)\b", bo_dau(chu_de))
    lop = m.group(1) if m else ("12" if loai in ("TN", "HSG_B") else "")
    moc_ct = {"10": 2022, "11": 2023, "12": 2024}.get(lop, 2022)
    lui = min(VONG_NAM_HOC[lan % len(VONG_NAM_HOC)], NAM_HOC_TOI_DA - 1)
    cu_nhat = max(hien_tai - NAM_HOC_TOI_DA + 1, moc_ct)
    muc_tieu = max(hien_tai - lui, cu_nhat)
    return {"muc_tieu": muc_tieu, "cu_nhat": cu_nhat,
            "ghi_chu": "Năm học mục tiêu %d-%d (lượt %d, giới hạn từ %d-%d)" % (muc_tieu, muc_tieu + 1, lan + 1, cu_nhat, cu_nhat + 1)}


def cu_hon_gioi_han(chuoi, cu_nhat):
    """Chỉ loại khi thấy rõ 'năm học 20xx-20yy' (yy = xx+1) cũ hơn giới hạn; mọi trường hợp mơ hồ thì giữ lại."""
    t = bo_dau(chuoi)
    for a, b in re.findall(r"\b(20\d\d) ?(20\d\d)\b", t):
        if int(b) == int(a) + 1:
            return int(a) < cu_nhat
    return False


# ---------------- TÌM KIẾM ----------------
def _gon(s):
    s = re.sub(r"<[^>]+>", "", str(s or "")).replace("&amp;", "&")
    return re.sub(r"\s+", " ", s).strip()


def tim_kiem(truy_van):
    """Trả về [(tiêu đề, url)] bằng xưởng tìm kiếm tim_kiem.py (thư viện ddgs, có chờ khi bị giới hạn, Brave nếu có khoá)."""
    kq, nguon, _ = TK.tim([truy_van])
    print("   nguồn tìm: %s" % nguon)
    return [(r["tieuDe"], r["url"]) for r in kq]


def lay_link_file_trong_trang(url, loai):
    """Quét một trang web, trả về [(tên hiển thị, link file)] đã qua bộ lọc phạm vi / môn khác."""
    try:
        r = requests.get(url, headers=UA, timeout=25)
    except Exception as e:
        print("   ✖ Không mở được trang %s: %s" % (url, e))
        return []
    if r.status_code >= 400 or "html" not in r.headers.get("Content-Type", "html").lower():
        return []
    ra, da_co = [], set()
    for href, noi_dung in re.findall(r"<a\s[^>]*href\s*=\s*[\"']([^\"']+)[\"'][^>]*>([\s\S]*?)</a>", r.text, re.I):
        if len(ra) >= SO_LINK_QUET_TOI_DA:
            break
        href = href.replace("&amp;", "&").strip()
        if re.match(r"(javascript:|mailto:|#)", href, re.I):
            continue
        tuyet_doi = chuyen_link_tai_truc_tiep(urljoin(url, href).split("#")[0])
        if not la_link_file(tuyet_doi) or tuyet_doi in da_co:
            continue
        da_co.add(tuyet_doi)
        ten = _gon(noi_dung)[:150]
        if la_ngoai_pham_vi(loai, ten, tuyet_doi) or la_mon_khac(ten, tuyet_doi):
            continue
        ra.append((ten, tuyet_doi))
    return ra


# ---------------- KIỂM TRA LINK (không tải trọn file) ----------------
def _loai_theo_dau_file(b):
    if b[:4] == b"%PDF":
        return "pdf"
    if b[:2] == b"PK":
        return "zip"
    if b[:4] == b"\xd0\xcf\x11\xe0":
        return "office-cu"
    if b[:4] == b"Rar!":
        return "rar"
    if b[:4] == b"7z\xbc\xaf":
        return "7z"
    if b[:2] == b"\xff\xd8":
        return "jpg"
    if b[:4] == b"\x89PNG":
        return "png"
    return ""


def kiem_tra_noi_dung(dau, kich_thuoc, ten, url):
    """Giống kiemTraFile_ trong Mã.gs. kich_thuoc = None nghĩa là chưa biết (nhưng đã lớn hơn mức tối thiểu)."""
    url_gon = str(url).split("?")[0]
    if RE_TEN_MAU.search(ten) or RE_TEN_MAU.search(url_gon):
        return False, "Tên hoặc link giống file mẫu thử (dummy/sample...)"
    if kich_thuoc is not None and kich_thuoc < KICH_THUOC_TOI_THIEU:
        return False, "File quá nhỏ (%d byte)" % kich_thuoc
    if kich_thuoc is not None and kich_thuoc > KICH_THUOC_TOI_DA:
        return False, "File quá lớn cho Apps Script (%d MB)" % (kich_thuoc // 1048576)
    loai = _loai_theo_dau_file(bytes(dau[:8]))
    if not loai:
        return False, "Nội dung không phải PDF/Word/Excel/PowerPoint/ZIP/RAR/ảnh hợp lệ"
    m = re.search(r"\.(\w+)$", ten)
    duoi = m.group(1).lower() if m else ""
    if duoi == "pdf" and loai != "pdf":
        return False, "Đuôi .pdf nhưng nội dung không phải PDF"
    if duoi in ("docx", "xlsx", "pptx") and loai != "zip":
        return False, "Đuôi .%s nhưng nội dung không đúng định dạng" % duoi
    return True, loai


def kiem_tra_link(url, loai_chu_de):
    """Mở link dạng stream, chỉ đọc vài KB đầu. Trả về (ok, tên, kích thước | None, lý do)."""
    try:
        r = requests.get(url, headers=UA, stream=True, timeout=(10, 25), allow_redirects=True)
    except Exception as e:
        return False, "", None, "Không mở được link: %s" % str(e)[:100]
    with r:
        if r.status_code >= 400:
            return False, "", None, "HTTP %d" % r.status_code
        if "text/html" in r.headers.get("Content-Type", "").lower():
            return False, "", None, "Link trả về trang web (HTML), không phải file trực tiếp"
        ten = ""
        cd = r.headers.get("Content-Disposition", "")
        m = re.search(r"filename\*=(?:UTF-8'')?([^;]+)|filename=\"?([^\";]+)\"?", cd, re.I)
        if m:
            ten = lam_sach_ten(m.group(1) or m.group(2))
        if not ten:
            ten = lam_sach_ten(url.split("?")[0].split("#")[0].split("/")[-1])
        dau = bytearray()
        try:
            for khoi in r.iter_content(8192):
                dau += khoi
                if len(dau) > KICH_THUOC_TOI_THIEU:
                    break
        except Exception as e:
            return False, ten, None, "Lỗi khi đọc file: %s" % str(e)[:100]
        cl = r.headers.get("Content-Length", "")
        if cl.isdigit() and not r.headers.get("Content-Encoding"):
            kich_thuoc = int(cl)
        else:
            kich_thuoc = len(dau) if len(dau) <= KICH_THUOC_TOI_THIEU else None
    ok, ket = kiem_tra_noi_dung(dau, kich_thuoc, ten or "downloaded_file", url)
    if not ok:
        return False, ten, kich_thuoc, ket
    if ten and not re.search(r"\.\w{2,4}$", ten):   # tên không có đuôi (ví dụ link export) -> bổ sung đuôi
        if ket == "pdf":
            ten += ".pdf"
        else:
            mf = re.search(r"format=(docx|xlsx|pptx)", url)
            if mf:
                ten += "." + mf.group(1)
    if not ten:
        ten = "downloaded_file"
    if la_ngoai_pham_vi(loai_chu_de, ten):
        return False, ten, kich_thuoc, "Tên file cho thấy ngoài phạm vi %s: %s" % (PHAM_VI[loai_chu_de]["ten"], ten)
    if la_mon_khac(ten):
        return False, ten, kich_thuoc, "Tên file cho thấy là môn khác: " + ten
    return True, ten, kich_thuoc, ket


# ---------------- SHEET ----------------
def lay_tab_san_sang(bang):
    try:
        return bang.worksheet(TAB_SAN_SANG)
    except Exception:
        tab = bang.add_worksheet(TAB_SAN_SANG, rows=1000, cols=len(COT_SS))
        tab.update(range_name="A1", values=[COT_SS])
        tab.format("A1:J1", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.99, "green": 0.91, "blue": 0.78}})
        tab.freeze(rows=1)
        return tab


def chon_chu_de(duoc_lieu):
    """Xoay vòng giống chayNgam: chủ đề đang bật, lâu chưa THỬ nhất (cột F), chưa có thì cột C."""
    chon, cu_nhat = None, float("inf")
    for i, r in enumerate(duoc_lieu[1:], start=2):
        r = (list(r) + [""] * 7)[:7]
        ten = str(r[0]).strip()
        bat = r[1] is True or str(r[1]).strip().upper() == "TRUE"
        if not ten or not bat:
            continue
        moc = r[5] if isinstance(r[5], (int, float)) and not isinstance(r[5], bool) else r[2]
        lan_cuoi = float(moc) if isinstance(moc, (int, float)) and not isinstance(moc, bool) else 0.0
        if lan_cuoi < cu_nhat:
            cu_nhat, chon = lan_cuoi, {"dong": i, "chu_de": ten, "loai": doc_loai(ten, r[6]), "so_da_tai": r[4]}
    return chon


def main():
    gc, _drive, email_sa = D.ket_noi()
    print("Tài khoản dịch vụ:", email_sa)
    bang = gc.open_by_key(ID_BANG_TAI)
    print('Bảng tính: "%s" (%s)' % (bang.title, ID_BANG_TAI))
    tab_cd, tab_dt, tab_nk = bang.worksheet(TAB_CHU_DE), bang.worksheet(TAB_DA_TAI), bang.worksheet(TAB_NHAT_KY)
    tab_ss = lay_tab_san_sang(bang)

    # UNFORMATTED_VALUE: ngày giờ trả về dạng số nên so sánh được, không phụ thuộc định dạng vùng
    lieu_cd = tab_cd.get_all_values(value_render_option="UNFORMATTED_VALUE")
    chon = chon_chu_de(lieu_cd)
    if not chon:
        print("Không có chủ đề nào đang bật trong sheet ChuDe.")
        return
    chu_de, loai, dong = chon["chu_de"], chon["loai"], chon["dong"]
    print("Chủ đề: %s [%s]" % (chu_de, loai))

    lan = sum(1 for r in tab_nk.get_all_values()[1:] if len(r) > 1 and r[1].strip() == chu_de)
    nh = thong_tin_nam_hoc(chu_de, loai, lan)
    print("📅", nh["ghi_chu"])

    da_biet = {chuan_hoa_url(r[3]) for r in tab_dt.get_all_values()[1:] if len(r) > 3 and r[3]}
    da_biet |= {chuan_hoa_url(r[1]) for r in tab_ss.get_all_values()[1:] if len(r) > 1 and r[1]}

    nam_ky_thi = nh["muc_tieu"] + 1 if loai == "TN" else nh["muc_tieu"]
    q1 = "%s %s file PDF" % (chu_de, ("kì thi %d" % nam_ky_thi) if loai == "TN" else ("năm học %d-%d" % (nh["muc_tieu"], nh["muc_tieu"] + 1)))
    ds_truy_van = list(dict.fromkeys([q1] + TK.cac_truy_van(chu_de)))[:SO_TRUY_VAN_TOI_DA]

    thong_ke = {"tim": 0, "ket_qua": 0, "loai_tru": 0, "trung": 0, "kiem_tra_loi": 0, "trang": 0, "xep": 0}
    xep_hang = []

    def nhan(ten, url, kich_thuoc=None):
        xep_hang.append([bay_gio_iso(), url, ten, chu_de, loai, duong_dan_thu_muc(chu_de, loai), kich_thuoc if kich_thuoc is not None else "", "Chờ", 0, ""])
        da_biet.add(chuan_hoa_url(url))
        thong_ke["xep"] += 1

    def xu_ly_ung_vien(ten_goi, url):
        """Lọc nhanh trước (không tốn mạng), kiểm tra link sau. Trả về True nếu đã xếp hàng."""
        if chuan_hoa_url(url) in da_biet:
            thong_ke["trung"] += 1
            return False
        if la_ngoai_pham_vi(loai, ten_goi, url) or la_mon_khac(ten_goi, url) or cu_hon_gioi_han(ten_goi + " " + url, nh["cu_nhat"]):
            thong_ke["loai_tru"] += 1
            return False
        ok, ten, kich_thuoc, ly_do = kiem_tra_link(url, loai)
        if not ok:
            thong_ke["kiem_tra_loi"] += 1
            print("   🚫 %s → %s" % (url[:90], ly_do))
            da_biet.add(chuan_hoa_url(url))   # không kiểm tra lại link hỏng trong cùng lượt
            return False
        nhan(ten, url, kich_thuoc)
        print("   ✅ %s (%s)" % (ten, url[:80]))
        return True

    loi_tim = ""
    try:
        trang_cho = []
        for idx, q in enumerate(ds_truy_van):
            if not con_thoi_gian(120) or thong_ke["xep"] >= SO_FILE_TOI_DA:
                break
            if idx > 0 and (thong_ke["xep"] > 0 or trang_cho):
                break   # chỉ thử truy vấn tiếp khi truy vấn trước chưa cho gì phù hợp
            thong_ke["tim"] += 1
            kq = tim_kiem(q)
            thong_ke["ket_qua"] += len(kq)
            print("🔎 %s → %d kết quả" % (q, len(kq)))
            for tieu_de, url in kq:
                link = chuyen_link_tai_truc_tiep(url)
                if la_ngoai_pham_vi(loai, tieu_de, link):
                    thong_ke["loai_tru"] += 1
                    continue
                if la_link_file(link):
                    if thong_ke["xep"] < SO_FILE_TOI_DA and con_thoi_gian(60):
                        xu_ly_ung_vien(tieu_de, link)
                else:
                    trang_cho.append((tieu_de, link))
        for tieu_de, url in trang_cho[:SO_TRANG_QUET_TOI_DA]:
            if thong_ke["xep"] >= SO_FILE_TOI_DA or not con_thoi_gian(60):
                break
            thong_ke["trang"] += 1
            links = lay_link_file_trong_trang(url, loai)
            print("🧭 Quét %s: %d link file" % (url[:80], len(links)))
            tu_trang = 0
            for ten, link in links:
                if tu_trang >= SO_FILE_MOI_TRANG or thong_ke["xep"] >= SO_FILE_TOI_DA or not con_thoi_gian(60):
                    break
                if xu_ly_ung_vien(ten, link):
                    tu_trang += 1
    except Exception as e:
        loi_tim = str(e)[:200]
        print("❌ Lỗi giữa chừng:", loi_tim)

    if xep_hang:
        tab_ss.append_rows(xep_hang, value_input_option="USER_ENTERED", table_range="A1")

    if thong_ke["xep"] > 0:
        trang_thai = "CÓ FILE MỚI"
    elif thong_ke["ket_qua"] == 0:
        trang_thai = "LỖI TÌM KIẾM"
    else:
        trang_thai = "KHÔNG CÓ MỚI"
    thanh_cong = trang_thai in ("CÓ FILE MỚI", "KHÔNG CÓ MỚI")
    tom_tat = ("[%s] Python: tìm %d lần, %d kết quả, quét %d trang | xếp hàng %d, trùng %d, loại phạm vi %d, link hỏng %d%s"
               % (trang_thai, thong_ke["tim"], thong_ke["ket_qua"], thong_ke["trang"], thong_ke["xep"], thong_ke["trung"],
                  thong_ke["loai_tru"], thong_ke["kiem_tra_loi"], (" | lỗi: " + loi_tim) if loi_tim else ""))
    print("📊", tom_tat)

    luc_so = bay_gio_so()
    if thanh_cong:
        tab_cd.update(range_name="C%d" % dong, values=[[luc_so]], value_input_option="RAW")
        tab_cd.format("C%d" % dong, DINH_DANG_NGAY)
    tab_cd.update(range_name="D%d" % dong, values=[[tom_tat[:500]]], value_input_option="RAW")
    tab_cd.update(range_name="F%d" % dong, values=[[luc_so]], value_input_option="RAW")
    tab_cd.format("F%d" % dong, DINH_DANG_NGAY)
    # Cột E (số file đã tải) do Apps Script cộng thêm khi tải thật xong
    kq_ghi = tab_nk.append_row([luc_so, chu_de, thong_ke["xep"], tom_tat[:1000], trang_thai], value_input_option="RAW", table_range="A1")
    try:
        m = re.search(r"!A(\d+)", kq_ghi["updates"]["updatedRange"])
        if m:
            tab_nk.format("A%s" % m.group(1), DINH_DANG_NGAY)
    except Exception as e:
        print("[Cảnh báo] Không định dạng được ô thời gian của NhatKyChay:", e)

if __name__ == "__main__":
    main()
