"""
cuu_loai.py – CỨU CÂU "LOẠI" DO MÁY ĐẶT – bước 2, tự động.   [24/11/2026]

Hai loại lỗi được cứu (câu "Loại" do MÁY đặt: cột Kiểm tra có "[5 tầng", không phải trùng / ngoài CT 2018):

 A. LỖI TÁCH ĐỀ (thiếu phương án / thiếu ý / đề quá ngắn / lỗi nội dung / thiếu số liệu):
    1. Gửi FILE GỐC cho Gemini, yêu cầu tìm lại đúng câu và chép NGUYÊN VĂN đề + phương án.
    2. Kiểm tra bằng code: đủ 4 phương án / 4 ý, đủ dài, GIỐNG câu cũ, dấu $ chẵn.
    3. Đạt → ghi đè Nội dung + Phương án, trả về "Chưa duyệt" để duyet_cau.py chạy lại ĐẦY ĐỦ 5 tầng.

 B. LỖI HÌNH / ĐỒ THỊ (thiếu ảnh hoặc gắn nhầm nhiều ảnh sai):  [MỚI 24/11]
    1. CÓ hình trong file gốc          → cắt đúng vùng hình từ file gốc (PDF/ảnh) thay ảnh sai. KHÔNG vẽ lại.
    2. KHÔNG có hình nhưng ĐỦ dữ kiện  → Gemini viết code matplotlib, chạy trong tiến trình riêng (có giới hạn),
                                         kiểm tra PNG hợp lệ → tải lên Drive.
    3. THIẾU dữ kiện                   → KHÔNG bịa; giữ "Loại", ghi rõ không cứu được.
    Thành công → xoá ảnh cũ (ghi đè ô hình bằng ảnh mới), sửa chữ nếu cần, "Chưa duyệt" để chạy lại 5 tầng.

Mỗi câu chỉ cứu MỘT lần: dấu "[cứu Loại dd/mm: …]" ở cột Kiểm tra.

TĂNG SỐ CÂU CỨU MỖI LƯỢT (đều chỉnh bằng biến môi trường, có mặc định):
  CUU_LOAI_TOI_DA      số câu tối đa mỗi lượt                         (mặc định 100)
  CUU_LOAI_SONG_SONG   số file gốc xử lí song song                   (mặc định 1)
  CUU_LOAI_LO          số câu tách đề gửi 1 lần                      (mặc định 12)
  CUU_HINH_LO          số câu hình gửi 1 lần                         (mặc định 6)
  CUU_LOAI_CHE_DO      tat_ca | tach | hinh                          (mặc định tat_ca)
  CUU_HINH_THU_MUC_ID  ID thư mục Drive chứa ảnh cứu (BẮT BUỘC để cứu hình)
  CUU_HINH_COT         tên cột lưu hình (mặc định "Link ảnh", cùng cột duyet_cau.py đọc)
  CUU_HINH_DINH_DANG   link | id | ten (bỏ trống = tự đoán theo các ô hình đang có)
  CUU_HINH_MAU         regex nhận lí do loại về hình (mặc định = đúng 3 chuỗi duyet_cau.py ghi: "Thiếu dữ kiện khi không có hình gốc",
                       "Câu nhắc tới hình nhưng không có mô tả hình", "Nhìn hình")
  CUU_HINH_VE_MOI      0 = tắt việc vẽ mới bằng matplotlib
Cần thêm thư viện: pillow (bắt buộc cho hình), pymupdf (cắt hình từ PDF), matplotlib + numpy (vẽ mới).
"""
import base64, concurrent.futures as cf, datetime as dt, io, json, os, re, subprocess, sys, tempfile, threading

import doc_de as X
import duyet_cau as D
import cuu_nghi_van as CN

try:
    import quota_xuong as Q
except Exception:
    Q = None


def _so(ten, mac):
    try: return int(float(os.environ.get(ten, "") or mac))
    except Exception: return mac


DAU = "cứu Loại"
LI_DO_TACH = re.compile(r"Thiếu phương án|Thiếu ý đúng/sai|Nội dung câu quá ngắn|Lỗi nội dung|số liệu chưa có trong bản lưu")
# lí do về hình/đồ thị: ĐÚNG các chuỗi duyet_cau.py ghi ở cột Kiểm tra (KHÔNG dùng từ "hình" trần: lí do chung
# "Loại vì máy và các model chưa thống nhất đáp án, câu không có hình" cũng chứa chữ "hình" nhưng KHÔNG phải lỗi hình).
LI_DO_HINH = re.compile(os.environ.get("CUU_HINH_MAU") or
                        r"Thiếu dữ kiện khi không có hình gốc|Câu nhắc tới hình nhưng không có mô tả hình|Nhìn hình")
