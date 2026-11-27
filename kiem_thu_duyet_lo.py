"""Kiểm thử chế độ lô của duyet_cau.main() bằng dữ liệu giả (không cần khoá, không gọi mạng)."""
import sys, types, os, importlib

class Dummy(types.ModuleType):
    def __getattr__(self, k):
        if k.startswith("__"): raise AttributeError(k)
        return lambda *a, **kw: None
class HetHanMuc(Exception): pass

def nap(so_lo, toi_da, het_o_lo=None):
    os.environ.update(DUYET_LO_CAU=str(so_lo), DUYET_TOI_DA_CAU=str(toi_da), GHI_GIAN_CACH="0")
    for m in ("doc_de", "duyet_cau"): sys.modules.pop(m, None)
    X = Dummy("doc_de"); X.HetHanMuc = HetHanMuc
    X.bo_dau = lambda t: t; X.ID_KHO_CHUNG = "k"; X.TAB_YCCD = "y"; X.TZ = None; X.CT_CU_MO_TA = ""
    sys.modules["doc_de"] = X
    D = importlib.import_module("duyet_cau")
    D.GHI_GIAN_CACH = 0
    td = ["Mã câu","Mã YCCĐ","Mã bài","Lớp","Mức độ","Dạng","Nội dung","Phương án","Đáp án","Tên file","File ID","Kiểm tra","Trạng thái duyệt"]
    rows = [td] + [["C%02d"%i,"","","","","TN","nd %d"%i,"A.1 B.2 C.3 D.4","A","f (câu %d)"%i,"F1","","Chưa duyệt"] for i in range(25)]
    class WS:
        def get_all_values(self): return rows
        def col_values(self, n): return [r[n-1] for r in rows]
    class Kho:
        def worksheet(self, t): return WS()
    X.ket_noi = lambda: (None, None, "sa")
    X.doc_cau_hinh = lambda kho: ["m"]
    X.bay_gio = lambda: "t"
    nhat = {"lo": [], "ghi": []}
    class K(Kho): pass
    gc = types.SimpleNamespace(open_by_key=lambda i: K())
    X.ket_noi = lambda: (gc, None, "sa")
    D.doc_chi_muc = lambda kho: {}
    D.tang1 = lambda x, y: None
    D.lay_tep_goc = lambda *a: {"mime": "x", "data": b""}
    def tang(tep, lo, yccd, cm):
        nhat["lo"].append(len(lo))
        if het_o_lo and len(nhat["lo"]) == het_o_lo: raise HetHanMuc("cạn")
        return {}, [], "m", {}, {}, "m", {}, ""
    D.chay_cac_tang = tang
    D.quyet_dinh = lambda x, *a: x.__setitem__("hoan", False)
    D.xep_loai = lambda x: "AI duyệt"
    def ghi(tab, c, c_anh, ds, ngay, tk):
        for x in ds:
            if x.get("da_ghi") or x["loi_nang"]: continue
            x["da_ghi"] = True; nhat["ghi"].append(x["ma"]); tk["ai"] += 1
    D.ghi_ket_qua = ghi
    D.mau_ngau_nhien = D.do_chinh_xac = D.ghi_nhip = lambda *a, **k: None
    D.Q = None; D.VH = None; D.CT = None; D.CN = None; D.TU_SUA = False
    D.PHIEU_BA = False; D.CUU_HINH = False; D.cuu_them_file = lambda *a: None; D.SONG_SONG = False
    D.chay_cac_tang = tang
    return D, nhat

# 1) lô 10, không giới hạn → 10+10+5, ghi hết 25 câu
D, n = nap(10, 0); D.main()
assert n["lo"] == [10, 10, 5] and len(n["ghi"]) == 25, n

# 2) trần 12 câu → lô 10 + lô cắt còn 2; chỉ ghi 12 câu
D, n = nap(10, 12); D.main()
assert n["lo"] == [10, 2] and len(n["ghi"]) == 12, n

# 3) hết hạn mức ở lô 2 → 10 câu của lô 1 đã được ghi, lô 2 không ghi
D, n = nap(10, 0, het_o_lo=2); D.main()
assert n["lo"] == [10, 10] and len(n["ghi"]) == 10, n

# 4) chế độ cũ (0): một lô 25 câu, ghi hết
D, n = nap(0, 0); D.main()
assert n["lo"] == [25] and len(n["ghi"]) == 25, n
print("TẤT CẢ ĐẠT")
