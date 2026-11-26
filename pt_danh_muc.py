"""
pt_danh_muc.py – DANH MỤC, CẤU TRÚC ĐỀ VÀ NGƯỠNG MẶC ĐỊNH CỦA HỆ THỐNG PHÂN TÍCH ĐỀ TN THPT (Vật lí).

Mọi giá trị ở đây là MẶC ĐỊNH; Apps Script có thể ghi đè bằng gói việc (goi.danhMuc, goi.cauTruc, goi.mucTieu, goi.thoiGianPhut)
đọc từ tab PT_CauHinh của Google Sheet, nên đổi chuẩn không cần sửa code Python.
"""

MUC = ("NB", "TH", "VD", "VDC")
TEN_MUC = {"NB": "Nhận biết", "TH": "Thông hiểu", "VD": "Vận dụng", "VDC": "Vận dụng cao"}
LA_MA = {1: "I", 2: "II", 3: "III", 4: "IV"}

# Chương trình GDPT 2018, sách Kết nối tri thức (khớp tên chương dùng trong Kho chung; sửa ở tab PT_CauHinh nếu cần).
DANH_MUC_MAC_DINH = [
    {"lop": 10, "ma": "10.1", "ten": "Mở đầu (sai số, đơn vị, đại lượng vật lí)"},
    {"lop": 10, "ma": "10.2", "ten": "Động học"},
    {"lop": 10, "ma": "10.3", "ten": "Động lực học"},
    {"lop": 10, "ma": "10.4", "ten": "Công, năng lượng, công suất"},
    {"lop": 10, "ma": "10.5", "ten": "Động lượng"},
    {"lop": 10, "ma": "10.6", "ten": "Chuyển động tròn"},
    {"lop": 10, "ma": "10.7", "ten": "Biến dạng của vật rắn"},
    {"lop": 11, "ma": "11.1", "ten": "Dao động"},
    {"lop": 11, "ma": "11.2", "ten": "Sóng"},
    {"lop": 11, "ma": "11.3", "ten": "Trường điện"},
    {"lop": 11, "ma": "11.4", "ten": "Dòng điện, mạch điện"},
    {"lop": 12, "ma": "12.1", "ten": "Vật lí nhiệt"},
    {"lop": 12, "ma": "12.2", "ten": "Khí lí tưởng"},
    {"lop": 12, "ma": "12.3", "ten": "Từ trường"},
    {"lop": 12, "ma": "12.4", "ten": "Vật lí hạt nhân và phóng xạ"},
    {"lop": 0, "ma": "KHAC", "ten": "Khác / liên môn / ngoài danh mục"},
]

# Cấu trúc đề tham chiếu (dạng thức thi TN THPT từ 2025): 18 TN + 4 Đúng/Sai + 6 trả lời ngắn = 10 điểm, 50 phút.
CAU_TRUC_MAC_DINH = {
    "1": {"dang": "TN", "so_cau": 18, "diem_cau": 0.25},
    "2": {"dang": "DS", "so_cau": 4, "diem_y": [0.25, 0.25, 0.25, 0.25]},   # điểm danh nghĩa mỗi ý (cách chấm thật 0,1/0,25/0,5/1 chỉ dùng khi tính điểm)
    "3": {"dang": "TLN", "so_cau": 6, "diem_cau": 0.25},
}
THOI_GIAN_PHUT_MAC_DINH = 50

# Tỉ lệ điểm mục tiêu theo mức nhận thức: chỉ để so sánh, KHÔNG phải quy định – giáo viên đặt lại ở tab PT_CauHinh.
MUC_TIEU_MAC_DINH = {"NB": 0.40, "TH": 0.30, "VD": 0.20, "VDC": 0.10}
DUNG_SAI_MUC_TIEU = 0.10        # lệch quá ngưỡng này (theo điểm) thì nhận xét

NANG_LUC = ["Nhận thức vật lí", "Tìm hiểu thế giới tự nhiên dưới góc độ vật lí", "Vận dụng kiến thức, kĩ năng đã học"]
DANG_BAI = ["Lí thuyết – khái niệm", "Tính toán trực tiếp", "Tính toán nhiều bước", "Đồ thị – bảng số liệu",
            "Thực nghiệm – xử lí số liệu", "Tình huống thực tiễn", "Đọc hiểu – ngữ cảnh"]

