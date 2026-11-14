"""
tron_de_docx.py – TRỘN ĐỀ TRỰC TIẾP TRONG FILE WORD (.docx). Bản Python của taoMotMaDe (ChucNang.gs), giữ nguyên hình, bảng,
công thức Word (OMML) và mọi chỉnh sửa tay của thầy vì chỉ DI CHUYỂN các đoạn có sẵn, không dựng lại đề.

Quy ước hoán vị (giống taoBoHoanViTD):
  thuTu[p][k] = g : vị trí mới k (0-based) của Phần p là câu gốc g.
  pa[g][j]    = i : với câu gốc g (Phần I), phương án mới ở vị trí j là phương án gốc i.
  y[g][j]     = i : với câu gốc g (Phần II), ý mới ở vị trí j là ý gốc i.
Cấu trúc đề nhận ra bằng chữ (giống phanTichCauTrucDe): dòng "PHẦN I..IV", "Câu n:", phương án bắt đầu "A." … "D.",
ý Phần II bắt đầu "a)" … "d)", sau dòng "Họ, tên thí sinh"; dừng ở bảng đáp án / dòng "HẾT" / "ĐÁP ÁN".
"""
import copy
import re

from docx.oxml.ns import qn

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
NHAN, NHAN_Y = "ABCD", "abcd"

RE_KHONG_TRON_PA = re.compile(
    r"(tất\s*cả|cả\s+(?:hai|ba|bốn|[A-D])(?![A-Za-zÀ-ỹ])|đáp\s*án|phương\s*án\s+[A-D](?![A-Za-zÀ-ỹ])"
    r"|(?:^|[^A-Za-zÀ-ỹ])[A-D]\s*(?:và|hoặc|,)\s*[A-D](?![A-Za-zÀ-ỹ])|các\s+(?:đáp\s*án|phương\s*án)\s+trên)", re.I)


# ============================================================ tiện ích văn bản
def _ts_cua_doan(p):
    """Các phần tử w:t thuộc dòng chữ của đoạn (bỏ chữ trong khung văn bản/hình)."""
    ra = []
    for t in p.iter(W + "t"):
        a, trong = t.getparent(), False
        while a is not None and a is not p:
            if a.tag in (W + "txbxContent", W + "drawing", W + "pict"):
                trong = True
                break
            a = a.getparent()
        if not trong:
            ra.append(t)
    return ra


def text_doan(p):
    return "".join(t.text or "" for t in _ts_cua_doan(p))


def text_phan_tu(el):
    """Chữ của một phần tử khối (đoạn hoặc bảng), gồm cả chữ trong công thức."""
    return "".join(x for x in el.itertext() if x)


def text_ke_ca_cong_thuc(el):
    return "".join((t.text or "") for t in el.iter() if t.tag in (W + "t", M + "t"))


def sua_trong_doan(p, mau, fn):
    """Với mỗi chỗ khớp `mau` trong chữ của đoạn, fn(m) trả (bat_dau, ket_thuc, chu_moi) hoặc None. Làm từ cuối lên đầu."""
    ts = _ts_cua_doan(p)
    if not ts:
        return 0
    s = "".join(t.text or "" for t in ts)
    cac = [x for x in (fn(m) for m in mau.finditer(s)) if x]
    for a, b, moi in reversed(cac):
        _thay_khoang(ts, a, b, moi)
    return len(cac)


def _thay_khoang(ts, a, b, moi):
    """Thay chữ ở khoảng [a, b) (a == b là chèn) của chuỗi nối các w:t; giữ định dạng của run đầu tiên bị chạm."""
    pos, da_dat = 0, False
    for t in ts:
        tx = t.text or ""
        lo, hi = pos, pos + len(tx)
        pos = hi
        if a == b:                                   # chèn
            if a <= hi:
                t.text = tx[:a - lo] + moi + tx[a - lo:]
                t.set(XML_SPACE, "preserve")
                return
            continue
        if hi <= a or lo >= b:
            continue
        x, y = max(a, lo) - lo, min(b, hi) - lo
        if not da_dat:
            t.text = tx[:x] + moi + tx[y:]
            da_dat = True
        else:
            t.text = tx[:x] + tx[y:]
        t.set(XML_SPACE, "preserve")


