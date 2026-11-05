"""
giao_thuc.py – GIAO THỨC "GÓI VIỆC v2 / KẾT QUẢ v2" GIỮA APPS SCRIPT VÀ XƯỞNG PYTHON (tạo đề).

Apps Script (XuongTaoDeV2.gs) ghi goi_de_<mã>.json + ket_qua_<mã>.json + 2 tệp Word rỗng (HS, GV) rồi gửi tao_de.yml.
Xưởng đọc gói, ghi tiến độ vào ket_qua, cuối cùng ghi đề và 2 tệp Word. Tệp do thầy sở hữu → chỉ CẬP NHẬT, không tạo mới
(tài khoản dịch vụ không có dung lượng Drive).

GÓI v2 (goi_de_<mã>.json)
  phienBan   2
  loai       "tao_de" | "sua_cau" | "tron_de"
  ma         "TD-051126-101500"
  cauHinh    {grade, subject, textbook, tenDe, thoiGianPhut, dauTrang: [["tieu"|"phu"|"nghieng", "chữ"], ...]}
  thamSo     {B3, B4, B5, B8, B9, B15, B24, B25, B26}      (giá trị ô, chỉ để tham chiếu)
  trangThai0 {yc:{p1..p4}, dm:{p1..p4}, dsMa:[...], vtThucTien:{...}, nganHang:"..."}   (= khoiTaoTrangThaiAgent, bỏ phần chạy)
  tuyChon    {cheDo:"day_du"|"nhanh", xacMinh:true, hinhAnh:true, dungCauMau:true}
  dich       {docxHS:<fileId>, docxGV:<fileId>}
  phieu      (chỉ loai "sua_cau") {de:{phan1..4}, cau:[{phan, so, lyDo}]}

KẾT QUẢ v2 (ket_qua_<mã>.json)
  phienBan 2 · trangThai CHO|DANG_LAM|XONG|LOI|HOAN · buoc · phanTram · luot · nhatKy[{t,b,c}] · canhBao[]
  deThi {phan1..phan4} · model · tomTat{} · tep{docxHS, docxGV} · hoanDen (ISO, chỉ khi HOAN) · loi · luc
  HOAN = hết hạn mức Gemini: Apps Script gửi lại sau hoanDen. Đề đang soạn dở nằm trong deThi/tienDo để làm tiếp.

Gói cũ (v1: chỉ có B9, grade, maDe…) vẫn đọc được: phienBan = 1.
"""
import datetime as dt
import io
import json
import time

TZ = dt.timezone(dt.timedelta(hours=7))
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TRANG_THAI = ("CHO", "DANG_LAM", "XONG", "LOI", "HOAN")
LOAI_VIEC = ("tao_de", "sua_cau", "tron_de")
NHAT_KY_TOI_DA = 300
KHOANG_GHI_GIAY = 20          # không ghi Drive dày hơn mức này (trừ khi ép)


def bay_gio():
    return dt.datetime.now(TZ)


def kiem_goi(goi):
    """Trả về danh sách lỗi của gói (rỗng = dùng được). Gói v1 chỉ cần grade."""
    if not isinstance(goi, dict):
        return ["gói không phải đối tượng JSON"]
    if goi.get("phienBan", 1) == 1:
        return [] if (goi.get("grade") or goi.get("B9")) else ["gói v1 thiếu grade/B9"]
    loi = []
    if goi.get("phienBan") != 2:
        loi.append("phienBan không hỗ trợ: %r" % goi.get("phienBan"))
    if goi.get("loai") not in LOAI_VIEC:
        loi.append("loai phải là một trong %s" % ", ".join(LOAI_VIEC))
    if not goi.get("ma"):
        loi.append("thiếu ma")
    ch = goi.get("cauHinh") or {}
    if str(ch.get("grade", "")) not in ("10", "11", "12"):
        loi.append("cauHinh.grade phải là 10, 11 hoặc 12")
    if goi.get("loai") in ("tao_de", None):
        yc = (goi.get("trangThai0") or {}).get("yc") or {}
        if not all(k in yc and isinstance(yc[k], int) and yc[k] >= 0 for k in ("p1", "p2", "p3", "p4")):
            loi.append("trangThai0.yc phải có p1..p4 là số nguyên ≥ 0")
        elif sum(yc[k] for k in ("p1", "p2", "p3", "p4")) == 0:
            loi.append("trangThai0.yc: tổng số câu bằng 0")
    if goi.get("loai") == "sua_cau" and not (goi.get("phieu") or {}).get("cau"):
        loi.append("loai sua_cau cần phieu.cau")
    if goi.get("loai") != "tron_de":
        d = goi.get("dich") or {}
        if not (d.get("docxHS") and d.get("docxGV")):
            loi.append("thiếu dich.docxHS / dich.docxGV (tệp Word rỗng do Apps Script tạo sẵn)")
    return loi