LI_DO_KHONG_CUU = re.compile(r"Trùng hẳn|Ngoài chương trình")

LO = _so("CUU_LOAI_LO", 12)
LO_HINH = _so("CUU_HINH_LO", 6)
TOI_DA = _so("CUU_LOAI_TOI_DA", 100)          # [24/11] hạ tạm vì hạn mức Actions/Gemini đang cạn; nâng lại 300 khi hết căng
SONG_SONG = max(1, _so("CUU_LOAI_SONG_SONG", 1))    # [24/11] 1 = lần lượt (tiết kiệm quota); nâng 3 khi hạn mức dư
CHE_DO = (os.environ.get("CUU_LOAI_CHE_DO") or "tat_ca").lower()
# >>> DÁN ID THƯ MỤC DRIVE CHỨA ẢNH CỨU VÀO GIỮA HAI DẤU NGOẶC KÉP (không cần sửa workflow). Biến môi trường CUU_HINH_THU_MUC_ID, nếu có, được ưu tiên.
THU_MUC_MAC_DINH = "1JBZWN5hWMqqIBwAYTWKkykfNEr1ftgK_?hl=vi"
THU_MUC = (os.environ.get("CUU_HINH_THU_MUC_ID") or THU_MUC_MAC_DINH).strip()
COT_HINH = (os.environ.get("CUU_HINH_COT") or "Link ảnh").strip()      # cùng cột duyet_cau.py đọc cho tầng 6
DINH_DANG = (os.environ.get("CUU_HINH_DINH_DANG") or "").strip().lower()
VE_MOI = (os.environ.get("CUU_HINH_VE_MOI") or "1") != "0"

KHOA_DRIVE = threading.Lock()   # googleapiclient không an toàn khi dùng song song → khoá mọi lệnh Drive

SCHEMA = {"type": "OBJECT", "properties": {"ket_qua": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "ma_cau": {"type": "STRING"}, "tim_thay": {"type": "BOOLEAN"}, "noi_dung": {"type": "STRING"}, "phuong_an": {"type": "STRING"}},
    "required": ["ma_cau", "tim_thay"]}}}, "required": ["ket_qua"]}

SCHEMA_HINH = {"type": "OBJECT", "properties": {"ket_qua": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "ma_cau": {"type": "STRING"},
    "loai": {"type": "STRING", "enum": ["CAT_TU_GOC", "VE_MOI", "THIEU_DU_KIEN", "KHONG_TIM_THAY"]},
    "trang": {"type": "INTEGER"},
    "hop": {"type": "ARRAY", "items": {"type": "NUMBER"}},
    "noi_dung": {"type": "STRING"}, "du_kien": {"type": "STRING"}, "ma_python": {"type": "STRING"}},
    "required": ["ma_cau", "loai"]}}}, "required": ["ket_qua"]}


# ───────────────────────── nhận diện câu cần cứu ─────────────────────────
def phan_loai(kt):
    """'hinh' | 'tach' | None. Câu do máy Loại, chưa từng được cứu, không phải trùng/ngoài CT."""
    if DAU in kt or D.DAU_MAY not in kt: return None
    doan = kt.rsplit(D.DAU_MAY, 1)[-1]
    if LI_DO_KHONG_CUU.search(doan): return None
    if CHE_DO in ("tat_ca", "hinh") and LI_DO_HINH.search(doan): return "hinh"
    if CHE_DO in ("tat_ca", "tach") and LI_DO_TACH.search(doan): return "tach"
    return None


def la_loai_do_tach(kt):
    return phan_loai(kt) == "tach"


# ───────────────────────── kiểm tra bản tách lại ─────────────────────────
def _so_trong(s):
    return set(re.findall(r"\d+(?:[.,]\d+)?", str(s)))