# ============================================================ cấu trúc đề
def danh_sach_khoi(body):
    return [e for e in body if e.tag in (W + "p", W + "tbl")]


def la_bang_dap_an(el):
    if el.tag != W + "tbl":
        return False
    hang = el.findall(W + "tr")
    if not hang:
        return False
    o = hang[0].findall(W + "tc")
    t = text_phan_tu(hang[0]).lower()
    if len(o) == 2 and ("câu hỏi" in t or "đáp án" in t):
        return True
    return len(o) == 3 and "nội dung" in t and "điểm" in t


def la_doan_trong(el):
    if el.tag != W + "p":
        return False
    if text_doan(el).strip():
        return False
    for x in el.iter():
        if x.tag in (W + "drawing", W + "pict", W + "object", M + "oMath", M + "oMathPara"):
            return False
    return True


def phan_tich_cau_truc(els):
    """{1:[{start,end,so}],…} – mỗi câu là đoạn chỉ số [start, end) trong danh sách khối `els`."""
    n, bat_dau = len(els), 0
    for i, e in enumerate(els):
        if "Họ, tên thí sinh" in text_phan_tu(e):
            bat_dau = i + 1
            break
    kq, phan, cau, ket_thuc = {1: [], 2: [], 3: [], 4: []}, 0, None, n

    def dong(end):
        nonlocal cau
        if cau:
            cau["end"] = end
            kq[phan].append(cau)
            cau = None

    for i in range(bat_dau, n):
        el = els[i]
        if la_bang_dap_an(el):
            ket_thuc = i
            break
        if el.tag != W + "p":
            continue
        t = text_doan(el).strip()
        if len(t) < 40 and re.match(r"^[.…\s\-–—―]*Hết", t, re.I):
            ket_thuc = i
            break
        if re.match(r"^(ĐÁP\s*ÁN|HƯỚNG\s*DẪN\s*CHẤM)", t, re.I):
            ket_thuc = i
            break
        m = re.match(r"^PHẦN\s*(IV|III|II|I)(?![IVX])", t.upper())
        if m:
            dong(i)
            phan = {"I": 1, "II": 2, "III": 3, "IV": 4}[m.group(1)]
            continue
        mc = re.match(r"^Câu\s*(\d+)\s*[:.]", t, re.I) if phan else None
        if mc:
            dong(i)
            cau = {"start": i, "so": int(mc.group(1))}
    dong(ket_thuc)
    for p in (1, 2, 3, 4):
        ds = kq[p]
        if ds:
            c = ds[-1]
            while c["end"] - 1 > c["start"] and la_doan_trong(els[c["end"] - 1]):
                c["end"] -= 1
    return kq


def cau_truc_hien_tai(body):
    els = danh_sach_khoi(body)
    return els, phan_tich_cau_truc(els)


# ============================================================ bảng đáp án
def tim_bang_dap_an(els):
    bang = None
    for e in els:
        if e.tag == W + "tbl":
            h = e.findall(W + "tr")
            if h:
                o = h[0].findall(W + "tc")
                t = text_phan_tu(h[0]).lower()
                if len(o) == 2 and ("câu hỏi" in t or "đáp án" in t):
                    bang = e
    return bang


def _duyet_bang(bang, fn):
    phan = ""
    for hang in bang.findall(W + "tr"):
        o = hang.findall(W + "tc")
        if not o:
            continue
        c0 = text_phan_tu(o[0]).strip().upper()
        if "PHẦN III" in c0:
            phan = "III"
            continue
        if "PHẦN II" in c0:
            phan = "II"
            continue
        if "PHẦN I" in c0:
            phan = "I"
            continue
        m = re.match(r"\d+", c0)
        if phan and m and len(o) >= 2:
            fn({"I": 1, "II": 2, "III": 3}[phan], int(m.group(0)), o[1])


def doc_dap_an_goc(els):
    kq = {1: {}, 2: {}, 3: {}}
    bang = tim_bang_dap_an(els)
    if bang is not None:
        _duyet_bang(bang, lambda p, so, o: kq[p].__setitem__(so, text_phan_tu(o).strip()))
    return kq


