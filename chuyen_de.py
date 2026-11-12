"""
chuyen_de.py – XƯỞNG SOẠN CHUYÊN ĐỀ ÔN TẬP (Python, GitHub Actions) – thay cho phần gọi Gemini của cdotMotPhan_ trong Apps Script.

Cùng khuôn "gói việc" với de_cuong.py:
  Apps Script (XuongChuyenDe.gs) dựng sẵn lời nhắc từng phần bằng ĐÚNG các hàm đang dùng (cdotLoiNhac_, cdotLoiNhacTN_,
  cdotLoiNhacRaSoat_), ghi goi_<mã>.json + ket_qua_<mã>.json vào thư mục _Xuong_Python rồi gửi lệnh chuyen_de.yml.
  Xưởng:
    1. Đọc gói, gọi Gemini lần lượt từng phần theo đúng thứ tự (cùng nhiệt độ 0,5, cùng câu dặn "CÔNG CỤ TÍNH" do
       Apps Script gắn vào lời nhắc, cùng cách lấy chữ sau lần chạy code cuối).
    2. Thay {{PHAN_n}} = bản thô phần n (dùng cho Đề luyện thi TN: hướng dẫn giải đọc đề đã ra) và
       {{RS_TL}} = mọi phần đứng trước (dùng cho phần RÀ SOÁT ĐÁP ÁN).
    3. (Tuỳ chọn, gói ghi kiemTraSo = true) tính lại đáp số bằng sympy và nối bảng vào phần rà soát.
    4. Ghi ket_qua_<mã>.json: trangThai XONG / LOI. Apps Script tự nhận, chuẩn hoá công thức, tạo Docs, Word, gửi mail.
Lỗi bất kì (hết hạn mức, Gemini lỗi…) → trangThai LOI → Apps Script tự soạn lại như cũ bằng đường Meta.

[12/11/2026] BẢN VÁ so với bản đầu:
  • Gọi Gemini bằng doc_de.goi_gemini (dùng chung với tao_de, doc_de): xoay GEMINI_API_KEY … _5, chờ khi chạm giới hạn
    theo PHÚT, tự tìm model thay khi 404, thinkingConfig thấp, ghi lượt dùng vào tab Quota_SuDung (dòng "xưởng …").
  • Giữ nhánh gọi lại KHÔNG có công cụ chạy code khi model từ chối code_execution (như cdotGoiGemini_ ở Apps Script).
  • Phần bị cắt cụt (finishReason = MAX_TOKENS): thử lại cùng model với trần token gấp đôi; vẫn cụt thì bỏ model đó,
    sang model kế tiếp; hết model thì báo LOI (Apps Script soạn lại) thay vì đưa phần dở dang vào tài liệu.
  • Hạn tổng HAN_TONG_PHUT: quá hạn thì ghi LOI ngay, không để Apps Script chờ đủ 90 phút.
  • Runner GitHub huỷ / quá giờ (SIGINT, SIGTERM) → vẫn kịp ghi LOI.
  • Ghi tienDo ("2/5") vào ket_qua sau mỗi phần.
  • Không còn cắt mất dấu đóng ``` của khối JSON "KIỂM TRA SỐ"; nhận cả tiêu đề viết đậm **KIỂM TRA SỐ**.
Biến môi trường: GOOGLE_CREDENTIALS, GEMINI_API_KEY (+ _2 … _5, không bắt buộc), GOI_ID, KQ_ID.
Không dùng khoá trả phí (GEMINI_API_KEY_TRA_PHI không được truyền vào workflow này).
"""
import base64
import datetime as dt
import io
import json
import os
import re
import signal
import time

import gspread
import sympy
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

import doc_de as X   # goi_gemini dùng chung: xoay khoá, chờ 429 theo phút, ghi quota

