# YT Music 每日自動影片

每天自動做一支約 1 小時的 lofi 音樂影片：從 Google Drive 音樂庫隨機挑 12–15 首、淡入淡出接在一起，
配上客廳喇叭背景與曲名字幕，第 0 秒放封面，套用主題庫裡當天的英文主題、標題、說明與標籤，
上傳到 Google Drive，早上 8 點寄出通知信。整個流程不需要呼叫 AI，也沒有 API 費用。

| 時間（台灣） | 流程 | 檔案 |
|---|---|---|
| 03:17 | 製作影片並上傳 Google Drive | `.github/workflows/daily-video.yml` |
| 07:52 | 寄出 YouTube 標題、說明、標籤 | `.github/workflows/daily-email.yml` |

GitHub 排程常會晚幾分鐘到十幾分鐘才啟動，所以信件排在 07:52。

## 一次性設定

### 1. Google Drive
建立兩個資料夾（放在「我的雲端硬碟」最上層）：
- `YT Music Library`：放音樂檔（mp3 / m4a / wav / flac 都可以），檔名就是畫面上顯示的曲名
- `YT Music Output`：成品會放在這裡

### 2. rclone（讓 GitHub 能存取你的 Google Drive）
在自己的電腦執行：
```
winget install Rclone.Rclone
rclone config
```
依序選：`n`（新增）→ 名稱輸入 `gdrive` → 類型選 `drive` → client_id / secret 直接 Enter →
scope 選 `1`（完整存取）→ 其他一路 Enter → `Use web browser` 選 `y`，在瀏覽器登入 Google 並允許。
完成後執行 `rclone config file` 找到設定檔，把整個檔案內容複製起來（下一步用）。

### 3. Gmail 應用程式密碼
Google 帳戶需先開啟兩步驟驗證，再到 https://myaccount.google.com/apppasswords 建立一組 16 碼密碼。

### 4. GitHub Secrets
repo → Settings → Secrets and variables → Actions → New repository secret：

| 名稱 | 內容 |
|---|---|
| `RCLONE_CONF` | 第 2 步複製的 rclone 設定檔全文 |
| `GMAIL_ADDRESS` | 寄信用的 Gmail 地址 |
| `GMAIL_APP_PASSWORD` | 第 3 步的 16 碼密碼 |
| `MAIL_TO` | （選填）收信地址，不填就寄給自己 |

資料夾名稱不同的話，可在同一頁的 Variables 新增 `DRIVE_LIBRARY_FOLDER` / `DRIVE_OUTPUT_FOLDER`。

### 5. 測試
repo → Actions → Daily video → Run workflow，成功後再跑一次 Daily email。

## 主題庫（`data/themes.json`）
每天一個主題，依日期排好，目前排到 **2027-01-18**。每個主題包含：

| 欄位 | 說明 |
|---|---|
| `date` | 使用日期（台灣時間） |
| `background` | 當天的背景圖檔名（`assets/backgrounds/` 裡） |
| `cover_title` / `cover_subtitle` | 封面上的大標與小字 |
| `youtube_title` | YouTube 標題 |
| `description` | 說明文前兩段；程式會再接上一句訂閱邀請、曲目時間軸和 hashtag |
| `hashtags` / `tags` | 程式會在 `tags` 後面自動補上 lofi 通用標籤 |
| `theme_note_zh` | 給你看的中文主題說明，寫在通知信裡 |

想改哪一天的標題，直接編輯該筆再 push 即可。主題庫只剩 14 天以內時，通知信會提醒你補充；
若某天沒有排主題，影片照常產出，但會用通用的備用標題，信裡也會註明。

## 可調整的設定（`config.json`）

| 欄位 | 說明 |
|---|---|
| `track_count_min` / `track_count_max` | 每支影片的歌曲數 |
| `target_minutes` | 目標長度（分鐘） |
| `crossfade_seconds` | 歌曲間淡入淡出秒數 |
| `cover_seconds` | 開頭封面顯示秒數 |

## 背景圖
背景圖放在 `assets/backgrounds/`（png / jpg / webp），每天用哪一張由主題庫的 `background` 決定。
建議 16:9、至少 1600×900；比例不同會自動從中間裁切。

## 每天的產出
`YT Music Output` 裡會多三個檔案：
- `日期_主題.mp4`：影片
- `日期_主題_cover.jpg`：封面（可直接當 YouTube 縮圖）
- `日期_主題_description.txt`：標題、說明（含曲目時間軸）、標籤

每天的結果記在 `data/history.json`。這個檔每天自動 commit，
也讓公開 repo 保持活動，排程不會因 60 天無活動被 GitHub 停用。
