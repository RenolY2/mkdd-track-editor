#!/usr/bin/env bash

# Create and enter a temporary directory.
cd /tmp
rm -rf MKDDTE_BUNDLE_TMP
mkdir MKDDTE_BUNDLE_TMP
cd MKDDTE_BUNDLE_TMP

# Retrieve a fresh checkout from the repository to avoid a potentially
# polluted local checkout.
git clone https://github.com/RenolY2/mkdd-track-editor.git --depth=1
cd mkdd-track-editor

# Create a virtual environment.
python3 -m venv venv
source venv/bin/activate
export PYTHONNOUSERSITE=1

# Install dependencies.
python3 -m pip install -r requirements-build-linux.txt
python3 -m pip install -r requirements.txt

# Build the bundle.
python setup.py build

# Open directory in file explorer.
cd build
xdg-open .
