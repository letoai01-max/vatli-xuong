"""
kiem_thu_quota_phut.py – KIỂM THỬ điều phối phút GitHub Actions (quota_phut.py + trung_tam.py + cấu hình + workflow). Không cần khoá, không gọi mạng.
Chạy: python kiem_thu_quota_phut.py   (sai một ca → thoát mã 1 để Actions báo đỏ)
"""
import datetime as dt, io, json, os, random, re, sys, tempfile, contextlib

import quota_phut as Q

LOI = []


def kiem(ten, dieu_kien):
    if not dieu_kien:
        LOI.append(ten)
    print(("✅ " if dieu_kien else "❌ ") + ten)


Q.QUOTA, Q.DU_PHONG, Q.DEM_CUOI, Q.TRAN_KHI_MU, Q.CHI_PHI_LICH = 2000.0, 200.0, 1.0, 60.0, 15.0
Q.CHE_DO = "dieu_phoi"
D = dt.date


def tt_gia(thang_dung, hom_nay_theo_viec=None, hn=D(2026, 11, 10), uoc=None):
    hn_v = hom_nay_theo_viec or {}
    return {"hom_nay": hn, "hom_qua": hn - dt.timedelta(days=1), "thang": hn.strftime("%Y-%m"), "da_dung_thang": float(thang_dung),
            "uoc_repo_thang": float(thang_dung), "co_billing": False, "hom_nay_theo_viec": hn_v, "hom_qua_theo_viec": {}, "thang_theo_viec": {},
            "tuoi_cho": {}, "luot_hom_nay": {}, "luot_thang": {}, "da_dung_hom_nay": float(sum(hn_v.values())), "da_dung_hom_qua": 0.0, "uoc": uoc or {}}


# ---- tên việc ----
kiem("tên việc từ path có @ref", Q.ten_viec({"path": ".github/workflows/duyet_cau.yml@refs/heads/main"}) == "duyet_cau")
kiem("tên việc: chữ hoa → thường (Xuat_de)", Q.ten_viec({"path": ".github/workflows/Xuat_de.yml"}) == "xuat_de")
kiem("tên việc: gạch ngang → gạch dưới (quet-anh-cron)", Q.ten_viec({"path": ".github/workflows/quet-anh-cron.yml"}) == "quet_anh_cron")
os.environ.pop("GH_VIEC", None)
os.environ["GITHUB_WORKFLOW_REF"] = "me/vatli-xuong/.github/workflows/quet-anh-cron.yml@refs/heads/main"
kiem("việc lấy từ GITHUB_WORKFLOW_REF, không theo tên tệp Python", Q.viec_tu_tep("xuat_de.py") == "quet_anh_cron")
os.environ["GH_VIEC"] = "xuat_de"
kiem("GH_VIEC ghi đè (bước phụ xuat_de trong quet-anh-cron)", Q.viec_tu_tep("xuat_de.py") == "xuat_de")
del os.environ["GH_VIEC"], os.environ["GITHUB_WORKFLOW_REF"]
kiem("chạy ngoài Actions: tên tệp + bí danh", Q.viec_tu_tep("quet_bu_hinh_anh.py") == "quet_anh_cron" and Q.viec_tu_tep("tu_giai.py") == "tu_giai")

