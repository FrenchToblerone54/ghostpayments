#!/bin/bash
set -e
echo "Building GhostPayments binary..."
cd "$(dirname "$0")/.."
python3.13 -m PyInstaller \
    --onefile \
    --name ghostpayments \
    --add-data "app/static:app/static" \
    --add-data "app/templates:app/templates" \
    run.py
echo "Generating checksums..."
cd dist
sha256sum ghostpayments > ghostpayments.sha256
cd ..
echo "Build complete!"
ls -lh dist/
