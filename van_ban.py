"""
van_ban.py – KHUNG chuyển vbChay (Agent văn bản, Apps Script) sang xưởng Python.

Luồng, thứ tự và điều kiện bám đúng vbChay đã gửi. Các hàm trợ giúp (vbNguon_, vbDocNguon_, vbPhanLoai_, vbDocSau_...)
CHƯA có code gốc nên để ở dạng khung (NotImplementedError) kèm hợp đồng suy ra từ chỗ gọi; khi có code gốc sẽ điền.
Quy tắc: ghi vào ĐÚNG các tab/cột mà Apps Script đang dùng, để TuHoc.gs (thNhanDeXuatVanBan_), vbMailQuanTrong_,
vbNhacHan_, vbBanTinTuan_ vẫn chạy như cũ.
"""
import os
import sys
import time

GIAY_TOI_DA = 22 * 60          # ngân sách mỗi lượt (giữ quỹ phút GitHub); workflow còn có timeout-minutes
SO_DOC_MOI_LUOT = 5            # TODO: lấy đúng giá trị VB.SO_DOC_MOI_LUOT trong code gốc
LO_PHAN_LOAI = 25              # vbChay gửi Gemini phân loại 25 mục mỗi lần
T0 = time.time()


def con_gio(du_tru=0):
    """Tương đương vbConGio_(duTru): còn thời gian không?"""
    return (time.time() - T0) < GIAY_TOI_DA - du_tru


# ---------------- Hàm trợ giúp: điền khi có code gốc ----------------
def ap_dung_de_xuat():            # vbApDungDeXuat_()
    raise NotImplementedError

def nap_lich_su_dang_bat():       # đọc VB_NAP_LICH_SU: chuyển cờ này từ Thuộc tính sang tab CauHinh của Kho chung
    raise NotImplementedError

def tat_nap_lich_su():            # tương đương p.deleteProperty('VB_NAP_LICH_SU')
    raise NotImplementedError

def khoa_da_co():                 # vbKhoaDaCo_() -> {khoa: {'hang': số dòng hoặc None}}
    raise NotImplementedError

def dau_nam_hoc():                # vbDauNamHoc_() -> ngày (date) đầu năm học
    raise NotImplementedError

def danh_sach_nguon():            # vbNguon_() -> [{'ten','coQuan','soTrang'}]
    raise NotImplementedError

def doc_nguon(n, so_trang):       # vbDocNguon_(n, soTrang) -> [{'soHieu','trichYeu','ngay',...}]
    raise NotImplementedError

def tao_khoa(x):                  # vbKhoa_(x)
    raise NotImplementedError

def chuan_ngay(s):                # vbNgay_(s) -> date hoặc None
    raise NotImplementedError

def ghi_nguon(n, kq):             # vbGhiNguon_(n, kq)
    raise NotImplementedError

def ghi_da_xet(rows):             # vbGhiDaXet_(rows): [khoa, trích yếu[:300], kết luận, thời gian]
    raise NotImplementedError

def phan_loai(lo):                # vbPhanLoai_(lo) -> [{'lienQuan': 'cao'|'trung_binh'|..., 'lyDo': str}]
    raise NotImplementedError

def doc_sau(x):                   # vbDocSau_(x): tải bản gốc lên Drive + Gemini đọc -> {'lienQuan': ..., ...}
    raise NotImplementedError

def bo_sung_tep(x, hang):         # vbBoSungTep_(x, hang)
    raise NotImplementedError

def ghi_quan_trong(ds):           # thay cho vbMailQuanTrong_: ghi vào tab, Apps Script (MailApp) gửi thư
    raise NotImplementedError

LOAI_TRU = None                   # VB_LOAI_TRU: regex lấy từ code gốc
UU_TIEN = None                    # VB_UU_TIEN: regex lấy từ code gốc


