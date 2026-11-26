"""
pt_danh_gia.py – EXAM EVALUATOR (khối thứ sáu của Python Analysis Engine). THUẦN CODE, không gọi AI, chạy lại được vô hạn.

Ghép kết quả các khối trước thành: bảng câu hợp nhất, ma trận (chương × mức, lớp × mức, phần × mức), thống kê điểm / thời gian / độ phân hoá,
nhận xét theo luật và DANH SÁCH CÂU CẦN GIÁO VIÊN DUYỆT kèm lí do.
Quy ước điểm: Phần I, III theo diem_cau; Phần II tính DANH NGHĨA theo từng ý (mỗi ý = 1/4 điểm câu) để chia mức nhận thức theo ý;
cách chấm thật của Phần II (đúng 1/2/3/4 ý → 0,1/0,25/0,5/1) chỉ ảnh hưởng điểm dự kiến, không ảnh hưởng ma trận.

[25/11/2026] Bổ sung: (1) mức nhận thức lấy từ KẾT QUẢ CHỐT của pt_nhan_thuc (bỏ phiếu lượt 1 / lượt 2 / sáu tiêu chí / trọng tài);
(2) đối chiếu đáp án máy / AI / người soạn với đáp án chính thức (pt_so_khop) – đề Bộ thì chốt đáp án Bộ;
(3) mục "theoChuong": số câu của từng chương kèm nội dung, chuyên đề, mức, phần.
"""
from collections import defaultdict
import pt_danh_muc as DM
import pt_nhan_thuc as NT
import pt_so_khop as SK

MUC = DM.MUC


def _ty(x, tong):
    return round(x / tong, 4) if tong else 0.0


def _don_vi_cham(c, cau_truc):
    """[(mức, điểm, mã chương)] cho một câu."""
    ct = cau_truc.get(str(c["phan"]), {})
    muc_cau = c.get("muc_do") or "TH"
    if c["dang"] == "DS":
        ys = {str(y.get("y", "")).strip().lower()[:1]: y.get("muc_do") for y in (c.get("y_ds") or [])}
        diem_y = ct.get("diem_y") or [0.25] * 4
        return [(ys.get(k) or muc_cau, diem_y[i] if i < len(diem_y) else 0.25, c.get("ma_chuong")) for i, k in enumerate("abcd")]
    try:
        d = float(ct.get("diem_cau")) if ct.get("diem_cau") is not None else float(str(c.get("diem") or "0").replace(",", ".") or 0)
    except ValueError:
        d = 0.0
    return [(muc_cau, d or 0.25, c.get("ma_chuong"))]


def hop_nhat(ds_cau, pt, pl2, giai, danh_muc=None, chot=None):
    """
    Bảng câu hợp nhất. chot = {ma: kết quả pt_nhan_thuc.chot_cau} (None → hành xử như bản cũ: mức = lượt 1).
    danh_muc: nếu có, mã chương lạ được gộp về KHAC (giữ mã gốc ở ma_chuong_goc) để ma trận và mục theo chương khớp nhau.
    """
    hop_le_ch = {d["ma"] for d in danh_muc} if danh_muc else None
    ra = []
    for c in ds_cau:
        g, p2, s = pt.get(c["ma"], {}), pl2.get(c["ma"], {}), giai.get(c["ma"], {})
        r = {k: c.get(k) for k in ("stt", "ma", "phan", "so_cau", "dang", "noi_dung", "phuong_an", "co_hinh", "mo_ta_hinh", "diem")}
        r.update({k: g.get(k) for k in ("ma_chuong", "chuyen_de", "kien_thuc", "nang_luc", "dang_bai", "muc_do", "ly_do_muc_do", "y_ds", "so_buoc",
                                         "thoi_gian_giay", "ti_le_dung_du_kien", "bay_thuong_gap", "ma_yccd", "ngoai_chuong_trinh", "tu_tin",
                                         "dang_cau_hoi", "tieu_chi", "ma_quy_tac")})
        r["nang_luc"] = NT.chuan_nang_luc(r.get("nang_luc"))
        if hop_le_ch is not None and r.get("ma_chuong") not in hop_le_ch:
            r["ma_chuong_goc"], r["ma_chuong"] = r.get("ma_chuong"), "KHAC"
        r["muc_do_luot2"] = p2.get("muc_do")
        r["y_ds_luot2"] = p2.get("y_ds")
        k = (chot or {}).get(c["ma"])
        r["muc_do_luot1"] = g.get("muc_do")
        if k:                                          # [25/11/2026] mức đã CHỐT thay cho mức lượt 1
            ph = k.get("phieu") or {}
            r.update({"muc_do": k["muc_do"], "muc_tin_cay": k["tin_cay"], "muc_cach_chot": k["cach"], "muc_phieu": ph,
                      "muc_do_phan_xu": ph.get("phan_xu"), "muc_theo_tieu_chi": k.get("muc_theo_tieu_chi")})
            if k.get("y_ds"):
                r["y_ds"] = k["y_ds"]
        r.update({k2: s.get(k2, "") for k2 in ("da_de", "da_may", "da_groq", "ket_luan", "da_chot", "do_tin_cay", "ghi_chu",
                                              "nguon_chot", "ket_luan_so_khop", "chi_tiet_lech", "da_soan")})
        r["so_khop"] = s.get("so_khop") or {}
        r["la_de_bo"] = bool(s.get("la_de_bo"))
        ra.append(r)
    return ra


