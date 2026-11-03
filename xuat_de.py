"""
xuat_de.py – XUẤT NGÂN HÀNG CÂU HỎI ra questions.json (TỰ ĐỘNG LỌC TẬN GỐC)

[Hàng 4 – bản sửa]
  • Chỉ mục trùng được tính TRỰC TIẾP từ dữ liệu vừa đọc (qua chi_muc_trung.py) → câu mới thêm trong ngày cũng được lọc.
    Nếu không import/tính được thì tự lùi về đọc tab ChiMucTrung như cũ.
  • Câu giống chữ >= ngưỡng nhưng KHÁC ĐÁP ÁN với câu có trước: KHÔNG bỏ, vẫn xuất kèm trường "canh_bao" để người xem.
"""
import json, os, re, sys
import gspread
from google.oauth2.service_account import Credentials

try:
    import chi_muc_trung as CM
except Exception as e:           # thiếu doc_de.py... → dùng tab ChiMucTrung
    CM = None
    print("ℹ️ Không nạp được chi_muc_trung (%s) – sẽ đọc tab ChiMucTrung." % e)

ID_KHO_CHUNG = os.environ.get("SHEET_ID") or "1o49XTyBaxqT4NNR2TvRWSW5C2PPHKamRv8MTSeqdsQc"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

def ket_noi():
    raw = os.environ.get("GOOGLE_CREDENTIALS", "").strip()
    if raw:
        return gspread.authorize(Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES))
    if os.path.isfile("credentials.json"):
        return gspread.authorize(Credentials.from_service_account_file("credentials.json", scopes=SCOPES))
    sys.exit("Thiếu GOOGLE_CREDENTIALS.")

def doc_nut(kho):
    """Đọc tab CauHinh (cột A = tên nút, cột B = giá trị)."""
    try:
        return {str(r[0]).strip(): (str(r[1]).strip() if len(r) > 1 else "")
                for r in kho.worksheet("CauHinh").get_all_values()[1:] if r and str(r[0]).strip()}
    except Exception:
        return {}


def doc_chi_muc(kho):
    """{mã câu: [(mã câu giống, % giống chữ), ...]} từ tab ChiMucTrung (chi_muc_trung.py ghi mỗi đêm). Không có tab -> None."""
    try:
        v = kho.worksheet("ChiMucTrung").get_all_values()[1:]
    except Exception:
        return None
    kq = {}
    for r in v:
        r = r + [""] * 11
        if not r[0].strip():
            continue
        ds = []
        for k in (1, 4, 7):
            ma, chu = r[k].strip(), r[k + 1].strip().replace(",", ".")
            try:
                if ma:
                    ds.append((ma, float(chu)))
            except ValueError:
                pass
        kq[r[0].strip()] = ds
    return kq


def chi_muc_moi(d, nut):
    """Tính chỉ mục NGAY từ bảng d vừa đọc (luôn mới). Lỗi → None để lùi về tab ChiMucTrung."""
    if CM is None:
        return None
    try:
        kq = CM.tinh_chi_muc(CM.doc_cau(d), CM.doc_nguong_ghi(nut))
        return {ma: [(m, float(chu)) for m, chu, _ in ds] for ma, ds in kq}
    except Exception as e:
        print("⚠️ Không tính được chỉ mục trực tiếp (%s) – dùng tab ChiMucTrung." % e)
        return None


def chuan_dap_an(s):
    """Chuẩn hoá đáp án để so: chữ thường, bỏ khoảng trắng và dấu câu cuối ("A." = "a", "50 m" = "50m")."""
    return re.sub(r"\s+", "", str(s or "").lower()).strip(".,;:")


def loc_trung(ds, chi_muc, vi_tri, loai, nguong, dap_an_ca_kho=None):
    """Bỏ câu có bản GIỐNG CHỮ >= nguong với một câu ĐẾN TRƯỚC nó trong ngân hàng (câu trước không bị 'Loại').
    Chỉ bỏ câu sau, giữ câu trước -> cặp trùng không bao giờ mất cả hai.
    Nếu hai câu giống chữ mà ĐÁP ÁN KHÁC NHAU (một trong hai có thể sai) -> giữ lại, gắn "canh_bao".
    Trả về (giữ, số_bỏ, danh_sách_cảnh_báo)."""
    dap_an_ca_kho = dap_an_ca_kho or {}
    giu, bo, canh_bao = [], 0, []
    for x in ds:
        ma = x["ma_cau"]
        goc = next(((m, chu) for m, chu in chi_muc.get(ma, [])
                    if chu >= nguong and m in vi_tri and m not in loai and vi_tri[m] < vi_tri.get(ma, 0)), None)
        if goc is None:
            giu.append(x)
            continue
        da_nay = chuan_dap_an(x.get("dap_an"))
        da_goc = chuan_dap_an(dap_an_ca_kho.get(goc[0]))
        if da_nay and da_goc and da_nay != da_goc:
            msg = "Giống chữ %.0f%% với câu %s nhưng KHÁC ĐÁP ÁN – kiểm tra xem câu nào đúng." % (goc[1], goc[0])
            giu.append(dict(x, canh_bao=msg))
            canh_bao.append((ma, goc[0], goc[1]))
        else:
            bo += 1
    return giu, bo, canh_bao