# ---- ước tính phút từ lượt chạy ----
bay_gio = dt.datetime(2026, 11, 21, 6, 0, tzinfo=dt.timezone.utc)
luot = [
    {"path": ".github/workflows/duyet_cau.yml", "status": "completed", "run_started_at": "2026-11-21T01:00:00Z", "updated_at": "2026-11-21T01:30:10Z"},
    {"path": ".github/workflows/duyet_cau.yml", "status": "in_progress", "run_started_at": "2026-11-21T05:50:00Z"},
    {"path": ".github/workflows/tao_de.yml", "status": "queued", "created_at": "2026-11-21T05:59:00Z"},
    {"path": ".github/workflows/canh_gac.yml", "status": "completed", "run_started_at": "2026-11-20T00:20:00Z", "updated_at": "2026-11-20T00:21:20Z"},
    {"path": ".github/workflows/duyet_cau.yml", "status": "completed", "run_started_at": "2026-11-20T16:47:00Z", "updated_at": "2026-11-20T17:17:00Z"},
]
u = Q.uoc_tinh(luot, bay_gio)
kiem("lượt 30 phút 10 giây → 31 phút", u[("2026-11-21", "duyet_cau")][0] == 31 + 10)
kiem("lượt đang chạy tính đến bây giờ, lượt xếp hàng không tính", ("2026-11-21", "tao_de") not in u and u[("2026-11-21", "duyet_cau")][1] == 2)
kiem("ngày tính theo giờ VN (23h47 VN = 16h47 UTC thuộc ngày VN hôm đó)", u[("2026-11-20", "duyet_cau")][0] == 30 and u[("2026-11-20", "canh_gac")][0] == 2)

bl = Q.tong_tu_billing({"usageItems": [
    {"date": "2026-11-01", "product": "Actions", "quantity": 100, "unitType": "minutes"},
    {"date": "2026-11-02", "product": "Actions", "quantity": 50.5, "unitType": "Minutes"},
    {"date": "2026-11-02", "product": "Packages", "quantity": 3, "unitType": "gigabytes"}]})
kiem("billing chỉ cộng Actions + minutes", bl["tong"] == 150.5 and Q.tong_tu_billing({}) is None)

# ---- tổng hợp: hôm qua, hôm nay, cả tháng theo việc ----
sl = {"hom_nay": D(2026, 11, 21), "billing": None, "uoc": {("2026-11-20", "duyet_cau"): [40, 2], ("2026-11-21", "canh_gac"): [2, 1],
                                                            ("2026-11-05", "tao_de"): [30, 3], ("2026-10-31", "duyet_cau"): [99, 1]}}
t = Q.tong_hop(sl)
kiem("hôm qua tính đúng, riêng từng việc", t["da_dung_hom_qua"] == 40 and t["hom_qua_theo_viec"] == {"duyet_cau": 40})
kiem("cả tháng không lẫn tháng trước", t["da_dung_thang"] == 72 and t["thang_theo_viec"]["duyet_cau"] == 40)
t1 = Q.tong_hop({"hom_nay": D(2026, 12, 1), "billing": None, "uoc": {("2026-11-30", "duyet_cau"): [55, 1]}})
kiem("ngày mùng 1: 'hôm qua' lấy được ngày cuối tháng trước", t1["da_dung_hom_qua"] == 55 and t1["da_dung_thang"] == 0)
kiem("tuổi chờ: hôm qua có chạy thật → 0; chưa bao giờ → số ngày đã qua trong tháng (tối đa 7)", t["tuoi_cho"]["duyet_cau"] == 0 and t["tuoi_cho"]["tim_kiem"] == 7)
tb = Q.tong_hop({"hom_nay": D(2026, 11, 21), "billing": {"tong": 500.0, "theo_ngay": {}}, "uoc": sl["uoc"]})
kiem("billing lớn hơn ước tính → dùng billing", tb["da_dung_thang"] == 500 and tb["co_billing"])

