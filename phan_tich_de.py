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
  tuyChon    {giai:true, groq:true, phanLoaiHaiLuot:true}
  cauTruc    {"1":{dang,so_cau,diem_cau},"2":{…,diem_y:[…]},"3":{…}}   (không có → mặc định pt_danh_muc)
  mucTieu    {NB,TH,VD,VDC}   thoiGianPhut   danhMuc [{lop,ma,ten}]   (không có → mặc định)
KẾT QUẢ: ket_qua.ketQua = {thongTin, cau[], maTran, thongKe, nhanXet[], canDuyet[], canhBao[], model{}}; tomTat cho Apps Script ghi Sheet.
Biến môi trường: GOOGLE_CREDENTIALS, GEMINI_API_KEY(_n), GROQ_API_KEY (tuỳ chọn), GOI_ID, KQ_ID.
"""
import json, os, sys

import doc_de as X
import giao_thuc as GT
import pt_danh_muc as DM
import pt_engine as E
import pt_danh_gia as DG
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
    tuy = {"giai": True, "groq": True, "phanLoaiHaiLuot": True}
    tuy.update(goi.get("tuyChon") or {})
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
        pt, model["phan_tich"] = E.phan_tich_kien_thuc(cau, danh_muc, yccd, ds_model, nhat_ky, tien_do.get("pt"))
        tien_do["pt"] = pt; luu("phan_tich")
        pl2 = tien_do.get("pl2") or {}
        if tuy["phanLoaiHaiLuot"] and not pl2:
            p.tien_do("Cognitive Classifier", 58, "lượt 2 độc lập")
            ds_khac = list(reversed(ds_model)) if len(ds_model) > 1 else ds_model
            pl2 = E.phan_loai_nhan_thuc(cau, ds_khac, nhat_ky)
            tien_do["pl2"] = pl2; luu("phan_loai")

        # 4. Physics Solver
        giai = tien_do.get("giai") or {}
        if tuy["giai"] and not giai:
            p.tien_do("Physics Solver", 65, "giải độc lập bằng code")
            giai, mg = E.giai_may(cau, ds_model, model["phan_tich"], tuy["groq"], nhat_ky)
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
        p.loi("%s: %s" % (type(e).__name__, str(e)[:400])); raise
    finally:
        if Q:
            try: Q.ghi_sheet(kho)
            except Exception: pass

    # 5–6. Exam Evaluator (thuần code) + đóng gói
    p.tien_do("Exam Evaluator", 92, "ma trận, thống kê, câu cần duyệt")
    ds = DG.hop_nhat(cau, pt, pl2, giai)
    dg = DG.danh_gia(ds, cau_truc, muc_tieu, thoi_gian, danh_muc, canh_bao_tach)
    tt = dict(thong_tin)
    for k_goi, k_kq in (("tenDe", "ten_de"), ("kyThi", "ky_thi"), ("nam", "nam"), ("loaiDe", "loai_de")):
        if (goi.get("thongTin") or {}).get(k_goi): tt[k_kq] = goi["thongTin"][k_goi]
    ket_qua = {"phienBan": 1, "thongTin": tt, "cau": ds, "maTran": dg["maTran"], "thongKe": dg["thongKe"], "nhanXet": dg["nhanXet"],
               "canDuyet": dg["canDuyet"], "canhBao": p.canh_bao, "model": model, "mucTieu": muc_tieu}
    tom_tat = {"tong_cau": dg["thongKe"]["so_cau"], "can_duyet": dg["thongKe"]["so_cau_can_duyet"], "phan_hoa": dg["thongKe"]["phan_hoa"],
               "diem_du_kien": dg["thongKe"]["diem_du_kien"], "khop": dg["thongKe"]["dap_an"]["KHỚP"]}
    p.extra.pop("tienDo", None)                                      # xong rồi: bỏ điểm nhớ cho nhẹ
    p.phan_tram, p.buoc = 100, "xong"
    p.ghi("XONG", ep=True, ketQua=ket_qua, tomTat=tom_tat, model=model.get("phan_tich", ""))
    print("📦 " + json.dumps(tom_tat, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
