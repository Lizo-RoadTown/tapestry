#!/usr/bin/env bash
# Create a new ADR file from the template.
# Usage: ./new_adr.sh "short title in title case"

set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 \"<short title>\"" >&2
  exit 1
fi

title="$1"
adr_dir="${ADR_DIR:-docs/adr}"
template="${ADR_TEMPLATE:-$(dirname "$0")/../assets/adr-template.md}"

mkdir -p "$adr_dir"

# Find next number
last=$(ls "$adr_dir" 2>/dev/null | grep -E '^[0-9]{4}-' | sort | tail -1 | cut -d- -f1 || true)
if [ -z "$last" ]; then
  next="0001"
else
  next=$(printf "%04d" $((10#$last + 1)))
fi

# Slugify title
slug=$(echo "$title" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g' | sed -E 's/^-+|-+$//g')

file="$adr_dir/${next}-${slug}.md"
date=$(date +%Y-%m-%d)

if [ ! -f "$template" ]; then
  echo "Template not found at $template" >&2
  exit 1
fi

# Substitute placeholders
sed -e "s/{{NUMBER}}/$next/g" \
    -e "s/{{TITLE}}/$title/g" \
    -e "s/{{DATE}}/$date/g" \
    "$template" > "$file"

echo "Created $file"
