import os
import requests


def gui_telegram(noi_dung):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("ℹ️ Chưa cấu hình Telegram, bỏ qua gửi tin.", flush=True)
        return False
    lien_ket = ""
    if os.environ.get("GITHUB_RUN_ID"):
        lien_ket = "\n🔗 %s/%s/actions/runs/%s" % (
            os.environ.get("GITHUB_SERVER_URL", "https://github.com"),
            os.environ.get("GITHUB_REPOSITORY", ""), os.environ["GITHUB_RUN_ID"])
    try:
        r = requests.post("https://api.telegram.org/bot%s/sendMessage" % token,
                          data={"chat_id": chat_id, "text": str(noi_dung)[:3800] + lien_ket,
                                "disable_web_page_preview": "true"}, timeout=15)
        if not r.ok:
            print("⚠️ Telegram trả về", r.status_code, r.text[:200], flush=True)
        return r.ok
    except Exception as e:
        print("⚠️ Không gửi được Telegram:", type(e).__name__, flush=True)
        return False
