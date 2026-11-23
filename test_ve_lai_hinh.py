# -*- coding: utf-8 -*-
"""test_ve_lai_hinh.py – kiểm ve_lai_hinh.py KHÔNG cần khoá, KHÔNG gọi mạng (Gemini, GitHub, Drive đều giả lập).
Sai kết quả mong đợi thì thoát mã khác 0 để Actions báo đỏ."""
import json
import os

os.environ.pop("GITHUB_TOKEN", None)
import ve_lai_hinh as V

PNG0 = b"\x89PNG\r\n\x1a\n" + b"0" * 20

# ---------------------------------------------------------------- 1. kiểm spec · biểu thức an toàn
for bt in ("2*x**2", "2*sin(pi*x/2)+1", "3*x^2-1", "exp(-x/2)"):
    V.kiem_bieu_thuc(bt)
for xau in ("__import__('os')", "x.real", "open('f')", "lambda: 1", "x;1", "evil(x)", "a+1"):
    try:
        V.kiem_bieu_thuc(xau); raise SystemExit("PHẢI từ chối biểu thức: %r" % xau)
    except ValueError:
        pass
for xau in ({"loai": "gi_do"}, {"loai": "so_do", "so_do": [{"k": "phep_thuat"}]}, {"loai": "so_do", "so_do": [{"k": "doan", "a": [0, 0]}]},
            {"loai": "do_thi", "do_thi": {"truc_x": {"min": 5, "max": 1}, "truc_y": {"min": 0, "max": 1}, "duong": []}},
            {"loai": "so_do", "so_do": [{"k": "doan", "a": [0, "x"], "b": [1, 1]}]}):
    try:
        V.chuan_spec(xau); raise SystemExit("PHẢI từ chối spec: %r" % (xau,))
    except ValueError:
        pass
print("kiểm spec + biểu thức OK")

# ---------------------------------------------------------------- 2. vẽ thật bằng matplotlib
DT = {"loai": "do_thi", "do_thi": {"truc_x": {"nhan": "t (s)", "min": 0, "max": 10, "cac_moc": [{"v": 4}]},
      "truc_y": {"nhan": "v (m/s)", "min": 0, "max": 12, "cac_moc": [{"v": 6}]},
      "duong": [{"kieu": "gap_khuc", "diem": [[0, 2], [4, 6], [10, 6]]}, {"kieu": "ham", "bieu_thuc": "2*sin(pi*x/2)+4", "tu": 0, "den": 10, "net": "dut"}],
      "duong_doi": [{"x": 4, "y": 6}]}}
SD = {"loai": "so_do", "rong": 7, "so_do": [
    {"k": "nguon", "a": [0, 0], "b": [0, 3], "nhan": "$E$"}, {"k": "doan", "a": [0, 3], "b": [4, 3]},
    {"k": "dien_tro", "a": [4, 3], "b": [4, 0], "nhan": "$R_1$"}, {"k": "doan", "a": [4, 0], "b": [0, 0]},
    {"k": "dong_ho", "tam": [2, 0], "r": 0.4, "chu": "A"}, {"k": "lo_xo", "a": [6, 1], "b": [9, 1], "so_vong": 6},
    {"k": "mui_ten", "a": [9, 2], "b": [11, 2], "nhan": "$\\vec{F}$"}, {"k": "chu", "vt": [5, 4], "noi_dung": "(a)"}]}
for sp in (DT, SD):
    png, nhan = V.ve(V.chuan_spec(sp))
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 3000, "PNG không hợp lệ"
    assert nhan, "không thu được nhãn"
print("vẽ đồ thị + sơ đồ OK")

# ---------------------------------------------------------------- 3. cổng luật bằng code
DE = "Một vật chuyển động có đồ thị vận tốc theo thời gian như hình. Vận tốc đạt 6 m/s tại t = 4 s rồi giữ không đổi đến 10 s."
MT = V.mo_ta_hinh(DE + " [Hình: đồ thị v-t, đi từ (0; 2) lên (4; 6), sau đó nằm ngang đến t = 10 s]")
assert len(MT) == 1
sp = V.chuan_spec(DT)
loi, cb = V.kiem_luat(sp, V.ve(sp)[1], DE, "", "24", MT)
assert not loi, loi
# số bịa
sp2 = json.loads(json.dumps(DT)); sp2["do_thi"]["truc_y"]["cac_moc"].append({"v": 9, "nhan": "9"})
s2 = V.chuan_spec(sp2); loi, _ = V.kiem_luat(s2, V.ve(s2)[1], DE, "", "24", MT)
assert any("không có trong đề" in l for l in loi), loi
# lộ đáp án (đáp án 24 không có trong đề)
sp3 = json.loads(json.dumps(DT)); sp3["do_thi"]["diem"] = [{"x": 4, "y": 6, "nhan": "24"}]
s3 = V.chuan_spec(sp3); loi, _ = V.kiem_luat(s3, V.ve(s3)[1], DE, "", "24", MT)
assert any("không có trong đề" in l or "lộ đáp án" in l for l in loi), loi
# mô tả có số mà hình thiếu: mô tả nhắc 12 nhưng đồ thị không thể hiện
MT2 = V.mo_ta_hinh("[Hình: đồ thị có các mốc 4, 6 và 12]")
loi, _ = V.kiem_luat(sp, V.ve(sp)[1], DE + " và 12", "", "", MT2)
assert any("chưa thể hiện" in l for l in loi), loi
# [[DO_THI]] JSON: số 3 trong dữ liệu phải có trên hình
MT3 = V.mo_ta_hinh('x [[DO_THI: {"x":[0,4,10],"y":[2,6,6],"font_size":14}]]')
need = V.so_can_co_tren_hinh(MT3)
assert need == {2.0, 4.0, 6.0, 10.0}, need          # bỏ 0 (và font_size), giữ số liệu
print("cổng luật OK")