def can_duyet(cau, canh_bao_tach):
    """Danh sách [{ma, ly_do[]}] – mọi lí do đều do LUẬT sinh ra, giáo viên thấy ngay vì sao câu bị gắn cờ."""
    ds = []
    for c in cau:
        ld = []
        if c.get("muc_tin_cay"):                       # [25/11/2026] đã chốt nhiều phiếu: chỉ gắn cờ khi KHÔNG đủ tin cậy hoặc mâu thuẫn luật
            ph = c.get("muc_phieu") or {}
            if c["muc_tin_cay"] == "thấp":
                ld.append("Mức nhận thức chưa thống nhất (%s) – tạm xếp %s" % (
                    ", ".join("%s %s" % (t, ph[k]) for k, t in (("luot1", "lượt 1"), ("luot2", "lượt 2"), ("tieu_chi", "sáu tiêu chí"), ("phan_xu", "trọng tài")) if ph.get(k)), c["muc_do"]))
            ld += NT.kiem_nhat_quan(c)
        else:
            if c.get("muc_do_luot2") and c.get("muc_do") and c["muc_do"] != c["muc_do_luot2"]:
                ld.append("Hai lượt phân loại mức độ lệch nhau (%s ↔ %s)" % (c["muc_do"], c["muc_do_luot2"]))
            b, m = c.get("so_buoc") or 0, c.get("muc_do")
            if m in ("VD", "VDC") and b and b <= 1:
                ld.append("Xếp %s nhưng chỉ %d bước giải" % (m, b))
            if m in ("NB",) and b >= 3:
                ld.append("Xếp NB nhưng cần %d bước giải" % b)
        if c.get("tu_tin") == "thấp":
            ld.append("Mô hình tự đánh giá độ chắc chắn phân loại thấp")
        kl = c.get("ket_luan")
        if c.get("nguon_chot") == SK.NGUON_BO and c.get("ket_luan_so_khop") == "KHÔNG KHỚP":
            ld.append("Đề của Bộ: chốt đáp án Bộ; máy/AI không khớp (%s) – kiểm tra tách câu, đọc hình, hoặc đáp án chép từ tệp" % c.get("chi_tiet_lech", ""))
        elif kl in ("LỆCH_NÊN_SỬA", "LỆCH_CẦN_XEM", "NHIỀU_ĐÁP_ÁN"):
            ld.append("Đáp án: " + kl.replace("_", " ").lower() + (" – " + c["ghi_chu"] if c.get("ghi_chu") else ""))
        elif kl == "KHÔNG_GIẢI_ĐƯỢC" and not c.get("da_de"):
            ld.append("Không có đáp án trong đề và máy chưa giải được")
        elif c.get("do_tin_cay") == "thấp" and kl not in ("ĐỊNH_TÍNH",) and c.get("nguon_chot") != SK.NGUON_BO:
            ld.append("Độ tin cậy đáp án thấp")
        if c.get("co_hinh") and kl != "KHỚP" and c.get("ket_luan_so_khop") != "KHỚP":
            ld.append("Câu có hình, đáp án chưa được đối chiếu chắc chắn")
        if c.get("ngoai_chuong_trinh"):
            ld.append("Có thể ngoài nội dung cốt lõi GDPT 2018")
        if c.get("dang") == "TN" and len(c.get("phuong_an") or []) != 4:
            ld.append("Số phương án khác 4 (có thể tách câu sai)")
        if ld:
            ds.append({"ma": c["ma"], "ly_do": ld})
    for w in canh_bao_tach:
        if w.startswith("Trùng mã") or w.startswith("Phần "):
            ds.append({"ma": "(cả đề)", "ly_do": [w]})
    return ds


