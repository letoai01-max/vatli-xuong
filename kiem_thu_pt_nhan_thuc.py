"""
kiem_thu_pt_nhan_thuc.py – TEST cho chốt mức nhận thức, đối chiếu đáp án chính thức, mục theo chương. [25/11/2026]
Chạy được không cần khoá, không gọi mạng; không cần duyet_cau (truyền hàm so khớp giả). Sai thì thoát mã khác 0.
    python kiem_thu_pt_nhan_thuc.py
"""
import sys
import pt_danh_muc as DM
import pt_nhan_thuc as NT
import pt_so_khop as SK
import pt_danh_gia as DG

LOI = []


def dung(dieu_kien, ten):
    print(("  ✓ " if dieu_kien else "  ✗ ") + ten)
    if not dieu_kien:
        LOI.append(ten)


# --- hàm so khớp giả thay duyet_cau (cùng chữ ký)
def _loai(d): return {"TN": "TN", "DS": "DS", "TLN": "TL", "TL": "TL"}[d]
def _chuan(loai, s):
    s = str(s or "").strip()
    return s.upper() if loai == "TN" else s
def _khop(loai, a, b):
    if loai == "DS": return SK.tach_y_ds(a) == SK.tach_y_ds(b)
    if loai == "TL":
        try: return abs(float(str(a).replace(",", ".")) - float(str(b).replace(",", "."))) <= 0.02 * abs(float(str(b).replace(",", ".")))
        except ValueError: return False
    return _chuan(loai, a) == _chuan(loai, b)
HAM = (_loai, _chuan, _khop)

print("1. Sáu tiêu chí & luật văn bản")
tc_cao = {k: "VD" for k in DM.TIEU_CHI_KHOA}; tc_cao["yeu_cau_ket_qua"] = "VDC"
dung(NT.muc_theo_tieu_chi(tc_cao) == "VD", "mức theo tiêu chí = mức cao thứ nhì (một tiêu chí lẻ không kéo mức lên)")
dung(NT.muc_theo_tieu_chi({"huy_dong_kien_thuc": "NB"}) is None, "thiếu tiêu chí → không bỏ phiếu")
cau_nho = {"dang": "TN", "co_hinh": False, "noi_dung": "Đơn vị của cường độ dòng điện là gì?"}
dung(NT.dau_hieu_van_ban(cau_nho)["tran"] == "TH", "câu hỏi đơn vị, không số liệu → trần TH")
dung(bool(NT.kiem_nhat_quan({**cau_nho, "muc_do": "VD"})), "xếp VD cho câu nhớ đơn vị bị gắn cờ")
dung(not NT.kiem_nhat_quan({**cau_nho, "muc_do": "NB"}), "NB hợp lí → không cờ")
dung(NT.dau_hieu_van_ban({"dang": "TN", "noi_dung": "Hãy thiết kế thí nghiệm kiểm chứng định luật."})["san"] == "VD", "thiết kế thí nghiệm → sàn VD")

print("2. Chốt mức bằng bỏ phiếu")
r = NT.chot_muc({"luot1": "TH", "luot2": "TH", "tieu_chi": "TH", "phan_xu": None})
dung(r["muc_do"] == "TH" and r["tin_cay"] == "cao", "3/3 đồng thuận → cao")
r = NT.chot_muc({"luot1": "VD", "luot2": "TH", "tieu_chi": "TH", "phan_xu": None})
dung(r["muc_do"] == "TH" and r["tin_cay"] == "vừa", "đa số 2/3 → vừa")
r = NT.chot_muc({"luot1": "VD", "luot2": "TH", "tieu_chi": None, "phan_xu": None})
dung(r["muc_do"] == "VD" and r["tin_cay"] == "thấp", "hai phiếu lệch, chưa có trọng tài → thấp, tạm theo lượt 1")
r = NT.chot_muc({"luot1": "VD", "luot2": "TH", "tieu_chi": None, "phan_xu": "TH"})
dung(r["muc_do"] == "TH" and r["tin_cay"] == "vừa", "trọng tài đứng về một phiếu → vừa")
r = NT.chot_muc({"luot1": "NB", "luot2": "VD", "tieu_chi": None, "phan_xu": "VDC"})
dung(r["tin_cay"] == "thấp", "trọng tài khác mọi phiếu → thấp")
r = NT.chot_muc({"luot1": "NB", "luot2": "VDC", "tieu_chi": "VDC", "phan_xu": None})
dung(r["muc_do"] == "VDC" and r["tin_cay"] == "thấp", "phiếu lệch 3 bậc → thấp dù có đa số")
dung(NT.chot_muc({})["tin_cay"] == "thấp", "không phiếu nào → thấp")

