#!/bin/bash
# 上传 WSJ PDF 到 R2 bucket
# 用法: bash upload_to_r2.sh [--date YYYY-MM-DD]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/output"
BUCKET="wsj-reader"
TARGET_DATE=""
COUNT=0

# 解析参数
while [[ $# -gt 0 ]]; do
  case $1 in
    --date) TARGET_DATE="$2"; shift 2 ;;
    *) echo "用法: $0 [--date YYYY-MM-DD]"; exit 1 ;;
  esac
done

if [ ! -d "$OUTPUT_DIR" ]; then
  echo "output 目录不存在: $OUTPUT_DIR"
  exit 1
fi

for date_dir in "$OUTPUT_DIR"/*/; do
  date=$(basename "$date_dir")
  [[ $date =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || continue

  # 如果指定了日期，只处理该日期
  if [ -n "$TARGET_DATE" ] && [ "$date" != "$TARGET_DATE" ]; then
    continue
  fi

  pdf_dir="$date_dir/pdf"
  [ -d "$pdf_dir" ] || continue

  for pdf in "$pdf_dir"/*.pdf; do
    [ -f "$pdf" ] || continue
    filename=$(basename "$pdf")
    key="$date/pdf/$filename"
    echo "Uploading $key"
    npx wrangler r2 object put "$BUCKET/$key" --file "$pdf" --content-type "application/pdf" --remote
    ((COUNT++))
  done
done

echo "Done. Uploaded $COUNT files."
