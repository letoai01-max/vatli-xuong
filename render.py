"""
render.py – XƯỞNG DỰNG VIDEO BÀI GIẢNG (chạy trên GitHub Actions, gọi từ VideoAgent.gs)

1. Lấy kịch bản đã duyệt từ web app Apps Script (?a=kichban&m=<mã>&t=<VIDEO_SECRET>).
2. Mỗi cảnh: giọng đọc tiếng Việt (edge-tts, miễn phí) → hình:
     tieu_de : màn hình chữ
     so_do   : sơ đồ vẽ bằng code từ THÔNG SỐ trong kịch bản (nam châm, ống dây, chiều dòng điện, điện kế…),
               có thể hoạt hoạ một đối tượng dịch chuyển
     do_thi  : đồ thị từ số liệu
     anh_ai  : ảnh AI cho cảnh phụ (Pollinations, miễn phí; lỗi thì thay bằng màn hình chữ)
3. Ghép các cảnh, chèn phụ đề khớp từng câu → out/<mã>.mp4 và out/<mã>.srt (720p).
"""
import asyncio, json, math, os, re, shutil, subprocess, sys, textwrap, urllib.parse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import patches
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont
import edge_tts

W, H, FPS = 1280, 720, 25
GIONG = {"Nữ": "vi-VN-HoaiMyNeural", "Nam": "vi-VN-NamMinhNeural"}
def _tim_font(ds):
    for f in ds:
        if os.path.exists(f):
            return f
    return ds[-1]


