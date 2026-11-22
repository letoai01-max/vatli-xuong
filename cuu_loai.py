"""
cuu_loai.py – CỨU CÂU "LOẠI" DO LỖI TÁCH ĐỀ (thiếu phương án / thiếu ý / đề quá ngắn / lỗi nội dung) – bước 2, tự động.   [22/11/2026]

Với mỗi câu "Loại" do MÁY đặt (cột Kiểm tra có "[5 tầng") vì các lí do trên (không phải trùng, ngoài CT 2018):
  1. Gửi FILE GỐC cho Gemini, yêu cầu tìm lại đúng câu đó và chép NGUYÊN VĂN đề + phương án (không tự bịa).
  2. Kiểm tra bản mới bằng code: đủ 4 phương án / 4 ý, đủ dài, GIỐNG câu cũ (≥ 60% từ đầu câu cũ còn trong bản mới), dấu $ chẵn.
  3. Đạt → ghi đè Nội dung + Phương án, trả trạng thái về "Chưa duyệt" để duyet_cau.py chạy lại ĐẦY ĐỦ 5 tầng (không tự duyệt ở đây).
     Không đạt → giữ "Loại", ghi dấu để không làm lại.
Mỗi câu chỉ cứu MỘT lần: dấu "[cứu Loại dd/mm: …]" ở cột Kiểm tra. CUU_LOAI_TOI_DA câu mỗi lượt (mặc định 150).
"""
import base64, datetime as dt, json, os, re, time

import doc_de as X
import duyet_cau as D
import cuu_nghi_van as CN

try:
    import quota_xuong as Q
except Exception:
    Q = None

DAU = "cứu Loại"
LI_DO_TACH = re.compile(r"Thiếu phương án|Thiếu ý đúng/sai|Nội dung câu quá ngắn|Lỗi nội dung|số liệu chưa có trong bản lưu")   # [22/11] thêm: bản lưu thiếu số liệu so với đề gốc = lỗi tách đề
LI_DO_KHONG_CUU = re.compile(r"Trùng hẳn|Ngoài chương trình")
LO = 12
TOI_DA = int(float(os.environ.get("CUU_LOAI_TOI_DA", "150") or 150))
SCHEMA = {"type": "OBJECT", "properties": {"ket_qua": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "ma_cau": {"type": "STRING"}, "tim_thay": {"type": "BOOLEAN"}, "noi_dung": {"type": "STRING"}, "phuong_an": {"type": "STRING"}},
    "required": ["ma_cau", "tim_thay"]}}}, "required": ["ket_qua"]}


def la_loai_do_tach(kt):
    """Câu Loại do máy, vì lỗi tách đề, chưa từng được cứu."""
    if DAU in kt or D.DAU_MAY not in kt: return False
    doan = kt.rsplit(D.DAU_MAY, 1)[-1]
    return bool(LI_DO_TACH.search(doan)) and not LI_DO_KHONG_CUU.search(doan)


def hop_le(dang, nd_cu, nd, pa):
    """None nếu bản tách lại dùng được; ngược lại trả lí do (chuỗi). Trả thêm (nd, pa) đã cân $ qua hop_le_day_du."""
    loai = D.loai_dang(dang)
    nd, pa = str(nd or "").strip(), str(pa or "").strip()
    if len(re.sub(r"\s", "", nd)) < 15: return "đề tách lại vẫn quá ngắn"
    n = D.dem_phuong_an(loai, nd, pa) if loai in ("TN", "DS") else 4
    if loai in ("TN", "DS") and n < 4: return "tách lại vẫn thiếu phương án/ý (%d/4)" % n
    a = set(X.bo_dau(str(nd_cu)[:120]).split())
    b = set(X.bo_dau(nd).split())
    if a and len(a & b) / len(a) < 0.6: return "bản tách lại không giống câu cũ (có thể nhầm câu)"
    return None


def hop_le_day_du(dang, nd_cu, nd, pa):
    """(nd, pa, None) nếu dùng được (đã cân $ nếu cần); (None, None, lí do) nếu không."""
    nd, ok1 = CN.sua_dola(str(nd or "")); pa, ok2 = CN.sua_dola(str(pa or ""))
    if not (ok1 and ok2): return None, None, "dấu $ lẻ, không cân được"
    ly = hop_le(dang, nd_cu, nd, pa)
    return (nd, pa, None) if ly is None else (None, None, ly)


def tach_lai(tep, lo, cac_model):
    du_lieu = [{"ma_cau": x["ma"], "vi_tri": x["vi_tri"], "dang": x["dang"], "dau_cau": str(x["nd"])[:150],
                "phuong_an_hien_co": str(x["pa"])[:300]} for x in lo]
    loi = ("File đính kèm là ĐỀ GỐC. Với MỖI câu dưới đây (nhận ra bằng vi_tri và dau_cau), tìm đúng câu đó trong file và chép LẠI ĐẦY ĐỦ, "
           "NGUYÊN VĂN: noi_dung = phần đề bài (công thức LaTeX đặt trong $…$, số thập phân dấu phẩy, nếu có hình ghi [Hình: mô tả ngắn]); "
           "phuong_an = các phương án (nhiều lựa chọn: A., B., C., D.) hoặc các ý (đúng/sai: a), b), c), d)), MỖI cái một dòng. "
           "KHÔNG chép đáp án / hướng dẫn chấm vào noi_dung hay phuong_an. KHÔNG tự bịa hay suy đoán phương án: nếu file thật sự thiếu "
           "hoặc không tìm ra câu thì tim_thay = false.\nCÁC CÂU:\n" + json.dumps(du_lieu, ensure_ascii=False))
    data, _ = X.goi_gemini({"contents": [{"role": "user", "parts": [
        {"inline_data": {"mime_type": tep["mime"], "data": base64.b64encode(tep["data"]).decode()}}, {"text": loi}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA, "temperature": 0, "maxOutputTokens": 30000}},
        cac_model)
    j = json.loads("".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]))
    return {str(g.get("ma_cau")): g for g in j.get("ket_qua", [])}