def danh_gia(cau, cau_truc, muc_tieu, thoi_gian_phut, danh_muc, canh_bao_tach=(), la_bo=False, ly_do_bo="", co_theo_chuong=True):
    ten_chuong = {d["ma"]: d["ten"] for d in danh_muc}
    lop_chuong = {d["ma"]: d["lop"] for d in danh_muc}
    mt_chuong = defaultdict(lambda: {m: {"diem": 0.0, "don_vi": 0} for m in MUC})
    mt_lop = defaultdict(lambda: {m: 0.0 for m in MUC})
    mt_phan = defaultdict(lambda: {m: 0.0 for m in MUC})
    muc_tong = {m: {"diem": 0.0, "don_vi": 0} for m in MUC}
    nl, db = defaultdict(float), defaultdict(float)
    tong_diem, diem_ky_vong, tg = 0.0, 0.0, 0
    for c in cau:
        ct = cau_truc.get(str(c["phan"]), {})
        don_vi = _don_vi_cham(c, cau_truc)
        d_cau = sum(d for _, d, _ in don_vi)
        tong_diem += d_cau
        p = c.get("ti_le_dung_du_kien")
        p = min(1.0, max(0.0, float(p))) if p is not None else 0.5
        diem_ky_vong += d_cau * p
        tg += int(c.get("thoi_gian_giay") or 0)
        for m, d, ch in don_vi:
            m = m if m in MUC else "TH"
            mt_chuong[ch or "KHAC"][m]["diem"] += d; mt_chuong[ch or "KHAC"][m]["don_vi"] += 1
            mt_lop[lop_chuong.get(ch, 0)][m] += d
            mt_phan[DM.LA_MA.get(c["phan"], str(c["phan"]))][m] += d
            muc_tong[m]["diem"] += d; muc_tong[m]["don_vi"] += 1
        nl[c.get("nang_luc") or "Chưa rõ"] += d_cau
        db[c.get("dang_bai") or "Chưa rõ"] += d_cau
    ma_tran = {
        "chuong": [{"ma": ch, "ten": ten_chuong.get(ch, ch), "lop": lop_chuong.get(ch, 0),
                    "muc": {m: round(v[m]["diem"], 3) for m in MUC}, "don_vi": {m: v[m]["don_vi"] for m in MUC},
                    "tong_diem": round(sum(v[m]["diem"] for m in MUC), 3)}
                   for ch, v in sorted(mt_chuong.items(), key=lambda kv: (lop_chuong.get(kv[0], 99), kv[0]))],
        "lop": [{"lop": l, "muc": {m: round(v[m], 3) for m in MUC}, "tong_diem": round(sum(v.values()), 3)} for l, v in sorted(mt_lop.items())],
        "phan": [{"phan": k, "muc": {m: round(v[m], 3) for m in MUC}, "tong_diem": round(sum(v.values()), 3)} for k, v in sorted(mt_phan.items())]}
    ty_muc = {m: _ty(muc_tong[m]["diem"], tong_diem) for m in MUC}
    thong_ke = {
        "so_cau": len(cau), "so_y_cham": sum(v["don_vi"] for v in muc_tong.values()), "tong_diem": round(tong_diem, 3),
        "muc": {m: {"diem": round(muc_tong[m]["diem"], 3), "ti_le": ty_muc[m], "so_don_vi": muc_tong[m]["don_vi"], "muc_tieu": muc_tieu.get(m)} for m in MUC},
        "phan_hoa": round(ty_muc["VD"] + ty_muc["VDC"], 4),
        "diem_du_kien": round(diem_ky_vong * (10 / tong_diem) if tong_diem else 0, 2),
        "thoi_gian_uoc_phut": round(tg / 60, 1), "thoi_gian_thi_phut": thoi_gian_phut,
        "ap_luc_thoi_gian": round((tg / 60) / thoi_gian_phut, 2) if thoi_gian_phut else None,
        "nang_luc": {k: _ty(v, tong_diem) for k, v in sorted(nl.items(), key=lambda kv: -kv[1])},
        "dang_bai": {k: _ty(v, tong_diem) for k, v in sorted(db.items(), key=lambda kv: -kv[1])},
        "so_cau_co_hinh": sum(1 for c in cau if c.get("co_hinh")),
        "so_cau_ngoai_ct": sum(1 for c in cau if c.get("ngoai_chuong_trinh")),
        "dap_an": {k: sum(1 for c in cau if c.get("ket_luan") == k) for k in
                   ("KHỚP", "CHỈ_CÓ_MÁY", "LỆCH_NÊN_SỬA", "LỆCH_CẦN_XEM", "NHIỀU_ĐÁP_ÁN", "KHÔNG_GIẢI_ĐƯỢC", "ĐỊNH_TÍNH")}}
    thong_ke["nhat_quan_nhan_thuc"] = NT.thong_ke_nhat_quan(cau)                       # [25/11/2026]
    thong_ke["muc3"], ma_tran["nang_luc"] = thong_ke_theo_bo(cau, cau_truc)
    thong_ke["doi_chieu_dap_an"] = SK.thong_ke_doi_chieu(cau, la_bo, ly_do_bo)
    duyet = can_duyet(cau, canh_bao_tach)
    thong_ke["so_cau_can_duyet"] = len({d["ma"] for d in duyet if d["ma"] != "(cả đề)"})
    kq = {"maTran": ma_tran, "thongKe": thong_ke, "nhanXet": nhan_xet(thong_ke, ma_tran, muc_tieu), "canDuyet": duyet}
    if co_theo_chuong:
        kq["theoChuong"] = chia_theo_chuong(cau, cau_truc, danh_muc)
        kq["baoCaoChuong"] = bao_cao_chuong_md(kq["theoChuong"])
    return kq