print("3. Câu Đúng/Sai chốt từng ý")
g1 = {"muc_do": "VD", "y_ds": [{"y": "a", "muc_do": "NB"}, {"y": "b", "muc_do": "TH"}, {"y": "c", "muc_do": "VD"}, {"y": "d", "muc_do": "VD"}]}
g2 = {"muc_do": "VD", "y_ds": [{"y": "a", "muc_do": "NB"}, {"y": "b", "muc_do": "TH"}, {"y": "c", "muc_do": "VD"}, {"y": "d", "muc_do": "VDC"}]}
c_ds = {"dang": "DS", "ma": "II.1", "noi_dung": "x"}
dung(NT.can_phan_xu(c_ds, g1, g2), "ý d lệch giữa hai lượt → cần trọng tài")
k = NT.chot_cau(c_ds, g1, g2, {"muc_do": "VDC", "y_ds": [{"y": "d", "muc_do": "VDC"}]})
dung(k["y_ds"][3]["muc_do"] == "VDC" and k["muc_do"] == "VDC", "trọng tài chọn VDC cho ý d → mức câu = ý cao nhất")
dung(k["y_ds"][0]["muc_do"] == "NB" and k["y_ds"][0]["tin_cay"] == "cao", "ý a đồng thuận → cao")
k2 = NT.chot_cau(c_ds, g1, g2, {})
dung(k2["y_ds"][3]["tin_cay"] == "thấp" and k2["tin_cay"] == "thấp", "chưa có trọng tài: ý lệch kéo độ tin cậy cả câu xuống thấp")

print("4. Nhận diện đề Bộ")
dung(SK.la_de_bo({"don_vi": "BỘ GIÁO DỤC VÀ ĐÀO TẠO", "ky_thi": "KỲ THI TỐT NGHIỆP TRUNG HỌC PHỔ THÔNG NĂM 2025", "ten_de": "ĐỀ THI THAM KHẢO"})[0], "đề tham khảo của Bộ")
dung(not SK.la_de_bo({"don_vi": "SỞ GD&ĐT HÀ NỘI", "ten_de": "ĐỀ THI THỬ TỐT NGHIỆP THPT"})[0], "đề thi thử → không phải đề Bộ")
dung(not SK.la_de_bo({"ten_de": "Đề thi thử tốt nghiệp THPT quốc gia"}, {"loaiDe": "Đề thi thử"})[0], "'thi thử' luôn loại trừ")
dung(SK.la_de_bo({}, {"loaiDe": "Đề chính thức tốt nghiệp THPT quốc gia"})[0], "giáo viên nhập loại đề chính thức")
dung(SK.la_de_bo({"ten_de": "đề thi thử"}, None, "bo")[0], "ép = bo thắng tự nhận diện")
dung(not SK.la_de_bo({"don_vi": "BỘ GIÁO DỤC VÀ ĐÀO TẠO", "ky_thi": "TỐT NGHIỆP THPT", "ten_de": "ĐỀ"}, None, "khong")[0], "ép = khong thắng tự nhận diện")

print("5. Đối chiếu đáp án")
cau = [
    {"ma": "I.1", "dang": "TN", "dap_an_de": "B"},
    {"ma": "I.2", "dang": "TN", "dap_an_de": "C"},
    {"ma": "II.1", "dang": "DS", "dap_an_de": "a) Đ, b) S, c) Đ, d) S"},
    {"ma": "III.1", "dang": "TLN", "dap_an_de": "2,5"},
    {"ma": "III.2", "dang": "TLN", "dap_an_de": ""},
]
giai = {"I.1": {"da_may": "B", "da_chot": "B", "ket_luan": "KHỚP"},
        "I.2": {"da_may": "A", "da_chot": "A", "ket_luan": "LỆCH_NÊN_SỬA", "do_tin_cay": "vừa", "da_groq": "A"},
        "II.1": {"da_may": "a) Đ, b) Đ, c) Đ, d) S", "ket_luan": "LỆCH_CẦN_XEM"},
        "III.1": {"da_may": "2.5", "da_chot": "2,5", "ket_luan": "KHỚP"},
        "III.2": {"da_may": "7", "da_chot": "7", "ket_luan": "CHỈ_CÓ_MÁY"}}
