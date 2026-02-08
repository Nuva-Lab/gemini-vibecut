/**
 * Skill Function Declarations for Gemini API
 *
 * 6 atomic skills - Gemini decides WHEN to invoke them.
 * Each skill does exactly ONE thing.
 *
 * Skills:
 * 1. analyze_gallery - Analyze photos
 * 2. show_card - Display any card type to user
 * 3. create_character - Generate anime character
 * 4. create_manga - Generate manga panels
 * 5. generate_story_options - Get story options from Gemini
 * 6. respond - Send text message only
 */

export const skillFunctions = [
    {
        name: 'analyze_gallery',
        description: 'Analyze the user\'s gallery (images and videos) to understand their life characters, meaningful places, and creative potential. Call this when user grants gallery access. No parameters needed - media items are injected automatically.',
        parameters: {
            type: 'object',
            properties: {},
            required: []
        }
    },
    {
        name: 'show_card',
        description: `Display a card to the user. Handles all card types:
- "subject": Show a character/place/idea from gallery analysis (requires subject_id)
- "creation_suggestion": Suggest creating anime from a character (requires subject_id)
- "story_options": Show story options for a character (requires options array)
- "summary": Show exploration summary or wrap-up message

PRIORITY ORDER for subjects: Show characters (char_*) first, then places (place_*), then ideas (idea_*) LAST.`,
        parameters: {
            type: 'object',
            properties: {
                card_type: {
                    type: 'string',
                    enum: ['subject', 'creation_suggestion', 'story_options', 'summary'],
                    description: 'Type of card to display'
                },
                subject_id: {
                    type: 'string',
                    description: 'ID of subject for subject/creation_suggestion cards (e.g., "char_0", "place_1")'
                },
                message: {
                    type: 'string',
                    description: 'Optional message to show with the card (1 sentence, warm and personal)'
                },
                content: {
                    type: 'object',
                    description: 'Additional content for the card (varies by card_type)'
                }
            },
            required: ['card_type']
        }
    },
    {
        name: 'create_character',
        description: 'Generate an anime character from reference photos. Use when user accepts character creation suggestion or explicitly requests it.',
        parameters: {
            type: 'object',
            properties: {
                subject_id: {
                    type: 'string',
                    description: 'ID of the character from gallery analysis (e.g., "char_0")'
                },
                photo_indices: {
                    type: 'array',
                    items: { type: 'integer' },
                    description: 'Indices of photos to use as reference (best 3 photos of this character)'
                },
                name: {
                    type: 'string',
                    description: 'Name for the character (suggest based on gallery analysis)'
                }
            },
            required: ['subject_id', 'photo_indices']
        }
    },
    {
        name: 'create_manga',
        description: `Generate a multi-panel manga with a saved character.

IMPORTANT: When user provides a complete story concept (has subject + action + context), call this skill DIRECTLY.
YOU generate story_beats AND dialogues from their concept.

Example: User says "gogo running around in the room" → YOU create:
story_beats: [
  "Wide shot: Gogo bursts through the door, full of energy",
  "Low angle: Gogo leaps over the couch, ears flying",
  "Close-up: Gogo slides across the wooden floor, claws scrambling",
  "Medium shot: Gogo crashes into a pile of pillows, triumphant"
]
dialogues: [
  "ZOOMIES TIME!",
  "Can't catch me!",
  "Whoa whoa WHOA—",
  "...nailed it."
]

DIALOGUE RULES:
- 0-2 short lines per panel (1-8 words)
- Characters CAN and SHOULD talk (even pets!)
- Shows personality, reaction, emotion
- NOT narration - only what character says/thinks

Only use generate_story_options when user intent is VAGUE like "make something with my cat".`,
        parameters: {
            type: 'object',
            properties: {
                character_ids: {
                    type: 'array',
                    items: { type: 'string' },
                    description: 'IDs of saved characters to include. For multi-character stories, include ALL character IDs. Order matters - first character is primary.'
                },
                story_beats: {
                    type: 'array',
                    items: { type: 'string' },
                    description: 'Cinematic shot descriptions. Include camera angle (close-up/medium/wide/low angle) + action. Each shot should have DIFFERENT camera angle. Reference characters BY NAME in each beat.'
                },
                dialogues: {
                    type: 'array',
                    items: { type: 'string' },
                    description: 'What the character(s) say/think in each panel. Short, punchy (1-8 words). Can be empty string for silent panels.'
                },
                style: {
                    type: 'string',
                    enum: ['manga', 'webtoon', 'chibi', 'ghibli'],
                    description: 'Visual style for the manga (default: manga)'
                }
            },
            required: ['character_ids', 'story_beats', 'dialogues']
        }
    },
    {
        name: 'ask_story_question',
        description: `Ask user a PERSONALIZED question to build their manga story.

CRITICAL: Questions must feel DYNAMIC, not scripted!
- Reference what you KNOW about this character (from their photos, persona, traits)
- Build on their PREVIOUS choices in this conversation
- Show you understand their context with callbacks like "Since [name] loves..."

Example flow for a golden retriever named Oliver:
1. "Oliver seems like such a happy pup! What kind of day should we give him?"
   → [Sunny Adventure] [Cozy Nap Day]
2. User picks "Sunny Adventure"
3. "Perfect for Oliver! Where should his adventure take him?"
   → [Beach Day] [Park Exploration]

RULES:
- Start with a warm observation about the character
- Options should match the character's personality
- Keep it fun and conversational, never robotic
- After 2 questions, move to confirm_story`,
        parameters: {
            type: 'object',
            properties: {
                character_id: {
                    type: 'string',
                    description: 'Comma-separated IDs of saved characters (e.g. "id1" or "id1, id2" for multi-character stories)'
                },
                question: {
                    type: 'string',
                    description: 'Personalized question that references what you know about the character(s)'
                },
                options: {
                    type: 'array',
                    items: {
                        type: 'object',
                        properties: {
                            label: { type: 'string', description: 'Button text (2-4 words)' },
                            value: { type: 'string', description: 'Value sent back when clicked' }
                        }
                    },
                    description: '2 options tailored to this character'
                }
            },
            required: ['character_id', 'question', 'options']
        }
    },
    {
        name: 'confirm_story',
        description: `Show a story SYNOPSIS for user to approve or refine.

Present the story as a short narrative summary (like a movie logline).
User should understand what happens WITHOUT seeing technical details.

DO NOT mention: panels, shots, beats, generation, or any technical terms.
DO show: What happens in the story, the character's journey, the fun moment.

Example synopsis:
"Oliver discovers a mysterious ball at the beach and chases it into an
unexpected adventure - splashing through waves and making a new friend!"

User can:
- Click "Let's make it!" to generate
- Click "Change it up" to try different direction
- Type refinements in the text box`,
        parameters: {
            type: 'object',
            properties: {
                character_id: {
                    type: 'string',
                    description: 'Comma-separated IDs of saved characters (e.g. "id1" or "id1, id2" for multi-character stories)'
                },
                synopsis: {
                    type: 'string',
                    description: 'Story synopsis as a fun narrative (2-3 sentences, NO technical terms)'
                },
                story_beats: {
                    type: 'array',
                    items: { type: 'string' },
                    description: 'Internal: 4 cinematic descriptions (NOT shown to user)'
                },
                dialogues: {
                    type: 'array',
                    items: { type: 'string' },
                    description: 'Internal: Character lines for each moment (NOT shown to user)'
                }
            },
            required: ['character_id', 'synopsis', 'story_beats', 'dialogues']
        }
    },
    {
        name: 'respond',
        description: 'Send a text message to the user without any UI action. Use for conversational responses, clarifications, or when no skill action is needed.',
        parameters: {
            type: 'object',
            properties: {
                message: {
                    type: 'string',
                    description: 'The message to send to the user'
                }
            },
            required: ['message']
        }
    }
];

/**
 * Get a skill declaration by name
 */
export function getSkillByName(name) {
    return skillFunctions.find(s => s.name === name) || null;
}

/**
 * Validate skill arguments against declaration
 */
export function validateSkillArgs(name, args) {
    const skill = getSkillByName(name);
    if (!skill) return { valid: false, missing: ['unknown skill'] };

    const required = skill.parameters.required || [];
    const missing = required.filter(param => !(param in args));

    return {
        valid: missing.length === 0,
        missing: missing.length > 0 ? missing : undefined
    };
}
