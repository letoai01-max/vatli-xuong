"""
tron_de.py – XƯỞNG TRỘN ĐỀ (loại phiếu "tron_de" của giao_thuc.py). Thay taoMotMaDe / chayViecTronDe trong Apps Script.

Giữ đúng quy tắc của taoMotMaDe:
  - Trộn thứ tự câu Phần I, II, III (Phần IV giữ nguyên).
  - Trộn phương án A–D Phần I khi đọc được đáp án A/B/C/D của câu.
  - Trộn thứ tự ý a–d Phần II (tuỳ chọn) khi đọc được đủ 4 đáp án Đ/S.
  - Bộ hoán vị của các mã đề không trùng nhau.
  - Mỗi mã đề: 1 tệp Word HS + 1 tệp Word GV (qua xuat_de_v2.xuat_de), kèm bảng đáp án mới và ánh xạ về câu gốc.

GÓI "tron_de" (goi_de_<mã>.json), ngoài các trường chung của giao_thuc.py:
  cauHinh  {grade, subject, textbook, tenDe, thoiGianPhut, dauTrang}   (giống tao_de)
  deGoc    {phan1..phan4}   đề gốc, cùng định dạng deThi của ket_qua (cauHoi, A..D, dapAn)
           (hoặc nguon: {ketQuaId: "<fileId ket_qua của lượt tạo đề>"} thì xưởng đọc deThi từ đó)
  maDe     ["101", "102", ...]    danh sách mã đề cần tạo
  tuyChon  {tronCau:{"1":true,"2":true,"3":true}, tronPhuongAn:true, tronYPhan2:false}
  dich     {"101": {docxHS:<fileId>, docxGV:<fileId>}, ...}   tệp Word rỗng Apps Script tạo sẵn cho từng mã

KẾT QUẢ: tep = dich · tomTat = {soMaDe, dapAn:{mã:{p1,p2,p3,p4}}, anhXa:{mã:{...}}} · extra.dapAnMaDe, extra.anhXaMaDe.

QUY ƯỚC HOÁN VỊ (cùng nghĩa với mảng P, hv.pa, hv.y trong Apps Script):
  thuTu[p][k] = g   : vị trí mới k (0-based) của Phần p là câu gốc g.
  pa[g][j]    = i   : với câu gốc g (Phần I), phương án mới ở vị trí j là phương án gốc i.
  y[g][j]     = i   : với câu gốc g (Phần II), ý mới ở vị trí j là ý gốc i.
"""
import copy
import json
import os
import random
import re
import shutil
import sys
import tempfile

import giao_thuc as GT

CHU = "ABCD"
PHAN_TRON_CAU = (1, 2, 3)
SO_LAN_THU_KHAC_NHAU = 300


# ---------------- đọc đáp án ----------------
def doc_dap_an_p1(s):
    m = re.search(r"[ABCD]", str(s or "").upper())
    return m.group(0) if m else ""


def doc_dap_an_p2(s):
    """'a) Đ, b) S, c) Đ, d) S' → {'a': True, 'b': False, ...}; không đủ 4 ý → {}."""
    kq = {}
    for m in re.finditer(r"([a-dA-D])\s*[\)\.:\-]?\s*(Đúng|Sai|Đ|S)\b", str(s or ""), re.I):
        kq[m.group(1).lower()] = m.group(2).lower().startswith("đ")
    return kq if len(kq) == 4 else {}


def ghi_dap_an_p2(dung_sai):
    return ", ".join("%s) %s" % (k, "Đ" if dung_sai[k] else "S") for k in "abcd")


# ---------------- bộ hoán vị không trùng ----------------
def _hoan_vi(rng, n):
    a = list(range(n))
    rng.shuffle(a)
    return a


def tao_bo_hoan_vi(de, cfg, rng, da_dung):
    """Một bộ hoán vị {thuTu:{1,2,3}, pa:{g:[...]}, y:{g:[...]}} chưa trùng bộ nào trong da_dung (cố gắng, tối đa N lần)."""
    n = {p: len(de.get("phan%d" % p) or []) for p in (1, 2, 3)}
    for _ in range(SO_LAN_THU_KHAC_NHAU):
        hv = {"thuTu": {}, "pa": {}, "y": {}}
        for p in PHAN_TRON_CAU:
            hv["thuTu"][p] = _hoan_vi(rng, n[p]) if cfg["tronCau"].get(p, True) else list(range(n[p]))
        for g in range(n[1]):
            hv["pa"][g] = _hoan_vi(rng, 4)
        for g in range(n[2]):
            hv["y"][g] = _hoan_vi(rng, 4)
        khoa = json.dumps([hv["thuTu"], hv["pa"] if cfg["tronPhuongAn"] else 0, hv["y"] if cfg["tronYPhan2"] else 0], sort_keys=True)
        if khoa not in da_dung:
            da_dung.add(khoa)
            return hv, True
    return hv, False