soan = {"I.1": "B", "I.2": "C", "III.1": "9"}
bo = SK.doi_chieu(cau, giai, soan, True, HAM)
dung(bo["I.1"]["ket_luan_so_khop"] == "KHỚP" and bo["I.1"]["nguon_chot"] == SK.NGUON_BO, "I.1 khớp, nguồn chốt Bộ")
dung(bo["I.2"]["ket_luan_so_khop"] == "KHÔNG KHỚP" and bo["I.2"]["da_chot"] == "C", "I.2 máy lệch → KHÔNG KHỚP nhưng chốt đáp án Bộ")
dung(bo["I.2"]["ket_luan"] == "LỆCH_CẦN_XEM", "đề Bộ không bao giờ 'LỆCH_NÊN_SỬA'")
dung(bo["I.2"]["so_khop"]["soan"] == "KHỚP" and bo["I.2"]["so_khop"]["may"] == "KHÔNG KHỚP", "so từng nguồn riêng: soạn khớp, máy không")
dung("ý b" in bo["II.1"]["chi_tiet_lech"] and "ý a" not in bo["II.1"]["chi_tiet_lech"], "câu Đúng/Sai chỉ ra đúng ý lệch (b)")
dung(bo["III.1"]["ket_luan_so_khop"] == "KHÔNG KHỚP", "nguồn soạn lệch dù máy khớp → KHÔNG KHỚP")
dung(bo["III.2"]["ket_luan_so_khop"] == "CHƯA CÓ ĐÁP ÁN CHÍNH THỨC" and bo["III.2"]["nguon_chot"] == "MÁY / AI", "thiếu đáp án Bộ → không kết luận khớp, dùng máy")
thuong = SK.doi_chieu(cau, giai, {}, False, HAM)
dung(thuong["I.2"]["ket_luan"] == "LỆCH_NÊN_SỬA" and thuong["I.2"]["nguon_chot"] == "MÁY / AI", "đề thường giữ logic cũ")
rong = SK.doi_chieu(cau, {}, {}, True, HAM)
dung(rong["I.1"]["ket_luan_so_khop"] == "CHƯA ĐỐI CHIẾU" and rong["I.1"]["da_chot"] == "B", "không giải máy vẫn chốt đáp án Bộ")

print("6. Đánh giá, mục theo chương")
danh_muc = DM.DANH_MUC_MAC_DINH
cau_truc = DM.CAU_TRUC_MAC_DINH
pt = {"I.1": {"ma_chuong": "10.2", "chuyen_de": "Chuyển động thẳng", "muc_do": "NB", "so_buoc": 1, "tu_tin": "cao"},
      "I.2": {"ma_chuong": "12.3", "chuyen_de": "Cảm ứng", "muc_do": "VD", "so_buoc": 3, "tu_tin": "vừa"},
      "II.1": {"ma_chuong": "99.9", "chuyen_de": "?", "muc_do": "VD", "y_ds": g1["y_ds"], "so_buoc": 3, "tu_tin": "vừa"},
      "III.1": {"ma_chuong": "10.2", "chuyen_de": "Chuyển động thẳng", "muc_do": "TH", "so_buoc": 2, "tu_tin": "cao"},
      "III.2": {"ma_chuong": "11.1", "chuyen_de": "Dao động", "muc_do": "VD", "so_buoc": 3, "tu_tin": "cao"}}
pl2 = {"I.1": {"muc_do": "NB"}, "I.2": {"muc_do": "TH"}, "II.1": {"muc_do": "VD", "y_ds": g2["y_ds"]}, "III.1": {"muc_do": "TH"}, "III.2": {"muc_do": "VD"}}
cau_full = [{**c, "stt": i + 1, "phan": {"I": 1, "II": 2, "III": 3}[c["ma"].split(".")[0]], "so_cau": int(c["ma"].split(".")[1]),
             "noi_dung": "Nội dung câu %s " % c["ma"] + "x" * 400, "phuong_an": ["A. a", "B. b", "C. c", "D. d"], "co_hinh": False} for i, c in enumerate(cau)]
