"""
tim_kiem.py – XƯỞNG TÌM KIẾM TÀI LIỆU (Python, GitHub Actions) cho Download Agent.

Vì sao: Download Agent tìm tài liệu bằng Google Search của Gemini; khoá miễn phí hay hết lượt hoặc "quota 0",
còn nguồn dự phòng (DuckDuckGo/Bing gọi từ máy chủ Apps Script) gần như luôn bị chặn → ~30% lượt "LỖI TÌM KIẾM".
Xưởng này tìm SẴN mỗi sáng từ máy GitHub (không bị chặn như Apps Script, không cần khoá Gemini):
  1. Đọc các chủ đề đang bật (tab ChuDe của "Download Agent - Quản lý") và các bài đang thiếu câu
     (tab DoPhu của Kho chung – đúng cách Download Agent dựng "phiếu yêu cầu").
  2. Mỗi chủ đề thử LẦN LƯỢT các truy vấn, dừng khi đủ kết quả (đỡ bị DuckDuckGo giới hạn):
       năm học hiện tại → năm học trước (tài liệu trên mạng thường ghi năm trước) → filetype:pdf → câu rút gọn
       (bỏ phần trong ngoặc, "Kết nối tri thức", "Chương"…). Tìm bằng DuckDuckGo (miễn phí); có BRAVE_API_KEY thì thêm Brave.
  3. Ghi kết quả vào tab KetQuaTim_DL của Kho chung. Download Agent (tệp TimKiemXuong.gs) đọc tab này
     khi Google Search của Gemini không dùng được, thay cho nguồn dự phòng bị chặn.
Biến môi trường: GOOGLE_CREDENTIALS; tuỳ chọn BRAVE_API_KEY.
"""
import datetime as dt, json, os, re, sys, time, unicodedata

import gspread
import requests
from google.oauth2 import service_account

ID_KHO_CHUNG = "1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc"
ID_BANG_DOWNLOAD = "1gL1q0LnOR4Ylr7ae-n-a20GBbo5nPkidrdEOnCZttio"
TAB_KQ = "KetQuaTim_DL"
TIEU_DE_KQ = ["Chủ đề", "Truy vấn", "Cập nhật", "Số kết quả", "Kết quả (JSON)", "Nguồn"]
SO_KET_QUA = 15          # đủ số này thì không thử truy vấn tiếp
SO_PHIEU = 12            # số bài thiếu câu (phiếu) tìm sẵn mỗi lượt
NGHI_GIUA_TRUY_VAN = 4   # giây – tránh bị DuckDuckGo giới hạn
TZ = dt.timezone(dt.timedelta(hours=7))
BO_TEN_MIEN = re.compile(r"(youtube\.com|youtu\.be|facebook\.com|tiktok\.com|instagram\.com|twitter\.com|x\.com|"
                         r"duckduckgo\.com|bing\.com|google\.com/search|pinterest\.)", re.I)


def bo_dau(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "d").lower()


def nam_hoc_hien_tai(lui=0):
    d = dt.datetime.now(TZ)
    y = (d.year if d.month >= 8 else d.year - 1) - lui
    return "%d-%d" % (y, y + 1)


