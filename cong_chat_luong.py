"""
cong_chat_luong.py – CỔNG CHẤT LƯỢNG CHUNG cho mọi đầu ra do AI soạn (đề cương, đề kiểm tra, chuyên đề, đề HSG, phiếu).

Đề do AI soạn không có hướng dẫn chấm gốc, nên bằng chứng tin cậy là HAI LỜI GIẢI ĐỘC LẬP:
  • Bằng chứng 1: đáp án của chính agent soạn đề (bảng đáp án / hướng dẫn giải).
  • Bằng chứng 2: một model KHÁC, KHÔNG được xem đáp án, giải lại bằng code Python (công cụ chạy code của Gemini).
Một câu ĐẠT khi hai bằng chứng khớp, câu nhiều lựa chọn có ĐÚNG MỘT phương án đúng và đơn vị cùng thứ nguyên.
Các tầng:
  1. Luật bằng code (0 lượt): Đúng/Sai đúng 2 Đúng + 2 Sai, đủ 4 phương án, đáp án đúng dạng, công thức $…$ đóng mở đủ.
  2. Tách bảng đáp án của agent thành dữ liệu (1 lượt, model nhẹ).
  3. Giải độc lập bằng code (≈1 lượt / 12 câu, model chính khác model soạn).
  4. So khớp + thứ nguyên (pint) + phương án nhiễu vô lí (0 lượt).
Trả về báo cáo Markdown, bảng tóm tắt và đoạn "bằng chứng" để bước rà soát của agent tự sửa câu lệch.
"""
import json, re

from duyet_cau import loai_dang, tach_ds, khop, chuan, cung_thu_nguyen, json_cuoi, lay_so

try:
    import groq_xuong as G
except Exception:                       # thiếu groq_xuong: cổng vẫn chạy như cũ
    G = None

LO = 12
SAI_SO = 0.02
MAX_TRANH_CHAP = 30        # [Hàng 5] bảo vệ hạn mức Groq miễn phí


def _goi(goi_gemini, he, nguoi, co_code, cac_model):
    text, model = goi_gemini(he, nguoi, co_code, cac_model)
    return text, model


def tach_dap_an(goi_gemini, de_md, dap_an_md, cac_model):
    """Model nhẹ: lấy danh sách câu (số, dạng, số phương án) từ đề và đáp án tương ứng từ phần đáp án."""
    nhe = [m for m in cac_model if "lite" in m] + [m for m in cac_model if "lite" not in m]
    he = "Bạn trích xuất dữ liệu chính xác, không giải bài, không bình luận. Chỉ trả về một khối ```json```."
    nguoi = ("Từ ĐỀ và PHẦN ĐÁP ÁN dưới đây, lập danh sách MỌI câu hỏi theo đúng thứ tự trong đề. Mỗi phần tử: "
             "{\"so\": \"I.3\" (Phần La Mã + số câu), \"dang\": \"TN|DS|TLN|TL\", \"so_phuong_an\": 4, "
             "\"dap_an\": \"B\" | \"a) Đ, b) S, c) Đ, d) S\" | \"2,5\" | \"đáp số cuối\", \"don_vi\": \"m/s\"}. "
             "dap_an lấy NGUYÊN theo phần đáp án (không tự giải); không có thì để rỗng.\n\n=== ĐỀ ===\n" + de_md[:60000] +
             "\n\n=== PHẦN ĐÁP ÁN ===\n" + dap_an_md[:60000])
    text, _ = _goi(goi_gemini, he, nguoi, False, nhe)
    ds = json_cuoi(text) or []
    return [x for x in ds if isinstance(x, dict) and x.get("so")]


