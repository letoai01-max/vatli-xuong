"""
xuat_de_v2.py – XUẤT ĐỀ THI RA WORD (HS + GV) TỪ JSON phan1..phan4, BẰNG PANDOC (xưởng Python, GitHub Actions).

  • Công thức $…$ / $$…$$ → phương trình Word (OMML) thật; đồ thị vẽ bằng matplotlib (có mũi tên ở đầu hai trục);
    bảng số liệu → bảng Word; hình vẽ / ảnh thực tế lấy từ hinh_san {"P1_C3": "/đường/dẫn.png"} (bước vẽ hình điền vào).
  • Hai bản: HS (đề + ----HẾT----) và GV (đề + bảng đáp án + hướng dẫn giải, Phần IV có lời giải từng bước).
  • Không có mau_word.docx trong kho → tự dựng mẫu kiểu chữ Times New Roman 12, lề 2 cm, bảng có viền.
  • Chạy thử trên máy:  python xuat_de_v2.py de.json [cauhinh.json] [thư_mục_ra]
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import chuan_de as CD
import latex_chuan as L
from xuat_word import DINH_DANG_VAO, PAGE_BREAK, sua_md          # dùng lại đúng bộ sửa Markdown đã chạy ổn ở xuat_word.py

RE_TOAN = re.compile(r"(\$\$[\s\S]*?\$\$|\$[^$\n]+?\$)")
TIEU_DE_PHAN = {
    1: "PHẦN I. Câu trắc nghiệm nhiều phương án lựa chọn. Thí sinh trả lời từ câu 1 đến câu {n}. Mỗi câu hỏi thí sinh chỉ chọn một phương án.",
    2: "PHẦN II. Câu trắc nghiệm đúng sai. Thí sinh trả lời từ câu 1 đến câu {n}. Trong mỗi ý a), b), c), d) ở mỗi câu, thí sinh chọn đúng hoặc sai.",
    3: "PHẦN III. Câu trắc nghiệm trả lời ngắn. Thí sinh trả lời từ câu 1 đến câu {n}.",
    4: "PHẦN IV. Tự luận. Thí sinh trình bày lời giải từng bước, ghi rõ đơn vị.",
}
MAU = ["#000000", "#1f4e79", "#a61c00", "#38761d"]


# ------------------------------------------------------------------ Markdown
def thoat_md(s):
    """Thoát kí tự đặc biệt của Markdown ở phần CHỮ (không đụng công thức)."""
    ra = []
    for i, doan in enumerate(RE_TOAN.split(str(s))):
        if i % 2 == 1:
            ra.append(doan)
        else:
            doan = doan.replace("*", "\\*").replace("<", "\\<").replace(">", "\\>")
            doan = re.sub(r"(?m)^(\s*)#", r"\1\\#", doan)
            ra.append(doan)
    return "".join(ra)


def so_vn(s):
    return re.sub(r"(?<=\d)\.(?=\d)", ",", str(s))


def ve_do_thi(h, duong_dan):
    """Đồ thị từ hinhAnh chuẩn (line | scatter | bar). line/scatter có mũi tên ở đầu trục."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.0, 3.8), dpi=150)
    kieu = h.get("kieuDoThi", "line")
    for k, s in enumerate(h["duLieu"]):
        xs, ys = [p[0] for p in s["diem"]], [p[1] for p in s["diem"]]
        mau, ten = MAU[k % 4], s.get("ten") or None
        if kieu == "bar":
            n = len(h["duLieu"])
            if all(isinstance(x, str) for x in xs):
                pos = [i + (k - (n - 1) / 2) * 0.8 / n for i in range(len(xs))]
                ax.bar(pos, ys, width=0.8 / n, color=mau, label=ten)
                ax.set_xticks(range(len(xs)))
                ax.set_xticklabels(xs)
            else:
                ax.bar(xs, ys, color=mau, label=ten)
        elif kieu == "scatter":
            ax.scatter(xs, ys, color=mau, s=22, label=ten, zorder=3)
        else:
            ap = sorted(zip(xs, ys))
            ax.plot([p[0] for p in ap], [p[1] for p in ap], color=mau, linewidth=2, marker="o", markersize=3.5, label=ten)
    ax.set_xlabel(h.get("nhanTrucX", ""), loc="right")
    ax.set_ylabel(h.get("nhanTrucY", ""), loc="top")
    ax.grid(True, color="#e3e3e3", linewidth=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if kieu != "bar":
        ax.plot(1, 0, ">k", transform=ax.get_yaxis_transform(which="grid"), clip_on=False, markersize=6)
        ax.plot(0, 1, "^k", transform=ax.get_xaxis_transform(which="grid"), clip_on=False, markersize=6)
    if len([s for s in h["duLieu"] if s.get("ten")]) > 1:
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=min(4, len(h["duLieu"])), frameon=False)
    fig.tight_layout()
    fig.savefig(duong_dan)
    plt.close(fig)


