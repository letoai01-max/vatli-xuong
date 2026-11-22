"""
cuu_nghi_van.py – CỨU CÂU "CẦN NGƯỜI XEM" TỰ ĐỘNG (không cần giáo viên). Dùng bởi duyet_cau.py.   [22/11/2026]

Mỗi lí do khiến câu phải chờ giáo viên có một cách xử lí bằng máy riêng:
  1. Công thức $…$ không đóng mở đủ  → sua_dola(): tự cân lại bằng luật; không cân được thì giữ nghi vấn.
  2. Chưa gắn / sai mã YCCĐ          → chon_yccd(): model nhẹ chọn lại trong các mã cùng bài (cùng lớp); chỉ nhận khi "cao".
  3. Có từ khoá chương trình cũ       → xử lí trong duyet_cau.quyet_dinh: tầng 2 đã trả ngoai_ct2018 = false thì bỏ cờ.
  4. Câu có hình, máy chưa thống nhất → tang6_hinh(): gửi ẢNH THẬT cho model đa phương thức tự nhìn hình và giải (không cho xem
                                        đáp án), rồi bo_phieu(): hình + ít nhất một bằng chứng khác khớp và nhiều phiếu hơn mọi
                                        đáp án khác thì duyệt; không thì để nguyên (rồi theo XEM_CON_LAI: xem | loai).
Không import duyet_cau (tránh nạp hai lần khi chạy bằng trung_tam.py); các hàm so đáp án được truyền vào.
"""
import base64, json, os, re

try:
    import requests
except Exception:                      # thiếu requests: chỉ mất khả năng tải ảnh qua http, phần còn lại vẫn chạy
    requests = None

# Lí do "bất đồng" mà nhìn hình / bỏ phiếu có thể giải quyết. Lí do khác (số liệu lệch với đề gốc, đơn vị khác thứ nguyên…) giữ nguyên.
LI_DO_GIAI_DUOC = (
    "Thiếu dữ kiện khi không có hình gốc",
    "Câu nhắc tới hình nhưng không có mô tả hình",
    "HDC gốc",
    "Đáp số HDC",
    "Chỉ có HDC",
    "Không có HDC; hai lời giải",
    "Không có HDC; chỉ kiểm được",
    "Máy giải không chắc chắn",
    "Máy giải thấy",
    'Đáp án "',
)


def li_do_giai_duoc(ly_do):
    return any(str(ly_do).startswith(p) for p in LI_DO_GIAI_DUOC)


# ============================== 1. SỬA DẤU $ ==============================
_RE_TOAN = re.compile(r"[\\^_=+\-*/<>]|\d")
_RE_CHU_VIET = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.I)


def dem_dola(s):
    return len(re.findall(r"(?<!\\)\$", str(s or "")))


def _giong_toan(doan):
    """Đoạn ngắn trông như công thức (có kí hiệu toán, không có chữ tiếng Việt, không có dấu chấm câu cuối câu)."""
    d = str(doan or "").strip()
    return 0 < len(d) <= 60 and bool(_RE_TOAN.search(d)) and not _RE_CHU_VIET.search(d) and not re.search(r"[.?!]\s", d)


def sua_dola(s):
    """Trả (chuỗi_đã_sửa, True) nếu cân được số dấu $; (chuỗi_gốc, False) nếu lẻ mà không dám sửa; (chuỗi_gốc, True) nếu vốn đã chẵn.
    Chỉ làm hai việc an toàn: đóng $ ở cuối khi đoạn mở cuối cùng trông như công thức ngắn, hoặc mở $ ở đầu khi đoạn trước $ đầu tiên trông như công thức ngắn."""
    s = str(s or "")
    if dem_dola(s) % 2 == 0:
        return s, True
    vt = [m.start() for m in re.finditer(r"(?<!\\)\$", s)]
    cuoi = s[vt[-1] + 1:]
    if _giong_toan(cuoi):
        moi = s.rstrip() + "$"
        if dem_dola(moi) % 2 == 0:
            return moi, True
    dau = s[:vt[0]]
    if _giong_toan(dau):
        moi = "$" + s.lstrip()
        if dem_dola(moi) % 2 == 0:
            return moi, True
    return s, False


