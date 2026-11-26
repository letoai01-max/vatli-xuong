"""
pt_nhan_thuc.py – CHỐT MỨC ĐỘ NHẬN THỨC (THUẦN CODE, không gọi AI, chạy lại được vô hạn). [25/11/2026]

Vì sao cần: một lượt AI phân loại NB/TH/VD/VDC dễ dao động. Khối này gom nhiều "phiếu" độc lập rồi chốt, theo bảng tiêu chí nhận thức:
  luot1      mức do lượt phân tích kiến thức (pt_engine.phan_tich_kien_thuc)
  luot2      mức do lượt phân loại độc lập, model khác (pt_engine.phan_loai_nhan_thuc)
  tieu_chi   mức mà ÍT NHẤT HAI trong SÁU tiêu chí cùng đạt tới (không cộng điểm máy móc, không để một tiêu chí đơn lẻ kéo mức lên)
  phan_xu    trọng tài (pt_engine.phan_xu_nhan_thuc) chỉ chạy với câu các phiếu trên không đồng thuận hoặc vi phạm luật văn bản

Luật văn bản (dau_hieu_van_ban / kiem_nhat_quan) chỉ GHI CỜ và gửi trọng tài, KHÔNG tự đổi mức:
  động từ và hình thức chỉ là dấu hiệu tham khảo (nguyên tắc VIII của bảng tiêu chí).

Câu Đúng/Sai: chốt riêng từng ý a–d; mức của cả câu = mức cao nhất trong 4 ý; độ tin cậy của câu = độ tin cậy thấp nhất trong 4 ý.
"""
import re
import unicodedata
from collections import Counter

import pt_danh_muc as DM

MUC = DM.MUC
_TT = {m: i for i, m in enumerate(MUC)}
LUOT = ("luot1", "luot2", "tieu_chi", "phan_xu")


def khong_dau(s):
    s = unicodedata.normalize("NFD", str(s or "").lower().replace("đ", "d"))
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


def chuan_nang_luc(s):
    """Đưa tên thành phần năng lực mô hình trả về (có thể viết tắt / sai dấu) về đúng một trong ba tên của Bộ; không nhận ra → 'Chưa rõ'."""
    t = khong_dau(s)
    if "tim hieu" in t or "the gioi tu nhien" in t:
        return DM.NANG_LUC[1]
    if "van dung" in t:
        return DM.NANG_LUC[2]
    if "nhan thuc" in t:
        return DM.NANG_LUC[0]
    return "Chưa rõ"


def muc3(m):
    """NB/TH/VD/VDC → Biết/Hiểu/Vận dụng (cách gọi của Bộ). Mức lạ → Hiểu (như quy ước TH mặc định của evaluator)."""
    return DM.GOP_MUC3.get(m, DM.GOP_MUC3["TH"])


def hop_le(m):
    return m if m in _TT else None


def cao_hon(a, b):
    """Mức cao hơn trong hai mức (None bị bỏ qua)."""
    a, b = hop_le(a), hop_le(b)
    if not a or not b:
        return a or b
    return a if _TT[a] >= _TT[b] else b


# ====================================================================================== phiếu từ sáu tiêu chí
def muc_theo_tieu_chi(tc):
    """Mức cao thứ nhì trong 6 tiêu chí (= mức mà ≥ 2 tiêu chí cùng đạt). Thiếu dữ liệu (< 4 tiêu chí hợp lệ) → None."""
    if not isinstance(tc, dict):
        return None
    ds = sorted((_TT[tc[k]] for k in DM.TIEU_CHI_KHOA if tc.get(k) in _TT), reverse=True)
    if len(ds) < 4:
        return None
    return MUC[ds[1]]


def _phieu_tieu_chi(*cac_g):
    """Phiếu 'tieu_chi' của một câu: lấy MỨC THẤP NHẤT trong các lượt có điền tieu_chi (thận trọng, không tự nâng mức)."""
    ds = [muc_theo_tieu_chi((g or {}).get("tieu_chi")) for g in cac_g]
    ds = [m for m in ds if m]
    return min(ds, key=lambda m: _TT[m]) if ds else None


