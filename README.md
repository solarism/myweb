# 吳威震教授個人網站

Python / Flask 中英雙語單頁 RWD 網站。研究主軸為資通安全、人工智慧、區塊鏈與量子金融；頁首導覽可一鍵移至各區。網站完整載入十份 Markdown，提供中英文 Markdown CV 下載，以及學生網站留言 ↔ 教授 LINE 回覆。

## 本機啟動

需要 Python 3.12。請在 `myweb` 資料夾執行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
cp .env.example .env
python app.py
```

開啟 <http://127.0.0.1:5000>，英文版為 <http://127.0.0.1:5000/?lang=en>。Windows 的啟用指令為 `.venv\Scripts\activate`。已建立虛擬環境時只需啟用後執行 `python app.py`。

本機沒有填 LINE 金鑰也能瀏覽完整網站與下載 CV；聊天框會提供 Email 聯絡入口。更改 Python、HTML 或 CSS 後請重新啟動伺服器；只改來源 Markdown 不必重新啟動。

## 內容如何分類

| 網站區域 | 資料來源 |
| --- | --- |
| 首頁、關於、研究及授課領域、學經歷、證照、學術連結、聯絡資訊 | `CV.md` |
| 研究 | `國科會計劃.md`、`其他計劃.md` |
| 學術著作 | `期刊論文.md`、`研討會論文.md`、`專著及專書論文.md` |
| 教學與海外實習 | `教育部計劃.md` |
| 產學合作與專利 | `產學計劃.md`、`專利.md` |
| 榮譽 | `榮譽.md` |

## 修改 Markdown 自動更新

讀取順序：

1. `.env` 若有 `SOURCE_MD_DIR`，以此資料夾為準（十個檔案需齊全）。
2. 若上一層有 `CV.md`，直接讀取上一層十份原始附件。因此您目前修改 `CV` 資料夾的附件，網站下次讀取就會更新。
3. 在 GitHub 部署的獨立專案則使用 `content/zh/` 中的附件副本。

網頁每次請求重新讀取檔案；已開啟的閒置頁面每 30 秒檢查更新，聊天期間暫緩重新整理。清單數量、CV 下載、聯絡 Email 與電話均跟著來源變更。CV 使用 `##` 標題，成果使用編號清單，每一筆由 `1.` 等編號起始；保留各筆之間的 Markdown 結構。

把目前電腦的附件更新帶到 GitHub 前，先執行：

```bash
python scripts/sync_content.py --snapshot
```

此命令只將原附件複製到 `content/zh/`，不會修改上一層的原始檔案。遠端主機不能直接讀取您電腦的 Google Drive 資料夾；要將副本提交 GitHub 並重新部署，遠端內容才會更新。自己架設主機時也可將來源資料夾掛載到伺服器。

## 中英文內容維護

初始十份資料已提供英文版本；中文履歷也補齊了原英文簡介的中文翻譯。英文論文引用通常保留原發表語言，未提供拼音的共同作者保留原姓名。

- 原文：`content/zh/` 或 `SOURCE_MD_DIR` 指定的位置。
- 英文譯稿：`content/en/` 中的同名 Markdown。
- 中文 CV 譯稿：`content/CV.zh.md`。
- 上線配對檔：`content/translations.json`，按原文每個段落／標題／條目的 SHA-256 對應譯文。

**修改中文後，網頁及 CV 立即呈現最新內容；變動段落若尚未同步英文，英文版會顯示最新原文並標註待翻譯，不會沿用過時英文。** 未變動段落仍顯示已完成的英文。這是離線可用的來源對應機制，不會默默把履歷送往第三方翻譯服務。

要同步譯文，編輯 `content/en/` 對應檔；若改了 `CV.md`，也同步 `content/CV.zh.md`。請維持相同的段落、標題、編號順序，確認譯稿確實反映最新原文後執行：

```bash
python scripts/sync_content.py --snapshot --approve-translations
```

此操作會明確將目前原文與譯稿配對。不要在譯稿尚未更新時執行 `--approve-translations`。新增項目時兩種語言都要新增對應段落。網頁上的宣傳標語、導覽文字與品牌設定在 `labels.py`；研究成果本身由 Markdown 載入。

## CV 下載

- 中文：`/cv/zh.md`
- 英文：`/cv/en.md`

兩者均即時組合全部十份附件，包含學經歷、完整著作、各項計畫、專利與榮譽。已預先產生的檔案也在 `downloads/`；`python scripts/sync_content.py` 可重新產生。

