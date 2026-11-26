"""
pt_so_khop.py – ĐỐI CHIẾU ĐÁP ÁN VỚI ĐÁP ÁN CHÍNH THỨC TRONG TỆP ĐỀ (THUẦN CODE, không gọi AI). [25/11/2026]

Ba nguồn "không chính thức" được so với đáp án chính thức (dap_an_de, chép từ tệp đề / hướng dẫn chấm):
  may    đáp án máy giải độc lập bằng code (giai_may → da_may)
  groq   đáp án AI thứ hai, khác hãng (giai_may → da_groq; chỉ có ở câu tranh chấp / chỉ có máy)
  soan   đáp án do người hoặc AI soạn đề đưa vào (goi.dapAnSoan = {"I.3": "B", "II.1": "a) Đ, b) S, c) Đ, d) S", "III.2": "2,5"})

Với MỖI câu trả về kết luận KHỚP / KHÔNG KHỚP (kèm chi tiết ý lệch) và nguồn chốt:
  Đề của Bộ GD&ĐT (la_de_bo) và có đáp án trong tệp → CHỐT ĐÁP ÁN BỘ PHÁT HÀNH, máy/AI chỉ để so; lệch thì ghi "KHÔNG KHỚP" chứ không đề nghị sửa đáp án Bộ.
  Đề khác → giữ logic cũ của giai_may (hai bằng chứng độc lập), vẫn ghi KHỚP / KHÔNG KHỚP với đáp án trong đề.

Hàm so khớp (loai_dang, chuan, khop) lấy từ duyet_cau để dùng đúng một chuẩn với giai_may; truyền ham=(…) khi test.
"""
import re

import pt_danh_muc as DM
from pt_nhan_thuc import khong_dau

NGUON_TEN = {"may": "máy giải", "groq": "AI thứ hai (Groq)", "soan": "đáp án soạn"}
NGUON_BO = "BỘ PHÁT HÀNH"

_LOAI_TRU = ("thi thu", "khao sat", "de xuat", "on tap", "giua ky", "cuoi ky", "hoc ky", "so giao duc", "so gd", "tu luyen", "tu soan", "do truong")
_NHAN_BO = ("chinh thuc", "bo giao duc", "bo gd", "bo phat hanh", "minh hoa", "tham khao cua bo")


def la_de_bo(thong_tin, goi_thong_tin=None, che_do="tu_dong"):
    """
    Đề có đáp án do Bộ GD&ĐT phát hành không? Trả (True/False, lí do).
    che_do (goi.tuyChon.nguonDapAnChot): "bo" = ép là đề Bộ · "khong" = ép không phải · "tu_dong" (mặc định) = tự nhận diện.
    Tự nhận diện thận trọng: đề thi thử / khảo sát / của Sở / của trường KHÔNG bao giờ được coi là đề Bộ.
    """
    che_do = str(che_do or "tu_dong").lower()
    if che_do in ("bo", "true", "1"):
        return True, "giáo viên chọn nguồn chốt = đáp án Bộ"
    if che_do in ("khong", "false", "0", "may"):
        return False, "giáo viên tắt chốt theo đáp án Bộ"
    tt, g = thong_tin or {}, goi_thong_tin or {}
    loai = khong_dau(g.get("loaiDe"))
    chu = khong_dau(" ".join(str(x) for x in (g.get("tenDe"), g.get("kyThi"), tt.get("ten_de"), tt.get("ky_thi"), tt.get("don_vi")) if x))
    if any(t in loai + " " + chu for t in _LOAI_TRU):
        return False, "đề thi thử / khảo sát / của Sở, trường – không phải đề Bộ"
    if any(t in loai for t in _NHAN_BO) or ("tot nghiep" in loai and "quoc gia" in loai):
        return True, "loại đề giáo viên nhập: %s" % g.get("loaiDe")
    if "bo giao duc" in chu and ("tot nghiep" in chu or "trung hoc pho thong" in chu) and "de" in chu:
        return True, "đầu đề ghi Bộ Giáo dục và Đào tạo – kì thi tốt nghiệp THPT"
    return False, "không nhận diện được là đề Bộ"


# ====================================================================================== tiện ích
def _ham_mac_dinh():
    from duyet_cau import loai_dang, chuan, khop
    return loai_dang, chuan, khop


_DS = re.compile(r"([a-d])\s*[\)\.:\-]?\s*(đúng|sai|đ|s|true|false)\b", re.I)


def tach_y_ds(s):
    """'a) Đ, b) S, …' → {'a': 'Đ', 'b': 'S', …} (chuẩn hoá Đ/S)."""
    ra = {}
    for k, v in _DS.findall(str(s or "")):
        ra[k.lower()] = "Đ" if v.lower() in ("đúng", "đ", "true") else "S"
    return ra


def _chi_tiet(loai, da_chinh_thuc, da_khac, ten_nguon, ten_chinh):
    """Mô tả chỗ lệch: 'ý b: Bộ Đ ↔ máy S' / 'Bộ B ↔ máy C'."""
    if loai == "DS":
        a, b = tach_y_ds(da_chinh_thuc), tach_y_ds(da_khac)
        lech = ["ý %s: %s %s ↔ %s %s" % (k, ten_chinh, a.get(k, "?"), ten_nguon, b.get(k, "?")) for k in "abcd" if a.get(k) != b.get(k)]
        if lech:
            return "; ".join(lech)
    return "%s %s ↔ %s %s" % (ten_chinh, da_chinh_thuc, ten_nguon, da_khac)