ID_KHO_CHUNG = "1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc"
MODEL_MAC_DINH, MODEL_DU_PHONG_MAC_DINH = "gemini-3.8-flash", ["gemini-3.5-flash-lite"]
SAI_SO_CHO_PHEP = 0.02
TZ = dt.timezone(dt.timedelta(hours=7))
TRAN_TOKEN = [16384, 32768]        # lần đầu như Apps Script; bị cắt cụt thì thử lại với trần gấp đôi
HAN_TONG_PHUT = float(os.environ.get("HAN_TONG_PHUT", "48"))   # job GitHub tối đa 60 phút
T_BAT_DAU = time.time()

HetHanMuc = X.HetHanMuc

LUAT_KIEM_TRA_SO = (
    "\n\nCUỐI CÙNG, thêm đúng một mục \"## KIỂM TRA SỐ\" gồm MỘT khối ```json``` là mảng, mỗi phần tử cho một đáp số có tính toán "
    "(bỏ qua câu chỉ chọn lí thuyết): {\"cau\": \"III.2\", \"bieuThuc\": \"sqrt(2*20/9.8)\", \"dapSo\": 2.02, \"donVi\": \"s\"}. "
    "bieuThuc chỉ gồm số và + - * / ** ( ), sqrt, sin, cos, tan, asin, acos, atan, exp, log, pi, deg(...) để đổi độ sang rad; "
    "không dùng biến chữ; dapSo là số đúng như đã ghi trong đáp án (dấu chấm thập phân).")


