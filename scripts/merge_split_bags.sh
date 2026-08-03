#!/bin/bash

# Exit immediately if any command fails
set -e

# Default values
INPUT_DIR="."

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -i|--input-dir) INPUT_DIR="$2"; shift ;;
        -h|--help)
            echo "Usage: $0 [-i input_directory]"
            echo "  -i, --input-dir    Directory containing the split .mcap or .mcap.zstd files (default: current directory)"
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Navigate to input directory
cd "$INPUT_DIR" || { echo "Error: Cannot access directory $INPUT_DIR"; exit 1; }

# 0. Ensure 'mcap' CLI is available, download automatically if missing
if ! command -v mcap &> /dev/null; then
    echo "MCAP CLI tool not found. Detecting system architecture..."
    ARCH=$(uname -m)
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    
    if [ "$OS" = "linux" ]; then
        if [ "$ARCH" = "x86_64" ]; then
            MCAP_FILE="mcap-linux-amd64"
        elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
            MCAP_FILE="mcap-linux-arm64"
        elif [ "$ARCH" = "armv7l" ] || [ "$ARCH" = "armhf" ]; then
            MCAP_FILE="mcap-linux-arm"
        else
            echo "Error: Unsupported Linux architecture: $ARCH"
            exit 1
        fi
    elif [ "$OS" = "darwin" ]; then
        if [ "$ARCH" = "x86_64" ]; then
            MCAP_FILE="mcap-macos-amd64"
        elif [ "$ARCH" = "arm64" ]; then
            MCAP_FILE="mcap-macos-arm64"
        else
            echo "Error: Unsupported macOS architecture: $ARCH"
            exit 1
        fi
    else
        echo "Error: Unsupported operating system: $OS"
        exit 1
    fi

    DOWNLOAD_URL="https://github.com/foxglove/mcap/releases/latest/download/$MCAP_FILE"
    echo "Downloading MCAP CLI from $DOWNLOAD_URL..."
    
    mkdir -p ~/.local/bin
    curl -L "$DOWNLOAD_URL" -o ~/.local/bin/mcap
    chmod +x ~/.local/bin/mcap
    
    # Temporarily add to PATH for this script session if not already present
    export PATH="$HOME/.local/bin:$PATH"
    
    if command -v mcap &> /dev/null; then
        echo "Successfully installed mcap to ~/.local/bin/mcap"
    else
        echo "Error: Failed to install mcap CLI automatically."
        exit 1
    fi
fi

# 1. Decompress .mcap.zstd files only if the target .mcap doesn't exist yet
if ls *.mcap.zstd 1> /dev/null 2>&1; then
    echo "Checking for compressed .mcap.zstd files in $(pwd)..."
    for zstd_file in *.mcap.zstd; do
        target_mcap="${zstd_file%.zstd}"
        if [ -f "$target_mcap" ]; then
            echo "Skipping decompression for $zstd_file (target $target_mcap already exists)."
        else
            echo "Decompressing $zstd_file..."
            zstd -d "$zstd_file"
        fi
    done
fi

# Check if any .mcap files exist at all
if ! ls *.mcap 1> /dev/null 2>&1; then
    echo "Error: No .mcap files found to merge."
    exit 1
fi

# 2. Check for uncompressed/raw .mcap files that might be corrupted/incomplete (e.g. final split)
echo "Checking for raw .mcap files needing recovery..."
for mcap_file in *.mcap; do
    # Skip already fixed files if script is re-run
    if [[ "$mcap_file" == *_fixed.mcap ]]; then
        continue
    fi
    
    zstd_equivalent="${mcap_file}.zstd"
    
    # If the raw .mcap exists but a matching .zstd file does NOT exist, it's likely an uncompressed trailing split
    if [ ! -f "$zstd_equivalent" ]; then
        fixed_file="${mcap_file%.mcap}_fixed.mcap"
        
        # Avoid double-recovering if the fixed version already exists
        if [ -f "$fixed_file" ]; then
            echo "Found raw file $mcap_file, but $fixed_file already exists. Skipping recovery."
        else
            echo "Found raw uncompressed split ($mcap_file without .zstd). Running 'mcap recover'..."
            mcap recover "$mcap_file" -o "$fixed_file"
        fi
    fi
done

# Clean up or isolate file lists: use the fixed versions if they exist, otherwise the original .mcap
# We will build an array of final files to merge
FILES_TO_MERGE=()
for file in $(ls *.mcap | sort -V); do
    # If this is a raw file that has a corresponding _fixed.mcap version, skip the raw one
    if [ -f "${file%.mcap}_fixed.mcap" ] && [[ "$file" != *_fixed.mcap ]]; then
        continue
    fi
    FILES_TO_MERGE+=("$file")
done

# Automatically extract the prefix from the first valid file for the output name
first_file="${FILES_TO_MERGE[0]}"
OUTPUT_BAG_FILE="$(pwd)/$(echo "$first_file" | sed -E 's/(_[0-9]+)?(_fixed)?\.mcap$//').mcap"

echo "Detected output file path: $OUTPUT_BAG_FILE"

# Remove previously generated output file if it exists to avoid overwrite blocks
if [ -f "$OUTPUT_BAG_FILE" ]; then
    rm -f "$OUTPUT_BAG_FILE"
fi

# 3. Merge using the native mcap CLI tool
echo "Merging split parts into a single file..."
mcap merge -o "$OUTPUT_BAG_FILE" "${FILES_TO_MERGE[@]}" --allow-duplicate-metadata

echo "Success! Merged bag created at: $OUTPUT_BAG_FILE"
