"""
tao_de.py (v2 – KHUNG) – XƯỞNG TẠO ĐỀ THEO GIAO THỨC "GÓI VIỆC v2" (xem giao_thuc.py).

Việc đã làm đủ ở khung này: đọc gói v2, ghi tiến độ/nhật kí, soạn từng phần theo ĐẶC TẢ + CHỈ BÁO của Apps Script, chuẩn hoá đề
($…$), kiểm công thức, xuất 2 tệp Word (HS, GV) vào tệp rỗng thầy đã tạo sẵn, hết hạn mức Gemini → HOAN (làm tiếp sau).
ĐÃ NỐI (bước 4–5): kiểm cấu trúc + độ dài + hình + thực tiễn + chỉ báo và tự sửa (port kiemTraDeThi / agentKiemTraVaTuSuaDe);
cổng chất lượng cong_chat_luong (giải lại độc lập bằng code + Groq, soạn lại câu lệch); vẽ hình bằng code (ve_hinh);
kiểm trùng với Ngân hàng câu hỏi Kho chung (xuat_de.tinh_chi_muc); ghi hạn mức (quota_xuong); báo Telegram (thong_bao).
Mô-đun tuỳ chọn nạp lỗi → bỏ qua bước đó và ghi cảnh báo, không làm hỏng việc chính.
Đã port thêm: cấu trúc theo khối (lớp 12), đáp án Phần III vừa phiếu, Đúng/Sai 2–2 (kiểm + quy định gắn vào chỉ dẫn hệ thống), nhật kí câu mẫu Kho chung.
Câu mẫu Kho chung (ô B24) và YCCĐ Kho chung (ô B25) do Apps Script xử lí khi dựng gói (khoiTaoTrangThaiAgent), xưởng nhận sẵn qua trangThai0.
Đã thêm: Google Search cho phần có câu thực tiễn (soan_phan; lỗi Search → tự soạn lại không Search như Mã.gs; tắt bằng TIM_KIEM_GOOGLE=0).
Đã thêm: thẩm định khớp chỉ báo bằng AI (kiemDinhKhopChiBaoBangAI), ảnh thực tế (Wikimedia → Openverse → Google CSE nếu có khoá → AI tạo ảnh,
như layAnhChoHinh), hình vẽ lỗi thì thử web/AI, mẫu Word ô B4 (tuỳ chọn, DUNG_MAU_B4=1).
Đã thêm: làm sạch nhãn thừa trong câu (lamSachDeThi), tuỳ chọn gói (cheDo=nhanh, xacMinh, hinhAnh).
Chưa có: phiếu làm lại (sua_cau / tron_de).
Gói cũ (phienBan 1, chỉ có các ô B…) → chạy bản cũ đã đổi tên thành tao_de_v1.py (giữ làm dự phòng).
Biến môi trường: GOOGLE_CREDENTIALS / đăng nhập WIF, GEMINI_API_KEY…, GOI_ID, KQ_ID.
"""
import base64
import json
import os
import re
import shutil
import sys
import tempfile

import requests

import chuan_de as CD
import doc_de as X                      # goi_gemini (xoay khoá, model từ tab CauHinh), HetHanMuc, doc_cau_hinh
import giao_thuc as GT
import xuat_de_v2 as XD


def _nap(ten):
    try:
        return __import__(ten)
    except Exception as e:                      # thiếu thư viện / lỗi mô-đun: bỏ bước đó, không làm hỏng việc chính
        print("⚠️ Không nạp được %s: %s" % (ten, str(e)[:120]), flush=True)
        return None


CCL = _nap("cong_chat_luong")    # cổng chất lượng: giải độc lập bằng code + Groq
KD = _nap("kiem_dinh_de")        # goi_gemini đúng chữ ký của cong_chat_luong
VH = _nap("ve_hinh")             # vẽ hình bằng code (matplotlib) + Gemini kiểm lại
KT = _nap("xuat_de")             # chỉ mục chống trùng Ngân hàng câu hỏi
Q = _nap("quota_xuong")          # ghi lượt dùng Gemini/Groq vào Quota_SuDung
TB = _nap("thong_bao")           # Telegram (tuỳ chọn)

CHO_HOAN_PHUT = {"phut": 3, "ngay": 8}   # giống ChanVongLap.gs: hết lượt theo phút chờ 3', theo ngày chờ 8'

HE_THONG = (
    "Bạn là AI Agent Khảo thí môn Vật lí THPT (Chương trình GDPT 2018, Kết nối tri thức với cuộc sống). "
    "Soạn đề TUÂN THỦ CHÍNH XÁC DANH MỤC CÂU HỎI được giao. Đáp án phải đúng về vật lí, số liệu tính toán chính xác. "
    "Công thức viết bằng LaTeX trong dấu $…$ (ví dụ $\\frac{1}{2}mv^2$, $T = 2\\pi\\sqrt{\\frac{l}{g}}$); đơn vị trong \\text{ }, "
    "ví dụ $5\\text{ cm}$, $2\\text{ μF}$; số thập phân dùng dấu phẩy trong chữ, dấu chấm trong dapAn Phần III. "
    "CHỈ trả về MỘT đối tượng JSON đúng mẫu, không bình luận, không ```.")

MAU = {
    1: '{"phan1": [{"cauHoi": "...", "A": "...", "B": "...", "C": "...", "D": "...", "dapAn": "A"}]}',
    2: '{"phan2": [{"cauHoi": "nội dung dẫn...", "A": "ý a", "B": "ý b", "C": "ý c", "D": "ý d", "dapAn": "a) Đ, b) S, c) Đ, d) S"}]}',
    3: '{"phan3": [{"cauHoi": "...", "dapAn": "12.5"}]}',
    4: '{"phan4": [{"cauHoi": "đề bài...", "dapAn": "- Bước 1...\\n- Bước 2...\\n=> Đáp số: ... kèm đơn vị"}]}',
}
LUAT = {
    1: "Mỗi câu có đúng một đáp án đúng; bốn phương án A, B, C, D ngắn gọn, phương án nhiễu hợp lí.",
    2: "Mỗi câu có đúng 4 ý a), b), c), d) (trường A, B, C, D), trong đó ĐÚNG 2 ý Đúng và 2 ý Sai; vị trí hai ý Đúng thay đổi giữa các câu.",
    3: "Trường dapAn là MỘT SỐ (ví dụ 15.2), không đơn vị, không chữ cái.",
    4: "Trường dapAn là lời giải mỗi bước MỘT DÒNG (ngăn cách bằng \\n, mỗi dòng bắt đầu '- '), dòng cuối '=> Đáp số: …' kèm đơn vị.",
}


def dung_danh_muc(t0, p):
    """Danh mục câu của một phần từ trangThai0.dm (đúng dữ liệu agent Apps Script dùng)."""
    dm = (t0.get("dm") or {}).get("p%d" % p) or []
    dong = []
    for i, m in enumerate(dm, 1):
        if p == 2:
            dong.append("Câu %d (4 ý a, b, c, d lần lượt theo):\n" % i + "\n".join("   ý %s: %s" % ("abcd"[k], y) for k, y in enumerate(m)))
        else:
            dong.append("Câu %d: %s" % (i, m))
    return "\n".join(dong)


_RE_ESC = re.compile(r'\\\\|\\(?=[bfnrt][a-z])|\\(?!["/bfnrtu\\]|u[0-9a-fA-F]{4})')


def _sua_escape(s):
    """Gemini hay trả LaTeX với MỘT dấu \\ (\\omega, \\frac, \\text) làm JSON sai/sai nghĩa: gấp đôi các dấu \\ không phải escape JSON hợp lệ;
    \\f \\t \\b \\r \\n đứng trước chữ thường (\\frac, \\text, \\beta, \\rho, \\nu) cũng là LaTeX. Cặp \\\\ đã đúng thì giữ nguyên."""
    return _RE_ESC.sub(lambda m: m.group(0) if m.group(0) == "\\\\" else "\\\\", s)


def doc_json(text):
    s = re.sub(r"```json|```", "", str(text or "")).strip()
    a, b = s.find("{"), s.rfind("}")
    chuoi = s[a:b + 1] if a != -1 and b > a else s
    try:
        return json.loads(chuoi)
    except json.JSONDecodeError as loi_goc:      # thường do LaTeX một dấu \\ hoặc xuống dòng thật trong chuỗi
        try:
            return json.loads(_sua_escape(chuoi), strict=False)
        except json.JSONDecodeError:
            raise loi_goc


TIM_KIEM_GOOGLE = os.environ.get("TIM_KIEM_GOOGLE", "1").strip().lower() not in ("0", "false", "no", "off", "tat")
LENH_TIM_KIEM = ("\n\nDÙNG GOOGLE SEARCH để lấy SỐ LIỆU THỰC TẾ (thông số thiết bị, hiện tượng, đại lượng đo được) đưa vào các câu thực tiễn nêu trên; "
                 "số liệu phải hợp lí và khớp đáp án. Sau khi tra cứu, CHỈ trả về MỘT đối tượng JSON đúng mẫu, không bình luận, không ```.")


def _doc_text(data):
    cand = (data.get("candidates") or [{}])[0]
    return "".join(x.get("text", "") for x in (cand.get("content") or {}).get("parts", []) if not x.get("thought"))


