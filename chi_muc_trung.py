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


def chuan_chu(s, bo_so=False):
    s = X.bo_dau(s)                                    # bỏ dấu, bỏ $ và lệnh LaTeX, chỉ còn a-z0-9
    if bo_so:
        s = re.sub(r"\b\d+\b", " ", s)
    return re.sub(r"\s+", " ", s).strip().split(" ")


def cum(tu, n=3):
    tu = [t for t in tu if t]
    if len(tu) < n:
        return {" ".join(tu)} if tu else set()
    return {" ".join(tu[i:i + n]) for i in range(len(tu) - n + 1)}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def main():
    t0 = time.time()
    gc, _, sa = X.ket_noi()
    print("Tài khoản dịch vụ:", sa, flush=True)
    kho = gc.open_by_key(X.ID_KHO_CHUNG)
    d = kho.worksheet(TAB_NH).get_all_values()
    td = [t.strip() for t in d[0]]
    c = {t: td.index(t) for t in ["Mã câu", "Nội dung", "Phương án", "Trạng thái duyệt"] if t in td}
    cau = []
    for r in d[1:]:
        r = r + [""] * (len(td) - len(r))
        ma, nd = r[c["Mã câu"]].strip(), r[c["Nội dung"]].strip()
        if not ma or len(nd) < 15 or r[c["Trạng thái duyệt"]].strip() == "Loại":
            continue
        van = nd + " " + r[c["Phương án"]]
        cau.append({"ma": ma, "chu": cum(chuan_chu(van)), "dang": cum(chuan_chu(van, bo_so=True))})
    print("Đọc %d câu (bỏ câu Loại, câu quá ngắn)." % len(cau), flush=True)

    # chỉ mục ngược trên cụm "dạng" (bỏ số) – tìm được cả câu đổi số liệu
    df = Counter(g for x in cau for g in x["dang"])
    chi_muc = defaultdict(list)
    for i, x in enumerate(cau):
        for g in x["dang"]:
            if df[g] <= DF_TOI_DA:
                chi_muc[g].append(i)

    dong, so_cap = [TIEU_DE], 0
    luc = dt.datetime.now(X.TZ).strftime("%d/%m/%Y %H:%M")
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
            if s_dang < NGUONG_GHI:
                continue
            ket.append((s_dang, jaccard(x["chu"], cau[j]["chu"]) * 100, cau[j]["ma"]))
        if not ket:
            continue
        ket.sort(key=lambda k: (-k[1], -k[0]))
        hang = [x["ma"]]
        for s_dang, s_chu, ma in ket[:3]:
            hang += [ma, round(s_chu), round(s_dang)]
        hang += [""] * (len(TIEU_DE) - 1 - len(hang)) + [luc]
        dong.append(hang)
        so_cap += 1

    try:
        tab = kho.worksheet(TAB_CM)
    except Exception:
        tab = kho.add_worksheet(TAB_CM, rows=max(100, len(dong) + 10), cols=len(TIEU_DE))
    tab.clear()
    if tab.row_count < len(dong) + 5:
        tab.add_rows(len(dong) + 5 - tab.row_count)
    tab.update(range_name="A1", values=dong, value_input_option="RAW")
    rat_giong = sum(1 for h in dong[1:] if isinstance(h[2], int) and h[2] >= 90)
    doi_so = sum(1 for h in dong[1:] if isinstance(h[2], int) and isinstance(h[3], int) and h[3] >= 85 and h[2] < 90)
    tom = "Chỉ mục %s: %d câu, %d câu có câu giống ≥%d%%; %d gần như chép lại (chữ ≥90%%), %d cùng dạng đổi số liệu. %.0f giây." % (
        luc, len(cau), so_cap, NGUONG_GHI, rat_giong, doi_so, time.time() - t0)
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
