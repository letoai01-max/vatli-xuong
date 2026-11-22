"""
do_chat_luong.py – ĐO ĐỘ CHÍNH XÁC THẬT CỦA PIPELINE DUYỆT (mục 5), CHỈ ĐỌC, KHÔNG GHI VÀO KHO.   [22/11/2026]

Ý tưởng: lấy mẫu ngẫu nhiên các câu "AI duyệt" dạng TN / DS / TLN, đưa riêng ĐỀ + PHƯƠNG ÁN (giấu đáp án) cho một model
KHÔNG nằm trong các phiếu đã duyệt, rồi so với "Đáp án" đã duyệt.
  • tỉ lệ khớp  = ước lượng cận dưới cho độ chính xác của đáp án đã duyệt (model kiểm có thể tự giải sai);
  • câu LỆCH    = danh sách ưu tiên để giáo viên soát (đây là chỗ nhiều khả năng duyệt nhầm nhất).
Tách kết quả theo: dạng câu, có/không hình, đáp án có từ HDC gốc hay do máy giải (đọc từ cột Kiểm tra) → biết chỗ nào lỏng.

Chạy (trong repo xưởng, có GROQ_API_KEY + GOOGLE_CREDENTIALS):
    python do_chat_luong.py --n 150 --ra bao_cao_chat_luong.md
Chạy thử không mạng:  python do_chat_luong.py --thu
"""
import argparse, collections, random, re, sys

TAB_NH = "NganHangCauHoi"
TT_AI = "AI duyệt"


def loai_dang(d):
    t = str(d or "").lower()
    if re.search(r"đúng|sai|ds", t): return "DS"
    if re.search(r"ngắn|tln", t): return "TLN"
    if re.search(r"tự luận|^tl$", t): return "TL"
    return "TN"


def nguon_dap_an(kt):
    """Đáp án đến từ HDC gốc hay máy giải? (đoán từ ghi chú lần chạy máy gần nhất)."""
    d = kt.rsplit("[5 tầng", 1)[-1] if "[5 tầng" in kt else ""
    if re.search(r"máy tự giải|không có HDC|thiếu HDC|tự giải", d, re.I): return "máy giải (không HDC)"
    if re.search(r"Cứu bằng bỏ phiếu|duyệt lại|cứu Loại", kt): return "cứu bằng phiếu/duyệt lại"
    return "HDC gốc / khớp thường"


def chon_mau(rows, td, n, seed=2026):
    c = {t: td.index(t) for t in ("Mã câu", "Dạng", "Nội dung", "Phương án", "Đáp án", "Trạng thái duyệt", "Kiểm tra")}
    ung = []
    for r in rows:
        r = r + [""] * (len(td) - len(r))
        if r[c["Trạng thái duyệt"]].strip() != TT_AI: continue
        loai = loai_dang(r[c["Dạng"]])
        if loai == "TL" or not r[c["Đáp án"]].strip(): continue     # tự luận dài khó so tự động
        ung.append({"ma": r[c["Mã câu"]], "dang": loai, "noi_dung": r[c["Nội dung"]], "phuong_an": r[c["Phương án"]],
                    "dap_an": r[c["Đáp án"]].strip(), "co_hinh": "[Hình" in r[c["Nội dung"]] or "[[DO_THI" in r[c["Nội dung"]],
                    "nguon": nguon_dap_an(r[c["Kiểm tra"]])})
    random.Random(seed).shuffle(ung)
    return ung[:n]


def so_sanh(mau, kq, khop, gan=None):
    """kq: {ma: đáp án model kiểm}. Trả (thống kê theo nhóm, danh sách lệch, số câu model không trả lời)."""
    tk = collections.defaultdict(lambda: [0, 0])
    lech, bo = [], 0
    for x in mau:
        g = kq.get(x["ma"])
        if not g: bo += 1; continue
        ok = khop(x["dang"], x["dap_an"], g)
        for nhom in ("TỔNG", "dạng " + x["dang"], "có hình" if x["co_hinh"] else "không hình", "nguồn: " + x["nguon"]):
            tk[nhom][0] += 1; tk[nhom][1] += ok
        if not ok:
            nho = bool(gan and gan(x["dang"], x["dap_an"], g))
            if nho: tk["(trong số lệch) chỉ lệch ≤3%, nhiều khả năng do làm tròn"][0] += 1
            lech.append((x["ma"], x["dang"], x["dap_an"], g + ("  (≈ làm tròn)" if nho else ""), x["nguon"]))
    return tk, lech, bo


def bao_cao(tk, lech, bo, n_mau, model):
    ra = ["# Đo chất lượng duyệt – model kiểm: %s\n" % model,
          "Mẫu: %d câu AI duyệt; model không trả lời được: %d (không tính vào tỉ lệ).\n" % (n_mau, bo),
          "| Nhóm | Số câu | Khớp | Tỉ lệ khớp |", "|---|---:|---:|---:|"]
    for k in sorted(tk, key=lambda s: (s != "TỔNG", s)):
        t, ok = tk[k]
        if k.startswith("(trong số lệch)"): ra.append("| %s | %d | – | – |" % (k, t)); continue
        ra.append("| %s | %d | %d | %.1f%% |" % (k, t, ok, 100 * ok / max(t, 1)))
    ra += ["\nLưu ý: lệch ≠ chắc chắn sai. Model kiểm có thể giải sai; hãy để giáo viên soát danh sách lệch (ưu tiên cao).\n",
           "## Câu lệch (%d)\n" % len(lech), "| Mã câu | Dạng | Đáp án đã duyệt | Model kiểm | Nguồn |", "|---|---|---|---|---|"]
    ra += ["| %s | %s | %s | %s | %s |" % (m, d, a, g, ng) for m, d, a, g, ng in lech[:80]]
    return "\n".join(ra)


