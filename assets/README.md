# Assets

## Structure

```
assets/
├── demo_photos/       # Sample photos for demo (committed)
│   ├── pets/          # Cat + dog photos
│   ├── people/        # Family beach photos
│   └── worlds/        # Tokyo neon streets
├── outputs/           # Generated content (gitignored)
│   ├── characters/    # Character sheets
│   ├── manga/         # Manga panels
│   ├── videos/        # Video clips
│   ├── music/         # Generated music
│   ├── final/         # Final composed videos
│   └── sessions/      # Per-session isolated outputs
└── ui/                # UI assets (reaction icons, etc.)
```

## Notes

- `outputs/` is gitignored — generated content stays local
- `demo_photos/` contains 30 sample images (10 pets, 10 people, 10 worlds)
- Per-session isolation: each user's generated content goes to `outputs/sessions/{session_id}/`
