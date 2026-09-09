# LINE 雙向留言設定

程式已完成，但您的 LINE 官方帳號、金鑰及正式網站網址尚未設定，因此目前不會真的傳送 LINE 訊息。這是教授本人回覆的留言橋接，沒有生成式 AI 自動代答。

## 1. 建立官方帳號與 Messaging API

1. 到 [LINE Official Account Manager](https://manager.line.biz/) 建立或選擇官方帳號。
2. 在官方帳號的設定中啟用 Messaging API，選擇正確的 provider；provider 不可任意更換。
3. 到 [LINE Developers Console](https://developers.line.biz/console/) 選擇對應 channel。
4. 取得 **Channel secret** 與 **Channel access token**。支援長效 token；若採用需到期更新的 token，請安排更新。
5. 用教授自己的 LINE 加入此官方帳號為好友。學生只需使用網站聊天框，不需要加入 LINE。

官方說明：[開始使用 Messaging API](https://developers.line.biz/en/docs/messaging-api/getting-started/)、[建立聊天機器人](https://developers.line.biz/en/docs/messaging-api/building-bot/)。

## 2. 設定教授本人識別碼

教授的 Messaging API user ID 格式為 `U` 加 32 個十六進位字元，並非平常搜尋好友使用的 LINE ID。

若教授的 LINE 已連結到登入 Developers Console 的 Business ID，可在 channel 的 **Basic settings → Your user ID** 取得。若不是同一人，請由該 provider 下經過簽章驗證的 webhook 取得指定教授的 `source.userId`。程式不會將「第一位傳訊者」自動設為管理員。

官方說明：[取得 user ID](https://developers.line.biz/en/docs/messaging-api/getting-user-ids/)。

## 3. 放入伺服器環境變數

本機放在 `.env`，正式部署放在主機的秘密環境變數設定，請勿提交到 GitHub。

```dotenv
APP_ENV=production
SECRET_KEY=至少32字元且固定不變的隨機值
LINE_CHANNEL_ACCESS_TOKEN=您的ChannelAccessToken
LINE_CHANNEL_SECRET=您的ChannelSecret
LINE_ADMIN_USER_ID=教授的MessagingAPIUserID
DATABASE_PATH=/var/data/chat.sqlite3
```

三個 LINE 變數都設定後才會開啟留言表單；程式無法只根據「有填入字串」判斷 LINE 權限是否有效，請完成第 5 步實測。`SECRET_KEY` 用於簽署訪客的對話 Cookie，重設後既有訪客無法恢復原對話。

## 4. 設定 HTTPS webhook

部署後，將 LINE Developers Console 的 Webhook URL 設成：

```text
https://您的網域/line/webhook
```

按 **Verify**，啟用 **Use webhook** 與 **Webhook redelivery**。正式 webhook 必須使用可信憑證的 HTTPS；LINE 無法存取 `localhost`。視需求關閉官方帳號的預設自動回覆與歡迎訊息，避免多餘回覆。

伺服器會先驗證原始內容的 HMAC-SHA256 簽章，再處理 JSON。只有指定教授的一對一 LINE 文字指令可回覆網站；群組、其他使用者與附件都不會寫入學生對話。重复 webhook 以 `webhookEventId` 去重，學生間以獨立的簽署 Cookie 隔離。

官方說明：[驗證簽章](https://developers.line.biz/en/docs/messaging-api/verify-webhook-signature/)、[接收 webhook](https://developers.line.biz/en/docs/messaging-api/receiving-messages/)。

## 5. 實際收發

學生在網站送出訊息後，教授會在 LINE 官方帳號的對話收到：

```text
網站留言 [A1B2C3D4E5F6]
姓名：王同學

老師您好，我想了解量子金融研究。

回覆此學生，請傳送：
/reply A1B2C3D4E5F6 您的回覆內容
```

教授在**與官方帳號的 LINE 對話**中傳送：

```text
/reply A1B2C3D4E5F6 歡迎！可以先介紹你的背景與研究興趣。
```

程式會將回覆存入該學生的網站對話，並回傳 LINE 確認訊息。學生在原瀏覽器開著對話框時，大約 3.5 秒內會看到回覆。關閉聊天框不會刪除對話；在保存期限內用原瀏覽器回到網站即可查看。清除 Cookie、使用無痕模式或換裝置不會繼承原對話。LINE 內建「引用回覆」未串接，請使用上面的 `/reply` 指令。

網站顯示「已提交至 LINE」只表示 LINE API 接受請求。封鎖官方帳號、好友資格與額度等因素仍可能影響實際送達，因此啟用時一定要確認：**學生送出 → 教授 LINE 收到 → 教授回覆 → 原學生網站看到**。

## 6. 維運與限制

- 使用 SQLite 保存對話，必須掛載持久磁碟；目前部署配置為單一服務实例，適合教授個人網站。
- 預設保存 30 天，`CHAT_RETENTION_DAYS` 可調整。聊天相關請求會清理過期內容；可排程每天執行 `flask --app app:create_app cleanup-chat`，確保無人使用時也定期刪除。備份也應採用相同保存期限。
- 每個來源 IP 每分鐘最多 5 次傳送尝試（包含重試）；全站預設每天 100 次，可用 `CHAT_GLOBAL_DAILY_LIMIT` 修改。多位同學共用校園 IP 時會共享限制。
- 失敗的訊息仍留在對話中；23 小時內可按重試。重試使用同一個 LINE retry key，降低網路逾時導致重複送出的風險。沒有無限背景重送。
- LINE Push API 訊息可能計入官方帳號月額度，費用與可用額度依地區及帳號方案而定。
- 正式環境必須 HTTPS。只有部署在會清理偽造代理標頭的可信反向代理後方時，才設定 `TRUST_PROXY=1`。
- 目前支援文字訊息，不支援圖片、檔案或跨裝置對話恢復。大量公開流量時應再加反向代理層的流量限制。

官方參考：[Push API](https://developers.line.biz/en/reference/messaging-api/#send-push-message)、[重試機制](https://developers.line.biz/en/docs/messaging-api/retrying-api-request/)、[計價方式](https://developers.line.biz/en/docs/messaging-api/pricing/)。
