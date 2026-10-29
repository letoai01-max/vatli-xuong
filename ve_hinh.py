"""
ve_hinh.py – XƯỞNG VẼ HÌNH CHO ĐỀ (Python, GitHub Actions) – gọi từ VeHinhXuong.gs của agent tạo đề.

Với mỗi câu có hình loại "hinhve" (sơ đồ mạch điện, hình biểu diễn lực, nam châm – ống dây…):
  1. Gemini chuyển MÔ TẢ hình thành danh sách đối tượng vẽ (toạ độ, nhãn) – hoặc trả ve_duoc = false nếu không vẽ được bằng các đối tượng có sẵn.
  2. Vẽ bằng code: DÙNG LẠI ve_doi_tuong của render.py (nam châm, ống dây, điện kế, nguồn, điện trở, bóng đèn, vật, mặt phẳng,
     mũi tên lực, dây dẫn, đường sức, chữ) + thêm ampe kế / vôn kế, khoá K, tụ điện, lò xo, góc, nét đứt. Nét đen – xám kiểu SGK.
  3. KIỂM TRA: Gemini xem lại ảnh vừa vẽ so với mô tả; chưa khớp thì vẽ lại 1 lần theo góp ý; vẫn chưa khớp thì báo lỗi.
  4. Ghi PNG vào tệp dựng sẵn trên Drive (tệp do thầy sở hữu). Lỗi / không vẽ được → đổi tên "(LỖI) …" để agent quay về cách cũ.
Biến môi trường: GOOGLE_CREDENTIALS, GEMINI_API_KEY (_2, _3), GOI_ID.
"""
import base64, io, json, math, os, re, tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import patches
import numpy as np
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

import doc_de as X
import kiem_dinh_de as K          # ket_noi_ghi
import render as R                # ve_doi_tuong, MAU (bộ vẽ của xưởng video)
try:
    import quota_xuong as Q
except Exception:
    Q = None

# Bảng màu in đề: đen – xám thay cho màu video (nam châm vẫn phân biệt được hai cực)
MAU_DE = {"do": "#111111", "xanh": "#7a7a7a", "den": "#111111", "cam": "#b0b0b0", "luc": "#111111", "tim": "#111111"}
SO_LAN_VE = 2

TU_DIEN = """Toạ độ trong khung [x0, x1, y0, y1] (mặc định [0, 16, 0, 9]), trục y hướng LÊN. Các đối tượng (trường "kieu"):
- "nguon": nguồn điện tại (x, y), "nhan" (vd "E, r"). Hai bản cực dọc; dây nối vào hai bên trái/phải cách tâm 0,15.
- "dien_tro": điện trở từ "tu" [x1,y1] đến "den" [x2,y2] (hình chữ nhật trên đoạn dây), "nhan" (vd "R₁" hoặc "$R_1$").
- "bong_den": bóng đèn tại (x, y), bán kính 0,45.
- "dong_ho": ampe kế / vôn kế tại (x, y), "nhan": "A" hoặc "V", bán kính 0,55.
- "dien_ke": điện kế G tại (x, y), "kim": -1…1 (lệch kim).
- "khoa": khoá K từ "tu" đến "den", "dong": true/false, "nhan": "K".
- "tu_dien": tụ điện tại (x, y), "doc": true (hai bản dọc, dây nằm ngang) | false, "nhan".
- "day_dan": dây nối, "diem": [[x,y], …] (đường gấp khúc, các đoạn nên nằm ngang/dọc).
- "nam_cham": nam châm thẳng tại (x, y), "huongN": "phai"|"trai"|"len"|"xuong", "dai", "rong".
- "ong_day": ống dây tại (x, y), "dai", "cao", "soVong", "chieuDong": "len"|"xuong"|"khong" (CHỈ vẽ chiều dòng điện khi đề CHO SẴN, không vẽ khi đề hỏi), "dienKe": {"kim": 0} để nối điện kế G, "nhan".
- "duong_suc": đường sức từ, "diem": [[x,y], …] (có mũi tên ở giữa).
- "vat": vật tại (x, y), "kichThuoc", "hinh": "vuong"|"tron", "nhan" (chữ trong vật), "xoay" (độ – bằng góc nghiêng khi vật nằm trên mặt phẳng nghiêng; tâm vật cách mặt phẳng nửa kích thước).
- "mat_phang": mặt sàn / mặt phẳng nghiêng từ "tu" đến "den" (có gạch chéo bên dưới).
- "mui_ten": vectơ lực / vận tốc từ "tu" (điểm đặt) đến "den", "nhan" (đặt cạnh đầu mũi tên, vd "$\\\\vec{F}$"), "day" (độ dày, mặc định 2,5).
- "lo_xo": lò xo từ "tu" đến "den", "soVong" (mặc định 8).
- "goc": cung góc tâm (x, y), "r", "tu_do", "den_do" (độ, ngược chiều kim đồng hồ từ trục x), "nhan" (vd "$\\\\alpha$").
- "net_dut": đường nét đứt, "diem": [[x,y], …].
- "chu": chữ tại (x, y), "noiDung", "co" (cỡ chữ, mặc định 18).
QUY TẮC: dây nối phải chạm đúng đầu các linh kiện (mạch kín khi đề nói mạch kín); nhãn ngắn; không vẽ thừa chi tiết làm lộ đáp án;
giữ đối tượng trong khung, cách mép ít nhất 0,5."""


