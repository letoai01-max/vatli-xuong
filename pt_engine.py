"""
pt_engine.py – LÕI PHÂN TÍCH ĐỀ TN THPT (xưởng Python). Bốn khối đầu của "Python Analysis Engine":

  1. Document Reader      doc_tai_lieu()       Drive → PDF/ảnh (Word đổi PDF, .zip giải nén, PDF lớn nén/chia trang) – dùng lại doc_de.py
  2. Question Parser      tach_cau()           Gemini đọc thẳng tệp → từng câu có cấu trúc (phần, dạng, nội dung LaTeX, phương án, đáp án trong đề, hình)
  3. Physics Analyzer +   phan_tich_kien_thuc() chương/chuyên đề, kiến thức, năng lực, dạng bài, số bước, thời gian, YCCĐ
     Cognitive Classifier phan_loai_nhan_thuc() NB/TH/VD/VDC lượt 2 độc lập (model khác) để phát hiện chỗ phân loại không ổn định
  4. Physics Solver       giai_may()           giải độc lập bằng code (Gemini code_execution) + Groq phân xử → đối chiếu đáp án trong đề

Khối thứ sáu (Exam Evaluator – ma trận, thống kê) nằm ở pt_danh_gia.py và KHÔNG gọi AI.
Mọi lời gọi AI đi qua doc_de.goi_gemini (xoay khoá, hạn mức, ghi Quota_SuDung). Hết hạn mức → doc_de.HetHanMuc nổi lên cho phan_tich_de.py xử lí.
"""
import base64, json, re

import doc_de as X
import cong_chat_luong as CCL
from duyet_cau import loai_dang, chuan, khop, lay_so, tach_ds
import pt_danh_muc as DM

NHOM_TOI_DA_BYTE = 15 * 1024 * 1024          # tổng dung lượng gửi inline mỗi lượt gọi (Gemini giới hạn ≈ 20 MB cả yêu cầu)
LO_PHAN_TICH = 14                            # số câu mỗi lượt phân tích
LO_PHAN_LOAI = 28


class QuaDai(Exception):
    """Gemini hết chỗ trả lời (MAX_TOKENS) – nơi gọi chia nhỏ rồi gọi lại."""


# ====================================================================================== tiện ích gọi Gemini
def goi_json(parts, schema, ds_model, max_tokens=40000, nhiet=0.2):
    payload = {"contents": [{"role": "user", "parts": parts}],
               "generationConfig": {"responseMimeType": "application/json", "responseSchema": schema,
                                    "temperature": nhiet, "maxOutputTokens": max_tokens}}
    data, model = X.goi_gemini(payload, ds_model)
    cand = (data.get("candidates") or [None])[0]
    if not cand:
        raise RuntimeError("Gemini không trả kết quả: " + json.dumps(data)[:200])
    text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []) if not p.get("thought"))
    if cand.get("finishReason") == "MAX_TOKENS":
        raise QuaDai()
    try:
        return json.loads(text), model
    except ValueError:
        raise QuaDai() if len(text) > max_tokens * 2 else RuntimeError("Gemini trả JSON hỏng (finishReason %s)" % cand.get("finishReason"))


def goi_gemini_chu(he, nguoi, co_code, cac_model):
    """Chữ ký cong_chat_luong cần: (hệ thống, lời nhắc, có chạy code?, danh sách model) → (chữ, model)."""
    payload = {"systemInstruction": {"parts": [{"text": he}]}, "contents": [{"role": "user", "parts": [{"text": nguoi}]}],
               "generationConfig": {"temperature": 0.2, "maxOutputTokens": 30000}}
    if co_code:
        payload["tools"] = [{"code_execution": {}}]
    data, model = X.goi_gemini(payload, cac_model)
    cand = (data.get("candidates") or [{}])[0]
    return "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []) if not p.get("thought")), model


