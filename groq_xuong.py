"""
groq_xuong.py – GIẢI ĐỘC LẬP BẰNG MÔ HÌNH KHÁC HÃNG (Groq) cho xưởng Python. Dùng chung cho duyet_cau.py và tu_giai.py.

Groq không được xem đáp án, chỉ nhận đề + phương án, trả đáp án ngắn:
  nhiều lựa chọn "B" · đúng/sai "a) Đ, b) S, c) Đ, d) S" · trả lời ngắn / tự luận: một con số (đáp số cuối).
Thử lần lượt các mô hình trong GROQ_MODELS; mô hình bị Groq ngừng (404) tự bỏ qua; hết hạn mức (429) chờ theo Groq báo rồi thử lại 1 lần.
Thiếu GROQ_API_KEY hoặc Groq lỗi → trả về rỗng, nơi gọi tự làm như cũ (không bao giờ làm hỏng lượt chạy).
Lượt gọi được ghi vào Quota_SuDung (dòng "xưởng groq-…") qua quota_xuong.py.
Biến môi trường: GROQ_API_KEY (bắt buộc), GROQ_MODELS (tuỳ chọn, cách nhau bởi dấu phẩy).

[22/11/2026] XOAY NHIỀU KHOÁ + PHÂN LOẠI 429 (thêm, không đổi chỗ cũ):
  • Khoá: GROQ_API_KEY, GROQ_API_KEY_1 … GROQ_API_KEY_10 (mỗi Gmail/tổ chức Groq một khoá → mỗi khoá có hạn mức ngày riêng). Chỉ có một khoá thì y như cũ.
    Khoá bị 401/403 → bỏ khoá đó cả lượt. Log chỉ hiện 4 kí tự cuối của khoá.
  • GROQ_THONG_MINH = "true" (mặc định "false" → 429 xử lí y như cũ):
      – 429 hết hạn mức NGÀY (TPD/RPD): đánh dấu (model, khoá) hết hôm nay, đổi khoá/model NGAY, không chờ.
      – 429 "Request too large … output tokens per minute (OTPM) Limit L": hạ max_completion_tokens xuống L-100 rồi thử lại (chờ không giúp được).
      – Mọi (model, khoá) đều hết → giai_lo trả rỗng ngay, không ngủ 35 giây.
  • GROQ_MAX_TOKENS: trần token ra mỗi lượt gọi (mặc định 16000 như cũ).
"""
import json, os, re, threading, time

import requests

try:
    import quota_xuong as Q
except Exception:                       # thiếu tệp ghi hạn mức: vẫn chạy bình thường
    Q = None

URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS = [m.strip() for m in (os.environ.get("GROQ_MODELS") or os.environ.get("CFG_GROQ_MODELS")
          or "openai/gpt-oss-120b,qwen/qwen3.8-27b,openai/gpt-oss-20b").split(",") if m.strip()]
LO = int(os.environ.get("GROQ_LO") or 10)     # số câu mỗi lượt gọi [22/11] chỉnh được; qwen3.8 chỉ cho 1000 token ra/phút nên nên đặt 4–5
NGHI_GIUA_LUOT = 3         # giây – Groq miễn phí giới hạn token/phút
_HONG = set()
_KHOA_HONG = set()         # [22/11] khoá bị 401/403: bỏ cả lượt
_HET_NGAY = set()          # [22/11] cặp (model, khoá) đã hết hạn mức NGÀY
_KHOA_LUONG = threading.Lock()   # tầng 4 và phiếu ba chạy song song
THONG_MINH = os.environ.get("GROQ_THONG_MINH", "false").strip().lower() in ("true", "1", "yes", "on", "bat", "bật")
try:
    MAX_TOKENS = max(200, int(float(os.environ.get("GROQ_MAX_TOKENS") or 16000)))
except ValueError:
    MAX_TOKENS = 16000


def _ds_khoa():
    """[22/11] Danh sách khoá (bỏ rỗng, bỏ trùng): GROQ_API_KEY, GROQ_API_KEY_1 … _10."""
    ds = []
    for ten in ["GROQ_API_KEY"] + ["GROQ_API_KEY_%d" % i for i in range(1, 11)]:
        v = os.environ.get(ten, "").strip()
        if v and v not in ds:
            ds.append(v)
    return ds


def _che(key):
    return "…" + key[-4:]


