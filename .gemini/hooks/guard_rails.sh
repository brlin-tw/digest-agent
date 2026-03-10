#!/bin/bash
# .gemini/hooks/guard_rails.sh
# 此腳本用於攔截對關鍵目錄或檔案的危險操作

TARGET="$1"
ACTION="$2" # 假設作為參數傳入，或從環境變數判斷

# 檢查是否試圖刪除 data/ 目錄或 app.py
if [[ "$TARGET" == *"data"* ]] || [[ "$TARGET" == *"app.py"* ]]; then
  echo "🚫 [守護者攔截] 檢測到危險操作！" >&2
  echo "警告：試圖刪除或修改核心保護對象: $TARGET" >&2
  echo "身為你的 SRE 守護者，我必須拒絕此操作以維持系統穩定性。" >&2
  
  # 回傳符合 Gemini CLI 規範的 JSON
  echo '{"decision": "deny", "reason": "Protected core files/directories"}'
  exit 1
fi

echo '{"decision": "allow"}'
exit 0