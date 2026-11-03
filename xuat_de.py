"""
chi_muc_trung.py – CHỈ MỤC CHỐNG TRÙNG CHO NGÂN HÀNG CÂU HỎI (Python, GitHub Actions, mỗi đêm) – CHỈ ĐỌC NganHangCauHoi.

Với MỖI câu (trừ câu "Loại"), tìm tối đa 3 câu GIỐNG NHẤT trong toàn ngân hàng, tính 2 điểm (0–100%):
  • Giống chữ: so cả đề + phương án, KỂ CẢ số liệu → gần 100% là chép lại.
  • Giống dạng: bỏ hết số liệu rồi so → cao mà "giống chữ" thấp là CÙNG DẠNG, KHÁC SỐ LIỆU (đổi số).
Cách tính: chuỗi 3 từ liên tiếp (bỏ dấu, bỏ lệnh LaTeX), chỉ so những câu có chung đủ nhiều cụm (chỉ mục ngược) → chạy vài
chục giây cho hàng chục nghìn câu, không gọi Gemini.
Ghi tab ChiMucTrung của Kho chung (ghi đè mỗi đêm): Mã câu | Giống nhất | Giống chữ | Giống dạng | Câu 2 | … | Cập nhật.
Dùng ở đâu: duyet_cau.py (tầng 1) đọc tab này → câu gần trùng câu đã có trong kho được ghi chú / chuyển "Cần người xem".
Biến môi trường: GOOGLE_CREDENTIALS; tuỳ chọn NGUONG_GHI (mặc định 60: chỉ ghi cặp giống từ 60% trở lên).

[Hàng 4 – bản sửa]
  • Tách doc_cau() và tinh_chi_muc() thành hàm riêng để xuat_de.py gọi trực tiếp (chỉ mục luôn MỚI, không phụ thuộc đêm trước).
  • Câu "Loại" nhận diện giống xuat_de.py: có chữ "loại" (không phân biệt hoa/thường) trong Trạng thái duyệt.
"""
import datetime as dt, json, os, re, sys, time
from collections import Counter, defaultdict

import doc_de as X

TAB_NH, TAB_CM = "NganHangCauHoi", "ChiMucTrung"
TIEU_DE = ["Mã câu", "Giống nhất", "Giống chữ (%)", "Giống dạng (%)", "Câu 2", "Chữ 2 (%)", "Dạng 2 (%)",
           "Câu 3", "Chữ 3 (%)", "Dạng 3 (%)", "Cập nhật"]
NGUONG_GHI = float(os.environ.get("NGUONG_GHI", "60"))
DF_TOI_DA = 300            # cụm từ xuất hiện ở hơn 300 câu (câu chữ chung kiểu "một vật có khối lượng") không dùng để tìm ứng viên
CHUNG_TOI_THIEU = 3        # hai câu phải chung ít nhất 3 cụm mới đem so
UNG_VIEN_TOI_DA = 40
NOI_DUNG_TOI_THIEU = 15    # câu ngắn hơn không đủ cụm 3 từ để so → không lập chỉ mục (xuat_de vẫn xuất, chỉ không lọc trùng được)


def chuan_chu(s, bo_so=False):
    s = X.bo_dau(s)                                    # bỏ dấu, bỏ $ và lệnh LaTeX, chỉ còn a-z0-9
    if bo_so:
        s = re.sub(r"\b\d+[a-z]{0,3}\b", " ", s)             # cả số dính đơn vị: 10cm, 5kg, 2s
    return re.sub(r"\s+", " ", s).strip().split(" ")


def cum(tu, n=3):
    tu = [t for t in tu if t]
    if len(tu) < n:
        return {" ".join(tu)} if tu else set()
    return {" ".join(tu[i:i + n]) for i in range(len(tu) - n + 1)}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def doc_nut(kho):
    """Đọc tab CauHinh (cột A = tên nút, cột B = giá trị)."""
    try:
        return {str(r[0]).strip(): (str(r[1]).strip() if len(r) > 1 else "")
                for r in kho.worksheet(X.TAB_CAU_HINH).get_all_values()[1:] if r and str(r[0]).strip()}
    except Exception:
        return {}


def doc_nguong_ghi(nut, mac_dinh=None):
    """Ngưỡng ghi chỉ mục từ nút NGUONG_GHI (30–100); không có/sai → mặc định."""
    try:
        return min(100.0, max(30.0, float(nut["NGUONG_GHI"])))
    except (KeyError, ValueError):
        return NGUONG_GHI if mac_dinh is None else mac_dinh


def doc_cau(d):
    """d = get_all_values() của NganHangCauHoi → danh sách câu cần lập chỉ mục (bỏ câu Loại, câu quá ngắn)."""
    td = [t.strip() for t in d[0]]
    c = {t: td.index(t) for t in ["Mã câu", "Nội dung", "Phương án", "Trạng thái duyệt"] if t in td}
    cau = []
    for r in d[1:]:
        r = r + [""] * (len(td) - len(r))
        ma, nd = r[c["Mã câu"]].strip(), r[c["Nội dung"]].strip()
        if not ma or len(nd) < NOI_DUNG_TOI_THIEU or "loại" in r[c["Trạng thái duyệt"]].strip().lower():
            continue
        van = nd + " " + r[c["Phương án"]]
        cau.append({"ma": ma, "chu": cum(chuan_chu(van)), "dang": cum(chuan_chu(van, bo_so=True))})
    return cau


