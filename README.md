# 吳威震教授個人網站

Python / Flask 中英雙語 RWD 網站。內容包含個人履歷、研究計畫、學術著作、教學、產學合作、專利、榮譽及專業服務，並提供中英文 Markdown CV 下載。可在 Flask 執行，也可匯出靜態 HTML 至 GitHub Pages。

## 本機啟動

使用 Python 3.12，在專案目錄執行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
cp .env.example .env
python app.py
```

中文頁為 <http://127.0.0.1:5000>，英文頁為 <http://127.0.0.1:5000/?lang=en>。網站無訊息轉送、聊天 API、webhook 或資料庫需求。正式環境設定 `APP_ENV=production`；只有位於可信任反向代理後方時才設定 `TRUST_PROXY=1`。

## 內容與版面

| 網站區域 | Markdown 檔案 |
| --- | --- |
| 個人履歷、學術檔案、學經歷、研究及授課領域、證照 | `CV.md` |
| 專業服務 | `服務.md` |
| 研究計畫 | `國科會計劃.md`、`其他計劃.md` |
| 學術著作 | `期刊論文.md`、`研討會論文.md`、`專著及專書論文.md` |
| 教學與海外實習 | `教育部計劃.md` |
| 產學合作與專利 | `產學計劃.md`、`專利.md` |
| 榮譽 | `榮譽.md` |

履歷位於首頁主視覺後，直接顯示，不需要展開或下載才能閱讀。服務區塊直接顯示全部紀錄。聯絡專線保留於 CV 下載檔，不呈現在網頁上。

研究主視覺使用本機 JavaScript 計算三維座標、透視投影與 SVG 繪圖：

- 移動滑鼠改變視角，拖曳旋轉；觸控螢幕可左右滑動旋轉並保留垂直頁面捲動。
- 方向鍵旋轉，加減鍵或按鈕縮放，Home 或「重設視角」恢復初始位置。
- 圖形只在互動後更新，不持續自動旋轉。偏好減少動態效果時停用滑鼠懸停視差與平滑過渡，仍可主動拖曳或使用鍵盤。
- 停用 JavaScript 時保留靜態研究關係圖、文字說明、履歷與清單。

版面與字級在 `static/site.css`，中英文介面標題在 `labels.py`。

## 修改與翻譯

預設讀取專案內的 `content/zh/`，不會自動讀取上一層的舊附件。若要使用外部來源，可在 `.env` 設定 `SOURCE_MD_DIR`，指定資料夾需包含上表全部 11 份檔案。

中文直接呈現來源 Markdown。英文譯稿在 `content/en/` 的同名檔案中。`content/translations.json` 依原文段落、標題與清單項目的 SHA-256 指紋配對譯文；中文修改後，未同步的英文段落會顯示最新原文並標註待翻譯，避免沿用過時資料。

更新中英文檔案後，維持相同的段落、標題與編號順序，再執行：

```bash
python scripts/sync_content.py --approve-translations
```

此命令配對譯文並更新 `downloads/` 的完整履歷。若只要重新產生 CV，執行 `python scripts/sync_content.py`。使用外部來源時，`--snapshot` 可將來源複製到 `content/zh/`；不要用未更新的外部附件覆蓋專案中的新版本。

Flask 每次請求重新讀取 Markdown，已開啟的頁面每 30 秒檢查更新。靜態版本須重新匯出或部署後重新整理。

## CV 下載

- 中文：`/cv/zh.md`
- 英文：`/cv/en.md`

兩者組合全部 11 份內容，包含完整著作、計畫、專利、榮譽及服務。預先產生的版本位於 `downloads/`。來源資料核對紀錄見 [資料核對.md](docs/資料核對.md)。

## GitHub Pages

`.github/workflows/pages.yml` 會在 `main` 分支推送後執行測試、匯出與部署。儲存庫的 Pages 設定須選擇 **GitHub Actions** 作為來源。靜態頁使用相對路徑，支援 `/myweb/` 子路徑；英文頁為 `en.html`。

本機匯出與預覽：

```bash
python scripts/export_static.py
python -m http.server 8000 --directory dist/pages
```

開啟 <http://127.0.0.1:8000>。靜態輸出只包含中英文 HTML、CSS、JavaScript、圖示及 CV 檔案，不呼叫 Flask API。

## Docker 或 Python 主機

```bash
cp .env.example .env
docker compose up --build -d
```

本機網址為 <http://127.0.0.1:8000>。Compose 掛載 `./content` 為唯讀來源。對外使用時設定 HTTPS 反向代理。`render.yaml` 提供 Python Web Service 設定，不需要持久資料磁碟；套用設定前可自行選擇主機方案。

建置與啟動命令：

```bash
pip install -r requirements.lock
gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 60 'app:create_app()'
```

## 驗證與打包

```bash
pip install -r requirements-dev.txt
python -m pytest -q
node --check static/site.js
python scripts/package.py
```

ZIP 使用檔案白名單，排除 `.env`、資料庫、Git 設定與虛擬環境。