# [25/11/2026] Bản tiêu chí cũ giữ lại làm TIEU_CHI_MUC_CU: tắt công tắc tuyChon.nhanThucV2 thì xưởng chạy y như trước.
TIEU_CHI_MUC_CU = (
    "TIÊU CHÍ MỨC ĐỘ (dùng nhất quán):\n"
    "- NB (Nhận biết): nhớ / nhận ra khái niệm, định luật, đơn vị, công thức; thay số 1 bước; đọc trực tiếp một giá trị từ hình, đồ thị, bảng.\n"
    "- TH (Thông hiểu): giải thích hiện tượng, so sánh, suy luận 1–2 bước; tính toán 2 bước với công thức quen thuộc; đọc đồ thị để suy ra đại lượng khác.\n"
    "- VD (Vận dụng): giải bài toán nhiều bước (≥ 3) kết hợp ≥ 2 kiến thức; mô hình hoá tình huống thực tiễn; xử lí số liệu thí nghiệm.\n"
    "- VDC (Vận dụng cao): tổng hợp liên chương, nhiều bước (≥ 4) cần biến đổi toán học phức tạp, lập luận hoặc đề xuất phương án mới, đồ thị phức tạp.\n"
    "Câu Đúng/Sai: phân loại RIÊNG TỪNG Ý a, b, c, d (thường a, b mức thấp hơn c, d). Chọn mức theo yêu cầu tư duy thật, không theo vị trí câu trong đề."
)


# ====================================================================================================================
# [25/11/2026] BỘ TIÊU CHÍ NHẬN DIỆN MỨC ĐỘ NHẬN THỨC – chép từ "Bảng tiêu chí nhận biết các mức độ nhận thức trong môn Vật lí THPT".
# Một nguồn duy nhất cho cả lượt 1 (phan_tich_kien_thuc), lượt 2 (phan_loai_nhan_thuc) và trọng tài (phan_xu_nhan_thuc).
# Giáo viên có thể ghi đè toàn văn bằng goi.tieuChiMuc (tab PT_CauHinh) mà không sửa code.
# ====================================================================================================================
TIEU_CHI_KHOA = ("huy_dong_kien_thuc", "xu_li_du_kien", "lua_chon_phuong_phap", "so_buoc_lap_luan", "do_moi_tinh_huong", "yeu_cau_ket_qua")
TEN_TIEU_CHI = {
    "huy_dong_kien_thuc": "Huy động kiến thức", "xu_li_du_kien": "Xử lí dữ kiện", "lua_chon_phuong_phap": "Lựa chọn phương pháp",
    "so_buoc_lap_luan": "Số bước lập luận", "do_moi_tinh_huong": "Độ mới của tình huống", "yeu_cau_ket_qua": "Yêu cầu kết quả"}

DANG_CAU_HOI = ["Khái niệm, định nghĩa", "Định luật, nguyên lí", "Công thức", "Đơn vị đo", "Hiện tượng vật lí", "Hình vẽ, sơ đồ", "Đồ thị",
                "Bảng số liệu", "Bài toán định lượng", "Thí nghiệm", "Tình huống thực tiễn", "Nhận định đúng/sai", "So sánh, phân biệt",
                "Dự đoán kết quả", "Thiết kế, đề xuất giải pháp"]

# Bộ quy tắc gợi ý (mục VII của bảng tiêu chí): mã → (mô tả, mức gợi ý). "Xem xét VD/VDC" = gợi ý, không phải kết luận.
QUY_TAC = {
    "NB01": ("Nhớ công thức, định luật, khái niệm trực tiếp", "NB"),
    "NB02": ("Nhận diện đại lượng, đơn vị, kí hiệu", "NB"),
    "TH01": ("Thay số trực tiếp vào công thức quen thuộc", "TH"),
    "TH02": ("Giải thích hiện tượng bằng một kiến thức đã học", "TH"),
    "TH03": ("Đọc và hiểu thông tin trực tiếp từ đồ thị", "TH"),
    "VD01": ("Phải tự lựa chọn công thức hoặc phương pháp giải", "VD"),
    "VD02": ("Phải phối hợp nhiều kiến thức để giải quyết nhiệm vụ", "VD"),
    "VD03": ("Phải xử lí dữ liệu, phân tích nhiều giai đoạn", "VD"),
    "VDC01": ("Phải xây dựng chiến lược giải quyết vấn đề phức hợp", "VDC"),
    "VDC02": ("Phải đánh giá, phản biện hoặc tối ưu phương án", "VDC"),
    "VDC03": ("Phải thiết kế thí nghiệm hoặc đề xuất giải pháp mới", "VDC"),
}

