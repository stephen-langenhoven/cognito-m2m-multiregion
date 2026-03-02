#!/bin/bash
set -e

OUTPUT_ZIP="lambda_package.zip"
PACKAGE_DIR="packages"

echo "Cleaning old package..."
rm -f "$OUTPUT_ZIP"

echo "Creating new package..."

# Add index.py
zip -r "$OUTPUT_ZIP" index.py

# Add all package contents at root level
if [ -d "$PACKAGE_DIR" ]; then
    # -j flattens directory structure so contents of packages/ go to root
    # But we need to preserve subdirectories inside packages, so don't use -j.
    # Instead, cd into packages and zip its contents.
    (
        cd "$PACKAGE_DIR"
        zip -r "../$OUTPUT_ZIP" .
    )
else
    echo "Warning: packages directory not found. Only index.py will be zipped."
fi

echo "Build complete: $OUTPUT_ZIP"
