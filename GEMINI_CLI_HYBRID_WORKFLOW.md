# 🚀 Gemini CLI + Antigravity: 雙劍合璧實戰指南

這份文件定義了如何在 **Antigravity IDE** 中整合 **Gemini CLI**，將其定位為「系統守護者 (SRE Guardian)」與「背景監控者 (Watcher)」。

---

## 🎭 角色定位 (The Role Play)

| 平台 | 角色 | 職責 |
| :--- | :--- | :--- |
| **Antigravity (GUI)** | **創造者 (The Creator)** | 視覺開發、UI 調校、即時代碼編寫、對話式開發。 |
| **Gemini CLI (Terminal)** | **守護者 (The Guardian)** | 背景任務監控 (make dev)、系統安全攔截 (Hooks)、自動化測試排程。 |

---

## 🔮 啟動咒語 (The Magic Sentence)

在 Antigravity 的終端機 (Terminal) 中輸入 `gemini` 並按下回車，接著輸入以下指令：

> **「請作為我的 SRE 守護者 (Guardian)，在背景執行 `make dev` 啟動 Streamlit 服務並給我 shell_id。持續監控輸出日誌，若發現任何 Traceback 或 Error，請立刻主動分析並回報。同時，請嚴格執行我們在 `.gemini/hooks/` 定義的安全攔截規則，防止任何對 `data/` 或 `app.py` 的誤刪操作。」**

---

## 🛡️ 核心守護功能 (Core Guardian Features)

### 1. 背景日誌監控 (Watcher Mode)
*   **功能**：Gemini CLI 會調用 `run_in_background: true`。
*   **價值**：你不需要盯著終端機看日誌，當 Streamlit 噴錯（例如 Python ImportError 或 SQL 鎖定）時，Agent 會主動跳出來提醒你並提供修正建議。

### 2. 物理級安全攔截 (Hooks Protection)
*   **機制**：利用 `.gemini/hooks/guard_rails.sh`。
*   **價值**：即使你在 IDE 中不小心寫錯了「刪除目錄」的腳本，終端機裡的 Gemini CLI 也會因為觸發 `BeforeTool` Hook 而強制阻擋，保護 `data/digest.db` 不被誤刪。

### 3. 自動化回饋迴圈 (Feedback Loop)
*   **機制**：利用 `AfterTool` Hook 連結 `make test`。
*   **價值**：當你在 Antigravity 儲存檔案後，Gemini CLI 會在背景自動跑測試，並在終端機視窗默默回報測試結果，實現真正的「自癒式開發」。

---

## 🛠️ 工作坊示範流程 (Workshop Flow)

1.  **啟動**：在 Antigravity 終端機執行上述「咒語」。
2.  **開發**：在 Antigravity 編輯器中修改 `src/pages/1_articles.py` 的 UI。
3.  **錯誤觸發**：故意在代碼中寫一個語法錯誤。
4.  **驚喜回饋**：展示 Gemini CLI 如何在背景發現錯誤並主動彈出通知。
5.  **安全展示**：嘗試在終端機刪除 `app.py`，展示 Hooks 的攔截成功畫面。

---
**💡 記得：** 好的架構師會利用工具的差異化（IDE 的靈活 vs. CLI 的嚴謹）來打造最穩固的開發流程！🚀