# ============================== 2. BỎ PHIẾU ==============================
def bo_phieu(loai, phieu, khop, sai_so, bat_buoc="hinh", toi_thieu=2, cach_biet=1):
    """phieu: {nguồn: đáp án đã chuẩn hoá (rỗng = không có phiếu)}. Trả (đáp án thắng, [nguồn đồng ý]) hoặc None.
    Điều kiện thắng: ≥ toi_thieu phiếu, hơn nhóm đứng sau ít nhất cach_biet phiếu, và (nếu có bat_buoc) nhóm thắng có phiếu của nguồn đó."""
    nhom = []
    for nguon, da in phieu.items():
        if not da:
            continue
        for g in nhom:
            if khop(loai, da, g[0], sai_so):
                g[1].append(nguon)
                break
        else:
            nhom.append([da, [nguon]])
    if not nhom:
        return None
    nhom.sort(key=lambda g: -len(g[1]))
    top = nhom[0]
    if len(top[1]) >= toi_thieu and (len(nhom) == 1 or len(top[1]) >= len(nhom[1][1]) + cach_biet) and (not bat_buoc or bat_buoc in top[1]):
        return top[0], top[1]
    return None


# ============================== 3. TẦNG 6: NHÌN HÌNH THẬT ==============================
def tach_link_anh(s):
    return [u for u in re.split(r"[,;\s]+", str(s or "").strip()) if u][:4]


def tai_anh(drive, u, tai_ve):
    """Trả (bytes, mime) hoặc None. images/… trong kho đã checkout; link Drive qua tai_ve; link http khác tải thẳng."""
    try:
        m = re.search(r"/file/d/([\w-]{20,})", u) or re.search(r"[?&]id=([\w-]{20,})", u) or re.search(r"googleusercontent\.com/d/([\w-]{20,})", u)
        if m and drive:
            b = tai_ve(drive, m.group(1))
        else:
            g = re.match(r"^https?://raw\.githubusercontent\.com/[^/]+/[^/]+/[^/]+/(.+)$", u, re.I)
            duong = g.group(1) if g else ("" if re.match(r"^https?://", u, re.I) else re.sub(r"^\.?/", "", u))
            if duong and os.path.isfile(duong):
                with open(duong, "rb") as f:
                    b = f.read()
            elif requests and re.match(r"^https?://", u, re.I):
                r = requests.get(u, timeout=60)
                r.raise_for_status()
                b = r.content
            else:
                return None
        low = u.lower()
        mime = "image/jpeg" if re.search(r"\.jpe?g($|\?)", low) else "image/webp" if re.search(r"\.webp($|\?)", low) else "image/png"
        return (b, mime) if b and len(b) > 200 else None
    except Exception as e:
        print("  Không tải được ảnh %s: %s" % (u[:60], str(e)[:80]), flush=True)
        return None


def _json_cuoi(text):
    ds = re.findall(r"```(?:json)?\s*([\[{][\s\S]*?[\]}])\s*```", text or "")
    for t in reversed(ds):
        try:
            return json.loads(t)
        except ValueError:
            continue
    m = re.search(r"(\{[\s\S]*\})", text or "")
    if m:
        try:
            return json.loads(m.group(1))
        except ValueError:
            pass
    return None


