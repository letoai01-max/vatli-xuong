"""
quota_phut.py – ĐIỀU PHỐI PHÚT GITHUB ACTIONS CỦA XƯỞNG (hạn mức 2.000 phút/tháng): đếm · chia theo ngày và theo mức quan trọng · tự cắt/hoãn · hiển thị.

Repo riêng tư gói miễn phí được 2.000 phút/tháng cho CẢ TÀI KHOẢN. Mọi việc của xưởng đều chạy qua trung_tam.py, và trung_tam.py gọi
module này trước và sau mỗi việc – nên KHÔNG cần sửa từng tệp việc, và không tốn thêm phút (chạy bên trong job sẵn có).

1. ĐẾM  (số ƯỚC TÍNH: thời gian chạy làm tròn lên từng lượt; billing tính từng job làm tròn lên nên có thể lệch vài phút)
   • cả tháng: billing GitHub nếu có secret GH_BILLING_TOKEN; không có thì tính từ các lượt chạy của repo này (không thấy repo khác).
   • hôm nay · HÔM QUA · cả tháng, theo từng việc (workflow): danh sách lượt chạy của repo bằng GITHUB_TOKEN (cần permissions: actions: read).
2. CHIA NGÂN SÁCH NGÀY (tự cân đối lại mỗi lượt chạy)
   khả dụng = hạn mức − dự phòng − phút đã dùng TRƯỚC hôm nay;  ngân sách ngày = khả dụng / số ngày còn lại (kể cả hôm nay).
   Hôm nay dùng chưa hết → dồn sang các ngày sau; dùng lố → các ngày sau bị cắt bớt.  NHỊP = ngân sách ngày / ngân sách chuẩn (đều mỗi ngày).
3. MỨC QUAN TRỌNG (1 = tuỳ chọn … 5 = thiết yếu, bảng CAU_HINH_VIEC hoặc mục NGAN_SACH_PHUT trong trung_tam_dieu_phoi.json) và LOẠI VIỆC
   • khan     (canh_gac…)  : luôn được chạy, kể cả bằng phần dự phòng; chỉ dừng khi cả tháng hết sạch.
   • yeu_cau  (tạo đề, đề cương, giáo án…, hoặc bất kì việc nào bấm chạy tay/Apps Script gọi): không bị ngân sách NGÀY chặn – có người đang chờ;
              chỉ bị cắt theo số phút còn lại của THÁNG (chừa nửa dự phòng cho việc khẩn và quỹ cố định GH_CHI_PHI_LICH_NGAY cho lịch cron các ngày sau). Phút đã dùng vẫn bị trừ vào ngân sách các việc định kì.
   • dinh_ky  (duyệt câu, đọc đề, tự giải, quét ảnh, tìm kiếm, tải tài liệu…, chạy theo lịch cron): chia ngân sách ngày theo trọng số = 2^(mức−1) (việc chờ N ngày chưa chạy thật được hưởng N+1 ngày phần chia nên chạy luân phiên, không bị bỏ đói);
              việc đang chạy được mượn 25% phần chưa dùng của việc KÉM quan trọng hơn và 10% của việc quan trọng hơn/bằng (chống việc chạy sớm ăn hết ngày).
              Khi NHỊP tụt (tiêu quá tay) thì việc mức thấp bị tạm dừng trước: nhịp ≥0,8 chạy mọi mức; ≥0,55 mức ≥2; ≥0,3 mức ≥3; ≥0,12 mức ≥4; thấp hơn chỉ mức 5.
              Nhịp hồi lại (ngày sau dùng ít) thì các việc đó tự chạy lại. Phần cắt xuống dưới "toi_thieu" phút thì hoãn hẳn (khỏi tốn phút cài đặt mà làm không được gì).
4. HIỂN THỊ: dòng đầu mỗi lượt chạy (log + trang Summary), tab Quota_Phut (tháng · hôm qua · hôm nay · từng việc · trạng thái hiện tại),
   tab Quota_Phut_Ngay (chi tiết ngày × việc), bản tóm tắt trong báo cáo canh gác 7h20 và Telegram; báo Telegram khi chạm 70% / 90% / 100% hoặc dự báo vượt.
Nguyên tắc: phần phụ không làm hỏng việc chính – lỗi mạng/quyền chỉ cảnh báo; không đọc được số liệu thì giới hạn lượt ở GH_TRAN_KHI_MU phút
(mặc định 60) thay vì chạy không giới hạn.

Biến môi trường (đều tuỳ chọn):
  QUOTA_PHUT_CHE_DO   dieu_phoi (mặc định) | canh_bao (chỉ ghi và báo, không cắt) | tat (như chưa có module)
  GH_QUOTA_PHUT_THANG 2000   GH_DU_PHONG_PHUT 200   GH_PHUT_DEM_CUOI 1 (đệm cho các bước sau cùng của job)   GH_TRAN_KHI_MU 60
  GH_MUC_QUAN_TRONG   JSON ghi đè mức quan trọng, ví dụ {"tim_kiem":1,"duyet_cau":5}
  GH_CHU / GH_LOAI_CHU  chủ tài khoản (mặc định GITHUB_REPOSITORY_OWNER) / user | org
  GH_BILLING_TOKEN    PAT classic đọc billing (không có thì ước tính)      GITHUB_TOKEN  tự có trong Actions, workflow cần truyền vào env
  QUOTA_SHEET_ID      Sheet ghi số liệu (mặc định Kho chung)
Giả định: chu kì hạn mức = THÁNG DƯƠNG LỊCH, ngày tính theo giờ Việt Nam. Đối chiếu với Settings → Billing and plans của GitHub.
[21/11/2026] Bản 2: điều phối mọi việc qua trung_tam.py, mức quan trọng, nhịp, số liệu hôm qua và theo từng việc.
"""
import calendar, datetime as dt, json, math, os, re, sys, urllib.error, urllib.parse, urllib.request

TZ = dt.timezone(dt.timedelta(hours=7))
TAB_TONG, TAB_NGAY = "Quota_Phut", "Quota_Phut_Ngay"
TAB_BAN_DO = "Quota_Phut_BanDo"        # [22/11/2026] số liệu cho bản đồ nhiệt: giờ chạy · tỉ trọng ngày/tháng · số ngày có chạy
GHI_BAN_DO = os.environ.get("QUOTA_PHUT_GHI_BAN_DO", "1") != "0"   # công tắc: đặt 0 thì y như bản cũ
THU_MUC = os.path.dirname(os.path.abspath(__file__))
ID_KHO_CHUNG = "1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc"
MOC_BAO = (70, 90, 100)
NGUONG_CHAY_THAT = 3                   # lượt chạy từ chừng này phút trở lên mới tính là "đã làm việc" (lượt hoãn chỉ tốn 1-2 phút cài đặt)
TOI_DA_NGAY_CHO = 7                    # việc chờ N ngày chưa chạy thật được hưởng (N+1) ngày phần chia (tối đa 8) – chống việc mức thấp bị bỏ đói
TRONG_SO_MUC = {1: 1.0, 2: 2.0, 3: 4.0, 4: 8.0, 5: 16.0}
MUON_TU_KEM, MUON_TU_CAO = 0.25, 0.1    # được mượn bao nhiêu phần ngân sách chưa dùng của việc khác: việc kém quan trọng hơn / quan trọng hơn hoặc bằng
GIU_DU_PHONG_YEU_CAU = 0.5             # việc theo yêu cầu chừa lại bao nhiêu phần dự phòng cho việc khẩn