# ---- kế hoạch / nhịp ----
k = Q.ke_hoach(D(2026, 11, 1), 0, 0)
kiem("ngày 1: (2000-200)/30 = 60 phút/ngày, nhịp 1", abs(k["ngan_sach_ngay"] - 60) < 1e-9 and abs(k["nhip"] - 1) < 1e-9)
k = Q.ke_hoach(D(2026, 11, 15), 1000, 40)
kiem("ngày 15, đã dùng 1000 (hôm nay 40): ngân sách (2000-200-960)/16 = 52,5; còn hôm nay 12,5", abs(k["ngan_sach_ngay"] - 52.5) < 1e-9 and abs(k["con_lai_hom_nay"] - 12.5) < 1e-9)
kiem("nhịp < 1 khi đã tiêu quá tay", Q.ke_hoach(D(2026, 11, 10), 900, 0)["nhip"] < 1)
kiem("hết sạch khả dụng → ngân sách 0, không âm", Q.ke_hoach(D(2026, 11, 30), 1990, 0)["ngan_sach_ngay"] == 0)
kiem("mốc cảnh báo 70/90/100", [Q.muc_canh_bao(x) for x in (1000, 1400, 1800, 2100)] == [0, 70, 90, 100])
kiem("bậc nhịp → mức tối thiểu được chạy", [Q.muc_toi_thieu_cho_chay(x) for x in (1.2, 0.8, 0.6, 0.4, 0.2, 0.05)] == [1, 1, 2, 3, 4, 5])

# ---- quyết định theo mức quan trọng ----
def qd(viec, tt, mac=None, ev=""):
    return Q.quyet_dinh_tu_so_lieu(viec, mac, tt, ev)

t0 = tt_gia(540, hn=D(2026, 11, 10))              # đã dùng đúng 60/ngày × 9 ngày
q = qd("duyet_cau", t0, 150)
kiem("định kì mức 4 đầu ngày: được chạy, trần < mặc định 150", q["cho_chay"] and 10 <= q["phut"] < 150)
ke0 = Q.ke_hoach(t0["hom_nay"], 540, 0)
kiem("trọng số theo mức: duyet_cau (4) được phần chia lớn hơn tim_kiem (2)", Q.phan_bo_ngay(ke0, {})["duyet_cau"] > 3 * Q.phan_bo_ngay(ke0, {})["tim_kiem"])
kiem("việc quan trọng mượn được nhiều hơn: cap(duyet_cau) > cap(tim_kiem) đầu ngày", Q.chia_phan(ke0, "duyet_cau", {}) > Q.chia_phan(ke0, "tim_kiem", {}))
kiem("mặc định nhỏ hơn ngân sách → giữ mặc định", qd("duyet_cau", t0, 10)["phut"] == 10)
q = qd("duyet_cau", tt_gia(540, {"duyet_cau": 60}))
kiem("đã dùng hết ngân sách hôm nay → hoãn (het_phan)", not q["cho_chay"] and q["ma"] == "het_phan")
tn = tt_gia(1450, hn=D(2026, 11, 10))
kiem("tiêu quá tay (nhịp thấp) → việc mức 2 tạm dừng", qd("tim_kiem", tn)["ma"] == "nhip_thap" and not qd("tim_kiem", tn)["cho_chay"])
kiem("… việc mức 3 cũng tạm dừng; mức 4 không bị nhịp chặn (phần chia của việc tạm dừng dồn cho nó)", qd("tu_giai", tn)["ma"] == "nhip_thap" and qd("duyet_cau", tn, 150)["ma"] != "nhip_thap"
     and Q.phan_bo_ngay(Q.ke_hoach(tn["hom_nay"], 1450, 0), {})["duyet_cau"] > Q.ke_hoach(tn["hom_nay"], 1450, 0)["ngan_sach_ngay"] * 0.4)
kiem("nhịp hồi lại thì việc mức 2 tự chạy lại", qd("tim_kiem", t0)["cho_chay"])
q = qd("tao_de", tt_gia(540, {"duyet_cau": 200}, hn=D(2026, 11, 10)), 45)
kiem("theo yêu cầu: không bị ngân sách NGÀY chặn (đã vượt ngân sách hôm nay vẫn chạy)", q["cho_chay"] and q["phut"] == 45)
kiem("bấm chạy tay (workflow_dispatch) việc định kì → coi là theo yêu cầu", qd("duyet_cau", tt_gia(540, {"x": 200}), 150, "workflow_dispatch")["loai_hieu_luc"] == "yeu_cau"
     and qd("duyet_cau", tt_gia(540, {"x": 200}), 150, "workflow_dispatch")["cho_chay"])