_T_NGUYEN_TAC = (
    "NGUYÊN TẮC CỐT LÕI: phân loại theo HOẠT ĐỘNG TƯ DUY THỰC SỰ mà học sinh bắt buộc phải thực hiện để hoàn thành yêu cầu; "
    "KHÔNG dựa vào động từ, độ dài câu, số phép tính, hình thức trình bày (trắc nghiệm / đúng-sai / có hình / có số liệu thực tế). "
    "Động từ chỉ là dấu hiệu tham khảo: phải đọc toàn bộ câu hỏi, dữ kiện, yêu cầu và điều kiện giải.\n"
    "KHÔNG MẶC ĐỊNH: nhiều phép tính ⇒ VDC; có đồ thị ⇒ VD; có tình huống thực tế ⇒ VDC; nhiều dữ kiện ⇒ VDC; câu dài ⇒ khó. "
    "'Số bước lập luận' là số bước SUY LUẬN/chọn chiến lược, không phải số phép tính: nhiều phép thay số lần lượt vào công thức cho sẵn vẫn chỉ là TH."
)

_T_BON_MUC = (
    "BỐN MỨC (nhận diện tổng quát):\n"
    "- NB (Nhận biết): NHỚ, NHẬN RA. Một kiến thức trực tiếp; dữ kiện trực tiếp, đầy đủ; nhớ/nhận ra công thức; không tính hoặc rất đơn giản; "
    "không cần lập luận; đồ thị/bảng chỉ đọc trực tiếp một giá trị; tình huống quen thuộc; kết quả là thông tin trực tiếp.\n"
    "- TH (Thông hiểu): HIỂU, GIẢI THÍCH. Hiểu một kiến thức / một quan hệ giữa các đại lượng; dữ kiện trực tiếp hoặc biến đổi đơn giản; "
    "thay số trực tiếp vào công thức quen thuộc; giải thích, so sánh đơn giản theo tiêu chí quen thuộc; đồ thị: giải thích ý nghĩa độ dốc/diện tích/quan hệ đơn giản; "
    "kết quả là kết luận có giải thích.\n"
    "- VD (Vận dụng): ÁP DỤNG, CHỌN VÀ SỬ DỤNG kiến thức để giải quyết vấn đề. Một hoặc nhiều kiến thức; dữ kiện cần xử lí/suy luận; tự chọn, biến đổi và phối hợp công thức; "
    "chuỗi suy luận có trình tự; khai thác đồ thị/bảng để tính toán; tình huống có biến đổi hoặc gắn thực tế; kết quả là giải quyết được nhiệm vụ.\n"
    "- VDC (Vận dụng cao): PHÂN TÍCH, TỔNG HỢP, TỰ XÂY DỰNG CHIẾN LƯỢC giải quyết vấn đề phức hợp. Nhiều kiến thức phối hợp (có thể liên chương/liên môn); "
    "dữ kiện phân tán, ẩn hoặc dư; thiết lập hệ thức phức hợp; nhiều giai đoạn, kết hợp điều kiện; lập luận nhiều bước, đánh giá phương án; tình huống mới, phức tạp; "
    "kết quả là giải pháp / đánh giá / kết luận có lập luận sâu.\n"
)

_T_SAU_TIEU_CHI = (
    "SÁU TIÊU CHÍ (điền tieu_chi: mỗi tiêu chí một mức NB/TH/VD/VDC; không cộng điểm máy móc, xem xét tổng thể):\n"
    "1. huy_dong_kien_thuc: NB một kiến thức trực tiếp | TH hiểu một kiến thức | VD một hoặc nhiều kiến thức | VDC nhiều kiến thức phối hợp.\n"
    "2. xu_li_du_kien: NB nhận diện dữ kiện | TH hiểu, xử lí đơn giản | VD chọn lọc, biến đổi | VDC dữ kiện phức tạp, có thể dư hoặc ẩn.\n"
    "3. lua_chon_phuong_phap: NB không cần lựa chọn | TH lựa chọn quen thuộc | VD tự lựa chọn | VDC xây dựng chiến lược.\n"
    "4. so_buoc_lap_luan: NB không hoặc rất ít | TH một bước đơn giản | VD nhiều bước liên tiếp | VDC nhiều giai đoạn, có điều chỉnh.\n"
    "5. do_moi_tinh_huong: NB đã học trực tiếp | TH quen thuộc | VD có biến đổi | VDC mới hoặc phức tạp.\n"
    "6. yeu_cau_ket_qua: NB nhận diện, tái hiện | TH giải thích, xác định | VD giải quyết vấn đề | VDC đánh giá, đề xuất, tối ưu.\n"
)

