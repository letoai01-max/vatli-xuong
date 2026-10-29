"""
xuat_word.py – XUẤT WORD BẰNG PANDOC (Python, GitHub Actions) – thử song song với Word của Apps Script (đề cương trước).

Apps Script (WordPandoc.gs) vẫn tạo bản Word như cũ, rồi gửi thêm "gói việc" gồm ĐÚNG nội dung đã dùng để tạo Word đó
(tên, đầu trang, các phần Markdown) và một tệp Word rỗng "<tên> (pandoc).docx" nằm cạnh bản cũ. Xưởng:
  1. Dựng Markdown: đầu trang (Title / Subtitle / nghiêng), mỗi phần sang trang mới, dòng [[DO_THI: {…}]] → ảnh đồ thị
     vẽ bằng matplotlib (cùng quy ước với dcotHinh_ của Apps Script).
  2. pandoc → .docx: công thức $…$ / $$…$$ thành PHƯƠNG TRÌNH WORD (OMML) thật; bảng, tiêu đề, đậm giữ nguyên.
     Có tệp mau_word.docx trong kho thì dùng làm mẫu kiểu chữ (--reference-doc).
  3. Ghi đè nội dung vào tệp "(pandoc).docx" (tệp do thầy sở hữu nên không tốn dung lượng tài khoản dịch vụ).
Lỗi → đổi tên tệp thành "(pandoc – LỖI) …" để thầy biết; bản Word cũ không bị ảnh hưởng.
Biến môi trường: GOOGLE_CREDENTIALS, GOI_ID, DICH_ID.
"""
import io, json, os, re, shutil, subprocess, sys, tempfile

from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

import kiem_dinh_de as K        # ket_noi_ghi (quyền sửa Drive)

RE_DO_THI = re.compile(r"^\s*\[\[DO_THI:\s*(\{.*\})\s*\]\]\s*$")
MAU = ["#000000", "#1f4e79", "#a61c00", "#38761d"]
PAGE_BREAK = '\n\n```{=openxml}\n<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n```\n\n'
DINH_DANG_VAO = "markdown+hard_line_breaks+tex_math_dollars+pipe_tables+raw_attribute+fenced_divs-fancy_lists-implicit_figures-smart"