def _dat_text_o(tc, gia_tri):
    ps = tc.findall(W + "p")
    if not ps:
        return
    p = ps[0]
    for thua in ps[1:]:
        tc.remove(thua)
    r_mau = p.find(W + "r")
    rpr = copy.deepcopy(r_mau.find(W + "rPr")) if r_mau is not None and r_mau.find(W + "rPr") is not None else None
    for c in list(p):
        if c.tag != W + "pPr":
            p.remove(c)
    r = p.makeelement(W + "r", {})
    if rpr is not None:
        r.append(rpr)
    t = r.makeelement(W + "t", {})
    t.text = gia_tri
    t.set(XML_SPACE, "preserve")
    r.append(t)
    p.append(r)


def ghi_dap_an_vao_bang(els, dap_an):
    """dap_an = {'p1':[…], 'p2':[…], 'p3':[…]} theo thứ tự câu MỚI. Trả về True nếu có bảng."""
    bang = tim_bang_dap_an(els)
    if bang is None:
        return False

    def ghi(p, so, tc):
        mang = dap_an.get("p%d" % p) or []
        gt = mang[so - 1] if 0 < so <= len(mang) else None
        if gt not in (None, ""):
            _dat_text_o(tc, str(gt))
    _duyet_bang(bang, ghi)
    return True


# ============================================================ sắp lại câu / đánh lại số
def sap_lai_cau(body, els, cac_cau, hoan_vi):
    """Đặt các câu theo thứ tự mới (hoan_vi[k] = chỉ số câu gốc ở vị trí k). Các câu liền nhau nên chỉ cần đổi chỗ."""
    if not cac_cau or len(hoan_vi) != len(cac_cau):
        raise ValueError("hoán vị không khớp số câu")
    a, b = cac_cau[0]["start"], cac_cau[-1]["end"]
    khoi = [els[c["start"]:c["end"]] for c in cac_cau]
    cu = els[a:b]
    neo = cu[0].getprevious()
    if neo is None:
        raise ValueError("không có mốc để chèn")
    for e in cu:
        body.remove(e)
    for g in hoan_vi:
        for e in khoi[g]:
            neo.addnext(e)
            neo = e


def danh_lai_so_cau(p, so):
    sua_trong_doan(p, re.compile(r"^(\s*Câu\s*)(\d+)", re.I), lambda m: (m.start(2), m.end(2), str(so)))


def _can_giua(p):
    jc = p.find(W + "pPr/" + W + "jc")
    return jc is not None and jc.get(W + "val") == "center"


def danh_lai_so_hinh(els, ct):
    dem = {}
    mau_chu_thich = re.compile(r"^\s*(Hình|Bảng)\s*(\d+)", re.I)
    mau_thay = re.compile(r"(Hình|hình|HÌNH|Bảng|bảng|BẢNG)(\s*)(\d+)")
    for p in (1, 2, 3, 4):
        for c in ct[p]:
            anh_xa = {}
            for i in range(c["start"], c["end"]):
                el = els[i]
                if el.tag != W + "p" or not _can_giua(el):
                    continue
                m = mau_chu_thich.match(text_doan(el))
                if not m:
                    continue
                khoa = m.group(1).lower() + "|" + m.group(2)
                if khoa in anh_xa:
                    continue
                dem[m.group(1).lower()] = dem.get(m.group(1).lower(), 0) + 1
                anh_xa[khoa] = str(dem[m.group(1).lower()])
            if not anh_xa:
                continue

            def thay(m, anh_xa=anh_xa):
                moi = anh_xa.get(m.group(1).lower() + "|" + m.group(3))
                return None if (not moi or moi == m.group(3)) else (m.start(3), m.end(3), moi)
            for i in range(c["start"], c["end"]):
                if els[i].tag == W + "p":
                    sua_trong_doan(els[i], mau_thay, thay)


# ============================================================ trộn phương án Phần I
def _chu_cua_run(r):
    return "".join(t.text or "" for t in r.findall(W + "t"))


def _la_run_tab(r):
    return r.tag == W + "r" and r.find(W + "tab") is not None and not r.findall(W + "t") and \
        all(c.tag in (W + "rPr", W + "tab") for c in r)