q = qd("tao_de", tt_gia(1900, hn=D(2026, 11, 20)), 45)
kiem("theo yêu cầu: tháng gần hết → bị cắt/từ chối, không vượt hạn mức", q["phut"] <= max(0, 100 - 100 - 15 * 10) or not q["cho_chay"])
q = qd("tao_de", tt_gia(1500, hn=D(2026, 11, 10)), 45)
kiem("theo yêu cầu chừa quỹ cho lịch cron các ngày sau (còn 500, 21 ngày × 15 = 315, dự phòng 100)", q["cho_chay"] and q["phut"] <= 500 - 100 - 315 - 1 + 1e-9 or not q["cho_chay"])
q = qd("canh_gac", tt_gia(1995, hn=D(2026, 11, 20)), 5)
kiem("việc khẩn vẫn dùng phần dự phòng khi tháng gần hết", q["cho_chay"] and abs(q["phut"] - 4) < 1e-9)
kiem("việc khẩn cũng dừng khi hết sạch hạn mức", not qd("canh_gac", tt_gia(2000, hn=D(2026, 11, 20)), 5)["cho_chay"])
kiem("việc chưa khai báo → mức 2 định kì (không lỗi)", qd("viec_la_hoac", t0)["muc"] == 2)

# ---- cổng quyet_dinh ----
sl0 = {"uoc": {}, "billing": None, "hom_nay": D(2026, 11, 1)}
q = Q.quyet_dinh("duyet_cau", 150, so_lieu=sl0, su_kien="schedule")
kiem("quyet_dinh với số liệu giả", q["cho_chay"] and 0 < q["phut"] <= 58 and q["co_so_lieu"])
Q.CHE_DO = "canh_bao"
kiem("chế độ canh_bao: không cắt", Q.quyet_dinh("duyet_cau", 150, so_lieu=sl0)["phut"] == 150)
Q.CHE_DO = "tat"
kiem("chế độ tat: nguyên mặc định", Q.quyet_dinh("duyet_cau", 150)["phut"] == 150 and Q.gioi_han("duyet_cau", 150) == 150)
Q.CHE_DO = "dieu_phoi"
_goc = Q.doc_so_lieu
Q.doc_so_lieu = lambda *a, **k: None
kiem("không đọc được số liệu → trần khi mù 60 phút, vẫn cho chạy", Q.quyet_dinh("duyet_cau", 150)["phut"] == 60 and Q.quyet_dinh("duyet_cau", 150)["cho_chay"])
kiem("kiem_thu (ngoài điều phối) không bị đụng", Q.quyet_dinh("kiem_thu", 15)["phut"] == 15)
Q.doc_so_lieu = _goc
os.environ["QUOTA_PHUT_DA_DIEU_PHOI"] = "1"
kiem("duyet_cau.py bản cũ gọi gioi_han khi trung_tam đã điều phối → trả nguyên, không tính hai lần", Q.gioi_han("duyet_cau", 37) == 37)
del os.environ["QUOTA_PHUT_DA_DIEU_PHOI"]