def hop_le(dang, nd_cu, nd, pa):
    """None nếu bản tách lại dùng được; ngược lại trả lí do (chuỗi)."""
    loai = D.loai_dang(dang)
    nd, pa = str(nd or "").strip(), str(pa or "").strip()
    if len(re.sub(r"\s", "", nd)) < 15: return "đề tách lại vẫn quá ngắn"
    n = D.dem_phuong_an(loai, nd, pa) if loai in ("TN", "DS") else 4
    if loai in ("TN", "DS") and n < 4: return "tách lại vẫn thiếu phương án/ý (%d/4)" % n
    a = set(X.bo_dau(str(nd_cu)[:120]).split())
    b = set(X.bo_dau(nd).split())
    if a:
        ti_le = len(a & b) / len(a)
        if ti_le < 0.6:
            # [24/11] nới có điều kiện: giống ≥ 45% VÀ mọi số liệu trong đầu câu cũ đều còn trong bản mới (câu cũ hay bị cắt/lỗi dấu)
            so_cu = _so_trong(str(nd_cu)[:200])
            if not (ti_le >= 0.45 and so_cu and so_cu <= _so_trong(nd)):
                return "bản tách lại không giống câu cũ (có thể nhầm câu)"
    return None


def hop_le_day_du(dang, nd_cu, nd, pa):
    """(nd, pa, None) nếu dùng được (đã cân $ nếu cần); (None, None, lí do) nếu không."""
    nd, ok1 = CN.sua_dola(str(nd or "")); pa, ok2 = CN.sua_dola(str(pa or ""))
    if not (ok1 and ok2): return None, None, "dấu $ lẻ, không cân được"
    ly = hop_le(dang, nd_cu, nd, pa)
    return (nd, pa, None) if ly is None else (None, None, ly)


