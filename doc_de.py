"""
doc_de.py – XƯỞNG ĐỌC ĐỀ (Python, chạy trên GitHub Actions) – thay cho xuLyDeMotLuot() trong XuLyDe.gs của Kho chung.

Làm ĐÚNG như bản Apps Script, chỉ khác là không còn giới hạn 6 phút/lượt và không tốn 90 phút trigger/ngày:
  1. Đọc tab DaTai của "Download Agent - Quản lý", thêm file mới vào tab XuLyDe (trạng thái "Chờ").
  2. Lấy lần lượt từng file chờ: PDF, ảnh gửi thẳng cho Gemini; Google Docs xuất PDF; Word đổi PDF bằng LibreOffice.
  3. Gemini (cùng lời nhắc, cùng schema, cùng model trong tab CauHinh) tách TỪNG câu, gắn Mã YCCĐ.
  4. Ghi câu vào NganHangCauHoi ("Chưa duyệt"), đánh dấu file trong XuLyDe; lỗi 3 lần thì bỏ qua.
  5. Ghi nhịp chạy vào tab Agent (dòng "Xưởng đọc đề (Python)") để Meta / canh gác theo dõi.
Hết hạn mức Gemini → dừng lượt, lượt sau làm tiếp. Lỗi chung → lượt chạy GitHub báo đỏ và GitHub tự email.

Biến môi trường (GitHub Secrets): GOOGLE_CREDENTIALS (toàn bộ nội dung credentials.json), GEMINI_API_KEY,
GEMINI_API_KEY_TRA_PHI (không bắt buộc): dùng khi khoá miễn phí HẾT LƯỢT trong ngày, tối đa TOI_DA_LUOT_TRA_PHI lượt gọi/lượt chạy.
"""
import base64, datetime as dt, io, json, os, re, shutil, subprocess, sys, tempfile, time, unicodedata

import gspread
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# ---------------- CẤU HÌNH (giống XuLyDe.gs) ----------------
ID_KHO_CHUNG = "1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc"
ID_BANG_DOWNLOAD = "1gL1q0LnOR4Ylr7ae-n-a20GBbo5nPkidrdEOnCZttio"   # "Download Agent - Quản lý"
TAB_DA_TAI, TAB_XU_LY, TAB_NGAN_HANG, TAB_YCCD, TAB_CAU_HINH, TAB_AGENT = "DaTai", "XuLyDe", "NganHangCauHoi", "YCCD", "CauHinh", "Agent"
TEN_AGENT = "Xưởng đọc đề (Python)"
MODEL_MAC_DINH, MODEL_DU_PHONG_MAC_DINH = "gemini-3.8-flash", ["gemini-3.5-flash-lite"]
THOI_GIAN_TOI_DA_PHUT = float(os.environ.get("THOI_GIAN_TOI_DA_PHUT", "100"))
KICH_THUOC_TOI_DA = 12 * 1024 * 1024
SO_LAN_THU = 3
SO_CAU_KHI_QUA_DAI = 40
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
TOI_DA_LUOT_TRA_PHI = int(os.environ.get("TOI_DA_LUOT_TRA_PHI", "20"))    # chặn chi phí mỗi lượt chạy
TRANG_THAI_KHOA = {"tra_phi": False, "da_dung_tra_phi": 0, "het": set()}


def ds_khoa_mien_phi():
    """GEMINI_API_KEY, GEMINI_API_KEY_2 … GEMINI_API_KEY_5 (bỏ ô trống, bỏ khoá trùng)."""
    ds = []
    for ten in ["GEMINI_API_KEY"] + ["GEMINI_API_KEY_%d" % i for i in range(2, 6)]:
        k = os.environ.get(ten, "").strip()
        if k and k not in [x[1] for x in ds]:
            ds.append((ten, k))
    return ds


