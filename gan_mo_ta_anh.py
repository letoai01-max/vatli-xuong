# -*- coding: utf-8 -*-
"""
gan_mo_ta_anh.py – GẮN MÔ TẢ CHO ẢNH TRONG KHO ẢNH SGK (workflow gan_mo_ta_anh.yml, chạy tay khi cần).

Vì sao cần: soan_giao_an.py chọn ảnh theo chữ trong TÊN TỆP + TÊN THƯ MỤC + MÔ TẢ trên Drive; nó không đọc chữ nằm trong ảnh.
Ảnh tên kiểu "Screenshot 2026-09-29 131110.png" vì vậy không bao giờ khớp. Script này:
  1. Liệt kê ảnh trong kho (KHO_ANH_SGK_ID, kể cả thư mục con).
  2. Với ảnh CHƯA có mô tả: gửi ảnh cho Gemini → đọc số hình ("Hình 26.1") nếu in trong ảnh, tóm tắt nội dung, rút từ khoá.
  3. Ghi kết quả vào ô MÔ TẢ (description) của tệp trên Drive, dạng:
        Hình 26.1 – Tàu lượn siêu tốc ... Bài: Cơ năng. Từ khoá: cơ năng, thế năng, ... [AI]
     (đứng đầu là số hình để xưởng cộng điểm trùng số hình; đuôi [AI] đánh dấu mô tả do máy viết).
  4. Luôn ghi thêm out/chi_muc_anh.json (id → mô tả). Nếu tài khoản dịch vụ chỉ có quyền XEM (không ghi được mô tả),
     hãy tải tệp này ở Artifacts, đặt vào thư mục gốc của repo với tên chi_muc_anh.json: soan_giao_an.py tự đọc.

An toàn khi chạy lại: ảnh đã có mô tả do NGƯỜI viết không bao giờ bị ghi đè; ảnh có mô tả [AI] bị bỏ qua trừ khi LAM_LAI=1;
mỗi lượt chỉ xử lí TOI_DA ảnh (mặc định 60) để không cạn hạn mức Gemini – chạy lại để làm tiếp phần còn lại.

Biến môi trường: GOOGLE_CREDENTIALS, GEMINI_API_KEY, KHO_ANH_SGK_ID; tuỳ chọn TOI_DA, LAM_LAI (1 = viết lại mô tả [AI]).
"""
import json
import os
import re
import shutil
import sys
import tempfile
import time

from googleapiclient.errors import HttpError

import de_cuong as DC
import soan_giao_an as SG          # dùng lại: nap_kho_anh, _tai_anh
import ve_hinh as VH               # dùng lại: goi_json (Gemini đọc ảnh)

THU_MUC_RA = "out"
DAU_AI = "[AI]"
GIAN_CACH_GIAY = 4                 # nghỉ giữa hai lượt gọi Gemini
LOI_NHAC = (
    "Đây là MỘT ảnh trong kho ảnh sách giáo khoa Vật lí THPT (bộ Kết nối tri thức hoặc sách Chuyên đề). "
    "Tệp có thể là ảnh chụp màn hình nên chú thích 'Hình n.m' có thể nằm ở mép ảnh, bị cắt hoặc không có.\n"
    "Thư mục chứa ảnh: %s | Tên tệp: %s\n\n"
    "NHIỆM VỤ:\n"
    "1) soHinh: nếu thấy RÕ chú thích dạng 'Hình 26.1' in trong ảnh thì chép số (ví dụ \"26.1\"); không chắc chắn thì để chuỗi rỗng, KHÔNG đoán.\n"
    "2) noiDung: một đến hai câu ngắn nói ảnh thể hiện gì về mặt vật lí (hiện tượng, thiết bị, thí nghiệm, đồ thị, đại lượng và nhãn đọc được).\n"
    "3) bai: tên bài học / chủ đề vật lí mà ảnh minh hoạ (rỗng nếu không suy ra được).\n"
    "4) tuKhoa: 4–8 từ khoá tiếng Việt về nội dung vật lí để tìm lại ảnh (ví dụ: cơ năng, con lắc đơn, bảo toàn năng lượng).\n"
    "Trả về JSON đúng dạng: {\"soHinh\": \"\", \"noiDung\": \"\", \"bai\": \"\", \"tuKhoa\": []}"
)


def tao_mo_ta(kq):
    so = str(kq.get("soHinh") or "").strip().replace(",", ".").replace("-", ".")
    so = so if re.fullmatch(r"\d{1,2}\.\d{1,2}", so) else ""
    nd = re.sub(r"\s+", " ", str(kq.get("noiDung") or "")).strip().rstrip(".")
    bai = re.sub(r"\s+", " ", str(kq.get("bai") or "")).strip().rstrip(".")
    tk = [re.sub(r"\s+", " ", str(t)).strip() for t in (kq.get("tuKhoa") or []) if str(t).strip()][:8]
    if not nd and not tk:
        return ""
    phan = [("Hình %s – " % so if so else "") + (nd + "." if nd else "")]
    if bai:
        phan.append("Bài: %s." % bai)
    if tk:
        phan.append("Từ khoá: %s." % ", ".join(tk))
    return (" ".join(phan) + " " + DAU_AI)[:900]