def main():
    gc, drive, sa = X.ket_noi()
    kho = gc.open_by_key(X.ID_KHO_CHUNG)
    tab = kho.worksheet(D.TAB_NH)
    d = tab.get_all_values()
    td = d[0]
    c = {t: td.index(t) for t in ["Mã câu", "Dạng", "Nội dung", "Phương án", "Tên file", "File ID", "Kiểm tra", "Trạng thái duyệt"] if t in td}
    cac_model = X.doc_cau_hinh(kho)
    nhom = {}
    for r in d[1:]:
        r = r + [""] * (len(td) - len(r))
        if r[c["Trạng thái duyệt"]].strip() != D.TT["LOAI"] or not la_loai_do_tach(r[c["Kiểm tra"]]): continue
        fid = r[c["File ID"]].strip() or "khong_ro"
        if fid == "khong_ro": continue
        nhom.setdefault(fid, []).append({"ma": r[c["Mã câu"]], "dang": r[c["Dạng"]], "nd": r[c["Nội dung"]], "pa": r[c["Phương án"]],
                                         "vi_tri": (re.search(r"\(câu\s*([^)]*)\)", r[c["Tên file"]]) or [None, ""])[1],
                                         "ly_do": r[c["Kiểm tra"]].rsplit(D.DAU_MAY, 1)[-1][:150]})
    tong = sum(len(v) for v in nhom.values())
    print("Có %d câu Loại do lỗi tách đề trong %d file." % (tong, len(nhom)), flush=True)
    ngay = dt.datetime.now(X.TZ).strftime("%d/%m")
    thong_ke = {"cuu": 0, "khong": 0}
    da_lam = 0
    for fid, ds in nhom.items():
        if da_lam >= TOI_DA or not D.con_gio(): break
        ds = ds[:TOI_DA - da_lam]
        try:
            tep = D.mo_tep_goc(drive, fid)
            if not tep:
                ket = {x["ma"]: None for x in ds}
            else:
                moi = {}
                for k in range(0, len(ds), LO): moi.update(tach_lai(tep, ds[k:k + LO], cac_model))
                ket = {}
                for x in ds:
                    g = moi.get(x["ma"])
                    if not g or not g.get("tim_thay"): ket[x["ma"]] = (None, "file gốc không có / không tìm lại được câu này"); continue
                    nd, pa, ly = hop_le_day_du(x["dang"], x["nd"], g.get("noi_dung"), g.get("phuong_an"))
                    ket[x["ma"]] = (None, ly) if ly else ((nd, pa), "")
        except X.HetHanMuc as e:
            print("⏸️ Hết hạn mức Gemini – dừng:", str(e)[:150], flush=True); break
        except Exception as e:
            print("⚠️ File %s lỗi, để lượt sau: %s" % (fid[:12], str(e)[:150]), flush=True); continue
        ma_cot = tab.col_values(c["Mã câu"] + 1)
        dong_cua = {v.strip(): i + 1 for i, v in enumerate(ma_cot) if i > 0 and v.strip()}
        kt_cot = tab.col_values(c["Kiểm tra"] + 1)
        cap = []
        for x in ds:
            dong = dong_cua.get(x["ma"])
            if not dong: continue
            kt_cu = kt_cot[dong - 1] if dong - 1 < len(kt_cot) else ""
            if DAU in kt_cu: continue                                   # có chạy khác vừa cứu: bỏ qua
            kq = ket.get(x["ma"])
            col = lambda t, dh=dong: D.gspread_a1(c[t] + 1, dh)
            if kq and kq[0]:
                nd, pa = kq[0]
                kt = "%s | [%s %s: tách lại từ file gốc, đủ phương án – chờ duyệt lại 5 tầng] (lí do cũ: %s)" % (kt_cu, DAU, ngay, x["ly_do"])
                cap += [{"range": col("Nội dung"), "values": [[nd]]}, {"range": col("Phương án"), "values": [[pa]]},
                        {"range": col("Trạng thái duyệt"), "values": [[D.TT["CHUA"]]]}, {"range": col("Kiểm tra"), "values": [[kt[:45000]]]}]
                thong_ke["cuu"] += 1
            else:
                ly = kq[1] if kq else "không mở được file gốc"
                cap.append({"range": col("Kiểm tra"), "values": [[("%s | [%s %s: không cứu được – %s]" % (kt_cu, DAU, ngay, ly))[:45000]]]})
                thong_ke["khong"] += 1
        if cap: tab.batch_update(cap, value_input_option="RAW")
        da_lam += len(ds)
        print("📄 File %s: %d câu xử lí" % (fid[:12], len(ds)), flush=True)
    print("📊 Cứu Loại: %d câu trả về 'Chưa duyệt' (sẽ qua 5 tầng), %d câu không cứu được." % (thong_ke["cuu"], thong_ke["khong"]))
    if Q: Q.ghi_sheet(kho)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if Q: Q.ghi_sheet()
        raise
