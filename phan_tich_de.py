"""
phan_tich_de.py – XƯỞNG PHÂN TÍCH ĐỀ TN THPT QUỐC GIA (Vật lí). Điểm vào của "Python Analysis Engine"; chạy bởi phan_tich_de.yml.

Giao thức (cùng khuôn kiem_dinh_de / tao_de, dùng giao_thuc.Phien để ghi tiến độ):
  Apps Script (PhanTichDe.gs) lưu tệp đề vào Drive (chia quyền XEM cho tài khoản dịch vụ), ghi goi_pt_<mã>.json + ket_qua_pt_<mã>.json,
  gửi lệnh phan_tich_de.yml (ma, goi, ket_qua). Xưởng chạy 6 khối, ghi tiến độ (CHO → DANG_LAM → XONG | LOI | HOAN) vào ket_qua.
  HOAN (hết hạn mức Gemini): đã làm xong khối nào thì lưu ở ket_qua.tienDo; Apps Script gửi lại sau hoanDen và xưởng làm tiếp, không làm lại từ đầu.

GÓI (goi_pt_<mã>.json)
  phienBan 2 · loai "phan_tich_de" · ma "PT-251126-101500"
  tep        [{id, ten}]                                   tệp đề (và đáp án nếu riêng); PDF / Word / ảnh / .zip
  thongTin   {tenDe, kyThi, nam, loaiDe}                    giáo viên nhập (ưu tiên hơn thông tin mô hình đọc được)
  tuyChon    {giai:true, groq:true, phanLoaiHaiLuot:true,
              nhanThucV2:true,      [25/11] chốt mức nhận thức theo bảng tiêu chí 6 tiêu chí + bỏ phiếu (tắt = như bản cũ)
              phanXuMuc:true,       [25/11] trọng tài cho câu các phiếu mức độ lệch nhau
              soKhopDapAn:true,     [25/11] KHỚP / KHÔNG KHỚP máy · AI · người soạn với đáp án chính thức trong tệp
              theoChuong:true,      [25/11] mục phân chia số câu (kèm nội dung) theo chương
              nguonDapAnChot:"tu_dong"}   "bo" = ép coi là đề Bộ (chốt đáp án Bộ) · "khong" = không · "tu_dong" = tự nhận diện
  tieuChiMuc "…toàn văn tiêu chí mức độ…" (tuỳ chọn, ghi đè pt_danh_muc.TIEU_CHI_MUC)
  dapAnSoan  {"I.3":"B","II.1":"a) Đ, b) S, c) Đ, d) S","III.2":"2,5"}   (tuỳ chọn) đáp án do người / AI soạn đề, để so với đáp án chính thức
  cauTruc    {"1":{dang,so_cau,diem_cau},"2":{…,diem_y:[…]},"3":{…}}   (không có → mặc định pt_danh_muc)
  mucTieu    {NB,TH,VD,VDC}   thoiGianPhut   danhMuc [{lop,ma,ten}]   (không có → mặc định)
KẾT QUẢ: ket_qua.ketQua = {thongTin, cau[], maTran, thongKe, nhanXet[], canDuyet[], canhBao[], model{}, theoChuong[], baoCaoChuong, nguonDapAnChot}; tomTat cho Apps Script ghi Sheet.
Biến môi trường: GOOGLE_CREDENTIALS, GEMINI_API_KEY(_n), GROQ_API_KEY (tuỳ chọn), GOI_ID, KQ_ID.
"""
import json, os, sys

import doc_de as X
import giao_thuc as GT
import pt_danh_muc as DM
import pt_engine as E
import pt_danh_gia as DG
import pt_nhan_thuc as NT
import pt_so_khop as SK
from duyet_cau import json_cuoi  # noqa: F401  (đảm bảo module nạp được sớm, lỗi thiếu thư viện hiện ngay đầu lượt)

try:
    import quota_xuong as Q
except Exception:
    Q = None


