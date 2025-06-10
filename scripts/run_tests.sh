#!/bin/bash
set -e # 如果任何命令失敗，立即退出

echo "======================================"
echo "🚀 開始執行蒼狼 AI 專案自動化測試 🚀"
echo "======================================"
echo "執行時間: $(date '+%Y-%m-%d %H:%M:%S %Z')"

# --- 後端測試 ---
echo -e "\n🧪 執行後端 Pytest 測試 (於 backend/ 目錄)..."
if [ -d "backend" ]; then
  cd backend
  echo "ℹ️  目前目錄: $(pwd)"
  echo "ℹ️  執行 pytest..."
  if pytest; then
    echo "✅ 後端 Pytest 測試通過。"
  else
    echo "❌ 後端 Pytest 測試失敗。"
    # set -e 將確保腳本在此處退出
    # 如果需要更明確的控制或清理操作，可以移除 set -e 並手動 exit 1
    exit 1
  fi
  cd ..
  echo "ℹ️  返回專案根目錄: $(pwd)"
else
  echo "⚠️ 警告：未找到 backend/ 目錄，跳過後端測試。"
fi

# --- 前端測試 ---
echo -e "\n🧪 執行前端 Jest 測試 (於 frontend/ 目錄)..."
if [ -d "frontend" ]; then
  cd frontend
  echo "ℹ️  目前目錄: $(pwd)"
  echo "ℹ️  執行 npm test -- --passWithNoTests..."
  # npm test 會執行 package.json 中 "scripts": { "test": "jest" }
  # Jest 預設會在沒有找到測試檔案時失敗 (除非有 --passWithNoTests 或類似配置)
  # Next.js 的 Jest 配置可能已經處理了這一點，但明確加上更安全
  if npm test -- --passWithNoTests; then
    echo "✅ 前端 Jest 測試通過 (或沒有找到測試檔案)。"
  else
    echo "❌ 前端 Jest 測試失敗。"
    exit 1
  fi
  cd ..
  echo "ℹ️  返回專案根目錄: $(pwd)"
else
  echo "⚠️ 警告：未找到 frontend/ 目錄，跳過前端測試。"
fi

echo -e "\n======================================"
echo "🎉 所有測試執行完畢 🎉"
echo "======================================"
