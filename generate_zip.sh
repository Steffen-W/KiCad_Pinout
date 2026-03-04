#!/bin/bash

set -e

# Restore metadata if backup exists
cleanup() {
    if [[ -f "metadata_.json" ]]; then
        mv metadata_.json metadata.json
    fi
    if [[ -n "$temp_dir" ]] && [[ -d "$temp_dir" ]]; then
        rm -rf "$temp_dir"
    fi
}
trap cleanup EXIT

# Check for required tools
if ! command -v jq &> /dev/null; then
    echo "Error: jq is required but not installed (apt install jq)"
    exit 1
fi
if ! command -v zip &> /dev/null; then
    echo "Error: zip is required but not installed (apt install zip)"
    exit 1
fi

# Clean up old ZIP
rm -f KiCadPinout.zip

# Update metadata version
mv metadata.json metadata_.json
jq --arg today "$(date +%Y.%m.%d)" '.versions[0].version |= $today' metadata_.json > metadata.json

# Create temporary build directory
temp_dir=$(mktemp -d)
build_dir="$temp_dir/build"
mkdir -p "$build_dir"

# Copy metadata and resources
cp metadata.json "$build_dir/"
cp -r resources "$build_dir/"

# Copy plugin files into plugins/ (required by KiCad PCM)
mkdir -p "$build_dir/plugins/KiCadPinout"
git ls-files -- 'KiCadPinout/*.png' 'KiCadPinout/*.py' 'KiCadPinout/plugin.json' \
    'KiCadPinout/requirements.txt' | while read -r f; do
    cp "$f" "$build_dir/plugins/KiCadPinout/"
done
[[ -d "KiCadPinout/kicad_advanced" ]] && cp -r KiCadPinout/kicad_advanced "$build_dir/plugins/KiCadPinout/"

cp __init__.py "$build_dir/plugins/"

# Clean up unwanted files
find "$build_dir" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$build_dir" -name "*.pyc" -delete 2>/dev/null || true
find "$build_dir" -name "*.log" -delete 2>/dev/null || true
find "$build_dir" -name "*.fbp" -delete 2>/dev/null || true

# Create ZIP
zip_target="$(pwd)/KiCadPinout.zip"
cd "$build_dir"
zip -rq "$zip_target" .
cd - > /dev/null

# Show contents
echo ""
echo "Package contents:"
unzip -l KiCadPinout.zip
zip_size=$(stat -c%s KiCadPinout.zip 2>/dev/null || stat -f%z KiCadPinout.zip)
echo "ZIP size: $((zip_size / 1024))K"
echo "ZIP file created: $(realpath KiCadPinout.zip)"
