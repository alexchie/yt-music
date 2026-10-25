# YT Music 每日自動影片

每天自動做一支約 1 小時的 lofi 音樂影片：從 Google Drive 音樂庫每天隨機挑 8–9 首、以隨機順序排列，接點都用淡出淡入銜接，
背景是當天從網路抓的一張免版權相關照片（照片來源寫在 YouTube 說明裡，不放在畫面上），配上曲名字幕，
第 0 秒放封面，套用主題庫裡當天的英文主題、標題、說明與標籤，上傳到 Google Drive，
接著自動上傳到 YouTube，早上 8 點寄出通知信。整個流程不需要呼叫 AI，也沒有 API 費用。

| 時間（台灣） | 流程 | 檔案 |
|---|---|---|
| 03:17 | 製作影片並上傳 Google Drive | `.github/workflows/daily-video.yml` |
| 影片做好後 | 把 Drive 裡最新的影片上傳到 YouTube（09:10 再檢查一次） | `.github/workflows/daily-upload.yml` |
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

### 5. YouTube 自動上傳
影片在 Drive（rclone 登入的那個 Google 帳號）裡，上傳到另一個帳號的 YouTube 頻道也沒問題，
因為兩邊各用各的授權。

1. 用**要上傳的 YouTube 帳號**登入 https://console.cloud.google.com/ ，建立新專案。
2. 「API 和服務 → 程式庫」搜尋 **YouTube Data API v3** → 啟用。
3. 「OAuth 同意畫面」：使用者類型選「外部」，填應用程式名稱與 email；完成後按「**發布應用程式**」改成正式版
   （維持「測試中」的話，授權每 7 天就會失效）。
4. 「憑證 → 建立憑證 → OAuth 用戶端 ID」，類型選「**電腦版應用程式**」，下載 JSON 存成 `client_secret.json`。
5. 在自己的電腦執行：
   ```
   pip install google-auth-oauthlib
   python scripts/get_youtube_token.py client_secret.json
   ```
   瀏覽器會跳出登入畫面：選 YouTube 頻道所在的帳號（看到「Google 尚未驗證這個應用程式」就按「進階 → 前往」）。
   終端機會印出三個值。
6. 在 GitHub Secrets 新增 `YT_CLIENT_ID`、`YT_CLIENT_SECRET`、`YT_REFRESH_TOKEN`。
7. （選填）在 Variables 新增 `YT_PRIVACY`：`public`（預設）、`unlisted` 或 `private`。

注意：
- **Google 未審核的專案，上傳的影片一律會被鎖成「私人」**，即使設定 public。要自動公開，需提交
  [YouTube API 稽核申請](https://support.google.com/youtube/contact/yt_api_form)；通過前請到 YouTube Studio 手動改公開或排程。
- 自訂縮圖需要頻道完成手機驗證（https://www.youtube.com/verify）；沒驗證的話影片照常上傳，只是不會設縮圖。
- 每天的上傳紀錄（影片網址）記在 `data/uploads.json`，同一支影片不會重複上傳。
- API 每日免費配額可上傳約 6 支，一天一支綽綽有餘。

### 6. 測試
repo → Actions → Daily video → Run workflow，成功後 Daily YouTube upload 會自動接著跑，再跑一次 Daily email。

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
| `image_query` | （選填）背景照片的英文搜尋關鍵字，例如 `rainy window cozy room`；沒填就用封面標題 |

想改哪一天的標題，直接編輯該筆再 push 即可。主題庫只剩 14 天以內時，通知信會提醒你補充；
若某天沒有排主題，影片照常產出，但會用通用的備用標題，信裡也會註明。

## 可調整的設定（`config.json`）

| 欄位 | 說明 |
|---|---|
| `track_count_min` / `track_count_max` | 每支影片的歌曲數（每天在這個範圍內隨機） |
| `crossfade_seconds` | 歌曲間淡入淡出秒數 |
| `cover_seconds` | 開頭封面顯示秒數 |

## 背景圖
每天從 [Openverse](https://openverse.org/) 搜尋一張和主題相關、**CC0 或公有領域**（不需標示也可商用）的寬幅照片，
用主題的 `image_query`（選填，英文關鍵字）或封面標題搜尋，用過的照片不會再用。
照片出處會加在 YouTube 說明的曲目表後面，例如：
`Background photo: "Rainy window" by Jane (CC0 1.0) via Flickr: https://...`

找不到合適的照片或連不上 Openverse 時，改用 `assets/backgrounds/` 裡的圖（由主題庫的 `background` 決定）。
建議 16:9、至少 1600×900；比例不同會自動從中間裁切。

## 每天的產出
`YT Music Output` 裡會多三個檔案（只保留最近 3 天，更舊的會自動永久刪除，請在 3 天內上傳到 YouTube）：
- `日期_主題.mp4`：影片
- `日期_主題_cover.jpg`：封面（可直接當 YouTube 縮圖）
- `日期_主題_description.txt`：標題、說明（含曲目時間軸）、標籤

每天的結果記在 `data/history.json`。這個檔每天自動 commit，
也讓公開 repo 保持活動，排程不會因 60 天無活動被 GitHub 停用。
