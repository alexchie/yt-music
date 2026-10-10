"""Email today's YouTube title, description and tags (or a failure notice).

Needs env vars: GMAIL_ADDRESS, GMAIL_APP_PASSWORD, MAIL_TO (optional, defaults to GMAIL_ADDRESS),
DRIVE_OUTPUT_FOLDER (optional, shown in the mail), RUN_URL (optional, link to the Actions page).
"""
import datetime
import json
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent


def main():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    today = datetime.datetime.now(ZoneInfo(cfg["timezone"])).date().isoformat()
    history_path = ROOT / "data" / "history.json"
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else []
    entry = next((h for h in reversed(history) if h["date"] == today), None)
    folder = os.environ.get("DRIVE_OUTPUT_FOLDER", "YT Music Output")
    run_url = os.environ.get("RUN_URL", "")

    if entry is None:
        subject = f"[YT Music] {today} 今天的影片沒有產出"
        body = (
            f"今天（{today}）的影片製作流程沒有成功完成，請到 GitHub Actions 查看錯誤紀錄：\n{run_url}\n"
        )
    else:
        minutes = entry["duration_seconds"] / 60
        warning = f"\n⚠️ AI 產生標題失敗，使用了備用標題：{entry['ai_error']}\n" if entry.get("ai_error") else ""
        subject = f"[YT Music] {today}｜{entry['cover_title']}"
        body = (
            f"今天的影片已上傳到 Google Drive「{folder}」資料夾。\n"
            f"主題概念：{entry['theme_note_zh']}\n"
            f"長度：{minutes:.0f} 分鐘，共 {len(entry['tracks'])} 首\n"
            f"檔案：{', '.join(entry['files'])}\n"
            f"{warning}\n"
            "━━━━━━━━ YouTube 標題 ━━━━━━━━\n"
            f"{entry['youtube_title']}\n\n"
            "━━━━━━━━ YouTube 說明 ━━━━━━━━\n"
            f"{entry['description']}\n\n"
            "━━━━━━━━ 標籤 ━━━━━━━━\n"
            f"{', '.join(entry['tags'])}\n"
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ["GMAIL_ADDRESS"]
    msg["To"] = os.environ.get("MAIL_TO") or os.environ["GMAIL_ADDRESS"]
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(os.environ["GMAIL_ADDRESS"], os.environ["GMAIL_APP_PASSWORD"])
        smtp.send_message(msg)
    print(f"Sent: {subject}")


if __name__ == "__main__":
    main()
