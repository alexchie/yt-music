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
    entries = [h for h in history if h["date"] == today]
    uploads_path = ROOT / "data" / "uploads.json"
    uploads = json.loads(uploads_path.read_text(encoding="utf-8")) if uploads_path.exists() else []
    links = {u["file"]: u for u in uploads}
    folder = os.environ.get("DRIVE_OUTPUT_FOLDER", "YT Music Output")
    run_url = os.environ.get("RUN_URL", "")

    if not entries:
        subject = f"[YT Music] {today} 今天的影片沒有產出"
        body = (
            f"今天（{today}）的影片製作流程沒有成功完成，請到 GitHub Actions 查看錯誤紀錄：\n{run_url}\n"
        )
    else:
        last = entries[-1]
        warning = ""
        if not all(e.get("scheduled_theme", True) for e in entries):
            warning += "\n⚠️ 有影片沒有可用的主題，使用了備用的通用標題。\n"
        if last.get("themes_remaining", 99) < 14:
            warning += f"\n⚠️ 早上的主題庫只剩 {last['themes_remaining']} 天，請盡快補充 data/themes.json。\n"
        if last.get("pool_remaining", 99) < 14:
            warning += f"\n⚠️ 晚上的主題庫只剩 {last['pool_remaining']} 個，請盡快補充 data/themes_pool.json。\n"
        subject = f"[YT Music] {today}｜{' / '.join(e.get('zh', {}).get('cover_title', e['cover_title']) for e in entries)}"
        parts = [
            f"今天共 {len(entries)} 支影片，每支各有中文版和英文版，檔案在 Google Drive「{folder}」資料夾。\n"
            f"音樂庫目前共 {last.get('library_size', '?')} 首。\n{warning}"
        ]
        for e in entries:
            parts.append(
                f"\n━━━━━━━━ {e.get('publish_at', '')[11:16]} 發布｜{e['cover_title']} ━━━━━━━━\n"
                f"主題概念：{e['theme_note_zh']}\n"
                f"長度：{e['duration_seconds'] / 60:.0f} 分鐘，共 {len(e['tracks'])} 首：{'、'.join(e['tracks'])}\n"
            )
            for lang, v in e.get("versions", {}).items():
                desc_file = next((f for f in e["files"] if f.endswith(f"_{lang}_description.txt")), "")
                up = links.get(desc_file)
                status = f"{up['url']}（{'已排程' if up.get('publish_at') else up['privacy']}）" if up else "尚未上傳"
                parts.append(
                    f"\n【{'中文版' if lang == 'zh' else '英文版'}】{status}\n"
                    f"標題：{v['youtube_title']}\n\n說明：\n{v['description']}\n\n標籤：{', '.join(v['tags'])}\n"
                )
        body = "".join(parts)

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
