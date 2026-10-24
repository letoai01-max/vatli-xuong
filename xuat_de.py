import os
import requests
import io
from docx import Document
from docx.shared import Inches

def xuat_de_co_anh(worksheet, danh_sach_cau_hoi_chon, file_output="DeThi.docx"):
    doc = Document()
    doc.add_heading("ĐỀ KIỂM TRA VẬT LÍ", level=1)

    all_values = worksheet.get_all_values()
    
    for idx, row_num in enumerate(danh_sach_cau_hoi_chon, start=1):
        row_vals = all_values[row_num - 1] # row_num tính từ 1, list từ 0
        
        # Cột G (index 2) là nội dung câu hỏi, Cột W (index 22) là link ảnh
        noi_dung = row_vals[1] if len(row_vals) > 1 else ""
        link_anh = row_vals[22].strip() if len(row_vals) > 22 else ""

        # Ghi nội dung câu hỏi
        doc.add_paragraph(f"Câu {idx}: {noi_dung}")

        # Nếu cột W có link ảnh, tự động tải và chèn vào Word
        if link_anh.startswith("http"):
            try:
                response = requests.get(link_anh)
                if response.status_code == 200:
                    image_stream = io.BytesIO(response.content)
                    doc.add_picture(image_stream, width=Inches(3.5)) # Chỉnh kích thước ảnh tùy ý
            except Exception as e:
                print(f"Không tải được ảnh dòng {row_num}: {e}")

    doc.save(file_output)
    print(f"✨ Đã xuất đề thành công ra file: {file_output}")