def dong_hinh(p, i, h, thu_muc, hinh_san, canh_bao):
    """Các dòng Markdown của hinhAnh một câu (có chú thích nghiêng)."""
    ma = "P%d_C%d" % (p, i)
    vt = "Phần %d câu %d" % (p, i)
    if not h:
        return []
    if not h.get("hopLe"):
        canh_bao.append("%s: hình không hợp lệ (%s) – bỏ qua." % (vt, h.get("lyDo")))
        return []
    ct = ["*%s*" % thoat_md(h["chuThich"]), ""] if h.get("chuThich") else []
    if h["loai"] == "bang":
        td = [thoat_md(x).replace("|", "\\|") for x in h["tieuDeCot"]]
        t = ["| " + " | ".join(td) + " |", "|" + "|".join(["---"] * len(td)) + "|"]
        t += ["| " + " | ".join(thoat_md(x).replace("|", "\\|") for x in r) + " |" for r in h["dong"]]
        return [""] + ct + t + [""]
    if h["loai"] == "dothi":
        try:
            duong = os.path.join(thu_muc, "dothi_%s.png" % ma)
            ve_do_thi(h, duong)
            return ["", "![](%s){width=4.3in}" % duong, ""] + ct[:1] + [""]
        except Exception as e:
            canh_bao.append("%s: không vẽ được đồ thị – %s" % (vt, str(e)[:80]))
            return ["*(Đồ thị: không vẽ được)*"]
    duong = (hinh_san or {}).get(ma)
    if duong and os.path.isfile(duong):
        return ["", "![](%s){width=4.3in}" % duong, ""] + ct[:1] + [""]
    canh_bao.append("%s: chưa có ảnh cho hình '%s' – để chỗ trống ghi chú." % (vt, h["loai"]))
    return ["", "*[Hình: %s]*" % thoat_md(h.get("moTa") or h.get("tuKhoaTimKiem") or ""), ""]


def _bang_ngang(tieu, hang, mot_hang=10):
    """Bảng đáp án ngang, ngắt thành nhiều bảng mỗi `mot_hang` cột."""
    out = []
    for a in range(0, len(hang), mot_hang):
        khuc = hang[a:a + mot_hang]
        out += ["| Câu | " + " | ".join(k for k, _ in khuc) + " |", "|" + "|".join(["---"] * (len(khuc) + 1)) + "|",
                "| %s | " % tieu + " | ".join(v for _, v in khuc) + " |", ""]
    return out


