"""
doc_de.py – XƯỞNG ĐỌC ĐỀ (Python, chạy trên GitHub Actions) – thay cho xuLyDeMotLuot() trong XuLyDe.gs của Kho chung.

Làm ĐÚNG như bản Apps Script, chỉ khác là không còn giới hạn 6 phút/lượt và không tốn 90 phút trigger/ngày:
  1. Đọc tab DaTai của "Download Agent - Quản lý", thêm file mới vào tab XuLyDe (trạng thái "Chờ").
  2. Lấy lần lượt từng file chờ: PDF, ảnh gửi thẳng cho Gemini; Google Docs xuất PDF; Word đổi PDF bằng LibreOffice.
  3. Gemini (cùng lời nhắc, cùng schema, cùng model trong tab CauHinh) tách TỪNG câu, gắn Mã YCCĐ.
  4. Ghi câu vào NganHangCauHoi ("Chưa duyệt"), đánh dấu file trong XuLyDe; lỗi 3 lần thì bỏ qua.
  5. Ghi nhịp chạy vào tab Agent (dòng "Xưởng đọc đề (Python)") để Meta / canh gác theo dõi.
Hết hạn mức Gemini → dừng lượt, lượt sau làm tiếp. Lỗi chung → lượt chạy GitHub báo đỏ và GitHub tự email.

[29/10/2026] BỎ GIỚI HẠN CỦA BẢN APPS SCRIPT (quy trình, lời nhắc, schema, cách ghi giữ nguyên):
  • File PDF/Word lớn hơn KICH_THUOC_TOI_DA (giới hạn gửi kèm của Gemini): nén lại bằng PyMuPDF; vẫn lớn thì CHIA THEO TRANG
    thành nhiều phần, mỗi phần kèm 1 trang kế tiếp (đọc nốt câu vắt trang) và 2 trang cuối tài liệu (thường là đáp án / HDC).
  • Tài liệu dài (Gemini hết chỗ trả lời): thay cho "chỉ lấy 40 câu đầu", đọc TIẾP THEO LÔ SO_CAU_MOI_LO câu cho đến hết
    (tối đa SO_LO_TOI_DA lô mỗi phần). Mã câu đánh số liên tục; câu đã có mã trong ngân hàng thì không ghi lại.
  • Mỗi lượt gọi Gemini được ghi vào tab Quota_SuDung (dòng "xưởng …") qua quota_xuong.py.

[20/11/2026] ĐỌC FILE NÉN .zip / .rar (có công tắc CHO_PHEP_DOC_NEN – tắt thì chạy y như bản cũ):
  • Giải nén NGAY TRONG BỘ NHỚ (không ghi đĩa), lấy PDF / Word / ảnh bên trong (tệp nén lồng nhau 1 cấp), bỏ __MACOSX, file ẩn, file tạm ~$.
    Mỗi file con thành một "phần" gửi Gemini như PDF lớn; mã câu đánh số liên tục cho cả tệp nén, cột "Tên file" ghi "tệp nén › file con (câu N)".
  • Một file con lỗi (không phải hết hạn mức) thì bỏ qua file đó, các file con khác vẫn đọc; trạng thái ghi "Đã xử lý (một phần)" kèm tên file lỗi.
  • Chặn zip bomb: tối đa GIOI_HAN_SO_FILE_NEN file và GIOI_HAN_GIAI_NEN dung lượng sau giải nén. Tệp nén có mật khẩu → báo lỗi.
  • .rar cần thư viện rarfile (pip) và công cụ unar hoặc unrar (apt) trong workflow; .zip dùng thư viện có sẵn của Python.

[20/11/2026] QUÉT MỤC "ĐƯỢC CHIA SẺ VỚI TÔI" (có công tắc CHO_PHEP_QUET_CHIA_SE – tắt thì chạy y như bản cũ):
  • Ngoài THU_MUC_NGUON, quét thêm mọi file / thư mục (kể cả thư mục con) đang hiện ở "Được chia sẻ với tôi" của tài khoản đang đăng nhập
    (Drive API: sharedWithMe = true). File đã có trong XuLyDe (so theo File ID) thì bỏ qua; mỗi lượt chỉ thêm tối đa GIOI_HAN_CHIA_SE_MOI_LUOT file mới.
  • LƯU Ý: GOOGLE_CREDENTIALS là TÀI KHOẢN DỊCH VỤ nên "Được chia sẻ với tôi" ở đây là của tài khoản dịch vụ, KHÔNG phải trang Drive cá nhân của thầy.
    Muốn file / thư mục nào vào hàng chờ: chia sẻ (quyền Xem) cho email tài khoản dịch vụ (dòng "Tài khoản dịch vụ:" đầu log).

Biến môi trường (GitHub Secrets): GOOGLE_CREDENTIALS (toàn bộ nội dung credentials.json), GEMINI_API_KEY,
GEMINI_API_KEY_TRA_PHI (không bắt buộc): dùng khi khoá miễn phí HẾT LƯỢT trong ngày, tối đa TOI_DA_LUOT_TRA_PHI lượt gọi/lượt chạy.
CHO_PHEP_DOC_NEN (không bắt buộc, mặc định true; tab CauHinh cùng tên sẽ ghi đè): bật/tắt đọc file .zip / .rar.
CHO_PHEP_QUET_CHIA_SE (không bắt buộc, mặc định true): bật/tắt quét "Được chia sẻ với tôi"; GIOI_HAN_CHIA_SE_MOI_LUOT (mặc định 200).
"""
import base64, datetime as dt, io, json, os, re, shutil, subprocess, sys, tempfile, threading, time, unicodedata

import gspread
import requests
import latex_chuan as L   # [Mục 24] chuẩn hoá LaTeX giống ChuanLatex.gs
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

try:
    import quota_xuong as Q          # ghi lượt dùng Gemini vào tab Quota_SuDung
except Exception:
    Q = None

# ---------------- CẤU HÌNH (giống XuLyDe.gs) ----------------
ID_KHO_CHUNG = "1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc"
ID_BANG_DOWNLOAD = "1gL1q0LnOR4Ylr7ae-n-a20GBbo5nPkidrdEOnCZttio"   # "Download Agent - Quản lý"
TAB_DA_TAI, TAB_XU_LY, TAB_NGAN_HANG, TAB_YCCD, TAB_CAU_HINH, TAB_AGENT = "DaTai", "XuLyDe", "NganHangCauHoi", "YCCD", "CauHinh", "Agent"
TEN_AGENT = "Xưởng đọc đề (Python)"
MODEL_MAC_DINH, MODEL_DU_PHONG_MAC_DINH = "gemini-3.8-flash", ["gemini-3.5-flash-lite"]
THOI_GIAN_TOI_DA_PHUT = float(os.environ.get("THOI_GIAN_TOI_DA_PHUT", "100"))
KICH_THUOC_TOI_DA = 12 * 1024 * 1024
SO_LAN_THU = 3
SO_CAU_KHI_QUA_DAI = 40            # (bản cũ) chỉ còn dùng làm cỡ lô đầu tiên khi đọc tài liệu dài
SO_CAU_MOI_LO = int(os.environ.get("SO_CAU_MOI_LO", "40"))
SO_LO_TOI_DA = int(os.environ.get("SO_LO_TOI_DA", "10"))          # mỗi phần tối đa 10 lô (≈400 câu)
GIOI_HAN_TAI_VE = 300 * 1024 * 1024                                # file quá lớn mới bỏ qua hẳn
CHO_PHEP_DOC_NEN = os.environ.get("CHO_PHEP_DOC_NEN", "true").strip().lower() not in ("false", "0", "no", "off", "tat", "tắt")   # [20/11/2026] công tắc đọc .zip/.rar
TZ = dt.timezone(dt.timedelta(hours=7))

COT_XL = ["File ID", "Tên file", "Link", "Chủ đề tải", "Trạng thái", "Số câu", "Số lần thử",
          "Lỗi gần nhất", "Thời gian xử lý", "Loại đề", "Lớp", "Đơn vị ra đề", "Năm học"]
COT_NH = ["Mã câu", "Mã YCCĐ", "Mã bài", "Lớp", "Mức độ", "Dạng", "Nội dung", "Phương án", "Đáp án",
          "Lời giải / HDC", "Điểm", "Loại đề", "Đơn vị ra đề", "Năm học", "Kì thi", "Tên file", "Link file", "File ID",
          "Chủ đề tải", "Kiểm tra", "Trạng thái duyệt", "Thời gian"]