def tinh_chi_muc(cau, nguong_ghi=None):
    """→ [(mã câu, [(mã câu giống, % chữ, % dạng), ...tối đa 3]), ...] chỉ gồm câu có ít nhất 1 câu giống."""
    nguong_ghi = NGUONG_GHI if nguong_ghi is None else nguong_ghi
    # chỉ mục ngược trên cụm "dạng" (bỏ số) – tìm được cả câu đổi số liệu
    df = Counter(g for x in cau for g in x["dang"])
    chi_muc = defaultdict(list)
    for i, x in enumerate(cau):
        for g in x["dang"]:
            if df[g] <= DF_TOI_DA:
                chi_muc[g].append(i)

    kq = []
    for i, x in enumerate(cau):
        dem = Counter()
        for g in x["dang"]:
            for j in chi_muc.get(g, ()):
                if j != i:
                    dem[j] += 1
        ket = []
        for j, n in dem.most_common(UNG_VIEN_TOI_DA):
            if n < CHUNG_TOI_THIEU:
                break
            s_dang = jaccard(x["dang"], cau[j]["dang"]) * 100
            if s_dang < nguong_ghi:
                continue
            ket.append((s_dang, jaccard(x["chu"], cau[j]["chu"]) * 100, cau[j]["ma"]))
        if not ket:
            continue
        ket.sort(key=lambda k: (-k[1], -k[0]))
        kq.append((x["ma"], [(ma, round(s_chu), round(s_dang)) for s_dang, s_chu, ma in ket[:3]]))
    return kq


def main():
    t0 = time.time()
    gc, _, sa = X.ket_noi()
    print("Tài khoản dịch vụ:", sa, flush=True)
    kho = gc.open_by_key(X.ID_KHO_CHUNG)
    nut = doc_nut(kho)
    if nut.get("KIEM_TRA_TRUNG_LAP", "true").lower() in ("false", "0", "no", "off", "tat", "tắt"):
        print("⏹️ KIEM_TRA_TRUNG_LAP đang tắt – nghỉ lượt này.")
        nhip(kho, "Lượt %s: công tắc KIEM_TRA_TRUNG_LAP đang tắt, không lập chỉ mục." % dt.datetime.now(X.TZ).strftime("%d/%m/%Y %H:%M"))
        return
    nguong = doc_nguong_ghi(nut)
    cau = doc_cau(kho.worksheet(TAB_NH).get_all_values())
    print("Đọc %d câu (bỏ câu Loại, câu quá ngắn)." % len(cau), flush=True)

    luc = dt.datetime.now(X.TZ).strftime("%d/%m/%Y %H:%M")
    dong = [TIEU_DE]
    for ma, ds in tinh_chi_muc(cau, nguong):
        hang = [ma]
        for ma2, s_chu, s_dang in ds:
            hang += [ma2, s_chu, s_dang]
        hang += [""] * (len(TIEU_DE) - 1 - len(hang)) + [luc]
        dong.append(hang)
    so_cap = len(dong) - 1

    try:
        tab = kho.worksheet(TAB_CM)
    except Exception:
        tab = kho.add_worksheet(TAB_CM, rows=max(100, len(dong) + 10), cols=len(TIEU_DE))
    if tab.row_count < len(dong) + 5:
        tab.add_rows(len(dong) + 5 - tab.row_count)
    tab.update(range_name="A1", values=dong, value_input_option="RAW")
    if tab.row_count > len(dong):          # xoá phần dư của đêm trước SAU khi đã ghi xong
        tab.batch_clear(["A%d:K%d" % (len(dong) + 1, tab.row_count)])
    rat_giong = sum(1 for h in dong[1:] if isinstance(h[2], int) and h[2] >= 90)
    doi_so = sum(1 for h in dong[1:] if isinstance(h[2], int) and isinstance(h[3], int) and h[3] >= 85 and h[2] < 90)
    tom = "Chỉ mục %s: %d câu, %d câu có câu giống ≥%d%%; %d gần như chép lại (chữ ≥90%%), %d cùng dạng đổi số liệu. %.0f giây." % (
        luc, len(cau), so_cap, nguong, rat_giong, doi_so, time.time() - t0)
    print("📊 " + tom, flush=True)
    nhip(kho, tom)


def nhip(kho, ghi_chu):
    try:
        t = kho.worksheet(X.TAB_AGENT)
        ten, ten_agent = t.col_values(1), "Xưởng chỉ mục trùng (Python)"
        luc = dt.datetime.now(X.TZ).strftime("%d/%m/%Y %H:%M")
        if ten_agent in ten:
            dong = ten.index(ten_agent) + 1
        else:
            dong = len(ten) + 1
            t.update(range_name="A%d:D%d" % (dong, dong), values=[[ten_agent, "Miễn phí", "", 26]], value_input_option="USER_ENTERED")
        t.update(range_name="E%d" % dong, values=[[luc]], value_input_option="USER_ENTERED")
        t.update(range_name="G%d" % dong, values=[[ghi_chu[:300]]], value_input_option="RAW")
    except Exception as e:
        print("Không ghi được nhịp chạy:", e)


if __name__ == "__main__":
    main()