def soan_phan(goi, p, cac_model, ghi_chu_loi="", ph=None):
    """Soạn một phần. Phần có câu thực tiễn dùng Google Search (như callGemini(prompt, true) của Mã.gs);
    Search lỗi (không phải hết hạn mức) → soạn lại KHÔNG Search và ghi cảnh báo, giống agentSoanPhan."""
    ch, t0 = goi["cauHinh"], goi["trangThai0"]
    n = t0["yc"]["p%d" % p]
    co_tt = bool((t0.get("vtThucTien") or {}).get("p%d" % p))

    def dung_payload(tim_kiem):
        nguoi = ("Soạn riêng PHẦN %d của đề kiểm tra môn %s lớp %s (%s).\n\n=== DANH MỤC CÂU HỎI BẮT BUỘC ===\n%s\n\n"
                 "ĐÚNG %d câu. %s\n\nNGUỒN CÂU HỎI THAM KHẢO TỪ GIÁO VIÊN:\n%s\n\nMẫu JSON:\n%s%s%s") % (
            p, ch.get("subject", "Vật lí"), ch.get("grade"), ch.get("textbook", ""), dung_danh_muc(t0, p), n, LUAT[p] + quy_dinh_phan(p),
            (t0.get("nganHang") or "")[:6000], MAU[p] + lenh_bo_sung(t0, p), LENH_TIM_KIEM if tim_kiem else "",
            ("\n\nLƯU Ý SỬA LỖI LẦN TRƯỚC: " + ghi_chu_loi) if ghi_chu_loi else "")
        gen = {"temperature": 0.3, "maxOutputTokens": 32768}
        if not tim_kiem:
            gen["responseMimeType"] = "application/json"      # Gemini không cho vừa Search vừa ép JSON → khi Search chỉ ép bằng lời
        pl = {"contents": [{"role": "user", "parts": [{"text": nguoi}]}], "systemInstruction": {"parts": [{"text": he_thong_cho(p == 2)}]},
              "generationConfig": gen}
        if tim_kiem:
            pl["tools"] = [{"google_search": {}}]
        return pl

    def lay_mang(data):
        kq = doc_json(_doc_text(data))
        mang = kq.get("phan%d" % p) if isinstance(kq, dict) else kq
        return mang if isinstance(mang, list) else []

    if TIM_KIEM_GOOGLE and co_tt:
        try:
            data, model = X.goi_gemini(dung_payload(True), cac_model)
            mang = lay_mang(data)
            if mang:
                if ph:
                    ph.ghi_nhat_ky("soạn phần %d" % p, "có dùng Google Search (câu thực tiễn)")
                return mang, model
            raise ValueError("Search trả về JSON rỗng")
        except X.HetHanMuc:
            raise
        except Exception as e:
            if ph:
                ph.them_canh_bao("Phần %d: Google Search lỗi (%s) → soạn không Search, số liệu thực tiễn do AI tự đặt." % (p, str(e)[:100]))
            else:
                print("⚠️ Search lỗi phần %d: %s" % (p, str(e)[:100]), flush=True)
    data, model = X.goi_gemini(dung_payload(False), cac_model)
    try:
        return lay_mang(data), model
    except ValueError as e:                      # JSONDecodeError ⊂ ValueError: JSON hỏng không sửa được → gọi lại đúng một lần
        if ph:
            ph.them_canh_bao("Phần %d: Gemini trả JSON hỏng (%s) → soạn lại một lần." % (p, str(e)[:80]))
        data, model = X.goi_gemini(dung_payload(False), cac_model)
        return lay_mang(data), model


# =====================================================================================================================
# BƯỚC 4/5 – KIỂM SOÁT CHẤT LƯỢNG (port từ Mã.gs: kiemTraDeThi, kiemTraDoDaiDe, kiemTraHinhAnhDe, kiemTraThucTienDe,
# kiemTraKhopChiBao, agentKiemTraVaTuSuaDe) + nối cong_chat_luong, ve_hinh, xuat_de (chỉ mục trùng), quota_xuong, thong_bao
# =====================================================================================================================
GIOI_HAN_DO_DAI = {"p1CauHoi": 200, "p1PhuongAn": 100, "p2Dan": 280, "p2Y": 200, "p3": 280, "p4": 380}   # = Mã.gs
SO_VONG_SUA_CAU_TRUC = 2                                                   # = SO_VONG_SUA_TOI_DA của agentKiemTraVaTuSuaDe
SO_VONG_SUA_DAP_AN = int(os.environ.get("SO_VONG_SUA_DAP_AN", "1"))        # số lần soạn lại câu lệch sau cổng chất lượng
TOI_DA_HINH_VE = int(os.environ.get("TOI_DA_HINH_VE", "8"))      # hình vẽ + ảnh thực tế mỗi lượt (Apps Script: SO_ANH_TAO_TOI_DA = 6)
SO_VONG_SUA_CHI_BAO = 1                                              # số lần soạn lại câu chưa khớp chỉ báo
MODEL_TAO_ANH = [m.strip() for m in os.environ.get("MODEL_TAO_ANH", "gemini-2.5-flash-image").split(",") if m.strip()]
DUNG_MAU_B4 = os.environ.get("DUNG_MAU_B4", "0").strip().lower() in ("1", "true", "yes", "on")
UA_WEB = {"User-Agent": "DeThiVatLi/1.0 (GitHub Actions; xuong Python)"}
LA_MA = {"I": 1, "II": 2, "III": 3, "IV": 4}
MO_TA_THUC_TIEN = {
    1: "câu hỏi gắn ngữ cảnh THỰC TIỄN (hiện tượng đời sống, thiết bị, kĩ thuật, tự nhiên), chỉ ở mức Nhận biết hoặc Thông hiểu đúng như mức độ của chỉ báo",
    2: "câu chùm xây dựng trên MỘT ngữ cảnh thực tiễn hoặc mô phỏng kĩ thuật thống nhất (ô tô qua gờ giảm tốc, đồ thị dao động địa chấn/sóng âm, thông số một thiết bị gia dụng...)",
    3: "bài toán gắn tình huống THỰC TẾ ở mức Thông hiểu: số liệu sát thực tế, đáp án là một con số",
    4: "bài toán tự luận gắn tình huống THỰC TẾ: số liệu hợp lí với thực tế, lời giải bám sát tình huống",
}
RE_CAU_CAN_HINH = re.compile(
    r"((cho|dựa\s+vào|từ|trên|theo|quan\s+sát)\s+đồ\s*thị|như\s+hình|hình\s*vẽ|hình\s+(bên|dưới|sau|trên)|"
    r"đồ\s*thị\s+(bên|dưới|sau|trên|ở\s+hình|như\s+hình|trong\s+hình|hình)|bảng\s+(bên|dưới|sau|trên)|"
    r"bảng\s+số\s*liệu\s+(sau|dưới|bên)|theo\s+bảng|cho\s+(trong|ở|bởi)\s+bảng)", re.I)
QUY_DINH_HINH = (
    ' HÌNH/BẢNG/ĐỒ THỊ (trường tuỳ chọn "hinhAnh"): CHỈ thêm khi chỉ báo hoặc câu hỏi THỰC SỰ cần; cả đề tối đa khoảng 6. '
    'Có "hinhAnh" thì câu hỏi viết "như hình vẽ", "đồ thị bên", "bảng dưới đây", KHÔNG chép lại số liệu vào câu hỏi; số liệu phải khớp đáp án. '
    'Bốn dạng: {"loai":"bang","chuThich":"Bảng 1. ...","tieuDeCot":["t (s)","v (m/s)"],"dong":[["0","2"],["1","4"]]} (≤6 cột, ≤10 dòng) · '
    '{"loai":"dothi","kieuDoThi":"line|scatter|bar","chuThich":"Hình 1. ...","nhanTrucX":"t (s)","nhanTrucY":"v (m/s)","duLieu":[{"ten":"Vật 1","diem":[[0,2],[4,10]]}]} · '
    '{"loai":"hinhve","chuThich":"Hình 2. ...","moTa":"mô tả rất chi tiết để vẽ: các vật, vị trí, kí hiệu, chiều mũi tên, nhãn chữ ngắn"} (sơ đồ mạch điện, hình thí nghiệm, hình biểu diễn lực) · '
    '{"loai":"anhthuc","chuThich":"Hình 3. ...","tuKhoaTimKiem":"2-5 từ khoá tiếng Anh","moTa":"ảnh cần có"}.')


def quy_dinh_phan(p):
    G = GIOI_HAN_DO_DAI
    dai = {1: " Độ dài: câu hỏi tối đa %d ký tự, mỗi phương án tối đa %d ký tự." % (G["p1CauHoi"], G["p1PhuongAn"]),
           2: " Độ dài: câu dẫn tối đa %d ký tự, mỗi ý tối đa %d ký tự." % (G["p2Dan"], G["p2Y"]),
           3: " Độ dài: đề bài tối đa %d ký tự, chỉ nêu dữ kiện cần để tính." % G["p3"],
           4: " Độ dài: đề bài tối đa %d ký tự." % G["p4"]}[p]
    return dai + QUY_DINH_HINH


