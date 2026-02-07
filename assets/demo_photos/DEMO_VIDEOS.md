# Demo Videos — Curated List

> Videos WITH AUDIO are essential for Gemini video understanding (dialogue, ambient sounds, music).
> Mixkit/Pexels free downloads strip audio, so we need to source manually.

## Requirements

- **Audio**: Must have clear audio (dialogue, ambient, or music)
- **Duration**: 10-30 seconds
- **Resolution**: 480p-720p MP4 is plenty
- **Filesize**: Under 3MB each after compression
- **License**: CC0/Public Domain or CC-BY (repo is public)

## Recommended Clips

### 1. Pet — Cat playing with owner (WITH meowing/purring)

| Source | Search term |
|--------|-------------|
| Pexels | "cat meowing" or "cat playing sounds" |
| YouTube CC | "cat meowing compilation" (Creative Commons filter) |
| Pixabay | "cat sound" |

**What to look for**: Cat interacting with owner, audible meows or purrs. 10-20s.

Suggested Pexels pages:
- https://www.pexels.com/search/videos/cat%20meowing/
- https://www.pexels.com/search/videos/cat%20playing/

### 2. Pet — Dog at park (WITH barking/panting)

| Source | Search term |
|--------|-------------|
| Pexels | "dog park barking" or "dog playing outdoor" |
| Pixabay | "dog bark park" |

**What to look for**: Dog running, fetching, or playing — audible barks or panting. 10-20s.

### 3. Family — Outdoor gathering (WITH chatter/laughter)

| Source | Search term |
|--------|-------------|
| Pexels | "family talking outdoor" or "family picnic" |
| Pixabay | "family gathering sound" |

**What to look for**: Family walking, eating, or chatting together — audible conversation/laughter. 15-25s.

### 4. Vlog — Person talking to camera

| Source | Search term |
|--------|-------------|
| Pexels | "vlog talking" or "person speaking camera" |
| Pixabay | "vlogger talking" |

**What to look for**: Someone speaking directly to camera (selfie/front-facing style). Clear speech. 15-20s.

### 5. Video call — Conference/meeting screen recording

| Source | Search term |
|--------|-------------|
| Pexels | "video call" or "zoom meeting" |
| Pixabay | "video conference" |

**What to look for**: Split-screen or laptop view of video call. Audible voices. 15-20s.

### 6. City — Street scene with ambient noise

| Source | Search term |
|--------|-------------|
| Pexels | "tokyo street night" or "city walk sounds" |
| Pixabay | "city ambience walk" |

**What to look for**: Street-level walking footage with ambient city noise (traffic, crowd chatter, music). 15-20s.

### 7. Scenery — Nature with ambient sound

| Source | Search term |
|--------|-------------|
| Pexels | "ocean waves" or "forest birds" or "waterfall" |
| Pixabay | "nature sounds" |

**What to look for**: Natural landscape with clear ambient audio (waves crashing, birds chirping, wind). 15-20s.

### 8. Cooking — Kitchen activity with narration

| Source | Search term |
|--------|-------------|
| Pexels | "cooking tutorial" or "kitchen cooking" |
| Pixabay | "cooking sounds kitchen" |

**What to look for**: Someone cooking with audible sounds (sizzling, chopping, narration). 15-25s.

## After Downloading

Place raw downloads in `assets/demo_photos/videos/` with these names:

```
cat_clip.mp4
dog_clip.mp4
family_clip.mp4
vlog_clip.mp4
videocall_clip.mp4
tokyo_clip.mp4
scenery_clip.mp4
cooking_clip.mp4
```

Then compress to 480p:

```bash
for f in *_raw.mp4; do
  out="${f%_raw.mp4}.mp4"
  ffmpeg -y -i "$f" \
    -vf "scale=-2:480" \
    -t 20 \
    -c:v libx264 -preset fast -crf 28 \
    -c:a aac -b:a 96k \
    -movflags +faststart \
    "$out"
done
```

**Important**: Use `-b:a 96k` (not 64k) to preserve audio quality for speech understanding.

## Verify Audio Exists

```bash
for f in *.mp4; do
  audio=$(ffprobe -v error -select_streams a -show_entries stream=codec_name -of csv=p=0 "$f" 2>/dev/null)
  echo "$f: audio=${audio:-NONE}"
done
```