_T_DANG_CAU_HOI = (
    "NHẬN DIỆN THEO DẠNG CÂU HỎI (điền dang_cau_hoi là MỘT trong 15 dạng; NB | TH | VD | VDC):\n"
    "1. Khái niệm, định nghĩa: nhận ra/nêu đúng | diễn giải bản chất | dùng khái niệm giải quyết tình huống | phân tích tình huống phức tạp bằng nhiều khái niệm.\n"
    "2. Định luật, nguyên lí: phát biểu/nhận diện | giải thích ý nghĩa, điều kiện áp dụng | áp dụng giải bài toán | kết hợp nhiều định luật.\n"
    "3. Công thức: nhớ/nhận diện | hiểu quan hệ giữa các đại lượng | chọn, biến đổi, kết hợp công thức | thiết lập hệ thức hoặc tìm cách giải tối ưu.\n"
    "4. Đơn vị đo: nhận biết tên, kí hiệu | giải thích quan hệ giữa các đơn vị | đổi đơn vị và dùng trong bài toán | xử lí hệ đơn vị nhiều đại lượng.\n"
    "5. Hiện tượng vật lí: nhận ra tên/đặc điểm | giải thích nguyên nhân, bản chất | giải thích hiện tượng thực tế | phân tích hiện tượng nhiều yếu tố.\n"
    "6. Hình vẽ, sơ đồ: nhận diện bộ phận, kí hiệu | giải thích cấu tạo, nguyên lí | phân tích sơ đồ để tính toán | phân tích, lựa chọn, đề xuất phương án thiết kế.\n"
    "7. Đồ thị: đọc giá trị, điểm, trục, đơn vị | giải thích ý nghĩa độ dốc/diện tích/quan hệ đơn giản | khai thác để tính toán, suy ra đại lượng | phân tích nhiều giai đoạn, rút ra quy luật.\n"
    "8. Bảng số liệu: đọc, nhận ra giá trị | nhận xét xu hướng, so sánh | tính toán, xử lí, rút kết luận | phân tích, đánh giá quy luật, dự đoán, kiểm chứng.\n"
    "9. Bài toán định lượng: xác định đại lượng, công thức trực tiếp | thay số trực tiếp vào công thức quen thuộc | lựa chọn phương pháp, giải nhiều bước | nhiều giai đoạn, nhiều điều kiện hoặc tối ưu.\n"
    "10. Thí nghiệm: nhận biết dụng cụ, thao tác | hiểu quy trình, mục đích, nguyên lí | xử lí số liệu, xác định kết quả | thiết kế thí nghiệm, đánh giá sai số, đề xuất cải tiến.\n"
    "11. Tình huống thực tiễn: nhận diện kiến thức liên quan | giải thích tình huống quen thuộc | tính toán/đề xuất cách giải quyết | đánh giá, so sánh, lựa chọn giải pháp phức tạp.\n"
    "12. Nhận định đúng/sai: xác định đúng sai dựa trên kiến thức ghi nhớ | phân tích, giải thích nhận định | kết hợp kiến thức để kiểm tra nhận định | phản biện nhận định nhiều điều kiện.\n"
    "13. So sánh, phân biệt: nhận ra điểm khác trực tiếp | so sánh theo tiêu chí quen thuộc | phân tích để chọn phương án phù hợp | đánh giá nhiều phương án theo tiêu chí và ràng buộc.\n"
    "14. Dự đoán kết quả: nhận ra kết quả trực tiếp | dự đoán từ quy luật quen thuộc | dự đoán bằng công thức và dữ kiện | dự đoán trong tình huống nhiều biến số.\n"
    "15. Thiết kế, đề xuất giải pháp: nhận biết phương án/thiết bị có sẵn | giải thích lựa chọn phương án | vận dụng kiến thức đề xuất giải pháp phù hợp | xây dựng, so sánh, tối ưu và bảo vệ giải pháp.\n"
)