# ---------------- trộn một mã đề ----------------
def tron_mot_ma(de_goc, hv, cfg):
    """Trả về (de_moi, dap_an, anh_xa, ghi_chu). Không sửa de_goc."""
    ghi_chu, de_moi, dap_an, anh_xa = [], {}, {}, {}

    # Phần I
    cauI, daI, axI = [], [], []
    for k, g in enumerate(hv["thuTu"][1]):
        c = copy.deepcopy(de_goc["phan1"][g])
        dung = doc_dap_an_p1(c.get("dapAn"))
        pa = hv["pa"][g]
        if cfg["tronPhuongAn"] and dung:
            goc = {i: c.get(CHU[i], "") for i in range(4)}
            for j in range(4):
                c[CHU[j]] = goc[pa[j]]
            moi = CHU[pa.index(CHU.index(dung))]
            c["dapAn"] = moi
            axI.append({"moi": k + 1, "goc": g + 1, "phuongAn": [CHU[i] for i in pa]})
        else:
            if cfg["tronPhuongAn"]:
                ghi_chu.append("Phần I câu gốc %d: giữ nguyên phương án (không đọc được đáp án)" % (g + 1))
            moi = dung
            axI.append({"moi": k + 1, "goc": g + 1})
        cauI.append(c)
        daI.append(moi)
    de_moi["phan1"], dap_an["p1"], anh_xa["p1"] = cauI, daI, axI

    # Phần II
    cauII, daII, axII = [], [], []
    for k, g in enumerate(hv["thuTu"][2]):
        c = copy.deepcopy(de_goc["phan2"][g])
        ds = doc_dap_an_p2(c.get("dapAn"))
        y = hv["y"][g]
        if cfg["tronYPhan2"] and ds:
            goc = {i: c.get(CHU[i], "") for i in range(4)}
            for j in range(4):
                c[CHU[j]] = goc[y[j]]
            moi_ds = {"abcd"[j]: ds["abcd"[y[j]]] for j in range(4)}
            c["dapAn"] = ghi_dap_an_p2(moi_ds)
            axII.append({"moi": k + 1, "goc": g + 1, "y": ["abcd"[i] for i in y]})
        else:
            if cfg["tronYPhan2"]:
                ghi_chu.append("Phần II câu gốc %d: giữ nguyên thứ tự ý (không đọc được đáp án Đ/S)" % (g + 1))
            axII.append({"moi": k + 1, "goc": g + 1})
        cauII.append(c)
        daII.append(str(c.get("dapAn", "")))
    de_moi["phan2"], dap_an["p2"], anh_xa["p2"] = cauII, daII, axII

    # Phần III
    cauIII = [copy.deepcopy(de_goc["phan3"][g]) for g in hv["thuTu"][3]]
    de_moi["phan3"] = cauIII
    dap_an["p3"] = [str(c.get("dapAn", "")) for c in cauIII]
    anh_xa["p3"] = [{"moi": k + 1, "goc": g + 1} for k, g in enumerate(hv["thuTu"][3])]

    # Phần IV: giữ nguyên
    de_moi["phan4"] = copy.deepcopy(de_goc.get("phan4") or [])
    dap_an["p4"] = ["(giữ nguyên)"] * len(de_moi["phan4"])
    return de_moi, dap_an, anh_xa, ghi_chu


# ---------------- cấu hình / kiểm gói ----------------
def doc_cau_hinh(goi):
    tc = goi.get("tuyChon") or {}
    tc_cau = tc.get("tronCau") or {}
    return {
        "tronCau": {p: tc_cau.get(str(p), tc_cau.get(p, True)) is not False for p in PHAN_TRON_CAU},
        "tronPhuongAn": tc.get("tronPhuongAn") is not False,
        "tronYPhan2": tc.get("tronYPhan2") is True,
    }


def kiem_goi_tron(goi, de_goc):
    loi = []
    ds = goi.get("maDe")
    if not isinstance(ds, list) or not ds or len(set(map(str, ds))) != len(ds):
        loi.append("maDe phải là danh sách mã không rỗng, không trùng")
        ds = []
    dich = goi.get("dich") or {}
    for ma in ds:
        d = dich.get(str(ma)) or {}
        if not (d.get("docxHS") and d.get("docxGV")):
            loi.append("dich thiếu docxHS/docxGV cho mã đề %s" % ma)
    for p in (1, 2, 3):
        if not isinstance(de_goc.get("phan%d" % p), list):
            loi.append("đề gốc thiếu phan%d" % p)
    return loi