# ───────────────────────── gọi Gemini (có chia đôi lô khi lỗi) ─────────────────────────
def _goi(tep, loi, schema, cac_model):
    data, _ = X.goi_gemini({"contents": [{"role": "user", "parts": [
        {"inline_data": {"mime_type": tep["mime"], "data": base64.b64encode(tep["data"]).decode()}}, {"text": loi}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": schema, "temperature": 0, "maxOutputTokens": 30000}},
        cac_model)
    j = json.loads("".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]))
    return {str(g.get("ma_cau")).strip(): g for g in j.get("ket_qua", [])}


def an_toan(ham, tep, lo, cac_model, **kw):
    """Lô lỗi (JSON cụt, quá dài, mạng…) → chia đôi thử lại; còn 1 câu mà vẫn lỗi → đánh dấu __loi (để lượt sau, KHÔNG tính là đã cứu)."""
    try:
        return ham(tep, lo, cac_model, **kw)
    except X.HetHanMuc:
        raise
    except Exception as e:
        if len(lo) == 1: return {lo[0]["ma"]: {"__loi": str(e)[:120]}}
        g = len(lo) // 2
        r = an_toan(ham, tep, lo[:g], cac_model, **kw)
        r.update(an_toan(ham, tep, lo[g:], cac_model, **kw))
        return r


def tach_lai(tep, lo, cac_model, ky=False):
    """ky=True: lần thử thứ 2 – gửi nhiều ngữ cảnh hơn để Gemini định vị đúng câu."""
    dai_nd, dai_pa = (450, 700) if ky else (150, 300)
    du_lieu = [{"ma_cau": x["ma"], "vi_tri": x["vi_tri"], "dang": x["dang"], "dau_cau": str(x["nd"])[:dai_nd],
                "phuong_an_hien_co": str(x["pa"])[:dai_pa]} for x in lo]
    loi = ("File đính kèm là ĐỀ GỐC. Với MỖI câu dưới đây (nhận ra bằng vi_tri và dau_cau), tìm đúng câu đó trong file và chép LẠI ĐẦY ĐỦ, "
           "NGUYÊN VĂN: noi_dung = phần đề bài (công thức LaTeX đặt trong $…$, số thập phân dấu phẩy, nếu có hình ghi [Hình: mô tả ngắn]); "
           "phuong_an = các phương án (nhiều lựa chọn: A., B., C., D.) hoặc các ý (đúng/sai: a), b), c), d)), MỖI cái một dòng. "
           "KHÔNG chép đáp án / hướng dẫn chấm vào noi_dung hay phuong_an. KHÔNG tự bịa hay suy đoán phương án: nếu file thật sự thiếu "
           "hoặc không tìm ra câu thì tim_thay = false.")
    if ky:
        loi += (" LƯU Ý LẦN THỬ LẠI: số thứ tự câu trong file có thể khác vi_tri (đánh số lại theo mã đề / phần); hãy đối chiếu theo NỘI DUNG "
                "dau_cau và số liệu, tìm cả trong các phần khác nhau của file và các mã đề khác nhau.")
    loi += "\nCÁC CÂU:\n" + json.dumps(du_lieu, ensure_ascii=False)
    return _goi(tep, loi, SCHEMA, cac_model)


def danh_gia_tach(x, g):
    """((nd, pa), '') nếu đạt; (None, lí do) nếu không; (None, None) nếu lỗi tạm (để lượt sau)."""
    if g and g.get("__loi"): return None, None
    if not g or not g.get("tim_thay"): return None, "file gốc không có / không tìm lại được câu này"
    nd, pa, ly = hop_le_day_du(x["dang"], x["nd"], g.get("noi_dung"), g.get("phuong_an"))
    return ((nd, pa), "") if not ly else (None, ly)


def cuu_tach(tep, ds, cac_model, out):
    moi = {}
    for k in range(0, len(ds), LO):
        moi.update(an_toan(tach_lai, tep, ds[k:k + LO], cac_model))
        for x in ds[k:k + LO]:                      # ghi dần để nếu hết hạn mức giữa chừng vẫn giữ phần đã làm
            out[x["ma"]] = danh_gia_tach(x, moi.get(x["ma"]))
    # lần 2: chỉ thử lại câu "không tìm lại được / không giống" với ngữ cảnh dài hơn
    sai = [x for x in ds if out[x["ma"]][1] and re.search(r"tìm lại|không giống", out[x["ma"]][1])]
    for k in range(0, len(sai), LO):
        lan2 = an_toan(tach_lai, tep, sai[k:k + LO], cac_model, ky=True)
        for x in sai[k:k + LO]:
            kq = danh_gia_tach(x, lan2.get(x["ma"]))
            if kq[0]: out[x["ma"]] = kq


# ───────────────────────── HÌNH / ĐỒ THỊ ─────────────────────────
CAM = re.compile(r"\b(os|sys|subprocess|socket|shutil|requests|urllib|eval|exec|open|compile|__import__|importlib|pathlib|input|globals|locals|getattr|setattr)\b|__")


def _png_hop_le(im):
    """(bytes PNG, '') nếu ảnh dùng được; (None, lí do) nếu không."""
    im = im.convert("RGB")
    w, h = im.size
    if w < 80 or h < 80: return None, "ảnh quá nhỏ (%dx%d)" % (w, h)
    if w > 6000 or h > 6000: return None, "ảnh quá lớn"
    hist = im.convert("L").histogram()
    if sum(hist[:240]) / float(w * h) < 0.004: return None, "ảnh gần như trống"
    b = io.BytesIO(); im.save(b, "PNG")
    return b.getvalue(), ""


def cat_anh(tep, g):
    """Cắt vùng hình từ file gốc theo toạ độ Gemini trả về. (png, '') hoặc (None, lí do)."""
    try:
        from PIL import Image
    except Exception:
        return None, "thiếu thư viện pillow"
    hop = g.get("hop")
    try:
        y0, x0, y1, x1 = [max(0.0, min(1000.0, float(v))) for v in hop]
    except Exception:
        return None, "không có toạ độ hình hợp lệ"
    if y1 - y0 < 20 or x1 - x0 < 20: return None, "toạ độ hình quá nhỏ"
    mime = str(tep.get("mime", ""))
    if "pdf" in mime:
        try:
            import fitz
        except Exception:
            return None, "thiếu thư viện pymupdf (pip install pymupdf)"
        doc = fitz.open(stream=tep["data"], filetype="pdf")
        try:
            so = int(g.get("trang") or 1) - 1
            if not 0 <= so < len(doc): return None, "số trang Gemini trả về sai"
            im = Image.open(io.BytesIO(doc[so].get_pixmap(matrix=fitz.Matrix(3, 3)).tobytes("png")))
        finally:
            doc.close()
    elif mime.startswith("image/"):
        im = Image.open(io.BytesIO(tep["data"]))
    else:
        return None, "file gốc dạng %s chưa cắt được ảnh (chỉ PDF/ảnh)" % (mime or "?")
    im = im.convert("RGB")
    W, H = im.size
    pad = 0.012
    box = (int(max(0, x0 / 1000 - pad) * W), int(max(0, y0 / 1000 - pad) * H),
           int(min(1, x1 / 1000 + pad) * W), int(min(1, y1 / 1000 + pad) * H))
    return _png_hop_le(im.crop(box))


def chay_ve(code):
    """Chạy code matplotlib do AI viết trong tiến trình riêng (thư mục tạm, 40 giây, whitelist import). (png, '') hoặc (None, lí do)."""
    code = str(code or "").strip()
    code = re.sub(r"^```(?:python)?\s*|```\s*$", "", code, flags=re.M).strip()
    if len(code) < 30: return None, "không có code vẽ"
    for m in re.finditer(r"^\s*(?:from\s+(\S+)\s+import|import\s+(.+))", code, flags=re.M):
        mods = [m.group(1)] if m.group(1) else [s.strip().split(" ")[0] for s in m.group(2).split(",")]
        for mo in mods:
            if mo.split(".")[0] not in ("matplotlib", "numpy", "math"):
                return None, "code vẽ import thư viện không cho phép (%s)" % mo
    if CAM.search(code): return None, "code vẽ có lệnh không cho phép"
    try:
        from PIL import Image
    except Exception:
        return None, "thiếu thư viện pillow"
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "ve.py"), "w", encoding="utf-8") as f:
            f.write("import matplotlib\nmatplotlib.use('Agg')\n" + code + "\n")
        env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "LD_LIBRARY_PATH") if k in os.environ}
        env.update({"MPLBACKEND": "Agg", "MPLCONFIGDIR": td, "HOME": td})
        try:
            r = subprocess.run([sys.executable, "ve.py"], cwd=td, capture_output=True, timeout=40, env=env)
        except subprocess.TimeoutExpired:
            return None, "code vẽ chạy quá 40 giây"
        if r.returncode != 0:
            return None, "code vẽ báo lỗi: " + r.stderr.decode("utf-8", "ignore").strip().splitlines()[-1][:100] if r.stderr.strip() else "code vẽ báo lỗi"
        p = os.path.join(td, "hinh.png")
        if not os.path.exists(p): return None, "code vẽ không tạo hinh.png"
        try:
            with Image.open(p) as im:
                im.load()
                return _png_hop_le(im.copy())
        except Exception as e:
            return None, "PNG hỏng: " + str(e)[:60]


