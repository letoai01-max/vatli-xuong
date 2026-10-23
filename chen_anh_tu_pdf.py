import os
import subprocess
from docx import Document
from docx.shared import Inches

def trich_xuat_anh_tu_pdf(pdf_path, output_dir):
    """Trích xuất toàn bộ hình ảnh, đồ thị từ file PDF gốc bằng pdfimages (poppler)"""
    os.makedirs(output_dir, exist_ok=True)
    prefix = os.path.join(output_dir, "img")
    try:
        subprocess.run(["pdfimages", "-png", pdf_path, prefix], check=True)
        print(f"Đã trích xuất ảnh thành công vào thư mục: {output_dir}")
    except Exception as e:
        print(f"Lỗi khi trích xuất ảnh bằng pdfimages: {e}")

def chen_anh_vao_file_word(docx_path, image_dir, output_docx_path):
    """
    Quét file Word thô do hệ thống xuất ra, tìm các đoạn có chứa [Hình: ...] hoặc [Đồ thị: ...]
    và tự động chèn ảnh PNG tương ứng từ thư mục image_dir vào ngay dưới đoạn đó.
    """
    doc = Document(docx_path)
    
    # Lấy danh sách các file ảnh đã tách ra và sắp xếp theo thứ tự
    anh_hop_le = sorted([os.path.join(image_dir, f) for f in os.listdir(image_dir) if f.endswith('.png')])
    anh_index = 0

    for p in doc.paragraphs:
        # Kiểm tra xem đoạn văn có chứa từ khóa mô tả hình ảnh không
        if "[Hình:" in p.text or "[Đồ thị" in p.text or "[Mạch điện" in p.text:
            print(f"Phát hiện vị trí có hình: {p.text}")
            
            if anh_index < len(anh_hop_le):
                anh_path = anh_hop_le[anh_index]
                try:
                    # Chèn ảnh vào tệp Word với chiều rộng chuẩn (5.5 inches)
                    p.add_run().add_picture(anh_path, width=Inches(5.5))
                    print(f"-> Đã chèn ảnh {os.path.basename(anh_path)} thành công.")
                    anh_index += 1
                except Exception as ex:
                    print(f"Lỗi khi chèn ảnh vào docx: {ex}")
            else:
                print("-> Đã hết ảnh trong kho để chèn.")

    # Lưu lại file Word hoàn chỉnh có kèm hình ảnh
    doc.save(output_docx_path)
    print(f"Đã lưu file Word hoàn chỉnh tại: {output_docx_path}")

if __name__ == "__main__":
    # Cấu hình đường dẫn file đầu vào và đầu ra khi chạy trên GitHub Actions hoặc máy
    file_pdf_goc = "de_thi_goc.pdf"
    thu_muc_anh = "./extracted_images"
    file_docx_tho = "de_thi_xuat_ra.docx"
    file_docx_hoan_chinh = "de_thi_vat_li_chuan_anh.docx"

    # Thực thi quy trình
    trich_xuat_anh_tu_pdf(file_pdf_goc, thu_muc_anh)
    
    if os.path.exists(file_docx_tho):
        chen_anh_vao_file_word(file_docx_tho, thu_muc_anh, file_docx_hoan_chinh)
    else:
        print(f"Không tìm thấy file Word thô: {file_docx_tho}")