def giai_doc_lap(goi_gemini, de_md, cac_cau, cac_model, model_soan):
    thu_tu = sorted([m for m in cac_model if m != model_soan], key=lambda m: "lite" in m) or list(cac_model)
    he = ("Bạn là học sinh giỏi Vật lí, giải ĐỘC LẬP (không có đáp án). BẮT BUỘC dùng công cụ chạy code Python cho mọi phép tính số. "
          "Cuối cùng trả về MỘT khối ```json``` là mảng kết quả.")
    kq, model = {}, ""
    for k in range(0, len(cac_cau), LO):
        lo = [c["so"] for c in cac_cau[k:k + LO]]
        nguoi = ("Trong ĐỀ dưới đây, hãy giải các câu: " + ", ".join(lo) + ".\n"
                 "Nhiều lựa chọn: xét LẦN LƯỢT A, B, C, D; ghi mọi phương án đúng vào phuong_an_dung. nhieu_vo_li CHỈ ghi phương án "
                 "VÔ LÍ VỀ VẬT LÍ (sai thứ nguyên / đơn vị, giá trị âm cho đại lượng luôn dương, vượt giới hạn vật lí như hiệu suất > 100%, "
                 "v > c); phương án chỉ đơn giản là SAI thì KHÔNG ghi – phần lớn các câu nhieu_vo_li để mảng rỗng. Đúng/sai: xét từng ý a, b, c, d. "
                 "Trả lời ngắn / tự luận: đáp số cuối (số, dấu chấm thập phân) và đơn vị SI.\n"
                 "Mỗi phần tử: {\"so\": \"I.3\", \"phuong_an_dung\": [\"B\"], \"nhieu_vo_li\": [], "
                 "\"y_ds\": {\"a\": \"Đ\", \"b\": \"S\", \"c\": \"Đ\", \"d\": \"S\"}, \"dap_so\": 2.02, \"don_vi\": \"s\", "
                 "\"tu_tin\": \"cao|vừa|thấp\"}\n\n=== ĐỀ ===\n" + de_md[:60000])
        text, model = _goi(goi_gemini, he, nguoi, True, thu_tu)
        for g in json_cuoi(text) or []:
            if isinstance(g, dict) and g.get("so"):
                kq[str(g["so"]).strip()] = g
    return kq, model


def _dap_an_may(loai, g):
    if not g: return "", []
    if loai == "TN":
        pa = sorted({str(p).strip().upper()[:1] for p in (g.get("phuong_an_dung") or []) if str(p).strip()})
        return (pa[0] if len(pa) == 1 else ""), pa
    if loai == "DS":
        y = g.get("y_ds") or {}
        if len(y) != 4: return "", []
        return ", ".join("%s) %s" % (k, "Đ" if str(y.get(k, "")).upper()[:1] in ("Đ", "D") else "S") for k in "abcd"), []
    v = g.get("dap_so")
    try: return ("%g" % float(v)).replace(".", ","), []
    except (TypeError, ValueError): return "", []


def lay_noi_dung_cau(goi_gemini, de_md, ds_so, cac_model):
    """[Hàng 5] Model nhẹ chép NGUYÊN VĂN câu + phương án của vài câu tranh chấp (để gửi cho Groq)."""
    nhe = [m for m in cac_model if "lite" in m] + [m for m in cac_model if "lite" not in m]
    he = "Bạn chép nguyên văn, không giải, không sửa. Chỉ trả về một khối ```json```."
    nguoi = ("Từ ĐỀ dưới đây, chép NGUYÊN VĂN nội dung và các phương án của các câu: " + ", ".join(ds_so) + ". "
             "Mỗi phần tử: {\"so\": \"I.3\", \"noi_dung\": \"...\", \"phuong_an\": \"A. ... B. ... C. ... D. ...\"} "
             "(đúng/sai: phuong_an chứa các ý a), b), c), d)). Giữ nguyên công thức $…$.\n\n=== ĐỀ ===\n" + de_md[:60000])
    text, _ = _goi(goi_gemini, he, nguoi, False, nhe)
    return {str(x["so"]).strip(): x for x in (json_cuoi(text) or []) if isinstance(x, dict) and x.get("so")}


def phan_xu_groq(goi_gemini, de_md, tranh_chap, cac_model):
    """[Hàng 5] tranh_chap: [{so, loai}] → ({so: đáp án Groq}, tên model). Công tắc tắt / thiếu khoá / lỗi → ({}, '')."""
    if not tranh_chap or not (G and G.san_sang()):
        return {}, ""
    try:
        nd = lay_noi_dung_cau(goi_gemini, de_md, [t["so"] for t in tranh_chap], cac_model)
        ds = [{"ma": t["so"], "dang": t["loai"], "noi_dung": nd[t["so"]]["noi_dung"],
               "phuong_an": nd[t["so"]].get("phuong_an") or ""}
              for t in tranh_chap if t["so"] in nd and str(nd[t["so"]].get("noi_dung") or "").strip()]
        return G.giai_lo(ds)
    except Exception as e:
        print("  [Cổng chất lượng] Vòng Groq lỗi, bỏ qua: %s" % str(e)[:100], flush=True)
        return {}, ""