# mức: 1 tuỳ chọn · 2 nền · 3 thường · 4 quan trọng · 5 thiết yếu.  phut = trần mặc định mỗi lượt.  toi_thieu = dưới mức này thì hoãn.
# lich False = việc không có lịch cron (chạy tay/được gọi) nên không chiếm phần chia mỗi ngày.  ngoai True = không điều phối được (chỉ đếm).
CAU_HINH_VIEC = {
    "canh_gac":      {"muc": 5, "loai": "khan",    "phut": 5,   "toi_thieu": 1},
    "quota_phut":    {"muc": 5, "loai": "khan",    "phut": 10,  "toi_thieu": 1},
    "tao_de":        {"muc": 5, "loai": "yeu_cau", "phut": 45,  "toi_thieu": 5},
    "xuat_de":       {"muc": 4, "loai": "dinh_ky", "phut": 10,  "toi_thieu": 3},
    "duyet_cau":     {"muc": 4, "loai": "dinh_ky", "phut": 150, "toi_thieu": 10},
    "tron_de":       {"muc": 4, "loai": "yeu_cau", "phut": 30,  "toi_thieu": 3},
    "kiem_dinh_de":  {"muc": 4, "loai": "yeu_cau", "phut": 40,  "toi_thieu": 5},
    "de_cuong":      {"muc": 4, "loai": "yeu_cau", "phut": 45,  "toi_thieu": 5},
    "chuyen_de":     {"muc": 4, "loai": "yeu_cau", "phut": 48,  "toi_thieu": 5},
    "soan_giao_an":  {"muc": 4, "loai": "yeu_cau", "phut": 26,  "toi_thieu": 5},
    "ve_hinh":       {"muc": 3, "loai": "yeu_cau", "phut": 20,  "toi_thieu": 3},
    "xuat_word":     {"muc": 3, "loai": "yeu_cau", "phut": 15,  "toi_thieu": 3},
    "video":         {"muc": 3, "loai": "yeu_cau", "phut": 40,  "toi_thieu": 5},
    "tu_giai":       {"muc": 3, "loai": "dinh_ky", "phut": 60,  "toi_thieu": 8},
    "doc_de":        {"muc": 3, "loai": "dinh_ky", "phut": 100, "toi_thieu": 10},
    "chi_muc_trung": {"muc": 3, "loai": "dinh_ky", "phut": 20,  "toi_thieu": 5},
    "cau_mau":       {"muc": 3, "loai": "yeu_cau", "phut": 40,  "toi_thieu": 5, "lich": False},   # [22/11] câu mẫu hoá (cau_mau.py), chưa có lịch cron
    "quet_anh_cron": {"muc": 2, "loai": "dinh_ky", "phut": 120, "toi_thieu": 8},
    "tim_kiem":      {"muc": 2, "loai": "dinh_ky", "phut": 25,  "toi_thieu": 5},
    "tai_tai_lieu":  {"muc": 2, "loai": "dinh_ky", "phut": 25,  "toi_thieu": 5},
    "van_ban":       {"muc": 2, "loai": "dinh_ky", "phut": 30,  "toi_thieu": 5, "lich": False},
    "gan_mo_ta_anh": {"muc": 1, "loai": "yeu_cau", "phut": 60,  "toi_thieu": 5},
    "thu_drive":     {"muc": 1, "loai": "yeu_cau", "phut": 5,   "toi_thieu": 1},
    "kiem_thu":      {"muc": 3, "loai": "yeu_cau", "phut": 15,  "toi_thieu": 1, "ngoai": True},
}
CAU_HINH_MAC_DINH_LA = {"muc": 2, "loai": "dinh_ky", "phut": 30, "toi_thieu": 5, "lich": False}     # việc chưa khai báo
# tên tệp Python → tên workflow (khi chạy ngoài GitHub Actions, không có GITHUB_WORKFLOW_REF)
BI_DANH_TEP = {"quet_bu_hinh_anh": "quet_anh_cron", "render": "video"}
SU_KIEN_THEO_YEU_CAU = ("workflow_dispatch", "repository_dispatch")


def _so(ten, mac_dinh):
    try:
        return float(os.environ.get(ten, mac_dinh))
    except (TypeError, ValueError):
        return float(mac_dinh)


def _nap_json():
    try:
        with open(os.path.join(THU_MUC, "trung_tam_dieu_phoi.json"), encoding="utf-8") as f:
            return json.load(f).get("NGAN_SACH_PHUT") or {}
    except Exception:
        return {}


def _gop_cau_hinh():
    """Mặc định trong mã < mục NGAN_SACH_PHUT.viec của trung_tam_dieu_phoi.json < biến môi trường GH_MUC_QUAN_TRONG."""
    kq = {k: dict(v) for k, v in CAU_HINH_VIEC.items()}
    js = _nap_json()
    for k, v in (js.get("viec") or {}).items():
        if isinstance(v, dict) and not str(k).startswith("_"):
            kq.setdefault(chuan_hoa(k), dict(CAU_HINH_MAC_DINH_LA)).update(v)
    try:
        for k, v in json.loads(os.environ.get("GH_MUC_QUAN_TRONG", "{}") or "{}").items():
            kq.setdefault(chuan_hoa(k), dict(CAU_HINH_MAC_DINH_LA))["muc"] = int(v)
    except (ValueError, TypeError, AttributeError):
        print("⚠️ GH_MUC_QUAN_TRONG không phải JSON hợp lệ – bỏ qua.", flush=True)
    return kq


def chuan_hoa(ten):
    return re.sub(r"[\s\-]+", "_", str(ten or "").strip().lower())


_JS = _nap_json()
CHE_DO = (os.environ.get("QUOTA_PHUT_CHE_DO") or str(_nap_json().get("che_do") or "dieu_phoi")).strip().lower()   # [22/11] có thể đặt "che_do" trong trung_tam_dieu_phoi.json (repo public: "canh_bao")
QUOTA = _so("GH_QUOTA_PHUT_THANG", _JS.get("quota_thang", 2000))
DU_PHONG = _so("GH_DU_PHONG_PHUT", _JS.get("du_phong", 200))
DEM_CUOI = _so("GH_PHUT_DEM_CUOI", _JS.get("dem_cuoi", 1))
CHI_PHI_LICH = _so("GH_CHI_PHI_LICH_NGAY", _JS.get("chi_phi_lich_ngay", 15))   # phút/ngày tốn cho các lượt cron dù chỉ cài đặt rồi hoãn
TRAN_KHI_MU = _so("GH_TRAN_KHI_MU", 60)
CAU_HINH = _gop_cau_hinh()


