danh_sach_json = []
    
    # Duyệt qua từng dòng trong bảng tính
    for row in all_values:
        # Lấy giá trị các cột quan trọng
        ma_cau = row[0].strip() if len(row) > 0 else ""     # Cột A: Mã câu
        noi_dung = row[6].strip() if len(row) > 6 else ""   # Cột G: Nội dung câu hỏi
        phuong_an = row[7].strip() if len(row) > 7 else ""  # Cột H: Phương án
        dap_an = row[8].strip() if len(row) > 8 else ""     # Cột I: Đáp án
        trang_thai = row[20].strip() if len(row) > 20 else "" # Cột U: Trạng thái
        link_anh = row[22].strip() if len(row) > 22 else ""   # Cột W: Link ảnh GitHub
        
        # BỘ LỌC CHUẨN XÁC: Chỉ lấy dòng nào có mã câu bắt đầu bằng 'C-' hoặc chứa mã hợp lệ, 
        # đồng thời Cột G phải có nội dung câu hỏi thực sự (loại bỏ hoàn toàn các dòng tiêu đề, tổng số tiết,...)
        if ma_cau.startswith("C-") and noi_dung:
            danh_sach_json.append({
                "ma_cau": ma_cau,
                "noi_dung": noi_dung,
                "phuong_an": phuong_an,
                "dap_an": dap_an,
                "trang_thai": trang_thai,
                "link_anh": link_anh
            })