# ============================== VẼ ==============================
def _diem(o, k, mac):
    v = o.get(k, mac)
    return float(v[0]), float(v[1])


def ve_them(ax, o):
    """Các đối tượng render.py chưa có. Trả True nếu đã vẽ."""
    k = o.get("kieu")
    x, y = float(o.get("x", 8)), float(o.get("y", 4.5))
    den = "#111111"
    if k == "dong_ho":
        r = float(o.get("r", 0.55))
        ax.add_patch(patches.Circle((x, y), r, fc="white", ec=den, lw=2, zorder=3))
        ax.text(x, y, str(o.get("nhan", "A")), ha="center", va="center", fontsize=17, weight="bold", zorder=4)
    elif k == "khoa":
        (x1, y1), (x2, y2) = _diem(o, "tu", [x - 0.8, y]), _diem(o, "den", [x + 0.8, y])
        for px, py in ((x1, y1), (x2, y2)):
            ax.add_patch(patches.Circle((px, py), 0.08, fc="white", ec=den, lw=1.5, zorder=3))
        if o.get("dong"):
            ax.plot([x1, x2], [y1, y2], color=den, lw=2.2)
        else:
            g = math.atan2(y2 - y1, x2 - x1) + math.radians(28)
            d = math.hypot(x2 - x1, y2 - y1)
            ax.plot([x1, x1 + d * math.cos(g)], [y1, y1 + d * math.sin(g)], color=den, lw=2.2)
        if o.get("nhan"):
            ax.text((x1 + x2) / 2, max(y1, y2) + 0.55, o["nhan"], ha="center", fontsize=15)
    elif k == "tu_dien":
        if o.get("doc", True):
            for dx_ in (-0.13, 0.13):
                ax.plot([x + dx_, x + dx_], [y - 0.5, y + 0.5], color=den, lw=3)
            nx, ny = x, y + 0.85
        else:
            for dy_ in (-0.13, 0.13):
                ax.plot([x - 0.5, x + 0.5], [y + dy_, y + dy_], color=den, lw=3)
            nx, ny = x + 0.9, y
        if o.get("nhan"):
            ax.text(nx, ny, o["nhan"], ha="center", va="center", fontsize=15)
    elif k == "lo_xo":
        (x1, y1), (x2, y2) = _diem(o, "tu", [x - 1, y]), _diem(o, "den", [x + 1, y])
        n = int(o.get("soVong", 8))
        t = np.linspace(0, 1, 2 * n + 3)
        ux, uy = x2 - x1, y2 - y1
        d = math.hypot(ux, uy) or 1
        px_, py_ = -uy / d * 0.25, ux / d * 0.25
        xs = [x1 + ux * s for s in t]
        ys = [y1 + uy * s for s in t]
        for i in range(2, len(t) - 2):
            sgn = 1 if i % 2 else -1
            xs[i] += px_ * sgn; ys[i] += py_ * sgn
        ax.plot(xs, ys, color=den, lw=1.8)
    elif k == "goc":
        r = float(o.get("r", 1.0))
        a, b = float(o.get("tu_do", 0)), float(o.get("den_do", 30))
        ax.add_patch(patches.Arc((x, y), 2 * r, 2 * r, theta1=a, theta2=b, color=den, lw=1.5))
        if o.get("nhan"):
            g = math.radians((a + b) / 2)
            ax.text(x + (r + 0.35) * math.cos(g), y + (r + 0.35) * math.sin(g), o["nhan"], ha="center", va="center", fontsize=15)
    elif k == "vat":                                   # bản in đề: nền xám nhạt, chữ đen, có thể xoay theo mặt phẳng nghiêng
        sz, xoay = float(o.get("kichThuoc", 1)), float(o.get("xoay", 0))
        if o.get("hinh") == "tron":
            ax.add_patch(patches.Circle((x, y), sz / 2, fc="#d9d9d9", ec=den, lw=1.8, zorder=2))
        else:
            ax.add_patch(patches.Rectangle((x - sz / 2, y - sz / 2), sz, sz, angle=xoay, rotation_point="center",
                                           fc="#d9d9d9", ec=den, lw=1.8, zorder=2))
        if o.get("nhan"):
            ax.text(x, y, o["nhan"], ha="center", va="center", fontsize=15, color=den, zorder=3)
    elif k == "mui_ten":                               # nhãn đặt cạnh ĐẦU mũi tên (không đè lên vật ở gốc)
        (x1, y1), (x2, y2) = _diem(o, "tu", [x, y]), _diem(o, "den", [x + 1, y])
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), zorder=4,
                    arrowprops=dict(arrowstyle="-|>", color=den, lw=float(o.get("day", 2.5)), mutation_scale=22))
        if o.get("nhan"):
            d = math.hypot(x2 - x1, y2 - y1) or 1
            ux, uy = (x2 - x1) / d, (y2 - y1) / d
            ax.text(x2 + 0.45 * ux - 0.35 * uy, y2 + 0.45 * uy + 0.35 * ux, o["nhan"], ha="center", va="center", fontsize=17, zorder=5)
    elif k == "ong_day":                               # bản in đề: nét đen–xám, KHÔNG tự ghi chữ (tránh lộ đáp án)
        dai, cao, n = float(o.get("dai", 4)), float(o.get("cao", 2)), int(o.get("soVong", 8))
        w = dai / max(n, 1)
        for i in range(n):
            xi = x - dai / 2 + w * (i + 0.5)
            ax.add_patch(patches.Arc((xi, y), w * 0.9, cao, theta1=90, theta2=270, color="#9a9a9a", lw=1.6, ls="--"))
            ax.add_patch(patches.Arc((xi, y), w * 0.9, cao, theta1=-90, theta2=90, color=den, lw=2.4))
        chieu = o.get("chieuDong", "khong")
        if chieu in ("len", "xuong"):
            for i in range(0, n, max(1, n // 3)):
                xi = x - dai / 2 + w * (i + 0.5) + w * 0.45
                a_, b_ = (y - 0.25, y + 0.25) if chieu == "len" else (y + 0.25, y - 0.25)
                ax.annotate("", xy=(xi, b_), xytext=(xi, a_), arrowprops=dict(arrowstyle="-|>", color=den, lw=2, mutation_scale=18))
        if o.get("nhan"):
            ax.text(x, y + cao / 2 + 0.4, o["nhan"], ha="center", fontsize=15)
        dk = o.get("dienKe")
        if isinstance(dk, dict):
            trai, phai = (x - dai / 2, y - cao / 2), (x + dai / 2, y - cao / 2)
            gx, gy = x, y - cao / 2 - 1.6
            ax.plot([trai[0], trai[0], gx - 0.6], [trai[1], gy, gy], color=den, lw=2)
            ax.plot([phai[0], phai[0], gx + 0.6], [phai[1], gy, gy], color=den, lw=2)
            R.ve_doi_tuong(ax, {"kieu": "dien_ke", "x": gx, "y": gy, "kim": dk.get("kim", 0)})
    elif k == "bong_den":
        ax.add_patch(patches.Circle((x, y), 0.45, fc="white", ec=den, lw=2, zorder=3))
        for a_, b_ in ((-0.3, 0.3), (0.3, -0.3)):
            ax.plot([x - 0.3, x + 0.3], [y + a_, y + b_], color=den, lw=1.5, zorder=4)
        if o.get("nhan"):
            ax.text(x, y + 0.8, o["nhan"], ha="center", fontsize=15)
    elif k == "net_dut":
        d = np.array(o.get("diem", []), dtype=float)
        if len(d) >= 2:
            ax.plot(d[:, 0], d[:, 1], color="#555555", lw=1.4, ls="--")
    else:
        return False
    return True


def ve_hinh(spec, duong_dan):
    R.MAU.update(MAU_DE)
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    x0, x1, y0, y1 = [float(v) for v in (spec.get("khung") or [0, 16, 0, 9])[:4]]
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal"); ax.axis("off")
    fig.patch.set_facecolor("white")
    loi = 0
    for o in spec.get("doiTuong") or []:
        try:
            if not ve_them(ax, o):
                R.ve_doi_tuong(ax, o)
        except Exception as e:
            loi += 1
            print("  Bỏ qua đối tượng lỗi:", json.dumps(o, ensure_ascii=False)[:120], e, flush=True)
    fig.savefig(duong_dan, dpi=150, bbox_inches="tight", pad_inches=0.15, facecolor="white")
    plt.close(fig)
    return loi


# ============================== GEMINI ==============================
def goi_json(phan, cac_model, nhiet_do=0.2):
    payload = {"contents": [{"role": "user", "parts": phan}],
               "generationConfig": {"temperature": nhiet_do, "responseMimeType": "application/json", "maxOutputTokens": 8192}}
    data, model = X.goi_gemini(payload, cac_model)
    cand = (data.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []) if not p.get("thought"))
    return json.loads(re.sub(r"^```(?:json)?|```$", "", text.strip()).strip()), model


def lap_so_do(muc, cac_model, gop_y=""):
    loi_nhan = ("Bạn vẽ hình cho câu hỏi đề kiểm tra Vật lí THPT (kiểu hình SGK Việt Nam) bằng các ĐỐI TƯỢNG có sẵn dưới đây.\n"
                + TU_DIEN + "\n\nCÂU HỎI: " + str(muc.get("cauHoi") or "")[:1200]
                + "\nCHÚ THÍCH HÌNH: " + str(muc.get("chuThich") or "")
                + "\nMÔ TẢ HÌNH CẦN VẼ: " + str(muc.get("moTa") or "")
                + (("\n\nLẦN VẼ TRƯỚC CHƯA ĐẠT, cần sửa: " + gop_y) if gop_y else "")
                + "\n\nTrả về JSON: {\"ve_duoc\": true, \"ly_do\": \"\", \"khung\": [0, 16, 0, 9], \"doiTuong\": [ {…}, … ]}. "
                  "Nếu hình KHÔNG thể vẽ đúng bằng các đối tượng trên (ảnh thực tế, thiết bị phức tạp, hình 3D…) thì "
                  "{\"ve_duoc\": false, \"ly_do\": \"…\"}.")
    return goi_json([{"text": loi_nhan}], cac_model)[0]


def kiem_hinh(muc, duong_dan, cac_model):
    with open(duong_dan, "rb") as f:
        anh = base64.b64encode(f.read()).decode()
    loi_nhan = ("Đây là hình vừa vẽ cho câu hỏi Vật lí. Đối chiếu hình với MÔ TẢ: đủ linh kiện / vật / lực, đúng cách mắc (nối tiếp, song song), "
                "đúng chiều mũi tên, nhãn đúng và đọc được, dây nối kín khi cần, không chồng chéo khó nhìn.\n"
                "MÔ TẢ: " + str(muc.get("moTa") or "") + "\nCÂU HỎI: " + str(muc.get("cauHoi") or "")[:800] +
                "\nTrả về JSON: {\"khop\": true|false, \"loi\": \"liệt kê ngắn các chỗ sai/thiếu (rỗng nếu khớp)\"}.")
    kq, _ = goi_json([{"inline_data": {"mime_type": "image/png", "data": anh}}, {"text": loi_nhan}], cac_model, 0)
    return bool(kq.get("khop")), str(kq.get("loi") or "")[:400]


def ve_mot_hinh(muc, cac_model, thu_muc, so):
    """Trả (đường dẫn PNG, ghi chú) hoặc ném lỗi với lí do."""
    gop_y = ""
    for lan in range(SO_LAN_VE):
        spec = lap_so_do(muc, cac_model, gop_y)
        if not spec.get("ve_duoc", True):
            raise ValueError("không vẽ được bằng code: " + str(spec.get("ly_do") or "")[:200])
        if not spec.get("doiTuong"):
            raise ValueError("Gemini không trả danh sách đối tượng")
        ra = os.path.join(thu_muc, "hinh_%d_%d.png" % (so, lan))
        loi_dt = ve_hinh(spec, ra)
        khop, gop_y = kiem_hinh(muc, ra, cac_model)
        print("  Lần vẽ %d: %d đối tượng%s → %s" % (lan + 1, len(spec["doiTuong"]), (", %d lỗi" % loi_dt) if loi_dt else "",
                                                 "KHỚP" if khop else "chưa khớp: " + gop_y), flush=True)
        if khop:
            return ra, "vẽ bằng code, %d lần" % (lan + 1)
    raise ValueError("vẽ %d lần vẫn chưa khớp mô tả: %s" % (SO_LAN_VE, gop_y))


# ============================== CHẠY ==============================
def main():
    gc, drive, sa = K.ket_noi_ghi()
    buf = io.BytesIO()
    tai = MediaIoBaseDownload(buf, drive.files().get_media(fileId=os.environ["GOI_ID"]))
    xong = False
    while not xong:
        _, xong = tai.next_chunk()
    goi = json.loads(buf.getvalue().decode("utf-8"))
    cac_model = X.doc_cau_hinh(gc.open_by_key(X.ID_KHO_CHUNG))
    ds = goi.get("hinh") or []
    print("Vẽ %d hình; model: %s" % (len(ds), ", ".join(cac_model)), flush=True)
    thu = tempfile.mkdtemp()
    dat, het_luot = 0, ""
    def bao_loi(muc, ly_do):                   # đổi tên "(LỖI) …" → agent thôi chờ, quay về cách tạo ảnh cũ ngay
        try:
            cu = drive.files().get(fileId=muc["dich"], fields="name").execute().get("name", "")
            drive.files().update(fileId=muc["dich"], body={"name": "(LỖI) " + cu, "description": ly_do[:400]}).execute()
        except Exception:
            pass
    try:
        for so, muc in enumerate(ds, 1):
            print("🖊️ Hình %d: %s" % (so, str(muc.get("chuThich") or muc.get("moTa"))[:90]), flush=True)
            if het_luot:
                bao_loi(muc, het_luot); continue
            try:
                ra, ghi_chu = ve_mot_hinh(muc, cac_model, thu, so)
                drive.files().update(fileId=muc["dich"], media_body=MediaFileUpload(ra, mimetype="image/png"),
                                     body={"description": "Xưởng Python: " + ghi_chu}).execute()
                dat += 1
                print("  ✅ Đã ghi ảnh.", flush=True)
            except X.HetHanMuc as e:
                het_luot = "Gemini hết hạn mức: " + str(e)[:150]
                print("⏸️ " + het_luot + " – các hình còn lại agent tạo theo cách cũ.", flush=True)
                bao_loi(muc, het_luot)
            except Exception as e:
                print("  ⚠️ " + str(e)[:200], flush=True)
                bao_loi(muc, str(e))
    finally:
        if Q:
            Q.ghi_sheet()
    print("📊 Vẽ được %d/%d hình." % (dat, len(ds)), flush=True)


if __name__ == "__main__":
    main()