# ---------------------------------------------------------------- 4. luồng xử lí một câu (Gemini / tải ảnh / GitHub giả)
HANG = {"spec": [], "ket_luan": "khong_khop", "nhin": [], "prompts": [], "up": 0}


def goi_gia(prompt, anh=(), models=(), timeout=0):
    HANG["prompts"].append(prompt)
    if "BẢN MÔ TẢ DỮ LIỆU" in prompt:
        return json.dumps(HANG["spec"].pop(0))
    if "Các ảnh đính kèm" in prompt:
        return json.dumps({"ket_luan": HANG["ket_luan"], "ly_do": "chiều mũi tên sai"})
    d = HANG["nhin"].pop(0) if HANG["nhin"] else {"khop": True}
    return json.dumps(d)


V.GOI = goi_gia
V.tai_anh = lambda cell, drive=None, toi_da=4: [PNG0] if V.tach_link(cell) else []
V.day_len_repo = lambda png, ma: (HANG.__setitem__("up", HANG["up"] + 1) or "https://raw.githubusercontent.com/o/r/main/images/ve_lai/%s_x.png" % ma)
os.environ["GITHUB_TOKEN"] = "gia"
X = {"ma": "q1", "noi_dung": DE + " [Hình: đồ thị v-t, đi từ (0; 2) lên (4; 6), sau đó nằm ngang đến t = 10 s]", "phuong_an": "A. 1\nB. 2\nC. 3\nD. 4",
     "dap_an": "24", "link_anh": "https://raw.githubusercontent.com/o/r/main/images/cu.png"}


def moi(**kw):
    HANG.update({"spec": [json.loads(json.dumps(DT))], "ket_luan": "khong_khop", "nhin": [], "prompts": [], "up": 0}); HANG.update(kw)


# 4a. hình cũ KHỚP → giữ nguyên, không vẽ, không đẩy
moi(ket_luan="khop")
k = V.xu_li_cau(dict(X), None, ["m"])
assert k["hanh_dong"] == "khop" and k["link_moi"] is None and V.DAU_HINH in k["ghi"] and HANG["up"] == 0 and len(HANG["prompts"]) == 1, k
# 4b. hình cũ SAI, vẽ được → thay, link cũ lưu trong ghi chú
moi()
k = V.xu_li_cau(dict(X), None, ["m"])
assert k["hanh_dong"] == "da_ve_lai" and k["link_moi"].endswith("q1_x.png") and "cu.png" in k["ghi"] and V.DAU_HINH in k["ghi"] and HANG["up"] == 1, k
# 4c. lần vẽ đầu có số bịa, lần hai đúng → thành công ở lần 2 và lỗi được đưa lại cho model
bia = json.loads(json.dumps(DT)); bia["do_thi"]["truc_y"]["cac_moc"].append({"v": 9, "nhan": "9"})
moi(spec=[bia, json.loads(json.dumps(DT))])
k = V.xu_li_cau(dict(X), None, ["m"])
assert k["hanh_dong"] == "da_ve_lai" and "lần vẽ 2" in k["ghi"], k
assert any("SỬA HẾT" in p and "số 9" in p for p in HANG["prompts"]), "lỗi luật chưa được đưa lại cho model"
# 4d. model nhìn lại chê → vẽ lại; chê mãi → không gắn hình lỗi, hình cũ SAI bị gỡ
chê = {"khop": False, "sai_lech": ["đoạn đầu phải đi lên, hình vẽ đi xuống"], "thua": [], "thieu": []}
moi(spec=[json.loads(json.dumps(DT)) for _ in range(3)], nhin=[chê, chê, chê])
k = V.xu_li_cau(dict(X), None, ["m"])
assert k["hanh_dong"] == "go_hinh" and k["link_moi"] == "" and "cu.png" in k["ghi"] and HANG["up"] == 0, k
# 4e. hình cũ chỉ "không chắc" + không vẽ được → GIỮ hình cũ
moi(ket_luan="khong_chac", spec=[json.loads(json.dumps(DT)) for _ in range(3)], nhin=[chê, chê, chê])
k = V.xu_li_cau(dict(X), None, ["m"])
assert k["hanh_dong"] == "giu_cu" and k["link_moi"] is None, k
# 4f. đề thiếu dữ kiện → không vẽ bừa
moi(spec=[{"du_du_lieu": False, "ly_do_thieu": "không nói đồ thị đi qua đâu"}])
k = V.xu_li_cau(dict(X), None, ["m"])
assert k["hanh_dong"] == "go_hinh" and "thiếu dữ liệu" in k["ghi"], k
# 4g. không có GITHUB_TOKEN → không làm gì (không gỡ hình cũ)
del os.environ["GITHUB_TOKEN"]
moi()
k = V.xu_li_cau(dict(X), None, ["m"])
assert k["hanh_dong"] == "khong_lam_gi" and k["link_moi"] is None and not k["ghi"], k
os.environ["GITHUB_TOKEN"] = "gia"
# 4h. câu không có mô tả hình và không nhắc hình → bỏ qua, 0 lượt AI
moi()
k = V.xu_li_cau({"ma": "q2", "noi_dung": "Tính động năng của vật 2 kg chuyển động với tốc độ 3 m/s.", "phuong_an": "", "dap_an": "", "link_anh": ""}, None, ["m"])
assert k["hanh_dong"] == "bo_qua" and not HANG["prompts"], k
# 4i. chưa có hình + mô tả đủ → vẽ và gắn
moi()
k = V.xu_li_cau(dict(X, link_anh=""), None, ["m"])
assert k["hanh_dong"] == "da_ve_lai" and HANG["up"] == 1, k
print("luồng một câu OK")