def _tach_phuong_an(cac_doan):
    """→ (danh sách đoạn, danh sách khe [{doan, nhan(run), noi_dung[], tab[]}]) hoặc None nếu không nhận ra đúng A,B,C,D."""
    khe, mong_doi = [], 0
    for p in cac_doan:
        hien_tai = None
        for c in list(p):
            if c.tag == W + "pPr":
                continue
            if c.tag == W + "r" and mong_doi < 4:
                tx = _chu_cua_run(c)
                m = re.match(r"^(\s*)%s\.(\s*)(.*)$" % NHAN[mong_doi], tx, re.S)
                if m and c.find(W + "drawing") is None:
                    if m.group(3):                                  # nhãn và nội dung chung một run → tách đôi
                        moi = copy.deepcopy(c)
                        for t in c.findall(W + "t"):
                            c.remove(t)
                        t1 = c.makeelement(W + "t", {})
                        t1.text = m.group(1) + NHAN[mong_doi] + ". "
                        t1.set(XML_SPACE, "preserve")
                        c.append(t1)
                        for t in moi.findall(W + "t"):
                            moi.remove(t)
                        t2 = moi.makeelement(W + "t", {})
                        t2.text = m.group(3)
                        t2.set(XML_SPACE, "preserve")
                        moi.append(t2)
                        c.addnext(moi)
                        hien_tai = {"doan": p, "nhan": c, "noi_dung": [moi], "tab": []}
                        khe.append(hien_tai)
                        mong_doi += 1
                        # phần còn lại của đoạn tiếp tục xử lí, bắt đầu từ `moi`
                        continue
                    hien_tai = {"doan": p, "nhan": c, "noi_dung": [], "tab": []}
                    khe.append(hien_tai)
                    mong_doi += 1
                    continue
            if hien_tai is None:
                if c.tag == W + "r" and not _chu_cua_run(c).strip() and not any(x.tag in (W + "drawing",) for x in c.iter()):
                    continue
                return None                                        # có chữ trước nhãn đầu của đoạn → không chắc → không trộn
            if _la_run_tab(c):
                hien_tai["tab"].append(c)
            else:
                if hien_tai["tab"]:                                 # chữ sau tab mà chưa có nhãn mới → bất thường
                    return None
                hien_tai["noi_dung"].append(c)
    if mong_doi != 4:
        return None
    return khe


def tron_phuong_an(els, cau, q):
    """Trộn phương án A–D của một câu Phần I. q[k] = phương án gốc ở vị trí mới k. Trả về True nếu đã trộn."""
    if all(v == i for i, v in enumerate(q)):
        return False
    ds = []
    for i in range(cau["start"] + 1, cau["end"]):
        el = els[i]
        if el.tag == W + "p" and re.match(r"^\s*[A-D]\.", text_doan(el)):
            ds.append(el)
        elif ds:
            break
    if not ds:
        return False
    # làm trên bản sao để nếu không chắc thì không đụng đề
    ban_sao = [copy.deepcopy(p) for p in ds]
    khe = _tach_phuong_an(ban_sao)
    if not khe or "".join(re.match(r"\s*([A-D])", _chu_cua_run(k["nhan"])).group(1) for k in khe) != NHAN:
        return False
    chu = [text_ke_ca_cong_thuc(_gia_doan(k)) for k in khe]
    if RE_KHONG_TRON_PA.search(" | ".join(chu)):
        return False
    # dựng lại theo từng đoạn, giữ nguyên số phương án mỗi dòng và vị trí tab
    nhom = {}
    for k in khe:
        nhom.setdefault(id(k["doan"]), []).append(k)
    cac_khe_cu = [{"nhan": k["nhan"], "noi_dung": k["noi_dung"], "tab": k["tab"]} for k in khe]
    vt = 0
    for p in ban_sao:
        ks = nhom.get(id(p), [])
        for c in list(p):
            if c.tag != W + "pPr":
                p.remove(c)
        for j, k in enumerate(ks):
            moi_chu = NHAN[vt]
            goc = cac_khe_cu[q[vt]]
            nhan = copy.deepcopy(goc["nhan"])
            for t in nhan.findall(W + "t"):
                t.text = (re.match(r"^\s*", t.text or "").group(0)) + moi_chu + ". "
                t.set(XML_SPACE, "preserve")
                break
            p.append(nhan)
            for x in goc["noi_dung"]:
                p.append(copy.deepcopy(x))
            if j < len(ks) - 1:
                for x in k["tab"]:                                 # tab của KHE (vị trí), không theo nội dung
                    p.append(copy.deepcopy(x))
            vt += 1
    for goc, moi in zip(ds, ban_sao):
        goc.getparent().replace(goc, moi)
    return True