# ---------------- KẾT NỐI GOOGLE ----------------
def ket_noi():
    raw_cred = os.environ["GOOGLE_CREDENTIALS"].strip()
    try:
        tt = json.loads(raw_cred)
    except Exception:
        try:
            tt = json.loads(base64.b64decode(raw_cred).decode("utf-8"))
        except Exception as e:
            raise ValueError("GOOGLE_CREDENTIALS không đúng định dạng JSON hoặc Base64 hợp lệ: " + str(e))
    if "private_key" in tt:
        tt["private_key"] = tt["private_key"].replace("\\n", "\n")
    # spreadsheets (đọc + ghi): cần để quota_xuong ghi lượt dùng vào tab Quota_SuDung của Kho chung
    cred = service_account.Credentials.from_service_account_info(
        tt, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(cred), build("drive", "v3", credentials=cred, cache_discovery=False)


def doc_tep(drive, fid):
    buf = io.BytesIO()
    tai = MediaIoBaseDownload(buf, drive.files().get_media(fileId=fid))
    xong = False
    while not xong:
        _, xong = tai.next_chunk()
    return json.loads(buf.getvalue().decode("utf-8") or "{}")


def ghi_tep(drive, fid, du_lieu):
    media = MediaIoBaseUpload(io.BytesIO(json.dumps(du_lieu, ensure_ascii=False).encode("utf-8")), mimetype="text/plain")
    drive.files().update(fileId=fid, media_body=media).execute()


def ds_model(gc):
    try:
        v = gc.open_by_key(ID_KHO_CHUNG).worksheet("CauHinh").get_all_values()[1:]
        cfg = {str(r[0]).strip(): str(r[1]).strip() for r in v if r and str(r[0]).strip()}
    except Exception as e:
        print("Không đọc được CauHinh, dùng model mặc định:", e)
        cfg = {}
    chinh = cfg.get("MODEL_CHINH") or MODEL_MAC_DINH
    du_phong = [m for m in re.split(r"[,;\s]+", cfg.get("MODEL_DU_PHONG", "")) if m] or MODEL_DU_PHONG_MAC_DINH
    return [chinh] + [m for m in du_phong if m != chinh]


# ---------------- GỌI GEMINI (cùng cách làm của cdotGoiGemini_ trong Apps Script) ----------------
def lay_chu(cand):
    """Có chạy code: lấy phần chữ SAU kết quả code cuối nếu nó đủ dài (bài hoàn chỉnh); không thì lấy toàn bộ chữ."""
    parts = (cand.get("content") or {}).get("parts") or []

    def chu_cua(ds):
        return "".join(p["text"] for p in ds if not p.get("thought") and isinstance(p.get("text"), str)).strip()

    vi_tri = -1
    for i, p in enumerate(parts):
        if "codeExecutionResult" in p or "code_execution_result" in p:
            vi_tri = i
    tat_ca = chu_cua(parts)
    sau = chu_cua(parts[vi_tri + 1:]) if vi_tri >= 0 else ""
    ra = sau if len(sau) > len(tat_ca) * 0.3 else tat_ca
    # Chỉ gỡ rào ``` khi CẢ BÀI bị bọc trong ```markdown … ```; không đụng tới khối ```json``` ở cuối (KIỂM TRA SỐ)
    dau = re.match(r"^```(?:markdown|md)?[ \t]*\n?", ra, re.I)
    if dau and (re.match(r"^```(?:markdown|md)\b", ra, re.I) or ra.count("```") % 2 == 1):
        ra = ra[dau.end():]
        ra = re.sub(r"\n?```\s*$", "", ra)
    return ra


def _tao_payload(he, nguoi, co_code, tran):
    p = {"systemInstruction": {"parts": [{"text": he}]},
         "contents": [{"role": "user", "parts": [{"text": nguoi}]}],
         "generationConfig": {"temperature": 0.5, "maxOutputTokens": tran}}
    if co_code:
        p["tools"] = [{"code_execution": {}}]
    return p


def _goi_mot_lan(he, nguoi, co_code, ds, tran):
    """Một lần gọi doc_de.goi_gemini; model từ chối công cụ chạy code → gọi lại không có công cụ."""
    try:
        return X.goi_gemini(_tao_payload(he, nguoi, co_code, tran), ds)
    except HetHanMuc:
        raise
    except RuntimeError as e:
        if co_code and re.search(r"code[_ ]?execution|tool", str(e), re.I):
            print("⚠️ Model không hỗ trợ chạy code – gọi lại không có công cụ.", flush=True)
            return X.goi_gemini(_tao_payload(he, nguoi, False, tran), ds)
        raise


def goi_gemini(he, nguoi, co_code, cac_model):
    """Trả (chữ, model). Hết hạn mức → HetHanMuc; lỗi khác / phần cụt ở mọi model → RuntimeError."""
    loai, loi = set(), []
    for _ in range(len(cac_model) + 4):                       # giới hạn vòng để không lặp vô hạn
        ds = [m for m in list(cac_model)[:6] if m not in loai]
        if not ds:
            break
        model = ds[0]
        for tran in TRAN_TOKEN:
            data, model = _goi_mot_lan(he, nguoi, co_code, ds if tran == TRAN_TOKEN[0] else [model], tran)
            cand = (data.get("candidates") or [{}])[0]
            text = lay_chu(cand)
            if cand.get("finishReason") == "MAX_TOKENS":
                print("✂️ %s bị cắt cụt ở trần %d token." % (model, tran), flush=True)
                continue
            if text.strip():
                return text, model
            loi.append("%s: phản hồi rỗng (%s)" % (model, cand.get("finishReason")))
            break
        else:
            loi.append("%s: bị cắt cụt (MAX_TOKENS) kể cả ở trần %d" % (model, TRAN_TOKEN[-1]))
        loai.add(model)
    raise RuntimeError(" | ".join(loi) or "Không gọi được Gemini")


# ---------------- KIỂM TRA SỐ BẰNG SYMPY (tuỳ chọn) ----------------
_X = sympy.Symbol("x")
CHO_PHEP = {"sqrt": sympy.sqrt, "sin": sympy.sin, "cos": sympy.cos, "tan": sympy.tan, "asin": sympy.asin, "acos": sympy.acos,
            "atan": sympy.atan, "exp": sympy.exp, "log": sympy.log, "ln": sympy.log, "pi": sympy.pi, "e": sympy.E,
            "deg": sympy.Lambda(_X, _X * sympy.pi / 180)}


def tinh(bieu_thuc):
    s = str(bieu_thuc).replace("^", "**").replace("×", "*").replace("·", "*").replace(",", ".")
    kiem = re.sub(r"\d(?:\.\d+)?[eE][-+]?\d+", "0", re.sub(r"\b(sqrt|sin|cos|tan|asin|acos|atan|exp|log|ln|pi|deg|e)\b", "", s))
    if re.search(r"[A-Za-z_]", kiem):
        raise ValueError("có biến chữ")
    if len(s) > 300:
        raise ValueError("biểu thức quá dài")
    if re.search(r"\*\*\s*\(?\s*-?\d{3,}", s):
        raise ValueError("số mũ quá lớn")
    return float(sympy.sympify(s, locals=CHO_PHEP, rational=False).evalf())


def tach_kiem_tra_so(md):
    m = re.search(r"^[#*\s]*KIỂM TRA SỐ.*$", md, re.M)
    if not m:
        return md, []
    phan = md[m.end():]
    j = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", phan, re.S) or re.search(r"(\[\s*\{.*\}\s*\])", phan, re.S)
    ds = []
    if j:
        try:
            ds = [x for x in json.loads(j.group(1)) if isinstance(x, dict)]
        except ValueError:
            ds = []
    return md[:m.start()].rstrip(), ds


def bang_kiem_tra_so(ds, so_phan):
    if not ds:
        return "", 0, 0
    dong = ["### Kiểm tra lại đáp số bằng code (sympy) – phần %s" % so_phan, "",
            "| Câu | Biểu thức | Đáp số đã ghi | Code tính lại | Kết quả |", "|---|---|---|---|---|"]
    sai = dem = 0
    for x in ds[:80]:
        cau, bt, dv = str(x.get("cau", "")), str(x.get("bieuThuc", "")), str(x.get("donVi", "") or "")
        try:
            ghi = float(str(x.get("dapSo")).replace(",", "."))
            gt = tinh(bt)
            lech = abs(gt - ghi) / max(abs(ghi), 1e-12) if ghi != 0 else abs(gt)
            dung = lech <= SAI_SO_CHO_PHEP
            dem += 1
            if not dung:
                sai += 1
            kq = "✔ khớp" if dung else "✘ LỆCH %.1f%% – cần xem lại" % (lech * 100)
            dong.append("| %s | `%s` | %s %s | %.4g | %s |" % (cau, bt.replace("|", "/"), ghi, dv, gt, kq))
        except Exception as e:
            dong.append("| %s | `%s` | %s | – | không tính được (%s) |" % (cau, bt.replace("|", "/"), x.get("dapSo"), str(e)[:40]))
    dong.append("")
    dong.append("Đã tính lại %d đáp số: %d khớp, %d lệch quá %d%%." % (dem, dem - sai, sai, int(SAI_SO_CHO_PHEP * 100)))
    return "\n".join(dong), dem, sai


# ---------------- CHẠY ----------------
def _bi_huy(signum, frame):
    raise KeyboardInterrupt("runner GitHub huỷ hoặc quá giờ (tín hiệu %s)" % signum)


def kiem_han():
    if time.time() - T_BAT_DAU > HAN_TONG_PHUT * 60:
        raise RuntimeError("Quá hạn tổng %.0f phút của xưởng – Apps Script sẽ soạn lại." % HAN_TONG_PHUT)


def main():
    try:
        signal.signal(signal.SIGTERM, _bi_huy)   # SIGINT mặc định đã là KeyboardInterrupt
    except (ValueError, OSError):
        pass
    gc, drive = ket_noi()
    goi_id, kq_id = os.environ["GOI_ID"], os.environ["KQ_ID"]
    goi = doc_tep(drive, goi_id)
    cac_model = ds_model(gc)
    print("Chuyên đề %s; model: %s" % (goi.get("ma"), ", ".join(cac_model)))
    ra, tieu_de, ban_tho, model_dung = {}, {}, {}, ""
    cac_bang, tong_dem, tong_sai = [], 0, 0
    ghi_tep(drive, kq_id, {"trangThai": "DANG_LAM", "luc": dt.datetime.now(TZ).isoformat()})
    try:
        cac_buoc = [b for b in goi["buoc"] if b]
        for b in cac_buoc:
            kiem_han()
            so = str(b["so"])
            td = str(b.get("tieuDe") or "")
            tieu_de[so] = td
            nguoi = b["nguoi"]
            nguoi = re.sub(r"\{\{PHAN_(\d+)\}\}", lambda m: ban_tho.get(m.group(1), "")[:14000], nguoi)
            if "{{RS_TL}}" in nguoi:
                truoc = [ban_tho[k] for k in sorted((k for k in ban_tho if int(k) < int(so)), key=int)]
                nguoi = nguoi.replace("{{RS_TL}}", "\n\n".join(truoc)[:120000])
            if b.get("kiemTraSo"):
                nguoi += LUAT_KIEM_TRA_SO
            t0 = time.time()
            text, model_dung = goi_gemini(b["he"], nguoi, b.get("coCode"), cac_model)
            if b.get("kiemTraSo"):
                text, ds = tach_kiem_tra_so(text)
                bang, dem, sai = bang_kiem_tra_so(ds, so)
                if bang:
                    cac_bang.append(bang)
                tong_dem += dem
                tong_sai += sai
            ra[so] = text
            ban_tho[so] = ("# " + td + "\n\n" if td else "") + text
            print("✅ Phần %s xong (%.0f giây, %d kí tự)" % (so, time.time() - t0, len(text)), flush=True)
            try:
                ghi_tep(drive, kq_id, {"trangThai": "DANG_LAM", "tienDo": "%d/%d" % (len(ra), len(cac_buoc)),
                                       "luc": dt.datetime.now(TZ).isoformat()})
            except Exception as e:
                print("Không ghi được tiến độ (bỏ qua):", str(e)[:100])
        # nối bảng kiểm tra số vào phần cuối (rà soát); cộng số chỗ lệch vào "SỐ CHỖ CẦN SỬA"
        if cac_bang and cac_buoc:
            cuoi = str(cac_buoc[-1]["so"])
            rs = ra.get(cuoi, "")
            m = re.search(r"SỐ CHỖ CẦN SỬA:\s*(\d+)", rs)
            if m and tong_sai:
                rs = rs[:m.start(1)] + str(int(m.group(1)) + tong_sai) + rs[m.end(1):]
            ra[cuoi] = rs.rstrip() + "\n\n" + "\n\n".join(cac_bang)
        kiem = ("%d đáp số, %d lệch" % (tong_dem, tong_sai)) if tong_dem else ""
        ghi_tep(drive, kq_id, {"trangThai": "XONG", "model": model_dung, "kiemTraSo": kiem, "tieuDe": tieu_de,
                               "buoc": ra, "luc": dt.datetime.now(TZ).isoformat()})
        print("📦 Đã ghi kết quả. Apps Script sẽ tạo Docs, Word trong vài phút.")
    except BaseException as e:   # gồm cả KeyboardInterrupt khi runner huỷ / quá giờ
        ly_do = "Runner GitHub huỷ hoặc quá giờ" if isinstance(e, KeyboardInterrupt) else str(e)
        try:
            ghi_tep(drive, kq_id, {"trangThai": "LOI", "loi": ly_do[:500], "luc": dt.datetime.now(TZ).isoformat()})
        except Exception:
            pass
        raise
    finally:
        Q = getattr(X, "Q", None)
        if Q:
            try:
                Q.ghi_sheet(gc.open_by_key(ID_KHO_CHUNG))
            except Exception as e:
                print("Không ghi được hạn mức (bỏ qua):", str(e)[:100])


if __name__ == "__main__":
    main()
