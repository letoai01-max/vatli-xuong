"""
chuan_de.py – CHUẨN HOÁ ĐỀ THI (JSON phan1..phan4) THEO MỘT QUY ƯỚC DUY NHẤT: công thức trong $…$ / $$…$$.

Làm ba việc, không gọi AI:
  1. chuan_hoa_de(de): làm sạch từng trường chữ bằng latex_chuan.chuan_hoa_latex, đưa đáp án Phần I–IV và hinhAnh
     về dạng chuẩn (cùng dạng kiemTraDeThi / chuanHoaHinhAnh của Mã.gs).
  2. kiem_tra_latex(de): liệt kê lỗi công thức (thiếu/thừa $, lệnh \\ ngoài $) – đưa vào vòng "soạn lại câu".
  3. tu_dinh_dang_cu(de_cu): đổi đề theo mẫu cũ của tao_de.py (phan_I_trac_nghiem_…) sang phan1..phan4.

Đề chuẩn:  phan1[{cauHoi,A,B,C,D,dapAn:"B"}] · phan2[{cauHoi,A,B,C,D,dapAn:"a) Đ, b) S, c) Đ, d) S"}]
           phan3[{cauHoi,dapAn:"12.5"}] · phan4[{cauHoi,dapAn:"- bước…\\n=> Đáp số: …"}]  (+ hinhAnh, maChiBao, loiGiai tuỳ chọn)
"""
import copy
import re

import latex_chuan as L

CAC_Y = ("A", "B", "C", "D")
RE_TOAN = re.compile(r"\$\$[\s\S]*?\$\$|\$[^$\n]+?\$")
RE_LENH_TRAN = re.compile(r"\\[A-Za-z]{2,}|[\^_]\{")
RE_UNICODE_TOAN = re.compile("[αβγδεθλμπρστφωΔΩΦΣΘΛ≈≤≥≠±×∞→⇒²³⁻°]")


def _s(v):
    return "" if v is None else str(v)


RE_MICRO_TEXT = re.compile(r"\\text\{(\s*)[μµ]([A-Za-z]+)\}")
RE_MICRO = re.compile(r"[μµ](?=[A-Za-z])")


def _sua_micro_trong_toan(m):
    """latex_chuan đổi μ → \\mu (không có khoảng trắng) nên μF thành \\muF – lệnh không tồn tại, pandoc không dựng được phương trình.
    Đưa về \\mu\\text{F} trước khi chuẩn hoá (μ ở ngoài công thức giữ nguyên chữ Unicode)."""
    t = RE_MICRO_TEXT.sub(lambda g: "\\,\\mu\\text{" + g.group(2) + "}", m.group(0))
    return RE_MICRO.sub("\\mu ", t).replace("\\mu \\text", "\\mu\\text") if RE_MICRO.search(t) else t


def tien_xu_ly(s):
    return RE_TOAN.sub(_sua_micro_trong_toan, _s(s))


# ---------------------------------------------------------------- đáp án
def chuan_dap_an_p1(v):
    m = re.search(r"[ABCD]", _s(v).upper())
    return m.group(0) if m else ""


def chuan_dap_an_p2(v):
    """Nhận: chuỗi "a) Đ, b) S…", "a-Đúng…", "ĐSĐS", dict {"a":True…} → "a) Đ, b) S, c) Đ, d) S" (thiếu ý → để lỗi cho luật)."""
    kq = {}
    if isinstance(v, dict):
        for k, x in v.items():
            k = _s(k).strip().lower()[:1]
            if k in "abcd" and k:
                kq[k] = "Đ" if (x is True or re.match(r"^\s*(đ|đúng|true|d)\b", _s(x), re.I)) else "S"
    else:
        s = _s(v)
        for g in re.finditer(r"([a-dA-D])\s*[).:\-–]\s*(Đúng|Sai|Đ|S|True|False)(?![A-Za-zÀ-ỹ])", s):
            kq[g.group(1).lower()] = "Đ" if g.group(2).lower() in ("đúng", "đ", "true") else "S"
        if not kq:
            ky_tu = re.sub(r"[^ĐSĐđsS]", "", s)
            if len(ky_tu) == 4:
                for k, c in zip("abcd", ky_tu):
                    kq[k] = "Đ" if c in "Đđ" else "S"
    if len(kq) != 4:
        return _s(v).strip()          # không đoán: giữ nguyên để kiem_tra phát hiện
    return ", ".join("%s) %s" % (k, kq[k]) for k in "abcd")