chot = {c["ma"]: NT.chot_cau(c, pt[c["ma"]], pl2[c["ma"]], {"muc_do": "TH"} if c["ma"] == "I.2" else {}) for c in cau_full}
ds = DG.hop_nhat(cau_full, pt, pl2, bo, danh_muc, chot)
dung([c for c in ds if c["ma"] == "II.1"][0]["ma_chuong"] == "KHAC" and [c for c in ds if c["ma"] == "II.1"][0]["ma_chuong_goc"] == "99.9", "mã chương lạ gộp về KHAC, giữ mã gốc")
dung([c for c in ds if c["ma"] == "I.2"][0]["muc_do"] == "TH" and [c for c in ds if c["ma"] == "I.2"][0]["muc_do_phan_xu"] == "TH", "mức chốt theo trọng tài thay mức lượt 1")
dg = DG.danh_gia(ds, cau_truc, DM.MUC_TIEU_MAC_DINH, 50, danh_muc, (), True, "test", True)
tc = {k["ma"]: k for k in dg["theoChuong"]}
dung(tc["10.2"]["so_cau"] == 2 and tc["10.2"]["so_cau_phan"] == {"I": 1, "III": 1}, "chương 10.2: 2 câu (I:1, III:1)")
dung(tc["10.4"]["so_cau"] == 0, "chương không có câu vẫn được liệt kê (so_cau = 0)")
dung(tc["KHAC"]["so_cau"] == 1, "KHAC hiện khi có câu")
dung(sum(k["so_cau"] for k in dg["theoChuong"]) == len(cau_full), "tổng số câu theo chương = tổng số câu")
dung(len(tc["10.2"]["cau"][0]["noi_dung"]) <= DM.DO_DAI_NOI_DUNG_CHUONG and tc["10.2"]["cau"][0]["noi_dung"].endswith("…"), "nội dung được cắt gọn có dấu …")
dung(abs(sum(k["tong_diem"] for k in dg["theoChuong"]) - dg["thongKe"]["tong_diem"]) < 0.01, "tổng điểm theo chương = tổng điểm đề")
dung("### 10.2" in dg["baoCaoChuong"] and "| I.1 |" in dg["baoCaoChuong"], "báo cáo Markdown có tiêu đề chương và bảng câu")
dc = dg["thongKe"]["doi_chieu_dap_an"]
dung(dc["so_cau"]["KHỚP"] == 1 and dc["so_cau"]["KHÔNG KHỚP"] == 3 and dc["so_cau"]["CHƯA CÓ ĐÁP ÁN CHÍNH THỨC"] == 1, "thống kê đối chiếu: 1 khớp, 3 không khớp, 1 chưa có")
dung(any("Đề của Bộ" in x for x in [d["ly_do"][0] for d in dg["canDuyet"] if d["ma"] == "I.2"] + [r for d in dg["canDuyet"] if d["ma"] == "I.2" for r in d["ly_do"]]), "câu không khớp đề Bộ có trong danh sách cần duyệt")
dung("nhat_quan_nhan_thuc" in dg["thongKe"] and dg["thongKe"]["nhat_quan_nhan_thuc"]["so_cau_phan_xu"] == 1, "thống kê nhất quán: 1 câu qua trọng tài")
hai_lan = DG.danh_gia(ds, cau_truc, DM.MUC_TIEU_MAC_DINH, 50, danh_muc, (), True, "test", True)
dung(hai_lan["thongKe"] == dg["thongKe"], "chạy hai lần cho cùng kết quả (Exam Evaluator thuần code)")
cu = DG.danh_gia(DG.hop_nhat(cau_full, pt, pl2, {}), cau_truc, DM.MUC_TIEU_MAC_DINH, 50, danh_muc, (), False, "", False)
dung("theoChuong" not in cu, "tắt công tắc theoChuong → không có mục mới")

print("7. Khung của Bộ: Biết / Hiểu / Vận dụng, đếm theo lệnh hỏi, thành phần năng lực")
dung(sum(sum(v.values()) for t in DM.BANG_NANG_LUC_MINH_HOA.values() for v in t.values()) == 40, "bảng minh hoạ của Bộ cộng đúng 40 lệnh hỏi")
dung(sum(DM.SO_LENH_HOI_MINH_HOA.values()) == 40 and DM.SO_LENH_HOI_MINH_HOA == {"Biết": 16, "Hiểu": 12, "Vận dụng": 12}, "tham chiếu 16/12/12")
for ten, nl in (("Nhận thức vật lí", 0), ("Tim hieu the gioi tu nhien", 1), ("Vận dụng kiến thức", 2), ("???", None)):
    dung(NT.chuan_nang_luc(ten) == (DM.NANG_LUC[nl] if nl is not None else "Chưa rõ"), "chuẩn hoá năng lực: %s" % ten)
