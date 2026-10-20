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
TOI_DA_LUOT_TRA_PHI = int(os.environ.get("TOI_DA_LUOT_TRA_PHI", "20"))   # chặn chi phí mỗi lượt chạy
TRANG_THAI_KHOA = {"tra_phi": False, "da_dung_tra_phi": 0}


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
    if re.match(r"^image/(png|jpeg|webp)$", mime):
        return {"data": tai_ve(drive, file_id), "mime": mime, "ten": ten}
    if mime == "application/vnd.google-apps.document":
        return {"data": tai_ve(drive, file_id, xuat_pdf=True), "mime": "application/pdf", "ten": ten}
    if mime in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword") or re.search(r"\.docx?$", ten, re.I):
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
        try:
            return _goi_gemini_mot_khoa(payload, ds_model, os.environ["GEMINI_API_KEY"])
        except HetHanMuc:
            if not khoa_tp:
                raise
            TRANG_THAI_KHOA["tra_phi"] = True
            print("💳 Khoá miễn phí hết lượt trong ngày → chuyển sang khoá trả phí (tối đa %d lượt gọi)." % TOI_DA_LUOT_TRA_PHI)
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
        raise HetHanMuc("HET_HAN_MUC – " + tom_tat)
    raise RuntimeError(tom_tat or "Không gọi được Gemini")


SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "la_tai_lieu_vat_li": {"type": "BOOLEAN"},
        "loai_de": {"type": "STRING"}, "lop": {"type": "INTEGER"}, "don_vi": {"type": "STRING"},
        "nam_hoc": {"type": "STRING"}, "ky_thi": {"type": "STRING"},
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


def gemini_doc_de(tep, viec, yccd, ds_model, gioi_han=0):
    loi_nhan = (
        "Bạn là giáo viên Vật lí THPT, đang xây ngân hàng câu hỏi theo chương trình GDPT 2018 (sách Kết nối tri thức).\n"
        "Tài liệu đính kèm: \"" + viec["ten"] + "\" (chủ đề tải về: " + (viec["chu_de"] or "không rõ") + ").\n\n"
        "NHIỆM VỤ\n"
        "1. Xác định đây có phải đề thi, đề kiểm tra hoặc tài liệu bài tập Vật lí có câu hỏi không (la_tai_lieu_vat_li).\n"
        "2. Ghi thông tin chung: loai_de (HSG / TN chính thức / TN minh hoạ / TN thi thử / KT giữa kì / KT cuối kì / "
        "Bài tập / Phiếu học tập / Khác), lop, don_vi (Sở, trường), nam_hoc, ky_thi.\n"
        "3. Tách " + (str(gioi_han) + " câu hỏi ĐẦU TIÊN" if gioi_han else "TẤT CẢ câu hỏi") + ", mỗi câu một phần tử, đúng thứ tự trong đề:\n"
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
        if not gioi_han:
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
    return ["C-%s-%03d" % (str(viec["id"])[:8], i + 1), ", ".join(hop_le), ma_bai, lop,
            TEN_MUC.get(c.get("muc_do"), c.get("muc_do") or ""), TEN_DANG.get(c.get("dang"), c.get("dang") or ""),
            c.get("noi_dung") or "", "\n".join(pa), c.get("dap_an") or "", c.get("loi_giai") or "", c.get("diem") or "",
            d.get("loai_de") or "", d.get("don_vi") or "", d.get("nam_hoc") or "", d.get("ky_thi") or "",
            "%s (câu %s)" % (viec["ten"], so), viec["link"], viec["id"], viec["chu_de"], "; ".join(kiem_tra),
            "Loại" if ngoai else "Chưa duyệt", luc]


def xoa_cau_cua_file(kho, tab_nh, file_id):
    cot = COT_NH.index("File ID") + 1
    ids = tab_nh.col_values(cot)
    dong = [i + 1 for i, v in enumerate(ids) if i > 0 and v == file_id]
    if dong:
        kho.batch_update({"requests": [{"deleteDimension": {"range": {"sheetId": tab_nh.id, "dimension": "ROWS",
                          "startIndex": d - 1, "endIndex": d}}} for d in sorted(dong, reverse=True)]})


def xu_ly_mot_file(kho, drive, tab_xl, tab_nh, viec, yccd, ds_model):
    luc = bay_gio()
    try:
        tep = chuan_bi_tep(drive, viec["id"])
        if tep.get("bo_qua"):
            tab_xl.update(range_name="E%d:I%d" % (viec["dong"], viec["dong"]), values=[["Bỏ qua", 0, viec["lan_thu"], tep["bo_qua"], luc]],
                          value_input_option="USER_ENTERED")
            return 0
        kq = gemini_doc_de(tep, viec, yccd, ds_model)
        mot_phan = False
        if kq.get("qua_dai"):
            kq = gemini_doc_de(tep, viec, yccd, ds_model, SO_CAU_KHI_QUA_DAI)
            mot_phan = True
        d = kq["du_lieu"]
        if not d.get("la_tai_lieu_vat_li") or not d.get("cau_hoi"):
            tab_xl.update(range_name="E%d:I%d" % (viec["dong"], viec["dong"]),
                          values=[["Bỏ qua", 0, viec["lan_thu"] + 1, "Không phải đề/tài liệu Vật lí có câu hỏi", luc]],
                          value_input_option="USER_ENTERED")
            return 0
        if viec["trang_thai"] == "Lỗi":
            xoa_cau_cua_file(kho, tab_nh, viec["id"])
        dong = [tao_dong_cau_hoi(c, i, d, viec, yccd, luc) for i, c in enumerate(d["cau_hoi"])]
        tab_nh.append_rows(dong, value_input_option="RAW", table_range="A1")
        tab_xl.update(range_name="E%d:M%d" % (viec["dong"], viec["dong"]), values=[[
            "Đã xử lý (một phần)" if mot_phan else "Đã xử lý", len(dong), viec["lan_thu"] + 1,
            "Tài liệu dài: chỉ lấy %d câu đầu" % SO_CAU_KHI_QUA_DAI if mot_phan else "", luc,
            d.get("loai_de") or "", d.get("lop") or "", d.get("don_vi") or "", d.get("nam_hoc") or ""]], value_input_option="USER_ENTERED")
        print("✅ %s: %d câu (%s)" % (viec["ten"], len(dong), kq["model"]))
        return len(dong)
    except HetHanMuc as e:
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
    so_moi = dong_bo_danh_sach(gc, tab_xl)
    if so_moi:
        print("📥 Thêm %d file mới vào hàng chờ." % so_moi)
    yccd = doc_yccd(kho)
    if not yccd["ds"]:
        raise SystemExit("Tab YCCD trống.")
    ds_model = doc_cau_hinh(kho)
    print("Model:", ", ".join(ds_model))
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
    tom_tat = "Lượt %s: %d file, %d câu mới%s%s." % (bay_gio(), so_file, so_cau,
        "; dùng khoá trả phí %d lượt" % TRANG_THAI_KHOA["da_dung_tra_phi"] if TRANG_THAI_KHOA["da_dung_tra_phi"] else "",
        " – dừng vì hết hạn mức Gemini" if het_han_muc else "")
    print("📊 " + tom_tat)
    ghi_nhip(kho, True, tom_tat)


if __name__ == "__main__":
    try:
        main()
    except Exception as loi:
        try:
            gc, _, _ = ket_noi()
            ghi_nhip(gc.open_by_key(ID_KHO_CHUNG), False, "Lỗi: " + str(loi))
        except Exception:
            pass
        raise
