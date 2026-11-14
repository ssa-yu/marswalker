# Marswalker 3D 徒步整合交接說明

## 目的

將 `/scratch/` 規劃器第 3 步產生的往返路線，交給獨立的第一人稱 3D 徒步頁展示。規劃器負責起點、目標點順序、路徑與地質分類；3D 頁只負責展示，不另行規劃路線。地質圖層共用專案現有 Jezero 圖資，不需要額外搜尋或由使用者另選圖檔。

## 主要串接流程

1. 使用者在 `/scratch/` 完成第 2 步分析與第 3 步路線規劃。
2. `web/scratch/scratch.js` 的 `publishPlannerRoute()` 從 `S.plan.tl` 匯出第 3 步的實際時間線座標。只移除停留期間重複的座標，不重算路徑。
3. 匯出的資料放在同源 `localStorage`，key 為 `marswalker-scratch-route`。資料包含：
   - `coords`：路線經緯度座標
   - `levels`：每一段沿用規劃器 `classAt()` 判定的分類
   - `waypoints`：規劃器實際採用的目標點及分類
   - `created`：產生時間
4. `open3dWalk()` 確認規劃已完成且不是過期規劃後，開啟 iframe，載入 `3d%20first%20point%20view.html`。
5. 3D 頁從同源 `localStorage` 讀取同一筆路線，用於第一人稱行走、路段速度/難度、目標點標記及 HUD。若沒有規劃器資料，頁面目前仍有內建示範路線作為單獨開啟時的 fallback。

## 地質圖層與圖資

規劃器底圖使用 `web/data/jezero/recon/class_ref.png` 顯示參考地質分類。3D 頁載入同一位置的分類圖及正射影像：

- `web/data/jezero/recon/hirise_1m.jpg`：HiRISE 正射影像
- `web/data/jezero/recon/class_ref.png`：規劃器共用的分類圖
- `web/data/jezero/recon/dtm_fine.tif`：選用的高程資料；若讀取失敗，影像及分類圖仍會載入

3D 裡的分類顏色沿用規劃器對應：堅實 `#62d6a4`、崎嶇 `#f4b740`、沙地 `#ff5a4e`、不可通行坡面 `#5a2a6e`。路段/目標分類由規劃器匯出，不由 3D 頁重新判斷。分類圖/正射影像載入失敗時只寫到瀏覽器 console，不再顯示「Jezero 載入失敗」標籤；也已移除額外的 Jezero 載入按鈕與自選檔案入口。

## 相關檔案

| 檔案 | 用途 |
| --- | --- |
| `web/scratch/scratch.js` | 分析/規劃器、分類判斷、匯出路線、開啟 3D iframe |
| `web/scratch/index.html` | 規劃器頁面與 3D iframe 容器 |
| `web/scratch/3d first point view.html` | 3D 徒步展示頁；檔名含空格，呼叫端使用 URL 編碼 |
| `web/data/jezero/recon/hirise_1m.jpg` | 共用 HiRISE 正射影像 |
| `web/data/jezero/recon/class_ref.png` | 共用地質分類影像 |
| `web/data/jezero/recon/dtm_fine.tif` | 選用 DTM |
| `火星徒步 3D 第一人稱導航 (1).html` | 專案根目錄的獨立 3D 頁版本；使用 `web/data/...` 相對路徑 |

3D 子頁在 `/scratch/` 以 `../data/jezero/recon/...` 讀取共用圖資；根目錄獨立 HTML 使用 `web/data/jezero/recon/...`。合併時應保留各自相對路徑。

## 3D 頁檔名變更

展示頁已由 `web/scratch/3d-walk.html` 改名為 `web/scratch/3d first point view.html`，並更新 `scratch.js` 的 iframe URL。合併時要保留新檔名與引用一起變更，避免 iframe 404。部署到靜態伺服器時需支援 URL 編碼後的空格路徑。

## 合併與人工驗收清單

- 確認上述規劃器、3D 頁與資料檔一起合併；不要只合併 HTML 而漏掉共用 raster 圖資。
- 以專案 HTTP server 開啟 `/scratch/`，完成分析與第 3 步規劃，再按 3D 徒步。
- 確認 3D 路線起點、終點、轉折、目標點順序與第 3 步一致，分類標記也一致。
- 確認 3D 頁讀取到 `marswalker-scratch-route`，而不是使用內建 fallback 路線。
- 確認正射影像及分類影像載入，Console/Network 無資產 404；DTM 若不可用，頁面仍可展示。
- 確認不再出現「Jezero 載入失敗」提示，也沒有額外的載入/選檔控制。
- 確認 `3d first point view.html` 的空格 URL 可正常載入。

## 已知事項與待確認

目前 3D 頁會將共用 HiRISE 正射影像與 `class_ref.png` 疊成材質，並嘗試讀取 DTM；不過頁面程式仍包含程式式地表色彩/高度函式及程序生成岩石（例如 `surfaceColor()`、`height()`、`placeRocks()`）。因此，「路線分類及顯示圖層共用規劃器圖資」已串接，但若交接要求「3D 地貌幾何與岩石也必須完全來自真實資料、不可程序生成」，目前版本尚未完全達到，合併前需決定是否移除這些程序生成元素並以 DTM/真實影像建模。不要把目前的程序生成幾何描述為真實地質觀測結果。

## 執行方式

從專案提供的本機 HTTP server 開啟 `/scratch/`。3D 頁透過 `localStorage` 與規劃器交換路線，因此兩頁需同源；直接以 `file://` 開啟時，路線共享及 fetch 圖資可能受瀏覽器限制。