def _gia_doan(k):
    """Đoạn giả chỉ để đọc chữ của một phương án (không gồm nhãn)."""
    p = k["doan"].makeelement(W + "p", {})
    for x in k["noi_dung"]:
        p.append(copy.deepcopy(x))
    return p


# ============================================================ trộn ý a–d Phần II
def tron_y_phan_ii(els, cau, q):
    if all(v == i for i, v in enumerate(q)):
        return False
    ds = []
    for i in range(cau["start"] + 1, cau["end"]):
        el = els[i]
        if el.tag == W + "p" and re.match(r"^\s*[a-d]\)", text_doan(el)):
            ds.append(el)
        elif ds:
            break
    if len(ds) != 4 or "".join(re.match(r"^\s*([a-d])\)", text_doan(e)).group(1) for e in ds) != NHAN_Y:
        return False
    ban_sao = [copy.deepcopy(e) for e in ds]
    for k, g in enumerate(q):
        moi = copy.deepcopy(ban_sao[g])
        sua_trong_doan(moi, re.compile(r"^(\s*)([a-d])\)"), lambda m, k=k: (m.start(2), m.end(2), NHAN_Y[k]))
        ds[0].addprevious(moi)
    for e in ds:
        e.getparent().remove(e)
    return True


# ============================================================ mã đề
def ghi_ma_de(doc, body, ma):
    """Thay số (hoặc dấu chấm chờ điền) sau chữ "Mã đề" bằng mã mới ở đầu/chân trang (mọi chỗ) và thân đề (chỗ đầu tiên, tính cả bảng).
    Không thấy chữ "Mã đề" ở đâu → thêm dòng "Mã đề: xxx" căn phải ngay trên dòng "Họ, tên thí sinh"."""
    mau1 = re.compile(r"(Mã\s*đề|MÃ\s*ĐỀ|Mã\s*Đề)([\s:]*(?:thi)?[\s:]*)(\d{1,6}|[.…_]{2,})", re.I)
    mau2 = re.compile(r"(Mã\s*đề|MÃ\s*ĐỀ|Mã\s*Đề)(\s*(?:thi)?\s*:\s*)?")

    def xu_ly(p):
        n = sua_trong_doan(p, mau1, lambda m: (m.start(3), m.end(3), ma))
        if n:
            return n
        return sua_trong_doan(p, mau2, lambda m: (m.end(), m.end(), ("" if m.group(2) else ": ") + ma))

    da = 0
    vung, thay_roi = [], set()
    for s in doc.sections:
        for hf in (s.header, s.footer, s.first_page_header, s.first_page_footer, s.even_page_header, s.even_page_footer):
            try:
                if hf.is_linked_to_previous:
                    continue
                el = hf._element
            except Exception:
                continue
            if id(el) in thay_roi:
                continue
            thay_roi.add(id(el))
            vung.append(el)
    for el in vung:
        for p in el.iter(W + "p"):
            da += 1 if xu_ly(p) else 0
    trong_than = 0
    for p in body.iter(W + "p"):
        if re.search(r"Mã\s*đề|MÃ\s*ĐỀ|Mã\s*Đề", text_doan(p)):
            if xu_ly(p):
                trong_than += 1
                break
    if da or trong_than:
        return True
    els = danh_sach_khoi(body)
    chi_so = 0
    for i, e in enumerate(els):
        if "Họ, tên thí sinh" in text_phan_tu(e):
            chi_so = i
            break
    p = els[0].makeelement(W + "p", {})
    ppr = p.makeelement(W + "pPr", {})
    jc = ppr.makeelement(W + "jc", {W + "val": "right"})
    ppr.append(jc)
    p.append(ppr)
    r = p.makeelement(W + "r", {})
    rpr = r.makeelement(W + "rPr", {})
    rpr.append(rpr.makeelement(W + "b", {}))
    r.append(rpr)
    t = r.makeelement(W + "t", {})
    t.text = "Mã đề: " + ma
    r.append(t)
    p.append(r)
    els[chi_so].addprevious(p)
    return True