def hoi_hinh(tep, lo, cac_model):
    du_lieu = [{"ma_cau": x["ma"], "vi_tri": x["vi_tri"], "dang": x["dang"], "dau_cau": str(x["nd"])[:300],
                "phuong_an_hien_co": str(x["pa"])[:200], "li_do_loai": x["ly_do"]} for x in lo]
    loi = ("File đính kèm là ĐỀ GỐC. Các câu dưới đây bị loại vì lỗi HÌNH / ĐỒ THỊ (thiếu ảnh hoặc gắn nhầm ảnh). Với MỖI câu (nhận ra bằng "
           "vi_tri và dau_cau), tìm câu đó trong file gốc rồi chọn đúng MỘT giá trị cho loai:\n"
           "- CAT_TU_GOC: file gốc CÓ hình/đồ thị của đúng câu này. Cho trang (số trang, đếm từ 1) và hop = [ymin, xmin, ymax, xmax] chuẩn hoá "
           "0–1000 bao trọn hình/đồ thị (kèm nhãn trục, chú thích, số liệu ghi trên hình) nhưng KHÔNG lấy chữ đề bài và phương án.\n"
           "- VE_MOI: file gốc KHÔNG có hình cho câu này nhưng lời đề đã ĐỦ dữ kiện định lượng để vẽ chính xác. Viết ma_python bằng matplotlib: "
           "chỉ import matplotlib, numpy, math; không đọc/ghi file nào khác; kết thúc bằng plt.savefig('hinh.png', dpi=200, bbox_inches='tight'); "
           "không dùng plt.show; hình rõ ràng, có tên trục + đơn vị, ĐÚNG từng số liệu trong đề, không thêm thông tin đề không nói.\n"
           "- THIEU_DU_KIEN: đề nhắc hình/đồ thị nhưng file gốc không có hình và chữ cũng thiếu thông số → KHÔNG vẽ; ghi du_kien là phần còn thiếu.\n"
           "- KHONG_TIM_THAY: không tìm được câu trong file.\n"
           "Nếu phần chữ trong dau_cau thiếu/sai so với file gốc thì ghi noi_dung = đề bài chép lại nguyên văn (LaTeX trong $…$, số thập phân dấu "
           "phẩy, chỗ có hình ghi [Hình: mô tả ngắn, đủ số liệu đọc được trên hình]); nếu đề cần hình mà dau_cau chưa có mô tả [Hình: …] thì BẮT BUỘC điền noi_dung kèm mô tả đó; nếu đã đúng thì để noi_dung rỗng. KHÔNG chép đáp án/hướng dẫn chấm. KHÔNG bịa số liệu.\n"
           "CÁC CÂU:\n" + json.dumps(du_lieu, ensure_ascii=False))
    return _goi(tep, loi, SCHEMA_HINH, cac_model)


