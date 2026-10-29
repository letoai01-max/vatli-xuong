"""
groq_xuong.py – GIẢI ĐỘC LẬP BẰNG MÔ HÌNH KHÁC HÃNG (Groq) cho xưởng Python. Dùng chung cho duyet_cau.py và tu_giai.py.

Groq không được xem đáp án, chỉ nhận đề + phương án, trả đáp án ngắn:
  nhiều lựa chọn "B" · đúng/sai "a) Đ, b) S, c) Đ, d) S" · trả lời ngắn / tự luận: một con số (đáp số cuối).
Thử lần lượt các mô hình trong GROQ_MODELS; mô hình bị Groq ngừng (404) tự bỏ qua; hết hạn mức (429) chờ theo Groq báo rồi thử lại 1 lần.
Thiếu GROQ_API_KEY hoặc Groq lỗi → trả về rỗng, nơi gọi tự làm như cũ (không bao giờ làm hỏng lượt chạy).
Lượt gọi được ghi vào Quota_SuDung (dòng "xưởng groq-…") qua quota_xuong.py.
Biến môi trường: GROQ_API_KEY (bắt buộc), GROQ_MODELS (tuỳ chọn, cách nhau bởi dấu phẩy).
"""
import json, os, re, time

import requests

try:
    import quota_xuong as Q
except Exception:                       # thiếu tệp ghi hạn mức: vẫn chạy bình thường
    Q = None

URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS = [m.strip() for m in os.environ.get("GROQ_MODELS", "openai/gpt-oss-120b,qwen/qwen3.8-27b,openai/gpt-oss-20b").split(",") if m.strip()]
LO = 10                    # số câu mỗi lượt gọi
NGHI_GIUA_LUOT = 3         # giây – Groq miễn phí giới hạn token/phút
_HONG = set()


def co_khoa():
    return bool(os.environ.get("GROQ_API_KEY", "").strip())


def _ghi(model, ma, data=None, treo=False):
    if not Q:
        return
    u = (data or {}).get("usage") or {}
    Q.ghi_luot(Q.nhan_groq(model), ma, u.get("prompt_tokens", 0), u.get("completion_tokens", 0), treo)


def goi(noi_dung, max_tokens=16000, suy_nghi="medium"):
    """Gửi một lời nhắn; trả (chữ, tên model) hoặc (None, '')."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return None, ""
    for model in MODELS:
        if model in _HONG:
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
                break
            try:
                j = r.json()
            except ValueError:
                j = {}
            _ghi(model, r.status_code, j if r.status_code == 200 else None)
            if r.status_code == 200:
                msg = ((j.get("choices") or [{}])[0].get("message") or {})
                return str(msg.get("content") or ""), model
            loi = str((j.get("error") or {}).get("message") or r.text)[:200]
            if r.status_code == 400 and re.search(r"reasoning", loi, re.I) and "reasoning_effort" in body:
                del body["reasoning_effort"]; continue
            if r.status_code == 400 and re.search(r"json|response_format", loi, re.I) and "response_format" in body:
                del body["response_format"]; continue
            if r.status_code == 404:
                _HONG.add(model); print("  [Groq] %s đã ngừng (404), bỏ qua." % model, flush=True); break
            if r.status_code == 429 and lan == 1:
                cho = min(60, int(float(r.headers.get("retry-after") or 20)) + 2)
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


def giai_lo(ds):
    """ds: [{ma, dang (TN|DS|TLN|TL hoặc tên dạng), noi_dung, phuong_an}] → ({ma: đáp án}, model). Không thấy đáp án gốc."""
    kq, model_dung = {}, ""
    if not co_khoa() or not ds:
        return kq, model_dung
    for k in range(0, len(ds), LO):
        lo = ds[k:k + LO]
        du_lieu = [{"ma_cau": x["ma"], "dang": x["dang"], "noi_dung": str(x["noi_dung"])[:1500],
                    "phuong_an": str(x.get("phuong_an") or "")[:800]} for x in lo]
        loi_nhan = ("Bạn là học sinh giỏi Vật lí. Tự giải ĐỘC LẬP, cẩn thận từng câu, tính toán chính xác. Ghi đáp án: "
                    "nhiều lựa chọn là MỘT chữ A-D; đúng/sai dạng \"a) Đ, b) S, c) Đ, d) S\"; trả lời ngắn và tự luận là MỘT con số "
                    "(đáp số cuối, dấu chấm thập phân, không kèm đơn vị). Câu không giải chắc chắn được thì dap_an để rỗng.\n"
                    "CHỈ trả về JSON đúng mẫu: {\"ket_qua\":[{\"ma_cau\":\"...\",\"dap_an\":\"...\"}]}, mỗi câu một phần tử.\n"
                    "CÁC CÂU:\n" + json.dumps(du_lieu, ensure_ascii=False))
        text, model = goi(loi_nhan)
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