def rut_gon(cd):
    """'Vật lí 11 Kết nối tri thức – Chương Sóng' → 'Vật lí 11 Sóng bài tập có đáp án'."""
    s = re.sub(r"\([^)]*\)", " ", cd)
    s = re.sub(r"(?i)\bkết nối tri thức\b|\bchương\b|\bTHPT không chuyên\b|[–—:|]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not re.search(r"(?i)đề|bài tập", s):
        s += " bài tập có đáp án"
    return s


def cac_truy_van(cd):
    ds = ["%s %s file PDF" % (cd, nam_hoc_hien_tai()), "%s %s file PDF" % (cd, nam_hoc_hien_tai(1)),
          "%s filetype:pdf" % cd, "%s pdf" % rut_gon(cd)]
    return list(dict.fromkeys(ds))


# ---------------- nguồn tìm kiếm ----------------
def tim_ddg(q):
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        for lan in range(2):
            try:
                with DDGS() as d:
                    return [{"url": r.get("href") or r.get("url"), "tieuDe": r.get("title", "")}
                            for r in d.text(q, region="vn-vi", max_results=SO_KET_QUA) or []]
            except Exception as e:
                if lan == 0 and re.search(r"(?i)rate|limit|202|429", str(e)):
                    print("  DuckDuckGo giới hạn tạm thời, chờ 30 giây rồi thử lại…", flush=True)
                    time.sleep(30)
                    continue
                if "No results" not in str(e):
                    print("  DuckDuckGo lỗi:", str(e)[:120])
                return []
    except ImportError as e:
        print("  Thiếu thư viện ddgs:", e)
        return []


def tim_brave(q):
    key = os.environ.get("BRAVE_API_KEY", "").strip()
    if not key:
        return []
    try:
        r = requests.get("https://api.search.brave.com/res/v1/web/search", params={"q": q, "count": SO_KET_QUA, "country": "vn"},
                         headers={"X-Subscription-Token": key, "Accept": "application/json"}, timeout=30)
        if r.status_code != 200:
            print("  Brave lỗi", r.status_code)
            return []
        return [{"url": x.get("url"), "tieuDe": x.get("title", "")} for x in (r.json().get("web") or {}).get("results", [])]
    except Exception as e:
        print("  Brave lỗi:", str(e)[:120])
        return []


def tim(ds_truy_van):
    kq, da_co, nguon, da_dung = [], set(), set(), []
    for q in ds_truy_van:
        if len(kq) >= SO_KET_QUA:
            break
        da_dung.append(q)
        for ten, ham in (("DuckDuckGo", tim_ddg), ("Brave", tim_brave)):
            ds = ham(q)
            if ds:
                nguon.add(ten)
            for r in ds:
                u = str(r.get("url") or "").strip()
                if not u.startswith("http") or u in da_co or BO_TEN_MIEN.search(u):
                    continue
                da_co.add(u)
                kq.append({"url": u, "tieuDe": re.sub(r"\s+", " ", str(r.get("tieuDe") or "")).strip()[:200]})
        time.sleep(NGHI_GIUA_TRUY_VAN)
    # ưu tiên link file trực tiếp lên trước
    kq.sort(key=lambda r: 0 if re.search(r"\.(pdf|docx?|xlsx?|pptx?|zip|rar)(\?|#|$)", r["url"], re.I) else 1)
    return kq[:SO_KET_QUA * 2], "+".join(sorted(nguon)) or "không có", da_dung


# ---------------- danh sách chủ đề cần tìm ----------------
def chu_de_dang_bat(gc):
    ds = []
    for r in gc.open_by_key(ID_BANG_DOWNLOAD).worksheet("ChuDe").get_all_values()[1:]:
        r = (r + [""] * 7)[:7]
        if r[0].strip() and str(r[1]).strip().upper() == "TRUE":
            ds.append(r[0].strip())
    return ds


def chu_de_phieu(kho):
    """Dựng tên chủ đề phiếu giống hệt chonPhieu_() của Download Agent (bài thiếu câu ở tab DoPhu)."""
    try:
        sh = kho.worksheet("DoPhu")
        nguong = float(sh.acell("L6").value or 3)
        uu_tien = {"11": 0, "12": 0, "10": 1}
        ten_muc = ["Nhận biết", "Thông hiểu", "Vận dụng"]
        ung = []
        for r in sh.get_all_values()[1:]:
            r = (r + [""] * 8)[:8]
            if not re.search(r"-B\d+$", r[0].strip()):
                continue
            so = lambda x: float(str(x).replace(",", ".") or 0) if re.match(r"^\s*[\d.,]+\s*$", str(x)) else 0
            thieu = [m for k, m in enumerate(ten_muc) if so(r[3 + k]) < nguong]
            if thieu:
                ung.append((uu_tien.get(r[1].strip(), 9), so(r[7]), r[1].strip(), r[2].strip(), ", ".join(thieu)))
        ung.sort()
        return ["Bài tập Vật lí %s Kết nối tri thức %s (câu %s) có đáp án" % (lop, ten, muc.lower())
                for _, _, lop, ten, muc in ung[:SO_PHIEU]]
    except Exception as e:
        print("Không đọc được DoPhu:", e)
        return []


def main():
    tt = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    print("Tài khoản dịch vụ:", tt.get("client_email"), flush=True)
    gc = gspread.authorize(service_account.Credentials.from_service_account_info(
        tt, scopes=["https://www.googleapis.com/auth/spreadsheets"]))
    kho = gc.open_by_key(ID_KHO_CHUNG)
    ds = chu_de_dang_bat(gc) + chu_de_phieu(kho)
    print("Năm học %s (thử cả %s) – %d chủ đề cần tìm sẵn." % (nam_hoc_hien_tai(), nam_hoc_hien_tai(1), len(ds)), flush=True)

    try:
        tab = kho.worksheet(TAB_KQ)
    except gspread.WorksheetNotFound:
        tab = kho.add_worksheet(TAB_KQ, rows=200, cols=len(TIEU_DE_KQ))
    luc = dt.datetime.now(TZ).strftime("%d/%m/%Y %H:%M")
    dong, tong, khong_co = [TIEU_DE_KQ], 0, 0
    for cd in ds:
        kq, nguon, da_dung = tim(cac_truy_van(cd))
        tong += len(kq)
        khong_co += 0 if kq else 1
        print("🔎 %-80s → %2d kết quả sau %d truy vấn (%s)" % (cd[:80], len(kq), len(da_dung), nguon), flush=True)
        dong.append([cd, " | ".join(da_dung), luc, len(kq), json.dumps(kq, ensure_ascii=False)[:45000], nguon])
    tab.clear()
    tab.update(range_name="A1", values=dong, value_input_option="RAW")
    print("📦 Đã ghi %d chủ đề (%d chủ đề không có kết quả), %d kết quả vào tab %s." % (len(ds), khong_co, tong, TAB_KQ))
    if ds and tong == 0:
        sys.exit("Không tìm được kết quả nào – nguồn tìm kiếm có thể đang bị chặn.")


if __name__ == "__main__":
    main()