def _con_cach(models=None):
    """[22/11] Còn (model, khoá) nào chưa hết hạn mức ngày / chưa hỏng không."""
    ks = [k for k in _ds_khoa() if k not in _KHOA_HONG]
    for m in (models or MODELS):
        if m in _HONG:
            continue
        if any((m, k) not in _HET_NGAY for k in ks):
            return True
    return False


def co_khoa():
    return bool(_ds_khoa())


def cong_tac_bat(ten="VONG_KIEM_TRA_THU_HAI_GROQ", mac_dinh=True):
    """[Hàng 5] Ưu tiên CFG_<ten> (tab CauHinhDong) → CONG_TAC trong trung_tam_dieu_phoi.json → mặc định."""
    v = os.environ.get("CFG_" + ten)
    if v is None:
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "trung_tam_dieu_phoi.json"), encoding="utf-8") as f:
                v = (json.load(f).get("CONG_TAC") or {}).get(ten)
        except Exception:
            v = None
    if v is None:
        return mac_dinh
    return str(v).strip().lower() not in ("false", "0", "no", "off", "tat", "tắt")


def san_sang():
    return co_khoa() and cong_tac_bat()


def _ghi(model, ma, data=None, treo=False):
    if not Q:
        return
    u = (data or {}).get("usage") or {}
    Q.ghi_luot(Q.nhan_groq(model), ma, u.get("prompt_tokens", 0), u.get("completion_tokens", 0), treo)


def goi(noi_dung, max_tokens=None, suy_nghi="medium", models=None):
    """Gửi một lời nhắn; trả (chữ, tên model) hoặc (None, ''). [22/11] models: chỉ thử các model này (mặc định MODELS).
    [22/11] Xoay khoá: với mỗi model thử lần lượt các khoá còn dùng được."""
    ks = _ds_khoa()
    if not ks:
        return None, ""
    max_tokens = max_tokens or MAX_TOKENS
    for model in (models or MODELS):
        if model in _HONG:
            continue
        sang_model = False
        for key in ks:
            if sang_model:
                break
            if key in _KHOA_HONG or (model, key) in _HET_NGAY:
                continue
            body = {"model": model, "messages": [{"role": "user", "content": noi_dung}], "temperature": 0.2,
                    "max_completion_tokens": max_tokens, "response_format": {"type": "json_object"}, "reasoning_effort": suy_nghi}
            lan = 0
            while lan < 4:
                lan += 1
                try:
                    r = requests.post(URL, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                                      data=json.dumps(body), timeout=240)
                except requests.RequestException as e:
                    _ghi(model, 0, treo=True)
                    print("  [Groq] %s treo / lỗi mạng: %s" % (model, str(e)[:100]), flush=True)
                    sang_model = True
                    break
                try:
                    j = r.json()
                except ValueError:
                    j = {}
                _ghi(model, r.status_code, j if r.status_code == 200 else None)
                if r.status_code == 200:
                    msg = ((j.get("choices") or [{}])[0].get("message") or {})
                    return str(msg.get("content") or ""), model
                loi_day_du = str((j.get("error") or {}).get("message") or r.text)
                loi = loi_day_du[:200]
                if r.status_code == 400 and re.search(r"reasoning", loi, re.I) and "reasoning_effort" in body:
                    del body["reasoning_effort"]; continue
                if r.status_code == 400 and re.search(r"json|response_format", loi, re.I) and "response_format" in body:
                    del body["response_format"]; continue
                if r.status_code in (401, 403):                       # [22/11] khoá hỏng / bị thu hồi: bỏ khoá này
                    with _KHOA_LUONG:
                        _KHOA_HONG.add(key)
                    print("  [Groq] khoá %s bị từ chối (%d), bỏ qua khoá này." % (_che(key), r.status_code), flush=True)
                    break
                if r.status_code == 404:
                    _HONG.add(model); print("  [Groq] %s đã ngừng (404), bỏ qua." % model, flush=True)
                    sang_model = True
                    break
                if r.status_code == 429 and THONG_MINH:
                    if re.search(r"tokens per day|requests per day|\(TPD\)|\(RPD\)", loi_day_du, re.I):
                        with _KHOA_LUONG:
                            _HET_NGAY.add((model, key))
                        print("  [Groq] %s khoá %s hết hạn mức NGÀY – đổi khoá/model, không chờ." % (model, _che(key)), flush=True)
                        break
                    m = re.search(r"Request too large.*?Limit (\d+), Requested (\d+)", loi_day_du, re.S | re.I)
                    if m:
                        tran = int(m.group(1)) - 100
                        if re.search(r"output tokens|OTPM", loi_day_du, re.I) and tran >= 200 and body["max_completion_tokens"] > tran:
                            print("  [Groq] %s vượt trần token ra/phút (%s) – hạ max_completion_tokens còn %d rồi thử lại." % (model, m.group(1), tran), flush=True)
                            body["max_completion_tokens"] = tran
                            continue
                        print("  [Groq] %s: yêu cầu quá lớn so với trần (%s), bỏ model này." % (model, loi), flush=True)
                        sang_model = True
                        break
                if r.status_code == 429 and lan == 1:
                    try:
                        cho = min(60, int(float(r.headers.get("retry-after") or 20)) + 2)
                    except ValueError:
                        cho = 22
                    print("  [Groq] %s hết hạn mức tạm thời, chờ %d giây…" % (model, cho), flush=True)
                    time.sleep(cho); continue
                if r.status_code in (500, 502, 503) and lan < 3:
                    time.sleep(5 * lan); continue
                print("  [Groq] %s lỗi %d: %s" % (model, r.status_code, loi), flush=True)
                break
    return None, ""


