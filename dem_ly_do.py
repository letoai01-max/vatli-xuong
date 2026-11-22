"""
dem_ly_do.py – ĐẾM CÂU "LOẠI" VÀ "CẦN NGƯỜI XEM" THEO LÍ DO (chỉ đọc, không ghi gì vào kho).   [22/11/2026]

Đọc tab NganHangCauHoi, lấy cột "Trạng thái duyệt" + "Kiểm tra", gom theo LÍ DO (đoạn sau dấu "[5 tầng" cuối cùng)
rồi in bảng đếm + tách riêng: có hình / không hình, đã được cứu/duyệt lại một lần chưa.

Chạy:
  • Trên máy có khoá Google:   python dem_ly_do.py
  • Từ file CSV xuất từ tab:   python dem_ly_do.py --csv NganHangCauHoi.csv     (Tệp > Tải xuống > CSV)
  • Ghi thêm ra file:          python dem_ly_do.py --ra dem_ly_do.md
"""
import argparse, collections, csv, re, sys

TAB_NH = "NganHangCauHoi"
DAU_MAY = "[5 tầng"
TT_LOAI, TT_XEM = "Loại", "Cần người xem"

# (nhãn, mẫu) – câu nhiều lí do được đếm ở MỌI nhóm khớp; thêm cột "chỉ một lí do" để khỏi cộng trùng.
NHOM = [
    ("Thiếu phương án (TN)",              r"Thiếu phương án"),
    ("Thiếu ý đúng/sai (DS)",             r"Thiếu ý đúng/sai"),
    ("Đề quá ngắn / thiếu đề",            r"quá ngắn"),
    ("Lỗi nội dung (model báo)",          r"Lỗi nội dung"),
    ("Trùng hẳn",                         r"Trùng hẳn"),
    ("Ngoài chương trình 2018",           r"Ngoài chương trình"),
    ("Máy/model bất đồng, không hình",    r"câu không có hình"),
    ("Bất đồng đáp án (có hình hoặc chưa phân loại)", r"chưa thống nhất|bất đồng|khác nhau|không khớp"),
    ("Thiếu dữ kiện / nhắc hình mà không có hình", r"Thiếu dữ kiện|nhắc tới hình"),
    ("Mã YCCĐ nghi vấn / chưa gắn",       r"YCCĐ|YCCD"),
    ("Từ khoá chương trình cũ",           r"chương trình cũ"),
    ("Công thức $…$ lỗi",                 r"\$…\$|không đóng mở"),
    ("Gần như trùng",                     r"Gần như trùng"),
    ("Đơn vị / số liệu chưa có",          r"số liệu chưa có|Đơn vị không cùng"),
    ("Không tự xác minh được (XEM_CON_LAI=loai)", r"không tự xác minh"),
]
NHOM = [(n, re.compile(m, re.I)) for n, m in NHOM]


def doan_cuoi(kt):
    """Đoạn lí do của LẦN CHẠY MÁY GẦN NHẤT; không có dấu máy → ''."""
    return kt.rsplit(DAU_MAY, 1)[-1] if DAU_MAY in kt else ""


def phan_loai(kt):
    d = doan_cuoi(kt)
    if not d: return ["(Không có dấu máy – giáo viên/GAS đặt)"]
    got = [n for n, p in NHOM if p.search(d)]
    return got or ["(Khác – xem mẫu bên dưới)"]


def doc_sheet():
    import doc_de as X
    gc, _drive, _sa = X.ket_noi()
    return gc.open_by_key(X.ID_KHO_CHUNG).worksheet(TAB_NH).get_all_values()


def doc_csv(tep):
    with open(tep, encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv"); ap.add_argument("--ra")
    a = ap.parse_args()
    v = doc_csv(a.csv) if a.csv else doc_sheet()
    td = [t.strip() for t in v[0]]
    for t in ("Trạng thái duyệt", "Kiểm tra"):
        if t not in td: sys.exit("Thiếu cột '%s' trong tab (có: %s)" % (t, ", ".join(td)))
    i_tt, i_kt = td.index("Trạng thái duyệt"), td.index("Kiểm tra")
    i_nd = td.index("Nội dung") if "Nội dung" in td else None
    i_dang = td.index("Dạng") if "Dạng" in td else None

    tong = collections.Counter()
    ct = {TT_LOAI: collections.Counter(), TT_XEM: collections.Counter()}
    mot_ly_do = {TT_LOAI: collections.Counter(), TT_XEM: collections.Counter()}
    phu = {TT_LOAI: collections.Counter(), TT_XEM: collections.Counter()}
    mau_khac = []
    for r in v[1:]:
        r = r + [""] * (len(td) - len(r))
        tt = r[i_tt].strip(); tong[tt or "(trống)"] += 1
        if tt not in ct: continue
        kt = r[i_kt]
        nhom = phan_loai(kt)
        for n in nhom: ct[tt][n] += 1
        if len(nhom) == 1: mot_ly_do[tt][nhom[0]] += 1
        d = doan_cuoi(kt)
        phu[tt]["đã cứu Loại một lần"] += "cứu Loại" in kt
        phu[tt]["đã duyệt lại một lần"] += "duyệt lại]" in kt
        phu[tt]["có mô tả [Hình…]"] += (i_nd is not None and "[Hình" in r[i_nd])
        phu[tt]["chưa có ý/phương án (cột Phương án trống)"] += not r[td.index("Phương án")].strip() if "Phương án" in td else 0
        if nhom == ["(Khác – xem mẫu bên dưới)"] and len(mau_khac) < 8: mau_khac.append(d.strip()[:160])

    ra = ["# Đếm theo lí do – tab %s\n" % TAB_NH, "Tổng theo trạng thái: " +
          ", ".join("%s = %d" % kv for kv in tong.most_common()) + "\n"]
    for tt in (TT_LOAI, TT_XEM):
        n = tong[tt]
        ra += ["\n## %s (%d câu)\n" % (tt, n), "| Lí do | Số câu | Chỉ riêng lí do này |", "|---|---:|---:|"]
        for ten, so in ct[tt].most_common():
            ra.append("| %s | %d (%.0f%%) | %d |" % (ten, so, 100 * so / max(n, 1), mot_ly_do[tt][ten]))
        ra.append("\nPhụ: " + "; ".join("%s = %d" % kv for kv in phu[tt].items()))
    if mau_khac:
        ra += ["\n## Mẫu lí do chưa gom được (để thêm mẫu vào NHOM)\n"] + ["- " + m for m in mau_khac]
    s = "\n".join(ra)
    print(s)
    if a.ra:
        open(a.ra, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    main()