def so_sanh_mot(loai, da_chinh_thuc, da_khac, ham):
    """(ket_luan, chi_tiet) một nguồn so với đáp án chính thức. ket_luan: KHỚP | KHÔNG KHỚP | CHƯA CÓ."""
    _, _, khop = ham
    if not str(da_khac or "").strip():
        return "CHƯA CÓ", ""
    return ("KHỚP", "") if khop(loai, da_khac, da_chinh_thuc) else ("KHÔNG KHỚP", "")


# ====================================================================================== đối chiếu cả đề
def doi_chieu(ds_cau, giai, dap_an_soan=None, la_bo=False, ham=None):
    """
    ds_cau: câu thô đã chuẩn hoá (cần ma, dang, dap_an_de). giai: {ma: kết quả giai_may} (có thể rỗng). Trả BẢN SAO giai đã bổ sung, mỗi câu thêm:
      so_khop            {may, groq, soan: KHỚP | KHÔNG KHỚP | CHƯA CÓ}
      ket_luan_so_khop   KHỚP | KHÔNG KHỚP | CHƯA ĐỐI CHIẾU (có đáp án chính thức nhưng chưa nguồn nào trả lời) | CHƯA CÓ ĐÁP ÁN CHÍNH THỨC
      chi_tiet_lech      chữ mô tả chỗ lệch (rỗng nếu khớp)
      nguon_chot         BỘ PHÁT HÀNH | ĐÁP ÁN TRONG ĐỀ | MÁY / AI | CHƯA CHỐT ĐƯỢC
      da_chot, da_soan, la_de_bo
    """
    ham = ham or _ham_mac_dinh()
    loai_dang, chuan, _ = ham
    dap_an_soan = dap_an_soan or {}
    ra = {}
    for c in ds_cau:
        ma, loai = c["ma"], loai_dang(c["dang"])
        r = dict((giai or {}).get(ma) or {})
        chinh = str(c.get("dap_an_de") or r.get("da_de") or "").strip()
        soan_tho = dap_an_soan.get(ma)
        soan = chuan(loai, soan_tho) if str(soan_tho or "").strip() else ""
        nguon = {"may": str(r.get("da_may") or ""), "groq": str(r.get("da_groq") or ""), "soan": str(soan or "")}
        sk, lech = {}, []
        for k, v in nguon.items():
            if chinh:
                kl, _ = so_sanh_mot(loai, chinh, v, ham)
                if kl == "KHÔNG KHỚP":
                    lech.append(_chi_tiet(loai, chinh, v, {"may": "máy", "groq": "Groq", "soan": "soạn"}[k], "Bộ" if la_bo else "đề"))
            else:
                kl = "CHƯA CÓ"
            sk[k] = kl
        co = [v for v in sk.values() if v != "CHƯA CÓ"]
        if not chinh:
            ketluan = "CHƯA CÓ ĐÁP ÁN CHÍNH THỨC"
        elif not co:
            ketluan = "CHƯA ĐỐI CHIẾU"
        else:
            ketluan = "KHỚP" if all(v == "KHỚP" for v in co) else "KHÔNG KHỚP"
        # --- nguồn chốt
        da_chot_cu = str(r.get("da_chot") or "")
        if la_bo and chinh:
            da_chot, nguon_chot = chinh, NGUON_BO
            r["do_tin_cay"] = "cao"
            if r.get("ket_luan") == "LỆCH_NÊN_SỬA":           # đáp án Bộ không bao giờ "nên sửa"
                r["ket_luan"] = "LỆCH_CẦN_XEM"
        elif chinh and da_chot_cu == chinh:
            da_chot, nguon_chot = chinh, "ĐÁP ÁN TRONG ĐỀ"
        elif da_chot_cu:
            da_chot, nguon_chot = da_chot_cu, "MÁY / AI"
        else:
            da_chot, nguon_chot = "", "CHƯA CHỐT ĐƯỢC"
        r.update({"da_de": chinh, "so_khop": sk, "ket_luan_so_khop": ketluan, "chi_tiet_lech": "; ".join(lech),
                  "nguon_chot": nguon_chot, "da_chot": da_chot, "da_soan": soan, "la_de_bo": bool(la_bo)})
        ra[ma] = r
    return ra


def thong_ke_doi_chieu(ds_cau_da_hop_nhat, la_bo=False, ly_do_bo=""):
    """Tổng hợp cho thongKe.doi_chieu_dap_an (thuần số liệu)."""
    d = {k: 0 for k in ("KHỚP", "KHÔNG KHỚP", "CHƯA ĐỐI CHIẾU", "CHƯA CÓ ĐÁP ÁN CHÍNH THỨC")}
    khong_khop = []
    nguon = {}
    for c in ds_cau_da_hop_nhat:
        kl = c.get("ket_luan_so_khop") or "CHƯA CÓ ĐÁP ÁN CHÍNH THỨC"
        d[kl] = d.get(kl, 0) + 1
        nguon[c.get("nguon_chot") or "CHƯA CHỐT ĐƯỢC"] = nguon.get(c.get("nguon_chot") or "CHƯA CHỐT ĐƯỢC", 0) + 1
        if kl == "KHÔNG KHỚP":
            khong_khop.append({"ma": c["ma"], "da_chinh_thuc": c.get("da_de", ""), "da_chot": c.get("da_chot", ""), "chi_tiet": c.get("chi_tiet_lech", "")})
    da_so = d["KHỚP"] + d["KHÔNG KHỚP"]
    return {"la_de_bo": bool(la_bo), "ly_do_nhan_dien": ly_do_bo, "nguon_chot": nguon, "so_cau": d, "ty_le_khop": round(d["KHỚP"] / da_so, 4) if da_so else None,
            "cau_khong_khop": khong_khop}