# ---------------- chạy ----------------
def main():
    import google.auth
    from googleapiclient.discovery import build
    import xuat_de_v2 as XD

    cred, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/drive"])
    drive = build("drive", "v3", credentials=cred, cache_discovery=False)
    goi_id, kq_id = os.environ["GOI_ID"], os.environ["KQ_ID"]
    goi = GT.doc_json_drive(drive, goi_id)
    ph = GT.Phien(drive, kq_id, goi)
    loi_goi = GT.kiem_goi(goi)
    if goi.get("loai") != "tron_de":
        loi_goi.append("tron_de.py chỉ nhận loai = tron_de")
    if loi_goi:
        ph.loi("Gói việc không hợp lệ: " + "; ".join(loi_goi))
        raise SystemExit(1)

    cu = GT.doc_json_drive(drive, kq_id)
    da_lam = set((cu.get("tienDo") or {}).get("maXong") or [])
    ph.luot = int(cu.get("luot", 0) or 0) + 1
    ph.tien_do("đọc gói", 3, "trộn đề · lượt %d" % ph.luot)
    try:
        de_goc = goi.get("deGoc")
        if not de_goc and (goi.get("nguon") or {}).get("ketQuaId"):
            de_goc = (GT.doc_json_drive(drive, goi["nguon"]["ketQuaId"]).get("deThi")) or {}
        de_goc = {k: v for k, v in (de_goc or {}).items() if k in ("phan1", "phan2", "phan3", "phan4")}
        loi = kiem_goi_tron(goi, de_goc)
        if loi:
            raise ValueError("; ".join(loi))

        cfg = doc_cau_hinh(goi)
        if any(k.lower().startswith("hinh") for p in (1, 2, 3, 4) for c in de_goc.get("phan%d" % p, []) for k in c):
            ph.them_canh_bao("Đề gốc có câu gắn hình: bản trộn này chưa chuyển hình theo câu, hãy kiểm tra Word.")
        ds = [str(m) for m in goi["maDe"]]
        rng = random.Random(goi["ma"])
        da_dung, dap_an_all, anh_xa_all, xong = set(), dict(cu.get("dapAnMaDe") or {}), dict(cu.get("anhXaMaDe") or {}), []
        tien = dict(cu.get("tienDo") or {})
        thu = tempfile.mkdtemp()
        try:
            for i, ma in enumerate(ds):
                hv, khac = tao_bo_hoan_vi(de_goc, cfg, rng, da_dung)     # luôn gọi để dãy ngẫu nhiên giống nhau khi chạy lại
                if not khac:
                    ph.them_canh_bao("Mã %s có bộ hoán vị trùng một mã khác (đề quá ít câu để trộn khác nhau)." % ma)
                if ma in da_lam:
                    continue
                ph.tien_do("trộn mã %s" % ma, 10 + 80 * i // len(ds), "%d/%d" % (i + 1, len(ds)))
                de_moi, dap_an, anh_xa, ghi_chu = tron_mot_ma(de_goc, hv, cfg)
                for g in ghi_chu:
                    ph.them_canh_bao("Mã %s: %s" % (ma, g))
                ch = dict(goi["cauHinh"])
                ch["tenDe"] = "%s - Mã đề %s" % (ch.get("tenDe", ""), ma)
                kq = XD.xuat_de(de_moi, ch, thu, hinh_san={}, ten_goc="De_%s" % ma)
                for c in kq["canhBao"]:
                    ph.them_canh_bao("Mã %s: %s" % (ma, c))
                d = goi["dich"][ma]
                GT.ghi_docx_vao_tep(drive, d["docxHS"], kq["hs"])
                GT.ghi_docx_vao_tep(drive, d["docxGV"], kq["gv"])
                dap_an_all[ma], anh_xa_all[ma] = dap_an, anh_xa
                da_lam.add(ma)
                tien["maXong"] = sorted(da_lam)
                ph.extra.update({"dapAnMaDe": dap_an_all, "anhXaMaDe": anh_xa_all, "tienDo": tien})
                ph.ghi("DANG_LAM", ep=True)
        finally:
            shutil.rmtree(thu, ignore_errors=True)

        ph.extra.update({"dapAnMaDe": dap_an_all, "anhXaMaDe": anh_xa_all})
        tom_tat = {"soMaDe": len(da_lam), "dapAn": dap_an_all, "anhXa": anh_xa_all, "soCanhBao": len(ph.canh_bao)}
        ph.xong(de_goc, tep=goi["dich"], tom_tat=tom_tat)
        print("✅ Xong trộn đề %s: %d mã" % (goi["ma"], len(da_lam)), flush=True)
    except Exception as e:
        ph.loi(str(e))
        for ma_d, d in (goi.get("dich") or {}).items():
            for k in ("docxHS", "docxGV"):
                if (d or {}).get(k) and not all(x in da_lam for x in [ma_d]):
                    GT.danh_dau_loi_tep(drive, d[k], str(e))
        raise


if __name__ == "__main__":
    main()
