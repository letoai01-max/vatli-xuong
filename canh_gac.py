"""
canh_gac.py – NGƯỜI CANH GÁC NGOÀI (GitHub Actions, độc lập hoàn toàn với Google Apps Script)

Mỗi sáng 7h20 (giờ Việt Nam) chỉ ĐỌC Kho chung bằng tài khoản dịch vụ:
  1. Tab Agent: agent có "Chu kì tối đa (giờ)" mà quá hạn → báo; lỗi trong 2 ngày gần nhất → báo.
  2. Tab ThoiGianChay: Meta-agent phải ghi dòng TỔNG của hôm qua (lúc 6h). Không có → Meta có thể đã ngừng.
     Có thì so tổng phút trigger với trần 90 phút/ngày.
Có vấn đề → lượt chạy báo ĐỎ và GitHub tự gửi email cho chủ kho. Không có vấn đề → lượt chạy XANH.
Báo cáo đầy đủ nằm ở trang tóm tắt (Summary) của lượt chạy trong tab Actions.
"""
import datetime as dt, json, os, re, sys

import gspread
from google.oauth2 import service_account

ID_KHO_CHUNG = "1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc"
TZ = dt.timezone(dt.timedelta(hours=7))
TRAN_PHUT, NGUONG = 90, 0.8
DU_PHONG_GIO = 3
NGAY_CHAY_THEO_YEU_CAU = 7
NGAY_LOI_GAN_DAY = 2


def doc_ngay(s):
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?", str(s or ""))
    if not m:
        return None
    # không có giờ → coi là cuối ngày, tránh báo quá hạn sớm
    return dt.datetime(int(m[3]), int(m[2]), int(m[1]), int(m[4] or 23), int(m[5] or 59), tzinfo=TZ)


def main():
    cred = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_CREDENTIALS"]), scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    kho = gspread.authorize(cred).open_by_key(ID_KHO_CHUNG)
    bay = dt.datetime.now(TZ)
    van, ghi_chu, tot = [], [], []

    # ---- 1. Meta-agent còn sống: dòng TỔNG của hôm qua trong ThoiGianChay ----
    try:
        tg = kho.worksheet("ThoiGianChay").get_all_values()[1:]
        hom_qua = (bay - dt.timedelta(days=1)).strftime("%d/%m/%Y")
        tong = [r for r in tg if len(r) >= 7 and r[0] == hom_qua and r[1] == "TỔNG"]
        if not tong:
            van.append("**Meta-agent không ghi thống kê ngày %s** (tab ThoiGianChay). Meta có thể đã ngừng, mất trigger "
                       "hoặc lỗi quyền script.processes – mở Meta-agent → Lượt thực thi, tìm TG_hangNgay." % hom_qua)
        else:
            phut = float(str(tong[-1][4]).replace(",", ".") or 0)
            if phut >= TRAN_PHUT * NGUONG:
                van.append("Thời gian chạy trigger ngày %s: **%.1f/%d phút** – sát trần, các agent có thể bị dừng." % (hom_qua, phut, TRAN_PHUT))
            else:
                tot.append("trigger hôm qua %.1f/%d phút" % (phut, TRAN_PHUT))
    except gspread.WorksheetNotFound:
        ghi_chu.append("Chưa có tab ThoiGianChay (chưa cài ThoiGianChay.gs trong Meta).")

    # ---- 2. Nhịp chạy và lỗi của từng agent ----
    dung_nhip = 0
    for r in kho.worksheet("Agent").get_all_values()[1:]:
        r = (r + [""] * 8)[:8]
        ten = r[0].strip()
        if not ten:
            continue
        chu_ki = float(r[3] or 0) if re.match(r"^\d+(\.\d+)?$", str(r[3]).strip()) else 0
        ok, loi, note = doc_ngay(r[4]), doc_ngay(r[5]), r[6]
        gio_ok = (bay - ok).total_seconds() / 3600 if ok else float("inf")
        if chu_ki:
            if gio_ok > chu_ki + DU_PHONG_GIO:
                van.append("**%s** quá hạn: lần chạy tốt cuối %s (chu kì tối đa %g giờ)." % (ten, r[4] or "chưa có", chu_ki))
            else:
                dung_nhip += 1
        elif gio_ok > NGAY_CHAY_THEO_YEU_CAU * 24:
            ghi_chu.append("%s: chưa chạy từ %s (chạy theo yêu cầu – bình thường nếu không giao việc)." % (ten, r[4] or "chưa từng"))
        else:
            dung_nhip += 1
        if loi and (not ok or loi >= ok) and (bay - loi).total_seconds() < NGAY_LOI_GAN_DAY * 86400:
            ngan = re.sub(r"\s+", " ", note)[:160]
            (ghi_chu if re.search(r"HET_LUOT|429|quota", note, re.I) else van).append("%s lỗi lúc %s: %s" % (ten, r[5], ngan))
    tot.append("%d agent đúng nhịp" % dung_nhip)

    # ---- Báo cáo ----
    dong = ["# 🛡️ Canh gác hệ thống agent – %s" % bay.strftime("%H:%M %d/%m/%Y"), ""]
    dong += ["## ⚠️ Cần xem ngay"] + ["- " + x for x in van] + [""] if van else ["## ✅ Không phát hiện sự cố", ""]
    if ghi_chu:
        dong += ["## Ghi chú"] + ["- " + x for x in ghi_chu] + [""]
    dong += ["**Đang ổn:** " + " · ".join(tot)]
    bao_cao = "\n".join(dong)
    print(bao_cao)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(bao_cao + "\n")
    if van:
        sys.exit("Phát hiện %d vấn đề – xem trang Summary của lượt chạy." % len(van))


if __name__ == "__main__":
    main()