def main():
    gc = ket_noi()
    kho = gc.open_by_key(ID_KHO_CHUNG)
    d = kho.worksheet("NganHangCauHoi").get_all_values()
    
    if not d or len(d) < 2:
        sys.exit("Tab NganHangCauHoi trống hoặc không đủ dữ liệu.")
        
    td = [t.strip() for t in d[0]]
    td_thap = [t.lower() for t in td]   # [Mục 22] so tên cột không phân biệt hoa thường ("Link Ảnh" / "Link ảnh")
    cot = lambda ten: td_thap.index(ten.lower()) if ten.lower() in td_thap else None
    
    c = {
        "ma_cau": cot("Mã câu") if cot("Mã câu") is not None else 0,
        "noi_dung": cot("Nội dung") if cot("Nội dung") is not None else 6,
        "phuong_an": cot("Phương án") if cot("Phương án") is not None else 7,
        "dap_an": cot("Đáp án") if cot("Đáp án") is not None else 8,
        "loi_giai": cot("Lời giải / HDC") if cot("Lời giải / HDC") is not None else 9,
        "trang_thai": cot("Trạng thái duyệt") if cot("Trạng thái duyệt") is not None else 20,
        "link_anh": cot("Link ảnh") if cot("Link ảnh") is not None else 22
    }

    lay = lambda r, idx: (r[idx].strip() if idx is not None and idx < len(r) else "")
    
    ds, vi_tri, loai, dap_an_ca_kho = [], {}, set(), {}
    for i, r in enumerate(d[1:]):
        ma = lay(r, c["ma_cau"])
        nd = lay(r, c["noi_dung"])
        trang_thai = lay(r, c["trang_thai"]).lower()
        if ma:
            vi_tri.setdefault(ma, i)                 # thứ tự dòng = thứ tự vào ngân hàng
            dap_an_ca_kho.setdefault(ma, lay(r, c["dap_an"]))   # đáp án của MỌI câu (kể cả đã duyệt) để so khi nghi trùng
            if "loại" in trang_thai:
                loai.add(ma)
        
        # 💡 ĐIỀU KIỆN LỌC TẬN GỐC:
        # Chỉ lấy các câu bắt đầu bằng "C-" VÀ trạng thái phải là CHƯA DUYỆT 
        # (nghĩa là bỏ qua mọi câu đã có chữ "ai duyệt", "đã duyệt" hoặc "loại").
        is_da_duyet = "ai duyệt" in trang_thai or "đã duyệt" in trang_thai or "loại" in trang_thai
        
        if not ma.startswith("C-") or len(nd) <= 5 or is_da_duyet:
            continue
            
        ds.append({
            "ma_cau": ma,
            "noi_dung": nd,
            "phuong_an": lay(r, c["phuong_an"]),
            "dap_an": lay(r, c["dap_an"]),
            "loi_giai": lay(r, c["loi_giai"]),
            "trang_thai": lay(r, c["trang_thai"]),
            "link_anh": lay(r, c["link_anh"])
        })
        
    nut = doc_nut(kho)
    bo_trung, canh_bao = 0, []
    if nut.get("KIEM_TRA_TRUNG_LAP", "true").lower() in ("false", "0", "no", "off", "tat", "tắt"):
        print("ℹ️ KIEM_TRA_TRUNG_LAP đang tắt – không lọc trùng.")
    else:
        chi_muc = chi_muc_moi(d, nut)
        if chi_muc is None:
            chi_muc = doc_chi_muc(kho)
            if chi_muc is not None:
                print("ℹ️ Dùng chỉ mục từ tab ChiMucTrung (câu mới thêm sau lượt chạy gần nhất có thể chưa được lọc).")
        if chi_muc is None:
            print("⚠️ Không có chỉ mục trùng – xuất không lọc trùng.")
        else:
            try:
                nguong = min(100.0, max(50.0, float(nut["NGUONG_TRUNG_CHEP"])))
            except (KeyError, ValueError):
                nguong = 90.0
            ds, bo_trung, canh_bao = loc_trung(ds, chi_muc, vi_tri, loai, nguong, dap_an_ca_kho)

    with open("questions.json.tmp", "w", encoding="utf-8") as f:   # ghi file tạm rồi mới thay, tránh file hỏng giữa chừng
        json.dump(ds, f, ensure_ascii=False, indent=2)
    os.replace("questions.json.tmp", "questions.json")

    print(f"✨ Đã xuất {len(ds)} câu hỏi chưa duyệt vào questions.json (bỏ {bo_trung} câu trùng câu có trước).")
    if canh_bao:
        print(f"⚠️ {len(canh_bao)} câu giống chữ câu có trước nhưng KHÁC ĐÁP ÁN (giữ lại, có trường canh_bao):")
        for ma, goc, chu in canh_bao[:20]:
            print(f"   {ma} ~ {goc} ({chu:.0f}%)")

if __name__ == "__main__":
    main()