_T_NHAM_LAN = (
    "CÁC TRƯỜNG HỢP DỄ NHẦM (áp dụng đúng):\n"
    "- Hỏi công thức tính tốc độ ⇒ NB (chỉ nhớ). Cho quãng đường, thời gian, tính tốc độ ⇒ TH (thay số trực tiếp).\n"
    "- Đồ thị v–t, tính độ dịch chuyển bằng diện tích hình đơn giản ⇒ TH (VD nếu phải chia vùng / xử lí dữ liệu). Đồ thị x–t, xác định vận tốc từ độ dốc ⇒ TH. "
    "Đồ thị phức tạp, vận tốc trung bình qua nhiều giai đoạn ⇒ VD.\n"
    "- Nhiều phép tính nhưng chỉ lần lượt thay số vào công thức cho sẵn ⇒ TH (số phép tính không quyết định mức). Một phép tính nhưng phải tự suy luận chọn công thức ⇒ có thể VD.\n"
    "- Số liệu thực tế nhưng áp dụng công thức trực tiếp ⇒ TH (bối cảnh thực tế không tự động nâng mức).\n"
    "- Đúng/sai yêu cầu nhớ định luật ⇒ NB (hình thức đúng/sai không quyết định mức). Đúng/sai yêu cầu phân tích nhiều mối quan hệ vật lí ⇒ VD hoặc VDC.\n"
    "- Có hình ảnh, sơ đồ mạch điện ⇒ NB, TH, VD hoặc VDC tuỳ yêu cầu xử lí hình. Thiết kế thí nghiệm kiểm chứng giả thuyết ⇒ thường VDC.\n"
)

_T_QUY_TRINH = (
    "QUY TRÌNH QUYẾT ĐỊNH (làm lần lượt 6 bước trước khi kết luận):\n"
    "B1 Yêu cầu thực sự: HS cần nhớ, giải thích, tính toán hay giải quyết vấn đề? "
    "B2 Kiến thức huy động: một kiến thức trực tiếp hay phải kết hợp nhiều? "
    "B3 Dữ kiện: có sẵn, cần biến đổi, hay phải tự tìm mối quan hệ? "
    "B4 Suy luận: không cần, đơn giản, hay nhiều bước? "
    "B5 Độc lập: làm theo cách quen thuộc hay tự chọn chiến lược? "
    "B6 Kết luận: chọn mức CAO NHẤT thực sự được thể hiện bởi yêu cầu tư duy BẮT BUỘC, không dựa vào hình thức trình bày.\n"
)

_T_QUY_TAC = ("BỘ QUY TẮC (điền ma_quy_tac: 1–3 mã ĐÚNG với câu; VD/VDC chỉ là 'xem xét', phải có đủ điều kiện mới chọn mức đó):\n" +
              "\n".join("%s: %s → %s" % (k, v[0], v[1]) for k, v in QUY_TAC.items()) + "\n")

_T_DS = ("CÂU ĐÚNG/SAI: phân loại RIÊNG TỪNG Ý a, b, c, d theo đúng yêu cầu tư duy của ý đó (thường a, b thấp hơn c, d). "
         "Mức của cả câu = mức cao nhất trong 4 ý. Không mặc định ý nào là VD/VDC chỉ vì nó đứng cuối.")

# ---------- [25/11/2026] KHUNG CỦA BỘ GD&ĐT (tài liệu "Cấp độ tư duy và bảng năng lực – đề minh hoạ TN THPT môn Vật lí", QĐ 764/QĐ-BGDĐT)
# Bộ dùng BA cấp độ Biết / Hiểu / Vận dụng và đếm theo LỆNH HỎI (Phần I, III: mỗi câu 1; Phần II: mỗi ý 1; cả đề 28 câu = 40 lệnh hỏi).
# Bốn mức NB/TH/VD/VDC của bảng tiêu chí vẫn giữ để giáo viên xem chi tiết; khi báo cáo theo Bộ thì VDC gộp vào Vận dụng.
MUC3 = ("Biết", "Hiểu", "Vận dụng")
GOP_MUC3 = {"NB": "Biết", "TH": "Hiểu", "VD": "Vận dụng", "VDC": "Vận dụng"}
TONG_LENH_HOI_MINH_HOA = 40
SO_LENH_HOI_MINH_HOA = {"Biết": 16, "Hiểu": 12, "Vận dụng": 12}          # 40% – 30% – 30%; chỉ là tham chiếu của đề minh hoạ, KHÔNG phải tỉ lệ bắt buộc
# Bảng năng lực – cấp độ tư duy của đề minh hoạ: {thành phần năng lực: {phần: {cấp độ: số lệnh hỏi}}}
BANG_NANG_LUC_MINH_HOA = {
    "Nhận thức vật lí":                                   {"I": {"Biết": 7, "Hiểu": 1, "Vận dụng": 2}, "II": {"Biết": 1, "Hiểu": 2, "Vận dụng": 1}, "III": {"Biết": 1, "Hiểu": 1, "Vận dụng": 1}},
    "Tìm hiểu thế giới tự nhiên dưới góc độ vật lí":      {"I": {"Biết": 1, "Hiểu": 0, "Vận dụng": 0}, "II": {"Biết": 1, "Hiểu": 2, "Vận dụng": 1}, "III": {"Biết": 0, "Hiểu": 0, "Vận dụng": 0}},
    "Vận dụng kiến thức, kĩ năng đã học":                 {"I": {"Biết": 1, "Hiểu": 5, "Vận dụng": 1}, "II": {"Biết": 4, "Hiểu": 0, "Vận dụng": 4}, "III": {"Biết": 0, "Hiểu": 1, "Vận dụng": 2}},
}