def main():
    toi_da = int(os.environ.get("TOI_DA", "60") or 60)
    lam_lai = os.environ.get("LAM_LAI", "").strip().lower() in ("1", "true", "yes")
    gc, drive = DC.ket_noi()
    cac_model = DC.ds_model(gc)
    kho = SG.nap_kho_anh(drive)
    if not kho:
        sys.exit("❌ Kho ảnh trống hoặc không đọc được: kiểm tra KHO_ANH_SGK_ID và việc chia sẻ thư mục cho tài khoản dịch vụ.")

    os.makedirs(THU_MUC_RA, exist_ok=True)
    chi_muc, dau = {}, os.path.join(THU_MUC_RA, "chi_muc_anh.json")
    if os.path.isfile("chi_muc_anh.json"):                   # giữ kết quả của các lượt trước (nếu đã đặt vào repo)
        try:
            chi_muc = json.load(open("chi_muc_anh.json", encoding="utf-8"))
        except Exception:
            chi_muc = {}

    can_lam = []
    for f in kho:
        mo = (f["mo_ta"] or "").strip()
        if mo and not (lam_lai and mo.endswith(DAU_AI)):
            continue                                          # đã có mô tả (của người, hoặc của máy và không yêu cầu làm lại)
        if f["id"] in chi_muc and not lam_lai:
            continue
        can_lam.append(f)
    print("🖼️ Kho %d ảnh; %d ảnh chưa có mô tả; lượt này xử lí tối đa %d." % (len(kho), len(can_lam), toi_da), flush=True)

    thu = tempfile.mkdtemp(prefix="mo_ta_")
    so_ok, so_loi, ghi_duoc, het_han = 0, 0, True, False
    try:
        for k, f in enumerate(can_lam[:toi_da], 1):
            tam = os.path.join(thu, "a.png")
            try:
                b64 = SG._tai_anh(drive, f, tam)
                kq, _ = VH.goi_json([{"text": LOI_NHAC % (f["duong"] or "(gốc)", f["ten"])},
                                     {"inline_data": {"mime_type": "image/jpeg", "data": b64}}], cac_model, 0.1)
                mo_ta = tao_mo_ta(kq if isinstance(kq, dict) else {})
                if not mo_ta:
                    raise ValueError("Gemini không trả nội dung dùng được")
            except DC.HetHanMuc:
                print("⏹️ Hết hạn mức Gemini – dừng; chạy lại sau để làm tiếp.", flush=True)
                het_han = True
                break
            except Exception as e:
                so_loi += 1
                print("⚠️ [%d] %s: %s: %s" % (k, f["ten"], type(e).__name__, str(e)[:120]), flush=True)
                time.sleep(GIAN_CACH_GIAY)
                continue
            chi_muc[f["id"]] = {"ten": f["ten"], "duong": f["duong"], "mo_ta": mo_ta}
            kieu = "chỉ mục"
            if ghi_duoc:
                try:
                    drive.files().update(fileId=f["id"], body={"description": mo_ta}, supportsAllDrives=True, fields="id").execute()
                    kieu = "Drive"
                except HttpError as e:
                    if getattr(e.resp, "status", 0) in (401, 403, 404):
                        ghi_duoc = False
                        print("⚠️ Không ghi được mô tả lên Drive (thiếu quyền Người chỉnh sửa trên thư mục) – "
                              "từ giờ chỉ ghi vào out/chi_muc_anh.json.", flush=True)
                    else:
                        print("⚠️ Lỗi ghi mô tả: %s" % str(e)[:120], flush=True)
            so_ok += 1
            print("✅ [%d] %s → %s (%s)" % (k, f["ten"], mo_ta[:110], kieu), flush=True)
            with open(dau, "w", encoding="utf-8") as g:      # ghi dần: lượt chạy bị ngắt vẫn giữ được kết quả
                json.dump(chi_muc, g, ensure_ascii=False, indent=1)
            time.sleep(GIAN_CACH_GIAY)
    finally:
        shutil.rmtree(thu, ignore_errors=True)

    with open(dau, "w", encoding="utf-8") as g:
        json.dump(chi_muc, g, ensure_ascii=False, indent=1)
    con_lai = len(can_lam) - so_ok                           # gồm cả ảnh bị lỗi (sẽ thử lại ở lượt sau)
    print("\n=== XONG: mô tả được %d ảnh, lỗi %d, còn %d ảnh chưa làm. Mô tả %s ===" % (
        so_ok, so_loi, con_lai, "đã ghi lên Drive" if ghi_duoc else "CHƯA lên Drive – dùng out/chi_muc_anh.json"), flush=True)
    if con_lai:
        print("➡️ Chạy lại workflow để làm tiếp phần còn lại.", flush=True)


if __name__ == "__main__":
    main()
