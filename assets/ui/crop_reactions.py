#!/usr/bin/env python3
"""
Crop FB reactions sprite into individual images.
Source: 1612x736 webp with 6 emojis + text labels

Precise measurements (pixel-detected):
- Each emoji is exactly 176px wide (circular)
- Emoji horizontal bounds: evenly spaced with 226px gaps
- Love emoji (reference): x=[373, 549], y=[242, 417] → 176x175px circle

We want: Love (index 1), Haha (index 2), Angry (index 5)
Output: Individual webp files + sprite, perfectly centered
"""

from PIL import Image
from pathlib import Path

def crop_reactions():
    script_dir = Path(__file__).parent
    input_path = script_dir / "fb-reactions-full.webp"

    if not input_path.exists():
        print(f"❌ Please save the FB reactions image to: {input_path}")
        return

    img = Image.open(input_path)
    width, height = img.size
    print(f"📐 Image size: {width}x{height}")

    # Precise measurements from pixel analysis
    # Each emoji: 176px wide circle
    # Horizontal bounds detected:
    #   Like:  x=[147, 323]  center_x = 235
    #   Love:  x=[373, 549]  center_x = 461
    #   Haha:  x=[599, 775]  center_x = 687
    #   Wow:   x=[825, 1001] center_x = 913
    #   Sad:   x=[1051, 1227] center_x = 1139
    #   Angry: x=[1277, 1453] center_x = 1365

    # Vertical: Love emoji y=[242, 417] gives center_y = 329 for 176px circle
    # Use same center_y for all since they're aligned

    emoji_size = 176
    center_y = 329  # Vertical center of emoji circles (from Love reference)
    half = emoji_size // 2  # 88px

    emojis = {
        'love':  461,   # center_x
        'haha':  687,
        'angry': 1365,
    }

    print(f"📐 Emoji size: {emoji_size}x{emoji_size}px circles")
    print(f"📐 Vertical center: y={center_y}")
    print(f"📐 Crop half-size: {half}px\n")

    for name, center_x in emojis.items():
        # Crop a perfect square centered on the emoji
        left = center_x - half
        right = center_x + half
        top = center_y - half
        bottom = center_y + half

        print(f"  {name}: center=({center_x}, {center_y}) → crop x=[{left}, {right}], y=[{top}, {bottom}]")

        cropped = img.crop((left, top, right, bottom))

        # Verify it's square
        w, h = cropped.size
        print(f"         cropped size: {w}x{h}")

        # Resize to 56x56 (2x retina for 28px display)
        final = cropped.resize((56, 56), Image.Resampling.LANCZOS)

        # Save as webp
        output_path = script_dir / f"reaction-{name}.webp"
        final.save(output_path, 'WEBP', quality=90)
        print(f"         ✅ Saved: {output_path.name}")

    # Create sprite: [love][haha][angry] each 56x56 = 168x56
    print(f"\n📐 Creating sprite...")
    sprite = Image.new('RGB', (56 * 3, 56), (255, 255, 255))

    for i, name in enumerate(['love', 'haha', 'angry']):
        reaction_img = Image.open(script_dir / f"reaction-{name}.webp")
        sprite.paste(reaction_img, (i * 56, 0))

    sprite_path = script_dir / "fb-reactions.webp"
    sprite.save(sprite_path, 'WEBP', quality=90)
    print(f"  ✅ Saved sprite: {sprite_path.name} (168x56)")

    print("\n🎉 Done! All emojis perfectly centered.")

if __name__ == "__main__":
    crop_reactions()