def doc_json(text):
    s = re.sub(r"<think>[\s\S]*?</think>", "", str(text or ""), flags=re.I).replace("```json", "").replace("```", "").strip()
    a, b = s.find("{"), s.rfind("}")
    if a != -1 and b > a:
        s = s[a:b + 1]
    j = json.loads(s)
    return j if isinstance(j, list) else (j.get("ket_qua") or [])


def giai_lo(ds, models=None):
    """[22/11] models: chỉ dùng các model này (phiếu thứ ba, thứ tư khác họ model). ds: [{ma, dang (TN|DS|TLN|TL hoặc tên dạng), noi_dung, phuong_an}] → ({ma: đáp án}, model). Không thấy đáp án gốc."""
    kq, model_dung = {}, ""
    if not san_sang() or not ds:
        return kq, model_dung
    if THONG_MINH and not _con_cach(models):                # [22/11] mọi model/khoá đã hết hôm nay: khỏi gọi
        return kq, model_dung
    for k in range(0, len(ds), LO):
        lo = ds[k:k + LO]
        du_lieu = [{"ma_cau": x["ma"], "dang": x["dang"], "noi_dung": str(x["noi_dung"])[:3000],
                    "phuong_an": str(x.get("phuong_an") or "")[:800]} for x in lo]
        loi_nhan = ("Bạn là học sinh giỏi Vật lí. Tự giải ĐỘC LẬP, cẩn thận từng câu, tính toán chính xác. Ghi đáp án: "
                    "nhiều lựa chọn là MỘT chữ A-D; đúng/sai dạng \"a) Đ, b) S, c) Đ, d) S\"; trả lời ngắn và tự luận là MỘT con số "
                    "(đáp số cuối, dấu chấm thập phân, không kèm đơn vị). Câu không giải chắc chắn được thì dap_an để rỗng.\n"
                    "CHỈ trả về JSON đúng mẫu: {\"ket_qua\":[{\"ma_cau\":\"...\",\"dap_an\":\"...\"}]}, mỗi câu một phần tử.\n"
                    "CÁC CÂU:\n" + json.dumps(du_lieu, ensure_ascii=False))
        text, model = goi(loi_nhan, models=models)
        if text is None:                               # [22/11] hết token/phút: chờ hết phút rồi thử lại ĐÚNG MỘT lần trước khi bỏ
            if THONG_MINH and not _con_cach(models):   # hết hạn mức ngày thì chờ vô ích
                break
            time.sleep(35)
            text, model = goi(loi_nhan, models=models)
        if text is None:
            break                                      # Groq không dùng được lượt này: phần còn lại để trống
        model_dung = model or model_dung
        try:
            for g in doc_json(text):
                if isinstance(g, dict) and g.get("ma_cau") is not None and str(g.get("dap_an") or "").strip():
                    kq[str(g["ma_cau"])] = str(g["dap_an"]).strip()
        except Exception as e:
            print("  [Groq] %s trả JSON hỏng: %s" % (model, str(e)[:80]), flush=True)
        if k + LO < len(ds):
            time.sleep(NGHI_GIUA_LUOT)
    return kq, model_dung