# ---- hiển thị ----
tt_hien = Q.tong_hop(sl)
ke_hien = Q.ke_hoach(tt_hien["hom_nay"], tt_hien["da_dung_thang"], tt_hien["da_dung_hom_nay"])
bang = Q.bang_hien_thi(tt_hien, ke_hien, da_bao=70)
nhan = {r[0]: r[1] for r in bang if len(r) > 1}
kiem("tab Quota_Phut có dòng HÔM QUA, hôm nay, cả tháng", nhan.get("Đã dùng HÔM QUA (20/11)") == 40 and nhan.get("Đã dùng cả tháng") == 72 and "Đã dùng hôm nay" in nhan)
kiem("tab Quota_Phut giữ mức cảnh báo đã báo", nhan.get("Mức cảnh báo đã báo (%)") == 70)
dong_duyet = next(r for r in bang if r and r[0] == "duyet_cau")
kiem("bảng từng việc: mức, hôm qua, cả tháng, trạng thái", dong_duyet[1] == 4 and dong_duyet[3] == 40 and dong_duyet[5] == 40 and dong_duyet[-1].startswith("Chạy"))
kiem("mọi dòng của bảng cùng số cột (Sheet không lỗi)", len({len(r) for r in bang if len(r) > 3}) == 1)
tom = "\n".join(Q.tom_tat(tt_hien, ke_hien))
kiem("tóm tắt có tháng, hôm qua, việc nhiều nhất", "đã dùng 72/2000" in tom and "Hôm qua (20/11): 40 phút" in tom and "duyet_cau 40" in tom)
md, muc, ngan = Q.bao_cao_markdown(sl)
kiem("báo cáo canh gác (markdown) có bảng từng việc", "| duyet_cau | 4 | 40 |" in md and muc == 0 and ngan)

# ---- cấu hình ----
cfg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "trung_tam_dieu_phoi.json"), encoding="utf-8"))
viec_js = {k: v for k, v in cfg["NGAN_SACH_PHUT"]["viec"].items() if not k.startswith("_")}
kiem("trung_tam_dieu_phoi.json: bảng việc khớp bảng mặc định trong mã", viec_js == Q.CAU_HINH_VIEC)
kiem("mọi việc có muc 1-5, loai hợp lệ, phut > 0", all(1 <= v["muc"] <= 5 and v["loai"] in ("khan", "yeu_cau", "dinh_ky") and v["phut"] > 0 for v in viec_js.values()))
kiem("công tắc DIEU_PHOI_PHUT, BAO_PHUT_HANG_NGAY có trong JSON", cfg["CONG_TAC"].get("DIEU_PHOI_PHUT") is True and cfg["CONG_TAC"].get("BAO_PHUT_HANG_NGAY") is True)
os.environ["GH_MUC_QUAN_TRONG"] = '{"tim_kiem": 5}'
kiem("GH_MUC_QUAN_TRONG đổi mức quan trọng không cần sửa mã", Q._gop_cau_hinh()["tim_kiem"]["muc"] == 5)
del os.environ["GH_MUC_QUAN_TRONG"]

# ---- MÔ PHỎNG CẢ THÁNG: lịch cron thật, nhu cầu tối đa ----
LICH = [(1.3, "tai_tai_lieu"), (13.3, "tai_tai_lieu"), (3.78, "duyet_cau"), (5.28, "doc_de"), (5.67, "tim_kiem"), (6.5, "xuat_de"), (7.33, "canh_gac"),
        (9.0, "quet_anh_cron"), (10.5, "tu_giai"), (13.67, "tim_kiem"), (16.5, "tu_giai"), (22.28, "doc_de"), (23.0, "chi_muc_trung"), (23.78, "duyet_cau")]
THUC = {"canh_gac": 1, "xuat_de": 2, "chi_muc_trung": 4, "tim_kiem": 8, "tai_tai_lieu": 6, "quet_anh_cron": 20}     # phút làm việc thực tế của việc nhẹ
YEU_CAU = ["tao_de", "de_cuong", "chuyen_de", "soan_giao_an", "video", "tron_de"]