# ====================================================================================== [25/11/2026] THEO KHUNG CỦA BỘ: Biết / Hiểu / Vận dụng, ĐẾM THEO LỆNH HỎI
def _lenh_hoi(c):
    """[(cấp độ Bộ, thành phần năng lực, phần)] – mỗi câu Phần I/III (và IV) một lệnh hỏi, mỗi ý a–d của Phần II một lệnh hỏi."""
    phan = DM.LA_MA.get(c["phan"], str(c["phan"]))
    nl_cau = NT.chuan_nang_luc(c.get("nang_luc"))
    if c["dang"] == "DS":
        ys = {str(y.get("y", "")).strip().lower()[:1]: y for y in (c.get("y_ds") or [])}
        return [(NT.muc3((ys.get(k) or {}).get("muc_do") or c.get("muc_do")), NT.chuan_nang_luc((ys.get(k) or {}).get("nang_luc")) if (ys.get(k) or {}).get("nang_luc") else nl_cau, phan)
                for k in "abcd"]
    return [(NT.muc3(c.get("muc_do")), nl_cau, phan)]


def thong_ke_theo_bo(cau, cau_truc):
    """
    (thongKe.muc3, maTran.nang_luc). Số liệu đối chiếu với bảng đề minh hoạ của Bộ (40 lệnh hỏi: Biết 16 · Hiểu 12 · Vận dụng 12) CHỈ ĐỂ THAM KHẢO,
    không phải tỉ lệ bắt buộc. Bốn mức NB/TH/VD/VDC vẫn ở maTran / thongKe.muc; ở đây VDC được gộp vào Vận dụng.
    """
    lh = [x for c in cau for x in _lenh_hoi(c)]
    tong = len(lh)
    muc = {m: sum(1 for a, _, _ in lh if a == m) for m in DM.MUC3}
    ref_tong = DM.TONG_LENH_HOI_MINH_HOA
    thong_ke = {
        "so_lenh_hoi": tong, "so_lenh_hoi_minh_hoa": ref_tong,
        "muc": {m: {"so_lenh_hoi": muc[m], "ti_le": _ty(muc[m], tong), "minh_hoa_so_lenh_hoi": DM.SO_LENH_HOI_MINH_HOA[m],
                    "minh_hoa_ti_le": _ty(DM.SO_LENH_HOI_MINH_HOA[m], ref_tong)} for m in DM.MUC3},
        "ghi_chu": "Đối chiếu với bảng năng lực – cấp độ tư duy của đề minh hoạ (QĐ 764/QĐ-BGDĐT); đây là tham chiếu, không phải tỉ lệ bắt buộc cho mọi đề."}
    ten_nl = list(DM.NANG_LUC) + ["Chưa rõ"]
    ct = {nl: {p: {m: 0 for m in DM.MUC3} for p in ("I", "II", "III")} for nl in ten_nl}
    for m, nl, p in lh:
        ct.setdefault(nl, {}).setdefault(p, {k: 0 for k in DM.MUC3})[m] += 1
    bang = []
    for nl in ten_nl:
        if nl == "Chưa rõ" and not sum(sum(v.values()) for v in ct[nl].values()):
            continue
        ref = DM.BANG_NANG_LUC_MINH_HOA.get(nl)
        bang.append({"nang_luc": nl, "phan": ct[nl], "tong": sum(sum(v.values()) for v in ct[nl].values()),
                     "minh_hoa_tong": sum(sum(v.values()) for v in ref.values()) if ref else None, "minh_hoa_phan": ref})
    tong_phan = {p: {m: sum(ct[nl].get(p, {}).get(m, 0) for nl in ct) for m in DM.MUC3} for p in ("I", "II", "III")}
    return thong_ke, {"don_vi": "lệnh hỏi", "bang": bang, "tong_theo_phan_muc": tong_phan,
                      "minh_hoa_tong_theo_phan_muc": {p: {m: sum(DM.BANG_NANG_LUC_MINH_HOA[nl][p][m] for nl in DM.BANG_NANG_LUC_MINH_HOA) for m in DM.MUC3} for p in ("I", "II", "III")}}


