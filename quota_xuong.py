"""
quota_xuong.py – GHI LƯỢT DÙNG GEMINI / GROQ CỦA XƯỞNG PYTHON VÀO TAB Quota_SuDung (Kho chung)

Cùng khuôn với QuotaKhoChung.gs của Apps Script: mỗi NGÀY QUOTA (giờ Thái Bình Dương) × MODEL một dòng, dòng mới ở trên.
Các dòng của xưởng có tên model bắt đầu bằng "xưởng " (ví dụ "xưởng gemini-3.8-flash", "xưởng groq-gpt-oss-120b",
"xưởng gemini-3.8-flash [GEMINI_API_KEY_2]") để không trộn với lượt gọi của Apps Script.

Dùng:  import quota_xuong as Q
       Q.ghi_luot(Q.nhan_gemini(model, ten_khoa), ma_http, usage)   # sau mỗi lượt gọi
       Q.ghi_sheet(kho)                                              # một lần ở cuối lượt chạy
Mọi lỗi ở đây đều bị bỏ qua: ghi hạn mức hỏng không bao giờ làm hỏng việc chính.
"""
import datetime as dt

try:
    from zoneinfo import ZoneInfo
    _TZ_QUOTA, _TZ_VN = ZoneInfo("America/Los_Angeles"), ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:                                  # máy thiếu dữ liệu múi giờ: lấy gần đúng
    _TZ_QUOTA, _TZ_VN = dt.timezone(dt.timedelta(hours=-8)), dt.timezone(dt.timedelta(hours=7))

TAB = "Quota_SuDung"
COT = ["Ngày quota (giờ Mỹ)", "Model", "Lượt gọi", "Thành công", "Hết hạn mức (429)", "Lỗi khác", "Treo",
       "Token vào", "Token ra", "Lần gọi cuối (giờ VN)", "Giới hạn/ngày", "% đã dùng"]
SO_DONG_DOC = 80
_DEM = {}


def nhan_gemini(model, ten_khoa=""):
    ten = "xưởng " + str(model)
    if ten_khoa and ten_khoa != "GEMINI_API_KEY":
        ten += " [%s]" % ten_khoa
    return ten


def nhan_groq(model):
    return "xưởng groq-" + str(model).split("/")[-1]


def ghi_luot(nhan, ma_http=None, tk_vao=0, tk_ra=0, treo=False):
    try:
        d = _DEM.setdefault(nhan, {"goi": 0, "ok": 0, "q429": 0, "loi": 0, "treo": 0, "tkVao": 0, "tkRa": 0})
        d["goi"] += 1
        if treo:
            d["treo"] += 1
        elif ma_http == 200:
            d["ok"] += 1
            d["tkVao"] += int(tk_vao or 0)
            d["tkRa"] += int(tk_ra or 0)
        elif ma_http == 429:
            d["q429"] += 1
        else:
            d["loi"] += 1
    except Exception:
        pass


def token_gemini(data):
    u = (data or {}).get("usageMetadata") or {}
    return int(u.get("promptTokenCount") or 0), int(u.get("candidatesTokenCount") or 0) + int(u.get("thoughtsTokenCount") or 0)


def _so(x):
    try:
        return float(str(x).replace(",", ".")) if str(x).strip() != "" else 0
    except ValueError:
        return 0


def _ngay(x):
    return str(x or "").lstrip("'").strip()[:10]


def ghi_sheet(kho=None):
    """Cộng dồn số đếm của lượt chạy vào tab Quota_SuDung. Gọi một lần ở cuối lượt."""
    if not _DEM:
        return
    try:
        if kho is None:
            import doc_de as X
            gc, _, _ = X.ket_noi()
            kho = gc.open_by_key(X.ID_KHO_CHUNG)
        import gspread
        try:
            ws = kho.worksheet(TAB)
        except gspread.WorksheetNotFound:
            ws = kho.add_worksheet(TAB, rows=500, cols=len(COT))
            ws.update(range_name="A1", values=[COT], value_input_option="RAW")
        ngay = dt.datetime.now(_TZ_QUOTA).strftime("%Y-%m-%d")
        gio = dt.datetime.now(_TZ_VN).strftime("%H:%M %d/%m/%Y")
        for nhan in list(_DEM):
            d = _DEM[nhan]
            # đọc lại ngay trước khi ghi (Apps Script có thể vừa chèn dòng mới ở trên)
            dong = ws.get("A2:L%d" % (SO_DONG_DOC + 1), value_render_option="UNFORMATTED_VALUE") or []
            i = next((k for k, r in enumerate(dong) if len(r) > 1 and _ngay(r[0]) == ngay and str(r[1]) == nhan), -1)
            if i >= 0:
                r = (dong[i] + [""] * 12)[:12]
                ws.update(range_name="C%d:J%d" % (i + 2, i + 2), value_input_option="RAW", values=[[
                    _so(r[2]) + d["goi"], _so(r[3]) + d["ok"], _so(r[4]) + d["q429"], _so(r[5]) + d["loi"],
                    _so(r[6]) + d["treo"], _so(r[7]) + d["tkVao"], _so(r[8]) + d["tkRa"], gio]])
            else:
                truoc = next((r for r in dong if len(r) > 1 and str(r[1]) == nhan), None)
                gioi_han = (truoc + [""] * 12)[10] if truoc else ""
                ws.insert_row(["'" + ngay, nhan, d["goi"], d["ok"], d["q429"], d["loi"], d["treo"], d["tkVao"], d["tkRa"],
                               gio, gioi_han, '=IF(N(K2)=0,"",C2/K2)'], index=2, value_input_option="USER_ENTERED")
                try:
                    ws.format("L2", {"numberFormat": {"type": "PERCENT", "pattern": "0%"}})
                except Exception:
                    pass
            del _DEM[nhan]
        print("📈 Đã ghi lượt dùng của xưởng vào tab %s." % TAB, flush=True)
    except Exception as e:
        print("⚠️ Không ghi được hạn mức vào %s (bỏ qua): %s" % (TAB, str(e)[:150]), flush=True)
