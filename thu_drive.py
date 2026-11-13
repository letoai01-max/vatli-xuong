import io, json, os, sys
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

tt = json.loads(os.environ["GOOGLE_CREDENTIALS"])
cred = service_account.Credentials.from_service_account_info(
    tt, scopes=["https://www.googleapis.com/auth/drive"])
drive = build("drive", "v3", credentials=cred, cache_discovery=False)
fid = os.environ["FOLDER_ID"].strip()

info = drive.files().get(fileId=fid, fields="name,driveId,owners(emailAddress)",
                         supportsAllDrives=True).execute()
print("Thư mục:", info)
print("Loại:", "DRIVE DÙNG CHUNG" if info.get("driveId") else "DRIVE CÁ NHÂN (My Drive)")

media = MediaIoBaseUpload(io.BytesIO(b"%PDF-1.4 thu " * 3000), mimetype="application/pdf")
try:
    f = drive.files().create(body={"name": "thu_upload.pdf", "parents": [fid]},
                             media_body=media, fields="id", supportsAllDrives=True).execute()
    print("✅ Tạo file mới được:", f["id"])
    drive.files().delete(fileId=f["id"], supportsAllDrives=True).execute()
    print("Đã xoá file thử.")
except Exception as e:
    print("❌ Không tạo được file:", str(e)[:400])
    sys.exit(1)