# ====================================================================================== 1. DOCUMENT READER
def doc_tai_lieu(drive, ds_tep, nhat_ky=print):
    """ds_tep: [{id, ten}] → (các phần [{data, mime, ten, ghi_chu_phan?}], danh sách cảnh báo)."""
    phan, canh_bao = [], []
    for t in ds_tep:
        try:
            kq = X.chuan_bi_tep_day_du(drive, t["id"])
        except Exception as e:
            canh_bao.append("Không đọc được tệp \"%s\": %s" % (t.get("ten", t["id"]), str(e)[:150]))
            continue
        if kq.get("bo_qua"):
            canh_bao.append("Bỏ qua \"%s\": %s" % (t.get("ten", t["id"]), kq["bo_qua"]))
            continue
        for p in kq["phan"]:
            p.setdefault("ten", t.get("ten", ""))
            phan.append(p)
        nhat_ky("Đọc tệp", "%s → %d phần, %.1f MB" % (t.get("ten", t["id"]), len(kq["phan"]), sum(len(p["data"]) for p in kq["phan"]) / 1048576))
    return phan, canh_bao


def _nhom(phan):
    """Gộp các phần nhỏ (đề + đáp án là 2 tệp riêng) vào cùng một lượt gọi nếu tổng không quá NHOM_TOI_DA_BYTE."""
    nhom, hien, tong = [], [], 0
    for p in phan:
        if hien and tong + len(p["data"]) > NHOM_TOI_DA_BYTE:
            nhom.append(hien); hien, tong = [], 0
        hien.append(p); tong += len(p["data"])
    if hien:
        nhom.append(hien)
    return nhom


# ====================================================================================== 2. QUESTION PARSER
SCHEMA_TACH = {
    "type": "OBJECT",
    "properties": {
        "la_de_vat_li": {"type": "BOOLEAN"},
        "thong_tin": {"type": "OBJECT", "properties": {
            "ten_de": {"type": "STRING"}, "ky_thi": {"type": "STRING"}, "nam": {"type": "STRING"}, "don_vi": {"type": "STRING"},
            "ma_de": {"type": "STRING"}, "thoi_gian_phut": {"type": "INTEGER"}, "co_dap_an_trong_tep": {"type": "BOOLEAN"}}},
        "con_cau_sau": {"type": "BOOLEAN"},
        "cau_hoi": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "phan": {"type": "INTEGER"}, "so_cau": {"type": "INTEGER"},
            "dang": {"type": "STRING", "enum": ["TN", "DS", "TLN", "TL"]},
            "noi_dung": {"type": "STRING"}, "phuong_an": {"type": "ARRAY", "items": {"type": "STRING"}},
            "dap_an": {"type": "STRING"}, "co_hinh": {"type": "BOOLEAN"}, "mo_ta_hinh": {"type": "STRING"},
            "diem": {"type": "STRING"}},
            "required": ["phan", "so_cau", "dang", "noi_dung", "co_hinh"]}}},
    "required": ["la_de_vat_li", "cau_hoi"]}


def _loi_nhac_tach(ghi_chu_phan, pham_vi, cau_truc):
    cach = ("các câu hỏi thứ %d đến thứ %d theo thứ tự xuất hiện (câu đầu tiên là thứ 1); ghi con_cau_sau = true nếu sau câu thứ %d còn câu hỏi"
            % (pham_vi[0], pham_vi[1], pham_vi[1])) if pham_vi else "TẤT CẢ câu hỏi"
    return ((ghi_chu_phan + "\n") if ghi_chu_phan else "") + (
        "Bạn là giáo viên Vật lí THPT. Các tệp đính kèm là một đề thi / đề kiểm tra Vật lí (có thể kèm đáp án, hướng dẫn chấm ở tệp riêng hoặc trang cuối).\n\n"
        "NHIỆM VỤ: tách " + cach + ", mỗi câu một phần tử, đúng thứ tự trong đề, KHÔNG tự giải, KHÔNG bỏ sót.\n"
        " - phan: 1 = nhiều lựa chọn, 2 = đúng/sai, 3 = trả lời ngắn, 4 = tự luận (theo tiêu đề PHẦN trong đề; không có tiêu đề thì suy từ dạng câu).\n"
        " - so_cau: số thứ tự câu TRONG PHẦN ấy như đề ghi (Câu 1…18 của Phần I; Phần II lại bắt đầu từ Câu 1; nếu đề đánh số liên tục cả đề thì giữ số của đề và ghi đúng phan).\n"
        " - dang: TN (4 phương án A–D), DS (4 ý a, b, c, d), TLN (đáp số), TL (tự luận).\n"
        " - noi_dung: chép NGUYÊN VĂN đề bài (bỏ tiền tố 'Câu n.'); công thức viết LaTeX trong $...$; hình vẽ, đồ thị, bảng thay bằng [Hình: mô tả đủ dữ kiện để giải] "
        "(đọc số liệu trên hình ghi vào mô tả); bảng số liệu chép thành bảng chữ.\n"
        " - phuong_an: mỗi phương án MỘT chuỗi có nhãn ('A. …', 'B. …' hoặc 'a) …', 'b) …'); câu TLN/TL để mảng rỗng.\n"
        " - dap_an: CHỈ lấy từ đáp án / hướng dẫn chấm CÓ TRONG tệp; TN ghi một chữ 'B'; DS ghi 'a) Đ, b) S, c) Đ, d) S'; TLN ghi số như đáp án (ví dụ '2,5'). "
        "Không có đáp án trong tệp thì để rỗng, tuyệt đối không tự suy ra.\n"
        " - co_hinh: true nếu câu cần hình vẽ, đồ thị, sơ đồ hay bảng số liệu mới giải được; mo_ta_hinh mô tả ngắn.\n"
        " - diem: điểm của câu nếu đề ghi, không có để rỗng.\n"
        "Ngoài ra ghi thong_tin (tên đề, kì thi, năm, đơn vị, mã đề, thời gian làm bài nếu có) và co_dap_an_trong_tep.\n"
        "Cấu trúc tham chiếu (chỉ để bạn đối chiếu, không bịa thêm câu): " +
        "; ".join("Phần %s: %d câu %s" % (k, v["so_cau"], v["dang"]) for k, v in cau_truc.items()) + ".")


