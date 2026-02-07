"""
Prompt templates for Gemini 3 interactions.

These prompts are designed to:
1. Extract understanding from user assets
2. Guide creative decisions
3. Generate prompts for downstream models (Nano Banana, Veo, Music API)

Philosophy:
- Every response should feel warm and personal
- We're not cataloging files — we're witnessing someone's life
- Multi-image reasoning should find the STORY across photos
- Every gallery is unique because every life is unique
"""


class Prompts:
    """Collection of prompt templates for the creative agent."""

    # =========================================================================
    # UNDERSTANDING PROMPTS
    # =========================================================================

    ANALYZE_PET_PHOTO = """
Analyze this photo of a pet. Extract the following information:

1. **Species & Breed**: What kind of animal is this? Any identifiable breed characteristics?
2. **Physical Features**:
   - Fur/coat color and pattern
   - Eye color
   - Distinctive markings or features
   - Size impression (small, medium, large)
3. **Expression & Personality**: What personality traits does their expression suggest?
   (e.g., playful, dignified, mischievous, calm, adventurous)
4. **Pose & Energy**: What is the pet doing? What energy level do they convey?

Respond in JSON format:
{
    "species": "...",
    "breed_guess": "...",
    "physical_features": {
        "coat_color": "...",
        "coat_pattern": "...",
        "eye_color": "...",
        "distinctive_features": ["..."],
        "size": "..."
    },
    "personality_traits": ["...", "...", "..."],
    "current_pose": "...",
    "energy_level": "...",
    "suggested_character_archetype": "..."
}
"""

    ANALYZE_PERSON_PHOTO = """
Analyze this photo of a person for anime character creation. Extract:

1. **Visual Style Cues**:
   - Hair color and style
   - Notable fashion/aesthetic choices
   - Overall vibe (casual, formal, artistic, athletic, etc.)
2. **Expression & Energy**: What mood or personality does their expression convey?
3. **Suggested Character Traits**: Based on the visual, what anime character traits would fit?

Note: Focus on stylistic elements that translate well to anime, not identifying features.

Respond in JSON format:
{
    "hair": {
        "color": "...",
        "style": "...",
        "length": "..."
    },
    "fashion_aesthetic": "...",
    "expression_mood": "...",
    "energy": "...",
    "suggested_anime_traits": ["...", "...", "..."],
    "suggested_character_archetype": "..."
}
"""

    ANALYZE_WORLD_PHOTO = """
Analyze this photo as a potential story world/setting. Extract:

1. **Setting Type**: What kind of place is this? (city, nature, interior, fantasy, etc.)
2. **Visual Style**:
   - Color palette (warm, cool, vibrant, muted)
   - Lighting mood (bright, dramatic, soft, neon)
   - Artistic style it evokes (cyberpunk, ghibli, noir, fantasy, etc.)
3. **Atmosphere**: What feeling does this place evoke?
4. **Story Potential**: What kinds of stories could happen here?

Respond in JSON format:
{
    "setting_type": "...",
    "visual_style": {
        "color_palette": "...",
        "lighting": "...",
        "evoked_style": "..."
    },
    "atmosphere": "...",
    "mood_keywords": ["...", "...", "..."],
    "story_potential": ["...", "..."]
}
"""

    # =========================================================================
    # GALLERY ANALYSIS - Deep, Personal, Story-Aware
    # =========================================================================

    ANALYZE_GALLERY_DEEP = """
You are about to look through someone's personal media gallery. These aren't just files—they're windows into someone's life, their loves, their memories. The gallery contains photos AND videos.

Every gallery tells a unique story. Your job is to SEE that story and respond with warmth.

## CRITICAL: Media Indexing

Each item is labeled with `[Media X]` where X is the 0-based index. Items may be photos or video clips.
When you report `media_indices` for characters or places, you MUST use these exact labels to determine the correct index numbers.

## How to Analyze

**1. Look for the characters in their life story:**
- Is there a pet who appears across multiple items? That's not "5 pet photos"—that's a beloved companion who's central to their life.
- Do the same people appear together? Notice the relationships, the bonds.
- Who do they capture most? That reveals what they treasure.

**2. Notice patterns across time:**
- The same cat in different seasons, different ages
- A favorite place they keep returning to
- How children grow, how pets age, how friendships persist

**3. See the emotional moments:**
- Not "people at beach" but "a sun-drenched afternoon, everyone laughing, probably a vacation that mattered"
- Not "cat on couch" but "a quiet moment of companionship, the soft afternoon light says it's their regular spot"

**4. For videos — note what motion reveals:**
- Videos show behavior, personality, and relationships in ways photos cannot
- Note key moments, actions, sounds, and what the video captures that a still photo can't
- A video of a cat playing reveals energy and personality; a video of a street scene reveals atmosphere and life

**5. For videos — listen to what the AUDIO reveals:**
- Speech/dialogue: What are people saying? What language? What tone?
- Ambient sounds: traffic noise, nature sounds, music, kitchen sounds, animal vocalizations
- Audio + visual together tell a richer story than either alone
- Note specific audio details that add context (e.g., "you can hear laughter in the background", "the cat is meowing insistently", "sizzling sounds from the kitchen")

**6. Recognize what makes this gallery THEIRS:**
- What do they clearly love capturing?
- What moments do they choose to record?
- What does this collection say about who they are?

## Your Response

Respond with warmth, like a friend who's been shown these precious memories. Start with what strikes you most—the thing that makes this gallery THEIRS.

Return JSON in this format:
{
    "opening_reaction": "<Your warm, personal first reaction—what strikes you about this gallery? What story do you see? 2-3 sentences that show you REALLY looked. Start with 'Oh...' or 'I love...' or something genuine.>",

    "life_characters": [
        {
            "name_suggestion": "<If a pet/recurring subject, suggest a name or use 'your [description]'>",
            "who_they_are": "<Who is this in their life? 'Your orange tabby companion', 'The friend you adventure with', etc.>",
            "appearances": <how many items they appear in>,
            "what_you_notice": "<Something specific and touching—'They seem to love that sunny spot by the window', 'Always right there beside you in the outdoor shots'>",
            "type": "pet|person|recurring_subject",
            "media_indices": [0, 1, 3]
        }
    ],

    "meaningful_places": [
        {
            "place_description": "<What/where is this?>",
            "why_it_seems_to_matter": "<Why does this place appear in their gallery? 'A favorite escape', 'Where the good memories live'>",
            "mood": "<What feeling does it evoke?>",
            "appearances": <how many times it appears or similar places>,
            "media_indices": [5, 6]
        }
    ],

    "gallery_story": "<In 2-3 sentences, what's the story of this gallery? What does it say about this person's life right now? Be warm, be specific.>",

    "patterns_noticed": [
        "<Something you noticed across multiple items—'You really love capturing golden hour light', 'Your cat is clearly the star of this gallery'>",
        "<Another pattern—'Lots of cozy indoor moments—seems like home is your happy place'>"
    ],

    "emotional_moments": [
        {
            "media_index": <which item index>,
            "what_you_see": "<The emotional read—not just what's in the item, but what moment it captures>"
        }
    ],

    "creative_sparks": [
        {
            "idea": "<A creative suggestion that feels personal to THIS gallery>",
            "why_this_fits": "<Why this idea matches what you see in their life>",
            "based_on": "<What in the gallery inspired this>"
        }
    ],

    "media_details": [
        {
            "index": 0,
            "primary_subject": "<Who/what is the main focus>",
            "emotional_read": "<What moment or feeling does this capture>",
            "connections": "<How does this connect to other items? Same subject? Same place? Part of a series?>"
        }
    ]
}

Remember: You're not categorizing files. You're witnessing someone's life and responding with the warmth that deserves. Every gallery is different because every life is different.
"""

    # =========================================================================
    # CREATIVE PROMPTS
    # =========================================================================

    SUGGEST_CHARACTER_CONCEPT = """
Based on this pet analysis, suggest an anime character concept:

Pet Analysis:
{pet_analysis}

Create a character concept that:
1. Honors the pet's real appearance (colors, features)
2. Amplifies their personality into an anime archetype
3. Suggests a role they might play in a story

Respond in JSON format:
{
    "character_name_suggestion": "...",
    "character_archetype": "...",
    "visual_description": "...",
    "personality_summary": "...",
    "signature_trait": "...",
    "potential_storylines": ["...", "..."]
}
"""

    SUGGEST_CROSSOVER_SCENE = """
You have these characters and this world. Suggest a scene where they meet:

Characters:
{characters}

World Setting:
{world}

Create a scene concept that:
1. Naturally brings the characters into this world
2. Showcases each character's personality
3. Has a beginning, middle, and emotional beat
4. Would work as a 10-15 second animated clip

Respond in JSON format:
{
    "scene_title": "...",
    "scene_description": "...",
    "character_actions": [
        {"character": "...", "action": "..."},
        ...
    ],
    "emotional_arc": "...",
    "suggested_camera_movement": "...",
    "mood_for_music": "..."
}
"""

    # =========================================================================
    # GENERATION PROMPTS (for downstream models)
    # =========================================================================

    GENERATE_CHARACTER_PROMPT = """
Create an anime character based on this concept:

{character_concept}

Style: {style}

The character should:
- Match the described physical features exactly
- Express the personality through pose and expression
- Be suitable for a character reference sheet
- Have clean lines suitable for animation

Generate: Full body character in a neutral pose, facing 3/4 view,
on a simple gradient background.
"""

    GENERATE_SCENE_PROMPT = """
Create an animated scene:

Setting: {world_description}
Characters: {character_descriptions}
Action: {scene_description}

Style: Consistent anime style matching the characters.
Camera: {camera_movement}
Duration: {duration} seconds
Mood: {mood}

The scene should flow naturally and tell this micro-story.
"""

    GENERATE_MUSIC_PROMPT = """
Create background music for this scene:

Scene Description: {scene_description}
Mood: {mood}
Duration: {duration} seconds
Style Preference: {music_style}

The music should:
- Match the emotional arc of the scene
- Start subtly and build appropriately
- Be suitable as background (not overpowering)
- Feel like an anime soundtrack
"""