def lenh_bo_sung(t0, p):
    """Chỉ báo hạt nhân + câu thực tiễn của phần p (đúng dữ liệu Apps Script gửi sang)."""
    s = []
    ma = (t0.get("dsMa") or {}).get("p%d" % p)
    if ma and any((m if isinstance(m, str) else any(m)) for m in ma):
        if p == 2:
            s.append('Mỗi câu thêm trường "maChiBaoY": mảng mã chỉ báo của ý a, b, c, d, ĐÚNG theo thứ tự câu: %s.' % json.dumps(ma, ensure_ascii=False))
        else:
            s.append('Mỗi câu thêm trường "maChiBao" (VD "CB12") ĐÚNG theo thứ tự câu: %s.' % json.dumps(ma, ensure_ascii=False))
    tt = (t0.get("vtThucTien") or {}).get("p%d" % p) or []
    if tt:
        s.append('Câu số %s (đếm từ 1) PHẢI là %s và ghi "thucTien": true.' % (", ".join(str(i + 1) for i in tt), MO_TA_THUC_TIEN[p]))
    k = lenh_theo_khoi(t0, p)
    if k:
        s.append(k)
    return ("\n\n" + "\n".join(s)) if s else ""


# ------------------------------------------------------------------ THEO KHỐI + QUY ĐỊNH TẠO ĐỀ (port Mã.gs: CAU_TRUC_DE_THEO_KHOI, kiemTraTheoKhoi,
# taoLenhTheoKhoi; DungSai22.gs: ds22KiemTra_; ChucNang.gs: QTD_QUY_DINH)
CAU_TRUC_DE_THEO_KHOI = {"12": {"p1": 18, "yDS": 16, "p3": 6, "p4": 0, "toiDaKiTuTLN": 4}}   # = Mã.gs (lớp 10, 11 giữ nguyên)
QTD_DUNG_SAI = (
    "QUY ĐỊNH BẮT BUỘC VỀ CÂU TRẮC NGHIỆM ĐÚNG/SAI: mỗi câu có đúng 4 ý a), b), c), d), trong đó ĐÚNG 2 ý có đáp án ĐÚNG "
    "và ĐÚNG 2 ý có đáp án SAI (không được 3–1, 4–0, 1–3, 0–4). Vị trí 2 ý đúng phải thay đổi giữa các câu, không cố định "
    "(ví dụ câu 1: a, c đúng; câu 2: b, d đúng; câu 3: a, d đúng…). Ý sai phải sai rõ ràng về kiến thức hoặc số liệu, không sai vì chữ nghĩa mập mờ. "
    "Trước khi trả lời, đếm lại từng câu Đúng/Sai: đủ 2 Đúng và 2 Sai thì mới được giữ; bảng đáp án phải khớp đúng 2 Đ và 2 S mỗi câu.")


def he_thong_cho(co_dung_sai):
    """HE_THONG + quy định Đúng/Sai 2–2 khi lệnh có nhắc câu Đúng/Sai (như qtdGanQuyDinh_ của ChucNang.gs)."""
    return HE_THONG + ("\n\n" + QTD_DUNG_SAI if co_dung_sai else "")


def cau_truc_khoi(t0):
    return CAU_TRUC_DE_THEO_KHOI.get(str(t0.get("_khoi", "")))


def lenh_theo_khoi(t0, p):
    """p = 0: toàn đề; 1..4: chỉ phần đó (như taoLenhTheoKhoi)."""
    ct = cau_truc_khoi(t0)
    if not ct:
        return ""
    dong = []
    if not p and ct["p4"] == 0:
        dong.append('ĐỀ LỚP %s THEO CẤU TRÚC ĐỀ THI TỐT NGHIỆP THPT: chỉ có Phần I (TNNLC), Phần II (Đúng/Sai), Phần III (Trả lời ngắn); KHÔNG có Phần IV tự luận, trường "phan4" là mảng rỗng [].' % t0.get("_khoi"))
    if not p or p == 3:
        dong.append('PHẦN III (phiếu trả lời ngắn TN THPT): mỗi đáp án là MỘT SỐ có TỐI ĐA %d KÍ TỰ, tính cả dấu trừ và dấu phẩy thập phân (VD: 12,5; -1,2; 0,25; 1250). '
                    'Đề bài phải nêu rõ đơn vị của kết quả và yêu cầu làm tròn (VD: "làm tròn kết quả đến hàng phần mười") để đáp án vừa %d kí tự; trường "dapAn" ghi dấu chấm thập phân.' % (ct["toiDaKiTuTLN"], ct["toiDaKiTuTLN"]))
    if not p or p == 2:
        dong.append("PHẦN II: mỗi câu gồm một ngữ cảnh/tình huống chung và 4 ý a, b, c, d xoay quanh ngữ cảnh đó, đúng kiểu câu Đúng/Sai của đề TN THPT.")
    return ("=== CẤU TRÚC ĐỀ LỚP %s (BẮT BUỘC) ===\n- " % t0.get("_khoi") + "\n- ".join(dong)) if dong else ""


def kiem_theo_khoi(de, t0):
    """kiemTraTheoKhoi: đáp án Phần III vừa phiếu (lớp 12) + mỗi câu Đúng/Sai đúng 2 Đúng – 2 Sai (ds22KiemTra_)."""
    loi, ct = [], cau_truc_khoi(t0)
    if ct:
        for i, c in enumerate(de.get("phan3") or [], 1):
            so = re.sub(r"\s", "", str(c.get("dapAn") if c.get("dapAn") is not None else "")).replace(".", ",", 1)
            if so and len(so) > ct["toiDaKiTuTLN"]:
                loi.append('Phần 3 câu %d: đáp án "%s" có %d kí tự, phiếu trả lời ngắn chỉ ghi tối đa %d kí tự; sửa đề (đổi đơn vị hoặc yêu cầu làm tròn) để đáp án vừa %d kí tự.'
                           % (i, so, len(so), ct["toiDaKiTuTLN"], ct["toiDaKiTuTLN"]))
    for i, c in enumerate(de.get("phan2") or [], 1):
        y = dict(re.findall(r"([a-d])\)\s*(Đ|S)", str(c.get("dapAn") or "")))
        if len(y) != 4:
            continue                                  # thiếu ý: kiem_cau_truc đã báo
        so_d = sum(1 for k in "abcd" if y[k] == "Đ")
        if so_d != 2:
            loi.append('Phần 2 câu %d: câu Đúng/Sai đang có %d ý Đúng và %d ý Sai ("%s"), quy định bắt buộc ĐÚNG 2 ý Đúng và 2 ý Sai. '
                       'Sửa NỘI DUNG ý (không chỉ đổi đáp án) để đủ 2 Đúng – 2 Sai, ý sai phải sai rõ ràng về kiến thức hoặc số liệu.' % (i, so_d, 4 - so_d, str(c.get("dapAn")).strip()))
    return loi