def ve_do_thi(json_txt, duong_dan):
    """Giống dcotHinh_: tối đa 4 đường, mỗi đường ≥2 điểm (tối đa 30), đường + điểm, chú thích dưới khi có nhiều đường."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    spec = json.loads(json_txt)
    ds = []
    for d in (spec.get("duong") or [])[:4]:
        diem = []
        for p in d.get("diem") or []:
            try:
                diem.append((float(p[0]), float(p[1])))
            except (TypeError, ValueError, IndexError):
                pass
        if len(diem) >= 2:
            ds.append((str(d.get("ten") or spec.get("y") or "y"), sorted(diem[:30])))
    if not ds:
        raise ValueError("đồ thị không có đường nào đủ 2 điểm")
    fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=150)
    for k, (ten, diem) in enumerate(ds):
        ax.plot([p[0] for p in diem], [p[1] for p in diem], color=MAU[k % 4], linewidth=2, marker="o", markersize=4, label=ten)
    ax.set_title(str(spec.get("tieuDe") or ""), fontsize=12)
    ax.set_xlabel(str(spec.get("x") or "")); ax.set_ylabel(str(spec.get("y") or ""))
    ax.grid(True, color="#dddddd", linewidth=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if len(ds) > 1:
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=min(4, len(ds)), frameon=False)
    fig.tight_layout()
    fig.savefig(duong_dan)
    plt.close(fig)


RE_GACH = re.compile(r"^\s*[-*+•]\s+")


def _so_thap_phan(m):
    """Trong công thức: 0,05 → 0{,}05 để Word không chèn khoảng trắng sau dấu phẩy thập phân."""
    return re.sub(r"(\d),(?=\d)", r"\1{,}", m.group(0))


def sua_md(md):
    """Pandoc cần dòng trống trước bảng, tiêu đề và gạch đầu dòng; Gemini hay viết sát nhau."""
    md = re.sub(r"\$\$[\s\S]*?\$\$|\$[^$\n]+\$", _so_thap_phan, str(md))
    ra, truoc = [], ""
    for dong in md.split("\n"):
        mo_bang = dong.lstrip().startswith("|") and not truoc.lstrip().startswith("|")
        tieu_de = re.match(r"^#{1,6}\s", dong) is not None
        mo_gach = RE_GACH.match(dong) is not None and RE_GACH.match(truoc) is None
        het_gach = RE_GACH.match(dong) is None and RE_GACH.match(truoc) is not None and dong.strip()
        het_bang = truoc.lstrip().startswith("|") and not dong.lstrip().startswith("|") and dong.strip()
        if RE_GACH.match(dong):
            dong = RE_GACH.sub("- ", dong, count=1)
        if (mo_bang or tieu_de or mo_gach or het_gach or het_bang) and truoc.strip():
            ra.append("")
        ra.append(dong)
        if tieu_de:
            ra.append("")
        truoc = dong
    return "\n".join(ra)


def dung_markdown(goi, thu_muc):
    phan, so_hinh, loi_hinh = [], 0, 0
    for kieu, chu in goi.get("dauTrang") or []:
        chu = str(chu).replace("\n", " ").strip()
        if kieu == "tieu":
            phan.append('::: {custom-style="Title"}\n' + chu + "\n:::")
        elif kieu == "phu":
            phan.append('::: {custom-style="Subtitle"}\n' + chu + "\n:::")
        else:
            phan.append("*" + chu + "*")
    dau = "\n\n".join(phan)
    than = []
    for md in goi.get("dsMd") or []:
        dong = []
        for l in str(md).split("\n"):
            m = RE_DO_THI.match(l)
            if not m:
                dong.append(l); continue
            so_hinh += 1
            ten = os.path.join(thu_muc, "hinh%d.png" % so_hinh)
            try:
                ve_do_thi(m.group(1), ten)
                dong += ["", "![](%s){width=4.5in}" % ten, ""]
            except Exception as e:
                loi_hinh += 1
                dong.append("*(Hình: không vẽ được – %s)*" % str(e)[:80])
        than.append(sua_md("\n".join(dong)))
    return dau + "\n\n" + PAGE_BREAK.join(than) + "\n", so_hinh, loi_hinh


def main():
    _, drive, sa = K.ket_noi_ghi()
    goi_id, dich_id = os.environ["GOI_ID"], os.environ["DICH_ID"]
    buf = io.BytesIO()
    tai = MediaIoBaseDownload(buf, drive.files().get_media(fileId=goi_id))
    xong = False
    while not xong:
        _, xong = tai.next_chunk()
    goi = json.loads(buf.getvalue().decode("utf-8"))
    print("Xuất Word (pandoc): %s – %d phần" % (goi.get("ten"), len(goi.get("dsMd") or [])), flush=True)
    thu = tempfile.mkdtemp()
    try:
        md, so_hinh, loi_hinh = dung_markdown(goi, thu)
        vao, ra = os.path.join(thu, "vao.md"), os.path.join(thu, "ra.docx")
        with open(vao, "w", encoding="utf-8") as f:
            f.write(md)
        lenh = ["pandoc", vao, "-f", DINH_DANG_VAO, "-t", "docx", "-o", ra, "--resource-path", thu]
        if os.path.isfile("mau_word.docx"):
            lenh += ["--reference-doc", os.path.abspath("mau_word.docx")]
            print("Dùng mẫu kiểu chữ mau_word.docx", flush=True)
        kq = subprocess.run(lenh, capture_output=True, text=True, timeout=300)
        if kq.returncode != 0:
            raise RuntimeError("pandoc lỗi: " + (kq.stderr or kq.stdout)[:400])
        if kq.stderr.strip():
            print("pandoc cảnh báo:", kq.stderr[:400], flush=True)
        drive.files().update(fileId=dich_id, media_body=MediaFileUpload(
            ra, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")).execute()
        print("✅ Đã ghi Word: %d đồ thị%s." % (so_hinh, (", %d đồ thị lỗi" % loi_hinh) if loi_hinh else ""), flush=True)
    except Exception as e:
        try:
            cu = drive.files().get(fileId=dich_id, fields="name").execute().get("name", "")
            drive.files().update(fileId=dich_id, body={"name": "(pandoc – LỖI) " + cu,
                                                       "description": "Xưởng xuất Word lỗi: " + str(e)[:300]}).execute()
        except Exception:
            pass
        raise
    finally:
        shutil.rmtree(thu, ignore_errors=True)


if __name__ == "__main__":
    main()