# ============================== HÀM THUẦN (test không cần mạng) ==============================
def cau_hinh_viec(viec):
    c = dict(CAU_HINH_MAC_DINH_LA)
    c.update(CAU_HINH.get(chuan_hoa(viec), {}))
    c["muc"] = max(1, min(5, int(c.get("muc", 2))))
    return c


def trong_so(viec):
    """Trọng số chia ngân sách = 2^(mức−1)."""
    c = cau_hinh_viec(viec)
    return float(c.get("trong_so") or TRONG_SO_MUC[c["muc"]])


def viec_tu_tep(ten_tep):
    """Tên việc khi chạy qua trung_tam.py: ưu tiên tên workflow của lượt chạy (khớp với danh sách lượt chạy GitHub trả về)."""
    if os.environ.get("GH_VIEC"):
        return chuan_hoa(os.environ["GH_VIEC"])
    ref = os.environ.get("GITHUB_WORKFLOW_REF", "").split("@")[0]
    if ref:
        return ten_viec({"path": ref})
    goc = re.sub(r"\.py$", "", os.path.basename(str(ten_tep)))
    return BI_DANH_TEP.get(chuan_hoa(goc), chuan_hoa(goc))


def ten_viec(run):
    """Tên việc = tên tệp workflow không đuôi, chữ thường, gạch ngang → gạch dưới (duyet_cau, quet_anh_cron)."""
    p = str(run.get("path") or run.get("name") or "khong_ro").split("@")[0]
    return chuan_hoa(re.sub(r"\.ya?ml$", "", os.path.basename(p))) or "khong_ro"


def _gio(s):
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def uoc_tinh(cac_luot, bay_gio):
    """Danh sách lượt chạy → {(ngày 'YYYY-MM-DD' giờ VN, việc): [phút, số lượt]}. Lượt đang chạy tính đến bây giờ; lượt xếp hàng thì chưa tính."""
    kq = {}
    for r in cac_luot:
        bd = _gio(r.get("run_started_at") or r.get("created_at"))
        if not bd:
            continue
        if r.get("status") == "completed":
            kt = _gio(r.get("updated_at")) or bd
        elif r.get("status") == "in_progress":
            kt = bay_gio
        else:
            continue
        phut = math.ceil(max(0.0, (kt - bd).total_seconds()) / 60.0)
        o = kq.setdefault((bd.astimezone(TZ).date().isoformat(), ten_viec(r)), [0, 0])
        o[0] += phut
        o[1] += 1
    return kq


def tong_tu_billing(j):
    """Phản hồi /settings/billing/usage → phút Actions cả tháng. Trả {"tong": …, "theo_ngay": {ngày: phút}} hoặc None nếu thiếu dữ liệu."""
    muc = (j or {}).get("usageItems")
    if not isinstance(muc, list):
        return None
    tong, theo_ngay = 0.0, {}
    for m in muc:
        if str(m.get("product", "")).lower() != "actions" or str(m.get("unitType", "")).lower() != "minutes":
            continue
        q = float(m.get("quantity") or 0)
        tong += q
        d = str(m.get("date", ""))[:10]
        theo_ngay[d] = theo_ngay.get(d, 0.0) + q
    return {"tong": tong, "theo_ngay": theo_ngay}


def ke_hoach(hom_nay, da_dung_thang, da_dung_hom_nay, khan=False, quota=None, du_phong=None):
    """Chia ngân sách: trả dict các số cần hiển thị. hom_nay là dt.date."""
    quota = QUOTA if quota is None else quota
    du_phong_chuan = DU_PHONG if du_phong is None else du_phong
    du_phong = 0.0 if khan else du_phong_chuan
    so_ngay = calendar.monthrange(hom_nay.year, hom_nay.month)[1]
    con_ngay = so_ngay - hom_nay.day + 1                                   # kể cả hôm nay
    truoc_hom_nay = max(0.0, da_dung_thang - da_dung_hom_nay)
    kha_dung = max(0.0, quota - du_phong - truoc_hom_nay)
    ngan_sach = kha_dung / con_ngay
    chuan = max(0.0, quota - du_phong_chuan) / so_ngay                     # ngân sách mỗi ngày nếu chia đều từ đầu tháng
    return {"quota": quota, "du_phong": du_phong, "da_dung_thang": da_dung_thang, "con_lai_thang": quota - da_dung_thang,
            "kha_dung": kha_dung, "so_ngay_con_lai": con_ngay, "ngan_sach_ngay": ngan_sach, "ngan_sach_chuan": chuan,
            "nhip": (ngan_sach / chuan) if chuan else 0.0,
            "da_dung_hom_nay": da_dung_hom_nay, "con_lai_hom_nay": max(0.0, ngan_sach - da_dung_hom_nay),
            "du_bao_cuoi_thang": da_dung_thang / hom_nay.day * so_ngay}


def muc_toi_thieu_cho_chay(nhip):
    """Nhịp tiêu thụ càng thấp (đã tiêu quá tay) thì chỉ còn các việc định kì mức cao được chạy."""
    for nguong, muc in ((0.8, 1), (0.55, 2), (0.3, 3), (0.12, 4)):
        if nhip >= nguong:
            return muc
    return 5


def cac_viec_dinh_ky():
    return [v for v, c in CAU_HINH.items() if c.get("loai") == "dinh_ky" and c.get("lich", True) and not c.get("ngoai")]


def phan_bo_ngay(ke, hom_nay_theo_viec, them=()):
    """Phần ngân sách ngày của từng việc định kì (theo trọng số mức quan trọng) → {việc: phần}."""
    muc_can = muc_toi_thieu_cho_chay(ke["nhip"])                           # việc đang tạm dừng vì nhịp thấp không chiếm phần chia
    cac = {v for v in cac_viec_dinh_ky() if cau_hinh_viec(v)["muc"] >= muc_can} | set(them)
    tong_w = sum(trong_so(v) for v in cac) or 1.0
    return {v: ke["ngan_sach_ngay"] * trong_so(v) / tong_w for v in cac}