def chinh_chu(x, nd_moi):
    """Giữ chữ cũ trừ khi bản chép lại hợp lệ (cân $, đủ dài, giống câu cũ)."""
    nd_moi = str(nd_moi or "").strip()
    if not nd_moi or nd_moi == str(x["nd"]).strip(): return x["nd"]
    nd, ok = CN.sua_dola(nd_moi)
    if not ok: return x["nd"]
    return nd if hop_le(x["dang"], x["nd"], nd, x["pa"]) is None else x["nd"]


def luu_drive(drive, png, ten):
    from googleapiclient.http import MediaIoBaseUpload
    with KHOA_DRIVE:
        f = drive.files().create(body={"name": ten, "parents": [THU_MUC]},
                                 media_body=MediaIoBaseUpload(io.BytesIO(png), mimetype="image/png"),
                                 fields="id", supportsAllDrives=True).execute()
        try:
            drive.permissions().create(fileId=f["id"], body={"type": "anyone", "role": "reader"}, supportsAllDrives=True).execute()
        except Exception:
            pass                                                           # thư mục đã chia sẻ sẵn thì không cần
    return f["id"]


def cuu_hinh(tep, ds, cac_model, ctx, out):
    ngay_gio = dt.datetime.now(X.TZ).strftime("%y%m%d%H%M%S")
    for k in range(0, len(ds), LO_HINH):
        lo = ds[k:k + LO_HINH]
        moi = an_toan(hoi_hinh, tep, lo, cac_model)
        for x in lo:
            g = moi.get(x["ma"])
            if g and g.get("__loi"): out[x["ma"]] = (None, None); continue          # lỗi tạm → lượt sau
            if not g: out[x["ma"]] = (None, "Gemini không trả kết quả cho câu này"); continue
            loai = g.get("loai")
            if loai == "THIEU_DU_KIEN":
                out[x["ma"]] = (None, "thiếu dữ kiện, không tự vẽ bịa: " + str(g.get("du_kien") or "")[:100]); continue
            if loai == "KHONG_TIM_THAY":
                out[x["ma"]] = (None, "không tìm thấy câu trong file gốc"); continue
            if loai == "CAT_TU_GOC":
                png, ly = cat_anh(tep, g); cach = "cắt từ file gốc"
            elif loai == "VE_MOI":
                if not VE_MOI: out[x["ma"]] = (None, "đã tắt vẽ mới"); continue
                png, ly = chay_ve(g.get("ma_python")); cach = "vẽ lại bằng matplotlib"
            else:
                out[x["ma"]] = (None, "loại xử lí không hợp lệ"); continue
            if not png: out[x["ma"]] = (None, "%s thất bại: %s" % (cach, ly)); continue
            ten = "cuu_%s_%s.png" % (re.sub(r"[^\w.-]", "_", x["ma"]), ngay_gio)
            try:
                fid_moi = luu_drive(ctx["drive"], png, ten)
            except Exception as e:
                out[x["ma"]] = (None, None); print("⚠️ Tải ảnh lên Drive lỗi (%s): %s" % (x["ma"], str(e)[:100]), flush=True); continue
            out[x["ma"]] = ({"nd": chinh_chu(x, g.get("noi_dung")), "id": fid_moi, "ten": ten, "cach": cach}, "")


# ───────────────────────── cột hình & định dạng giá trị ─────────────────────────
def tim_cot_hinh(td):
    for i, t in enumerate(td):                                            # giống duyet_cau.py: so tên không phân biệt hoa thường
        if t.strip().lower() == COT_HINH.lower(): return i
    return None


def tao_gia_tri_hinh(mau_o):
    """Trả hàm (id, ten) -> chuỗi ghi vào ô hình, theo đúng kiểu các ô hình đang có (hoặc CUU_HINH_DINH_DANG)."""
    mau_o = [m.strip() for m in mau_o if m and m.strip()]
    try:                                                                  # ô có thể chứa nhiều link: lấy link đầu theo cách duyet_cau.py tách
        mau_o = [(CN.tach_link_anh(m) or [m])[0] for m in mau_o]
    except Exception:
        pass
    kieu, mau = DINH_DANG, ""
    if not kieu:
        for m in mau_o:
            if "drive.google.com" in m or "googleusercontent" in m:
                kieu, mau = "link", re.split(r"[\s,;]+", m)[0]; break
        else:
            if any(re.fullmatch(r"[-\w]{25,}", m.split("\n")[0].strip()) for m in mau_o): kieu = "id"
            elif mau_o: kieu = "ten"
            else: kieu = "link"
    if kieu == "link":
        if "drive.google.com" in mau and re.search(r"[-\w]{25,}", mau):
            return lambda i, t: re.sub(r"[-\w]{25,}", i, mau, count=1)
        return lambda i, t: "https://drive.google.com/uc?id=" + i
    if kieu == "id": return lambda i, t: i
    return lambda i, t: t