# ====================================================================================== [25/11/2026] PHÂN CHIA CÂU HỎI THEO CHƯƠNG
def _cat(s, n):
    s = " ".join(str(s or "").split())
    return s if not n or len(s) <= n else s[:n - 1].rstrip() + "…"


def chia_theo_chuong(cau, cau_truc, danh_muc, do_dai=None, do_dai_pa=None):
    """
    Mỗi chương một khối: số câu, số câu theo phần, số ý chấm, điểm và tỉ lệ điểm, số câu / điểm theo mức, các chuyên đề và DANH SÁCH CÂU KÈM NỘI DUNG.
    Chương không có câu nào vẫn được liệt kê (so_cau = 0) để thấy lỗ hổng phủ chương, riêng KHAC chỉ hiện khi có câu.
    Mã chương không có trong danh mục đã được gộp về KHAC ở hop_nhat; nội dung đầy đủ nằm ở ketQua.cau[].noi_dung (nối bằng ma).
    """
    do_dai = DM.DO_DAI_NOI_DUNG_CHUONG if do_dai is None else do_dai
    do_dai_pa = DM.DO_DAI_PHUONG_AN_CHUONG if do_dai_pa is None else do_dai_pa
    khoi = {d["ma"]: {"ma": d["ma"], "ten": d["ten"], "lop": d["lop"], "cau": []} for d in danh_muc}
    khoi.setdefault("KHAC", {"ma": "KHAC", "ten": "Khác / liên môn / ngoài danh mục", "lop": 0, "cau": []})
    tong_diem = 0.0
    for c in cau:
        ch = c.get("ma_chuong") if c.get("ma_chuong") in khoi else "KHAC"
        d_cau = sum(d for _, d, _ in _don_vi_cham(c, cau_truc))
        tong_diem += d_cau
        khoi[ch]["cau"].append((c, d_cau))
    ra = []
    for ma, k in khoi.items():
        if ma == "KHAC" and not k["cau"]:
            continue
        ds = k["cau"]
        muc_cau = {m: sum(1 for c, _ in ds if (c.get("muc_do") if c.get("muc_do") in MUC else "TH") == m) for m in MUC}
        muc_diem = {m: 0.0 for m in MUC}
        y_cham = 0
        for c, _ in ds:
            for m, d, _ch in _don_vi_cham(c, cau_truc):
                muc_diem[m if m in MUC else "TH"] += d
                y_cham += 1
        phan = {}
        for c, _ in ds:
            kp = DM.LA_MA.get(c["phan"], str(c["phan"]))
            phan[kp] = phan.get(kp, 0) + 1
        cd = {}
        for c, _ in ds:
            cd.setdefault(c.get("chuyen_de") or "(chưa rõ chuyên đề)", []).append(c["ma"])
        d_ch = sum(d for _, d in ds)
        ra.append({
            "ma": ma, "ten": k["ten"], "lop": k["lop"], "so_cau": len(ds), "so_cau_phan": dict(sorted(phan.items())), "so_y_cham": y_cham,
            "tong_diem": round(d_ch, 3), "ti_le_diem": _ty(d_ch, tong_diem),
            "muc_so_cau": muc_cau, "muc_diem": {m: round(v, 3) for m, v in muc_diem.items()},
            "chuyen_de": [{"ten": t, "so_cau": len(v), "ma_cau": v} for t, v in sorted(cd.items(), key=lambda kv: (-len(kv[1]), kv[0]))],
            "cau": [{"ma": c["ma"], "phan": DM.LA_MA.get(c["phan"], str(c["phan"])), "dang": c["dang"], "muc_do": c.get("muc_do"),
                     "chuyen_de": c.get("chuyen_de") or "", "diem": round(d, 3), "co_hinh": bool(c.get("co_hinh")),
                     "noi_dung": _cat(c.get("noi_dung"), do_dai), "phuong_an": [_cat(p, do_dai_pa) for p in (c.get("phuong_an") or [])],
                     "da_chot": c.get("da_chot", ""), "ket_luan_so_khop": c.get("ket_luan_so_khop", "")} for c, d in ds]})
    return ra