# ---------------- Drive (nạp muộn để module chạy được khi chưa cài thư viện Google) ----------------
def doc_json_drive(drive, file_id):
    from googleapiclient.http import MediaIoBaseDownload
    buf = io.BytesIO()
    tai = MediaIoBaseDownload(buf, drive.files().get_media(fileId=file_id))
    xong = False
    while not xong:
        _, xong = tai.next_chunk()
    return json.loads(buf.getvalue().decode("utf-8") or "{}")


def ghi_json_drive(drive, file_id, du_lieu):
    from googleapiclient.http import MediaIoBaseUpload
    media = MediaIoBaseUpload(io.BytesIO(json.dumps(du_lieu, ensure_ascii=False).encode("utf-8")), mimetype="text/plain")
    drive.files().update(fileId=file_id, media_body=media).execute()


def ghi_docx_vao_tep(drive, file_id, duong_dan, ten_moi=None):
    """Ghi đè nội dung Word vào tệp rỗng đã tạo sẵn (đổi tên nếu cần)."""
    from googleapiclient.http import MediaFileUpload
    body = {"name": ten_moi} if ten_moi else None
    drive.files().update(fileId=file_id, body=body, media_body=MediaFileUpload(duong_dan, mimetype=MIME_DOCX)).execute()


def danh_dau_loi_tep(drive, file_id, ly_do):
    """Tệp đích lỗi → đổi tên "(LỖI) …" để thầy nhìn thấy (cùng quy ước vẽ hình)."""
    try:
        cu = drive.files().get(fileId=file_id, fields="name").execute().get("name", "")
        if not cu.startswith("(LỖI)"):
            drive.files().update(fileId=file_id, body={"name": "(LỖI) " + cu, "description": str(ly_do)[:300]}).execute()
    except Exception:
        pass


class Phien:
    """Một phiên làm việc của xưởng: giữ trạng thái kết quả trong bộ nhớ, ghi ra Drive có tiết chế."""

    def __init__(self, drive, kq_id, goi):
        self.drive, self.kq_id, self.goi = drive, kq_id, goi
        self.ma = goi.get("ma", "")
        self.nhat_ky, self.canh_bao = [], []
        self.buoc, self.phan_tram, self.luot = "", 0, int(goi.get("luot", 0) or 0)
        self.extra = {}
        self._lan_ghi = 0.0

    # --- nhật ký / tiến độ ---
    def ghi_nhat_ky(self, buoc, chi_tiet=""):
        self.nhat_ky.append({"t": bay_gio().strftime("%H:%M:%S"), "b": str(buoc)[:80], "c": str(chi_tiet)[:400]})
        if len(self.nhat_ky) > NHAT_KY_TOI_DA:
            self.nhat_ky = self.nhat_ky[-NHAT_KY_TOI_DA:]
        print("[%s] %s %s" % (self.nhat_ky[-1]["t"], buoc, chi_tiet), flush=True)

    def tien_do(self, buoc, phan_tram=None, chi_tiet=""):
        self.buoc = buoc
        if phan_tram is not None:
            self.phan_tram = max(self.phan_tram, min(99, int(phan_tram)))
        self.ghi_nhat_ky(buoc, chi_tiet)
        self.ghi("DANG_LAM")

    def them_canh_bao(self, text):
        if text and text not in self.canh_bao:
            self.canh_bao.append(str(text)[:300])

    # --- ghi kết quả ---
    def _noi_dung(self, trang_thai, **them):
        kq = {"phienBan": 2, "trangThai": trang_thai, "ma": self.ma, "buoc": self.buoc, "phanTram": self.phan_tram,
              "luot": self.luot, "nhatKy": self.nhat_ky, "canhBao": self.canh_bao, "luc": bay_gio().isoformat()}
        kq.update(self.extra)
        kq.update(them)
        return kq

    def ghi(self, trang_thai, ep=False, **them):
        if not ep and time.time() - self._lan_ghi < KHOANG_GHI_GIAY:
            return
        if trang_thai not in TRANG_THAI:
            raise ValueError("trangThai lạ: " + trang_thai)
        ghi_json_drive(self.drive, self.kq_id, self._noi_dung(trang_thai, **them))
        self._lan_ghi = time.time()

    def xong(self, de, tep=None, tom_tat=None, model=""):
        self.phan_tram, self.buoc = 100, "xong"
        self.ghi("XONG", ep=True, deThi=de, tep=tep or {}, tomTat=tom_tat or {}, model=model)

    def loi(self, thong_bao):
        self.ghi("LOI", ep=True, loi=str(thong_bao)[:500])

    def hoan(self, ly_do, phut_cho, de_dang_soan=None, tien_do_luu=None):
        den = (bay_gio() + dt.timedelta(minutes=phut_cho)).isoformat()
        them = {"loi": str(ly_do)[:300], "hoanDen": den}
        if de_dang_soan is not None:
            them["deThi"] = de_dang_soan
        if tien_do_luu is not None:
            them["tienDo"] = tien_do_luu
        self.ghi("HOAN", ep=True, **them)