def ket_noi_ghi():
    """Như doc_de.ket_noi nhưng có quyền SỬA Drive (ghi ket_qua)."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    import gspread
    tt = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    cred = service_account.Credentials.from_service_account_info(
        tt, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(cred), build("drive", "v3", credentials=cred, cache_discovery=False), tt.get("client_email", "")


def kiem_goi(goi):
    loi = []
    if not isinstance(goi, dict) or goi.get("loai") != "phan_tich_de":
        return ["gói không phải loai = phan_tich_de"]
    if not goi.get("ma"): loi.append("thiếu ma")
    if not [t for t in goi.get("tep") or [] if t.get("id")]: loi.append("thiếu tep[].id")
    return loi


# [26/11/2026] LỖI TẠM CỦA GEMINI (503 "high demand", 502/504, hết thời gian chờ…) KHÔNG phải lỗi của việc: đợi rồi làm tiếp từ tienDo.
# Chỉ khi thử lại LAN_THU_LAI_TOI_DA lần mà vẫn quá tải: khối Physics Solver (phần phụ) bị bỏ qua, các khối khác ghi LOI như cũ.
LAN_THU_LAI_TOI_DA = 3
PHUT_CHO_LOI_TAM = 10
_DAU_LOI_TAM = ("503", "502", "504", "high demand", "unavailable", "overloaded", "timed out", "timeout", "connection reset", "temporarily")


def la_loi_tam(e):
    """True nếu lỗi nhiều khả năng chỉ là quá tải / mạng tạm thời của Gemini (không phải lỗi dữ liệu hay hết hạn mức ngày)."""
    t = (type(e).__name__ + " " + str(e)).lower()
    return any(k in t for k in _DAU_LOI_TAM)


def main():
    gc, drive, sa = ket_noi_ghi()
    print("Tài khoản dịch vụ:", sa, flush=True)
    goi = GT.doc_json_drive(drive, os.environ["GOI_ID"])
    kq_id = os.environ["KQ_ID"]
    p = GT.Phien(drive, kq_id, goi)
    loi = kiem_goi(goi)
    if loi:
        p.loi("Gói việc không hợp lệ: " + "; ".join(loi)); sys.exit(1)
    try:
        cu = GT.doc_json_drive(drive, kq_id)
    except Exception:
        cu = {}
    tien_do = cu.get("tienDo") if isinstance(cu.get("tienDo"), dict) else {}          # kết quả dở dang của lượt HOAN trước
    p.luot = int(cu.get("luot", 0) or 0) + 1
    p.ghi_nhat_ky("Bắt đầu", "mã %s, %d tệp%s" % (goi["ma"], len(goi["tep"]), " (làm tiếp lượt trước)" if tien_do else ""))
    p.tien_do("Chuẩn bị", 2)

    try:
        kho = gc.open_by_key(X.ID_KHO_CHUNG)
        ds_model = X.doc_cau_hinh(kho)
        try:
            yccd = X.doc_yccd(kho)["van_ban"]
        except Exception as e:
            yccd = ""; p.them_canh_bao("Không đọc được danh sách YCCĐ của Kho chung (%s) – bỏ qua gắn mã YCCĐ." % str(e)[:80])
    except Exception as e:
        ds_model, yccd = [X.MODEL_MAC_DINH] + X.MODEL_DU_PHONG_MAC_DINH, ""
        p.them_canh_bao("Không mở được Kho chung (%s) – dùng model mặc định." % str(e)[:80])
    danh_muc = goi.get("danhMuc") or DM.DANH_MUC_MAC_DINH
    cau_truc = goi.get("cauTruc") or DM.CAU_TRUC_MAC_DINH
    muc_tieu = goi.get("mucTieu") or DM.MUC_TIEU_MAC_DINH
    thoi_gian = int(goi.get("thoiGianPhut") or DM.THOI_GIAN_PHUT_MAC_DINH)
    tuy = {"giai": True, "groq": True, "phanLoaiHaiLuot": True,
           "nhanThucV2": True, "phanXuMuc": True, "soKhopDapAn": True, "theoChuong": True, "nguonDapAnChot": "tu_dong"}   # [25/11/2026]
    tuy.update(goi.get("tuyChon") or {})
    tieu_chi = goi.get("tieuChiMuc") or (DM.TIEU_CHI_MUC if tuy["nhanThucV2"] else DM.TIEU_CHI_MUC_CU)
    nhat_ky = p.ghi_nhat_ky
    canh_bao_tach, model = [], {}

    def luu(buoc):                       # điểm nhớ: hết hạn mức giữa chừng thì lượt sau làm tiếp từ đây
        tien_do["buoc_xong"] = buoc
        p.extra["tienDo"] = tien_do
        p.ghi("DANG_LAM", ep=True)

    try:
        # 1–2. Document Reader + Question Parser
        if "cau" not in tien_do:
            p.tien_do("Document Reader", 5, "đọc tệp từ Drive")
            phan, cb = E.doc_tai_lieu(drive, goi["tep"], nhat_ky)
            for w in cb: p.them_canh_bao(w)
            if not phan:
                p.loi("Không đọc được tệp nào (sai định dạng, quá lớn, hoặc chưa chia sẻ cho tài khoản dịch vụ %s)." % sa); sys.exit(1)
            p.tien_do("Question Parser", 15, "tách câu hỏi")
            thong_tin, cau, m, cb = E.tach_cau(phan, cau_truc, ds_model, nhat_ky)
            if not cau:
                p.loi("Không tách được câu hỏi nào từ tệp."); sys.exit(1)
            tien_do.update({"thong_tin": thong_tin, "cau": cau, "canh_bao_tach": cb, "model_tach": m})
            luu("tach")
        thong_tin, cau, canh_bao_tach, model["tach"] = tien_do["thong_tin"], tien_do["cau"], tien_do.get("canh_bao_tach", []), tien_do.get("model_tach", "")
        for w in canh_bao_tach: p.them_canh_bao(w)

        # 3. Physics Analyzer + Cognitive Classifier
        p.tien_do("Physics Analyzer", 40, "%d câu" % len(cau))
        pt, model["phan_tich"] = E.phan_tich_kien_thuc(cau, danh_muc, yccd, ds_model, nhat_ky, tien_do.get("pt"), tieu_chi)
        tien_do["pt"] = pt; luu("phan_tich")
        pl2 = tien_do.get("pl2") or {}
        if tuy["phanLoaiHaiLuot"] and not pl2:
            p.tien_do("Cognitive Classifier", 58, "lượt 2 độc lập")
            ds_khac = list(reversed(ds_model)) if len(ds_model) > 1 else ds_model
            pl2 = E.phan_loai_nhan_thuc(cau, ds_khac, nhat_ky, tieu_chi)
            tien_do["pl2"] = pl2; luu("phan_loai")

        # 3b. Trọng tài mức nhận thức (chỉ câu các phiếu không đồng thuận hoặc vi phạm luật văn bản)   [25/11/2026]
        if tuy["nhanThucV2"] and tuy["phanXuMuc"] and "px" not in tien_do:
            cho_px = [c for c in cau if NT.can_phan_xu(c, pt.get(c["ma"]), pl2.get(c["ma"]))]
            if cho_px:
                p.tien_do("Cognitive Arbiter", 62, "%d/%d câu cần trọng tài" % (min(len(cho_px), DM.MAX_PHAN_XU), len(cau)))
                px, model["phan_xu"] = E.phan_xu_nhan_thuc(cho_px, pt, pl2, ds_model, tieu_chi, nhat_ky)
                if len(cho_px) > DM.MAX_PHAN_XU:
                    p.them_canh_bao("Có %d câu lệch mức nhận thức, trọng tài chỉ xử lí %d câu đầu (giữ hạn mức); các câu còn lại chốt theo đa số / trung vị." % (len(cho_px), DM.MAX_PHAN_XU))
            else:
                px = {}
            tien_do["px"], tien_do["model_px"] = px, model.get("phan_xu", ""); luu("phan_xu")
        elif tien_do.get("model_px"):
            model["phan_xu"] = tien_do["model_px"]

        # 4. Physics Solver
        giai = tien_do.get("giai") or {}
        if tuy["giai"] and not giai:
            p.tien_do("Physics Solver", 65, "giải độc lập bằng code")
            try:
                giai, mg = E.giai_may(cau, ds_model, model["phan_tich"], tuy["groq"], nhat_ky)
            except X.HetHanMuc:
                raise
            except Exception as e:
                # [26/11/2026] quá tải tạm thời: lần đầu để khối ngoài xếp lịch thử lại; hết số lần thử thì bỏ qua Physics Solver, không để mất cả việc
                if not (la_loi_tam(e) and tien_do.get("loi_tam", 0) >= LAN_THU_LAI_TOI_DA):
                    raise
                giai, mg = {}, {}
                p.them_canh_bao("Physics Solver bị bỏ qua vì Gemini quá tải liên tục (%s) – kết quả không có đáp án máy giải; "
                                "đáp án trong đề (nếu có) vẫn được đối chiếu." % str(e)[:100])
                nhat_ky("Physics Solver", "bỏ qua sau %d lần thử lại" % LAN_THU_LAI_TOI_DA)
            model.update(mg)
            tien_do["giai"], tien_do["model_giai"] = giai, mg; luu("giai")
        elif giai:
            model.update(tien_do.get("model_giai") or {})
    except X.HetHanMuc as e:
        p.hoan("Hết hạn mức Gemini: " + str(e)[:200], 60, tien_do_luu=tien_do)
        print("⏸️ Hết hạn mức – Apps Script sẽ gửi lại sau.", flush=True)
        return
    except SystemExit:
        raise
    except Exception as e:
        if la_loi_tam(e) and tien_do.get("loi_tam", 0) < LAN_THU_LAI_TOI_DA:             # [26/11/2026] quá tải tạm thời → HOAN ngắn, làm tiếp từ tienDo
            tien_do["loi_tam"] = tien_do.get("loi_tam", 0) + 1
            p.hoan("Gemini quá tải tạm thời (%s) – thử lại lần %d/%d sau %d phút" % (str(e)[:120], tien_do["loi_tam"], LAN_THU_LAI_TOI_DA, PHUT_CHO_LOI_TAM),
                   PHUT_CHO_LOI_TAM, tien_do_luu=tien_do)
            print("⏸️ Gemini quá tải tạm thời – hoãn %d phút, Apps Script sẽ gửi lại." % PHUT_CHO_LOI_TAM, flush=True)
            return
        p.loi("%s: %s" % (type(e).__name__, str(e)[:400])); raise
    finally:
        if Q:
            try: Q.ghi_sheet(kho)
            except Exception: pass

    # 5–6. Exam Evaluator (thuần code) + đóng gói
    p.tien_do("Exam Evaluator", 92, "ma trận, thống kê, câu cần duyệt")
    tt = dict(thong_tin)
    for k_goi, k_kq in (("tenDe", "ten_de"), ("kyThi", "ky_thi"), ("nam", "nam"), ("loaiDe", "loai_de")):
        if (goi.get("thongTin") or {}).get(k_goi): tt[k_kq] = goi["thongTin"][k_goi]
    px_chot = tien_do.get("px") or {}
    chot = {c["ma"]: NT.chot_cau(c, pt.get(c["ma"]), pl2.get(c["ma"]), px_chot.get(c["ma"])) for c in cau} if tuy["nhanThucV2"] else None   # [25/11/2026]
    la_bo, ly_do_bo = False, ""
    if tuy["soKhopDapAn"]:                                                                                                        # [25/11/2026]
        try:
            la_bo, ly_do_bo = SK.la_de_bo(thong_tin, goi.get("thongTin"), tuy["nguonDapAnChot"])
            giai = SK.doi_chieu(cau, giai, goi.get("dapAnSoan") or {}, la_bo)
            if la_bo:
                p.them_canh_bao("Đề được coi là đề của Bộ (%s): đáp án chốt = đáp án Bộ phát hành trong tệp; máy / AI chỉ để so sánh. "
                                "Nếu nhận diện sai, đặt tuyChon.nguonDapAnChot = \"khong\"." % ly_do_bo)
                if not any(c.get("dap_an_de") for c in cau):
                    p.them_canh_bao("Đề của Bộ nhưng tệp không có đáp án chính thức – hãy đính kèm file đáp án để đối chiếu; tạm dùng đáp án máy.")
        except Exception as e:                                                      # phần phụ không được làm hỏng việc chính
            p.them_canh_bao("Không đối chiếu được đáp án chính thức (%s: %s) – bỏ qua." % (type(e).__name__, str(e)[:120]))
    ds = DG.hop_nhat(cau, pt, pl2, giai, danh_muc, chot)
    dg = DG.danh_gia(ds, cau_truc, muc_tieu, thoi_gian, danh_muc, canh_bao_tach, la_bo, ly_do_bo, tuy["theoChuong"])
    ket_qua = {"phienBan": 1, "thongTin": tt, "cau": ds, "maTran": dg["maTran"], "thongKe": dg["thongKe"], "nhanXet": dg["nhanXet"],
               "canDuyet": dg["canDuyet"], "canhBao": p.canh_bao, "model": model, "mucTieu": muc_tieu,
               "nguonDapAnChot": SK.NGUON_BO if la_bo else "THEO ĐÁP ÁN TRONG ĐỀ / MÁY"}
    if tuy["theoChuong"]:
        ket_qua["theoChuong"], ket_qua["baoCaoChuong"] = dg["theoChuong"], dg["baoCaoChuong"]
        print(dg["baoCaoChuong"], flush=True)
    dc = dg["thongKe"]["doi_chieu_dap_an"]
    tom_tat = {"tong_cau": dg["thongKe"]["so_cau"], "can_duyet": dg["thongKe"]["so_cau_can_duyet"], "phan_hoa": dg["thongKe"]["phan_hoa"],
               "diem_du_kien": dg["thongKe"]["diem_du_kien"], "khop": dg["thongKe"]["dap_an"]["KHỚP"],
               "khop_dap_an_chinh_thuc": dc["so_cau"]["KHỚP"], "khong_khop_dap_an_chinh_thuc": dc["so_cau"]["KHÔNG KHỚP"], "de_bo": la_bo,
               "muc_tin_cay_thap": dg["thongKe"]["nhat_quan_nhan_thuc"]["tin_cay"]["thấp"],
               "lenh_hoi": dg["thongKe"]["muc3"]["so_lenh_hoi"], "biet_hieu_vandung": [dg["thongKe"]["muc3"]["muc"][m]["so_lenh_hoi"] for m in DM.MUC3]}
    p.extra.pop("tienDo", None)                                      # xong rồi: bỏ điểm nhớ cho nhẹ
    p.phan_tram, p.buoc = 100, "xong"
    p.ghi("XONG", ep=True, ketQua=ket_qua, tomTat=tom_tat, model=model.get("phan_tich", ""))
    print("📦 " + json.dumps(tom_tat, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