def tach_cau(phan, cau_truc, ds_model, nhat_ky=print):
    """Trả (thong_tin, ds_cau thô, model, cảnh báo). Mỗi nhóm tệp một lượt gọi; hết chỗ trả lời thì chia theo khoảng câu."""
    thong_tin, cau, canh_bao, model = {}, {}, [], ""
    la_vat_li = False
    for k, nhom in enumerate(_nhom(phan), 1):
        parts = [{"inline_data": {"mime_type": p["mime"], "data": base64.b64encode(p["data"]).decode()}} for p in nhom]
        ghi_chu = " ".join(p.get("ghi_chu_phan", "") for p in nhom).strip()
        pham_vi, tiep = None, True
        while tiep:
            try:
                kq, model = goi_json(parts + [{"text": _loi_nhac_tach(ghi_chu, pham_vi, cau_truc)}], SCHEMA_TACH, ds_model, max_tokens=60000)
            except QuaDai:
                pham_vi = pham_vi or (1, 14)
                if pham_vi[1] - pham_vi[0] < 6:
                    raise RuntimeError("Gemini không tách được ngay cả khi chia nhỏ khoảng câu")
                pham_vi = (pham_vi[0], pham_vi[0] + (pham_vi[1] - pham_vi[0]) // 2)
                nhat_ky("Tách câu", "đề dài – chia khoảng câu %d–%d" % pham_vi)
                continue
            la_vat_li = la_vat_li or bool(kq.get("la_de_vat_li"))
            for ten, v in (kq.get("thong_tin") or {}).items():
                if v not in (None, "", 0) and not thong_tin.get(ten):
                    thong_tin[ten] = v
            for c in kq.get("cau_hoi") or []:
                kh = (int(c.get("phan") or 0), int(c.get("so_cau") or 0))
                if kh not in cau or len(str(c.get("noi_dung", ""))) > len(str(cau[kh].get("noi_dung", ""))):
                    cau[kh] = c
            if pham_vi and kq.get("con_cau_sau"):
                pham_vi = (pham_vi[1] + 1, pham_vi[1] + 14)
            else:
                tiep = False
        nhat_ky("Tách câu", "nhóm %d: đã có %d câu" % (k, len(cau)))
    if not la_vat_li:
        canh_bao.append("Mô hình cho rằng tệp không phải đề Vật lí – kiểm tra lại tệp đã tải lên.")
    ds = chuan_hoa_cau(list(cau.values()), cau_truc, canh_bao)
    return thong_tin, ds, model, canh_bao


def chuan_hoa_cau(cac, cau_truc, canh_bao):
    """Gán mã câu 'I.3', suy phần từ dạng khi thiếu, sắp xếp, kiểm tra số câu theo cấu trúc."""
    ra = []
    phan_cua_dang = {"TN": 1, "DS": 2, "TLN": 3, "TL": 4}
    for c in cac:
        d = c.get("dang") or "TN"
        p = int(c.get("phan") or 0) or phan_cua_dang.get(d, 1)
        c["phan"], c["dang"] = p, d
        c["so_cau"] = int(c.get("so_cau") or 0)
        c["noi_dung"] = str(c.get("noi_dung") or "").strip()
        c["phuong_an"] = [str(x).strip() for x in (c.get("phuong_an") or []) if str(x).strip()]
        c["dap_an_de"] = chuan(loai_dang(d), c.get("dap_an")) if str(c.get("dap_an") or "").strip() else ""
        c["co_hinh"] = bool(c.get("co_hinh"))
        ra.append(c)
    ra.sort(key=lambda c: (c["phan"], c["so_cau"]))
    for i, c in enumerate(ra):
        c["stt"] = i + 1
        c["ma"] = "%s.%d" % (DM.LA_MA.get(c["phan"], str(c["phan"])), c["so_cau"])
    for k, v in cau_truc.items():
        co = sum(1 for c in ra if str(c["phan"]) == k)
        if co != int(v["so_cau"]):
            canh_bao.append("Phần %s: tách được %d câu, cấu trúc tham chiếu là %d câu – kiểm tra tách câu." % (DM.LA_MA.get(int(k), k), co, v["so_cau"]))
    ma = [c["ma"] for c in ra]
    for m in {m for m in ma if ma.count(m) > 1}:
        canh_bao.append("Trùng mã câu %s – có thể tách nhầm / đề đánh số lặp." % m)
    for c in ra:
        if c["dang"] == "TN" and len(c["phuong_an"]) != 4:
            canh_bao.append("Câu %s (TN) có %d phương án (cần 4)." % (c["ma"], len(c["phuong_an"])))
        if c["dang"] == "DS" and len(c["phuong_an"]) != 4:
            canh_bao.append("Câu %s (Đúng/Sai) có %d ý (cần 4)." % (c["ma"], len(c["phuong_an"])))
    return ra


# ====================================================================================== 3. PHYSICS ANALYZER + COGNITIVE CLASSIFIER
SCHEMA_PHAN_TICH = {
    "type": "OBJECT", "properties": {"cau": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
        "ma": {"type": "STRING"}, "ma_chuong": {"type": "STRING"}, "chuyen_de": {"type": "STRING"},
        "kien_thuc": {"type": "ARRAY", "items": {"type": "STRING"}},
        "nang_luc": {"type": "STRING"}, "dang_bai": {"type": "STRING"},
        "muc_do": {"type": "STRING", "enum": list(DM.MUC)}, "ly_do_muc_do": {"type": "STRING"},
        "y_ds": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "y": {"type": "STRING"}, "muc_do": {"type": "STRING", "enum": list(DM.MUC)}, "kien_thuc": {"type": "STRING"}}}},
        "so_buoc": {"type": "INTEGER"}, "thoi_gian_giay": {"type": "INTEGER"},
        "ti_le_dung_du_kien": {"type": "NUMBER"},
        "bay_thuong_gap": {"type": "STRING"}, "ma_yccd": {"type": "ARRAY", "items": {"type": "STRING"}},
        "ngoai_chuong_trinh": {"type": "BOOLEAN"}, "tu_tin": {"type": "STRING", "enum": ["cao", "vừa", "thấp"]}},
        "required": ["ma", "ma_chuong", "muc_do", "so_buoc", "thoi_gian_giay", "ti_le_dung_du_kien", "tu_tin"]}}},
    "required": ["cau"]}