FONT_DAM = _tim_font(["/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"])
FONT_THUONG = _tim_font(["/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
MAU = {"do": "#d32f2f", "xanh": "#1565c0", "den": "#212121", "cam": "#ef6c00", "luc": "#2e7d32", "tim": "#6a1b9a"}
plt.rcParams.update({"font.family": ["Noto Sans", "DejaVu Sans"], "mathtext.fontset": "dejavusans"})
TAM = "tam"
NGHI_GIAY = 0.5  # khoảng lặng cuối mỗi cảnh


def chay(lenh):
    r = subprocess.run(lenh, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("Lệnh lỗi: " + " ".join(lenh[:6]) + " …\n" + r.stderr[-2000:])
    return r.stdout


def thoi_luong(tep):
    return float(chay(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", tep]).strip())


# ------------------------------------------------------------------ giọng đọc
async def _tts(chu, giong, ra):
    await edge_tts.Communicate(chu, giong, rate="+0%").save(ra)


def doc(chu, giong, ra):
    for lan in range(3):
        try:
            asyncio.run(_tts(chu, giong, ra))
            if os.path.getsize(ra) > 1000:
                return
        except Exception as e:  # mạng chập chờn: thử lại
            loi = e
    raise RuntimeError("Không tạo được giọng đọc: %s" % loi)


# ------------------------------------------------------------------ phụ đề
def tach_cau(chu, toi_da=58):
    cau = [c.strip() for c in re.split(r"(?<=[.!?…;:])\s+", chu.strip()) if c.strip()]
    ra = []
    for c in cau:
        if len(c) <= toi_da:
            ra.append(c)
        else:
            ra.extend(textwrap.wrap(c, toi_da, break_long_words=False))
    return ra or [chu]


def gio_srt(t):
    ms = int(round(t * 1000))
    return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


# ------------------------------------------------------------------ màn hình chữ
def nen_toi():
    anh = Image.new("RGB", (W, H))
    px = anh.load()
    for y in range(H):
        for x in range(0, W, 4):
            t = (x / W + y / H) / 2
            c = (int(13 + 20 * t), int(27 + 40 * t), int(62 + 70 * t))
            for k in range(4):
                if x + k < W:
                    px[x + k, y] = c
    return anh


def man_hinh_chu(tieu_de, phu_de, ra):
    anh = nen_toi()
    v = ImageDraw.Draw(anh)
    f1, f2 = ImageFont.truetype(FONT_DAM, 54), ImageFont.truetype(FONT_THUONG, 30)
    dong1 = textwrap.wrap(tieu_de or "", 30) or [""]
    dong2 = textwrap.wrap(phu_de or "", 60)
    tong = len(dong1) * 70 + len(dong2) * 44 + 30
    y = (H - tong) / 2
    for d in dong1:
        w = v.textlength(d, font=f1)
        v.text(((W - w) / 2, y), d, font=f1, fill=(255, 255, 255))
        y += 70
    y += 30
    for d in dong2:
        w = v.textlength(d, font=f2)
        v.text(((W - w) / 2, y), d, font=f2, fill=(180, 210, 255))
        y += 44
    anh.save(ra)


# ------------------------------------------------------------------ sơ đồ vẽ bằng code
def _mau(t, mac_dinh="den"):
    return MAU.get(t or mac_dinh, t if isinstance(t, str) and t.startswith("#") else MAU[mac_dinh])


def ve_doi_tuong(ax, o, dx=0.0, dy=0.0):
    k = o.get("kieu")
    x, y = float(o.get("x", 8)) + dx, float(o.get("y", 4.5)) + dy
    if k == "nam_cham":
        dai, rong = float(o.get("dai", 2.4)), float(o.get("rong", 0.8))
        huong = o.get("huongN", "phai")
        doc_ = huong in ("len", "xuong")
        a, b = (rong, dai) if doc_ else (dai, rong)
        x0, y0 = x - a / 2, y - b / 2
        if doc_:
            n_tren = huong == "len"
            ax.add_patch(patches.Rectangle((x0, y), a, b / 2, color=MAU["do"] if n_tren else MAU["xanh"]))
            ax.add_patch(patches.Rectangle((x0, y0), a, b / 2, color=MAU["xanh"] if n_tren else MAU["do"]))
            ax.text(x, y + b / 4, "N" if n_tren else "S", ha="center", va="center", color="white", fontsize=20, weight="bold")
            ax.text(x, y - b / 4, "S" if n_tren else "N", ha="center", va="center", color="white", fontsize=20, weight="bold")
        else:
            n_phai = huong == "phai"
            ax.add_patch(patches.Rectangle((x, y0), a / 2, b, color=MAU["do"] if n_phai else MAU["xanh"]))
            ax.add_patch(patches.Rectangle((x0, y0), a / 2, b, color=MAU["xanh"] if n_phai else MAU["do"]))
            ax.text(x + a / 4, y, "N" if n_phai else "S", ha="center", va="center", color="white", fontsize=20, weight="bold")
            ax.text(x - a / 4, y, "S" if n_phai else "N", ha="center", va="center", color="white", fontsize=20, weight="bold")
    elif k == "ong_day":
        dai, cao, n = float(o.get("dai", 4)), float(o.get("cao", 2)), int(o.get("soVong", 8))
        w = dai / max(n, 1)
        for i in range(n):
            xi = x - dai / 2 + w * (i + 0.5)
            ax.add_patch(patches.Arc((xi, y), w * 0.9, cao, theta1=90, theta2=270, color="#8d6e63", lw=2, ls="--"))   # mặt sau
            ax.add_patch(patches.Arc((xi, y), w * 0.9, cao, theta1=-90, theta2=90, color="#bf360c", lw=3))            # mặt trước
        chieu = o.get("chieuDong", "khong")
        if chieu in ("len", "xuong"):
            for i in range(0, n, max(1, n // 3)):
                xi = x - dai / 2 + w * (i + 0.5) + w * 0.45
                y1, y2 = (y - 0.25, y + 0.25) if chieu == "len" else (y + 0.25, y - 0.25)
                ax.annotate("", xy=(xi, y2), xytext=(xi, y1), arrowprops=dict(arrowstyle="-|>", color=MAU["cam"], lw=2.5, mutation_scale=20))
            ax.text(x, y + cao / 2 + 0.35, "dòng điện cảm ứng", ha="center", color=MAU["cam"], fontsize=13)
        trai, phai = (x - dai / 2, y - cao / 2), (x + dai / 2, y - cao / 2)
        dk = o.get("dienKe")
        if isinstance(dk, dict):
            gx, gy = x, y - cao / 2 - 1.6
            ax.plot([trai[0], trai[0], gx - 0.6], [trai[1], gy, gy], color="black", lw=2)
            ax.plot([phai[0], phai[0], gx + 0.6], [phai[1], gy, gy], color="black", lw=2)
            ve_doi_tuong(ax, {"kieu": "dien_ke", "x": gx, "y": gy, "kim": dk.get("kim", 0)})
    elif k == "dien_ke":
        r = float(o.get("r", 0.6))
        ax.add_patch(patches.Circle((x, y), r, fc="white", ec="black", lw=2, zorder=3))
        ax.add_patch(patches.Arc((x, y), r * 1.5, r * 1.5, theta1=40, theta2=140, color="#757575", lw=1, zorder=4))
        goc = math.radians(90 - 40 * float(o.get("kim", 0)))
        ax.plot([x, x + r * 0.8 * math.cos(goc)], [y - r * 0.1, y - r * 0.1 + r * 0.8 * math.sin(goc)], color=MAU["do"], lw=2.5, zorder=5)
        ax.text(x, y - r * 0.45, "G", ha="center", va="center", fontsize=14, weight="bold", zorder=5)
    elif k == "mui_ten":
        (x1, y1), (x2, y2) = o.get("tu", [x, y]), o.get("den", [x + 1, y])
        x1, y1, x2, y2 = x1 + dx, y1 + dy, x2 + dx, y2 + dy
        m = _mau(o.get("mau"), "do")
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color=m, lw=float(o.get("day", 3)), mutation_scale=25))
        if o.get("nhan"):
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.35, o["nhan"], ha="center", color=m, fontsize=16, weight="bold")
    elif k in ("duong_suc", "day_dan"):
        d = np.array(o.get("diem", []), dtype=float)
        if len(d) >= 2:
            d = d + [dx, dy]
            m = _mau(o.get("mau"), "xanh" if k == "duong_suc" else "den")
            ax.plot(d[:, 0], d[:, 1], color=m, lw=1.8 if k == "duong_suc" else 2.2)
            if k == "duong_suc":
                i = len(d) // 2
                ax.annotate("", xy=d[i], xytext=d[i - 1], arrowprops=dict(arrowstyle="-|>", color=m, lw=1.5, mutation_scale=18))
    elif k == "nguon":
        ax.plot([x - 0.15, x - 0.15], [y - 0.6, y + 0.6], color="black", lw=3)
        ax.plot([x + 0.15, x + 0.15], [y - 0.3, y + 0.3], color="black", lw=5)
        ax.text(x, y + 0.9, o.get("nhan", ""), ha="center", fontsize=15)
    elif k == "dien_tro":
        (x1, y1), (x2, y2) = o.get("tu", [x - 1, y]), o.get("den", [x + 1, y])
        cx, cy, goc = (x1 + x2) / 2 + dx, (y1 + y2) / 2 + dy, math.degrees(math.atan2(y2 - y1, x2 - x1))
        dai = math.hypot(x2 - x1, y2 - y1)
        ax.add_patch(patches.Rectangle((cx - dai * 0.3, cy - 0.2), dai * 0.6, 0.4, angle=goc, rotation_point="center", fc="white", ec="black", lw=2))
        ax.plot([x1 + dx, x2 + dx], [y1 + dy, y2 + dy], color="black", lw=2, zorder=0)
        ax.text(cx, cy + 0.5, o.get("nhan", ""), ha="center", fontsize=15)
    elif k == "bong_den":
        ax.add_patch(patches.Circle((x, y), 0.45, fc="#fff59d", ec="black", lw=2))
        ax.plot([x - 0.3, x + 0.3], [y - 0.3, y + 0.3], color="black", lw=1.5)
        ax.plot([x - 0.3, x + 0.3], [y + 0.3, y - 0.3], color="black", lw=1.5)
    elif k == "vat":
        s, m = float(o.get("kichThuoc", 1)), _mau(o.get("mau"), "cam")
        if o.get("hinh") == "tron":
            ax.add_patch(patches.Circle((x, y), s / 2, fc=m, ec="black", lw=1.5))
        else:
            ax.add_patch(patches.Rectangle((x - s / 2, y - s / 2), s, s, fc=m, ec="black", lw=1.5))
        ax.text(x, y, o.get("nhan", ""), ha="center", va="center", fontsize=15, color="white", weight="bold")
    elif k == "mat_phang":
        (x1, y1), (x2, y2) = o.get("tu", [1, 1]), o.get("den", [15, 1])
        ax.plot([x1, x2], [y1, y2], color="black", lw=2)
        for t in np.linspace(0, 1, 25):
            px, py = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
            ax.plot([px, px - 0.25], [py, py - 0.25], color="#616161", lw=1)
    elif k == "chu":
        ax.text(x, y, o.get("noiDung", ""), ha="center", va="center", fontsize=int(o.get("co", 18)), color=_mau(o.get("mau"), "den"))


def ve_so_do(h, ra, t=0.0):
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    # chừa dải trên cho tiêu đề + công thức, dải dưới 20% cho phụ đề – hình không bao giờ bị phụ đề che
    ax = fig.add_axes([0.02, 0.2, 0.96, 0.6])
    x0, x1, y0, y1 = (h.get("khung") or [0, 16, 0, 9])[:4]
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal"); ax.axis("off")
    fig.patch.set_facecolor("white")
    hh = h.get("hoatHoa") or {}
    chi_so = int(hh.get("chiSo", -1)) if hh else -1
    for i, o in enumerate(h.get("doiTuong", [])):
        dx = float(hh.get("dx", 0)) * t if i == chi_so else 0.0
        dy = float(hh.get("dy", 0)) * t if i == chi_so else 0.0
        try:
            ve_doi_tuong(ax, o, dx, dy)
        except Exception as e:
            print("Bỏ qua đối tượng lỗi:", o, e)
    if h.get("tieuDe"):
        fig.text(0.5, 0.955, h["tieuDe"], ha="center", va="top", fontsize=24, weight="bold", color="#1a237e")
    if h.get("congThuc"):
        try:
            fig.text(0.5, 0.85, h["congThuc"], ha="center", va="center", fontsize=24,
                     bbox=dict(boxstyle="round,pad=0.35", fc="#fff8e1", ec="#ef6c00"))
        except Exception:
            pass
    fig.savefig(ra, dpi=100)
    plt.close(fig)


def ve_do_thi(h, ra):
    fig, ax = plt.subplots(figsize=(W / 100, H / 100), dpi=100)
    mau = ["#000000", "#1565c0", "#d32f2f", "#2e7d32"]
    for i, d in enumerate((h.get("duong") or [])[:4]):
        p = np.array(d.get("diem", []), dtype=float)
        if len(p) >= 2:
            ax.plot(p[:, 0], p[:, 1], "-o", color=mau[i], lw=2.5, ms=6, label=d.get("ten", ""))
    ax.set_xlabel(h.get("x", ""), fontsize=18); ax.set_ylabel(h.get("y", ""), fontsize=18)
    ax.set_title(h.get("tieuDe", ""), fontsize=22, weight="bold")
    ax.grid(alpha=0.35); ax.tick_params(labelsize=14)
    ax.spines[["top", "right"]].set_visible(False)
    if len(h.get("duong") or []) > 1:
        ax.legend(fontsize=15)
    fig.tight_layout(rect=[0.03, 0.2, 0.97, 0.98]); fig.savefig(ra, dpi=100); plt.close(fig)


def anh_ai(mo_ta, ra, hat):
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(mo_ta + ", educational illustration, clean, no text") + \
          "?width=%d&height=%d&nologo=true&seed=%d" % (W, H, hat)
    for lan in range(2):
        try:
            r = requests.get(url, timeout=150)
            if r.ok and r.headers.get("content-type", "").startswith("image"):
                with open(ra + ".tmp", "wb") as f:
                    f.write(r.content)
                Image.open(ra + ".tmp").convert("RGB").resize((W, H)).save(ra)
                return True
        except Exception as e:
            print("Ảnh AI lỗi:", e)
    return False


# ------------------------------------------------------------------ dựng từng cảnh
MA_HOA = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p", "-r", str(FPS),
          "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]


def dung_canh(c, i, giong):
    thu = os.path.join(TAM, "c%02d" % i)
    os.makedirs(thu, exist_ok=True)
    am = os.path.join(thu, "giong.mp3")
    doc(c["loiThoai"], giong, am)
    d_am = thoi_luong(am)
    D = d_am + NGHI_GIAY
    h = c.get("hinh") or {}
    loai = h.get("loai", "tieu_de")
    clip = os.path.join(thu, "canh.mp4")
    am_vao = ["-i", am, "-filter_complex", "[1:a]apad=pad_dur=%.2f[a]" % NGHI_GIAY]
    if loai == "so_do" and h.get("hoatHoa"):
        n = int(math.ceil(D * FPS))
        for f in range(n):
            ve_so_do(h, os.path.join(thu, "f%05d.png" % f), t=min(1.0, f / max(1, int(d_am * FPS))))
        chay(["ffmpeg", "-y", "-framerate", str(FPS), "-i", os.path.join(thu, "f%05d.png")] + am_vao +
             ["-map", "0:v", "-map", "[a]", "-t", "%.2f" % D] + MA_HOA + [clip])
        return clip, d_am, D
    anh = os.path.join(thu, "hinh.png")
    if loai == "so_do":
        ve_so_do(h, anh)
    elif loai == "do_thi":
        ve_do_thi(h, anh)
    elif loai == "anh_ai" and anh_ai(h.get("moTa", "physics classroom"), anh, 1000 + i):
        n = int(math.ceil(D * FPS))   # ảnh AI: phóng chậm cho sinh động
        chay(["ffmpeg", "-y", "-i", anh, "-i", am, "-filter_complex",
              "[0:v]scale=2560:-1,zoompan=z='min(zoom+0.0006,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=%d:s=%dx%d:fps=%d[v];"
              "[1:a]apad=pad_dur=%.2f[a]" % (n, W, H, FPS, NGHI_GIAY),
              "-map", "[v]", "-map", "[a]", "-t", "%.2f" % D] + MA_HOA + [clip])
        return clip, d_am, D
    else:
        man_hinh_chu(h.get("tieuDe") or c.get("loiThoai", "")[:60], h.get("phuDe", ""), anh)
    chay(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", anh] + am_vao +
         ["-map", "0:v", "-map", "[a]", "-t", "%.2f" % D] + MA_HOA + [clip])
    return clip, d_am, D


def main():
    ma = sys.argv[1]
    url, bi_mat = os.environ["WEBAPP_URL"], os.environ["VIDEO_SECRET"]
    r = requests.get(url, params={"a": "kichban", "m": ma, "t": bi_mat}, timeout=60)
    kb = r.json()
    if not kb or kb.get("loi") or not kb.get("canh"):
        raise SystemExit("Không lấy được kịch bản: %s" % str(kb)[:300])
    giong = GIONG.get(kb.get("giong", "Nữ"), GIONG["Nữ"])
    shutil.rmtree(TAM, ignore_errors=True); os.makedirs(TAM); os.makedirs("out", exist_ok=True)

    ds, srt, t0, so = [], [], 0.0, 1
    for i, c in enumerate(kb["canh"], 1):
        print("Cảnh %d/%d: %s" % (i, len(kb["canh"]), (c.get("hinh") or {}).get("loai")))
        clip, d_am, D = dung_canh(c, i, giong)
        ds.append(clip)
        cau = tach_cau(c["loiThoai"])
        tong = sum(len(x) for x in cau) or 1
        t = t0
        for x in cau:
            dt = d_am * len(x) / tong
            srt.append("%d\n%s --> %s\n%s\n" % (so, gio_srt(t), gio_srt(t + dt - 0.05), x)); so += 1
            t += dt
        t0 += D

    danh_sach = os.path.join(TAM, "ds.txt")
    with open(danh_sach, "w", encoding="utf-8") as f:
        f.write("".join("file '%s'\n" % os.path.abspath(x) for x in ds))
    noi = os.path.join(TAM, "noi.mp4")
    chay(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", danh_sach, "-c", "copy", noi])
    tep_srt = os.path.join("out", ma + ".srt")
    with open(tep_srt, "w", encoding="utf-8") as f:
        f.write("\n".join(srt))
    kieu = "FontName=Noto Sans,FontSize=15,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=3,Outline=2,Shadow=0,MarginV=24"
    chay(["ffmpeg", "-y", "-i", noi, "-vf", "subtitles=%s:force_style='%s'" % (tep_srt, kieu), "-c:a", "copy",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
          os.path.join("out", ma + ".mp4")])
    print("Xong: %.1f giây, %d cảnh" % (t0, len(ds)))


if __name__ == "__main__":
    main()
