#!/usr/bin/env bash
# exit on error
set -o errexit

# Install the real system FFmpeg
apt-get update && apt-get install -y ffmpeg

# Install your python packages
pip install -r requirements.txt