def mo_phong(yc=(0, 3), yc_phut=12, seed=1, cai_dat=2, hoan=1, so_ngay=30):
    random.seed(seed)
    uoc, tong_viec, chay, hoan_dem = {}, {}, {}, {}
    for ngay in range(1, so_ngay + 1):
        hn = D(2026, 11, ngay)
        sk = [(g, v, "schedule") for g, v in LICH] + [(random.uniform(7, 21), random.choice(YEU_CAU), "workflow_dispatch") for _ in range(random.randint(*yc))]
        for gio, v, ev in sorted(sk):
            kho = dict(uoc)
            kho[(hn.isoformat(), v)] = [kho.get((hn.isoformat(), v), [0, 0])[0] + cai_dat, 1]    # lượt này đã tốn phút cài đặt khi hỏi
            tt = Q.tong_hop({"hom_nay": hn, "billing": None, "uoc": kho})
            mac = Q.cau_hinh_viec(v)["phut"] if ev == "schedule" else yc_phut
            q = Q.quyet_dinh_tu_so_lieu(v, mac, tt, ev)
            dung = cai_dat + min(q["phut"], mac, THUC.get(v, mac)) if q["cho_chay"] else hoan
            (chay if q["cho_chay"] else hoan_dem)[v] = (chay if q["cho_chay"] else hoan_dem).get(v, 0) + 1
            k = (hn.isoformat(), v)
            uoc[k] = [uoc.get(k, [0, 0])[0] + dung, uoc.get(k, [0, 0])[1] + 1]
            tong_viec[v] = tong_viec.get(v, 0) + dung
    return sum(tong_viec.values()), tong_viec, chay, hoan_dem


with contextlib.redirect_stdout(io.StringIO()):
    kq = {ten: mo_phong(**kw) for ten, kw in (("vừa", {}), ("nhẹ", {"yc": (0, 1)}), ("nặng", {"yc": (2, 6), "yc_phut": 25}), ("rất nặng", {"yc": (4, 9), "yc_phut": 30, "seed": 3}))}
for ten, (tong, tv, ch, ho) in kq.items():
    print("   mô phỏng nhu cầu %-8s: %4d phút/2000 · chạy %d · hoãn %d · duyet_cau %d phút, tao_de %d phút" % (ten, tong, sum(ch.values()), sum(ho.values()), tv.get("duyet_cau", 0), tv.get("tao_de", 0)))
kiem("mô phỏng nhu cầu vừa/nhẹ: cả tháng KHÔNG vượt 2000 phút", kq["vừa"][0] <= 2000 and kq["nhẹ"][0] <= 2000)
kiem("mô phỏng nhu cầu nặng/rất nặng: vượt không quá 10% (phần vượt là phút cài đặt của lịch cron khi đã cạn)", kq["nặng"][0] <= 2200 and kq["rất nặng"][0] <= 2200)
kiem("mô phỏng: dùng ≥ 80% hạn mức khi nhu cầu đủ (không để phí)", kq["vừa"][0] >= 1600)
kiem("mô phỏng: mọi việc định kì đều được chạy ít nhất một lần trong tháng (không bị bỏ đói)", all(kq["nhẹ"][2].get(v, 0) >= 1 for v in Q.cac_viec_dinh_ky()))
kiem("mô phỏng: việc mức 4 (duyet_cau) chạy nhiều hơn việc mức 2 (tim_kiem)", kq["vừa"][2].get("duyet_cau", 0) > kq["vừa"][2].get("tim_kiem", 0))
kiem("mô phỏng: việc theo yêu cầu mức 5 (tao_de) hầu hết được chạy", kq["vừa"][2].get("tao_de", 0) >= 0.7 * (kq["vừa"][2].get("tao_de", 0) + kq["vừa"][3].get("tao_de", 0)))

# ---- trung_tam.chay_viec với tệp việc giả ----
thu = tempfile.mkdtemp()
with open(os.path.join(thu, "viec_gia.py"), "w", encoding="utf-8") as f:
    f.write("import os\nprint('CHAY thoi_gian=' + os.environ.get('THOI_GIAN_TOI_DA_PHUT','') + ' han_tong=' + os.environ.get('HAN_TONG_PHUT',''))\nopen(os.environ['DAU_VET'],'a').write('x')\n")
with open(os.path.join(thu, "viec_ket.py"), "w", encoding="utf-8") as f:
    f.write("import sys\nsys.exit('lỗi giả của việc')\n")
