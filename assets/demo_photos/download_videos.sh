#!/bin/bash
# Download demo videos from Mixkit (free stock, no attribution required)
# Diverse clips that look like real phone recordings / screen captures
# Output: 480p MP4, ~15-20s, small filesize

SCRIPT_DIR="$(dirname "$0")"
VIDEOS_DIR="$SCRIPT_DIR/videos"

mkdir -p "$VIDEOS_DIR"
rm -f "$VIDEOS_DIR"/*.mp4 "$VIDEOS_DIR"/*_raw.mp4 2>/dev/null

echo "=== Downloading demo videos from Mixkit ==="

# --- Pets ---
echo "[1/8] cat_clip (person playing with cat)..."
curl -sL "https://assets.mixkit.co/videos/1779/1779-720.mp4" -o "$VIDEOS_DIR/cat_clip_raw.mp4"

echo "[2/8] dog_clip (corgi chasing tennis ball in park)..."
curl -sL "https://assets.mixkit.co/videos/45868/45868-720.mp4" -o "$VIDEOS_DIR/dog_clip_raw.mp4"

# --- People / Family ---
echo "[3/8] family_clip (family walking in park)..."
curl -sL "https://assets.mixkit.co/videos/33729/33729-720.mp4" -o "$VIDEOS_DIR/family_clip_raw.mp4"

# --- Talking heads / Vlog ---
echo "[4/8] vlog_clip (man recording himself walking on street)..."
curl -sL "https://assets.mixkit.co/videos/34469/34469-720.mp4" -o "$VIDEOS_DIR/vlog_clip_raw.mp4"

echo "[5/8] videocall_clip (conference video call at home)..."
curl -sL "https://assets.mixkit.co/videos/14037/14037-720.mp4" -o "$VIDEOS_DIR/videocall_clip_raw.mp4"

# --- Scenery / Travel ---
echo "[6/8] tokyo_clip (pedestrian walk in Tokyo)..."
curl -sL "https://assets.mixkit.co/videos/4231/4231-720.mp4" -o "$VIDEOS_DIR/tokyo_clip_raw.mp4"

echo "[7/8] scenery_clip (natural seashore with green cliffs)..."
curl -sL "https://assets.mixkit.co/videos/1082/1082-720.mp4" -o "$VIDEOS_DIR/scenery_clip_raw.mp4"

# --- Everyday / Lifestyle ---
echo "[8/8] cooking_clip (woman cooking breakfast in kitchen)..."
curl -sL "https://assets.mixkit.co/videos/42909/42909-720.mp4" -o "$VIDEOS_DIR/cooking_clip_raw.mp4"

echo ""
echo "=== Compressing to 480p MP4 (max 20s) ==="
for f in "$VIDEOS_DIR"/*_raw.mp4; do
  if [ -f "$f" ]; then
    out="${f%_raw.mp4}.mp4"
    basename_raw=$(basename "$f")
    basename_out=$(basename "$out")

    filesize=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null)
    if [ "$filesize" -lt 10000 ]; then
      echo "SKIP (download failed): $basename_raw"
      rm "$f"
      continue
    fi

    echo "Compressing: $basename_raw -> $basename_out"
    ffmpeg -y -i "$f" \
      -vf "scale=-2:480" \
      -t 20 \
      -c:v libx264 -preset fast -crf 28 \
      -c:a aac -b:a 64k \
      -movflags +faststart \
      "$out" 2>/dev/null

    if [ -f "$out" ]; then
      rm "$f"
    else
      echo "  FAILED to compress: $basename_raw"
    fi
  fi
done

echo ""
echo "=== Results ==="
total=0
for f in "$VIDEOS_DIR"/*.mp4; do
  if [ -f "$f" ]; then
    size=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null)
    sizeMB=$(echo "scale=1; $size/1048576" | bc)
    dur=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$f" 2>/dev/null)
    res=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$f" 2>/dev/null)
    echo "  $(basename "$f"): ${sizeMB}MB, ${dur%.*}s, ${res}"
    total=$((total + 1))
  fi
done
echo ""
echo "Total clips: $total"
du -sh "$VIDEOS_DIR"