def chia_phan(ke, viec, hom_nay_theo_viec, tuoi_cho=None):
    """Số phút tối đa cho việc định kì `viec` hôm nay: phần của mình + phần mượn từ ngân sách chưa dùng của việc khác (không vượt phần còn lại của ngày)."""
    phan = phan_bo_ngay(ke, hom_nay_theo_viec, them=(viec,))
    muc_toi = cau_hinh_viec(viec)["muc"]
    con = {v: max(0.0, p - hom_nay_theo_viec.get(v, 0)) for v, p in phan.items()}
    muon = sum(c * (MUON_TU_KEM if cau_hinh_viec(v)["muc"] < muc_toi else MUON_TU_CAO) for v, c in con.items() if v != viec)
    cua_minh = max(0.0, phan[viec] * (1 + (tuoi_cho or {}).get(viec, 0)) - hom_nay_theo_viec.get(viec, 0))   # phần chia cộng dồn các ngày chờ
    return max(0.0, min(ke["con_lai_hom_nay"], cua_minh + muon))


def tong_hop(so_lieu):
    """Gộp số liệu đọc về thành các con số dùng để chia. so_lieu = {"uoc": {...}, "billing": {...}|None, "hom_nay": date}."""
    hn = so_lieu["hom_nay"]
    hq = hn - dt.timedelta(days=1)
    thang = hn.strftime("%Y-%m")
    uoc = so_lieu["uoc"]
    theo_viec = {"hom_nay": {}, "hom_qua": {}, "thang": {}}
    luot = {"hom_nay": {}, "hom_qua": {}, "thang": {}}
    for (n, v), x in uoc.items():
        for khoa, dung in (("hom_nay", n == hn.isoformat()), ("hom_qua", n == hq.isoformat()), ("thang", n.startswith(thang))):
            if dung:
                theo_viec[khoa][v] = theo_viec[khoa].get(v, 0) + x[0]
                luot[khoa][v] = luot[khoa].get(v, 0) + x[1]
    uoc_thang = sum(theo_viec["thang"].values())
    cuoi = {}                                   # ngày gần nhất mỗi việc có lượt chạy thật
    for (n, v), x in uoc.items():
        if x[0] >= NGUONG_CHAY_THAT:
            cuoi[v] = max(cuoi.get(v, ""), n)
    tuoi_cho = {}
    for v in set(CAU_HINH) | set(theo_viec["thang"]):
        ngay_cho = (hn - dt.date.fromisoformat(cuoi[v])).days - 1 if v in cuoi else hn.day - 1      # hôm qua có chạy → 0 ngày chờ
        tuoi_cho[v] = max(0, min(TOI_DA_NGAY_CHO, ngay_cho))
    bl = so_lieu.get("billing")
    da_dung = max(bl["tong"], uoc_thang) if bl else uoc_thang            # billing có thể chậm hơn thực tế → lấy số lớn hơn
    return {"hom_nay": hn, "hom_qua": hq, "thang": thang, "da_dung_thang": float(da_dung), "uoc_repo_thang": float(uoc_thang),
            "co_billing": bool(bl), "hom_nay_theo_viec": theo_viec["hom_nay"], "hom_qua_theo_viec": theo_viec["hom_qua"],
            "thang_theo_viec": theo_viec["thang"], "tuoi_cho": tuoi_cho, "luot_hom_nay": luot["hom_nay"], "luot_thang": luot["thang"],
            "da_dung_hom_nay": float(sum(theo_viec["hom_nay"].values())), "da_dung_hom_qua": float(sum(theo_viec["hom_qua"].values())),
            "uoc": uoc}


def quyet_dinh_tu_so_lieu(viec, mac_dinh, tt, su_kien=""):
    """Phần lõi (tách ra để test): có cho chạy không, tối đa bao nhiêu phút, vì sao.
    Trả {viec, muc, loai, loai_hieu_luc, phut, cho_chay, ma, ly_do, ke}.  ma: ok | het_thang | het_phan | nhip_thap."""
    c = cau_hinh_viec(viec)
    mac_dinh = float(c["phut"] if mac_dinh is None else mac_dinh)
    loai = c["loai"]
    if loai == "dinh_ky" and su_kien in SU_KIEN_THEO_YEU_CAU:
        loai = "yeu_cau"                                   # người/Apps Script chủ động bấm chạy → coi như có người đang chờ
    toi_thieu = float(c["toi_thieu"])
    khan = loai == "khan"
    ke = ke_hoach(tt["hom_nay"], tt["da_dung_thang"], tt["da_dung_hom_nay"], khan=khan)
    con_thang = max(0.0, ke["con_lai_thang"])
    ma, ly_do = "ok", ""
    if khan:
        cap = con_thang - DEM_CUOI
    elif loai == "yeu_cau":
        cap = con_thang - DU_PHONG * GIU_DU_PHONG_YEU_CAU - CHI_PHI_LICH * (ke["so_ngay_con_lai"] - 1) - DEM_CUOI   # chừa quỹ cố định cho lịch cron các ngày sau
    else:
        muc_can = muc_toi_thieu_cho_chay(ke["nhip"])
        if c["muc"] < muc_can:
            cap, ma = 0.0, "nhip_thap"
            ly_do = "nhịp tiêu thụ %.2f (ngân sách ngày %.0f/%.0f phút chuẩn) → việc mức %d tạm dừng, chỉ mức ≥%d được chạy" % (
                ke["nhip"], ke["ngan_sach_ngay"], ke["ngan_sach_chuan"], c["muc"], muc_can)
        else:
            cap = chia_phan(ke, viec, tt["hom_nay_theo_viec"], tt.get("tuoi_cho")) - DEM_CUOI
    ket = min(mac_dinh, cap)
    if cap < toi_thieu:                                    # toi_thieu chỉ áp cho phần NGÂN SÁCH, không áp cho số phút người dùng tự đặt
        ket = 0.0
        if ma == "ok":
            ma = "het_thang" if (loai in ("khan", "yeu_cau") or ke["kha_dung"] <= 0) else "het_phan"
            ly_do = ("hạn mức tháng gần hết (còn %.0f phút)" % con_thang) if ma == "het_thang" else \
                    ("phần ngân sách hôm nay của việc này đã hết (ngày còn %.0f phút)" % ke["con_lai_hom_nay"])
    return {"viec": viec, "muc": c["muc"], "loai": c["loai"], "loai_hieu_luc": loai, "phut": ket, "cho_chay": ket > 0,
            "ma": ma, "ly_do": ly_do, "ke": ke}


def gioi_han_tu_so_lieu(viec, mac_dinh, tt):
    """Tương thích bản 1: trả (số phút tối đa, ke_hoach)."""
    q = quyet_dinh_tu_so_lieu(viec, mac_dinh, tt)
    return q["phut"], q["ke"]


def trang_thai_viec(viec, tt):
    """Dòng trạng thái hiện tại của một việc (để hiển thị)."""
    c = cau_hinh_viec(viec)
    if c.get("ngoai"):
        return "Ngoài điều phối (chỉ đếm)"
    q = quyet_dinh_tu_so_lieu(viec, None, tt)
    if q["loai"] == "khan":
        return "Luôn chạy (khẩn)"
    if q["loai"] == "yeu_cau":
        return "Theo yêu cầu, tối đa %d phút" % q["phut"] if q["cho_chay"] else "Từ chối: hết hạn mức tháng"
    if q["cho_chay"]:
        return "Chạy, tối đa %d phút" % q["phut"]
    return "Tạm dừng: nhịp thấp" if q["ma"] == "nhip_thap" else "Hoãn: hết phần hôm nay"


