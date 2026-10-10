#!/bin/bash

DIR="$1"

if [ -z "$DIR" ] || [ ! -d "$DIR" ]; then
    echo "Usage: $0 <directory>"
    exit 1
fi

while IFS= read -r -d '' file; do
    echo "===== $file seed to role collection ====="
    uv run --env-file .env -m resume_matcher roles add $file
    echo
done < <(find "$DIR" -maxdepth 1 -type f -print0)
