"""
pt_danh_gia.py – EXAM EVALUATOR (khối thứ sáu của Python Analysis Engine). THUẦN CODE, không gọi AI, chạy lại được vô hạn.

Ghép kết quả các khối trước thành: bảng câu hợp nhất, ma trận (chương × mức, lớp × mức, phần × mức), thống kê điểm / thời gian / độ phân hoá,
nhận xét theo luật và DANH SÁCH CÂU CẦN GIÁO VIÊN DUYỆT kèm lí do.
Quy ước điểm: Phần I, III theo diem_cau; Phần II tính DANH NGHĨA theo từng ý (mỗi ý = 1/4 điểm câu) để chia mức nhận thức theo ý;
cách chấm thật của Phần II (đúng 1/2/3/4 ý → 0,1/0,25/0,5/1) chỉ ảnh hưởng điểm dự kiến, không ảnh hưởng ma trận.
"""
from collections import defaultdict
import pt_danh_muc as DM

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


def hop_nhat(ds_cau, pt, pl2, giai):
    ra = []
    for c in ds_cau:
        g, p2, s = pt.get(c["ma"], {}), pl2.get(c["ma"], {}), giai.get(c["ma"], {})
        r = {k: c.get(k) for k in ("stt", "ma", "phan", "so_cau", "dang", "noi_dung", "phuong_an", "co_hinh", "mo_ta_hinh", "diem")}
        r.update({k: g.get(k) for k in ("ma_chuong", "chuyen_de", "kien_thuc", "nang_luc", "dang_bai", "muc_do", "ly_do_muc_do", "y_ds", "so_buoc",
                                         "thoi_gian_giay", "ti_le_dung_du_kien", "bay_thuong_gap", "ma_yccd", "ngoai_chuong_trinh", "tu_tin")})
        r["muc_do_luot2"] = p2.get("muc_do")
        r["y_ds_luot2"] = p2.get("y_ds")
        r.update({k: s.get(k, "") for k in ("da_de", "da_may", "da_groq", "ket_luan", "da_chot", "do_tin_cay", "ghi_chu")})
        ra.append(r)
    return ra


def can_duyet(cau, canh_bao_tach):
    """Danh sách [{ma, ly_do[]}] – mọi lí do đều do LUẬT sinh ra, giáo viên thấy ngay vì sao câu bị gắn cờ."""
    ds = []
    for c in cau:
        ld = []
        if c.get("muc_do_luot2") and c.get("muc_do") and c["muc_do"] != c["muc_do_luot2"]:
            ld.append("Hai lượt phân loại mức độ lệch nhau (%s ↔ %s)" % (c["muc_do"], c["muc_do_luot2"]))
        if c.get("tu_tin") == "thấp":
            ld.append("Mô hình tự đánh giá độ chắc chắn phân loại thấp")
        b, m = c.get("so_buoc") or 0, c.get("muc_do")
        if m in ("VD", "VDC") and b and b <= 1:
            ld.append("Xếp %s nhưng chỉ %d bước giải" % (m, b))
        if m in ("NB",) and b >= 3:
            ld.append("Xếp NB nhưng cần %d bước giải" % b)
        kl = c.get("ket_luan")
        if kl in ("LỆCH_NÊN_SỬA", "LỆCH_CẦN_XEM", "NHIỀU_ĐÁP_ÁN"):
            ld.append("Đáp án: " + kl.replace("_", " ").lower() + (" – " + c["ghi_chu"] if c.get("ghi_chu") else ""))
        elif kl == "KHÔNG_GIẢI_ĐƯỢC" and not c.get("da_de"):
            ld.append("Không có đáp án trong đề và máy chưa giải được")
        elif c.get("do_tin_cay") == "thấp" and kl not in ("ĐỊNH_TÍNH",):
            ld.append("Độ tin cậy đáp án thấp")
        if c.get("co_hinh") and kl != "KHỚP":
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


def danh_gia(cau, cau_truc, muc_tieu, thoi_gian_phut, danh_muc, canh_bao_tach=()):
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
    duyet = can_duyet(cau, canh_bao_tach)
    thong_ke["so_cau_can_duyet"] = len({d["ma"] for d in duyet if d["ma"] != "(cả đề)"})
    return {"maTran": ma_tran, "thongKe": thong_ke, "nhanXet": nhan_xet(thong_ke, ma_tran, muc_tieu), "canDuyet": duyet}


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
    nx.append("Điểm dự kiến %.2f/10 và thời gian ước tính là ƯỚC LƯỢNG của mô hình AI, cần hiệu chỉnh bằng dữ liệu bài làm thật." % tk["diem_du_kien"])
    return nx