with open(os.path.join(thu, "viec_cham.py"), "w", encoding="utf-8") as f:
    f.write("import time\ntry:\n    time.sleep(30)\nexcept Exception:\n    print('NUỐT')\nprint('KHONG_DUOC_TOI_DAY')\n")
os.environ["DAU_VET"] = os.path.join(thu, "dau_vet")
import trung_tam as TT
gia = os.path.join(thu, "so_lieu.json")


def chay_tt(ten, uoc, env=None, hn="2026-11-10"):
    json.dump({"hom_nay": hn, "billing": None, "uoc": uoc}, open(gia, "w"))
    for k in ("THOI_GIAN_TOI_DA_PHUT", "HAN_TONG_PHUT", "QUOTA_PHUT_DA_DIEU_PHOI"):
        os.environ.pop(k, None)
    os.environ.update({"QUOTA_PHUT_SO_LIEU_THU": gia, "GITHUB_EVENT_NAME": "schedule", "GH_VIEC": "tim_kiem"})
    for k, v in (env or {}).items():
        os.environ[k] = v
    ghi = []
    Q.cap_nhat = lambda *a, **k: ghi.append(1)
    ma, out = 0, io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            TT.chay_viec(ten, os.path.join(thu, ten))
        except SystemExit as e:
            ma = e.code or 1
    return ma, out.getvalue(), bool(ghi)


Q.CHE_DO = "dieu_phoi"
TT._cfg = {"CONG_TAC": {"DIEU_PHOI_PHUT": True}}
if os.path.exists(os.environ["DAU_VET"]):
    os.remove(os.environ["DAU_VET"])