def chuan_dap_an_p3(v):
    s = _s(v).strip().replace("\u2212", "-").replace("−", "-").replace("{,}", ".")
    s = re.sub(r"\s+", "", s)
    if re.fullmatch(r"[-+]?\d+,\d+", s):
        s = s.replace(",", ".")
    return s


def chuan_dap_an_p4(v):
    s = _s(v).replace("\\n", "\n") if "\n" not in _s(v) else _s(v)
    dong = [d.strip() for d in re.split(r"\r?\n", s) if d.strip()]
    ra = []
    for d in dong:
        if d.startswith("=>") or d.startswith("- "):
            ra.append(d)
        elif d.startswith("-"):
            ra.append("- " + d[1:].strip())
        else:
            ra.append("- " + d)
    return "\n".join(ra)


# ---------------------------------------------------------------- hình ảnh (bản Python của chuanHoaHinhAnh)
def _khong_dau(s):
    import unicodedata
    s = unicodedata.normalize("NFD", _s(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")
    return re.sub(r"[^a-z0-9]", "", s)


def _so(v):
    try:
        return float(_s(v).replace(",", ".").replace("{.}", "."))
    except ValueError:
        return float("nan")


def chuan_hinh_anh(h):
    """→ dict chuẩn (có hopLe/lyDo) hoặc None nếu câu không có hình."""
    import json
    if h in (None, "", [], {}):
        return None
    if isinstance(h, str):
        s = re.sub(r"```json|```", "", h).strip()
        if not s.startswith(("{", "[")):
            return None
        try:
            h = json.loads(s)
        except ValueError:
            return None
    if isinstance(h, list):
        h = h[0] if h else None
    if not isinstance(h, dict):
        return None
    if h.get("daChuanHoa"):
        return h
    l = _khong_dau(h.get("loai") or h.get("type"))
    if re.search(r"bang|table", l):
        loai = "bang"
    elif re.search(r"dothi|graph|chart|plot", l):
        loai = "dothi"
    elif re.search(r"anhthuc|photo|web|image|anh", l):
        loai = "anhthuc"
    elif re.search(r"hinhve|sodo|hinh|diagram|drawing", l):
        loai = "hinhve"
    elif h.get("dong") or h.get("rows"):
        loai = "bang"
    elif h.get("duLieu") or h.get("series") or h.get("diem"):
        loai = "dothi"
    elif h.get("moTa"):
        loai = "hinhve"
    elif h.get("tuKhoaTimKiem"):
        loai = "anhthuc"
    else:
        return None
    kq = {"daChuanHoa": True, "loai": loai, "chuThich": _s(h.get("chuThich") or h.get("caption")).strip(), "hopLe": True, "lyDo": ""}
    if loai == "bang":
        dong = [[_s(x) for x in r] for r in (h.get("dong") or h.get("rows") or []) if isinstance(r, list)]
        td = [_s(x) for x in h["tieuDeCot"]] if isinstance(h.get("tieuDeCot"), list) else None
        if td is None and dong:
            td = dong.pop(0)
        td = td or []
        so_cot = min(8, max([len(td)] + [len(r) for r in dong] + [0]))
        dem = lambda r: (r[:so_cot] + [""] * so_cot)[:so_cot]
        kq["tieuDeCot"], kq["dong"] = dem(td), [dem(r) for r in dong[:15]]
        if so_cot < 1 or not kq["dong"]:
            kq["hopLe"], kq["lyDo"] = False, "bảng cần tieuDeCot và ít nhất 1 dòng số liệu"
        return kq
    if loai == "dothi":
        kd = _khong_dau(h.get("kieuDoThi") or h.get("kieu") or h.get("chartType"))
        kq["kieuDoThi"] = "bar" if re.search(r"bar|cot|column", kd) else ("scatter" if re.search(r"scatter|diem|cham", kd) else "line")
        kq["nhanTrucX"], kq["nhanTrucY"] = _s(h.get("nhanTrucX") or h.get("xLabel")).strip(), _s(h.get("nhanTrucY") or h.get("yLabel")).strip()
        ds = h.get("duLieu") or h.get("series") or ([{"ten": "", "diem": h["diem"]}] if isinstance(h.get("diem"), list) else [])
        out = []
        for s in ds:
            if not isinstance(s, dict):
                continue
            tho = s.get("diem") or s.get("data") or s.get("points") or []
            diem = []
            for p in tho:
                if isinstance(p, (list, tuple)) and len(p) >= 2:
                    x, y = p[0], p[1]
                elif isinstance(p, dict):
                    x, y = p.get("x"), p.get("y")
                else:
                    continue
                xs = _so(x)
                x = _s(x) if (kq["kieuDoThi"] == "bar" and xs != xs) else xs
                ys = _so(y)
                if ys == ys and (isinstance(x, str) or x == x):
                    diem.append([x, ys])
            if diem:
                out.append({"ten": _s(s.get("ten") or s.get("name") or s.get("label")).strip(), "diem": diem})
        kq["duLieu"] = out[:4]
        toi_thieu = 1 if kq["kieuDoThi"] == "bar" else 2
        if not any(len(s["diem"]) >= toi_thieu for s in kq["duLieu"]):
            kq["hopLe"], kq["lyDo"] = False, "đồ thị cần duLieu có ít nhất 2 điểm [x, y] là số"
        return kq
    kq["moTa"], kq["tuKhoaTimKiem"] = _s(h.get("moTa") or h.get("description")).strip(), _s(h.get("tuKhoaTimKiem") or h.get("query")).strip()
    if loai == "hinhve" and not kq["moTa"]:
        kq["hopLe"], kq["lyDo"] = False, "hình vẽ cần moTa chi tiết"
    if loai == "anhthuc" and not (kq["tuKhoaTimKiem"] or kq["moTa"]):
        kq["hopLe"], kq["lyDo"] = False, "ảnh thực tế cần tuKhoaTimKiem hoặc moTa"
    return kq


# ---------------------------------------------------------------- chuẩn hoá cả đề
def chuan_hoa_de(de):
    """→ (đề mới, danh sách thay đổi đáng chú ý). Không sửa đề gốc."""
    de = copy.deepcopy(de) if isinstance(de, dict) else {}
    ghi = []
    for p in (1, 2, 3, 4):
        khoa = "phan%d" % p
        ds = de.get(khoa)
        de[khoa] = ds if isinstance(ds, list) else []
        for i, c in enumerate(de[khoa]):
            if not isinstance(c, dict):
                de[khoa][i] = c = {"cauHoi": _s(c)}
            for k in ("cauHoi", "A", "B", "C", "D", "loiGiai"):
                if k in c:
                    moi = L.chuan_hoa_latex(tien_xu_ly(c[k]))
                    if moi != _s(c[k]).strip():
                        ghi.append("Phần %d câu %d: chuẩn hoá %s" % (p, i + 1, k))
                    c[k] = moi
            cu = c.get("dapAn")
            if p == 1:
                c["dapAn"] = chuan_dap_an_p1(cu)
            elif p == 2:
                c["dapAn"] = chuan_dap_an_p2(cu)
            elif p == 3:
                c["dapAn"] = chuan_dap_an_p3(cu)
            else:
                c["dapAn"] = L.chuan_hoa_latex(tien_xu_ly(chuan_dap_an_p4(cu)))
            if _s(cu).strip() != _s(c["dapAn"]).strip():
                ghi.append("Phần %d câu %d: đáp án đưa về dạng chuẩn" % (p, i + 1))
            if "hinhAnh" in c:
                h = chuan_hinh_anh(c["hinhAnh"])
                if h:
                    h["chuThich"] = L.chuan_hoa_latex(tien_xu_ly(h["chuThich"]))
                    c["hinhAnh"] = h
                else:
                    del c["hinhAnh"]
    return de, ghi


def kiem_tra_latex(de):
    """Lỗi công thức theo từng câu (không dùng AI). Trả về list chuỗi 'Phần p câu i: …'."""
    loi = []
    for p in (1, 2, 3, 4):
        for i, c in enumerate((de or {}).get("phan%d" % p) or []):
            if not isinstance(c, dict):
                continue
            for k in ("cauHoi", "A", "B", "C", "D", "dapAn", "loiGiai"):
                s = _s(c.get(k))
                if not s:
                    continue
                if k == "dapAn" and p in (1, 2, 3):
                    continue
                vi_tri = "Phần %d câu %d (%s)" % (p, i + 1, k)
                if s.count("$") % 2:
                    loi.append("%s: số dấu $ lẻ – công thức mở mà không đóng." % vi_tri)
                    continue
                ngoai = RE_TOAN.sub(" ", s)
                if RE_LENH_TRAN.search(ngoai):
                    loi.append("%s: có lệnh LaTeX nằm ngoài $…$ (VD %s)." % (vi_tri, RE_LENH_TRAN.search(ngoai).group(0)))
                if RE_UNICODE_TOAN.search(RE_TOAN.sub(" ", s)):
                    loi.append("%s: còn kí hiệu Unicode ngoài $…$; đưa vào công thức." % vi_tri)
                for m in RE_TOAN.finditer(s):
                    if m.group(0).count("{") != m.group(0).count("}"):
                        loi.append("%s: ngoặc nhọn { } không cân trong công thức." % vi_tri)
                        break
    return loi


def tu_dinh_dang_cu(de_cu):
    """Đề theo mẫu cũ của tao_de.py → phan1..phan4."""
    if not isinstance(de_cu, dict):
        return {"phan1": [], "phan2": [], "phan3": [], "phan4": []}
    if any(k in de_cu for k in ("phan1", "phan2", "phan3", "phan4")):
        return de_cu
    de = {"phan1": [], "phan2": [], "phan3": [], "phan4": []}
    for c in de_cu.get("phan_I_trac_nghiem_nhieu_lua_chon") or []:
        lc = c.get("lua_chon") or {}
        de["phan1"].append({"cauHoi": c.get("cau_hoi", ""), **{k: lc.get(k, "") for k in CAC_Y}, "dapAn": c.get("dap_an", ""),
                            "loiGiai": c.get("huong_dan_giai", "")})
    for c in de_cu.get("phan_II_trac_nghiem_dung_sai") or []:
        md = c.get("menh_de") or {}
        de["phan2"].append({"cauHoi": c.get("noi_dung_dan", ""), **{k: md.get(k.lower(), md.get(k, "")) for k in CAC_Y},
                            "dapAn": c.get("dap_an", {}), "loiGiai": c.get("huong_dan_giai", "")})
    for c in de_cu.get("phan_III_tra_loi_ngan") or []:
        de["phan3"].append({"cauHoi": c.get("cau_hoi", ""), "dapAn": c.get("dap_an", ""), "loiGiai": c.get("huong_dan_giai", "")})
    for c in de_cu.get("phan_IV_tu_luan") or []:
        da = c.get("dap_an_chi_tiet")
        de["phan4"].append({"cauHoi": c.get("cau_hoi", ""), "dapAn": "\n".join(da) if isinstance(da, list) else _s(da)})
    return de
