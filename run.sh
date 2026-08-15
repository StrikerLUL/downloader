#!/bin/bash

# --- VOE Video Downloader - CLI Runner ---
SOURCE_DIR="$( cd "$( dirname "$(readlink -f "${BASH_SOURCE[0]}")" )" &> /dev/null && pwd )"

if [ -d "$SOURCE_DIR/venv" ]; then
    exec "$SOURCE_DIR/venv/bin/python3" "$SOURCE_DIR/download_video.py" "$@"
else
    exec python3 "$SOURCE_DIR/download_video.py" "$@"
fi
