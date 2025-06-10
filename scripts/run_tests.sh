#!/bin/bash
set -e # 如果任何命令失敗，立即退出

echo "======================================"
echo "🚀 開始執行蒼狼 AI 專案自動化測試 🚀"
echo "======================================"
echo "執行時間: $(date '+%Y-%m-%d %H:%M:%S %Z')"

# --- 後端測試 ---
echo -e "\n🎨 正在執行後端 Python 程式碼風格檢查 (flake8)..."
# 檢查 flake8 是否安裝，如果未安裝則提示 (可選，但良好實踐)
if ! command -v flake8 &> /dev/null
then
    echo "⚠️  警告: flake8 命令未找到，跳過程式碼風格檢查。"
    echo "   請使用 'pip install flake8' 安裝後再試。"
else
    # 執行 flake8，針對 backend 目錄
    if flake8 backend/; then
        echo "✅ 後端 Python 程式碼風格檢查通過 (flake8)。"
    else
        echo "❌ 後端 Python 程式碼風格檢查未通過 (flake8)。請修正以上錯誤。"
        exit 1 # 風格檢查失敗則退出
    fi
fi

echo -e "\n🧪 執行後端 Pytest 測試 (於 backend/ 目錄)..."
if [ -d "backend" ]; then
  cd backend
  echo "ℹ️  目前目錄: $(pwd)"
  echo "ℹ️  執行 pytest..."
  if pytest; then
    echo "✅ 後端 Pytest 測試通過。"

    # --- 導出 API Schema ---
    echo -e "\n🎨 正在生成 OpenAPI schema (openapi.json)..."
    # 假設 export_api_schema.py 在 scripts/ 目錄下，且我們當前在 backend/ 目錄
    # 需要先返回到專案根目錄才能正確執行
    cd ..
    echo "ℹ️  目前目錄: $(pwd) (準備導出 schema)"
    if python scripts/export_api_schema.py; then
      echo "✅ OpenAPI schema 已成功生成於專案根目錄。"
    else
      echo "❌ OpenAPI schema 生成失敗。"
      exit 1 # Schema 生成失敗則退出
    fi
    # 如果後續還有操作需要從 backend 目錄執行，則需要再次 cd backend
    # 但目前後端測試已結束，下一個是前端測試，所以保持在根目錄是OK的，
    # 或者前端測試自己會 cd frontend。為清晰起見，這裡明確返回根目錄後再進行前端部分。
    # （實際上，上面的 cd .. 已經讓我們在根目錄了）

  else
    echo "❌ 後端 Pytest 測試失敗。"
    # set -e 將確保腳本在此處退出
    # 如果需要更明確的控制或清理操作，可以移除 set -e 並手動 exit 1
    exit 1
  fi
  # 如果 Pytest 成功，且 schema 導出也成功，此時應該仍在專案根目錄
  # 如果 Pytest 失敗，腳本已退出
  # 如果 Pytest 成功但 schema 導出失敗，腳本也已退出
  # 因此，如果能執行到這裡，表示後端測試和 schema 導出都成功了。
  # 如果之前是從 backend 目錄返回的，這裡就不需要再次 cd ..
  # 由於我在 schema 導出前加了 cd .. ，所以現在的 pwd 應該是專案根目錄
  # echo "ℹ️  返回專案根目錄: $(pwd)" # 這行可以省略或確認
else
  echo "⚠️ 警告：未找到 backend/ 目錄，跳過後端測試及 schema 生成。"
fi

# --- 前端測試 ---
echo -e "\n🎨 正在執行前端程式碼品質與風格檢查 (ESLint)..."
if [ -d "frontend" ]; then
  cd frontend
  echo "ℹ️  目前目錄: $(pwd)"
  # 檢查 package.json 中是否有 lint 命令
  if grep -q '"lint":' package.json; then
    echo "ℹ️  偵測到 'npm run lint' 命令，執行中..."
    if npm run lint; then
      echo "✅ 前端 ESLint 檢查通過。"
    else
      echo "❌ 前端 ESLint 檢查未通過。請修正以上錯誤。"
      exit 1 # ESLint 檢查失敗則退出
    fi
  else
    # 如果 package.json 中沒有 lint 命令，嘗試直接執行 npx eslint
    echo "⚠️  警告: 'npm run lint' 未在 package.json 中定義。"
    echo "ℹ️  嘗試執行 npx eslint . --ext .ts,.tsx (請確保 ESLint 已配置且相關套件已安裝)"
    if command -v npx &> /dev/null && npx eslint . --ext .ts,.tsx; then
      echo "✅ 前端 ESLint 檢查通過 (使用 npx eslint)。"
    else
      echo "❌ 前端 ESLint 檢查失敗或 ESLint 未正確配置/安裝 (使用 npx eslint)。"
      echo "   請確保專案已配置 ESLint，或在 package.json 中定義 'lint' 指令。"
      exit 1 # ESLint 檢查失敗則退出
    fi
  fi
  cd .. # 從 frontend 目錄返回專案根目錄
  echo "ℹ️  返回專案根目錄: $(pwd)"
else
  echo "⚠️ 警告：未找到 frontend/ 目錄，跳過前端 ESLint 檢查及 Jest 測試。"
fi


# 確保我們是從專案根目錄開始執行前端測試（如果前端測試的 cd frontend 依賴此）
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
  echo "⚠️ 警告：未找到 frontend/ 目錄，跳過前端 Jest 測試。" # 此警告已在 ESLint 步驟中給出，但保留也無妨
fi

echo -e "\n======================================"
echo "🎉 所有測試執行完畢 🎉"
echo "======================================"