# ====================================================================================== luật văn bản (chỉ ghi cờ)
_TU_VDC = ("thiet ke thi nghiem", "de xuat phuong an", "de xuat cach", "phuong an toi uu", "phan bien", "danh gia phuong an", "bao ve giai phap")
_TU_NB = ("phat bieu", "dinh nghia", "don vi cua", "don vi do", "don vi nao", "ki hieu", "ky hieu", "cong thuc nao", "la gi", "ten goi", "dung cu nao", "thiet bi nao")
_SO = re.compile(r"\d+(?:[.,]\d+)?")


def dau_hieu_van_ban(c):
    """{'san': mức tối thiểu hợp lí | None, 'tran': mức tối đa hợp lí | None, 'ghi': [lí do]} – suy từ chữ trong đề."""
    nd = khong_dau(c.get("noi_dung"))
    san = tran = None
    ghi = []
    if any(t in nd for t in _TU_VDC):
        san = "VD"
        ghi.append("đề có yêu cầu thiết kế / đề xuất / tối ưu / phản biện – thường từ VD trở lên (VDC02, VDC03)")
    if c.get("dang") == "TN" and not c.get("co_hinh") and len(nd) < 220:
        nd_chu = re.sub(r"\$[^$]*\$", " ", nd)                       # bỏ công thức; còn lại có số liệu nào không?
        if not _SO.search(nd_chu) and any(t in nd for t in _TU_NB):
            tran = "TH"
            ghi.append("câu hỏi nhớ / nhận diện, không có số liệu – tối đa TH (NB01, NB02)")
    return {"san": san, "tran": tran, "ghi": ghi}


def kiem_nhat_quan(c):
    """Danh sách lí do (chuỗi) khi mức đã chốt mâu thuẫn với các dấu hiệu khác. Rỗng = ổn. c cần: muc_do, so_buoc, tieu_chi, ma_quy_tac, noi_dung, dang."""
    ld = []
    m = hop_le(c.get("muc_do"))
    if not m:
        return ld
    dh = dau_hieu_van_ban(c)
    if dh["tran"] and _TT[m] > _TT[dh["tran"]]:
        ld.append("Xếp %s nhưng %s" % (m, dh["ghi"][-1]))
    if dh["san"] and _TT[m] < _TT[dh["san"]]:
        ld.append("Xếp %s nhưng %s" % (m, dh["ghi"][0]))
    tc = c.get("tieu_chi") if isinstance(c.get("tieu_chi"), dict) else {}
    b = int(c.get("so_buoc") or 0)
    cao = any(tc.get(k) in ("VD", "VDC") for k in ("lua_chon_phuong_phap", "yeu_cau_ket_qua"))
    if m in ("VD", "VDC") and 0 < b <= 1 and not cao:
        ld.append("Xếp %s nhưng chỉ %d bước và không phải tự chọn phương pháp / giải quyết vấn đề" % (m, b))
    if m == "NB" and b >= 3:
        ld.append("Xếp NB nhưng cần %d bước giải" % b)
    mtc = muc_theo_tieu_chi(tc)
    if mtc and abs(_TT[m] - _TT[mtc]) >= 2:
        ld.append("Mức %s lệch từ 2 bậc trở lên so với sáu tiêu chí (%s)" % (m, mtc))
    qt = [str(x) for x in (c.get("ma_quy_tac") or []) if str(x) in DM.QUY_TAC]
    if qt:
        muc_qt = [DM.QUY_TAC[x][1] for x in qt]
        if m in ("VD", "VDC") and all(x in ("NB", "TH") for x in muc_qt):
            ld.append("Xếp %s nhưng quy tắc nhận diện chỉ là %s" % (m, ", ".join(qt)))
        if m in ("NB", "TH") and any(x == "VDC" for x in muc_qt):
            ld.append("Xếp %s nhưng có quy tắc %s (gợi ý VDC)" % (m, ", ".join(x for x in qt if DM.QUY_TAC[x][1] == "VDC")))
    return ld


