"""
dinh_dang_van_ban.py – DOCUMENT FORMATTER (Agent định dạng văn bản/đề thi chuẩn Nghị định 30/2020/NĐ-CP)
Đọc thông số lề trang, phông chữ từ trung_tam_dieu_phoi.json và chuẩn hóa tệp .docx.
"""
import os
import sys
import json
from docx import Document
from docx.shared import Cm, Pt

CONFIG_FILE = "trung_tam_dieu_phoi.json"


def doc_cau_hinh_nd30():
    mac_dinh = {
        "font_chu": "Times New Roman",
        "co_chu_noi_dung": 13,
        "le_tren_cm": 2.0,
        "le_duoi_cm": 2.0,
        "le_trai_cm": 3.0,
        "le_phai_cm": 1.5
    }
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f).get("DINH_DANG_NGHI_DINH_30", {})
                mac_dinh.update(cfg)
        except Exception:
            pass
    return mac_dinh


def chuan_hoa_nghi_dinh_30(input_docx, output_docx=None):
    if not os.path.isfile(input_docx):
        print(f"⚠️ Không tìm thấy tệp Word: {input_docx}")
        return
    cfg = doc_cau_hinh_nd30()
    doc = Document(input_docx)

    # 1. Thiết lập khổ giấy A4 và căn lề chuẩn Nghị định 30 (Trái 3cm, Phải 1.5cm, Trên 2cm, Dưới 2cm)
    for section in doc.sections:
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(cfg["le_tren_cm"])
        section.bottom_margin = Cm(cfg["le_duoi_cm"])
        section.left_margin = Cm(cfg["le_trai_cm"])
        section.right_margin = Cm(cfg["le_phai_cm"])

    # 2. Chuẩn hóa phông chữ Times New Roman và cỡ chữ 13pt
    style_normal = doc.styles["Normal"]
    style_normal.font.name = cfg["font_chu"]
    style_normal.font.size = Pt(cfg["co_chu_noi_dung"])

    for p in doc.paragraphs:
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.15
        for run in p.runs:
            run.font.name = cfg["font_chu"]
            run.font.size = Pt(cfg["co_chu_noi_dung"])

    ích = output_docx or input_docx
    doc.save(ích)
    print(f"✅ [Document Formatter]: Đã chuẩn hóa định dạng Nghị định 30 tại: {ích}")


if __name__ == "__main__":
    tep_vao = sys.argv[1] if len(sys.argv) > 1 else "de_thi_vat_li_chuan_anh.docx"
    tep_ra = sys.argv[2] if len(sys.argv) > 2 else tep_vao
    chuan_hoa_nghi_dinh_30(tep_vao, tep_ra)