_T_KHUNG_BO = (
    "KHUNG CẤP ĐỘ CỦA BỘ GD&ĐT (đối chiếu khi phân loại): Biết = huy động, nhận ra, tái hiện thông tin / kiến thức / biểu thức vật lí đã học "
    "(KHÔNG đồng nhất với 'câu chỉ có lí thuyết': phải xét yêu cầu thực tế). Hiểu = diễn giải, giải thích, mô tả, đọc hiểu và phân tích thông tin, hiện tượng, quy luật hoặc dữ liệu "
    "(có thể gặp ở câu định tính, đồ thị, bảng số liệu hoặc tính toán đơn giản). Vận dụng = dùng kiến thức, kĩ năng, lập luận vật lí để xử lí dữ liệu, giải quyết nhiệm vụ / tình huống "
    "(không căn cứ riêng vào độ dài câu hỏi hay việc có phép tính). Tương ứng: NB = Biết · TH = Hiểu · VD và VDC = Vận dụng (VDC chỉ là mức chi tiết trong Vận dụng, hãy giữ VDC cho câu thật sự đòi hỏi chiến lược phức hợp)."
)
NANG_LUC_MO_TA = {
    "Nhận thức vật lí": "nhận biết, nêu, giải thích, diễn giải kiến thức / khái niệm / quy luật vật lí; dùng ngôn ngữ vật lí",
    "Tìm hiểu thế giới tự nhiên dưới góc độ vật lí": "quan sát, thí nghiệm, đọc / xử lí đồ thị và số liệu thực nghiệm, đặt giả thuyết, kiểm chứng, dự đoán, rút kết luận từ dữ liệu",
    "Vận dụng kiến thức, kĩ năng đã học": "dùng kiến thức, công thức, kĩ năng để giải bài toán và tình huống thực tiễn, đề xuất giải pháp",
}
_T_NANG_LUC = ("THÀNH PHẦN NĂNG LỰC (nang_luc) là một CHIỀU KHÁC với cấp độ tư duy: chọn thành phần mà câu hỏi hướng tới, độc lập với mức Biết/Hiểu/Vận dụng. "
               "Chỉ dùng đúng một trong ba tên sau (câu Đúng/Sai: điền nang_luc riêng cho từng ý trong y_ds):\n" +
               "\n".join("- %s: %s" % kv for kv in NANG_LUC_MO_TA.items()) + "\n")

# Văn bản dùng trong lời nhắc (đưa vào cả ba lượt gọi AI để cùng một chuẩn).
TIEU_CHI_MUC = "\n".join(["TIÊU CHÍ MỨC ĐỘ NHẬN THỨC (dùng nhất quán):", _T_NGUYEN_TAC, _T_BON_MUC, _T_SAU_TIEU_CHI, _T_DANG_CAU_HOI,
                          _T_NHAM_LAN, _T_QUY_TRINH, _T_QUY_TAC, _T_DS, _T_KHUNG_BO, _T_NANG_LUC])

# Ngưỡng và hằng số cho khối chốt mức / trọng tài / báo cáo theo chương.
MAX_PHAN_XU = 24                 # tối đa số câu gửi trọng tài mỗi lượt (giữ hạn mức Gemini)
DO_DAI_NOI_DUNG_CHUONG = 300     # số kí tự nội dung mỗi câu trong mục "theo chương" (0 = đủ toàn văn)
DO_DAI_PHUONG_AN_CHUONG = 150

# Nhận diện đề do Bộ GD&ĐT phát hành (đáp án chính thức): xem pt_so_khop.la_de_bo(). Có thể ép bằng goi.tuyChon.nguonDapAnChot = "bo" | "khong".
