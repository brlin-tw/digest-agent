---
name: git-expert
description: 檢查並總結目前的程式碼變更 (local changes) 並產生專業的 Commit Message 建議
---

# Git 常見問題與提交建議 (Git Expert)

## 技能目標
協助開發者快速了解當前專案的變更內容，並生成符合 Conventional Commits 規範的提交訊息。

## 執行步驟
1. **檢查狀態**：執行 `git status` 了解哪些檔案已被修改。
2. **分析差異 (Staged)**：對已暫存 (staged) 的變更執行 `git diff --cached`。
3. **分析差異 (Unstaged)**：對未暫存 (unstaged) 的變更執行 `git diff`。
4. **生成建議**：
   - 使用條列式總結變更點。
   - 根據變更類型 (feat, fix, docs, style, refactor, perf, test, chore) 產生 commit message。

## 範例觸發詞
- "幫我看看我剛才改了什麼？"
- "幫我檢查 local changes 並產生 commit message"
- "產生這份變更的提交訊息"