# ====================================================================================== bỏ phiếu
def chot_muc(phieu, tu_tin_thap=False):
    """
    phieu: {luot1, luot2, tieu_chi, phan_xu} (giá trị None nếu thiếu).
    Trả {muc_do, tin_cay: cao|vừa|thấp, cach, phieu}.
      cao    mọi phiếu đồng thuận (≥ 2 phiếu)
      vừa    đa số, hoặc trọng tài đứng về một phiếu
      thấp   không có đa số / trọng tài khác mọi phiếu / các phiếu lệch ≥ 3 bậc → CHỜ GIÁO VIÊN DUYỆT
    """
    co = {k: v for k, v in phieu.items() if v in _TT}
    if not co:
        return {"muc_do": "TH", "tin_cay": "thấp", "cach": "không có phiếu nào – tạm xếp TH", "phieu": dict(phieu)}
    gia_tri = list(co.values())
    chi_so = sorted(_TT[v] for v in gia_tri)
    lech = chi_so[-1] - chi_so[0]
    dem = Counter(gia_tri).most_common()
    px = co.get("phan_xu")
    if len(set(gia_tri)) == 1 and len(gia_tri) >= 2:
        muc, tin, cach = gia_tri[0], "cao", "%d/%d phiếu đồng thuận" % (len(gia_tri), len(gia_tri))
    elif px:
        khac = [v for k, v in co.items() if k != "phan_xu"]
        if px in khac:
            muc, cach = px, "trọng tài chọn %s (cùng %d phiếu khác)" % (px, khac.count(px))
            tin = "cao" if khac.count(px) >= 2 else "vừa"
        else:
            muc, tin = MUC[chi_so[(len(chi_so) - 1) // 2]], "thấp"
            cach = "trọng tài (%s) khác mọi phiếu khác – lấy mức trung vị" % px
    elif len(dem) == 1 or dem[0][1] > dem[1][1]:
        muc, tin, cach = dem[0][0], "vừa", "đa số %d/%d phiếu" % (dem[0][1], len(gia_tri))
    elif "luot1" in co and len(gia_tri) == 2:
        muc, tin, cach = co["luot1"], "thấp", "hai phiếu lệch nhau, không có trọng tài – tạm theo lượt 1"
    else:
        muc, tin, cach = MUC[chi_so[(len(chi_so) - 1) // 2]], "thấp", "không có đa số – lấy mức trung vị"
    if lech >= 3 and tin != "thấp":
        tin, cach = "thấp", cach + "; các phiếu lệch từ 3 bậc"
    if tu_tin_thap and tin == "cao":
        tin = "vừa"
    return {"muc_do": muc, "tin_cay": tin, "cach": cach, "phieu": dict(phieu)}


_XEP = {"cao": 2, "vừa": 1, "thấp": 0}


def _khoa_y(y):
    return str((y or {}).get("y", "")).strip().lower()[:1]


def _ban_do_y(g):
    return {_khoa_y(y): y for y in ((g or {}).get("y_ds") or []) if _khoa_y(y) in ("a", "b", "c", "d")}


def chot_cau(c, g1, g2=None, px=None):
    """
    Chốt mức cho MỘT câu. c: câu thô (cần dang); g1: kết quả lượt 1; g2: lượt 2; px: trọng tài ({} nếu không có).
    Trả {muc_do, tin_cay, cach, phieu, y_ds[{y, muc_do, kien_thuc, tin_cay, phieu}], muc_theo_tieu_chi, kiem_nhat_quan[]}.
    """
    g1, g2, px = g1 or {}, g2 or {}, px or {}
    tt = (g1.get("tu_tin") or "").lower().startswith("thấp")
    phieu = {"luot1": hop_le(g1.get("muc_do")), "luot2": hop_le(g2.get("muc_do")),
             "tieu_chi": _phieu_tieu_chi(g1, g2), "phan_xu": hop_le(px.get("muc_do"))}
    if c.get("dang") == "DS":
        y1, y2, yp = _ban_do_y(g1), _ban_do_y(g2), _ban_do_y(px)
        if y1 or y2 or yp:
            ds_y, muc_cau, tin_cau, cach_y = [], None, "cao", []
            for k in "abcd":
                p_y = {"luot1": hop_le((y1.get(k) or {}).get("muc_do")) or phieu["luot1"],
                       "luot2": hop_le((y2.get(k) or {}).get("muc_do")) or phieu["luot2"],
                       "tieu_chi": None,
                       "phan_xu": hop_le((yp.get(k) or {}).get("muc_do")) or (phieu["phan_xu"] if not yp else None)}
                r = chot_muc(p_y, tt)
                ds_y.append({"y": k, "muc_do": r["muc_do"], "tin_cay": r["tin_cay"], "phieu": r["phieu"],
                             "kien_thuc": str((y1.get(k) or y2.get(k) or {}).get("kien_thuc") or ""),
                             "nang_luc": chuan_nang_luc((y1.get(k) or {}).get("nang_luc") or g1.get("nang_luc"))})
                muc_cau = cao_hon(muc_cau, r["muc_do"])
                if _XEP[r["tin_cay"]] < _XEP[tin_cau]:
                    tin_cau = r["tin_cay"]
                if r["tin_cay"] == "thấp":
                    cach_y.append("ý %s: %s" % (k, r["cach"]))
            return {"muc_do": muc_cau, "tin_cay": tin_cau, "phieu": phieu, "y_ds": ds_y, "muc_theo_tieu_chi": phieu["tieu_chi"],
                    "cach": "mức cao nhất trong 4 ý" + ("; " + "; ".join(cach_y) if cach_y else "")}
    r = chot_muc(phieu, tt)
    r.update({"y_ds": [], "muc_theo_tieu_chi": phieu["tieu_chi"]})
    return r


def can_phan_xu(c, g1, g2=None):
    """True nếu câu cần trọng tài: các phiếu không đồng thuận, ý Đúng/Sai lệch nhau, hoặc vi phạm luật văn bản."""
    g1, g2 = g1 or {}, g2 or {}
    if not g1:
        return False
    p = [v for v in (hop_le(g1.get("muc_do")), hop_le(g2.get("muc_do")), _phieu_tieu_chi(g1, g2)) if v]
    if len(set(p)) > 1:
        return True
    if c.get("dang") == "DS":
        y1, y2 = _ban_do_y(g1), _ban_do_y(g2)
        if y2 and any((y1.get(k) or {}).get("muc_do") != (y2.get(k) or {}).get("muc_do") for k in "abcd"):
            return True
    tmp = dict(c)
    tmp.update({k: g1.get(k) for k in ("muc_do", "so_buoc", "tieu_chi", "ma_quy_tac")})
    return bool(kiem_nhat_quan(tmp))


def thong_ke_nhat_quan(ds_cau_da_hop_nhat):
    """Số liệu độ ổn định của việc phân loại (đưa vào thongKe.nhat_quan_nhan_thuc)."""
    n = len(ds_cau_da_hop_nhat)
    co2 = [c for c in ds_cau_da_hop_nhat if c.get("muc_do_luot1") and c.get("muc_do_luot2")]
    khop = sum(1 for c in co2 if c["muc_do_luot1"] == c["muc_do_luot2"])
    return {"so_cau": n, "so_cau_hai_luot": len(co2), "hai_luot_khop": khop,
            "ty_le_hai_luot_khop": round(khop / len(co2), 4) if co2 else None,
            "so_cau_phan_xu": sum(1 for c in ds_cau_da_hop_nhat if c.get("muc_do_phan_xu")),
            "tin_cay": {k: sum(1 for c in ds_cau_da_hop_nhat if c.get("muc_tin_cay") == k) for k in ("cao", "vừa", "thấp")}}