def muc_canh_bao(da_dung, quota=None):
    quota = QUOTA if quota is None else quota
    ti_le = 100.0 * da_dung / quota if quota else 0
    return max([m for m in MOC_BAO if ti_le >= m] or [0])


def tom_tat(tt, ke, so_viec=5):
    """Bản tóm tắt vài dòng (log đầu lượt, Summary, Telegram, báo cáo canh gác)."""
    q = ke["quota"]
    dong = ["⏱️ Phút GitHub Actions tháng %s: đã dùng %d/%d (%d%%), còn %d%s · dự báo cuối tháng ~%d" % (
        tt["thang"], tt["da_dung_thang"], q, round(100.0 * tt["da_dung_thang"] / q) if q else 0, ke["con_lai_thang"],
        "" if tt["co_billing"] else " [ước tính từ repo này]", ke["du_bao_cuoi_thang"]),
        "Hôm qua (%s): %d phút · hôm nay: %d phút, ngân sách ngày %.0f (nhịp %.2f)" % (
            tt["hom_qua"].strftime("%d/%m"), tt["da_dung_hom_qua"], tt["da_dung_hom_nay"], ke["ngan_sach_ngay"], ke["nhip"])]
    top = sorted(tt["thang_theo_viec"].items(), key=lambda a: -a[1])[:so_viec]
    if top:
        dong.append("Tháng này nhiều nhất: " + " · ".join("%s %d (hôm qua %d)" % (v, p, tt["hom_qua_theo_viec"].get(v, 0)) for v, p in top))
    muc = muc_toi_thieu_cho_chay(ke["nhip"])
    if muc > 1:
        dam = sorted(v for v in cac_viec_dinh_ky() if cau_hinh_viec(v)["muc"] < muc)
        dong.append("⚠️ Đang tiết kiệm: tạm dừng việc định kì mức <%d (%s)" % (muc, ", ".join(dam) or "không có"))
    return dong


# ============================== ĐỌC SỐ LIỆU (mạng) ==============================
def _goi(url, token):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "Authorization": "Bearer " + token,
                                               "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "vatli-xuong"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def lay_cac_luot(repo, token, tu_ngay):
    kq = []
    for trang in range(1, 11):
        j = _goi("https://api.github.com/repos/%s/actions/runs?per_page=100&page=%d&created=%s"
                 % (repo, trang, urllib.parse.quote(">=" + tu_ngay.isoformat())), token)
        ds = j.get("workflow_runs", [])
        kq += ds
        if len(ds) < 100:
            break
    return kq


def lay_billing(chu, loai, token, nam, thang):
    goc = "users/%s" % chu if loai != "org" else "organizations/%s" % chu
    return tong_tu_billing(_goi("https://api.github.com/%s/settings/billing/usage?year=%d&month=%d" % (goc, nam, thang), token))


def doc_so_lieu(bay_gio=None):
    """Đọc số liệu thật. Trả None nếu không đọc được số lượt chạy (thiếu token/quyền/mạng).
    QUOTA_PHUT_SO_LIEU_THU = đường dẫn JSON số liệu giả (chỉ để kiểm thử)."""
    bay_gio = bay_gio or dt.datetime.now(dt.timezone.utc)
    gia = os.environ.get("QUOTA_PHUT_SO_LIEU_THU")
    if gia:
        with open(gia, encoding="utf-8") as f:
            j = json.load(f)
        return {"hom_nay": dt.date.fromisoformat(j["hom_nay"]), "billing": j.get("billing"),
                "uoc": {(n, v): [p, l] for n, v, p, l in j["uoc"]}}
    hn = bay_gio.astimezone(TZ).date()
    repo, token = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_TOKEN", "")
    if not repo or not token:
        print("⚠️ Quota phút: thiếu GITHUB_REPOSITORY/GITHUB_TOKEN (workflow cần env GITHUB_TOKEN và permissions: actions: read).", flush=True)
        return None
    try:
        # lùi 1 ngày so với đầu tháng giờ VN để không sót lượt chạy tính theo UTC (và để có số liệu "hôm qua" vào ngày mùng 1)
        cac_luot = lay_cac_luot(repo, token, hn.replace(day=1) - dt.timedelta(days=1))
    except (urllib.error.URLError, ValueError, TimeoutError) as e:
        print("⚠️ Quota phút: không đọc được danh sách lượt chạy (%s)." % str(getattr(e, "code", e))[:80], flush=True)
        return None
    bl, tk = None, os.environ.get("GH_BILLING_TOKEN", "")
    chu = os.environ.get("GH_CHU") or os.environ.get("GITHUB_REPOSITORY_OWNER", "")
    if tk and chu:
        try:
            bl = lay_billing(chu, os.environ.get("GH_LOAI_CHU", "user").lower(), tk, hn.year, hn.month)
        except (urllib.error.URLError, ValueError, TimeoutError) as e:
            print("⚠️ Quota phút: không đọc được billing (%s) – dùng số ước tính từ lượt chạy." % str(getattr(e, "code", e))[:80], flush=True)
    return {"uoc": uoc_tinh(cac_luot, bay_gio), "billing": bl, "hom_nay": hn}


# ============================== QUYẾT ĐỊNH MỖI LƯỢT ==============================
def quyet_dinh(viec, mac_dinh=None, so_lieu=None, su_kien=None):
    """Cổng của mỗi lượt chạy. Không bao giờ ném lỗi. Trả dict như quyet_dinh_tu_so_lieu, thêm co_so_lieu và tt (có thể None)."""
    viec = chuan_hoa(viec)
    c = cau_hinh_viec(viec)
    mac = float(c["phut"] if mac_dinh is None else mac_dinh)
    su_kien = os.environ.get("GITHUB_EVENT_NAME", "") if su_kien is None else su_kien
    nguyen = {"viec": viec, "muc": c["muc"], "loai": c["loai"], "loai_hieu_luc": c["loai"], "phut": mac, "cho_chay": True,
              "ma": "ok", "ly_do": "", "ke": None, "tt": None, "co_so_lieu": False}
    if CHE_DO == "tat" or c.get("ngoai"):
        return nguyen
    try:
        sl = so_lieu or doc_so_lieu()
        if not sl:
            if CHE_DO != "canh_bao":
                nguyen["phut"] = min(mac, TRAN_KHI_MU)
            nguyen["ly_do"] = "không đọc được số liệu → giới hạn %d phút (GH_TRAN_KHI_MU)" % min(mac, TRAN_KHI_MU)
            return nguyen
        tt = tong_hop(sl)
        q = quyet_dinh_tu_so_lieu(viec, mac, tt, su_kien)
    except Exception as e:
        nguyen["phut"] = min(mac, TRAN_KHI_MU) if CHE_DO != "canh_bao" else mac
        nguyen["ly_do"] = "lỗi tính ngân sách (%s) → giới hạn %d phút" % (str(e)[:80], min(mac, TRAN_KHI_MU))
        return nguyen
    q.update({"tt": tt, "co_so_lieu": True})
    if CHE_DO == "canh_bao":
        q.update({"phut": mac, "cho_chay": True, "ly_do": (q["ly_do"] + " (chế độ canh_bao: không cắt)").strip()})
    return q


