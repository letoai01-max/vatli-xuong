"""
kiem_thu_v2.py – KIỂM THỬ giao thức v2, chuẩn hoá đề và xuất Word. Chạy: python kiem_thu_v2.py [thư_mục_ra]
Không cần khoá Google: tự giả lập thư viện Google khi máy chưa cài (xuat_word.py nạp chúng ở đầu tệp).
Cần: pandoc, python-docx, matplotlib. Kết quả: <thư_mục_ra>/KiemThu_HS.docx, KiemThu_GV.docx
"""
import sys
import types

for ten in ("gspread", "googleapiclient", "googleapiclient.http", "googleapiclient.discovery", "kiem_dinh_de"):
    try:
        __import__(ten)
    except ImportError:
        m = types.ModuleType(ten)
        m.MediaFileUpload = m.MediaIoBaseDownload = m.MediaIoBaseUpload = object
        sys.modules[ten] = m

import chuan_de as CD
import giao_thuc as GT
import xuat_de_v2 as X

DE_MAU = {
    "phan1": [
        {"cauHoi": "Một vật dao động điều hòa với phương trình $x = 5\\cos(4\\pi t)$ (cm). Chu kì dao động là", "A": "0.5 s", "B": "2 s", "C": "0,25 s", "D": "4 s", "dapAn": "A"},
        {"cauHoi": "Cho đồ thị vận tốc – thời gian của vật. Quãng đường vật đi được trong 4 s đầu là", "A": "8 m", "B": "16 m", "C": "20 m", "D": "24 m", "dapAn": "b",
         "hinhAnh": {"loai": "dothi", "kieuDoThi": "line", "chuThich": "Hình 1. Đồ thị v – t", "nhanTrucX": "t (s)", "nhanTrucY": "v (m/s)",
                     "duLieu": [{"ten": "Vật 1", "diem": [[0, 2], [4, 6]]}]}},
    ],
    "phan2": [
        {"cauHoi": "Một khối khí lí tưởng thực hiện quá trình đẳng nhiệt ở $27^\\circ C$.", "A": "Áp suất tăng khi thể tích giảm.", "B": "Tích $pV$ không đổi.",
         "C": "Nội năng của khí tăng.", "D": "Khí nhận nhiệt thì sinh công.", "dapAn": "a-Đúng, b-Đúng, c-Sai, d-Đúng"},
        {"cauHoi": "Bảng số liệu thí nghiệm khảo sát dao động của con lắc đơn.", "A": "Chu kì tăng khi chiều dài tăng.", "B": "$T$ tỉ lệ thuận với $l$.",
         "C": "$T^2$ tỉ lệ với $l$.", "D": "Gia tốc trọng trường xác định được từ thí nghiệm.", "dapAn": "ĐSĐS",
         "hinhAnh": {"loai": "bang", "chuThich": "Bảng 1. Kết quả đo", "tieuDeCot": ["l (m)", "T (s)"], "dong": [["0,25", "1,00"], ["1,00", "2,01"]]}},
    ],
    "phan3": [{"cauHoi": "Tính tần số góc của mạch dao động LC có $L = 2\\text{ mH}$ và $C = 5\\text{ μF}$ (rad/s).", "dapAn": "10000"}],
    "phan4": [{"cauHoi": "Một vật khối lượng $m = 0,5\\text{ kg}$ rơi tự do từ độ cao $h = 20\\text{ m}$. Tính vận tốc khi chạm đất.",
               "dapAn": "- Áp dụng $v = \\sqrt{2gh}$\n- Thay số: $v = \\sqrt{2 \\cdot 10 \\cdot 20} = 20\\text{ m/s}$\n=> Đáp số: $v = 20\\text{ m/s}$"}],
}


def kiem(dieu_kien, nhan):
    print(("✅ " if dieu_kien else "❌ ") + nhan)
    if not dieu_kien:
        kiem.loi += 1


kiem.loi = 0


