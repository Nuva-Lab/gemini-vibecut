#!/bin/bash
# Download demo images from Unsplash
# Curated for COHESIVE photo gallery feel - same pets, same family, same locations

SCRIPT_DIR="$(dirname "$0")"
PETS_DIR="$SCRIPT_DIR/pets"
PEOPLE_DIR="$SCRIPT_DIR/people"
WORLDS_DIR="$SCRIPT_DIR/worlds"

mkdir -p "$PETS_DIR" "$PEOPLE_DIR" "$WORLDS_DIR"

# Clear old files (except icons)
rm -f "$PETS_DIR"/*.jpg "$PETS_DIR"/*.webp 2>/dev/null
rm -f "$PEOPLE_DIR"/*.jpg "$PEOPLE_DIR"/*.webp 2>/dev/null
rm -f "$WORLDS_DIR"/*.jpg "$WORLDS_DIR"/*.webp 2>/dev/null

echo "=== Downloading SAME orange tabby cat (all from Tianlei Wu) ==="
# All 5 photos are the SAME cat - "meet my boi" series
curl -sL "https://images.unsplash.com/photo-1667518158994-8b3b2957dd01?w=600&fit=crop" -o "$PETS_DIR/cat_01.jpg"
curl -sL "https://images.unsplash.com/photo-1667518158890-0a6cf60de601?w=600&fit=crop" -o "$PETS_DIR/cat_02.jpg"
curl -sL "https://images.unsplash.com/photo-1667518156912-c032a0d4cd88?w=600&fit=crop" -o "$PETS_DIR/cat_03.jpg"
curl -sL "https://images.unsplash.com/photo-1667518157438-05eccbadb225?w=600&fit=crop" -o "$PETS_DIR/cat_04.jpg"
curl -sL "https://images.unsplash.com/photo-1667518158829-f193fd5ac457?w=600&fit=crop" -o "$PETS_DIR/cat_05.jpg"

echo "=== Downloading SAME golden retriever puppy (paired photographers) ==="
# Photos from same photographers = likely same dogs
curl -sL "https://images.unsplash.com/photo-1615233500064-caa995e2f9dd?w=600&fit=crop" -o "$PETS_DIR/dog_01.jpg"
curl -sL "https://images.unsplash.com/photo-1615233500147-5b196365bf3e?w=600&fit=crop" -o "$PETS_DIR/dog_02.jpg"
curl -sL "https://images.unsplash.com/photo-1611003228941-98852ba62227?w=600&fit=crop" -o "$PETS_DIR/dog_03.jpg"
curl -sL "https://images.unsplash.com/photo-1611003229186-80e40cd54966?w=600&fit=crop" -o "$PETS_DIR/dog_04.jpg"
curl -sL "https://images.unsplash.com/photo-1591160690555-5debfba289f0?w=600&fit=crop" -o "$PETS_DIR/dog_05.jpg"

echo "=== Downloading warm FAMILY moments (same family at beach) ==="
# Candid family photos - dad & son, mom & baby, genuine moments
curl -sL "https://images.unsplash.com/photo-1597698176091-8840ee2d12d5?w=600&fit=crop" -o "$PEOPLE_DIR/family_01.jpg"
curl -sL "https://images.unsplash.com/photo-1596510914914-e14c6f59f925?w=600&fit=crop" -o "$PEOPLE_DIR/family_02.jpg"
curl -sL "https://images.unsplash.com/photo-1597098469273-834bc9d81f0a?w=600&fit=crop" -o "$PEOPLE_DIR/family_03.jpg"
curl -sL "https://images.unsplash.com/photo-1596510914841-40223e421e29?w=600&fit=crop" -o "$PEOPLE_DIR/family_04.jpg"
curl -sL "https://images.unsplash.com/photo-1596510915004-8c01467f82ed?w=600&fit=crop" -o "$PEOPLE_DIR/family_05.jpg"
curl -sL "https://images.unsplash.com/photo-1597698194747-41e7a1bd4b19?w=600&fit=crop" -o "$PEOPLE_DIR/family_06.jpg"
curl -sL "https://images.unsplash.com/photo-1597524624057-0a3cba4d77b1?w=600&fit=crop" -o "$PEOPLE_DIR/family_07.jpg"
curl -sL "https://images.unsplash.com/photo-1597698125420-e6201dd444ff?w=600&fit=crop" -o "$PEOPLE_DIR/family_08.jpg"
# Add a couple more warm family/friends shots
curl -sL "https://images.unsplash.com/photo-1511895426328-dc8714191300?w=600&fit=crop" -o "$PEOPLE_DIR/family_09.jpg"
curl -sL "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?w=600&fit=crop" -o "$PEOPLE_DIR/family_10.jpg"

echo "=== Downloading Japanese neon streets (ALL from Willian Justen) ==="
# All from same photographer for consistent color grading
curl -sL "https://images.unsplash.com/photo-1678737175063-19ac8a8cdf25?w=800&fit=crop" -o "$WORLDS_DIR/tokyo_01.jpg"
curl -sL "https://images.unsplash.com/photo-1678737169917-4e19ce734b6d?w=800&fit=crop" -o "$WORLDS_DIR/tokyo_02.jpg"
curl -sL "https://images.unsplash.com/photo-1678737168417-f621f11b1bd6?w=800&fit=crop" -o "$WORLDS_DIR/tokyo_03.jpg"
curl -sL "https://images.unsplash.com/photo-1678737171805-0b2b0503dc95?w=800&fit=crop" -o "$WORLDS_DIR/tokyo_04.jpg"
curl -sL "https://images.unsplash.com/photo-1678737178220-f343cec4c048?w=800&fit=crop" -o "$WORLDS_DIR/tokyo_05.jpg"
curl -sL "https://images.unsplash.com/photo-1678737174409-bfd79e7b7d6f?w=800&fit=crop" -o "$WORLDS_DIR/tokyo_06.jpg"
curl -sL "https://images.unsplash.com/photo-1678737169727-a3236885e763?w=800&fit=crop" -o "$WORLDS_DIR/tokyo_07.jpg"
curl -sL "https://images.unsplash.com/photo-1678737169235-534857a216a5?w=800&fit=crop" -o "$WORLDS_DIR/tokyo_08.jpg"
curl -sL "https://images.unsplash.com/photo-1678737171211-bf2c3def509f?w=800&fit=crop" -o "$WORLDS_DIR/tokyo_09.jpg"
curl -sL "https://images.unsplash.com/photo-1678737168806-1be1e678e189?w=800&fit=crop" -o "$WORLDS_DIR/tokyo_10.jpg"

echo ""
echo "=== Converting to WebP format ==="
for f in "$PETS_DIR"/*.jpg "$PEOPLE_DIR"/*.jpg "$WORLDS_DIR"/*.jpg; do
  if [ -f "$f" ]; then
    filesize=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null)
    if [ "$filesize" -gt 1000 ]; then
      echo "Converting: $(basename "$f")"
      cwebp -q 80 "$f" -o "${f%.jpg}.webp" 2>/dev/null && rm "$f"
    else
      echo "FAILED (too small): $(basename "$f")"
      rm "$f"
    fi
  fi
done

echo ""
echo "=== Done! Results: ==="
echo "Pets (same cat + same dog):"
ls "$PETS_DIR"/*.webp 2>/dev/null | wc -l | xargs echo "  Count:"
echo "Family (warm moments):"
ls "$PEOPLE_DIR"/*.webp 2>/dev/null | wc -l | xargs echo "  Count:"
echo "Worlds (Tokyo neon, same photographer):"
ls "$WORLDS_DIR"/*.webp 2>/dev/null | wc -l | xargs echo "  Count:"
echo ""
du -sh "$SCRIPT_DIR"