def gioi_han(viec, mac_dinh, so_lieu=None):
    """Tương thích bản 1 (duyet_cau.py cũ gọi trực tiếp): số phút tối đa lượt này, 0 = hoãn. Nếu trung_tam.py đã điều phối rồi thì trả nguyên."""
    if os.environ.get("QUOTA_PHUT_DA_DIEU_PHOI"):
        return float(mac_dinh)
    q = quyet_dinh(viec, mac_dinh, so_lieu)
    print("⏱️ Quota phút: %s → %s" % (q["viec"], ("tối đa %d phút" % q["phut"]) if q["cho_chay"] else "hoãn: " + q["ly_do"]), flush=True)
    return q["phut"]


# ============================== GHI SHEET · BÁO TELEGRAM ==============================
def _bao(noi_dung):
    try:
        import thong_bao
        thong_bao.gui_telegram(noi_dung)
    except Exception as e:                                   # tuỳ chọn: không có Telegram thì bỏ qua
        print("Telegram bỏ qua (%s): %s" % (str(e)[:60], noi_dung), flush=True)


def _tab(kho, ten, cot):
    import gspread
    try:
        return kho.worksheet(ten)
    except gspread.WorksheetNotFound:
        return kho.add_worksheet(ten, rows=600, cols=cot)


def _mo_kho(gc=None, kho=None):
    """Mở Sheet ghi số liệu mà không phải nạp doc_de.py (nặng)."""
    ma = os.environ.get("QUOTA_SHEET_ID") or os.environ.get("SHEET_ID") or ID_KHO_CHUNG
    if gc is not None and (os.environ.get("QUOTA_SHEET_ID") or kho is None):
        return gc.open_by_key(ma)
    if kho is not None:
        return kho
    import gspread
    from google.oauth2 import service_account
    cred = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_CREDENTIALS"]), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return gspread.authorize(cred).open_by_key(ma)


def bang_hien_thi(tt, ke, da_bao=0):
    """Nội dung tab Quota_Phut (danh sách dòng). Tách ra để test."""
    bay_gio = dt.datetime.now(TZ).strftime("%d/%m/%Y %H:%M")
    nguon = "billing GitHub" if tt["co_billing"] else "ước tính từ lượt chạy của repo này"
    muc_can = muc_toi_thieu_cho_chay(ke["nhip"])
    hang = [["Chỉ số", "Giá trị", "Ghi chú"],
            ["Tháng", tt["thang"], "chu kì = tháng dương lịch"],
            ["Hạn mức tháng (phút)", ke["quota"], "GH_QUOTA_PHUT_THANG"],
            ["Đã dùng cả tháng", round(tt["da_dung_thang"]), nguon],
            ["… trong đó repo này (ước tính)", round(tt["uoc_repo_thang"]), "thời gian chạy làm tròn lên"],
            ["… repo / nguồn khác", round(max(0.0, tt["da_dung_thang"] - tt["uoc_repo_thang"])), "chỉ có khi có GH_BILLING_TOKEN"],
            ["Còn lại cả tháng", round(ke["con_lai_thang"]), ""],
            ["Dự phòng giữ lại", round(DU_PHONG), "chỉ việc khẩn dùng hết; việc theo yêu cầu chừa lại một nửa"],
            ["Số ngày còn lại (kể cả hôm nay)", ke["so_ngay_con_lai"], ""],
            ["Ngân sách mỗi ngày (hôm nay)", round(ke["ngan_sach_ngay"], 1), "= (hạn mức − dự phòng − đã dùng trước hôm nay) / số ngày còn lại"],
            ["Ngân sách chuẩn (chia đều từ đầu tháng)", round(ke["ngan_sach_chuan"], 1), ""],
            ["Nhịp tiêu thụ", round(ke["nhip"], 2), "= ngân sách ngày / chuẩn; <1 là đã tiêu quá tay"],
            ["Việc định kì đang được chạy", "mức ≥ %d" % muc_can, "nhịp ≥0,8: mọi mức · ≥0,55: ≥2 · ≥0,3: ≥3 · ≥0,12: ≥4 · thấp hơn: chỉ mức 5"],
            ["Đã dùng HÔM QUA (%s)" % tt["hom_qua"].strftime("%d/%m"), round(tt["da_dung_hom_qua"]), ""],
            ["Đã dùng hôm nay", round(tt["da_dung_hom_nay"]), ""],
            ["Còn lại hôm nay", round(ke["con_lai_hom_nay"], 1), ""],
            ["Dự báo cuối tháng (thô)", round(ke["du_bao_cuoi_thang"]), "nếu giữ tốc độ dùng trung bình từ đầu tháng"],
            ["Mức cảnh báo đã báo (%)", max(da_bao, muc_canh_bao(tt["da_dung_thang"])), "70 / 90 / 100 (ghi nhớ để không báo lặp)"],
            ["Cập nhật lúc", bay_gio, ""], [],
            ["Việc", "Mức (1-5)", "Loại", "Hôm qua", "Hôm nay", "Cả tháng", "Lượt tháng", "TB phút/lượt", "Phân bổ hôm nay", "Còn lại hôm nay", "Trạng thái hiện tại"]]
    phan = phan_bo_ngay(ke, tt["hom_nay_theo_viec"])
    cac = sorted(set(CAU_HINH) | set(tt["thang_theo_viec"]) | set(tt["hom_qua_theo_viec"]),
                 key=lambda v: (-tt["thang_theo_viec"].get(v, 0), v))
    ten_loai = {"khan": "khẩn", "yeu_cau": "theo yêu cầu", "dinh_ky": "định kì"}
    for v in cac:
        c = cau_hinh_viec(v)
        dung, luot = tt["thang_theo_viec"].get(v, 0), tt["luot_thang"].get(v, 0)
        p = phan.get(v)
        hang.append([v, c["muc"], ten_loai.get(c["loai"], c["loai"]), tt["hom_qua_theo_viec"].get(v, 0), tt["hom_nay_theo_viec"].get(v, 0),
                     dung, luot, round(dung / luot, 1) if luot else "", round(p, 1) if p is not None else "",
                     round(max(0.0, p - tt["hom_nay_theo_viec"].get(v, 0)), 1) if p is not None else "", trang_thai_viec(v, tt)])
    return hang