TEN_MUC = {"NB": "Nhận biết", "TH": "Thông hiểu", "VD": "Vận dụng", "VDC": "Vận dụng cao"}
TEN_DANG = {"TN": "Nhiều lựa chọn", "DS": "Đúng/sai", "TLN": "Trả lời ngắn", "TL": "Tự luận"}

CT_CU_MO_TA = (
    "sóng ánh sáng (giao thoa ánh sáng, tán sắc, quang phổ, tia hồng ngoại, tử ngoại, tia X); lượng tử ánh sáng (hiện tượng quang điện, "
    "công thoát, mẫu nguyên tử Bo, laze); mạch dao động LC, dao động và sóng điện từ trong mạch, sóng vô tuyến; dòng điện xoay chiều "
    "(mạch RLC, độ lệch pha u – i, công suất, hệ số công suất, cộng hưởng điện, máy biến áp, truyền tải điện năng); quang hình học "
    "(khúc xạ, phản xạ toàn phần, lăng kính, thấu kính, mắt, kính lúp, kính hiển vi, kính thiên văn); dòng điện trong kim loại, chất điện phân, "
    "chất khí, chân không, bán dẫn; thuyết tương đối hẹp; momen quán tính, chuyển động quay của vật rắn, momen động lượng (sách nâng cao); "
    "căng bề mặt, mao dẫn; từ vi mô đến vĩ mô.")
RE_CT_CU = re.compile(r"\b(" + "|".join([
    "giao thoa anh sang", "tan sac", "quang pho", "tia hong ngoai", "tia tu ngoai", "hien tuong quang dien", "quang dien ngoai",
    "quang dien trong", "gioi han quang dien", "cong thoat", "mau nguyen tu bo", "tien de bo", "mach dao dong", "mach lc",
    "dao dong dien tu", "song vo tuyen", "mach rlc", "doan mach xoay chieu", "he so cong suat", "cong huong dien", "may bien ap",
    "truyen tai dien", "khuc xa", "phan xa toan phan", "lang kinh", "thau kinh", "tieu cu", "kinh lup", "kinh hien vi",
    "kinh thien van", "mat can", "mat vien", "chat dien phan", "dien phan", "ban dan", "tia catot", "thuyet tuong doi",
    "momen quan tinh", "moment quan tinh", "momen dong luong", "cang be mat", "mao dan"]) + r")\b")

BAT_DAU = time.time()
TOI_DA_LUOT_TRA_PHI = int(os.environ.get("TOI_DA_LUOT_TRA_PHI", "40"))   # chặn chi phí mỗi lượt chạy
CHO_PHEP_DOC_DE = True                                              # công tắc bật/tắt (tab CauHinh)
TRANG_THAI_KHOA = {"tra_phi": False, "da_dung_tra_phi": 0, "het": set(), "hong": set(), "ngay": False}   # het = hết lượt ngày; hong = Google từ chối khoá

# [21/11/2026] AN TOÀN KHI NHIỀU LUỒNG GỌI GEMINI CÙNG LÚC (duyet_cau.py chạy song song các tầng).
#   • _KHOA: mọi chỗ đọc/ghi TRANG_THAI_KHOA đi qua khoá này (nhất là bộ đếm lượt khoá trả phí – trần chi phí không bị vượt).
#   • _CONG_GEMINI: tối đa GEMINI_SONG_SONG lượt gọi cùng lúc (mặc định 3). Đặt 1 = hệ như cũ (lần lượt từng lượt).
#     Luồng nào gặp 429 theo phút thì chờ khi đang giữ cổng, nên cả xưởng cùng lùi lại thay vì dồn thêm lượt vào khoá đang bị chặn.
#   Đọc đề (doc_de.py chạy một luồng) không bị ảnh hưởng.
def _so_nguyen_env(ten, mac_dinh):
    try:
        return int(float(os.environ.get(ten, "").strip() or mac_dinh))
    except ValueError:
        return mac_dinh


GEMINI_SONG_SONG = max(1, _so_nguyen_env("GEMINI_SONG_SONG", 3))
_KHOA = threading.RLock()
_CONG_GEMINI = threading.BoundedSemaphore(GEMINI_SONG_SONG)


def ds_khoa_mien_phi():
    """GEMINI_API_KEY, GEMINI_API_KEY_1 … GEMINI_API_KEY_5 (bỏ ô trống, bỏ khoá trùng theo giá trị)."""
    ds = []
    for ten in ["GEMINI_API_KEY"] + ["GEMINI_API_KEY_%d" % i for i in range(1, 6)]:
        k = os.environ.get(ten, "").strip()
        if k and k not in [x[1] for x in ds]:
            ds.append((ten, k))
    return ds


class HetHanMuc(Exception):
    """Hết hạn mức Gemini. [15/11] theo_ngay=True: hết lượt theo NGÀY (RPD) hoặc đã chạm trần chi phí khoá trả phí,
    nên thử lại sau vài phút là vô ích (nơi gọi nên hoãn đến mốc Gemini đặt lại hạn mức). Mặc định False = như cũ."""
    theo_ngay = False


def _het_han_muc(thong_bao, theo_ngay=False):
    e = HetHanMuc(thong_bao)
    e.theo_ngay = bool(theo_ngay)
    return e


class KhoaHong(RuntimeError):
    """Google từ chối chính khoá API (400 API_KEY_INVALID / 401 / 403 về khoá). Không phải hết hạn mức:
    thử model khác bằng cùng khoá chỉ phí thời gian, nên bỏ khoá này và chuyển sang khoá kế tiếp."""


def la_loi_khoa(ma, noi_dung):
    """True khi 400/401/403 mà nội dung nói về chính khoá API (không hợp lệ, hết hạn, bị thu hồi vì lộ...)."""
    if ma not in (400, 401, 403):
        return False
    return bool(re.search(r"API_KEY_INVALID|API key not valid|API key expired|API key was reported as leaked|pass a valid API key",
                          str(noi_dung or ""), re.I))


def bay_gio():
    return dt.datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S")


def con_thoi_gian(giay_du_tru=0):
    return time.time() - BAT_DAU < THOI_GIAN_TOI_DA_PHUT * 60 - giay_du_tru