# ---------------------------------------------------------------- 5. nối vào duyet_cau (xu_li_ds)
moi()
x1 = dict(X, dong=2, loi_nang=[], nghi_van=[], ghi_chu=[], sua={}, kiem_tra_cu="")
x2 = dict(X, ma="q3", dong=3, loi_nang=[], nghi_van=[], ghi_chu=[], sua={}, kiem_tra_cu="[hình 20/11: hình đang gắn khớp đề]")     # đã xử lí → bỏ qua
x3 = dict(X, ma="q4", dong=4, loi_nang=["Trùng hẳn"], nghi_van=[], ghi_chu=[], sua={}, kiem_tra_cu="")                              # lỗi nặng → bỏ qua
doi = V.xu_li_ds([x1, x2, x3], None, ["m"], chi_bao=False)
assert doi == 1 and x1["sua"]["link_anh"].endswith("q1_x.png") and x1["hinh_ve_lai"] and x1["link_anh"] == x1["sua"]["link_anh"], x1
assert not x2["sua"] and not x3["sua"] and not x2["ghi_chu"] and not x3["ghi_chu"]
moi(spec=[json.loads(json.dumps(DT)) for _ in range(3)], nhin=[chê, chê, chê])
x4 = dict(X, dong=5, loi_nang=[], nghi_van=[], ghi_chu=[], sua={}, kiem_tra_cu="")
V.xu_li_ds([x4], None, ["m"], chi_bao=False)
assert x4["sua"]["link_anh"] == "" and x4["link_anh"] == "" and any("cần người xem" in n for n in x4["nghi_van"]), x4
# chạy hai lần không đổi: câu đã có dấu "[hình" thì bỏ qua
x4["kiem_tra_cu"] = x4["ghi_chu"][0]
moi(); n_truoc = len(x4["ghi_chu"])
V.xu_li_ds([x4], None, ["m"], chi_bao=False)
assert len(x4["ghi_chu"]) == n_truoc and not HANG["prompts"]
# chạy thử (chỉ báo): không đổi Sheet, có lưu PNG xem thử
moi()
x5 = dict(X, ma="q5", dong=6, loi_nang=[], nghi_van=[], ghi_chu=[], sua={}, kiem_tra_cu="")
V.xu_li_ds([x5], None, ["m"], chi_bao=True)
assert not x5["sua"] and HANG["up"] == 0 and os.path.exists("ve_lai_xem_thu/q5.png") and "CHẠY THỬ" in x5["ghi_chu"][0], x5
os.remove("ve_lai_xem_thu/q5.png"); os.rmdir("ve_lai_xem_thu")
print("nối duyet_cau OK")

# ---------------------------------------------------------------- 6. cờ mặc định TẮT
os.environ.pop("VE_LAI_HINH", None)
assert not V.bat()
os.environ["VE_LAI_HINH"] = "true"
assert V.bat()
print("\nTẤT CẢ TEST ve_lai_hinh ĐẠT")