class HetHanMuc(Exception):
    pass


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
        _, xong = tai.next_chunk()
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
    if re.match(r"^image/(png|jpeg|webp)\$", mime):
        return {"data": tai_ve(drive, file_id), "mime": mime, "ten": ten}
    if mime == "application/vnd.google-apps.document":
        return {"data": tai_ve(drive, file_id, xuat_pdf=True), "mime": "application/pdf", "ten": ten}
    if mime in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword") or re.search(r"\.docx?\$", ten, re.I):
        return {"data": word_sang_pdf(tai_ve(drive, file_id), ten), "mime": "application/pdf", "ten": ten}
    return {"bo_qua": "Định dạng chưa hỗ trợ (%s)" % mime}


# ---------------- GEMINI ----------------
def doc_cau_hinh(kho):
    try:
        v = kho.worksheet(TAB_CAU_HINH).get_all_values()[1:]
        cfg = {str(r[0]).strip(): str(r[1]).strip() for r in v if r and str(r[0]).strip()}
    except Exception:
        cfg = {}
    chinh = cfg.get("MODEL_CHINH") or MODEL_MAC_DINH
    du_phong = [m.strip() for m in re.split(r"[,;\s]+", cfg.get("MODEL_DU_PHONG", "")) if m.strip()] or MODEL_DU_PHONG_MAC_DINH
    return [chinh] + [m for m in du_phong if m != chinh]


def goi_gemini(payload, ds_model):
    """Dùng khoá miễn phí; khoá miễn phí hết lượt (mọi model báo 429) thì chuyển sang khoá trả phí (nếu có)
    cho phần còn lại của lượt chạy, tối đa TOI_DA_LUOT_TRA_PHI lượt gọi."""
    khoa_tp = os.environ.get("GEMINI_API_KEY_TRA_PHI", "").strip()
    if not TRANG_THAI_KHOA["tra_phi"]:
        for ten, k in ds_khoa_mien_phi():
            if ten in TRANG_THAI_KHOA["het"]:
                continue
            try:
                return _goi_gemini_mot_khoa(payload, ds_model, k)
            except HetHanMuc:
                TRANG_THAI_KHOA["het"].add(ten)
                print("⏭️ %s hết lượt trong ngày, thử khoá tiếp theo." % ten)
        if not khoa_tp:
            raise HetHanMuc("HET_HAN_MUC – mọi khoá miễn phí đã hết lượt: " + ", ".join(sorted(TRANG_THAI_KHOA["het"])))
        TRANG_THAI_KHOA["tra_phi"] = True
        print("💳 Mọi khoá miễn phí hết lượt → chuyển sang khoá trả phí (tối đa %d lượt gọi)." % TOI_DA_LUOT_TRA_PHI)
    if TRANG_THAI_KHOA["da_dung_tra_phi"] >= TOI_DA_LUOT_TRA_PHI:
        raise HetHanMuc("HET_HAN_MUC – đã dùng đủ %d lượt khoá trả phí trong lượt chạy này" % TOI_DA_LUOT_TRA_PHI)
    TRANG_THAI_KHOA["da_dung_tra_phi"] += 1
    return _goi_gemini_mot_khoa(payload, ds_model, khoa_tp)


def _goi_gemini_mot_khoa(payload, ds_model, key):
    ds_model, ds_loi, co_loi_khac = list(ds_model), [], False
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
                ds_loi.append("%s: %s" % (model, str(e)[:120])); co_loi_khac = True
                break
            if r.status_code == 200:
                return r.json(), model
            try:
                msg = (r.json().get("error") or {}).get("message", r.text)[:220]
            except ValueError:
                msg = r.text[:220]
            if r.status_code != 429:
                co_loi_khac = True
            if r.status_code == 404 or re.search(r"no longer available|not found", msg, re.I):
                for x in re.findall(r"models/(gemini-[\w.\-]*\w)", msg):
                    if x != model and x not in ds_model:
                        ds_model.append(x)
                ds_loi.append("%s: ngừng hỗ trợ (404)" % model)
                break
            if r.status_code == 400 and re.search