def dung_markdown(de, cau_hinh, ban, thu_muc, hinh_san, canh_bao):
    """→ Markdown của một bản ('hs' hoặc 'gv')."""
    ch = cau_hinh or {}
    phan = []
    dau = ch.get("dauTrang")
    if not dau:
        dau = [["tieu", ch.get("tenDe") or "ĐỀ KIỂM TRA"],
               ["phu", "Môn: %s %s – Thời gian làm bài: %s phút" % (ch.get("subject", "Vật lí"), ch.get("grade", ""), ch.get("thoiGianPhut", 45))]]
    for kieu, chu in dau:
        chu = str(chu).replace("\n", " ").strip()
        phan.append('::: {custom-style="Title"}\n%s\n:::' % chu if kieu == "tieu" else
                    '::: {custom-style="Subtitle"}\n%s\n:::' % chu if kieu == "phu" else "*%s*" % chu)
    if ban == "hs":
        phan.append("Họ và tên: ................................................ Lớp: ............ SBD: ............")
    dong = []

    def them(*ds):
        for d in ds:
            dong.extend(d if isinstance(d, list) else [d])

    for p in (1, 2, 3, 4):
        ds = de["phan%d" % p]
        if not ds:
            continue
        them("", "**%s**" % thoat_md(TIEU_DE_PHAN[p].format(n=len(ds))), "")
        for i, c in enumerate(ds, 1):
            them("**Câu %d.** %s" % (i, thoat_md(c["cauHoi"])))
            them(dong_hinh(p, i, c.get("hinhAnh"), thu_muc, hinh_san, canh_bao))
            if p == 1:
                them(["**%s.** %s" % (k, thoat_md(c.get(k, ""))) for k in CD.CAC_Y])
            elif p == 2:
                them(["%s) %s" % (k.lower(), thoat_md(c.get(k, ""))) for k in CD.CAC_Y])
            them("")
    them("", "::: {custom-style=\"Subtitle\"}", "----HẾT----", ":::")
    if ban == "gv":
        them("", "**ĐÁP ÁN VÀ HƯỚNG DẪN GIẢI**", "")
        if de["phan1"]:
            them("**Phần I**", "", _bang_ngang("Đáp án", [(str(i), c["dapAn"] or "?") for i, c in enumerate(de["phan1"], 1)]))
        if de["phan2"]:
            them("**Phần II**", "", "| Câu | a | b | c | d |", "|---|---|---|---|---|")
            for i, c in enumerate(de["phan2"], 1):
                ys = dict(re.findall(r"([a-d])\)\s*(Đ|S)", c["dapAn"]))
                them("| %d | %s |" % (i, " | ".join(ys.get(k, "?") for k in "abcd")))
            them("")
        if de["phan3"]:
            them("**Phần III**", "", _bang_ngang("Đáp án", [(str(i), so_vn(c["dapAn"]) or "?") for i, c in enumerate(de["phan3"], 1)]))
        if de["phan4"]:
            them("**Phần IV**", "")
            for i, c in enumerate(de["phan4"], 1):
                them("**Câu %d.**" % i, "")
                for d in c["dapAn"].split("\n"):
                    them(thoat_md(d) if not d.startswith("=>") else "**%s**" % thoat_md(d), "" if d.startswith("=>") else "")
        co_loi_giai = [(p, i, c["loiGiai"]) for p in (1, 2, 3) for i, c in enumerate(de["phan%d" % p], 1) if c.get("loiGiai")]
        if co_loi_giai:
            them("", "**Hướng dẫn giải Phần I–III**", "")
            for p, i, t in co_loi_giai:
                them("- Phần %s câu %d: %s" % ("I" * p if p < 4 else "IV", i, thoat_md(t)))
    return "\n\n".join(phan) + "\n" + sua_md("\n".join(dong)) + "\n"


# ------------------------------------------------------------------ mẫu kiểu chữ + pandoc
def tao_mau_tham_chieu(duong_dan):
    """Mẫu Word cho pandoc: Times New Roman 12, lề 2 cm, tiêu đề đen căn giữa (đề thi, không phải tài liệu xanh mặc định)."""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor
    nap = subprocess.run(["pandoc", "-o", duong_dan, "--print-default-data-file", "reference.docx"], capture_output=True)
    if nap.returncode != 0:
        raise RuntimeError("pandoc không xuất được reference.docx: " + nap.stderr.decode("utf-8", "ignore")[:200])
    d = Document(duong_dan)

    def dat(ten, co=12, dam=None, nghieng=None, giua=False, sau=4):
        try:
            st = d.styles[ten]
        except KeyError:
            return
        st.font.name, st.font.size, st.font.color.rgb = "Times New Roman", Pt(co), RGBColor(0, 0, 0)
        st.element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Times New Roman")
        if dam is not None:
            st.font.bold = dam
        if nghieng is not None:
            st.font.italic = nghieng
        pf = st.paragraph_format
        pf.space_before, pf.space_after, pf.line_spacing = Pt(0), Pt(sau), 1.15
        if giua:
            pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for ten in ("Normal", "Body Text", "First Paragraph", "Compact", "Block Text", "Table Caption", "Image Caption"):
        dat(ten)
    dat("Title", 14, dam=True, giua=True, sau=2)
    dat("Subtitle", 12, dam=False, nghieng=True, giua=True, sau=4)
    for s in d.sections:
        s.top_margin = s.bottom_margin = s.left_margin = s.right_margin = Cm(2)
    d.save(duong_dan)


