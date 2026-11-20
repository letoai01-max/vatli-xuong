"""
kiem_thu_doc_de_nen.py – KIỂM THỬ ĐỌC FILE NÉN của doc_de.py (chạy không cần khoá, không gọi mạng).
[20/11/2026] Giả lập thư viện Google/gspread khi thiếu; kiểm giải nén zip (tên tiếng Việt, lồng 1 cấp, bỏ __MACOSX/file ẩn),
giới hạn zip bomb, công tắc CHO_PHEP_DOC_NEN và cách ghi tên file nguồn. Sai kết quả mong đợi thì thoát mã khác 0.
"""
import importlib, io, os, sys, types, zipfile

THU_MUC = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THU_MUC)
for ten in ["gspread", "latex_chuan", "google", "google.oauth2", "google.oauth2.service_account", "googleapiclient",
            "googleapiclient.discovery", "googleapiclient.http", "requests"]:
    try:
        importlib.import_module(ten)
    except ImportError:
        sys.modules[ten] = types.ModuleType(ten)
sys.modules["google.oauth2"].service_account = sys.modules["google.oauth2.service_account"]
sys.modules["googleapiclient.discovery"].build = lambda *a, **k: None
sys.modules["googleapiclient.http"].MediaIoBaseDownload = object
if not hasattr(sys.modules["latex_chuan"], "chuan_hoa_latex"):
    sys.modules["latex_chuan"].chuan_hoa_latex = lambda x: x

import doc_de as D

LOI = []


def kiem(dieu_kien, mo_ta):
    print(("✅ " if dieu_kien else "❌ ") + mo_ta)
    if not dieu_kien:
        LOI.append(mo_ta)


def tao_zip(muc, utf8=True):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for ten, nd in muc:
            z.writestr(ten, nd)
    return buf.getvalue()


PDF = b"%PDF-1.4\n%test\n"
ANH = b"\x89PNG\r\n\x1a\n" + b"0" * 20

# 1. Zip thường: giữ PDF/ảnh, bỏ rác
z = tao_zip([("Đề 1.pdf", PDF), ("thu/anh.png", ANH), ("__MACOSX/._Đề 1.pdf", b"x"), (".DS_Store", b"x"),
             ("~$tam.docx", b"x"), ("ghi chu.txt", b"x"), ("thu/", b"")])
ten = sorted(t for t, _ in D.giai_nen(z))
kiem(ten == ["thu/anh.png", "Đề 1.pdf"], "zip: giữ PDF + ảnh, bỏ __MACOSX, file ẩn, ~$, .txt, thư mục (được %s)" % ten)

# 2. Tên tiếng Việt kiểu zip cũ (byte UTF-8 nhưng KHÔNG có cờ UTF-8 → Python đọc ra cp437) được sửa lại
ten_that = "Đề thi.pdf".encode("utf-8")
cho = b"A" * len(ten_that)                      # ghi tên giả bằng ASCII rồi thay byte thật vào, giữ cờ UTF-8 = 0
zbytes = tao_zip([(cho.decode(), PDF)]).replace(cho, ten_that)
kiem([t for t, _ in D.giai_nen(zbytes)] == ["Đề thi.pdf"], "zip cũ (không cờ UTF-8): tên file tiếng Việt khôi phục đúng")

# 3. Tệp nén lồng 1 cấp
trong = tao_zip([("sâu.pdf", PDF)])
phan = D.tep_tu_nen(tao_zip([("ngoài.pdf", PDF), ("gói.zip", trong)]), "x.zip")
kiem(sorted(p["ten"] for p in phan) == ["ngoài.pdf", "sâu.pdf"], "lồng 1 cấp: đọc được cả file ngoài lẫn file trong")
trong2 = tao_zip([("sâu2.pdf", PDF)])
phan = D.tep_tu_nen(tao_zip([("a.zip", tao_zip([("b.zip", trong2)]))]), "x.zip")
kiem(phan == [], "lồng 2 cấp trở lên: bỏ qua (không đệ quy vô hạn)")

# 4. Phần trả về có đủ khoá cho Gemini
p = D.tep_tu_nen(tao_zip([("a.pdf", PDF), ("b.png", ANH)]), "x.zip")
kiem(all({"data", "mime", "ten"} <= set(x) for x in p) and {x["mime"] for x in p} == {"application/pdf", "image/png"},
     "mỗi phần có data / mime / ten, đúng mime PDF và PNG")

# 5. Chặn zip bomb và quá nhiều file
mo_ta = D.GIOI_HAN_GIAI_NEN
D.GIOI_HAN_GIAI_NEN = 1000
try:
    D.giai_nen(tao_zip([("a.pdf", b"0" * 5000)]))
    kiem(False, "vượt dung lượng giải nén phải báo lỗi")
except RuntimeError:
    kiem(True, "vượt dung lượng giải nén → báo lỗi")
D.GIOI_HAN_GIAI_NEN = mo_ta
so_cu = D.GIOI_HAN_SO_FILE_NEN
D.GIOI_HAN_SO_FILE_NEN = 3
try:
    D.giai_nen(tao_zip([("f%d.pdf" % i, PDF) for i in range(5)]))
    kiem(False, "quá nhiều file phải báo lỗi")