def model_dang_chay():
    """Hỏi Groq danh sách model đang hoạt động (chỉ model chat). Lỗi mạng/khoá → []."""
    import os, requests
    try:
        r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": "Bearer " + os.environ["GROQ_API_KEY"]}, timeout=30)
        ids = [m["id"] for m in r.json().get("data", []) if m.get("active", True)]
    except Exception as e:
        print("Không lấy được danh sách model Groq:", str(e)[:100]); return []
    bo = re.compile(r"whisper|guard|tts|orpheus|playai|embed|distil-whisper|safeguard", re.I)
    return [i for i in ids if not bo.search(i)]


def thu():
    import types
    td = ["Mã câu", "Dạng", "Nội dung", "Phương án", "Đáp án", "Trạng thái duyệt", "Kiểm tra"]
    rows = [["c1", "Trắc nghiệm", "đề 1 dài dài", "A.1 B.2 C.3 D.4", "A", TT_AI, "[5 tầng 21/11] ok"],
            ["c2", "Đúng/Sai", "đề 2 [Hình: x]", "a) b) c) d)", "a) Đ, b) S, c) Đ, d) S", TT_AI, "[5 tầng 21/11] máy tự giải"],
            ["c3", "Trả lời ngắn", "đề 3", "", "12,5", TT_AI, "[5 tầng 21/11 duyệt lại] Cứu bằng bỏ phiếu"],
            ["c4", "Trắc nghiệm", "đề 4", "", "B", "Loại", ""],
            ["c5", "Tự luận", "đề 5", "", "x", TT_AI, ""]]
    mau = chon_mau(rows, td, 10)
    assert {x["ma"] for x in mau} == {"c1", "c2", "c3"}, mau
    import duyet_cau as D
    kq = {"c1": "A", "c2": "a) Đ, b) Đ, c) Đ, d) S", "c3": "12.5"}
    tk, lech, bo = so_sanh(mau, kq, D.khop)
    assert tk["TỔNG"] == [3, 2] and [l[0] for l in lech] == ["c2"] and bo == 0, (dict(tk), lech)
    assert tk["có hình"] == [1, 0] and tk["dạng TLN"] == [1, 1]
    print(bao_cao(tk, lech, bo, len(mau), "giả")); print("\n✅ Tự kiểm tra đạt.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150); ap.add_argument("--model", default="", help="để trống = tự chọn model đang hoạt động, ưu tiên model chưa bỏ phiếu")
    ap.add_argument("--ra"); ap.add_argument("--thu", action="store_true")
    ap.add_argument("--lo", type=int, default=5, help="số câu mỗi lượt hỏi (nhỏ để khỏi vượt token/phút của Groq)")
    ap.add_argument("--nghi", type=float, default=8, help="giây nghỉ giữa các lượt")
    ap.add_argument("--phut", type=float, default=15, help="tối đa bao nhiêu phút")
    a = ap.parse_args()
    if a.thu: return thu()
    import doc_de as X, duyet_cau as D, groq_xuong as G
    if not G.co_khoa(): sys.exit("Thiếu GROQ_API_KEY.")
    gc, _d, _s = X.ket_noi()
    v = gc.open_by_key(X.ID_KHO_CHUNG).worksheet(TAB_NH).get_all_values()
    td = [t.strip() for t in v[0]]
    mau = chon_mau(v[1:], td, a.n)
    print("Mẫu %d câu ..." % len(mau), flush=True)
    bo = [{"ma": x["ma"], "dang": x["dang"], "noi_dung": x["noi_dung"], "phuong_an": x["phuong_an"]} for x in mau]
    song = [m for m in model_dang_chay() if "allam" not in m]         # allam-2-7b: yếu và giới hạn 4096 token → bỏ
    print("Model Groq dùng được:", ", ".join(song) or "(không lấy được)", flush=True)
    thu_lan = ([a.model] if a.model else []) + [m for m in song if m != a.model]
    if not thu_lan: sys.exit("Không có model Groq nào để dùng.")
    import time
    kq, dung, het_gio = {}, collections.Counter(), time.time() + a.phut * 60
    for k in range(0, len(bo), a.lo):
        if time.time() > het_gio: print("Hết %d phút, dừng ở câu %d/%d." % (a.phut, k, len(bo))); break
        chunk = bo[k:k + a.lo]
        for m in thu_lan:                                              # model đầu hết hạn mức → sang model kế, không bỏ lô
            r, _ = G.giai_lo(chunk, [m])
            if r: kq.update(r); dung[m] += len(r); break
        print("  đã hỏi %d/%d câu, có đáp án %d" % (min(k + a.lo, len(bo)), len(bo), len(kq)), flush=True)
        time.sleep(a.nghi)
    if not kq: sys.exit("Không model Groq nào trả được đáp án (xem danh sách model ở trên; có thể hết hạn mức).")
    model = ", ".join("%s (%d câu)" % kv for kv in dung.most_common())
    gan = lambda d, x, y: d in ("TLN", "TL") and D.khop(d, x, y, sai_so=0.03)
    s = bao_cao(tk, lech, boqua, len(mau), model or a.model)
    print(s)
    if a.ra: open(a.ra, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    main()