def giai_co_hinh(x, anh, goi_gemini, cac_model):
    """Một câu + ảnh → dict {phuong_an_dung, y_ds, dap_so, don_vi, tu_tin} hoặc None. KHÔNG cho xem đáp án."""
    loi = ("Bạn là học sinh giỏi Vật lí. Đề bài kèm HÌNH ảnh đính kèm (hình thuộc về câu này). Hãy NHÌN HÌNH, đọc số liệu / đồ thị / sơ đồ, "
           "rồi GIẢI ĐỘC LẬP. Dùng công cụ chạy code Python cho mọi phép tính số. Nhiều lựa chọn: xét từng phương án A–D, ghi mọi phương án đúng. "
           "Đúng/sai: xét từng ý a–d. Trả lời ngắn / tự luận: đáp số cuối + đơn vị SI. Nếu hình không đủ để giải hoặc không khớp đề, "
           'đặt "tu_tin": "thấp".\nCUỐI CÙNG trả MỘT khối ```json``` dạng: {"phuong_an_dung": ["B"], "y_ds": {"a": "Đ", "b": "S", "c": "Đ", "d": "S"}, '
           '"dap_so": 2.02, "don_vi": "s", "tu_tin": "cao|vừa|thấp"} (bỏ trường không dùng).\n\nĐỀ:\n'
           + str(x["noi_dung"])[:1800] + "\n\nPHƯƠNG ÁN:\n" + str(x["phuong_an"])[:900])
    parts = [{"inline_data": {"mime_type": m, "data": base64.b64encode(b).decode()}} for b, m in anh] + [{"text": loi}]
    payload = {"contents": [{"role": "user", "parts": parts}], "tools": [{"code_execution": {}}],
               "generationConfig": {"temperature": 0.2, "maxOutputTokens": 20000}}
    ds_model = sorted(cac_model, key=lambda m: "lite" in m)           # model thường trước, lite sau
    data, _ = goi_gemini(payload, ds_model)
    text = "".join(p.get("text", "") for p in (data.get("candidates") or [{}])[0].get("content", {}).get("parts", []))
    j = _json_cuoi(text)
    return j if isinstance(j, dict) else None


# ============================== 4. GÁN LẠI MÃ YCCĐ ==============================
def ung_vien_yccd(yccd, ma_bai, lop, toi_da=60):
    """Các mã YCCĐ để model chọn: cùng bài nếu biết; không thì cùng lớp; quá nhiều thì bỏ (trả [])."""
    ma_bai = str(ma_bai or "").strip()
    ks = [k for k in yccd if ma_bai and k.startswith(ma_bai + "-")]
    if not ks and str(lop or "").strip():
        l = re.sub(r"\D", "", str(lop))
        ks = [k for k in yccd if len(k) >= 4 and k[2:4] == l]
    return ks if 0 < len(ks) <= toi_da else []


def chon_yccd(ds, yccd, goi_gemini, cac_model):
    """ds: [{ma, noi_dung, phuong_an, ma_bai, lop}] → {mã câu: mã YCCĐ} chỉ gồm câu model chọn được với độ tin cậy "cao"."""
    mon = []
    for x in ds:
        uv = ung_vien_yccd(yccd, x.get("ma_bai"), x.get("lop"))
        if uv:
            mon.append({"ma_cau": x["ma"], "noi_dung": str(x["noi_dung"])[:700], "phuong_an": str(x["phuong_an"])[:300],
                        "cac_ma": [k + ": " + str(yccd[k])[:150] for k in uv]})
    if not mon:
        return {}
    loi = ("Với MỖI câu Vật lí THPT dưới đây, chọn ĐÚNG MỘT mã yêu cầu cần đạt trong 'cac_ma' mà câu kiểm tra trực tiếp. "
           "Chỉ chọn khi chắc chắn (tu_tin = cao); không có mã nào khớp thì ma = \"\".\nCÁC CÂU:\n" + json.dumps(mon, ensure_ascii=False))
    schema = {"type": "OBJECT", "properties": {"ket_qua": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
        "ma_cau": {"type": "STRING"}, "ma": {"type": "STRING"}, "tu_tin": {"type": "STRING"}}, "required": ["ma_cau", "ma", "tu_tin"]}}},
        "required": ["ket_qua"]}
    nhe = [m for m in cac_model if "lite" in m] + [m for m in cac_model if "lite" not in m]
    data, _ = goi_gemini({"contents": [{"role": "user", "parts": [{"text": loi}]}],
                          "generationConfig": {"responseMimeType": "application/json", "responseSchema": schema,
                                               "temperature": 0, "maxOutputTokens": 8000}}, nhe)
    j = json.loads("".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]))
    kq = {}
    for g in j.get("ket_qua", []):
        ma = str(g.get("ma", "")).strip().upper()
        if ma in yccd and str(g.get("tu_tin", "")).strip().lower().startswith("cao"):
            kq[str(g.get("ma_cau"))] = ma
    return kq