def ke_bang(duong_dan):
    """Viền đơn cho mọi bảng (pandoc mặc định không có viền)."""
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    d = Document(duong_dan)
    for b in d.tables:
        tblPr = b._tbl.tblPr
        for cu in tblPr.findall(qn("w:tblBorders")):
            tblPr.remove(cu)
        vien = OxmlElement("w:tblBorders")
        for canh in ("top", "left", "bottom", "right", "insideH", "insideV"):
            e = OxmlElement("w:" + canh)
            for k, v in (("val", "single"), ("sz", "4"), ("space", "0"), ("color", "808080")):
                e.set(qn("w:" + k), v)
            vien.append(e)
        tblPr.append(vien)
    d.save(duong_dan)


def md_sang_docx(md, thu_muc, ra, mau=None):
    vao = os.path.join(thu_muc, os.path.basename(ra) + ".md")
    with open(vao, "w", encoding="utf-8") as f:
        f.write(md)
    if not mau:
        mau = os.path.join(thu_muc, "mau_tham_chieu.docx")
        if not os.path.isfile(mau):
            tao_mau_tham_chieu(mau)
    lenh = ["pandoc", vao, "-f", DINH_DANG_VAO, "-t", "docx", "-o", ra, "--resource-path", thu_muc, "--reference-doc", mau]
    kq = subprocess.run(lenh, capture_output=True, text=True, timeout=300)
    if kq.returncode != 0:
        raise RuntimeError("pandoc lỗi: " + (kq.stderr or kq.stdout)[:400])
    ke_bang(ra)
    return kq.stderr.strip()


def xuat_de(de, cau_hinh, thu_muc_ra, hinh_san=None, ten_goc="De", mau_word=None):
    """→ {"hs": path, "gv": path, "canhBao": [...], "loiLatex": [...], "thongKe": {...}}"""
    os.makedirs(thu_muc_ra, exist_ok=True)
    de, ghi = CD.chuan_hoa_de(de)
    canh_bao, tam = [], tempfile.mkdtemp()
    try:
        if os.path.isfile("mau_word.docx") and not mau_word:
            mau_word = os.path.abspath("mau_word.docx")
        kq = {}
        for ban in ("hs", "gv"):
            md = dung_markdown(de, cau_hinh, ban, tam, hinh_san, canh_bao if ban == "hs" else [])
            ra = os.path.join(thu_muc_ra, "%s_%s.docx" % (ten_goc, ban.upper()))
            cb = md_sang_docx(md, tam, ra, mau_word)
            if cb:
                canh_bao.append("pandoc: " + cb[:200])
            kq[ban] = ra
        kq["canhBao"] = list(dict.fromkeys(canh_bao))
        kq["loiLatex"] = CD.kiem_tra_latex(de)
        kq["thongKe"] = {"soCau": {"p%d" % p: len(de["phan%d" % p]) for p in (1, 2, 3, 4)},
                         "soHinh": sum(1 for p in (1, 2, 3, 4) for c in de["phan%d" % p] if c.get("hinhAnh")), "daChuanHoa": len(ghi)}
        return kq
    finally:
        shutil.rmtree(tam, ignore_errors=True)


if __name__ == "__main__":
    de = json.load(open(sys.argv[1], encoding="utf-8"))
    ch = json.load(open(sys.argv[2], encoding="utf-8")) if len(sys.argv) > 2 else {}
    kq = xuat_de(CD.tu_dinh_dang_cu(de), ch, sys.argv[3] if len(sys.argv) > 3 else ".")
    print(json.dumps(kq, ensure_ascii=False, indent=1))