def main():
    ra = sys.argv[1] if len(sys.argv) > 1 else "ket_qua_kiem_thu"
    # --- chuẩn hoá đáp án
    kiem(CD.chuan_dap_an_p1("b") == "B", "Phần I: 'b' → B")
    kiem(CD.chuan_dap_an_p2("a-Đúng, b-Đúng, c-Sai, d-Đúng") == "a) Đ, b) Đ, c) S, d) Đ", "Phần II: dạng 'a-Đúng…' → chuẩn")
    kiem(CD.chuan_dap_an_p2("ĐSĐS") == "a) Đ, b) S, c) Đ, d) S", "Phần II: 'ĐSĐS' → chuẩn")
    kiem(CD.chuan_dap_an_p2({"a": True, "b": False, "c": True, "d": False}) == "a) Đ, b) S, c) Đ, d) S", "Phần II: dict → chuẩn")
    kiem(CD.chuan_dap_an_p2("a) Đ, b) S") == "a) Đ, b) S", "Phần II: thiếu ý → giữ nguyên để luật báo lỗi")
    kiem(CD.chuan_dap_an_p3(" 12,5 ") == "12.5", "Phần III: '12,5' → 12.5")
    kiem(CD.chuan_dap_an_p4("Bước 1\\n=> Đáp số: 2").split("\n") == ["- Bước 1", "=> Đáp số: 2"], "Phần IV: tách dòng '\\n', thêm '- '")
    # --- chuẩn hoá đề + LaTeX
    de, ghi = CD.chuan_hoa_de(DE_MAU)
    kiem("0{,}5" in de["phan1"][0]["A"] or de["phan1"][0]["A"] == "0.5 s", "đề giữ nguyên chữ thường ngoài công thức")
    kiem("\\mu\\text{F}" in de["phan3"][0]["cauHoi"], "μF trong $…$ → \\mu\\text{F} (không phải \\muF)")
    kiem(CD.kiem_tra_latex(de) == [], "đề mẫu không có lỗi LaTeX: %s" % CD.kiem_tra_latex(de))
    xau = {"phan1": [{"cauHoi": "Tính \\frac{1}{2}mv^2 của vật", "A": "$x", "B": "ok", "C": "ok", "D": "ok", "dapAn": "A"}]}
    loi = CD.kiem_tra_latex(xau)
    kiem(any("ngoài" in x for x in loi) and any("lẻ" in x for x in loi), "bắt được lệnh ngoài $ và $ lẻ: %d lỗi" % len(loi))
    cu = {"phan_I_trac_nghiem_nhieu_lua_chon": [{"cau": 1, "cau_hoi": "Q", "lua_chon": {"A": "1", "B": "2", "C": "3", "D": "4"}, "dap_an": "B"}],
          "phan_II_trac_nghiem_dung_sai": [{"cau": 1, "noi_dung_dan": "D", "menh_de": {"a": "1", "b": "2", "c": "3", "d": "4"},
                                            "dap_an": {"a": True, "b": False, "c": True, "d": False}}]}
    mo = CD.tu_dinh_dang_cu(cu)
    kiem(mo["phan1"][0]["B"] == "2" and mo["phan2"][0]["C"] == "3", "đổi mẫu cũ của tao_de.py sang phan1..phan4")
    h = CD.chuan_hinh_anh('{"type":"table","rows":[["a","b"],["1","2"]]}')
    kiem(h and h["loai"] == "bang" and h["tieuDeCot"] == ["a", "b"] and h["hopLe"], "hinhAnh dạng chuỗi JSON → bảng chuẩn")
    # --- giao thức
    goi = {"phienBan": 2, "loai": "tao_de", "ma": "TD-1", "cauHinh": {"grade": "10"}, "trangThai0": {"yc": {"p1": 2, "p2": 2, "p3": 1, "p4": 1}},
           "dich": {"docxHS": "a", "docxGV": "b"}}
    kiem(GT.kiem_goi(goi) == [], "gói v2 hợp lệ")
    kiem(len(GT.kiem_goi({"phienBan": 2, "loai": "tao_de", "ma": "x", "cauHinh": {"grade": "9"}})) >= 2, "gói v2 thiếu/sai bị báo lỗi")
    kiem(GT.kiem_goi({"grade": "10", "B9": "x", "maDe": "TD-1"}) == [], "gói v1 (chỉ ô B…) vẫn đọc được")

    class GiaDrive:                      # ghi ra bộ nhớ thay vì Drive
        pass
    ghi_lai = []
    GT.ghi_json_drive = lambda d, f, nd: ghi_lai.append(nd)
    ph = GT.Phien(GiaDrive(), "kq", goi)
    ph.tien_do("soan_phan_1", 20, "bắt đầu")
    ph.xong(de, tep={"docxHS": "a"})
    kiem(ghi_lai and ghi_lai[-1]["trangThai"] == "XONG" and ghi_lai[-1]["phanTram"] == 100 and ghi_lai[0]["trangThai"] == "DANG_LAM", "Phien ghi DANG_LAM rồi XONG (có tiết chế)")
    # --- xuất Word
    kq = X.xuat_de(DE_MAU, {"grade": "10", "tenDe": "ĐỀ KIỂM TRA THỬ", "thoiGianPhut": 45}, ra, ten_goc="KiemThu")
    kiem(not [c for c in kq["canhBao"] if "pandoc" in c], "pandoc không cảnh báo công thức")
    print("   ", kq["thongKe"], "cảnh báo:", kq["canhBao"], "lỗi latex:", kq["loiLatex"])
    import os
    kiem(all(os.path.getsize(kq[b]) > 5000 for b in ("hs", "gv")), "tạo được 2 tệp Word HS và GV")
    from docx import Document
    xml = Document(kq["gv"]).element.xml
    kiem("<m:oMath" in xml, "công thức thành phương trình Word (OMML)")
    kiem(len(Document(kq["gv"]).tables) == 4, "GV có 3 bảng đáp án + 1 bảng số liệu (%d bảng)" % len(Document(kq["gv"]).tables))
    kiem("pic:pic" in xml, "đồ thị được nhúng vào tệp")
    kiem("pic:pic" in Document(kq["hs"]).element.xml and "Đáp án" not in "".join(p.text for p in Document(kq["hs"]).paragraphs), "bản HS có đồ thị, không có đáp án")
    print("\n%s" % ("TẤT CẢ ĐẠT" if not kiem.loi else "%d MỤC LỖI" % kiem.loi))
    return 1 if kiem.loi else 0


if __name__ == "__main__":
    sys.exit(main())