def kiem_dinh(goi_gemini, de_md, dap_an_md, cac_model, model_soan):
    """Chạy cổng. Trả về (bao_cao_md, tom_tat dict, bang_chung_cho_ra_soat str)."""
    loi_chung = []
    if (de_md + dap_an_md).count("$") % 2:
        loi_chung.append("Công thức $…$ không đóng mở đủ ở đâu đó trong đề / đáp án")
    cac_cau = tach_dap_an(goi_gemini, de_md, dap_an_md, cac_model)
    if not cac_cau:
        return "### Báo cáo kiểm định (cổng chất lượng)\n\nChưa tách được danh sách câu – không kiểm định được lượt này.\n", \
               {"tong": 0}, ""
    may, model_giai = giai_doc_lap(goi_gemini, de_md, cac_cau, cac_model, model_soan)
    # [Hàng 5] danh sách câu tranh chấp (agent lệch máy hoặc máy chưa giải) → Groq phân xử
    tranh_chap = []
    for c in cac_cau:
        so_, loai_ = str(c["so"]).strip(), loai_dang(c.get("dang"))
        da_ = chuan(loai_, c.get("dap_an"))
        m_, pa_ = _dap_an_may(loai_, may.get(so_))
        if not da_ or (loai_ == "TL" and lay_so(da_) != lay_so(da_)) or (loai_ == "TN" and len(pa_) > 1):
            continue                               # lay_so(x) != lay_so(x) là cách kiểm tra NaN (câu định tính)
        if not m_ or not khop(loai_, m_, da_, SAI_SO):
            tranh_chap.append({"so": so_, "loai": loai_})
    groq_kq, model_groq = phan_xu_groq(goi_gemini, de_md, tranh_chap[:MAX_TRANH_CHAP], cac_model)
    dong = ["### Báo cáo kiểm định (cổng chất lượng)", "",
            "Mỗi câu được một model khác (%s), không xem đáp án, giải lại bằng code. Câu **đạt** khi đáp án của agent và lời giải "
            "bằng code khớp nhau, đúng một phương án đúng, đơn vị cùng thứ nguyên." % model_giai.replace("gemini-", ""), "",
            "| Câu | Đáp án của agent | Máy giải bằng code | Kết luận |", "|---|---|---|---|"]
    tt = {"tong": 0, "dat": 0, "lech": 0, "nhieu_dap_an": 0, "chua_giai": 0, "luat": 0, "dinh_tinh": 0, "goi_y": 0,
          "groq_xac_nhan": 0, "nen_sua": 0}
    bang_chung = []
    for c in cac_cau:
        so, loai = str(c["so"]).strip(), loai_dang(c.get("dang"))
        da = chuan(loai, c.get("dap_an"))
        g = may.get(so)
        m, pa = _dap_an_may(loai, g)
        tt["tong"] += 1
        van_de = []
        # tầng 1: luật
        if loai == "DS" and len(tach_ds(da)) == 4 and sum(1 for v in tach_ds(da).values() if v == "Đ") != 2:
            van_de.append("Đúng/Sai không phải 2 Đúng + 2 Sai")
        if loai == "TN" and int(c.get("so_phuong_an") or 4) < 4:
            van_de.append("thiếu phương án")
        if not da:
            van_de.append("agent chưa ghi đáp án")
        if van_de: tt["luat"] += 1
        # [29/10/2026] câu tự luận có đáp án bằng LỜI (không có số): không đem so với đáp số của máy
        if loai == "TL" and da and lay_so(da) != lay_so(da):
            tt["dinh_tinh"] += 1
            dong.append("| %s | %s | %s | %s |" % (so, da, "–", "ℹ️ câu định tính – máy không đối chiếu bằng số, thầy xem" +
                                                 ("; " + "; ".join(van_de) if van_de else "")))
            bang_chung.append("- Câu %s: câu định tính, cần thầy xem" % so)
            continue
        # tầng 3–4: so khớp
        if loai == "TN" and len(pa) > 1:
            tt["nhieu_dap_an"] += 1
            van_de.append("máy thấy %d phương án cùng đúng (%s)" % (len(pa), ", ".join(pa)))
        goi_y = ""                                 # [29/10/2026] nhiễu dễ loại chỉ là GỢI Ý chất lượng, không làm câu "không đạt"
        if g and g.get("nhieu_vo_li"):
            goi_y = "ℹ️ gợi ý: phương án %s có thể quá dễ loại" % ", ".join(map(str, g["nhieu_vo_li"]))
            tt["goi_y"] += 1
        if not m:
            if not (loai == "TN" and len(pa) > 1):
                tt["chua_giai"] += 1
                van_de.append("máy chưa giải được")
        elif da and not khop(loai, m, da, SAI_SO):
            tt["lech"] += 1
            van_de.append("LỆCH: agent %s, máy %s" % (da, m))
            so_d = sum(1 for v in tach_ds(m).values() if v == "Đ") if loai == "DS" else 2
            if so_d != 2:
                van_de.append("nếu máy đúng thì câu có %d Đúng – %d Sai, phải sửa cả nội dung ý cho đủ 2Đ–2S" % (so_d, 4 - so_d))
        if loai in ("TLN", "TL") and g and g.get("don_vi") and c.get("don_vi"):
            if cung_thu_nguyen(g["don_vi"], c["don_vi"]) is False:
                van_de.append("đơn vị không cùng thứ nguyên (%s / %s)" % (c["don_vi"], g["don_vi"]))
        # [Hàng 5] vòng 2: Groq (khác hãng, không xem đáp án) phân xử khi agent và máy lệch / máy chưa giải
        if so in groq_kq and da:
            gd = chuan(loai, groq_kq[so])
            if khop(loai, gd, da, SAI_SO):                       # Groq cùng ý agent
                if not m:
                    van_de = [v for v in van_de if v != "máy chưa giải được"]
                    tt["chua_giai"] -= 1
                    tt["groq_xac_nhan"] += 1
                    goi_y = (goi_y + " · " if goi_y else "") + "ℹ️ Groq xác nhận (Groq không chạy code, thầy lưu ý)"
                else:
                    van_de = [v for v in van_de if not v.startswith("nếu máy đúng")]
                    van_de.append("Groq đồng ý với agent, máy lệch → giữ đáp án, thầy xem")
            elif m and khop(loai, gd, m, SAI_SO):                # Groq cùng ý máy → 2/3 khác agent
                tt["nen_sua"] += 1
                van_de.append("NÊN SỬA: Groq và máy cùng đáp án %s (agent %s)" % (m, da))
                bang_chung.append("- Câu %s: SỬA đáp án từ %s thành %s (2/3 nguồn độc lập đồng ý); "
                                  "sửa kèm lời giải và nếu là Đúng/Sai thì giữ 2Đ–2S" % (so, da, m))
            else:
                van_de.append("3 nguồn cho 3 đáp án khác nhau (agent %s, máy %s, Groq %s) → thầy xem" % (da, m or "–", gd))
        if g and str(g.get("tu_tin", "")).lower().startswith("thấp"):
            van_de.append("máy không chắc chắn")
        dat = not van_de
        tt["dat"] += 1 if dat else 0
        dong.append("| %s | %s | %s | %s |" % (so, da or "–", m or (", ".join(pa) if pa else "–"),
                                              ("✔ đạt" if dat else "⚠️ " + "; ".join(van_de)) + (" · " + goi_y if goi_y else "")))
        if not dat:
            bang_chung.append("- Câu %s: %s" % (so, "; ".join(van_de)))
    dong += ["", "**Kết quả: %d/%d câu đạt 2 bằng chứng độc lập**; %d câu lệch đáp án, %d câu nhiều phương án đúng, "
             "%d câu máy chưa giải được, %d câu vi phạm luật hình thức%s." % (tt["dat"], tt["tong"], tt["lech"], tt["nhieu_dap_an"],
                                                                       tt["chua_giai"], tt["luat"],
                                                                       (", %d câu định tính (thầy xem)" % tt["dinh_tinh"] if tt["dinh_tinh"] else "") +
                                                                       (", %d gợi ý về phương án nhiễu" % tt["goi_y"] if tt["goi_y"] else ""))]
    if model_groq:
        dong.append("Vòng 2 (%s): %d câu được Groq xác nhận, %d câu nên sửa đáp án." % (model_groq, tt["groq_xac_nhan"], tt["nen_sua"]))
    if loi_chung: dong.append("Lưu ý chung: " + "; ".join(loi_chung))
    return "\n".join(dong) + "\n", tt, "\n".join(bang_chung)