SCHEMA_PHAN_LOAI = {
    "type": "OBJECT", "properties": {"cau": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
        "ma": {"type": "STRING"}, "muc_do": {"type": "STRING", "enum": list(DM.MUC)},
        "y_ds": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "y": {"type": "STRING"}, "muc_do": {"type": "STRING", "enum": list(DM.MUC)}}}}},
        "required": ["ma", "muc_do"]}}},
    "required": ["cau"]}


def _goi_cau(c):
    d = {"ma": c["ma"], "dang": c["dang"], "noi_dung": c["noi_dung"][:2500], "phuong_an": [p[:400] for p in c["phuong_an"]]}
    if c["co_hinh"]:
        d["hinh"] = (c.get("mo_ta_hinh") or "có hình")[:400]
    return d


def phan_tich_kien_thuc(ds_cau, danh_muc, yccd_van_ban, ds_model, nhat_ky=print, da_xong=None):
    """Phân tích từng câu (không cần tệp gốc). da_xong: {ma: kết quả} đã có từ lượt trước (HOAN) – bỏ qua. Trả {ma: kết quả}, model."""
    kq, model = dict(da_xong or {}), ""
    cho = [c for c in ds_cau if c["ma"] not in kq]
    ds_chuong = "\n".join("%s | lớp %s | %s" % (d["ma"], d["lop"] or "-", d["ten"]) for d in danh_muc)
    for k in range(0, len(cho), LO_PHAN_TICH):
        lo = cho[k:k + LO_PHAN_TICH]
        he = ("Bạn là tổ trưởng chuyên môn Vật lí THPT, phân tích câu hỏi của một đề thi tốt nghiệp THPT theo chương trình GDPT 2018 (sách Kết nối tri thức). "
              "Phân tích dựa trên NỘI DUNG và yêu cầu tư duy thật của câu, không dựa vào vị trí câu trong đề.\n\n" + DM.TIEU_CHI_MUC + "\n\n"
              "Với mỗi câu trả về:\n"
              " - ma (đúng như đầu vào), ma_chuong (CHỈ lấy trong danh mục chương bên dưới), chuyen_de (tên ngắn của chuyên đề / bài), kien_thuc (1–4 ý ngắn).\n"
              " - nang_luc: một trong " + " | ".join(DM.NANG_LUC) + ".\n"
              " - dang_bai: một trong " + " | ".join(DM.DANG_BAI) + ".\n"
              " - muc_do + ly_do_muc_do (≤ 200 kí tự, nêu số bước và kiến thức kết hợp). Câu Đúng/Sai: muc_do của cả câu = mức cao nhất trong 4 ý, "
              "đồng thời điền y_ds cho từng ý a–d.\n"
              " - so_buoc: số bước giải / lập luận tối thiểu. thoi_gian_giay: thời gian một học sinh khá cần để làm (đã gồm đọc đề).\n"
              " - ti_le_dung_du_kien: ước lượng 0–1 tỉ lệ học sinh cả nước làm đúng (chỉ là ước lượng của bạn, không phải số liệu thật).\n"
              " - bay_thuong_gap: lỗi / bẫy học sinh hay mắc (≤ 150 kí tự, có thể rỗng). ma_yccd: 0–3 mã từ danh sách YCCĐ, chỉ khi kiến thức thật sự nằm trong yêu cầu đó.\n"
              " - ngoai_chuong_trinh: true nếu kiến thức không thuộc nội dung cốt lõi GDPT 2018. tu_tin: mức chắc chắn về phân loại.\n\n"
              "DANH MỤC CHƯƠNG (mã | lớp | tên):\n" + ds_chuong +
              ("\n\nDANH SÁCH YCCĐ (mã | bài | yêu cầu):\n" + yccd_van_ban[:30000] if yccd_van_ban else ""))
        parts = [{"text": he + "\n\nCÁC CÂU CẦN PHÂN TÍCH:\n" + json.dumps([_goi_cau(c) for c in lo], ensure_ascii=False)}]
        try:
            ra, model = goi_json(parts, SCHEMA_PHAN_TICH, ds_model, max_tokens=30000)
        except QuaDai:
            if len(lo) == 1:
                raise RuntimeError("Phân tích câu %s quá dài" % lo[0]["ma"])
            nhat_ky("Phân tích", "lô quá dài – chia đôi")
            for nua in (lo[:len(lo) // 2], lo[len(lo) // 2:]):
                sub, model = phan_tich_kien_thuc(nua, danh_muc, yccd_van_ban, ds_model, nhat_ky, kq)
                kq.update(sub)
            continue
        for g in ra.get("cau") or []:
            if g.get("ma"):
                kq[str(g["ma"]).strip()] = g
        nhat_ky("Phân tích kiến thức", "%d/%d câu" % (len(kq), len(ds_cau)))
    return kq, model


def phan_loai_nhan_thuc(ds_cau, ds_model_khac, nhat_ky=print):
    """Lượt 2 ĐỘC LẬP (model khác, chỉ thấy đề, không thấy kết quả lượt 1): chỉ phân loại mức nhận thức. Trả {ma: {muc_do, y_ds}}."""
    kq = {}
    for k in range(0, len(ds_cau), LO_PHAN_LOAI):
        lo = ds_cau[k:k + LO_PHAN_LOAI]
        he = ("Bạn là giáo viên Vật lí giàu kinh nghiệm ra đề thi tốt nghiệp THPT. Phân loại mức nhận thức của từng câu.\n\n" + DM.TIEU_CHI_MUC +
              "\n\nTrả về ma (đúng như đầu vào) và muc_do; câu Đúng/Sai: muc_do = mức cao nhất trong 4 ý và điền y_ds cho từng ý a–d.\n\nCÁC CÂU:\n" +
              json.dumps([_goi_cau(c) for c in lo], ensure_ascii=False))
        ra, _ = goi_json([{"text": he}], SCHEMA_PHAN_LOAI, ds_model_khac, max_tokens=12000, nhiet=0.3)
        for g in ra.get("cau") or []:
            if g.get("ma"):
                kq[str(g["ma"]).strip()] = g
    nhat_ky("Phân loại lượt 2", "%d câu" % len(kq))
    return kq


# ====================================================================================== 4. PHYSICS SOLVER
def dung_de_md(ds_cau):
    dong, phan = [], None
    for c in ds_cau:
        if c["phan"] != phan:
            phan = c["phan"]
            dong += ["", "=== PHẦN %s ===" % DM.LA_MA.get(phan, phan)]
        dong.append("Câu %s: %s" % (c["ma"], c["noi_dung"]) + (("\n[Hình: %s]" % c["mo_ta_hinh"]) if c["co_hinh"] and c.get("mo_ta_hinh") and "[Hình" not in c["noi_dung"] else ""))
        dong += c["phuong_an"]
    return "\n".join(dong).strip()


def giai_may(ds_cau, ds_model, model_soan, dung_groq=True, nhat_ky=print):
    """
    Giải độc lập bằng code rồi đối chiếu với đáp án trong đề (nếu có). Mỗi câu trả về:
      da_de · da_may · da_groq · ket_luan · da_chot · do_tin_cay · ghi_chu
    ket_luan: KHỚP | CHỈ_CÓ_MÁY | LỆCH_NÊN_SỬA | LỆCH_CẦN_XEM | NHIỀU_ĐÁP_ÁN | KHÔNG_GIẢI_ĐƯỢC | ĐỊNH_TÍNH
    """
    de_md = dung_de_md(ds_cau)
    cac_cau = [{"so": c["ma"], "dang": c["dang"]} for c in ds_cau]
    nhat_ky("Giải bằng code", "%d câu, model %s" % (len(cac_cau), ", ".join(ds_model)))
    may, model_giai = CCL.giai_doc_lap(goi_gemini_chu, de_md, cac_cau, ds_model, model_soan)
    kq, tranh_chap = {}, []
    for c in ds_cau:
        loai, da = loai_dang(c["dang"]), c["dap_an_de"]
        g = may.get(c["ma"])
        m, pa = CCL._dap_an_may(loai, g)
        r = {"da_de": da, "da_may": m, "da_groq": "", "ket_luan": "", "da_chot": "", "do_tin_cay": "thấp", "ghi_chu": [],
             "tu_tin_may": str((g or {}).get("tu_tin", "")), "don_vi_may": str((g or {}).get("don_vi", ""))}
        if loai == "TN" and len(pa) > 1:
            r["ket_luan"] = "NHIỀU_ĐÁP_ÁN"; r["ghi_chu"].append("máy thấy %d phương án cùng đúng (%s)" % (len(pa), ", ".join(pa)))
        elif loai == "TL" and da and lay_so(da) != lay_so(da):
            r["ket_luan"] = "ĐỊNH_TÍNH"; r["da_chot"] = da
        elif g and g.get("nhieu_vo_li"):
            r["ghi_chu"].append("phương án nhiễu có thể quá dễ loại: %s" % ", ".join(map(str, g["nhieu_vo_li"])))
        if not r["ket_luan"]:
            if da and m and khop(loai, m, da):
                r.update(ket_luan="KHỚP", da_chot=da, do_tin_cay="cao")
            elif not da and m:
                r.update(ket_luan="CHỈ_CÓ_MÁY", da_chot=m, do_tin_cay="vừa")
                tranh_chap.append({"so": c["ma"], "loai": loai})          # không có đáp án đề → Groq làm nguồn thứ hai
            elif da and m:
                r["ket_luan"] = "LỆCH_CẦN_XEM"; r["ghi_chu"].append("đề ghi %s, máy giải %s" % (da, m)); tranh_chap.append({"so": c["ma"], "loai": loai})
            elif da and not m:
                r["ket_luan"] = "KHÔNG_GIẢI_ĐƯỢC"; r["da_chot"] = da; r["do_tin_cay"] = "vừa"; r["ghi_chu"].append("máy chưa giải được, giữ đáp án trong đề")
                tranh_chap.append({"so": c["ma"], "loai": loai})
            else:
                r["ket_luan"] = "KHÔNG_GIẢI_ĐƯỢC"; r["ghi_chu"].append("không có đáp án trong đề và máy chưa giải được")
        if r["tu_tin_may"].lower().startswith("thấp"):
            r["ghi_chu"].append("máy tự đánh giá độ tin cậy thấp")
            if r["do_tin_cay"] == "cao": r["do_tin_cay"] = "vừa"
        if c["co_hinh"]:
            r["ghi_chu"].append("câu có hình: máy chỉ giải theo mô tả hình, cần đối chiếu hình gốc")
            if r["do_tin_cay"] == "cao": r["do_tin_cay"] = "vừa"
        kq[c["ma"]] = r
    # vòng Groq (khác hãng, không chạy code, không xem đáp án) chỉ cho câu tranh chấp / chỉ có máy
    groq, model_groq = ({}, "")
    if dung_groq and tranh_chap:
        groq, model_groq = CCL.phan_xu_groq(goi_gemini_chu, de_md, tranh_chap[:CCL.MAX_TRANH_CHAP], ds_model)
        nhat_ky("Groq phân xử", "%d/%d câu có phiếu" % (len(groq), len(tranh_chap)))
    for c in ds_cau:
        r, loai = kq[c["ma"]], loai_dang(c["dang"])
        gq = groq.get(c["ma"])
        if not gq:
            continue
        r["da_groq"] = chuan(loai, gq)
        if r["ket_luan"] == "CHỈ_CÓ_MÁY":
            if khop(loai, r["da_groq"], r["da_may"]): r["do_tin_cay"] = "cao"
            else: r["do_tin_cay"] = "thấp"; r["ghi_chu"].append("Groq (%s) khác máy (%s)" % (r["da_groq"], r["da_may"]))
        elif r["ket_luan"] == "LỆCH_CẦN_XEM":
            if khop(loai, r["da_groq"], r["da_may"]):
                r["ket_luan"] = "LỆCH_NÊN_SỬA"; r["da_chot"] = r["da_may"]; r["do_tin_cay"] = "vừa"
                r["ghi_chu"].append("Groq và máy cùng đáp án %s, khác đáp án trong đề (%s)" % (r["da_may"], r["da_de"]))
            elif khop(loai, r["da_groq"], r["da_de"]):
                r["ghi_chu"].append("Groq đồng ý với đáp án trong đề; máy lệch → giữ đáp án đề"); r["da_chot"] = r["da_de"]; r["do_tin_cay"] = "vừa"
            else:
                r["ghi_chu"].append("3 nguồn cho 3 đáp án khác nhau (đề %s, máy %s, Groq %s)" % (r["da_de"], r["da_may"], r["da_groq"]))
        elif r["ket_luan"] == "KHÔNG_GIẢI_ĐƯỢC" and r["da_de"] and khop(loai, r["da_groq"], r["da_de"]):
            r["do_tin_cay"] = "vừa"; r["ghi_chu"].append("Groq xác nhận đáp án trong đề (Groq không chạy code)")
    for r in kq.values():
        r["ghi_chu"] = "; ".join(r["ghi_chu"])
    return kq, {"giai": model_giai, "groq": model_groq}