# ---------------- KẾT NỐI GOOGLE ----------------
def ket_noi():
    tt = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    cred = service_account.Credentials.from_service_account_info(
        tt, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"])
    return gspread.authorize(cred), build("drive", "v3", credentials=cred, cache_discovery=False), tt.get("client_email", "")


def tai_ve(drive, file_id, xuat_pdf=False):
    req = drive.files().export_media(fileId=file_id, mimeType="application/pdf") if xuat_pdf else drive.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    tai = MediaIoBaseDownload(buf, req, chunksize=8 * 1024 * 1024)
    xong = False
    while not xong:
        _, xong = tai.next_chunk(num_retries=3)
    return buf.getvalue()


def word_sang_pdf(du_lieu, ten):
    if not shutil.which("soffice"):
        print("Cài LibreOffice để đổi Word sang PDF (lần đầu trong lượt)…")
        subprocess.run(["sudo", "apt-get", "install", "-y", "-qq", "libreoffice-writer-nogui"], check=True, capture_output=True)
    thu = tempfile.mkdtemp()
    duoi = ".doc" if ten.lower().endswith(".doc") else ".docx"
    vao = os.path.join(thu, "vao" + duoi)
    with open(vao, "wb") as f:
        f.write(du_lieu)
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", thu, vao], check=True, capture_output=True, timeout=300)
    with open(os.path.join(thu, "vao.pdf"), "rb") as f:
        return f.read()


def chuan_bi_tep(drive, file_id):
    f = drive.files().get(fileId=file_id, fields="name,mimeType,size").execute()
    mime, ten, co = f.get("mimeType", ""), f.get("name", ""), int(f.get("size") or 0)
    if co > KICH_THUOC_TOI_DA:
        return {"bo_qua": "File lớn hơn %d MB" % (KICH_THUOC_TOI_DA // 1048576)}
    if mime == "application/pdf":
        return {"data": tai_ve(drive, file_id), "mime": "application/pdf", "ten": ten}
    if re.match(r"^image/(png|jpeg|webp)$", mime):
        return {"data": tai_ve(drive, file_id), "mime": mime, "ten": ten}
    if mime == "application/vnd.google-apps.document":
        return {"data": tai_ve(drive, file_id, xuat_pdf=True), "mime": "application/pdf", "ten": ten}
    if mime in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword") or re.search(r"\.docx?$", ten, re.I):
        return {"data": word_sang_pdf(tai_ve(drive, file_id), ten), "mime": "application/pdf", "ten": ten}
    return {"bo_qua": "Định dạng chưa hỗ trợ (%s)" % mime}


# ---------------- [20/11/2026] FILE NÉN .zip / .rar ----------------
MIME_NEN = {"application/zip", "application/x-zip-compressed", "application/vnd.rar",
            "application/x-rar-compressed", "application/x-rar"}
GIOI_HAN_SO_FILE_NEN = int(os.environ.get("GIOI_HAN_SO_FILE_NEN", "200"))              # chống tệp nén chứa quá nhiều file
GIOI_HAN_GIAI_NEN = int(os.environ.get("GIOI_HAN_GIAI_NEN_MB", "500")) * 1024 * 1024   # chống zip bomb (tổng dung lượng sau giải nén)
DUOI_DOC_DUOC = (".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".webp")
MIME_ANH = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def la_tep_nen(mime, ten):
    return mime in MIME_NEN or bool(re.search(r"\.(zip|rar)$", ten or "", re.I))


def _ten_trong_zip(info):
    """Tên file tiếng Việt trong zip cũ hay bị lỗi mã hoá (cp437) → sửa lại thành UTF-8."""
    ten = info.filename
    if not (info.flag_bits & 0x800):
        try:
            ten = ten.encode("cp437").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return ten


def _bo_qua_muc_nen(ten, la_thu_muc):
    base = os.path.basename(ten.rstrip("/"))
    return (la_thu_muc or "__MACOSX" in ten or base.startswith((".", "~$"))
            or not ten.lower().endswith(DUOI_DOC_DUOC + (".zip", ".rar")))


def giai_nen(du_lieu):
    """Trả [(tên trong tệp nén, bytes)] chỉ gồm PDF/Word/ảnh và tệp nén lồng nhau. Nhận dạng bằng 4 byte đầu, không tin đuôi file."""
    ra, tong = [], 0

    def nhan(co):
        nonlocal tong
        tong += co
        if tong > GIOI_HAN_GIAI_NEN or len(ra) >= GIOI_HAN_SO_FILE_NEN:
            raise RuntimeError("Tệp nén quá lớn hoặc quá nhiều file (giới hạn %d file, %d MB sau giải nén)"
                               % (GIOI_HAN_SO_FILE_NEN, GIOI_HAN_GIAI_NEN // 1048576))

    if du_lieu[:4] == b"PK\x03\x04":
        import zipfile
        with zipfile.ZipFile(io.BytesIO(du_lieu)) as z:
            for info in z.infolist():
                ten = _ten_trong_zip(info)
                if _bo_qua_muc_nen(ten, info.is_dir()):
                    continue
                nhan(info.file_size)
                ra.append((ten, z.read(info)))
    elif du_lieu[:4] == b"Rar!":
        try:
            import rarfile
        except ImportError:
            raise RuntimeError("Chưa cài thư viện rarfile: thêm 'pip install rarfile' và 'sudo apt-get install -y unar' vào workflow")
        with rarfile.RarFile(io.BytesIO(du_lieu)) as r:
            for info in r.infolist():
                ten = info.filename
                if _bo_qua_muc_nen(ten, info.is_dir()):
                    continue
                nhan(info.file_size)
                ra.append((ten, r.read(info)))
    else:
        raise RuntimeError("Không nhận ra định dạng tệp nén (chỉ hỗ trợ zip, rar)")
    return ra


def _phan_tu_bytes(du_lieu, ten):
    """Một file đã có bytes → danh sách phần gửi Gemini ([] nếu bỏ qua)."""
    duoi = os.path.splitext(ten.lower())[1]
    if duoi in MIME_ANH:
        return [{"data": du_lieu, "mime": MIME_ANH[duoi], "ten": ten}] if len(du_lieu) <= KICH_THUOC_TOI_DA else []
    if duoi == ".pdf":
        pdf = du_lieu
    elif duoi in (".doc", ".docx"):
        pdf = word_sang_pdf(du_lieu, ten)
    else:
        return []
    if len(pdf) <= KICH_THUOC_TOI_DA:
        return [{"data": pdf, "mime": "application/pdf", "ten": ten}]
    return tach_pdf(pdf, ten)


def tep_tu_nen(du_lieu, ten_nen, do_sau=0):
    """Tệp nén → danh sách phần (mỗi phần có 'ten' = tên file con). File con hỏng thì bỏ qua, không làm sập cả tệp."""
    phan = []
    for ten, b in giai_nen(du_lieu):
        if ten.lower().endswith((".zip", ".rar")):
            if do_sau < 1:                                   # cho phép lồng 1 cấp
                phan += tep_tu_nen(b, ten, do_sau + 1)
            continue
        try:
            phan += _phan_tu_bytes(b, ten)
        except Exception as e:                               # file con hỏng / không đổi được sang PDF: cảnh báo rồi bỏ qua
            print("  ⚠️ Bỏ qua %s trong %s: %s" % (ten, ten_nen, str(e)[:120]), flush=True)
    return phan


def chuan_bi_tep_day_du(drive, file_id):
    """Như chuan_bi_tep nhưng không bỏ qua file lớn: trả {"phan": [tệp, …]} (PDF lớn được nén / chia theo trang)."""
    f = drive.files().get(fileId=file_id, fields="name,mimeType,size").execute()
    mime, ten, co = f.get("mimeType", ""), f.get("name", ""), int(f.get("size") or 0)
    if co > GIOI_HAN_TAI_VE:
        return {"bo_qua": "File lớn hơn %d MB" % (GIOI_HAN_TAI_VE // 1048576)}
    if mime == "application/pdf":
        tep = {"data": tai_ve(drive, file_id), "mime": "application/pdf", "ten": ten}
    elif re.match(r"^image/(png|jpeg|webp)$", mime):
        if co > KICH_THUOC_TOI_DA:
            return {"bo_qua": "Ảnh lớn hơn %d MB" % (KICH_THUOC_TOI_DA // 1048576)}
        return {"phan": [{"data": tai_ve(drive, file_id), "mime": mime, "ten": ten}]}
    elif mime == "application/vnd.google-apps.document":
        tep = {"data": tai_ve(drive, file_id, xuat_pdf=True), "mime": "application/pdf", "ten": ten}
    elif mime in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword") or re.search(r"\.docx?$", ten, re.I):
        tep = {"data": word_sang_pdf(tai_ve(drive, file_id), ten), "mime": "application/pdf", "ten": ten}
    elif CHO_PHEP_DOC_NEN and la_tep_nen(mime, ten):          # [20/11/2026]
        phan = tep_tu_nen(tai_ve(drive, file_id), ten)
        if not phan:
            return {"bo_qua": "Tệp nén không có PDF/Word/ảnh đọc được"}
        print("  🗜️ Tệp nén %s: %d phần để đọc." % (ten, len(phan)), flush=True)
        return {"phan": phan, "tu_nen": True}
    else:
        return {"bo_qua": "Định dạng chưa hỗ trợ (%s)" % mime}
    if len(tep["data"]) <= KICH_THUOC_TOI_DA:
        return {"phan": [tep]}
    return {"phan": tach_pdf(tep["data"], ten)}


def _trang_raster(doc, i, dpi=110):
    """Một trang thành PDF ảnh JPEG (cho trang scan quá nặng)."""
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    from PIL import Image
    pix = doc[i].get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=70)
    out = fitz.open()
    trang = out.new_page(width=doc[i].rect.width, height=doc[i].rect.height)
    trang.insert_image(trang.rect, stream=buf.getvalue())
    return out.tobytes(garbage=4, deflate=True)


def tach_pdf(du_lieu, ten):
    """Nén PDF; vẫn quá KICH_THUOC_TOI_DA thì chia theo trang. Mỗi phần: các trang chính + 1 trang kế tiếp + 2 trang cuối tài liệu."""
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    doc = fitz.open(stream=du_lieu, filetype="pdf")
    n = len(doc)
    try:
        nen = doc.tobytes(garbage=4, deflate=True, deflate_images=True, deflate_fonts=True)
    except TypeError:
        nen = doc.tobytes(garbage=4, deflate=True)
    if len(nen) <= KICH_THUOC_TOI_DA:
        print("  🗜️ Nén PDF %.1f MB → %.1f MB, gửi nguyên tài liệu." % (len(du_lieu) / 1048576, len(nen) / 1048576), flush=True)
        return [{"data": nen, "mime": "application/pdf", "ten": ten}]
    tran = KICH_THUOC_TOI_DA * 0.9
    # mỗi trang một khối PDF riêng; trang scan quá nặng thì đổi thành ảnh JPEG
    khoi = []
    for i in range(n):
        t = fitz.open(); t.insert_pdf(doc, from_page=i, to_page=i)
        b = t.tobytes(garbage=4, deflate=True); t.close()
        if len(b) > tran / 4:
            b = _trang_raster(doc, i)
        khoi.append(b)
    cuoi = list(range(max(0, n - 2), n))
    co_cuoi = sum(len(khoi[i]) for i in cuoi)
    phan, i = [], 0
    while i < n:
        ngan_sach = tran - co_cuoi - (len(khoi[i + 1]) if i + 1 < n else 0)
        j, tong = i, 0
        while j < n and (j == i or tong + len(khoi[j]) <= ngan_sach):
            tong += len(khoi[j]); j += 1
        ghep = fitz.open()
        for k in range(i, j):
            ghep.insert_pdf(fitz.open(stream=khoi[k], filetype="pdf"))
        so_chinh, phu = j - i, []
        if j < n:
            ghep.insert_pdf(fitz.open(stream=khoi[j], filetype="pdf")); phu.append("1 trang kế tiếp (trang %d)" % (j + 1))
        them_cuoi = [c for c in cuoi if c > j]
        for c in them_cuoi:
            ghep.insert_pdf(fitz.open(stream=khoi[c], filetype="pdf"))
        if them_cuoi:
            phu.append("%d trang cuối tài liệu (trang %s, thường là đáp án / hướng dẫn chấm)" % (len(them_cuoi), ", ".join(str(c + 1) for c in them_cuoi)))
        phan.append({"data": ghep.tobytes(garbage=4, deflate=True), "mime": "application/pdf", "ten": ten,
                     "ghi_chu_phan": "Tài liệu gốc dài %d trang, được chia nhiều phần. Tệp đính kèm là PHẦN %%d/%%d: %d trang đầu của tệp "
                                     "là trang CHÍNH (trang %d–%d của tài liệu gốc)%s. CHỈ tách các câu hỏi BẮT ĐẦU trong các trang chính; "
                                     "các trang phụ chỉ để đọc nốt câu vắt trang và tra đáp án." % (n, so_chinh, i + 1, j,
                                     (", sau đó là " + " và ".join(phu)) if phu else "")})
        i = j
    for k, p in enumerate(phan):
        p["ghi_chu_phan"] = p["ghi_chu_phan"] % (k + 1, len(phan))
    print("  ✂️ PDF %d trang, %.1f MB → chia %d phần." % (n, len(du_lieu) / 1048576, len(phan)), flush=True)
    return phan


# ---------------- GEMINI ----------------
def doc_cau_hinh(kho):
    global SO_CAU_MOI_LO, SO_LO_TOI_DA, TOI_DA_LUOT_TRA_PHI, CHO_PHEP_DOC_DE, CHO_PHEP_DOC_NEN, GIOI_HAN_TAI_VE
    try:
        v = kho.worksheet(TAB_CAU_HINH).get_all_values()[1:]
        cfg = {str(r[0]).strip(): (str(r[1]).strip() if len(r) > 1 else "") for r in v if r and str(r[0]).strip()}
    except Exception:
        cfg = {}
    def _so(ten, mac_dinh):
        try:
            return int(float(cfg.get(ten, "")))
        except ValueError:
            return mac_dinh
    # Nút điều chỉnh trên tab CauHinh (không có thì giữ giá trị từ biến môi trường / mặc định)
    SO_CAU_MOI_LO = max(5, _so("GIOI_HAN_SO_CAU_TOI_DA", SO_CAU_MOI_LO))
    SO_LO_TOI_DA = max(1, _so("SO_LO_TOI_DA", SO_LO_TOI_DA))
    TOI_DA_LUOT_TRA_PHI = max(0, _so("TOI_DA_LUOT_TRA_PHI", TOI_DA_LUOT_TRA_PHI))
    CHO_PHEP_DOC_DE = cfg.get("CHO_PHEP_DOC_DE", "true").strip().lower() not in ("false", "0", "no", "off", "tat", "tắt")
    CHO_PHEP_DOC_NEN = cfg.get("CHO_PHEP_DOC_NEN", "true" if CHO_PHEP_DOC_NEN else "false").strip().lower() not in ("false", "0", "no", "off", "tat", "tắt")   # [20/11/2026]
    GIOI_HAN_TAI_VE = max(50, _so("GIOI_HAN_TAI_MB", GIOI_HAN_TAI_VE // 1048576)) * 1024 * 1024
    chinh = cfg.get("MODEL_CHINH") or MODEL_MAC_DINH
    du_phong = [m.strip() for m in re.split(r"[,;\s]+", cfg.get("MODEL_DU_PHONG", "")) if m.strip()] or MODEL_DU_PHONG_MAC_DINH
    return [chinh] + [m for m in du_phong if m != chinh]


def goi_gemini(payload, ds_model):
    """[21/11/2026] Cổng ngoài: giới hạn số lượt gọi cùng lúc (GEMINI_SONG_SONG), phần xoay khoá nằm ở _goi_gemini_theo_khoa."""
    with _CONG_GEMINI:
        return _goi_gemini_theo_khoa(payload, ds_model)


def _goi_gemini_theo_khoa(payload, ds_model):
    """Dùng khoá miễn phí; khoá miễn phí hết lượt (mọi model báo 429) thì chuyển sang khoá trả phí (nếu có)
    cho phần còn lại của lượt chạy, tối đa TOI_DA_LUOT_TRA_PHI lượt gọi."""
    khoa_tp = os.environ.get("GEMINI_API_KEY_TRA_PHI", "").strip()
    loi_tam = []                                                 # [25/11]
    if not TRANG_THAI_KHOA["tra_phi"]:
        for ten, k in ds_khoa_mien_phi():
            with _KHOA:
                bo_qua = ten in TRANG_THAI_KHOA["het"] or ten in TRANG_THAI_KHOA["hong"]
            if bo_qua:
                continue
            try:
                return _goi_gemini_mot_khoa(payload, ds_model, k, ten)
            except HetHanMuc as e:
                with _KHOA:
                    TRANG_THAI_KHOA["het"].add(ten)
                    if getattr(e, "theo_ngay", False):
                        TRANG_THAI_KHOA["ngay"] = True        # [15/11] có ít nhất một khoá bị 429 theo NGÀY thật
                print("⏭️ %s hết lượt trong ngày, thử khoá tiếp theo." % ten)
            except KhoaHong as e:
                with _KHOA:
                    TRANG_THAI_KHOA["hong"].add(ten)
                print("🔑 %s bị Google từ chối (khoá hỏng), bỏ khoá này trong lượt chạy và thử khoá tiếp theo: %s" % (ten, str(e)[:160]), flush=True)
            except RuntimeError as e:                     # [25/11] lỗi tạm (vd 503 quá tải): thử khoá kế tiếp thay vì dừng cả lượt, KHÔNG đánh dấu hết lượt/hỏng
                loi_tam.append(e)
                print("⚠️ %s gặp lỗi tạm, thử khoá tiếp theo: %s" % (ten, str(e)[:160]), flush=True)
        if loi_tam:                                              # [25/11] mọi khoá còn lại đều lỗi tạm → báo lỗi tạm, không chuyển sang khoá trả phí
            raise loi_tam[-1]
        with _KHOA:
            if not khoa_tp:
                if TRANG_THAI_KHOA["hong"] and not TRANG_THAI_KHOA["het"]:
                    raise KhoaHong("KHOA_HONG – mọi khoá miễn phí đều bị Google từ chối: " + ", ".join(sorted(TRANG_THAI_KHOA["hong"])))
                raise _het_han_muc("HET_HAN_MUC – mọi khoá miễn phí đã hết lượt: " + ", ".join(sorted(TRANG_THAI_KHOA["het"]))
                                   + ((" (khoá hỏng: " + ", ".join(sorted(TRANG_THAI_KHOA["hong"])) + ")") if TRANG_THAI_KHOA["hong"] else ""),
                                   theo_ngay=TRANG_THAI_KHOA.get("ngay", False))
        with _KHOA:
            if not TRANG_THAI_KHOA["tra_phi"]:
                TRANG_THAI_KHOA["tra_phi"] = True
                print("💳 Mọi khoá miễn phí hết lượt → chuyển sang khoá trả phí (tối đa %d lượt gọi)." % TOI_DA_LUOT_TRA_PHI)
    with _KHOA:                                                  # [21/11/2026] kiểm tra + tăng bộ đếm là MỘT bước: nhiều luồng không vượt trần chi phí
        if TRANG_THAI_KHOA["da_dung_tra_phi"] >= TOI_DA_LUOT_TRA_PHI:
            raise _het_han_muc("HET_HAN_MUC – đã dùng đủ %d lượt khoá trả phí trong lượt chạy này" % TOI_DA_LUOT_TRA_PHI, theo_ngay=True)   # trần chi phí: chạy lại ngay chỉ tốn thêm tiền
        TRANG_THAI_KHOA["da_dung_tra_phi"] += 1
    return _goi_gemini_mot_khoa(payload, ds_model, khoa_tp, "GEMINI_API_KEY_TRA_PHI")


def _ghi_quota(model, ten_khoa, ma, data=None, treo=False):
    if not Q:
        return
    try:
        tk_vao, tk_ra = Q.token_gemini(data) if ma == 200 else (0, 0)
        Q.ghi_luot(Q.nhan_gemini(model, ten_khoa), ma, tk_vao, tk_ra, treo)
    except Exception:
        pass


def phan_tich_429(r):
    """Trả (het_ngay, giay_cho). Hết theo phút -> chờ rồi thử lại cùng khoá; hết theo ngày -> đổi model/khoá."""
    txt = r.text or ""
    het_ngay = bool(re.search(r"PerDay|per day|daily", txt, re.I))
    m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', txt)
    giay = float(m.group(1)) if m else (30.0 if re.search(r"PerMinute|per minute", txt, re.I) else 0.0)
    return het_ngay, giay


def _goi_gemini_mot_khoa(payload, ds_model, key, ten_khoa=""):
    ds_model, ds_loi, co_loi_khac = list(ds_model), [], False
    thay_ngay = False                              # [15/11] có lần 429 thuộc loại theo NGÀY
    m = 0
    while m < len(ds_model) and m < 6:
        model = ds_model[m]
        payload["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0} if model.startswith("gemini-2.") else {"thinkingLevel": "low"}
        lan = 0
        while lan < 3:
            try:
                r = requests.post("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model,
                                  headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                                  data=json.dumps(payload), timeout=600)
            except requests.RequestException as e:
                _ghi_quota(model, ten_khoa, 0, treo=True)
                ds_loi.append("%s: %s" % (model, str(e)[:120])); co_loi_khac = True
                break
            if r.status_code == 200:
                data = r.json()
                _ghi_quota(model, ten_khoa, 200, data)
                return data, model
            _ghi_quota(model, ten_khoa, r.status_code)
            try:
                msg = (r.json().get("error") or {}).get("message", r.text)[:220]
            except ValueError:
                msg = r.text[:220]
            if la_loi_khoa(r.status_code, r.text):
                raise KhoaHong("%s lỗi %d: %s" % (ten_khoa or "khoá", r.status_code, msg))
            if r.status_code not in (429, 402):
                co_loi_khac = True
            else:
                het_ngay, giay = phan_tich_429(r)
                thay_ngay = thay_ngay or het_ngay
                if not het_ngay and 0 < giay <= 90 and lan < 2:
                    print("⏳ %s chạm giới hạn theo phút, chờ %.0fs rồi thử lại." % (ten_khoa or model, giay), flush=True)
                    time.sleep(giay + 2); lan += 1
                    continue
            if r.status_code == 404 or re.search(r"no longer available|not found", msg, re.I):
                for x in re.findall(r"models/(gemini-[\w.\-]*\w)", msg):
                    if x != model and x not in ds_model:
                        ds_model.append(x)
                ds_loi.append("%s: ngừng hỗ trợ (404)" % model)
                break
            if r.status_code == 400 and re.search("thinking", msg, re.I) and "thinkingConfig" in payload["generationConfig"]:
                del payload["generationConfig"]["thinkingConfig"]
                continue
            if r.status_code in (500, 502, 503, 504) and lan < 2:
                time.sleep((lan + 1) * 10); lan += 1
                continue
            ds_loi.append("%s lỗi %d: %s" % (model, r.status_code, msg))
            break
        m += 1
    tom_tat = " | ".join(ds_loi)
    if not co_loi_khac:
        raise _het_han_muc("HET_HAN_MUC – " + tom_tat, theo_ngay=thay_ngay)
    raise RuntimeError(tom_tat or "Không gọi được Gemini")


SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "la_tai_lieu_vat_li": {"type": "BOOLEAN"},
        "loai_de": {"type": "STRING"}, "lop": {"type": "INTEGER"}, "don_vi": {"type": "STRING"},
        "nam_hoc": {"type": "STRING"}, "ky_thi": {"type": "STRING"}, "con_cau_sau": {"type": "BOOLEAN"},
        "cau_hoi": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "so_cau": {"type": "STRING"},
            "dang": {"type": "STRING", "enum": ["TN", "DS", "TLN", "TL"]},
            "noi_dung": {"type": "STRING"},
            "phuong_an": {"type": "ARRAY", "items": {"type": "STRING"}},
            "dap_an": {"type": "STRING"}, "loi_giai": {"type": "STRING"},
            "ma_yccd": {"type": "ARRAY", "items": {"type": "STRING"}},
            "muc_do": {"type": "STRING", "enum": ["NB", "TH", "VD", "VDC"]},
            "diem": {"type": "STRING"},
            "ngoai_ct2018": {"type": "BOOLEAN"}, "ly_do_ngoai_ct": {"type": "STRING"}},
            "required": ["so_cau", "dang", "noi_dung", "ma_yccd", "muc_do", "ngoai_ct2018"]}}},
    "required": ["la_tai_lieu_vat_li", "cau_hoi"]}


def gemini_doc_de(tep, viec, yccd, ds_model, gioi_han=0, pham_vi=None):
    if pham_vi:
        cach_tach = ("các câu hỏi thứ %d đến thứ %d (đếm theo thứ tự xuất hiện trong tài liệu, câu đầu tiên là câu thứ 1); "
                     "ghi con_cau_sau = true nếu sau câu thứ %d vẫn còn câu hỏi" % (pham_vi[0], pham_vi[1], pham_vi[1]))
    else:
        cach_tach = str(gioi_han) + " câu hỏi ĐẦU TIÊN" if gioi_han else "TẤT CẢ câu hỏi"
    loi_nhan = ((tep.get("ghi_chu_phan") + "\n") if tep.get("ghi_chu_phan") else "") + (
        "Bạn là giáo viên Vật lí THPT, đang xây ngân hàng câu hỏi theo chương trình GDPT 2018 (sách Kết nối tri thức).\n"
        "Tài liệu đính kèm: \"" + viec["ten"] + "\" (chủ đề tải về: " + (viec["chu_de"] or "không rõ") + ").\n\n"
        "NHIỆM VỤ\n"
        "1. Xác định đây có phải đề thi, đề kiểm tra hoặc tài liệu bài tập Vật lí có câu hỏi không (la_tai_lieu_vat_li).\n"
        "2. Ghi thông tin chung: loai_de (HSG / TN chính thức / TN minh hoạ / TN thi thử / KT giữa kì / KT cuối kì / "
        "Bài tập / Phiếu học tập / Khác), lop, don_vi (Sở, trường), nam_hoc, ky_thi.\n"
        "3. Tách " + cach_tach + ", mỗi câu một phần tử, đúng thứ tự trong đề:\n"
        " - so_cau: số câu như trong đề (ví dụ \"1\", \"Câu 3\", \"Bài 2\").\n"
        " - dang: TN (nhiều lựa chọn), DS (đúng/sai, giữ các ý a, b, c, d trong cùng một câu), TLN (trả lời ngắn), TL (tự luận).\n"
        " - noi_dung: chép NGUYÊN VĂN đề bài; công thức viết LaTeX trong $...$; hình vẽ thay bằng [Hình: mô tả ngắn].\n"
        " - phuong_an: các phương án A, B, C, D hoặc các ý a, b, c, d (mỗi phương án một chuỗi); câu khác để mảng rỗng.\n"
        " - dap_an, loi_giai: CHỈ lấy từ đáp án / hướng dẫn chấm có trong tài liệu (lời giải tóm tắt, tối đa 600 kí tự). "
        "Không có thì để rỗng, KHÔNG tự giải.\n"
        " - ma_yccd: 1 đến 3 mã phù hợp nhất, CHỈ lấy trong danh sách bên dưới, và chỉ khi kiến thức câu hỏi kiểm tra THỰC SỰ nằm trong "
        "yêu cầu của mã đó. TUYỆT ĐỐI không gắn mã gượng ép (ví dụ câu giao thoa ánh sáng không được gắn mã sóng điện từ). "
        "Nội dung ngoài danh sách (chương trình cũ, chuyên đề) thì để mảng rỗng.\n"
        " - ngoai_ct2018: true nếu câu kiểm tra kiến thức KHÔNG thuộc nội dung cốt lõi chương trình GDPT 2018 (không khớp YCCĐ nào), "
        "đặc biệt các nội dung của chương trình 2006 sau: " + CT_CU_MO_TA + " Khi true thì ma_yccd để rỗng và ghi ly_do_ngoai_ct (ngắn).\n"
        " - muc_do: NB, TH, VD hoặc VDC, theo yêu cầu thực tế của câu (không chép theo mã YCCĐ).\n"
        " - diem: điểm của câu nếu đề ghi.\n\n"
        "DANH SÁCH YCCĐ (mã | bài | yêu cầu):\n" + yccd["van_ban"])
    payload = {
        "contents": [{"role": "user", "parts": [
            {"inline_data": {"mime_type": tep["mime"], "data": base64.b64encode(tep["data"]).decode()}},
            {"text": loi_nhan}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA,
                             "temperature": 0.2, "maxOutputTokens": 60000}}
    data, model = goi_gemini(payload, ds_model)
    cand = (data.get("candidates") or [None])[0]
    if not cand:
        raise RuntimeError("Gemini không trả kết quả: " + json.dumps(data)[:200])
    if cand.get("finishReason") == "MAX_TOKENS" and not gioi_han:
        return {"qua_dai": True}
    text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
    try:
        return {"du_lieu": json.loads(text), "model": model}
    except ValueError:
        if not gioi_han or pham_vi:
            return {"qua_dai": True}
        raise RuntimeError("Gemini trả JSON hỏng (finishReason %s)" % cand.get("finishReason"))


# ---------------- DỮ LIỆU ----------------
def bo_dau(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "d").lower()
    s = re.sub(r"\$|\\[a-z]+", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s)


def tu_khoa_ct_cu(noi_dung, phuong_an):
    m = RE_CT_CU.search(bo_dau(str(noi_dung or "") + " " + str(phuong_an or "")))
    return m.group(1) if m else ""


def doc_yccd(kho):
    kq = {"ds": [], "hop_le": set(), "van_ban": ""}
    for r in kho.worksheet(TAB_YCCD).get_all_values()[1:]:
        r = (r + [""] * 7)[:7]
        ma = str(r[0]).strip()
        if not ma or re.search(r"-PC\d+$", ma):
            continue
        kq["hop_le"].add(ma)
        kq["ds"].append("%s | %s | %s" % (ma, re.sub(r"^Bài\s*", "B", str(r[4])), r[6]))
    kq["van_ban"] = "\n".join(kq["ds"])
    return kq


def lay_id_file(link):
    m = re.search(r"/d/([\w-]{20,})", link) or re.search(r"[?&]id=([\w-]{20,})", link)
    return m.group(1) if m else ""


def dong_bo_danh_sach(gc, tab_xl):
    nguon = gc.open_by_key(ID_BANG_DOWNLOAD).worksheet(TAB_DA_TAI).get_all_values()[1:]
    da_co = {r[0] for r in tab_xl.get_all_values()[1:] if r}
    moi = []
    for r in nguon:
        r = (r + [""] * 7)[:7]
        fid = lay_id_file(str(r[2]))
        if not fid or fid in da_co:
            continue
        da_co.add(fid)
        moi.append([fid, r[1], r[2], r[5], "Chờ", "", 0, "", "", "", "", "", ""])
    if moi:
        tab_xl.append_rows(moi, value_input_option="USER_ENTERED", table_range="A1")
    return len(moi)


# ---------------- [MỚI] QUÉT THƯ MỤC NGUỒN: đưa file thầy tự tải lên vào hàng chờ ----------------
# Trước đây chỉ file do Download Agent ghi vào tab DaTai mới vào hàng chờ; file thầy tự đưa lên Drive thì không ai đọc.
# Bước này liệt kê file trong thư mục nguồn (kể cả thư mục con) và thêm vào XuLyDe nếu chưa có (so theo File ID).
# Thư mục phải được chia sẻ (quyền Xem) cho tài khoản dịch vụ. Muốn thêm thư mục khác: đặt biến môi trường
# THU_MUC_NGUON_THEM = "id1,id2" hoặc sửa danh sách dưới đây.
THU_MUC_NGUON = [
    "1vhmU0eHbJv9QSuUY3O0s32y1NU0JfN5u",
    "13qTafF7j1MEypcETiU3DD4T9rLGNiJqm",
    "1faJ18MELk-R_e-y8qzRUlNe5xQgbttxZ",
    "17ekG9WLOP1jZ4-yl1HcopmfnNvkpB_RR",
    "1ur54UiZ2IPcbI0FMXdZ0Ifr-iwRYKghL",
]
MIME_DOC_DUOC = {"application/pdf", "application/msword", "application/vnd.google-apps.document",
                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


CHO_PHEP_QUET_CHIA_SE = os.environ.get("CHO_PHEP_QUET_CHIA_SE", "true").strip().lower() not in ("false", "0", "no", "off", "tat", "tắt")   # [20/11/2026]
GIOI_HAN_CHIA_SE_MOI_LUOT = int(os.environ.get("GIOI_HAN_CHIA_SE_MOI_LUOT", "200"))     # chặn hàng chờ phình to trong một lượt


def la_file_doc_duoc(mime, ten):
    """[20/11/2026] Cùng điều kiện nhận file như vòng quét thư mục nguồn bên dưới (PDF / Word / Docs / ảnh / tệp nén)."""
    return bool(mime in MIME_DOC_DUOC or re.match(r"^image/(png|jpeg|webp)$", mime or "") or re.search(r"\.docx?$", ten or "", re.I)
                or (CHO_PHEP_DOC_NEN and la_tep_nen(mime, ten)))


def quet_thu_muc_nguon(drive, tab_xl):
    ds_goc = THU_MUC_NGUON + [x.strip() for x in os.environ.get("THU_MUC_NGUON_THEM", "").split(",") if x.strip()]
    da_co = {r[0] for r in tab_xl.get_all_values()[1:] if r}
    moi, da_quet = [], set()

    def liet_ke(thu_muc, ten_duong):
        if thu_muc in da_quet:
            return
        da_quet.add(thu_muc)
        trang = None
        while True:
            kq = drive.files().list(q="'%s' in parents and trashed = false" % thu_muc,
                                    fields="nextPageToken, files(id,name,mimeType)", pageSize=1000, pageToken=trang,
                                    supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
            for f in kq.get("files", []):
                mime, fid, ten = f.get("mimeType", ""), f["id"], f.get("name", "")
                if mime == "application/vnd.google-apps.folder":
                    liet_ke(fid, ten_duong + "/" + ten)
                elif fid in da_co:
                    continue
                elif mime in MIME_DOC_DUOC or re.match(r"^image/(png|jpeg|webp)$", mime) or re.search(r"\.docx?$", ten, re.I) \
                        or (CHO_PHEP_DOC_NEN and la_tep_nen(mime, ten)):        # [20/11/2026] tệp nén
                    da_co.add(fid)
                    moi.append([fid, ten, "https://drive.google.com/file/d/%s/view" % fid, ten_duong.strip("/"),
                                "Chờ", "", 0, "", "", "", "", "", ""])
            trang = kq.get("nextPageToken")
            if not trang:
                break

    for goc in ds_goc:
        try:
            ten_goc = drive.files().get(fileId=goc, fields="name", supportsAllDrives=True).execute().get("name", "")
            liet_ke(goc, ten_goc)
        except Exception as e:
            print("⚠️ Không quét được thư mục %s (đã chia sẻ cho tài khoản dịch vụ chưa?): %s" % (goc, str(e)[:160]))
    # [20/11/2026] "Được chia sẻ với tôi": thêm sau vòng thư mục nguồn, nên thư mục đã quét ở trên (da_quet) và file đã có (da_co) tự bị bỏ qua.
    if CHO_PHEP_QUET_CHIA_SE:
        n_truoc = len(moi)
        try:
            trang = None
            while True:
                kq = drive.files().list(q="sharedWithMe = true and trashed = false",
                                        fields="nextPageToken, files(id,name,mimeType)", pageSize=1000, pageToken=trang,
                                        supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
                for f in kq.get("files", []):
                    mime, fid, ten = f.get("mimeType", ""), f["id"], f.get("name", "")
                    if mime == "application/vnd.google-apps.folder":
                        liet_ke(fid, "Được chia sẻ/" + ten)
                    elif fid not in da_co and la_file_doc_duoc(mime, ten):
                        da_co.add(fid)
                        moi.append([fid, ten, "https://drive.google.com/file/d/%s/view" % fid, "Được chia sẻ",
                                    "Chờ", "", 0, "", "", "", "", "", ""])
                trang = kq.get("nextPageToken")
                if not trang:
                    break
        except Exception as e:                      # phần phụ: lỗi thì cảnh báo, các nguồn khác vẫn chạy
            print("⚠️ Không quét được \"Được chia sẻ với tôi\": %s" % str(e)[:160], flush=True)
        if len(moi) - n_truoc > GIOI_HAN_CHIA_SE_MOI_LUOT:
            print("ℹ️ \"Được chia sẻ với tôi\": có %d file mới, chỉ thêm %d file lượt này (GIOI_HAN_CHIA_SE_MOI_LUOT), phần còn lại lượt sau."
                  % (len(moi) - n_truoc, GIOI_HAN_CHIA_SE_MOI_LUOT), flush=True)
            del moi[n_truoc + GIOI_HAN_CHIA_SE_MOI_LUOT:]
        print("🔗 Được chia sẻ với tôi: %d file mới." % (len(moi) - n_truoc), flush=True)
    if moi:
        tab_xl.append_rows(moi, value_input_option="USER_ENTERED", table_range="A1")
    return len(moi)


def lay_file_cho(tab_xl, da_lam):
    for i, r in enumerate(tab_xl.get_all_values()[1:]):
        r = (r + [""] * len(COT_XL))[:len(COT_XL)]
        tt, lan = r[4], int(float(r[6] or 0))
        if r[0] in da_lam:
            continue
        if tt == "Chờ" or (tt == "Lỗi" and lan < SO_LAN_THU):
            return {"dong": i + 2, "id": r[0], "ten": r[1], "link": r[2], "chu_de": r[3], "lan_thu": lan, "trang_thai": tt}
    return None


def tao_dong_cau_hoi(c, i, d, viec, yccd, luc):
    ngoai = c.get("ngoai_ct2018") is True
    ma = [] if ngoai else [str(x).strip().upper() for x in (c.get("ma_yccd") or []) if str(x).strip()]
    hop_le = [x for x in ma if x in yccd["hop_le"]]
    sai = [x for x in ma if x not in yccd["hop_le"]]
    kiem_tra = []
    if sai:
        kiem_tra.append("Mã không có trong YCCD: " + ", ".join(sai))
    if ngoai:
        kiem_tra.append("Ngoài chương trình 2018" + (": " + c["ly_do_ngoai_ct"] if c.get("ly_do_ngoai_ct") else ""))
    elif not hop_le:
        kiem_tra.append("Chưa gắn được YCCĐ (có thể ngoài chương trình)")
    pa = c.get("phuong_an") or []
    tk = "" if ngoai else tu_khoa_ct_cu(c.get("noi_dung"), " ".join(pa))
    if tk:
        kiem_tra.append("Có từ khoá nội dung chương trình cũ (\"%s\") – cần xác nhận" % tk)
    if c.get("dang") == "TN" and len(pa) < 2:
        kiem_tra.append("Thiếu phương án")
    ma_bai = "-".join(hop_le[0].split("-")[:2]) if hop_le else ""
    lop = int(ma_bai[2:4]) if re.match(r"^VL\d{2}", ma_bai) else (d.get("lop") or "")
    so = re.sub(r"^câu\s*", "", str(c.get("so_cau") or i + 1).strip(), flags=re.I) or str(i + 1)
    ten_nguon = viec["ten"] if c.get("_nguon") in (None, "", viec["ten"]) else "%s › %s" % (viec["ten"], c["_nguon"])   # [20/11/2026] file con trong tệp nén
    return ["C-%s-%03d" % (str(viec["id"])[:8], i + 1), ", ".join(hop_le), ma_bai, lop,
            TEN_MUC.get(c.get("muc_do"), c.get("muc_do") or ""), TEN_DANG.get(c.get("dang"), c.get("dang") or ""),
            L.chuan_hoa_latex(c.get("noi_dung") or ""), L.chuan_hoa_latex("\n".join(pa)), c.get("dap_an") or "",
            L.chuan_hoa_latex(c.get("loi_giai") or ""), c.get("diem") or "",   # [Mục 24]
            d.get("loai_de") or "", d.get("don_vi") or "", d.get("nam_hoc") or "", d.get("ky_thi") or "",
            "%s (câu %s)" % (ten_nguon, so), viec["link"], viec["id"], viec["chu_de"], "; ".join(kiem_tra),
            "Loại" if ngoai else "Chưa duyệt", luc]


def xoa_cau_cua_file(kho, tab_nh, file_id):
    cot = COT_NH.index("File ID") + 1
    ids = tab_nh.col_values(cot)
    dong = [i + 1 for i, v in enumerate(ids) if i > 0 and v == file_id]
    if dong:
        kho.batch_update({"requests": [{"deleteDimension": {"range": {"sheetId": tab_nh.id, "dimension": "ROWS",
                          "startIndex": d - 1, "endIndex": d}}} for d in sorted(dong, reverse=True)]})


class HetThoiGian(Exception):
    pass


def doc_mot_phan(tep, viec, yccd, ds_model):
    """Đọc một tệp (hoặc một phần): cả tài liệu trong 1 lượt; dài quá thì đọc tiếp theo lô cho đến hết.
    Trả (thông tin chung, danh sách câu, còn sót?, số lượt gọi, model)."""
    kq = gemini_doc_de(tep, viec, yccd, ds_model)
    if not kq.get("qua_dai"):
        d = kq["du_lieu"]
        return d, d.get("cau_hoi") or [], False, 1, kq["model"]
    print("  📚 Tài liệu dài: đọc theo lô %d câu…" % SO_CAU_MOI_LO, flush=True)
    chung, cau, da_co, tu, co, so_lo, model = None, [], set(), 1, SO_CAU_MOI_LO, 0, ""
    while True:
        if so_lo >= SO_LO_TOI_DA:
            return chung or {}, cau, True, so_lo + 1, model
        if not con_thoi_gian(giay_du_tru=240):
            raise HetThoiGian("Hết thời gian lượt chạy khi đang đọc câu %d" % tu)
        kq = gemini_doc_de(tep, viec, yccd, ds_model, pham_vi=(tu, tu + co - 1))
        if kq.get("qua_dai"):
            if co > 10:
                co //= 2; continue
            raise RuntimeError("Lô câu %d–%d vẫn quá dài với Gemini" % (tu, tu + co - 1))
        so_lo += 1
        d, model = kq["du_lieu"], kq["model"]
        if chung is None:
            chung = d
            if not d.get("la_tai_lieu_vat_li"):
                return d, [], False, so_lo + 1, model
        moi = []
        for c in d.get("cau_hoi") or []:
            k = (str(c.get("so_cau") or "").strip().lower(), bo_dau(c.get("noi_dung"))[:80])
            if k not in da_co:
                da_co.add(k); moi.append(c)
        cau += moi
        print("  … lô %d: câu %d–%d → %d câu mới" % (so_lo, tu, tu + co - 1, len(moi)), flush=True)
        if not moi or d.get("con_cau_sau") is False or (d.get("con_cau_sau") is None and len(moi) < co):
            return chung, cau, False, so_lo + 1, model
        tu += len(moi)


def xu_ly_mot_file(kho, drive, tab_xl, tab_nh, viec, yccd, ds_model):
    luc = bay_gio()
    try:
        tep = chuan_bi_tep_day_du(drive, viec["id"])
        if tep.get("bo_qua"):
            tab_xl.update(range_name="E%d:I%d" % (viec["dong"], viec["dong"]), values=[["Bỏ qua", 0, viec["lan_thu"], tep["bo_qua"], luc]],
                          value_input_option="USER_ENTERED")
            return 0
        d, tat_ca, mot_phan, so_luot, model = None, [], False, 0, ""
        loi_con = []                                         # [20/11/2026] file con trong tệp nén bị lỗi
        for phan in tep["phan"]:
            ten_phan = phan.get("ten") or viec["ten"]
            if tep.get("tu_nen") and not con_thoi_gian(giay_du_tru=300):
                raise HetThoiGian("Hết thời gian lượt chạy khi đang đọc tệp nén")
            try:
                dp, cau, sot, n, model = doc_mot_phan(phan, dict(viec, ten=ten_phan), yccd, ds_model)
            except (HetHanMuc, HetThoiGian):
                raise
            except Exception as e:
                if not tep.get("tu_nen"):
                    raise
                loi_con.append("%s: %s" % (ten_phan, str(e)[:80]))
                print("  ⚠️ File con %s lỗi, bỏ qua: %s" % (ten_phan, str(e)[:160]), flush=True)
                continue
            for c in cau:
                c["_nguon"] = ten_phan
            so_luot += n
            mot_phan = mot_phan or sot
            if dp.get("la_tai_lieu_vat_li") and (d is None or not d.get("la_tai_lieu_vat_li")):
                d = dp
            elif d is None:
                d = dp
            tat_ca += cau
        if d is None:                                        # chỉ xảy ra khi MỌI file con của tệp nén đều lỗi
            raise RuntimeError(("Mọi file trong tệp nén đều lỗi: " + "; ".join(loi_con))[:290])
        d = dict(d or {})
        d["cau_hoi"] = tat_ca
        kq = {"model": model}
        if not d.get("la_tai_lieu_vat_li") or not d.get("cau_hoi"):
            tab_xl.update(range_name="E%d:I%d" % (viec["dong"], viec["dong"]),
                          values=[["Bỏ qua", 0, viec["lan_thu"] + 1, "Không phải đề/tài liệu Vật lí có câu hỏi", luc]],
                          value_input_option="USER_ENTERED")
            return 0
        if viec["trang_thai"] == "Lỗi":
            xoa_cau_cua_file(kho, tab_nh, viec["id"])
        dong = [tao_dong_cau_hoi(c, i, d, viec, yccd, luc) for i, c in enumerate(d["cau_hoi"])]
        da_co = set(tab_nh.col_values(1))                    # câu đã có mã trong ngân hàng (file từng đọc một phần) → không ghi lại
        dong = [r for r in dong if r[0] not in da_co]
        if dong:
            tab_nh.append_rows(dong, value_input_option="RAW", table_range="A1")
        ghi_chu = []
        if tep.get("tu_nen"):
            ghi_chu.append("Tệp nén: đọc %d phần từ các file bên trong" % len(tep["phan"]))
        elif len(tep["phan"]) > 1:
            ghi_chu.append("Tài liệu lớn: đọc theo %d phần" % len(tep["phan"]))
        if so_luot > len(tep["phan"]):
            ghi_chu.append("tài liệu dài: đọc theo lô (%d lượt Gemini)" % so_luot)
        if mot_phan:
            ghi_chu.append("chưa đọc hết: đã đủ %d lô/phần – tăng SO_LO_TOI_DA rồi đặt lại trạng thái \"Chờ\" để đọc tiếp" % SO_LO_TOI_DA)
        if loi_con:
            ghi_chu.append("%d file con lỗi, chưa đọc được (%s) – tải riêng file đó vào thư mục nguồn" % (len(loi_con), "; ".join(loi_con)))
        if len(d["cau_hoi"]) > len(dong):
            ghi_chu.append("%d câu đã có sẵn trong ngân hàng, không ghi lại" % (len(d["cau_hoi"]) - len(dong)))
        tab_xl.update(range_name="E%d:M%d" % (viec["dong"], viec["dong"]), values=[[
            "Đã xử lý (một phần)" if (mot_phan or loi_con) else "Đã xử lý", len(dong), viec["lan_thu"] + 1,
            "; ".join(ghi_chu)[:500], luc,
            d.get("loai_de") or "", d.get("lop") or "", d.get("don_vi") or "", d.get("nam_hoc") or ""]], value_input_option="USER_ENTERED")
        print("✅ %s: %d câu (%s)" % (viec["ten"], len(dong), kq["model"]))
        return len(dong)
    except (HetHanMuc, HetThoiGian) as e:
        tab_xl.update(range_name="H%d:I%d" % (viec["dong"], viec["dong"]), values=[[str(e)[:300], luc]], value_input_option="USER_ENTERED")
        raise
    except Exception as e:
        loi = str(e)[:300]
        lan = viec["lan_thu"] + 1
        tab_xl.update(range_name="E%d:I%d" % (viec["dong"], viec["dong"]),
                      values=[["Lỗi – bỏ qua" if lan >= SO_LAN_THU else "Lỗi", "", lan, loi, luc]], value_input_option="USER_ENTERED")
        print("⚠️ %s: %s" % (viec["ten"], loi))
        return 0


def ghi_nhip(kho, ok, ghi_chu):
    try:
        tab = kho.worksheet(TAB_AGENT)
        ten = tab.col_values(1)
        luc = dt.datetime.now(TZ).strftime("%d/%m/%Y %H:%M")
        if TEN_AGENT in ten:
            dong = ten.index(TEN_AGENT) + 1
        else:
            dong = len(ten) + 1
            tab.update(range_name="A%d:D%d" % (dong, dong), values=[[TEN_AGENT, "Miễn phí", "", 26]], value_input_option="USER_ENTERED")
        tab.update(range_name=("E%d" if ok else "F%d") % dong, values=[[luc]], value_input_option="USER_ENTERED")
        tab.update(range_name="G%d" % dong, values=[[ghi_chu[:300]]], value_input_option="RAW")
    except Exception as e:
        print("Không ghi được nhịp chạy:", e)


def main():
    gc, drive, email_sa = ket_noi()
    print("Tài khoản dịch vụ:", email_sa)
    kho = gc.open_by_key(ID_KHO_CHUNG)
    tab_xl, tab_nh = kho.worksheet(TAB_XU_LY), kho.worksheet(TAB_NGAN_HANG)
    ds_model = doc_cau_hinh(kho)          # [20/11/2026] đọc tab CauHinh TRƯỚC khi quét, vì công tắc CHO_PHEP_DOC_NEN quyết định có nhận file nén không
    so_moi = dong_bo_danh_sach(gc, tab_xl)
    if so_moi:
        print("📥 Thêm %d file mới vào hàng chờ." % so_moi)
    so_quet = quet_thu_muc_nguon(drive, tab_xl)
    if so_quet:
        print("📂 Quét thư mục nguồn: thêm %d file thầy tự tải vào hàng chờ." % so_quet)
    yccd = doc_yccd(kho)
    if not yccd["ds"]:
        raise SystemExit("Tab YCCD trống.")
    print("Model:", ", ".join(ds_model))
    if not CHO_PHEP_DOC_DE:
        print("⏹️ CHO_PHEP_DOC_DE đang tắt – nghỉ lượt này.")
        ghi_nhip(kho, True, "Lượt %s: công tắc CHO_PHEP_DOC_DE đang tắt, không xử lý." % bay_gio())
        return
    so_file = so_cau = 0
    da_lam, het_han_muc = set(), False
    try:
        while con_thoi_gian(giay_du_tru=300):
            viec = lay_file_cho(tab_xl, da_lam)
            if not viec:
                break
            da_lam.add(viec["id"])
            so_cau += xu_ly_mot_file(kho, drive, tab_xl, tab_nh, viec, yccd, ds_model)
            so_file += 1
    except HetHanMuc as e:
        het_han_muc = True
        print("⏸️ Hết hạn mức Gemini, lượt sau làm tiếp:", e)
    except HetThoiGian as e:
        print("⏸️ %s – file này để lượt sau đọc lại từ đầu." % e)
    tom_tat = "Lượt %s: %d file, %d câu mới%s%s." % (bay_gio(), so_file, so_cau,
        "; dùng khoá trả phí %d lượt" % TRANG_THAI_KHOA["da_dung_tra_phi"] if TRANG_THAI_KHOA["da_dung_tra_phi"] else "",
        " – dừng vì hết hạn mức Gemini" if het_han_muc else "")
    print("📊 " + tom_tat)
    if Q:
        Q.ghi_sheet(kho)
    ghi_nhip(kho, True, tom_tat)


if __name__ == "__main__":
    try:
        main()
    except Exception as loi:
        if Q:
            Q.ghi_sheet()
        try:
            gc, _, _ = ket_noi()
            ghi_nhip(gc.open_by_key(ID_KHO_CHUNG), False, "Lỗi: " + str(loi))
        except Exception:
            pass
        raise