# ---------------- Luồng chính (bám sát vbChay) ----------------
def chay():
    quan_trong, con_viec = [], False
    nap_ls = nap_lich_su_dang_bat()
    ap_dung_de_xuat()
    da_co, moc = khoa_da_co(), dau_nam_hoc()

    # 1. Gom mục mới từ mọi nguồn
    moi, can_tep = [], []
    for n in danh_sach_nguon():
        if not con_gio(150):
            con_viec = True
            continue
        ds, kq = [], ''
        try:
            ds = doc_nguon(n, max(n['soTrang'], 6) if nap_ls else n['soTrang'])
            kq = f'{len(ds)} mục'
        except Exception as e:
            kq = f'LỖI: {e}'
        ghi_nguon(n, kq)
        for x in ds:
            x['khoa'] = tao_khoa(x)
            x['nguon'] = n['ten']
            x['coQuanNguon'] = n.get('coQuan')
            ngay = chuan_ngay(x.get('ngay'))
            co = da_co.get(x['khoa'])
            if co and co.get('hang') and not any(y['x']['khoa'] == x['khoa'] for y in can_tep):
                can_tep.append({'x': x, 'hang': co['hang']})
                continue
            if co or (ngay and ngay < moc) or any(y['khoa'] == x['khoa'] for y in moi):
                continue
            moi.append(x)

    # 2. Lọc từ khoá, rồi Gemini phân loại theo trích yếu (lô 25)
    loai_ngay, can_hoi = [], []
    for x in moi:
        t = f"{x.get('soHieu') or ''} {x['trichYeu']}"
        if LOAI_TRU.search(t) and not UU_TIEN.search(t):
            loai_ngay.append([x['khoa'], x['trichYeu'][:300], 'Không (lọc từ khoá)', time.strftime('%d/%m/%Y %H:%M')])
        else:
            can_hoi.append(x)
    if loai_ngay:
        ghi_da_xet(loai_ngay)
    lien_quan = []
    i = 0
    while i < len(can_hoi) and con_gio(120):
        lo = can_hoi[i:i + LO_PHAN_LOAI]
        pl = phan_loai(lo)
        xet = []
        for k, x in enumerate(lo):
            p = pl[k] if k < len(pl) and pl[k] else {}
            m = p.get('lienQuan') or 'chua_ro'
            if m in ('cao', 'trung_binh'):
                x['muc'] = m
                lien_quan.append(x)
            elif m != 'chua_ro':
                xet.append([x['khoa'], x['trichYeu'][:300], f"Không liên quan ({p.get('lyDo') or ''})", time.strftime('%d/%m/%Y %H:%M')])
        if xet:
            ghi_da_xet(xet)
        if i + LO_PHAN_LOAI < len(can_hoi):
            con_viec = True
        i += LO_PHAN_LOAI

    # 3. Tải bản gốc + Gemini đọc (mức "cao" trước)
    lien_quan.sort(key=lambda x: 0 if x['muc'] == 'cao' else 1)
    da_doc = 0
    for x in lien_quan:
        if da_doc >= SO_DOC_MOI_LUOT or not con_gio(90):
            con_viec = True
            break
        try:
            r = doc_sau(x)
            da_doc += 1
            if r.get('lienQuan') == 'cao':
                quan_trong.append(r)
        except Exception as e:
            print(f"Đọc văn bản lỗi {x['khoa']}: {e}")

    # 3b. Văn bản đã có trong danh mục nhưng chưa có bản gốc trên Drive -> tải bổ sung
    for t in can_tep[:5]:
        if con_gio(60):
            try:
                bo_sung_tep(t['x'], t['hang'])
            except Exception as e:
                print(f'Bổ sung tệp lỗi: {e}')

    if not con_viec and nap_ls:
        tat_nap_lich_su()
    # 4. Thông báo: mail do Apps Script gửi (vbMailQuanTrong_, vbNhacHan_, vbBanTinTuan_ giữ nguyên bên đó)
    if quan_trong:
        ghi_quan_trong(quan_trong)
    return con_viec


if __name__ == '__main__':
    con_viec = chay()
    out = os.environ.get('GITHUB_OUTPUT')
    if out:
        with open(out, 'a', encoding='utf-8') as f:
            f.write(f"con_viec={'true' if con_viec else 'false'}\n")
    sys.exit(0)