# ───────────────────────── xử lí một file gốc (chạy trong luồng) ─────────────────────────
def xu_ly_file(fid, ds, cac_model, ctx, dung):
    kq = {"tach": {}, "hinh": {}, "loi": None}
    if dung.is_set() or not D.con_gio():
        kq["loi"] = "hết giờ / đã dừng"; return kq
    try:
        with KHOA_DRIVE:
            tep = D.mo_tep_goc(ctx["drive"], fid)
        if not tep:
            for x in ds: kq[x["kieu"]][x["ma"]] = (None, "không mở được file gốc")
            return kq
        ds_t = [x for x in ds if x["kieu"] == "tach"]
        ds_h = [x for x in ds if x["kieu"] == "hinh"]
        if ds_t: cuu_tach(tep, ds_t, cac_model, kq["tach"])
        if ds_h: cuu_hinh(tep, ds_h, cac_model, ctx, kq["hinh"])
    except X.HetHanMuc as e:
        dung.set(); kq["loi"] = "hết hạn mức Gemini: " + str(e)[:150]
    except Exception as e:
        kq["loi"] = str(e)[:150]
    return kq


# ───────────────────────── ghi kết quả vào sheet (chỉ luồng chính) ─────────────────────────
def ghi_file(tab, c, ds, out, ngay, tk, ctx):
    ma_cot = tab.col_values(c["Mã câu"] + 1)
    dong_cua = {v.strip(): i + 1 for i, v in enumerate(ma_cot) if i > 0 and v.strip()}
    kt_cot = tab.col_values(c["Kiểm tra"] + 1)
    cap, n = [], 0
    for x in ds:
        ket = out[x["kieu"]].get(x["ma"])
        if ket is None or ket[1] is None and not ket[0]: continue       # chưa xử lí / lỗi tạm → để lượt sau, KHÔNG đánh dấu
        dong = dong_cua.get(x["ma"])
        if not dong: continue
        kt_cu = kt_cot[dong - 1] if dong - 1 < len(kt_cot) else ""
        if DAU in kt_cu: continue                                       # có chạy khác vừa cứu: bỏ qua
        col = lambda t, dh=dong: D.gspread_a1(c[t] + 1, dh)
        kq, ly = ket
        n += 1
        if x["kieu"] == "tach":
            if kq:
                nd, pa = kq
                kt = "%s | [%s %s: tách lại từ file gốc, đủ phương án – chờ duyệt lại 5 tầng] (lí do cũ: %s)" % (kt_cu, DAU, ngay, x["ly_do"])
                cap += [{"range": col("Nội dung"), "values": [[nd]]}, {"range": col("Phương án"), "values": [[pa]]},
                        {"range": col("Trạng thái duyệt"), "values": [[D.TT["CHUA"]]]}, {"range": col("Kiểm tra"), "values": [[kt[:45000]]]}]
                tk["cuu_tach"] += 1
                continue
        else:
            if kq:
                kt = "%s | [%s %s: sửa hình (%s), chờ duyệt lại 5 tầng] (lí do cũ: %s)" % (kt_cu, DAU, ngay, kq["cach"], x["ly_do"])
                if kq["nd"] != x["nd"]: cap.append({"range": col("Nội dung"), "values": [[kq["nd"]]]})
                cap += [{"range": D.gspread_a1(ctx["cot_hinh"] + 1, dong), "values": [[ctx["gia_tri_hinh"](kq["id"], kq["ten"])]]},
                        {"range": col("Trạng thái duyệt"), "values": [[D.TT["CHUA"]]]}, {"range": col("Kiểm tra"), "values": [[kt[:45000]]]}]
                tk["cuu_hinh_cat" if "cắt" in kq["cach"] else "cuu_hinh_ve"] += 1
                continue
        cap.append({"range": col("Kiểm tra"), "values": [[("%s | [%s %s: không cứu được – %s]" % (kt_cu, DAU, ngay, ly))[:45000]]]})
        tk["khong"] += 1
    if cap: tab.batch_update(cap, value_input_option="RAW")
    return n


