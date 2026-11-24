"""kiem_thu_duyet_nhanh.py – kiểm thử [24/11/2026] chia lô Groq, ngắt sớm, ghi cuốn chiếu của duyet_cau.py (không cần khoá, không gọi mạng)."""
import os, sys, time, types, datetime as dt
def chay():
    """Chạy toàn bộ ca; trả danh sách ca hỏng. Dọn sạch os.environ / sys.modules / time.sleep sau khi xong để không ảnh hưởng test khác."""
    ban_dau_mod = {k: sys.modules.get(k) for k in ("doc_de", "groq_xuong", "duyet_cau")}
    ban_dau_env = dict(os.environ); ban_dau_ngu = time.sleep
    try:
        os.environ.update({"GROQ_HAN_PHUT": "0.02", "GHI_GIAN_CACH": "0"})   # hạn 1,2 giây để test nhanh
        # --- giả lập thư viện cùng thư mục ---
        X = types.ModuleType("doc_de"); X.HetHanMuc = type("HetHanMuc", (Exception,), {}); X.TZ = dt.timezone(dt.timedelta(hours=7))
        X.bo_dau = lambda s: s; X.CT_CU_MO_TA = ""
        sys.modules["doc_de"] = X
        G = types.ModuleType("groq_xuong"); G.co_khoa = lambda: True
        sys.modules["groq_xuong"] = G
        import duyet_cau as D
        D.GHI_GIAN_CACH = 0
        loi = []
        def kiem(ten, dieu_kien):
            print(("✅ " if dieu_kien else "❌ ") + ten, flush=True)
            if not dieu_kien: loi.append(ten)

        bo = [{"ma": "C%d" % i, "dang": "TN", "noi_dung": "n", "phuong_an": "p"} for i in range(5)]

        # 1. chia lô 2 câu + truyền max_completion_tokens khi hàm nhận
        goi = []
        def giai_ok(lo, models=None, max_completion_tokens=None):
            goi.append((len(lo), max_completion_tokens)); return {x["ma"]: "A" for x in lo}, "m1"
        G.giai_lo = giai_ok
        kq, m = D._groq_giai(bo)
        kiem("chia 5 câu thành lô 2+2+1", [g[0] for g in goi] == [2, 2, 1] and len(kq) == 5 and m == "m1")
        kiem("truyền max_completion_tokens=450", all(g[1] == 450 for g in goi))

        # 2. hàm không nhận max_completion_tokens → vẫn chạy, không lỗi
        def giai_cu(lo, models=None): return {x["ma"]: "B" for x in lo}, "m2"
        G.giai_lo = giai_cu; D._groq_canh_bao["max_token"] = False
        kq, m = D._groq_giai(bo)
        kiem("giai_lo cũ (không nhận max_completion_tokens) vẫn chạy", len(kq) == 5)

        # 3. rỗng 2 lô liên tiếp → dừng sớm, không gọi hết
        dem = []
        def giai_rong(lo, models=None, **kw): dem.append(1); return {}, ""
        G.giai_lo = giai_rong
        kq, m = D._groq_giai(bo)
        kiem("2 lô rỗng liên tiếp → dừng (gọi đúng 2 lần, không phải 3)", len(dem) == 2 and kq == {})

        # 4. quá hạn thời gian → trả phần đã giải, không treo
        def giai_cham(lo, models=None, **kw):
            if lo[0]["ma"] == "C0": return {"C0": "A", "C1": "A"}, "m3"
            time.sleep(30); return {x["ma"]: "A" for x in lo}, "m3"
        G.giai_lo = giai_cham
        t0 = time.time(); kq, m = D._groq_giai(bo); dt_ = time.time() - t0
        kiem("quá hạn: về sau ~1–3 giây (không ngủ 30 giây) và giữ 2 câu đã giải", dt_ < 6 and set(kq) == {"C0", "C1"})

        # 5. ngắt mạch 2 file liên tiếp
        D._groq_rong.update({"lien_tiep": 0, "da_bao": False})
        G.giai_lo = giai_rong
        ds = [{"ma": "C1", "dang": "TN", "noi_dung": "n", "phuong_an": "p"}]
        D.tang4_groq(ds); D.tang4_groq(ds)
        kiem("GROQ_NGAT_SAU=2: sau 2 file rỗng thì ngắt mạch", D.groq_da_ngat())

        # 6. ghi cuốn chiếu
        class Tab:
            def __init__(s, hong=0): s.lan = []; s.hong = hong
            def col_values(s, k): return ["Mã câu", "C1", "C2", "C3"]
            def batch_update(s, cap, value_input_option=None):
                if s.hong > 0: s.hong -= 1; raise RuntimeError("429")
                s.lan.append(cap)
        D.time.sleep = lambda *_: None
        c = {"Mã câu": 0, "Trạng thái duyệt": 1, "Kiểm tra": 2, "Đáp án": 3}
        def mk(ma, loi_nang=None):
            return {"ma": ma, "loi_nang": loi_nang or [], "nghi_van": [], "ghi_chu": [], "sua": {}, "bat_dong": [], "co_hinh": False,
                    "hoan": False, "kiem_tra_cu": "", "duyet_lai": False, "cuu_loai": False}
        tk = {"ai": 0, "xem": 0, "loai": 0, "hoan": 0}
        t = Tab(); ds = [mk("C1", ["Thiếu phương án (3/4)"]), mk("C2"), mk("C3")]
        D.ghi_ket_qua(t, c, None, [x for x in ds if x["loi_nang"]], "24/11", tk)       # ghi sớm câu Loại
        kiem("ghi sớm: 1 lần ghi cho câu Loại tầng 1", len(t.lan) == 1 and tk["loai"] == 1)
        D.ghi_ket_qua(t, c, None, ds, "24/11", tk)                                      # ghi phần còn lại
        kiem("ghi cuối: mỗi câu một lần ghi, không ghi lại câu đã ghi (tổng 3 lần)", len(t.lan) == 3 and tk == {"ai": 2, "xem": 0, "loai": 1, "hoan": 0})

        # 7. tắt GHI_CUON_CHIEU → một lần ghi cho cả file
        D.GHI_CUON_CHIEU = False; tk = {"ai": 0, "xem": 0, "loai": 0, "hoan": 0}; t = Tab(); ds = [mk("C1"), mk("C2"), mk("C3")]
        D.ghi_ket_qua(t, c, None, ds, "24/11", tk)
        kiem("GHI_CUON_CHIEU=false: một batch_update cho cả file như cũ", len(t.lan) == 1 and tk["ai"] == 3)
        D.GHI_CUON_CHIEU = True

        # 8. ghi lỗi 1 lần → thử lại thành công; hỏng hẳn 2 nhóm liên tiếp → dừng lượt
        tk = {"ai": 0, "xem": 0, "loai": 0, "hoan": 0}; t = Tab(hong=1); ds = [mk("C1")]
        D._ghi["loi_lien_tiep"] = 0
        D.ghi_ket_qua(t, c, None, ds, "24/11", tk)
        kiem("ghi lỗi thoáng qua → thử lại được", len(t.lan) == 1 and tk["ai"] == 1)
        t = Tab(hong=99); ds = [mk("C1"), mk("C2")]; D._ghi["loi_lien_tiep"] = 0
        try:
            D.ghi_ket_qua(t, c, None, ds, "24/11", {"ai": 0, "xem": 0, "loai": 0, "hoan": 0}); dung = False
        except D.LoiGhiSheet: dung = True
        kiem("Sheets hỏng liên tiếp → LoiGhiSheet (Actions báo đỏ)", dung and not any(x.get("da_ghi") for x in ds))

        # 9. [24/11] giới hạn thời gian cụm tầng: việc ngủ lâu → HetHanMuc, không treo
        t0 = time.time()
        try:
            D._chay_co_han({"a": lambda: 1, "b": lambda: __import__("threading").Event().wait(30)}, 0.02); dung = False
        except X.HetHanMuc: dung = True
        kiem("quá hạn cụm tầng → HetHanMuc sau ~1–3 giây (không ngủ 30 giây)", dung and time.time() - t0 < 6 and D._bo_roi["co"])
        D._bo_roi["co"] = False
        kq = D._chay_co_han({"a": lambda: 1, "b": lambda: 2}, 1)
        kiem("trong hạn: trả đủ kết quả", kq == {"a": 1, "b": 2})
        def hong(): raise ValueError("x")
        try:
            D._chay_co_han({"a": lambda: 1, "b": hong}, 1); dung = False
        except ValueError: dung = True
        kiem("lỗi của một việc được ném lại đúng loại lỗi", dung)
        kq = D._chay_co_han({"a": lambda: 7}, 0)
        kiem("TANG_HAN_PHUT=0: không giới hạn, vẫn chạy", kq == {"a": 7})


        return loi
    finally:
        time.sleep = ban_dau_ngu
        os.environ.clear(); os.environ.update(ban_dau_env)
        for k, v in ban_dau_mod.items():
            if v is None: sys.modules.pop(k, None)
            else: sys.modules[k] = v


def test_duyet_nhanh():
    assert chay() == []


if __name__ == "__main__":
    loi = chay()
    print("\nTHẤT BẠI: %s" % loi if loi else "\nTẤT CẢ ĐẠT")
    sys.exit(1 if loi else 0)