def bao_cao_chuong_md(theo_chuong):
    """Văn bản Markdown của mục 'theo chương' – dán thẳng vào Docs / ô Sheet / nhật ký."""
    dong = ["## Phân chia câu hỏi theo chương", ""]
    tong = sum(k["so_cau"] for k in theo_chuong)
    dong.append("Tổng %d câu. " % tong + " · ".join("%s: %d" % (("%s (lớp %s)" % (k["ma"], k["lop"]) if k["lop"] else k["ma"]), k["so_cau"]) for k in theo_chuong if k["so_cau"]))
    for k in theo_chuong:
        dong += ["", "### %s – %s%s: %d câu · %.2f điểm (%.0f%%)" % (k["ma"], k["ten"], " (lớp %s)" % k["lop"] if k["lop"] else "", k["so_cau"], k["tong_diem"], k["ti_le_diem"] * 100)]
        if not k["so_cau"]:
            dong.append("_Không có câu nào._")
            continue
        dong.append("Mức: " + " · ".join("%s %d" % (m, k["muc_so_cau"][m]) for m in MUC) + "   |   Phần: " + ", ".join("%s %d" % kv for kv in k["so_cau_phan"].items()))
        dong += ["", "| Mã | Dạng | Mức | Chuyên đề | Nội dung |", "|---|---|---|---|---|"]
        for c in k["cau"]:
            nd = c["noi_dung"].replace("|", "/") + (" [có hình]" if c["co_hinh"] else "")
            dong.append("| %s | %s | %s | %s | %s |" % (c["ma"], c["dang"], c["muc_do"] or "?", c["chuyen_de"].replace("|", "/"), nd))
    return "\n".join(dong)


