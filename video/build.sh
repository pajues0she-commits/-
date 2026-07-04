#!/usr/bin/env bash
# 수소 실린더 안전 영상 빌드: 프레임 캡처 → webm 인코딩
set -euo pipefail
cd "$(dirname "$0")"

FFMPEG="/opt/pw-browsers/ffmpeg-1011/ffmpeg-linux"
NODE_PATH="$(npm root -g)"
export NODE_PATH

echo "[1/2] 프레임 캡처 (Playwright/Chromium)…"
rm -f frames/f*.jpg frames/f*.png
node render.mjs

echo "[2/2] webm 인코딩 (VP8)…"
# 번들 ffmpeg: image2pipe(mjpeg parser) → webm(libvpx VP8). 오디오 없음.
cat $(ls -1 frames/f*.jpg | sort) | "$FFMPEG" -y \
  -f image2pipe -c:v mjpeg -framerate 30 -i pipe:0 \
  -c:v libvpx -b:v 6M -crf 8 -pix_fmt yuv420p -deadline good -cpu-used 1 -an \
  hydrogen_cylinder_safety.webm

echo "완료 → $(pwd)/hydrogen_cylinder_safety.webm"
ls -la hydrogen_cylinder_safety.webm