def canh_bao_so_cau_khoi(t0, ph):
    """kiemTraSoCauTheoKhoi: cảnh báo (không chặn) khi số câu của đặc tả lệch cấu trúc đề của khối."""
    ct = cau_truc_khoi(t0)
    if not ct:
        return
    yc, so_y = t0["yc"], sum(len(n or []) for n in ((t0.get("dm") or {}).get("p2") or []))
    lech = []
    if yc["p1"] != ct["p1"]: lech.append("Phần I có %d câu (cần %d)" % (yc["p1"], ct["p1"]))
    if so_y != ct["yDS"]: lech.append("Phần II có %d ý Đ/S (cần %d ý = %d câu)" % (so_y, ct["yDS"], ct["yDS"] // 4))
    if yc["p3"] != ct["p3"]: lech.append("Phần III có %d câu (cần %d)" % (yc["p3"], ct["p3"]))
    if yc["p4"] != ct["p4"]: lech.append("Phần IV có %d câu tự luận (cần %d)" % (yc["p4"], ct["p4"]))
    if lech:
        ph.them_canh_bao("Đặc tả lệch cấu trúc đề lớp %s: %s." % (t0.get("_khoi"), "; ".join(lech)))


def ghi_cau_mau(de, ph):
    """ghiNhatKyCauMau: câu nào phát triển từ câu mẫu nào của Kho chung."""
    ds = ["Phần %d câu %d ← %s" % (p, i, c["cauMau"]) for p in (1, 2, 3, 4) for i, c in enumerate(de.get("phan%d" % p) or [], 1) if c.get("cauMau")]
    if ds:
        ph.ghi_nhat_ky("câu phát triển từ Kho chung", "; ".join(ds)[:380])


# ------------------------------------------------------------------ kiểm tra bằng code (0 lượt Gemini)
def _rong(v):
    return v is None or str(v).strip() == ""


def lam_sach(v, la_lua_chon=False):
    t = str(v if v is not None else "").replace("\t", " ")
    t = re.sub(r"(?:Chỉ\s*báo\s*)?\[\s*CB\d+\s*\]\s*(?:\([^)]*\))?\s*[:.\-]?\s*", "", t, flags=re.I)
    t = re.sub(r"\[[^\[\]]*(?:CHỦ\s*ĐỀ|Bài\s*\d+|Chương\s*\d+)[^\[\]]*\]\s*[-:.]?\s*", "", t, flags=re.I)
    t = re.sub(r"\(\s*Mức\s*(?:biet|hieu|vanDung|biết|hiểu|vận dụng)\s*\)\s*[-:.]?\s*", "", t, flags=re.I)
    t = re.sub(r"^\s*(?:[A-Da-d]\s*[.)]\s+)+", "", t) if la_lua_chon else re.sub(r"^\s*(?:Câu\s*\d+\s*[:.)]\s*)+", "", t, flags=re.I)
    return t.strip()


def ma_cb(v):
    m = re.search(r"CB\d+", str(v if v is not None else "").upper())
    return m.group(0) if m else ""


def kiem_cau_truc(de, yc):
    loi = []
    for p in (1, 2, 3, 4):
        n = len(de.get("phan%d" % p) or [])
        if n != yc["p%d" % p]:
            loi.append("Phần %d đang có %d câu, Bản đặc tả yêu cầu ĐÚNG %d câu." % (p, n, yc["p%d" % p]))
    for i, c in enumerate(de.get("phan1") or [], 1):
        if _rong(c.get("cauHoi")):
            loi.append("Phần 1 câu %d: thiếu nội dung câu hỏi." % i)
        for k in "ABCD":
            if _rong(c.get(k)):
                loi.append("Phần 1 câu %d: thiếu phương án %s." % (i, k))
        if not re.fullmatch(r"[ABCD]", str(c.get("dapAn") or "").strip().upper()):
            loi.append("Phần 1 câu %d: đáp án phải là đúng một chữ A, B, C hoặc D." % i)
    for i, c in enumerate(de.get("phan2") or [], 1):
        if _rong(c.get("cauHoi")):
            loi.append("Phần 2 câu %d: thiếu nội dung dẫn." % i)
        for k in "ABCD":
            if _rong(c.get(k)):
                loi.append("Phần 2 câu %d: thiếu ý %s)." % (i, k.lower()))
        if len(re.findall(r"[a-d]\)\s*(?:Đúng|Sai|Đ|S)(?![A-Za-zÀ-ỹ])", str(c.get("dapAn") or ""), flags=re.I)) != 4:
            loi.append('Phần 2 câu %d: đáp án phải đủ 4 ý dạng "a) Đ, b) S, c) Đ, d) S".' % i)
    for i, c in enumerate(de.get("phan3") or [], 1):
        if _rong(c.get("cauHoi")):
            loi.append("Phần 3 câu %d: thiếu nội dung câu hỏi." % i)
        da = str(c.get("dapAn") if c.get("dapAn") is not None else "").strip()
        try:
            ok = bool(da) and re.fullmatch(r"[-+]?[\d.,\s]+", da) is not None and float(re.sub(r"\s", "", da).replace(",", ".")) == float(re.sub(r"\s", "", da).replace(",", "."))
        except ValueError:
            ok = False
        if not ok:
            loi.append('Phần 3 câu %d: đáp án phải là một con số (VD: 12.5), hiện là "%s".' % (i, da))
    for i, c in enumerate(de.get("phan4") or [], 1):
        if _rong(c.get("cauHoi")):
            loi.append("Phần 4 câu %d: thiếu đề bài." % i)
        dong = [x for x in re.split(r"\r?\n|\\n(?![a-zA-Z])", str(c.get("dapAn") or "")) if x.strip()]
        if len(dong) < 2:
            loi.append('Phần 4 câu %d: lời giải phải chia thành nhiều bước, mỗi bước một dòng (bắt đầu bằng "- "), dòng cuối "=> Đáp số: ...".' % i)
    return loi


def kiem_do_dai(de):
    G, loi = GIOI_HAN_DO_DAI, []
    dai = lambda v: len(lam_sach(v))
    dai_lc = lambda v: len(lam_sach(v, True))
    for i, c in enumerate(de.get("phan1") or [], 1):
        if dai(c.get("cauHoi")) > G["p1CauHoi"]:
            loi.append("Phần 1 câu %d: câu hỏi dài %d ký tự, cần rút gọn còn tối đa %d." % (i, dai(c.get("cauHoi")), G["p1CauHoi"]))
        for k in "ABCD":
            if dai_lc(c.get(k)) > G["p1PhuongAn"]:
                loi.append("Phần 1 câu %d: phương án %s dài %d ký tự, cần tối đa %d." % (i, k, dai_lc(c.get(k)), G["p1PhuongAn"]))
    for i, c in enumerate(de.get("phan2") or [], 1):
        if dai(c.get("cauHoi")) > G["p2Dan"]:
            loi.append("Phần 2 câu %d: câu dẫn dài %d ký tự, cần tối đa %d." % (i, dai(c.get("cauHoi")), G["p2Dan"]))
        for k in "ABCD":
            if dai_lc(c.get(k)) > G["p2Y"]:
                loi.append("Phần 2 câu %d: ý %s) dài %d ký tự, cần tối đa %d." % (i, k.lower(), dai_lc(c.get(k)), G["p2Y"]))
    for p, g in ((3, G["p3"]), (4, G["p4"])):
        for i, c in enumerate(de.get("phan%d" % p) or [], 1):
            if dai(c.get("cauHoi")) > g:
                loi.append("Phần %d câu %d: đề bài dài %d ký tự, cần tối đa %d." % (p, i, dai(c.get("cauHoi")), g))
    return loi


def kiem_hinh_anh(de):
    loi = []
    for p in (1, 2, 3, 4):
        for i, c in enumerate(de.get("phan%d" % p) or [], 1):
            h = CD.chuan_hinh_anh(c.get("hinhAnh"))
            nd = " ".join(str(c.get(k)) for k in ("cauHoi", "A", "B", "C", "D") if c.get(k))
            if h and not h.get("hopLe"):
                loi.append("Phần %d câu %d: trường hinhAnh (%s) thiếu dữ liệu: %s." % (p, i, h.get("loai"), h.get("lyDo")))
            elif not h and RE_CAU_CAN_HINH.search(nd):
                loi.append('Phần %d câu %d: câu hỏi nhắc tới hình/bảng/đồ thị nhưng chưa có trường "hinhAnh" hợp lệ (thêm hinhAnh hoặc viết lại câu không cần hình).' % (p, i))
    return loi


def kiem_thuc_tien(de, vt):
    loi = []
    for p in (1, 2, 3, 4):
        ds = de.get("phan%d" % p) or []
        for i in (vt or {}).get("p%d" % p) or []:
            if i < len(ds) and str(ds[i].get("thucTien")).lower() != "true":
                loi.append('Phần %d câu %d: phải là %s; soạn lại theo yêu cầu này và ghi "thucTien": true.' % (p, i + 1, MO_TA_THUC_TIEN[p]))
    return loi


def kiem_chi_bao(de, ds_ma):
    loi = []
    for p in (1, 3, 4):
        kv = ds_ma.get("p%d" % p) or []
        for i, c in enumerate(de.get("phan%d" % p) or []):
            if i < len(kv) and kv[i] and ma_cb(c.get("maChiBao")) != kv[i]:
                ht = ma_cb(c.get("maChiBao"))
                loi.append('Phần %d câu %d: phải đánh giá đúng chỉ báo [%s] và ghi "maChiBao": "%s" (hiện %s).' % (p, i + 1, kv[i], kv[i], ("là " + ht) if ht else "chưa ghi"))
    for i, c in enumerate(de.get("phan2") or []):
        kv = (ds_ma.get("p2") or [])[i] if i < len(ds_ma.get("p2") or []) else []
        ht = [ma_cb(x) for x in c.get("maChiBaoY") or []] if isinstance(c.get("maChiBaoY"), list) else []
        sai = ["ý %s) phải là [%s]" % ("abcd"[k], m) for k, m in enumerate(kv or []) if m and (ht[k] if k < len(ht) else "") != m]
        if sai:
            loi.append('Phần 2 câu %d: %s; ghi "maChiBaoY": %s.' % (i + 1, ", ".join(sai), json.dumps(kv, ensure_ascii=False)))
    return loi


def sap_xep_theo_ma(de, ds_ma):
    """Như sapXepTheoMaChiBao: AI trả đủ câu nhưng lệch thứ tự → xếp lại theo mã chỉ báo kỳ vọng."""
    for p in (1, 3, 4):
        ds, kv = de.get("phan%d" % p) or [], ds_ma.get("p%d" % p) or []
        if ds and len(ds) == len(kv) and all(kv) and sorted(ma_cb(c.get("maChiBao")) for c in ds) == sorted(kv):
            kho = {}
            for c in ds:
                kho.setdefault(ma_cb(c.get("maChiBao")), []).append(c)
            de["phan%d" % p] = [kho[m].pop(0) for m in kv]
    return de


def lam_sach_de(de):
    """lamSachDeThi: bỏ nhãn AI lỡ chép từ đặc tả ([CBxx], [CHỦ ĐỀ…/Bài…], (Mức…)), tiền tố "Câu n:" và nhãn "A."/"a)" bị lặp ở phương án."""
    for p in (1, 2, 3, 4):
        for c in de.get("phan%d" % p) or []:
            if isinstance(c, dict):
                if c.get("cauHoi") is not None:
                    c["cauHoi"] = lam_sach(c["cauHoi"])
                for k in "ABCD":
                    if c.get(k) is not None:
                        c[k] = lam_sach(c[k], True)
    return de


def chuan(de, t0):
    de, _ = CD.chuan_hoa_de(de if isinstance(de, dict) else {})
    lam_sach_de(de)
    if t0.get("dsMa"):
        sap_xep_theo_ma(de, t0["dsMa"])
    return de


def kiem_tra_day_du(de, t0):
    loi = kiem_cau_truc(de, t0["yc"]) + kiem_do_dai(de) + kiem_hinh_anh(de) + kiem_thuc_tien(de, t0.get("vtThucTien")) + CD.kiem_tra_latex(de) + kiem_theo_khoi(de, t0)
    if t0.get("dsMa"):
        loi += kiem_chi_bao(de, t0["dsMa"])
    return loi


# ------------------------------------------------------------------ Gemini: JSON
def goi_json_de(nguoi, cac_model, nhiet_do=0.3, quy_dinh_ds=True):
    payload = {"contents": [{"role": "user", "parts": [{"text": nguoi}]}], "systemInstruction": {"parts": [{"text": he_thong_cho(quy_dinh_ds)}]},
               "generationConfig": {"temperature": nhiet_do, "responseMimeType": "application/json", "maxOutputTokens": 32768}}
    data, model = X.goi_gemini(payload, cac_model)
    cand = (data.get("candidates") or [{}])[0]
    text = "".join(x.get("text", "") for x in (cand.get("content") or {}).get("parts", []) if not x.get("thought"))
    return doc_json(text), model


# ------------------------------------------------------------------ TỰ SỬA CẤU TRÚC (agentKiemTraVaTuSuaDe)
def tu_sua_cau_truc(goi, de, cac_model, ph):
    t0 = goi["trangThai0"]
    de = chuan(de, t0)
    ds = kiem_tra_day_du(de, t0)
    muc = "\n".join(("PHẦN %d:\n%s" % (p, dung_danh_muc(t0, p))) for p in (1, 2, 3, 4) if t0["yc"]["p%d" % p])[:12000]
    for vong in range(1, SO_VONG_SUA_CAU_TRUC + 1):
        if not ds:
            break
        ph.tien_do("tự sửa đề", None, "%d lỗi, vòng %d/%d" % (len(ds), vong, SO_VONG_SUA_CAU_TRUC))
        nguoi = ("Đề thi dạng JSON dưới đây KHÔNG ĐẠT kiểm tra đối chiếu với Bản đặc tả.\n\nDANH SÁCH LỖI CẦN SỬA:\n" + "\n".join("- " + l for l in ds[:60]) +
                 "\n\n=== DANH MỤC CÂU HỎI BẮT BUỘC ===\n" + muc +
                 "\n\nYÊU CẦU:\n- Sửa đúng các lỗi trên (bổ sung câu còn thiếu theo đúng danh mục, bỏ câu thừa), GIỮ NGUYÊN các câu đã đạt.\n"
                 + "".join("- Phần %d: %s%s\n" % (p, LUAT[p], quy_dinh_phan(p)) for p in (1, 2, 3, 4)) + "".join(lenh_bo_sung(t0, p) for p in (1, 2, 3, 4)) + ("\n\n" + lenh_theo_khoi(t0, 0) if cau_truc_khoi(t0) else "") +
                 '\n- Trả về TOÀN BỘ đề đã sửa, đúng cấu trúc JSON {"phan1": [...], "phan2": [...], "phan3": [...], "phan4": [...]}, không thêm lời giải thích.'
                 "\n\nĐỀ HIỆN TẠI:\n" + json.dumps(de, ensure_ascii=False))
        try:
            moi, _ = goi_json_de(nguoi, cac_model)
        except X.HetHanMuc:
            raise
        except Exception as e:
            ph.them_canh_bao("Tự sửa đề lỗi: %s" % str(e)[:120])
            break
        if not isinstance(moi, dict):
            break
        moi = chuan(moi, t0)
        ds_moi = kiem_tra_day_du(moi, t0)
        if len(ds_moi) < len(ds):
            de, ds = moi, ds_moi
        else:
            ph.ghi_nhat_ky("tự sửa đề", "bản sửa không tốt hơn (%d ≥ %d lỗi), giữ bản cũ" % (len(ds_moi), len(ds)))
            break
    if ds:
        ph.them_canh_bao("Đề còn %d lỗi cấu trúc sau khi tự sửa: %s" % (len(ds), " | ".join(ds[:4])))
    return de, ds


# ------------------------------------------------------------------ CỔNG CHẤT LƯỢNG (cong_chat_luong.py)
def _mo_ta_hinh(h):
    if not h or not h.get("hopLe"):
        return ""
    if h["loai"] == "bang":
        return "[Bảng] " + " | ".join(h["tieuDeCot"]) + "\n" + "\n".join(" | ".join(r) for r in h["dong"])
    if h["loai"] == "dothi":
        return "[Đồ thị %s, trục x: %s, trục y: %s] " % (h["kieuDoThi"], h["nhanTrucX"], h["nhanTrucY"]) + "; ".join(
            "%s: %s" % (s["ten"], s["diem"]) for s in h["duLieu"])
    return "[Hình: %s]" % (h.get("moTa") or h.get("tuKhoaTimKiem") or "")


def dung_md_kiem_dinh(de):
    """Đề và đáp án dạng chữ, mỗi câu mang số 'I.3', 'II.1'… cho cong_chat_luong.tach_dap_an."""
    de_md, da_md = [], []
    for p, ten in ((1, "I"), (2, "II"), (3, "III"), (4, "IV")):
        ds = de.get("phan%d" % p) or []
        if not ds:
            continue
        de_md.append("PHẦN %s" % ten)
        da_md.append("PHẦN %s" % ten)
        for i, c in enumerate(ds, 1):
            so = "%s.%d" % (ten, i)
            dong = ["Câu %s: %s" % (so, c.get("cauHoi", ""))]
            mt = _mo_ta_hinh(c.get("hinhAnh"))
            if mt:
                dong.append(mt)
            if p == 1:
                dong += ["%s. %s" % (k, c.get(k, "")) for k in "ABCD"]
            elif p == 2:
                dong += ["%s) %s" % (k.lower(), c.get(k, "")) for k in "ABCD"]
            de_md.append("\n".join(dong))
            da_md.append("Câu %s: %s" % (so, c.get("dapAn", "")))
    return "\n\n".join(de_md), "\n\n".join(da_md)


CAN_SUA = ("LỆCH", "NÊN SỬA", "phương án cùng đúng", "không phải 2 Đúng", "thiếu phương án", "không cùng thứ nguyên")
CHI_CANH_BAO = ("Groq đồng ý", "3 nguồn", "định tính")


def phan_loai_bang_chung(bang_chung):
    """→ (câu cần soạn lại [(phần, số, lý do)], câu chỉ cảnh báo [chuỗi])."""
    sua, canh = [], []
    for dong in str(bang_chung or "").splitlines():
        m = re.match(r"-\s*Câu\s+(IV|III|II|I)\.(\d+):\s*(.*)", dong.strip())
        if not m:
            continue
        p, i, ly = LA_MA[m.group(1)], int(m.group(2)), m.group(3)
        if any(k in ly for k in CHI_CANH_BAO) or not any(k in ly for k in CAN_SUA):
            canh.append("Kiểm định – phần %d câu %d: %s" % (p, i, ly[:200]))
        else:
            sua.append((p, i, ly))
    return sua, canh


def soan_lai_cau_lech(goi, de, sua, cac_model, ph):
    """Mỗi phần một lượt Gemini: viết lại ĐÚNG các câu bị cổng chất lượng báo lệch/nhiều đáp án, giữ nguyên câu khác."""
    t0 = goi["trangThai0"]
    for p in sorted({s[0] for s in sua}):
        ds = de.get("phan%d" % p) or []
        muc = [(i, ly) for (pp, i, ly) in sua if pp == p and 1 <= i <= len(ds)]
        if not muc:
            continue
        dm = (t0.get("dm") or {}).get("p%d" % p) or []
        cau = [{"so": i, "vanDeDuocBao": ly, "yeuCauDacTa": dm[i - 1] if i - 1 < len(dm) else "", "cauHienTai": ds[i - 1]} for i, ly in muc]
        ph.tien_do("soạn lại câu lệch phần %d" % p, None, "câu " + ", ".join(str(i) for i, _ in muc))
        nguoi = ("Cổng kiểm định ĐỘC LẬP (model khác giải lại bằng code, không xem đáp án) báo các câu PHẦN %d dưới đây có vấn đề. Với MỖI câu: giải lại "
                 "từng bước thật cẩn thận, rồi sửa đề hoặc đáp án cho NHẤT QUÁN (đáp án sai → sửa đáp án và lời giải; đề mơ hồ hoặc có nhiều đáp án đúng → sửa đề/phương án). "
                 "GIỮ NGUYÊN chỉ báo, mức độ, chủ đề và độ gọn. %s%s\n\nCÁC CÂU CẦN SỬA:\n%s\n\nTrả về JSON {\"cau\": [ ... ]}, mỗi phần tử là câu đã sửa có thêm "
                 "trường \"so\" (số câu như trên) và đúng các trường như mẫu: %s") % (
            p, LUAT[p], quy_dinh_phan(p), json.dumps(cau, ensure_ascii=False), MAU[p])
        try:
            kq, _ = goi_json_de(nguoi, cac_model, 0.2, quy_dinh_ds=(p == 2))
        except X.HetHanMuc:
            raise
        except Exception as e:
            ph.them_canh_bao("Soạn lại câu lệch phần %d lỗi: %s" % (p, str(e)[:120]))
            continue
        mang = kq.get("cau") if isinstance(kq, dict) else kq
        for it in (mang if isinstance(mang, list) else []):
            try:
                so = int(it.pop("so"))
            except (KeyError, ValueError, AttributeError, TypeError):
                continue
            if not (1 <= so <= len(ds)) or _rong(it.get("cauHoi")) or _rong(it.get("dapAn")):
                continue
            for k in ("maChiBao", "maChiBaoY", "thucTien", "hinhAnh"):
                if k not in it and k in ds[so - 1]:
                    it[k] = ds[so - 1][k]
            ds[so - 1] = it
    return de


def cong_chat_luong(goi, de, model_soan, cac_model, ph):
    """→ (đề, báo cáo md, tóm tắt dict). Chỉ BÁO CÁO + soạn lại câu lệch; lỗi của cổng không làm hỏng việc chính (trừ hết hạn mức)."""
    if CCL is None or KD is None:
        ph.them_canh_bao("Chưa nạp được cong_chat_luong/kiem_dinh_de – bỏ qua kiểm định đáp án độc lập.")
        return de, "", {}
    t0 = goi["trangThai0"]
    bao_cao, tt, canh = "", {}, []
    for vong in range(SO_VONG_SUA_DAP_AN + 1):
        de_md, da_md = dung_md_kiem_dinh(de)
        ph.tien_do("kiểm định đáp án độc lập", None, "lượt %d/%d" % (vong + 1, SO_VONG_SUA_DAP_AN + 1))
        try:
            bao_cao, tt, bang_chung = CCL.kiem_dinh(KD.goi_gemini, de_md, da_md, cac_model, model_soan)
        except X.HetHanMuc:
            raise
        except Exception as e:
            ph.them_canh_bao("Cổng kiểm định lỗi, bỏ qua: %s" % str(e)[:150])
            break
        sua, canh = phan_loai_bang_chung(bang_chung)
        ph.ghi_nhat_ky("kiểm định", "%s · cần soạn lại %d câu" % (json.dumps(tt, ensure_ascii=False), len(sua)))
        if not sua:
            break
        if vong >= SO_VONG_SUA_DAP_AN:               # hết lượt sửa: còn lệch thì báo thầy xem
            canh += ["Kiểm định – phần %d câu %d: %s" % (p, i, ly[:200]) for p, i, ly in sua]
            break
        de = chuan(soan_lai_cau_lech(goi, de, sua, cac_model, ph), t0)
    for c in canh[:20]:
        ph.them_canh_bao(c)
    return de, bao_cao, tt


# ------------------------------------------------------------------ THẨM ĐỊNH KHỚP CHỈ BÁO BẰNG AI (kiemDinhKhopChiBaoBangAI + agentKiemDinhChiBao)
def kiem_dinh_chi_bao_ai(de, t0, cac_model):
    """→ [(phần, số câu, lý do)]: câu/ý RÕ RÀNG chưa đo đúng chỉ báo được gán. Lỗi gọi AI → [] (như Mã.gs); hết hạn mức → ném lên."""
    ds_ma, dm = t0.get("dsMa"), t0.get("dm") or {}
    if not ds_ma:
        return []
    cat = lambda v, n: str(v if v is not None else "")[:n]
    lay = lambda ds, i: (ds[i] if ds and i < len(ds) else None)
    cap = []
    for p in (1, 2, 3, 4):
        for i, c in enumerate(de.get("phan%d" % p) or []):
            if p == 2:
                kv, yc = lay(ds_ma.get("p2"), i) or [], lay(dm.get("p2"), i) or []
                for k, m in enumerate(kv):
                    if m:
                        cap.append({"viTri": "P2-C%d%s" % (i + 1, "abcd"[k]), "ma": m, "chiBao": cat(yc[k] if k < len(yc) else "", 220),
                                    "cauHoi": "Dẫn: %s | Ý %s) %s" % (cat(c.get("cauHoi"), 250), "abcd"[k], cat(c.get("ABCD"[k]), 200))})
            else:
                m = lay(ds_ma.get("p%d" % p), i)
                if not m:
                    continue
                nd = cat(c.get("cauHoi"), 350)
                if p == 1:
                    nd += " | " + " ".join("%s. %s" % (k, cat(c.get(k), 80)) for k in "ABCD")
                cap.append({"viTri": "P%d-C%d" % (p, i + 1), "ma": m, "chiBao": cat(lay(dm.get("p%d" % p), i), 220), "cauHoi": nd})
    if not cap:
        return []
    nguoi = ("Bạn là chuyên gia thẩm định đề kiểm tra Vật lí. Đối chiếu từng câu/ý với chỉ báo hạt nhân được gán. Chỉ trả về JSON.\n\n"
             "Với mỗi mục, đánh giá câu/ý có đo ĐÚNG chỉ báo được gán không: đúng nội dung kiến thức, đúng hành vi (động từ), mức độ phù hợp, "
             "không lấy chỉ báo khác làm trọng tâm.\nChỉ đặt \"khop\": false khi RÕ RÀNG không khớp; trường hợp chấp nhận được thì \"khop\": true.\n\n"
             "DỮ LIỆU:\n%s\n\nTrả về JSON: {\"ketQua\": [ {\"viTri\": \"P1-C1\", \"khop\": true, \"lyDo\": \"ngắn gọn nếu không khớp\"} ]}" % json.dumps(cap, ensure_ascii=False))
    try:
        kq, _ = goi_json_de(nguoi, cac_model, 0.1, quy_dinh_ds=False)
    except X.HetHanMuc:
        raise
    except Exception as e:
        print("⚠️ Thẩm định chỉ báo lỗi, bỏ qua: %s" % str(e)[:120], flush=True)
        return []
    ds = kq.get("ketQua") if isinstance(kq, dict) else kq
    gop = {}
    for r in (ds if isinstance(ds, list) else []):
        if not isinstance(r, dict) or str(r.get("khop")).lower() != "false":
            continue
        m = re.match(r"^P(\d)-C(\d+)([a-d])?$", str(r.get("viTri") or ""), re.I)
        muc = next((x for x in cap if x["viTri"].lower() == str(r.get("viTri")).lower()), None)
        if not m or not muc:
            continue
        ly = '%snội dung CHƯA khớp chỉ báo [%s] "%s"%s. Soạn lại cho khớp đúng chỉ báo này.' % (
            ("ý %s) " % m.group(3).lower()) if m.group(3) else "", muc["ma"], cat(muc["chiBao"], 160), (" (%s)" % cat(r.get("lyDo"), 160)) if r.get("lyDo") else "")
        gop.setdefault((int(m.group(1)), int(m.group(2))), []).append(ly)
    return [(p, i, " ".join(v)) for (p, i), v in sorted(gop.items())]


def tham_dinh_chi_bao(goi, de, cac_model, ph):
    t0 = goi["trangThai0"]
    if not t0.get("dsMa"):
        return de
    for vong in range(SO_VONG_SUA_CHI_BAO + 1):
        ph.tien_do("thẩm định khớp chỉ báo", None, "lượt %d/%d" % (vong + 1, SO_VONG_SUA_CHI_BAO + 1))
        sua = kiem_dinh_chi_bao_ai(de, t0, cac_model)
        ph.ghi_nhat_ky("thẩm định chỉ báo", "%d câu chưa khớp%s" % (len(sua), (": " + "; ".join("P%d-C%d" % (p, i) for p, i, _ in sua))[:200] if sua else ""))
        if not sua:
            break
        if vong >= SO_VONG_SUA_CHI_BAO:
            for p, i, ly in sua[:15]:
                ph.them_canh_bao("Phần %d câu %d: %s" % (p, i, ly[:220]))
            break
        de = chuan(soan_lai_cau_lech(goi, de, sua, cac_model, ph), t0)
    return de


# ------------------------------------------------------------------ ẢNH THỰC TẾ + HÌNH DỰ PHÒNG (layAnhChoHinh: web → AI tạo ảnh)
def _tai_anh(url, thu_muc, ten):
    if not url:
        return None
    try:
        r = requests.get(url, headers=UA_WEB, timeout=30)
    except requests.RequestException:
        return None
    m = re.match(r"image/(png|jpeg|jpg|gif)", (r.headers.get("Content-Type") or "").lower())
    if r.status_code != 200 or not m or len(r.content) > 8 * 1024 * 1024:
        return None
    ra = os.path.join(thu_muc, ten + (".jpg" if m.group(1) in ("jpeg", "jpg") else "." + m.group(1)))
    with open(ra, "wb") as f:
        f.write(r.content)
    return ra


def anh_wikimedia(tu_khoa, thu_muc, ten):
    r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA_WEB, timeout=30, params={
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 10, "gsrsearch": tu_khoa,
        "prop": "imageinfo", "iiprop": "url|mime|extmetadata", "iiurlwidth": 1000})
    if r.status_code != 200:
        raise RuntimeError("Wikimedia lỗi %d" % r.status_code)
    pages = (((r.json() or {}).get("query") or {}).get("pages")) or {}
    for pg in sorted(pages.values(), key=lambda x: x.get("index", 0)):
        ii = (pg.get("imageinfo") or [{}])[0]
        mime = ii.get("mime") or ""
        if not re.search(r"image/(jpeg|png|svg)", mime) or ("svg" in mime and not ii.get("thumburl")):
            continue
        ra = _tai_anh(ii.get("thumburl") if "svg" in mime else (ii.get("thumburl") or ii.get("url")), thu_muc, ten)   # SVG: dùng bản PNG Wikimedia dựng sẵn
        if ra:
            gp = (((ii.get("extmetadata") or {}).get("LicenseShortName")) or {}).get("value", "")
            return ra, "Wikimedia Commons" + (", " + str(gp) if gp else "")
    return None


def anh_openverse(tu_khoa, thu_muc, ten):
    r = requests.get("https://api.openverse.org/v1/images/", headers=UA_WEB, timeout=30, params={"page_size": 8, "mature": "false", "q": tu_khoa})
    if r.status_code != 200:
        raise RuntimeError("Openverse lỗi %d" % r.status_code)
    for d in (r.json() or {}).get("results") or []:
        ra = _tai_anh(d.get("url"), thu_muc, ten) or _tai_anh(d.get("thumbnail"), thu_muc, ten)
        if ra:
            return ra, "Openverse" + (", CC " + str(d["license"]).upper() if d.get("license") else "")
    return None


def anh_google_cse(tu_khoa, thu_muc, ten):
    khoa, cx = os.environ.get("GOOGLE_CSE_KEY", "").strip(), os.environ.get("GOOGLE_CSE_CX", "").strip()
    if not khoa or not cx:
        return None
    r = requests.get("https://www.googleapis.com/customsearch/v1", timeout=30, params={
        "searchType": "image", "num": 6, "safe": "active", "rights": "cc_publicdomain|cc_attribute|cc_sharealike", "key": khoa, "cx": cx, "q": tu_khoa})
    if r.status_code != 200:
        raise RuntimeError("Google CSE lỗi %d" % r.status_code)
    for it in (r.json() or {}).get("items") or []:
        ra = _tai_anh(it.get("link"), thu_muc, ten)
        if ra:
            return ra, it.get("displayLink") or "web"
    return None


def anh_gemini(mo_ta, la_anh_thuc, thu_muc, ten):
    """taoAnhBangGemini: model sinh ảnh (MODEL_TAO_ANH). Lỗi/hết hạn mức → None, không làm HOAN cả đề vì một ảnh."""
    if not mo_ta or not MODEL_TAO_ANH:
        return None
    loi_nhac = (("Tạo một bức ảnh chân thực, rõ nét, bố cục gọn, dùng minh hoạ cho câu hỏi đề kiểm tra Vật lí THPT: %s. Không chèn chữ, logo hay hình mờ." % mo_ta)
                if la_anh_thuc else
                ("Vẽ hình minh hoạ cho câu hỏi đề kiểm tra Vật lí THPT theo phong cách hình vẽ sách giáo khoa Việt Nam: hình 2D phẳng, nét đen rõ trên nền trắng, "
                 "không tô bóng, không trang trí, tỉ lệ hợp lí, dùng đúng kí hiệu vật lí chuẩn (điện trở, nguồn điện, ampe kế, vôn kế, mũi tên véc-tơ lực, vận tốc...): %s" % mo_ta))
    data, _ = X.goi_gemini({"contents": [{"role": "user", "parts": [{"text": loi_nhac}]}], "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}}, MODEL_TAO_ANH)
    for pt in (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts")) or []:
        d = pt.get("inlineData") or pt.get("inline_data")
        if d and d.get("data"):
            mime = d.get("mimeType") or d.get("mime_type") or "image/png"
            ra = os.path.join(thu_muc, ten + (".jpg" if "jpeg" in mime else ".png"))
            with open(ra, "wb") as f:
                f.write(base64.b64decode(d["data"]))
            return ra
    return None


def tim_anh_thay_the(h, thu_muc, ten, loi, tt):
    """Web (nếu có từ khoá) rồi AI tạo ảnh → (đường dẫn, nguồn ghi chú) hoặc (None, '')."""
    tu_khoa = h.get("tuKhoaTimKiem") or ""
    if not tu_khoa:
        loi.append("thiếu tuKhoaTimKiem nên không tìm được trên web")
    else:
        for ten_cach, f in (("Wikimedia", anh_wikimedia), ("Openverse", anh_openverse), ("Google CSE", anh_google_cse)):
            try:
                kq = f(tu_khoa, thu_muc, ten)
                if kq:
                    return kq
            except Exception as e:
                loi.append("%s: %s" % (ten_cach, str(e)[:80]))
    if not tt["het_ai"]:
        try:
            ra = anh_gemini(h.get("moTa") or tu_khoa, h.get("loai") == "anhthuc", thu_muc, ten)
            if ra:
                return ra, ""
            loi.append("AI tạo ảnh không trả về ảnh")
        except X.HetHanMuc:
            tt["het_ai"] = True
            loi.append("AI tạo ảnh: hết hạn mức")
        except Exception as e:
            loi.append("AI tạo ảnh: %s" % str(e)[:100])
    return None, ""


# ------------------------------------------------------------------ VẼ HÌNH (ve_hinh.py) + ẢNH THỰC TẾ
def ve_hinh_cho_de(de, cac_model, ph, thu_muc):
    """→ {'P<phần>_C<câu>': đường dẫn ảnh}. Hình vẽ: code (ve_hinh) → web → AI. Ảnh thực tế: web → AI.
    Lỗi một hình → để chỗ trống ghi chú (xuat_de_v2 tự báo), không dừng cả đề."""
    hinh_san, tt, so = {}, {"het_ai": False}, 0
    for p in (1, 2, 3, 4):
        for i, c in enumerate(de.get("phan%d" % p) or [], 1):
            h = c.get("hinhAnh")
            if not (h and h.get("hopLe") and h.get("loai") in ("hinhve", "anhthuc")):
                continue
            if so >= TOI_DA_HINH_VE:
                ph.them_canh_bao("Phần %d câu %d: vượt %d hình/ảnh mỗi lượt, để chỗ trống." % (p, i, TOI_DA_HINH_VE))
                continue
            so += 1
            ph.tien_do("vẽ hình / tìm ảnh", None, "phần %d câu %d" % (p, i))
            ra, ghi, loi = None, "", []
            if h["loai"] == "hinhve":
                if VH is None:
                    loi.append("chưa nạp ve_hinh")
                else:
                    try:
                        ra, ghi = VH.ve_mot_hinh({"cauHoi": c.get("cauHoi", ""), "chuThich": h.get("chuThich", ""), "moTa": h.get("moTa", "")}, cac_model, thu_muc, so)
                    except X.HetHanMuc:
                        raise
                    except Exception as e:
                        loi.append("vẽ bằng code: %s" % str(e)[:100])
            if not ra:
                ra, nguon = tim_anh_thay_the(h, thu_muc, "anhweb%d" % so, loi, tt)
                if ra:
                    ghi = "ảnh web" + (" · " + nguon if nguon else " · AI tạo ảnh")
                    if nguon and not re.search(r"\(Nguồn:", h.get("chuThich") or ""):
                        h["chuThich"] = (h.get("chuThich") or "Hình") + " (Nguồn: %s)" % nguon       # GHI_NGUON_ANH_WEB
            if ra:
                hinh_san["P%d_C%d" % (p, i)] = ra
                ph.ghi_nhat_ky("hình/ảnh", "phần %d câu %d: %s" % (p, i, ghi))
            else:
                ph.them_canh_bao("Phần %d câu %d: không tạo/tìm được hình (%s)" % (p, i, "; ".join(loi)[:300]))
    return hinh_san


def tai_mau_b4(drive, goi, thu_muc):
    """Mẫu đề ô B4 (Google Doc hoặc .docx) → tệp .docx làm reference-doc cho pandoc. Lỗi → None (dùng mẫu mặc định)."""
    raw = str((goi.get("thamSo") or {}).get("B4") or "")
    m = re.search(r"/d/([\w-]{20,})", raw) or re.fullmatch(r"\s*([\w-]{20,})\s*", raw)
    if not m:
        return None
    ra = os.path.join(thu_muc, "mau_b4.docx")
    try:
        try:
            data = drive.files().export(fileId=m.group(1), mimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document").execute()
        except Exception:
            data = drive.files().get_media(fileId=m.group(1)).execute()
        with open(ra, "wb") as f:
            f.write(data)
        return ra
    except Exception as e:
        print("⚠️ Không tải được mẫu B4 (%s) – dùng mẫu mặc định." % str(e)[:100], flush=True)
        return None


# ------------------------------------------------------------------ KIỂM TRÙNG VỚI NGÂN HÀNG CÂU HỎI (xuat_de.py = chỉ mục chống trùng)
def kiem_trung_kho(kho, de, ph):
    """Chỉ CẢNH BÁO câu giống câu đã có trong Kho chung (câu mẫu được dùng làm nguồn tham khảo nên không tự sửa)."""
    if KT is None:
        return 0
    try:
        cau = KT.doc_cau(kho.worksheet(KT.TAB_NH).get_all_values())
        moi = []
        for p in (1, 2, 3, 4):
            for i, c in enumerate(de.get("phan%d" % p) or [], 1):
                van = lam_sach(c.get("cauHoi")) + " " + " ".join(str(c.get(k, "")) for k in "ABCD")
                if len(van.strip()) >= KT.NOI_DUNG_TOI_THIEU:
                    moi.append({"ma": "DE_P%d_C%d" % (p, i), "chu": KT.cum(KT.chuan_chu(van)), "dang": KT.cum(KT.chuan_chu(van, bo_so=True))})
        if not moi:
            return 0
        nguong = KT.doc_nguong_ghi(KT.doc_nut(kho))
        n = 0
        for ma, ds in KT.tinh_chi_muc(cau + moi, nguong):
            m = re.fullmatch(r"DE_P(\d)_C(\d+)", ma)
            if not m:
                continue
            for ma2, s_chu, s_dang in ds:
                if not ma2.startswith("DE_P") and n < 12:
                    ph.them_canh_bao("Phần %s câu %s giống câu %s trong Kho chung (chữ %d%%, dạng %d%%)." % (m.group(1), m.group(2), ma2, s_chu, s_dang))
                    n += 1
                    break
        ph.ghi_nhat_ky("kiểm trùng Kho chung", "%d câu giống câu đã có (ngưỡng dạng %d%%)" % (n, nguong))
        return n
    except Exception as e:
        ph.ghi_nhat_ky("kiểm trùng Kho chung", "bỏ qua: %s" % str(e)[:120])
        return 0


def bao_telegram(noi_dung):
    try:
        if TB:
            TB.gui_telegram(noi_dung)
    except Exception:
        pass


def main():
    import google.auth
    import gspread
    from googleapiclient.discovery import build
    cred, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    gc, drive = gspread.authorize(cred), build("drive", "v3", credentials=cred, cache_discovery=False)
    goi_id, kq_id = os.environ["GOI_ID"], os.environ["KQ_ID"]
    goi = GT.doc_json_drive(drive, goi_id)
    if goi.get("phienBan", 1) == 1:            # khớp GT.kiem_goi: thiếu phienBan = gói v1 (Apps Script đang gửi bằng guiDeSangXuong_ cũ)
        thong_bao = ("Gói việc là phiên bản 1 (thiếu phienBan/loai) nên xưởng không xử lí được. "
                     "Trong Apps Script chạy xtd2BatXuong(true) để taoDeThiAgent gửi gói v2, rồi tạo đề lại.")
        try:
            GT.Phien(drive, kq_id, goi).loi(thong_bao)   # báo ra B17 thay vì chỉ lỗi trong GitHub Actions
        except Exception as e:
            print("Không ghi được ket_qua:", e, flush=True)
        raise SystemExit(thong_bao)
    loi_goi = GT.kiem_goi(goi)
    ph = GT.Phien(drive, kq_id, goi)
    if loi_goi:
        ph.loi("Gói việc không hợp lệ: " + "; ".join(loi_goi))
        raise SystemExit(1)
    cu = GT.doc_json_drive(drive, kq_id)      # lần chạy lại sau HOAN: dùng tiếp phần đã soạn
    de = {k: v for k, v in (cu.get("deThi") or {}).items() if k in ("phan1", "phan2", "phan3", "phan4")}
    tien = dict(cu.get("tienDo") or {})       # các bước đã xong ở lượt trước: cauTrucXong, kiemDinhXong, kiemDinh, baoCao
    ph.luot = int(cu.get("luot", 0) or 0) + 1
    ph.tien_do("đọc gói", 3, "loại %s · khối %s · lượt %d" % (goi["loai"], goi["cauHinh"]["grade"], ph.luot))
    t0 = goi["trangThai0"]
    t0["_khoi"] = str(goi["cauHinh"]["grade"])        # lenh_theo_khoi / kiem_theo_khoi đọc khối từ đây
    nh = str(t0.get("nganHang") or "")
    if (goi.get("tuyChon") or {}).get("dungCauMau") is False and nh.startswith("=== CÂU HỎI THẬT TỪ KHO ĐỀ"):
        j = nh.find("=== HẾT CÂU MẪU ===")                # ô B24 tắt: bỏ khối câu mẫu Kho chung (nếu còn sót)
        t0["nganHang"] = nh[j + len("=== HẾT CÂU MẪU ==="):].lstrip() if j >= 0 else nh
    canh_bao_so_cau_khoi(t0, ph)
    tc = goi.get("tuyChon") or {}
    nhanh = str(tc.get("cheDo") or "").lower() == "nhanh"                     # "Tạo đề nhanh": chỉ soạn + tự sửa cấu trúc, bỏ các bước AI kiểm định
    xac_minh = (tc.get("xacMinh") is not False) and not nhanh
    co_hinh = tc.get("hinhAnh") is not False
    hinh_tam = tempfile.mkdtemp()

    def luu():                                # ghi đề + tiến độ ra Drive để HOAN/chạy lại không mất việc
        ph.extra["deThi"], ph.extra["tienDo"] = de, tien
        ph.ghi("DANG_LAM", ep=True)

    kho = None
    try:
        kho = gc.open_by_key(X.ID_KHO_CHUNG)
        cac_model = X.doc_cau_hinh(kho)
        model, ghi_chu = "", {}
        for p in (1, 2, 3, 4):
            n = t0["yc"]["p%d" % p]
            if n == 0:
                de["phan%d" % p] = []
                continue
            if len(de.get("phan%d" % p) or []) == n:
                ph.ghi_nhat_ky("bỏ qua phần %d" % p, "đã soạn đủ từ lượt trước")
                continue
            for lan in (1, 2):                # đủ số câu thì nhận; thiếu thì soạn lại 1 lần
                ph.tien_do("soạn phần %d" % p, 10 + 12 * p, "lần %d, cần %d câu" % (lan, n))
                mang, model = soan_phan(goi, p, cac_model, ghi_chu.get(p, ""), ph)
                if len(mang) == n:
                    break
                ghi_chu[p] = "lần trước chỉ có %d/%d câu; phải trả ĐỦ %d câu." % (len(mang), n, n)
            de["phan%d" % p] = mang
            if len(mang) != n:
                ph.them_canh_bao("Phần %d có %d/%d câu sau 2 lần soạn." % (p, len(mang), n))
            luu()                              # lưu phần đã soạn ngay, hết hạn mức giữa chừng vẫn giữ được
        model = model or cac_model[0]

        # --- BƯỚC 4a: kiểm cấu trúc/độ dài/hình/thực tiễn/chỉ báo + tự sửa (agentKiemTraVaTuSuaDe) ---
        if not tien.get("cauTrucXong"):
            ph.tien_do("chuẩn hoá và tự sửa cấu trúc", 62)
            de, _ = tu_sua_cau_truc(goi, de, cac_model, ph)
            ghi_cau_mau(de, ph)
            tien["cauTrucXong"] = True
            luu()
        else:
            de = chuan(de, t0)

        # --- thẩm định khớp chỉ báo bằng AI + soạn lại câu chưa khớp (agentKiemDinhChiBao) ---
        if not tien.get("chiBaoXong") and xac_minh:
            ph.tien_do("thẩm định khớp chỉ báo", 66)
            de = tham_dinh_chi_bao(goi, de, cac_model, ph)
            tien["chiBaoXong"] = True
            luu()

        # --- BƯỚC 4b/5: cổng chất lượng – giải độc lập bằng code (Gemini model khác + Groq), soạn lại câu lệch ---
        if not tien.get("kiemDinhXong") and xac_minh:
            ph.tien_do("kiểm định đáp án độc lập", 70)
            de, bao_cao, tt = cong_chat_luong(goi, de, model, cac_model, ph)
            tien.update({"kiemDinhXong": True, "kiemDinh": tt, "baoCao": bao_cao[:15000]})
            luu()
        tt_kd, bao_cao = tien.get("kiemDinh") or {}, tien.get("baoCao", "")

        # --- kiểm trùng với Ngân hàng câu hỏi Kho chung (chỉ cảnh báo) ---
        if not tien.get("trungXong"):
            ph.tien_do("kiểm trùng với Kho chung", 78)
            kiem_trung_kho(kho, de, ph)
            tien["trungXong"] = True

        ph.tien_do("chuẩn hoá và kiểm công thức", 82)
        de = chuan(de, t0)
        for l in CD.kiem_tra_latex(de):
            ph.them_canh_bao(l)

        # --- vẽ hình bằng code (ve_hinh) ---
        ph.tien_do("vẽ hình / tìm ảnh", 84)
        hinh_san = ve_hinh_cho_de(de, cac_model, ph, hinh_tam) if co_hinh else {}

        ph.tien_do("xuất Word HS và GV", 90)
        thu = tempfile.mkdtemp()
        mau_b4 = tai_mau_b4(drive, goi, thu) if DUNG_MAU_B4 else None
        kq = XD.xuat_de(de, goi["cauHinh"], thu, hinh_san=hinh_san, ten_goc="De", mau_word=mau_b4)
        for c in kq["canhBao"]:
            ph.them_canh_bao(c)
        GT.ghi_docx_vao_tep(drive, goi["dich"]["docxHS"], kq["hs"])
        GT.ghi_docx_vao_tep(drive, goi["dich"]["docxGV"], kq["gv"])
        tom_tat = dict(kq["thongKe"])
        tom_tat.update({"kiemDinh": tt_kd, "soHinhVe": len(hinh_san), "soCanhBao": len(ph.canh_bao)})
        ph.extra["baoCaoKiemDinh"] = bao_cao
        ph.xong(de, tep=goi["dich"], tom_tat=tom_tat, model=model)
        print("✅ Xong đề %s: %s" % (goi["ma"], json.dumps(tom_tat, ensure_ascii=False)), flush=True)
        bao_telegram("✅ Xưởng Python đã soạn xong đề %s (%d cảnh báo). %s" % (goi["ma"], len(ph.canh_bao), json.dumps(tt_kd, ensure_ascii=False)[:200]))
    except X.HetHanMuc as e:
        theo_ngay = bool(re.search(r"ngày|day|RPD", str(e), re.I))
        ph.hoan(str(e), CHO_HOAN_PHUT["ngay" if theo_ngay else "phut"], de_dang_soan=de, tien_do_luu=tien)
        print("⏸️ Hết hạn mức Gemini – Apps Script sẽ gửi lại:", str(e)[:150], flush=True)
    except Exception as e:
        ph.loi(str(e))
        for k in ("docxHS", "docxGV"):
            GT.danh_dau_loi_tep(drive, goi["dich"].get(k, ""), str(e))
        bao_telegram("❌ Xưởng Python lỗi khi soạn đề %s: %s" % (goi.get("ma", ""), str(e)[:200]))
        raise
    finally:
        shutil.rmtree(hinh_tam, ignore_errors=True)
        if Q:
            try:
                Q.ghi_sheet(kho)
            except Exception:
                pass


if __name__ == "__main__":
    main()