## LINE 雙向對話

完整步驟見 [LINE設定.md](docs/LINE設定.md)。需準備：

- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_CHANNEL_SECRET`
- `LINE_ADMIN_USER_ID`（教授本人的 Messaging API user ID）
- 固定的 `SECRET_KEY` 與公開 HTTPS 網址

Webhook 為 `/line/webhook`。學生提交後，教授的 LINE 收到對話代碼；教授傳送 `/reply 代碼 回覆內容`，學生原瀏覽器的聊天框即可顯示回覆。此功能不需要學生的 LINE 帳號，也不會用 AI 代替教授回覆。

聊天 Cookie 為 HttpOnly / SameSite，正式環境加 Secure；後端驗證 LINE 簽章與教授身分，處理 webhook 去重、傳送重試與限流。SQLite 預設保存訊息 30 天；部署時需使用持久磁碟。

## 上傳 GitHub

專案已包含 `.gitignore`、測試工作流程、Docker 與 Render 部署設定。沒有指定 GitHub 帳號或儲存庫，因此沒有建立遠端 repo 或自動公開資料。

方式一：在 GitHub 建立空的 repository，解壓縮 `dist/professor-website.zip`，將裡面 `myweb` 的**內容**上傳到儲存庫根目錄。請保留 `.github` 等隱藏檔案。

方式二：使用 Git（將最後一個網址換成自己的空儲存庫）：

```bash
git init
git add .
git commit -m "Build bilingual professor website"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

`.env`、虛擬環境、聊天紀錄及資料庫均排除。上傳前可執行 `git status --short` 確認。附件中的聯絡資料、經費與證照編號屬網站內容，已依需求保留；詳見 [資料核對.md](docs/資料核對.md)。

## 部署

**GitHub 負責存放程式碼；GitHub Pages 不會執行 Flask，也無法接收 LINE webhook。** 完整功能需要可執行 Python 的主機。

### Render

將 GitHub repo 連結到 Render，使用根目錄的 `render.yaml` 建立 Blueprint。此設定使用付費 Web Service 及 1 GB 持久磁碟，需在 Render 確認方案才會建立，本專案尚未替您訂購或部署。SQLite 檔案在 `/var/data/chat.sqlite3`；請填入秘密環境變數，完成後取得 HTTPS 網址並設定 LINE webhook。

若暫不啟用聊天，可手動建立 Python Web Service，不填三個 LINE 變數；但正式使用聊天前仍須配置持久磁碟。免費服務的臨時檔案系統不能保證聊天紀錄保留。

建置：`pip install -r requirements.lock`。

啟動：`gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 60 'app:create_app()'`。

### Docker 或自己的伺服器

```bash
cp .env.example .env
# 編輯 .env，設定 SECRET_KEY；正式 HTTPS 部署再設 APP_ENV=production
docker compose up --build -d
```

本機網址為 <http://127.0.0.1:8000>，對話放在 Docker named volume。Compose 掛載 `./content`，修改內容可直接反映；對外部署請在前方設定 HTTPS 反向代理。`APP_ENV=production` 需要至少 32 字元的固定 `SECRET_KEY`，並且必須使用 HTTPS 才能正常保存聊天 Cookie。

## 驗證與打包

```bash
pip install -r requirements-dev.txt
python -m pytest -q
node --check static/site.js
python scripts/package.py
```

封裝工具採明確的檔案白名單，不會把 `.env`、聊天資料庫、Git 設定或虚擬環境裝入 ZIP。網站對外啟用前，仍需用真實 LINE 帳號完成一次雙向收發測試。

## 主要檔案

```text
app.py                  Flask 入口、網頁、CV 與安全標頭
content_store.py        Markdown 讀取、翻譯配對、HTML 清理
chat.py                 LINE API、webhook、SQLite 對話
labels.py               中英文介面與網站標語
templates/index.html    單頁結構
static/                 RWD CSS、對話及導覽 JavaScript
content/                十份附件副本與英文譯稿
downloads/              預先產生的中英文 Markdown CV
tests/                  資料與 LINE 整合測試
scripts/                同步、CV 產生及打包工具
docs/                   LINE 設定與附件核對紀錄
```

部署文件依據：[Flask 正式部署](https://flask.palletsprojects.com/en/stable/deploying/)、[Render Flask 部署](https://render.com/docs/deploy-flask)、[Render 持久磁碟](https://render.com/docs/disks)。