def main():
    gc, drive, sa = X.ket_noi()
    kho = gc.open_by_key(X.ID_KHO_CHUNG)
    tab = kho.worksheet(D.TAB_NH)
    d = tab.get_all_values()
    td = d[0]
    c = {t: td.index(t) for t in ["Mã câu", "Dạng", "Nội dung", "Phương án", "Tên file", "File ID", "Kiểm tra", "Trạng thái duyệt"] if t in td}
    cac_model = X.doc_cau_hinh(kho)

    # chuẩn bị phần hình
    cot_hinh, gia_tri_hinh, hinh_bat = tim_cot_hinh(td), None, False
    if CHE_DO in ("tat_ca", "hinh"):
        if cot_hinh is None:
            print("⚠️ Không tìm thấy cột lưu hình (đặt CUU_HINH_COT) → tạm bỏ qua cứu hình.", flush=True)
        elif not THU_MUC:
            print("⚠️ Chưa đặt CUU_HINH_THU_MUC_ID (thư mục Drive chứa ảnh cứu) → tạm bỏ qua cứu hình.", flush=True)
        else:
            hinh_bat = True
            gia_tri_hinh = tao_gia_tri_hinh([r[cot_hinh] for r in d[1:] if len(r) > cot_hinh])
            print("🖼️ Cột hình: '%s'; ảnh cứu lưu vào thư mục Drive %s." % (td[cot_hinh], THU_MUC[:12]), flush=True)

    nhom = {}
    for r in d[1:]:
        r = r + [""] * (len(td) - len(r))
        if r[c["Trạng thái duyệt"]].strip() != D.TT["LOAI"]: continue
        kieu = phan_loai(r[c["Kiểm tra"]])
        if not kieu or (kieu == "hinh" and not hinh_bat): continue
        fid = r[c["File ID"]].strip() or "khong_ro"
        if fid == "khong_ro": continue
        nhom.setdefault(fid, []).append({"kieu": kieu, "ma": r[c["Mã câu"]], "dang": r[c["Dạng"]], "nd": r[c["Nội dung"]], "pa": r[c["Phương án"]],
                                         "vi_tri": (re.search(r"\(câu\s*([^)]*)\)", r[c["Tên file"]]) or [None, ""])[1],
                                         "ly_do": r[c["Kiểm tra"]].rsplit(D.DAU_MAY, 1)[-1][:150]})
    tong_t = sum(1 for v in nhom.values() for x in v if x["kieu"] == "tach")
    tong_h = sum(1 for v in nhom.values() for x in v if x["kieu"] == "hinh")
    print("Có %d câu Loại do lỗi tách đề + %d câu Loại do lỗi hình/đồ thị, trong %d file." % (tong_t, tong_h, len(nhom)), flush=True)

    # file nhiều câu cần cứu xử lí trước: 1 lần mở file gốc cứu được nhiều câu nhất
    lenh, con = [], TOI_DA
    for fid, ds in sorted(nhom.items(), key=lambda kv: -len(kv[1])):
        if con <= 0: break
        lenh.append((fid, ds[:con])); con -= len(lenh[-1][1])

    ngay = dt.datetime.now(X.TZ).strftime("%d/%m")
    tk = {"cuu_tach": 0, "cuu_hinh_cat": 0, "cuu_hinh_ve": 0, "khong": 0}
    ctx = {"drive": drive, "cot_hinh": cot_hinh, "gia_tri_hinh": gia_tri_hinh}
    dung = threading.Event()
    with cf.ThreadPoolExecutor(max_workers=SONG_SONG) as ex:
        fs = {ex.submit(xu_ly_file, fid, ds, cac_model, ctx, dung): (fid, ds) for fid, ds in lenh}
        for f in cf.as_completed(fs):
            fid, ds = fs[f]
            try:
                out = f.result()
                n = ghi_file(tab, c, ds, out, ngay, tk, ctx)
                print("📄 File %s: %d/%d câu xử lí%s" % (fid[:12], n, len(ds), (" – " + out["loi"]) if out["loi"] else ""), flush=True)
            except Exception as e:
                print("⚠️ File %s lỗi, để lượt sau: %s" % (fid[:12], str(e)[:150]), flush=True)
    if dung.is_set(): print("⏸️ Hết hạn mức Gemini – đã dừng, phần còn lại để lượt sau.", flush=True)
    print("📊 Cứu Loại: %d câu tách đề + %d câu hình (cắt từ file gốc) + %d câu hình (vẽ lại) trả về 'Chưa duyệt' (sẽ qua 5 tầng); "
          "%d câu không cứu được." % (tk["cuu_tach"], tk["cuu_hinh_cat"], tk["cuu_hinh_ve"], tk["khong"]))
    if Q: Q.ghi_sheet(kho)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if Q: Q.ghi_sheet()
        raise
