import os
import json
import base64
import gspread
from google.oauth2.service_account import Credentials
from docx import Document
from docx.shared import Cm, Pt

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def ket_noi_sheet():
    raw_cred = os.environ.get("GOOGLE_CREDENTIALS", "").strip()
    if raw_cred:
        try:
            tt = json.loads(raw_cred, strict=False)
        except Exception:
            tt = json.loads(base64.b64decode(raw_cred).decode("utf-8"), strict=False)
        if "private_key" in tt:
            tt["private_key"] = tt["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(tt, scopes=SCOPES)
    elif os.path.isfile("credentials.json"):
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    else:
        raise RuntimeError("Không tìm thấy GOOGLE_CREDENTIALS hoặc credentials.json!")
    return gspread.authorize(creds)

def don_rac_tab_ppct(sh):
    """Xóa chữ 'Từ chối' bị ghi nhầm vào Cột J và Cột U của tab Kiem_tra_PPCT"""
    try:
        ws_ppct = sh.worksheet("Kiem_tra_PPCT")
        vals = ws_ppct.get_all_values()
        updates = []
        for r_idx, row in enumerate(vals, start=1):
            for c_idx in range(4, len(row)):  # Từ cột E trở đi (ngoài bảng A:D)
                if row[c_idx].strip():
                    col_letter = gspread.utils.rowcol_to_a1(r_idx, c_idx + 1)
                    updates.append({"range": col_letter, "values": [[""]]})
        if updates:
            ws_ppct.batch_update(updates)
            print(f"🧹 Đã dọn sạch {len(updates)} ô bị ghi nhầm trên tab Kiem_tra_PPCT.")
    except Exception as e:
        print(f"Lưu ý khi kiểm tra tab Kiem_tra_PPCT: {e}")

def xuat_du_lieu():
    client = ket_noi_sheet()
    sheet_id = os.environ.get("SHEET_ID", "").strip()
    if not sheet_id and os.path.isfile("trung_tam_dieu_phoi.json"):
        with open("trung_tam_dieu_phoi.json", "r", encoding="utf-8") as f:
            sheet_id = json.load(f).get("SHEET_CONFIG", {}).get("SHEET_ID", "")

    sh = client.open_by_key(sheet_id)
    don_rac_tab_ppct(sh)

    sheet = sh.worksheet("NganHangCauHoi")
    all_values = sheet.get_all_values()

    danh_sach_json = []
    for row in all_values[1:]:
        ma_cau = row[0].strip() if len(row) > 0 else ""       # Cột A: Mã câu
        lop = row[3].strip() if len(row) > 3 else ""          # Cột D: Lớp
        muc_do = row[4].strip() if len(row) > 4 else ""       # Cột E: Mức độ
        dang = row[5].strip() if len(row) > 5 else ""         # Cột F: Dạng
        noi_dung = row[6].strip() if len(row) > 6 else ""     # Cột G: Nội dung
        phuong_an = row[7].strip() if len(row) > 7 else ""    # Cột H: Phương án
        dap_an = row[8].strip() if len(row) > 8 else ""       # Cột I: Đáp án
        loi_giai = row[9].strip() if len(row) > 9 else ""     # Cột J: Lời giải / HDC
        kiem_tra = row[19].strip() if len(row) > 19 else ""   # Cột T: Kiểm tra (5 tầng)
        trang_thai = row[20].strip() if len(row) > 20 else "" # Cột U: Trạng thái duyệt
        link_anh = row[22].strip() if len(row) > 22 else ""   # Cột W: Link ảnh

        if ma_cau.startswith("C-") and len(noi_dung) > 5:
            danh_sach_json.append({
                "ma_cau": ma_cau,
                "lop": lop,
                "muc_do": muc_do,
                "dang": dang,
                "noi_dung": noi_dung,
                "phuong_an": phuong_an,
                "dap_an": dap_an,
                "loi_giai": loi_giai,
                "kiem_tra": kiem_tra,
                "trang_thai": trang_thai,
                "link_anh": link_anh
            })

    # Ưu tiên xếp các câu "Cần người xem" lên đầu để giáo viên duyệt ngay trên giao diện
    uu_tien = [q for q in danh_sach_json if "cần người xem" in q["trang_thai"].lower() or "chưa duyệt" in q["trang_thai"].lower()]
    con_lai = [q for q in danh_sach_json if q not in uu_tien]
    ket_qua_xuat = uu_tien + con_lai

    with open("questions.json", "w", encoding="utf-8") as f:
        json.dump(ket_qua_xuat, f, ensure_ascii=False, indent=2)
    print(f"✨ Đã xuất {len(ket_qua_xuat)} câu hỏi ({len(uu_tien)} câu cần duyệt) vào questions.json!")

    # Tạo lại DeThi.docx chuẩn từ 40 câu đầu tiên đã duyệt
    doc = Document()
    for section in doc.sections:
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(3.0)
        section.right_margin = Cm(1.5)
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(13)

    doc.add_heading("ĐỀ KIỂM TRA VẬT LÍ (TRÍCH NGÂN HÀNG CÂU HỎI)", level=1)
    mau_de = [q for q in danh_sach_json if "loại" not in q["trang_thai"].lower()][:40]
    for idx, q in enumerate(mau_de, start=1):
        p = doc.add_paragraph()
        run_title = p.add_run(f"Câu {idx} [{q['ma_cau']} - Lớp {q['lop']}]: ")
        run_title.bold = True
        p.add_run(q["noi_dung"])
        if q["phuong_an"]:
            for pa in q["phuong_an"].split("\n"):
                if pa.strip():
                    doc.add_paragraph(pa.strip())
    doc.save("DeThi.docx")
    print("📄 Đã cập nhật DeThi.docx chuẩn Nghị định 30!")

if __name__ == "__main__":
    xuat_du_lieu()