# ============================== [22/11/2026] SỐ LIỆU CHO BẢN ĐỒ NHIỆT ==============================
NHAN_HIEN_THI = {"doc_de": "Đọc đề", "duyet_cau": "Duyệt câu", "tu_giai": "Tự giải", "tim_kiem": "Tìm kiếm tài liệu",
                 "tao_de": "Tạo đề", "quet_anh_cron": "Quét bù hình ảnh", "gan_mo_ta_anh": "Gán mô tả ảnh",
                 "tai_tai_lieu": "Tải tài liệu", "chuyen_de": "Chuyên đề", "soan_giao_an": "Soạn giáo án", "kiem_thu": "Kiểm thử",
                 "xuat_de": "Xuất đề & dữ liệu", "chi_muc_trung": "Chỉ mục trùng", "canh_gac": "Canh gác", "de_cuong": "Đề cương",
                 "thu_drive": "Thử Drive", "xuat_word": "Xuất Word", "pages_build_deployment": "pages_build_deployment"}


def _gia_tri_cron(truong, thap, cao):
    """Một trường cron (số · */n · a,b,c · *) → danh sách số. Dạng lạ (dải a-b…) trả None."""
    kq = set()
    for p in truong.split(","):
        if p == "*":
            kq |= set(range(thap, cao + 1))
        elif re.fullmatch(r"\*/\d+", p) and int(p[2:]) > 0:
            kq |= set(range(thap, cao + 1, int(p[2:])))
        elif p.isdigit():
            kq.add(int(p))
        else:
            return None
    return sorted(kq)


def gio_chay_tu_yml(van_ban):
    """Nội dung workflow .yml → danh sách 'HH:MM' giờ Việt Nam (cron là UTC, +7). Không có lịch → []. Không hiểu được → None."""
    ket = []
    for m in re.finditer(r"^\s*-?\s*cron:\s*[\"']([^\"']+)[\"']", van_ban, re.M):
        f = m.group(1).split()
        if len(f) < 2:
            return None
        ph, gi = _gia_tri_cron(f[0], 0, 59), _gia_tri_cron(f[1], 0, 23)
        if ph is None or gi is None:
            return None
        ket += [((g + 7) % 24, p) for g in gi for p in ph]
    return ["%02d:%02d" % x for x in sorted(set(ket))]


def mo_ta_gio_chay(viec, thu_muc_wf=None):
    """Chuỗi hiển thị cột 'Giờ chạy hằng ngày'. Đọc cron từ .github/workflows của repo (có sau actions/checkout)."""
    if viec == "pages_build_deployment":
        return "GitHub tự chạy khi đẩy code"
    thu_muc_wf = thu_muc_wf or os.path.join(THU_MUC, ".github", "workflows")
    van_ban = None
    try:
        for ten in os.listdir(thu_muc_wf):
            if chuan_hoa(re.sub(r"\.ya?ml$", "", ten)) == viec:
                with open(os.path.join(thu_muc_wf, ten), encoding="utf-8") as f:
                    van_ban = f.read()
                break
    except OSError:
        pass
    if van_ban is None:
        return "chưa rõ (không thấy workflow)"
    gio = gio_chay_tu_yml(van_ban)
    if gio is None:
        return "chưa đọc được lịch cron"
    if gio:
        return ", ".join(gio)
    return "khi đẩy code" if re.search(r"^\s*push:", van_ban, re.M) else "theo yêu cầu / chạy tay"


def bang_ban_do(tt, thu_muc_wf=None):
    """Nội dung tab Quota_Phut_BanDo: mỗi việc một dòng, sắp theo phút cả tháng giảm dần. Hàm thuần (test không cần mạng).
    Tỉ trọng ngày = phút HÔM QUA ÷ tổng phút hôm qua; tỉ trọng tháng = phút cả tháng ÷ tổng phút cả tháng (số ước tính của repo);
    số ngày có chạy = số ngày trong tháng (tính đến hôm nay) mà việc có ít nhất 1 phút."""
    thang, hn = tt["thang"], tt["hom_nay"]
    tong_hq = sum(tt["hom_qua_theo_viec"].values())
    tong_th = sum(tt["thang_theo_viec"].values())
    ngay_chay = {}
    for (n, v), x in tt["uoc"].items():
        if n.startswith(thang) and x[0] > 0:
            ngay_chay[v] = ngay_chay.get(v, 0) + 1
    hang = [["Việc", "Tên hiển thị", "Giờ chạy hằng ngày (giờ VN)", "Phút hôm qua (%s)" % tt["hom_qua"].strftime("%d/%m"),
             "Tỉ trọng trong ngày (hôm qua)", "Phút cả tháng", "Tỉ trọng tháng", "Số ngày có chạy", "Số ngày đã qua"]]
    for v in sorted(tt["thang_theo_viec"], key=lambda k: (-tt["thang_theo_viec"][k], k)):
        hq, th = tt["hom_qua_theo_viec"].get(v, 0), tt["thang_theo_viec"][v]
        hang.append([v, NHAN_HIEN_THI.get(v, v), mo_ta_gio_chay(v, thu_muc_wf), hq,
                     round(hq / tong_hq, 4) if tong_hq else 0, th, round(th / tong_th, 4) if tong_th else 0,
                     ngay_chay.get(v, 0), hn.day])
    return hang


def ghi_ban_do(kho, tt):
    """Ghi tab Quota_Phut_BanDo (ghi đè). Lỗi bất kì chỉ cảnh báo – không làm hỏng việc chính."""
    if not GHI_BAN_DO:
        return
    try:
        tab = _tab(kho, TAB_BAN_DO, 9)
        hang = bang_ban_do(tt)
        tab.clear()
        tab.update(range_name="A1", values=hang, value_input_option="RAW")
        try:
            n = len(hang)
            tab.format("E2:E%d" % n, {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}})
            tab.format("G2:G%d" % n, {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}})
        except Exception as e:
            print("⚠️ Không định dạng % cho %s (bỏ qua): %s" % (TAB_BAN_DO, str(e)[:80]), flush=True)
    except Exception as e:
        print("⚠️ Không ghi được tab %s (bỏ qua): %s" % (TAB_BAN_DO, str(e)[:150]), flush=True)


def _doc_da_bao(tab, thang):
    """Mức cảnh báo đã báo của THÁNG NÀY (sang tháng mới thì báo lại từ đầu)."""
    da_bao, thang_cu = 0, ""
    try:
        for r in tab.get("A1:B30"):
            if r and r[0] == "Tháng" and len(r) > 1:
                thang_cu = str(r[1])
            if r and r[0] == "Mức cảnh báo đã báo (%)" and len(r) > 1:
                da_bao = int(float(str(r[1]).replace(",", ".")))
    except (ValueError, IndexError, TypeError):
        return 0
    return da_bao if thang_cu == thang else 0