def nhan_xet(tk, mt, muc_tieu):
    nx = []
    if tk["tong_diem"] and abs(tk["tong_diem"] - 10) > 0.05:
        nx.append("Tổng điểm tính được là %.2f (khác 10) – kiểm tra tách câu / cấu trúc đề." % tk["tong_diem"])
    for m in MUC:
        t, v = muc_tieu.get(m), tk["muc"][m]["ti_le"]
        if t is not None and abs(v - t) > DM.DUNG_SAI_MUC_TIEU:
            nx.append("Mức %s chiếm %.0f%% điểm, %s mục tiêu %.0f%% (lệch %.0f điểm %%)." % (
                DM.TEN_MUC[m], v * 100, "cao hơn" if v > t else "thấp hơn", t * 100, abs(v - t) * 100))
    if tk["phan_hoa"] >= 0.35:
        nx.append("Phần vận dụng + vận dụng cao chiếm %.0f%% điểm: đề thiên về phân hoá." % (tk["phan_hoa"] * 100))
    elif tk["phan_hoa"] <= 0.15:
        nx.append("Phần vận dụng + vận dụng cao chỉ %.0f%% điểm: đề ít phân hoá nhóm học sinh khá giỏi." % (tk["phan_hoa"] * 100))
    if tk["ap_luc_thoi_gian"] and tk["ap_luc_thoi_gian"] > 1.0:
        nx.append("Thời gian ước tính cho học sinh khá (%.0f phút) vượt thời lượng thi (%s phút)." % (tk["thoi_gian_uoc_phut"], tk["thoi_gian_thi_phut"]))
    elif tk["ap_luc_thoi_gian"] and tk["ap_luc_thoi_gian"] < 0.6:
        nx.append("Thời gian ước tính chỉ %.0f%% thời lượng thi: đề khá nhẹ về khối lượng." % (tk["ap_luc_thoi_gian"] * 100))
    ch = [c for c in mt["chuong"] if c["tong_diem"]]
    if ch:
        top = max(ch, key=lambda c: c["tong_diem"])
        nx.append("Chương nhiều điểm nhất: %s (%.2f điểm)." % (top["ten"], top["tong_diem"]))
    for lop in mt["lop"]:
        if lop["lop"] in (10, 11, 12) and lop["tong_diem"] == 0:
            nx.append("Đề không có điểm nào thuộc lớp %d." % lop["lop"])
    if tk["so_cau_ngoai_ct"]:
        nx.append("%d câu có thể ngoài nội dung cốt lõi GDPT 2018 – xem tab Cần duyệt." % tk["so_cau_ngoai_ct"])
    m3 = tk.get("muc3") or {}
    if m3.get("so_lenh_hoi"):
        nx.append("Theo cấp độ của Bộ (đếm %d lệnh hỏi): Biết %d (%.0f%%), Hiểu %d (%.0f%%), Vận dụng %d (%.0f%%); đề minh hoạ là %d/%d/%d trên %d lệnh hỏi – chỉ để tham khảo, không phải tỉ lệ bắt buộc." % (
            m3["so_lenh_hoi"], *[x for m in DM.MUC3 for x in (m3["muc"][m]["so_lenh_hoi"], m3["muc"][m]["ti_le"] * 100)],
            *[DM.SO_LENH_HOI_MINH_HOA[m] for m in DM.MUC3], m3["so_lenh_hoi_minh_hoa"]))
        if m3["so_lenh_hoi"] != m3["so_lenh_hoi_minh_hoa"]:
            nx.append("Đề có %d lệnh hỏi, khác cấu trúc 40 lệnh hỏi (18 TN + 4×4 ý Đúng/Sai + 6 trả lời ngắn) – kiểm tra tách câu nếu đây là đề theo cấu trúc mới." % m3["so_lenh_hoi"])
    nk = tk.get("nhat_quan_nhan_thuc") or {}
    if nk.get("ty_le_hai_luot_khop") is not None:
        nx.append("Phân loại mức nhận thức: hai lượt độc lập khớp %.0f%% (%d/%d câu); %d câu qua trọng tài; %d câu độ tin cậy thấp chờ giáo viên duyệt." % (
            nk["ty_le_hai_luot_khop"] * 100, nk["hai_luot_khop"], nk["so_cau_hai_luot"], nk["so_cau_phan_xu"], nk["tin_cay"]["thấp"]))
    dc = tk.get("doi_chieu_dap_an") or {}
    if dc:
        so = dc["so_cau"]
        if dc.get("la_de_bo"):
            nx.append("Đề của Bộ (%s): đáp án chốt là đáp án Bộ phát hành." % dc.get("ly_do_nhan_dien", ""))
        if so["KHỚP"] + so["KHÔNG KHỚP"]:
            nx.append("Đối chiếu đáp án với đáp án chính thức trong tệp: %d khớp, %d không khớp (%.0f%% khớp)%s." % (
                so["KHỚP"], so["KHÔNG KHỚP"], dc["ty_le_khop"] * 100,
                "; câu không khớp: " + ", ".join(x["ma"] for x in dc["cau_khong_khop"][:12]) if dc["cau_khong_khop"] else ""))
        if so["CHƯA CÓ ĐÁP ÁN CHÍNH THỨC"]:
            nx.append("%d câu chưa có đáp án chính thức trong tệp nên chưa đối chiếu được." % so["CHƯA CÓ ĐÁP ÁN CHÍNH THỨC"])
    nx.append("Điểm dự kiến %.2f/10 và thời gian ước tính là ƯỚC LƯỢNG của mô hình AI, cần hiệu chỉnh bằng dữ liệu bài làm thật." % tk["diem_du_kien"])
    return nx