dung(NT.muc3("VDC") == "Vận dụng" and NT.muc3("NB") == "Biết", "VDC gộp vào Vận dụng khi báo cáo theo Bộ")
m3 = dg["thongKe"]["muc3"]
dung(m3["so_lenh_hoi"] == 1 + 1 + 4 + 1 + 1, "đếm lệnh hỏi: 4 câu 1 lệnh + câu Đúng/Sai 4 lệnh = 8 (thực %d)" % m3["so_lenh_hoi"])
dung(sum(v["so_lenh_hoi"] for v in m3["muc"].values()) == m3["so_lenh_hoi"], "tổng 3 cấp độ = tổng lệnh hỏi")
nl = dg["maTran"]["nang_luc"]
dung(nl["don_vi"] == "lệnh hỏi" and sum(b["tong"] for b in nl["bang"]) == m3["so_lenh_hoi"], "ma trận năng lực cộng đúng số lệnh hỏi")
dung(nl["minh_hoa_tong_theo_phan_muc"]["I"] == {"Biết": 9, "Hiểu": 6, "Vận dụng": 3} and nl["minh_hoa_tong_theo_phan_muc"]["II"] == {"Biết": 6, "Hiểu": 4, "Vận dụng": 6}, "tổng minh hoạ theo phần khớp bảng của Bộ (9-6-3, 6-4-6)")
dung(any("cấp độ của Bộ" in x for x in dg["nhanXet"]) and any("không phải tỉ lệ bắt buộc" in x for x in dg["nhanXet"]), "nhận xét nêu rõ tỉ lệ Bộ chỉ để tham khảo")
dung(any("khác cấu trúc 40" in x for x in dg["nhanXet"]), "đề không đủ 40 lệnh hỏi → nhắc kiểm tra tách câu")
# đề đúng cấu trúc Bộ: 18 TN + 4 DS + 6 TLN → 40 lệnh hỏi
full = []
for i in range(1, 19): full.append({"ma": "I.%d" % i, "phan": 1, "so_cau": i, "dang": "TN", "muc_do": "TH", "ma_chuong": "10.2", "nang_luc": "Nhận thức vật lí", "noi_dung": "x", "phuong_an": []})
for i in range(1, 5): full.append({"ma": "II.%d" % i, "phan": 2, "so_cau": i, "dang": "DS", "muc_do": "VDC", "ma_chuong": "12.3", "nang_luc": "Vận dụng kiến thức", "noi_dung": "x", "phuong_an": [],
                                   "y_ds": [{"y": k, "muc_do": m, "nang_luc": "Tìm hiểu thế giới tự nhiên"} for k, m in zip("abcd", ("NB", "TH", "VD", "VDC"))]})
for i in range(1, 7): full.append({"ma": "III.%d" % i, "phan": 3, "so_cau": i, "dang": "TLN", "muc_do": "VD", "ma_chuong": "11.1", "nang_luc": "Vận dụng", "noi_dung": "x", "phuong_an": []})
m3f, nlf = DG.thong_ke_theo_bo(full, cau_truc)
dung(m3f["so_lenh_hoi"] == 40, "đề đủ cấu trúc: đúng 40 lệnh hỏi (18 + 16 + 6)")
dung(m3f["muc"]["Biết"]["so_lenh_hoi"] == 4 and m3f["muc"]["Hiểu"]["so_lenh_hoi"] == 18 + 4 and m3f["muc"]["Vận dụng"]["so_lenh_hoi"] == 4 * 2 + 6, "ý Đúng/Sai tính riêng: Biết 4, Hiểu 22, Vận dụng 14")
dung(not any("khác cấu trúc 40" in x for x in DG.nhan_xet({**dg["thongKe"], "muc3": m3f}, dg["maTran"], DM.MUC_TIEU_MAC_DINH)), "đủ 40 lệnh hỏi → không cảnh báo cấu trúc")
dung(nlf["bang"][1]["phan"]["II"]["Hiểu"] == 4, "năng lực lấy theo từng ý Đúng/Sai (Tìm hiểu: 4 ý Hiểu)")

print()
if LOI:
    print("✗ %d kiểm tra hỏng:" % len(LOI)); [print("   -", x) for x in LOI]; sys.exit(1)
print("✓ Tất cả kiểm tra đạt")