def ghi_sheet(kho, tt, ke):
    tab = _tab(kho, TAB_TONG, 11)
    da_bao = _doc_da_bao(tab, tt["thang"])
    muc = muc_canh_bao(tt["da_dung_thang"])
    tab.clear()
    tab.update(range_name="A1", values=bang_hien_thi(tt, ke, da_bao), value_input_option="RAW")
    # chi tiết tháng theo ngày × việc (giữ nguyên các tháng cũ)
    tn = _tab(kho, TAB_NGAY, 6)
    cu = [r for r in tn.get_all_values()[1:] if r and r[0] != tt["thang"]]
    moi = [[tt["thang"], n, v, x[0], x[1]] for (n, v), x in sorted(tt["uoc"].items()) if n.startswith(tt["thang"])]
    tn.clear()
    tn.update(range_name="A1", values=[["Tháng", "Ngày", "Việc", "Phút (ước tính)", "Số lượt"]] + cu + moi, value_input_option="RAW")
    ghi_ban_do(kho, tt)
    return muc, da_bao


def cap_nhat(gc=None, kho=None, so_lieu=None):
    """Đọc số liệu, ghi Sheet, báo Telegram khi chạm mốc mới. Không bao giờ ném lỗi."""
    if CHE_DO == "tat":
        return
    try:
        sl = so_lieu or doc_so_lieu()
        if not sl:
            return
        tt = tong_hop(sl)
        ke = ke_hoach(tt["hom_nay"], tt["da_dung_thang"], tt["da_dung_hom_nay"])
        for d in tom_tat(tt, ke):
            print(d, flush=True)
        muc, da_bao = ghi_sheet(_mo_kho(gc, kho), tt, ke)
        du_bao_vuot = ke["du_bao_cuoi_thang"] > ke["quota"] and tt["hom_nay"].day >= 5
        if muc > da_bao:
            _bao("⏱️ Phút GitHub Actions: đã dùng %d/%d phút (%d%%) trong tháng %s. Ngân sách hôm nay còn %d phút." % (
                tt["da_dung_thang"], ke["quota"], muc, tt["thang"], ke["con_lai_hom_nay"]))
        elif du_bao_vuot and tt["hom_nay"].day % 5 == 0 and tt["da_dung_hom_nay"] > 0 and da_bao < 100:
            _bao("⏱️ Dự báo thô: giữ tốc độ này thì cuối tháng dùng ~%d phút, vượt hạn mức %d. Các việc nhẹ sẽ tự bị hoãn trước." % (
                ke["du_bao_cuoi_thang"], ke["quota"]))
    except Exception as e:
        print("⚠️ Quota phút: không ghi được Sheet (bỏ qua):", str(e)[:150], flush=True)


def bao_cao_markdown(so_lieu=None):
    """Đoạn markdown cho báo cáo canh gác / Summary: tháng, hôm qua, từng việc, việc đang bị tạm dừng. Trả (đoạn markdown, mức cảnh báo %, các dòng tóm tắt) hoặc (None, 0, [])."""
    sl = so_lieu or doc_so_lieu()
    if not sl:
        return None, 0, []
    tt = tong_hop(sl)
    ke = ke_hoach(tt["hom_nay"], tt["da_dung_thang"], tt["da_dung_hom_nay"])
    ngan = tom_tat(tt, ke, so_viec=6)
    dong = ["## ⏱️ Phút GitHub Actions"] + ["- " + d for d in ngan] + [""]
    dong += ["| Việc | Mức | Hôm qua | Hôm nay | Cả tháng | Trạng thái |", "|---|---|---|---|---|---|"]
    cac = sorted(set(tt["thang_theo_viec"]) | set(tt["hom_qua_theo_viec"]) | set(tt["hom_nay_theo_viec"]),
                 key=lambda v: (-tt["thang_theo_viec"].get(v, 0), v))
    for v in cac:
        dong.append("| %s | %d | %d | %d | %d | %s |" % (v, cau_hinh_viec(v)["muc"], tt["hom_qua_theo_viec"].get(v, 0),
                                                          tt["hom_nay_theo_viec"].get(v, 0), tt["thang_theo_viec"].get(v, 0), trang_thai_viec(v, tt)))
    return "\n".join(dong) + "\n", muc_canh_bao(tt["da_dung_thang"]), ngan


def cong():
    """Cổng RẺ chạy ngay sau checkout (chỉ thư viện chuẩn, chưa cài gì): in chay=false vào GITHUB_OUTPUT nếu lượt cron này sẽ bị hoãn,
    để các bước sau (setup-python, pip, chạy việc) được bỏ qua – lượt hoãn chỉ tốn ~1 phút thay vì ~2. Lỗi bất kì → chay=true (trung_tam.py quyết định lại)."""
    chay, viec = True, ""
    try:
        viec = viec_tu_tep("")
        q = quyet_dinh(viec)
        chay = q["cho_chay"] or q["loai_hieu_luc"] != "dinh_ky"
        if not q["cho_chay"] and cau_hinh_viec(viec).get("tay"):
            chay = False      # việc chạy tay thuần (không có Apps Script chờ ket_qua): hoãn thì bỏ qua từ cổng, khỏi tốn phút cài đặt
        if not chay:
            print("⏸️ Cổng phút: việc `%s` (mức %d) hoãn lượt này – %s" % (viec, q["muc"], q["ly_do"]), flush=True)
            if os.environ.get("GITHUB_STEP_SUMMARY"):
                with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
                    f.write("### ⏸️ Hoãn lượt `%s`\n- %s\n" % (viec, q["ly_do"]))
    except Exception as e:
        print("⚠️ Cổng phút lỗi (%s) → cho chạy." % str(e)[:80], flush=True)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write("chay=%s\n" % ("true" if chay else "false"))
    return chay


def main():
    if "--cong" in sys.argv:
        cong()
        return
    cap_nhat()
    sl = doc_so_lieu()
    if not sl:
        return
    tt = tong_hop(sl)
    ke = ke_hoach(tt["hom_nay"], tt["da_dung_thang"], tt["da_dung_hom_nay"])
    for d in tom_tat(tt, ke, so_viec=10):
        print(d, flush=True)
    print("%-16s %5s %9s %8s %9s  %s" % ("việc", "mức", "hôm qua", "hôm nay", "cả tháng", "trạng thái"), flush=True)
    for v in sorted(set(tt["thang_theo_viec"]) | set(tt["hom_nay_theo_viec"]), key=lambda v: -tt["thang_theo_viec"].get(v, 0)):
        print("%-16s %5d %9d %8d %9d  %s" % (v, cau_hinh_viec(v)["muc"], tt["hom_qua_theo_viec"].get(v, 0), tt["hom_nay_theo_viec"].get(v, 0),
                                              tt["thang_theo_viec"].get(v, 0), trang_thai_viec(v, tt)), flush=True)


if __name__ == "__main__":
    main()