dem = [["2026-11-%02d" % d, "x", 60, 1] for d in range(1, 10)]
ma, out, da_ghi = chay_tt("viec_gia.py", dem, {"GH_VIEC": "duyet_cau"})
kiem("trung_tam: việc định kì được chạy, trần phút truyền xuống THOI_GIAN_TOI_DA_PHUT", ma == 0 and os.path.exists(os.environ["DAU_VET"]) and re.search(r"CHAY thoi_gian=\d+", out) is not None)
kiem("trung_tam: sau việc luôn gọi cap_nhat (ghi Sheet)", da_ghi)
os.remove(os.environ["DAU_VET"])
ma, out, da_ghi = chay_tt("viec_gia.py", [["2026-11-10", "tim_kiem", 90, 3]] + dem, {"GH_VIEC": "tim_kiem"})
kiem("trung_tam: hết phần hôm nay → hoãn, KHÔNG chạy tệp việc, thoát mã 0", ma == 0 and not os.path.exists(os.environ["DAU_VET"]) and "Hoãn" in out.replace("hoãn", "Hoãn") and da_ghi)
ma, out, _ = chay_tt("viec_gia.py", [["2026-11-%02d" % d, "x", 100, 1] for d in range(1, 10)] + [["2026-11-10", "x", 130, 1]], {"GH_VIEC": "tao_de", "GITHUB_EVENT_NAME": "workflow_dispatch"})
kiem("trung_tam: việc theo yêu cầu vẫn chạy khi đã hết ngân sách NGÀY", ma == 0 and os.path.exists(os.environ["DAU_VET"]))
os.remove(os.environ["DAU_VET"])
ma, out, _ = chay_tt("viec_gia.py", [["2026-11-%02d" % d, "x", 100, 1] for d in range(1, 21)], {"GH_VIEC": "tao_de", "GITHUB_EVENT_NAME": "workflow_dispatch"}, hn="2026-11-21")
kiem("trung_tam: theo yêu cầu khi hết hạn mức tháng → từ chối, thoát mã ≠ 0, không chạy", ma != 0 and not os.path.exists(os.environ["DAU_VET"]))
ma, out, da_ghi = chay_tt("viec_ket.py", dem, {"GH_VIEC": "duyet_cau"})
kiem("trung_tam: việc tự thoát lỗi → mã thoát được giữ nguyên và vẫn cập nhật số phút", ma != 0 and da_ghi)
ma, out, _ = chay_tt("viec_gia.py", dem, {"GH_VIEC": "duyet_cau", "THOI_GIAN_TOI_DA_PHUT": "7"})
kiem("trung_tam: chỉ HẠ trần, không nâng (workflow đặt 7 phút → giữ 7)", "thoi_gian=7" in out)
os.environ["QUOTA_PHUT_CHE_DO_THU"] = ""
Q.CHE_DO = "tat"
ma, out, da_ghi = chay_tt("viec_gia.py", dem, {"GH_VIEC": "duyet_cau"})
kiem("trung_tam: QUOTA_PHUT_CHE_DO=tat → chạy như chưa có điều phối", ma == 0 and not da_ghi and os.path.exists(os.environ["DAU_VET"]))
Q.CHE_DO = "dieu_phoi"
os.remove(os.environ["DAU_VET"])
TT._cfg = {"CONG_TAC": {"DIEU_PHOI_PHUT": False}}
ma, out, da_ghi = chay_tt("viec_gia.py", dem, {"GH_VIEC": "duyet_cau"})
kiem("trung_tam: công tắc DIEU_PHOI_PHUT=false → chạy như cũ", ma == 0 and not da_ghi and os.path.exists(os.environ["DAU_VET"]))
TT._cfg = {"CONG_TAC": {"DIEU_PHOI_PHUT": True}}
if hasattr(__import__("signal"), "SIGALRM"):
    os.environ["GH_HAN_CUNG_THEM"] = "0.02"                       # 1,2 giây dung sai
    json.dump({"hom_nay": "2026-11-10", "billing": None, "uoc": dem}, open(gia, "w"))
    cu = Q.CAU_HINH["duyet_cau"]["phut"]
    _qd = Q.quyet_dinh
    Q.quyet_dinh = lambda *a, **k: dict(_qd(*a, **k), phut=0.0167, cho_chay=True)   # trần 1 giây
    ma, out, _ = chay_tt("viec_cham.py", dem, {"GH_VIEC": "duyet_cau"})
    Q.quyet_dinh = _qd
    kiem("trung_tam: đồng hồ cứng ngắt việc định kì quá trần, không bị `except Exception` nuốt, thoát mã 0", ma == 0 and "hết phần phút" in out and "NUỐT" not in out and "KHONG_DUOC" not in out)
    del os.environ["GH_HAN_CUNG_THEM"]

# ---- workflow ----
try:
    import yaml
    wf = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".github", "workflows")
    if os.path.isdir(wf):
        sai = []
        for ten in sorted(os.listdir(wf)):
            d = yaml.safe_load(open(os.path.join(wf, ten), encoding="utf-8"))
            buoc = [b for j in d["jobs"].values() for b in j.get("steps", [])]
            qua_tt = [b for b in buoc if "trung_tam.py" in str(b.get("run", ""))]
            if qua_tt and (((d.get("permissions") or {}).get("actions")) not in ("read", "write") or any("GITHUB_TOKEN" not in (b.get("env") or {}) for b in qua_tt)):
                sai.append(ten)
            if any(b.get("id") == "cong" for b in buoc) and not all("steps.cong.outputs.chay" in str(b.get("if", "")) for b in buoc[2:]):
                sai.append(ten + " (cổng)")
        kiem("workflow: mọi việc qua trung_tam có env GITHUB_TOKEN + permissions actions: read; bước sau cổng đều có điều kiện", not sai)
        if sai:
            print("   lỗi ở:", sai)
except ImportError:
    print("(bỏ qua kiểm tra workflow: chưa cài PyYAML)")

if LOI:
    print("\n❌ %d ca sai: %s" % (len(LOI), "; ".join(LOI)))
    sys.exit(1)
print("\n✅ Tất cả ca đạt.")