except RuntimeError:
    kiem(True, "quá nhiều file → báo lỗi")
D.GIOI_HAN_SO_FILE_NEN = so_cu

# 6. Định dạng lạ / rar khi chưa cài rarfile
try:
    D.giai_nen(b"khong phai tep nen")
    kiem(False, "dữ liệu lạ phải báo lỗi")
except RuntimeError:
    kiem(True, "dữ liệu không phải zip/rar → báo lỗi rõ ràng")
try:
    import rarfile  # noqa: F401
    kiem(True, "rarfile đã cài (bỏ qua ca thiếu thư viện)")
except ImportError:
    try:
        D.giai_nen(b"Rar!\x1a\x07\x00" + b"0" * 20)
        kiem(False, "thiếu rarfile phải báo lỗi hướng dẫn cài")
    except RuntimeError as e:
        kiem("rarfile" in str(e), "thiếu rarfile → báo lỗi có hướng dẫn cài")

# 7. Nhận dạng tệp nén
kiem(D.la_tep_nen("application/zip", "a") and D.la_tep_nen("", "Đề.RAR") and D.la_tep_nen("", "x.zip"), "la_tep_nen nhận zip/rar theo mime và đuôi")
kiem(not D.la_tep_nen("application/pdf", "a.pdf") and not D.la_tep_nen("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "a.docx"),
     "la_tep_nen KHÔNG nhận nhầm PDF và Word (docx vốn là zip bên trong)")

# 8. Tên file nguồn của câu hỏi
viec = {"id": "ABCDEFGH1234", "ten": "bo-de.zip", "link": "https://drive/x", "chu_de": "HSG"}
yccd = {"hop_le": set()}
d = {"loai_de": "HSG", "lop": 12}
r1 = D.tao_dong_cau_hoi({"so_cau": "1", "dang": "TL", "noi_dung": "A", "_nguon": "Đề 1.pdf"}, 0, d, viec, yccd, "t")
r2 = D.tao_dong_cau_hoi({"so_cau": "2", "dang": "TL", "noi_dung": "B"}, 1, d, viec, yccd, "t")
r3 = D.tao_dong_cau_hoi({"so_cau": "3", "dang": "TL", "noi_dung": "C", "_nguon": "bo-de.zip"}, 2, d, viec, yccd, "t")
vt = D.COT_NH.index("Tên file")
kiem(r1[vt] == "bo-de.zip › Đề 1.pdf (câu 1)", "câu từ file con: ghi 'tệp nén › file con (câu N)' (được %r)" % r1[vt])
kiem(r2[vt] == "bo-de.zip (câu 2)" and r3[vt] == "bo-de.zip (câu 3)", "câu không thuộc file con: tên file giữ như cũ")
kiem([r1[0], r2[0], r3[0]] == ["C-ABCDEFGH-001", "C-ABCDEFGH-002", "C-ABCDEFGH-003"], "mã câu đánh số liên tục")

# 9. Công tắc: tắt thì chuan_bi_tep_day_du trả về 'chưa hỗ trợ' như bản cũ
class GiaDrive:
    def __init__(self, mime, ten, noidung):
        self.mime, self.ten, self.nd = mime, ten, noidung
    def files(self):
        return self
    def get(self, **k):
        return types.SimpleNamespace(execute=lambda: {"name": self.ten, "mimeType": self.mime, "size": str(len(self.nd))})

du = tao_zip([("a.pdf", PDF)])
D.tai_ve = lambda drive, fid, xuat_pdf=False: du
D.CHO_PHEP_DOC_NEN = True
kq = D.chuan_bi_tep_day_du(GiaDrive("application/zip", "bo.zip", du), "id")
kiem(kq.get("tu_nen") is True and len(kq["phan"]) == 1, "công tắc BẬT: zip → 1 phần, đánh dấu tu_nen")
D.CHO_PHEP_DOC_NEN = False
kq = D.chuan_bi_tep_day_du(GiaDrive("application/zip", "bo.zip", du), "id")
kiem("bo_qua" in kq and "chưa hỗ trợ" in kq["bo_qua"], "công tắc TẮT: zip bị bỏ qua y như bản cũ")
D.CHO_PHEP_DOC_NEN = True
kq = D.chuan_bi_tep_day_du(GiaDrive("application/zip", "rong.zip", tao_zip([("ghi chu.txt", b"x")])), "id") if False else None
D.tai_ve = lambda drive, fid, xuat_pdf=False: tao_zip([("ghi chu.txt", b"x")])
kq = D.chuan_bi_tep_day_du(GiaDrive("application/zip", "rong.zip", b"x"), "id")
kiem("bo_qua" in kq and "không có" in kq["bo_qua"], "zip không chứa PDF/Word/ảnh → 'Bỏ qua' kèm lý do")

print("\n" + ("TẤT CẢ ĐẠT" if not LOI else "CÓ %d CA SAI" % len(LOI)))
sys.exit(1 if LOI else 0)
