#!/bin/zsh
# 增量上传 WSJ PDF 到 R2 bucket（通过 API 对比远程已有文件）
# 用法: bash upload_to_r2.sh [--date YYYY-MM-DD] [--force]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/output"
BUCKET="wsj-reader"
API_BASE="https://wsj.897654321.space/api"
TARGET_DATE=""
FORCE=false
UPLOADED=0
SKIPPED=0
MAX_PARALLEL=5

# 解析参数
while [[ $# -gt 0 ]]; do
  case $1 in
    --date) TARGET_DATE="$2"; shift 2 ;;
    --force) FORCE=true; shift ;;
    *) echo "用法: $0 [--date YYYY-MM-DD] [--force]"; exit 1 ;;
  esac
done

if [ ! -d "$OUTPUT_DIR" ]; then
  echo "output 目录不存在: $OUTPUT_DIR"
  exit 1
fi

for date_dir in "$OUTPUT_DIR"/*/; do
  date=$(basename "$date_dir")
  [[ $date =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || continue

  if [ -n "$TARGET_DATE" ] && [ "$date" != "$TARGET_DATE" ]; then
    continue
  fi

  pdf_dir="$date_dir/pdf"
  [ -d "$pdf_dir" ] || continue

  # 获取远程已有文件列表
  remote_files=""
  if [ "$FORCE" = false ]; then
    remote_files=$(curl -s "$API_BASE/files/$date" 2>/dev/null || echo "")
  fi

  for pdf in "$pdf_dir"/*.pdf; do
    [ -f "$pdf" ] || continue
    filename=$(basename "$pdf")

    # 检查远程是否已存在
    if [ "$FORCE" = false ] && echo "$remote_files" | grep -qF "\"$filename\""; then
      ((SKIPPED++))
      continue
    fi

    key="$date/pdf/$filename"
    echo "Uploading $key"
    npx wrangler r2 object put "$BUCKET/$key" --file "$pdf" --content-type "application/pdf" --remote &
    ((UPLOADED++))

    # 控制并发数
    if (( $(jobs -rp | wc -l) >= MAX_PARALLEL )); then
      wait -n
    fi
  done
done

wait
echo "Done. Uploaded $UPLOADED, skipped $SKIPPED (already on remote)."
