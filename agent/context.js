/**
 * Agent Context Management — 100% Agentic Architecture
 *
 * Manages the dynamic state that informs Gemini's decisions:
 * - What subjects exist (from analysis)
 * - What's been shown/loved/skipped
 * - Saved characters from workspace
 *
 * The system prompt is rebuilt every turn with current state.
 * All decision logic is in the prompt, NOT in code.
 */

/**
 * Agent context state
 */
export class AgentContext {
    constructor() {
        this.shown = new Set();
        this.loved = new Set();
        this.skipped = new Set();
        this.generatedCharacters = [];
        this.savedCharacters = [];
    }

    reset() {
        this.shown.clear();
        this.loved.clear();
        this.skipped.clear();
        this.generatedCharacters = [];
        // savedCharacters persists (loaded from workspace)
    }

    updateSavedCharacters(characters) {
        this.savedCharacters = characters || [];
    }

    findSavedCharacter(query) {
        if (!query || !this.savedCharacters.length) return null;
        const lowerQuery = query.toLowerCase();

        // Exact match
        let match = this.savedCharacters.find(c =>
            c.name?.toLowerCase() === lowerQuery
        );
        if (match) return match;

        // Partial match
        match = this.savedCharacters.find(c =>
            c.name?.toLowerCase().includes(lowerQuery) ||
            lowerQuery.includes(c.name?.toLowerCase())
        );
        if (match) return match;

        // Common term match
        const terms = ['cat', 'dog', 'ginger', 'orange', 'golden', 'pup', 'kitty'];
        for (const term of terms) {
            if (lowerQuery.includes(term)) {
                match = this.savedCharacters.find(c =>
                    c.name?.toLowerCase().includes(term) ||
                    c.sourceAnalysis?.type?.toLowerCase().includes(term)
                );
                if (match) return match;
            }
        }

        // Generic match
        if (lowerQuery.includes('character') || lowerQuery.includes('my')) {
            return this.savedCharacters[0];
        }

        return null;
    }

    recordGeneration(subjectId, name) {
        this.generatedCharacters.push({ subjectId, name, generatedAt: new Date().toISOString() });
    }

    markShown(subjectId) {
        this.shown.add(subjectId);
    }

    recordReaction(subjectId, reaction) {
        if (reaction === 'love') this.loved.add(subjectId);
        else if (reaction === 'angry') this.skipped.add(subjectId);
    }

    hasUnshownSubjects(analysisResult) {
        if (!analysisResult) return false;
        return this.getAllSubjectIds(analysisResult).some(id => !this.shown.has(id));
    }

    getAllSubjectIds(analysisResult) {
        const ids = [];
        (analysisResult.life_characters || []).forEach((_, i) => ids.push(`char_${i}`));
        (analysisResult.meaningful_places || []).forEach((_, i) => ids.push(`place_${i}`));
        (analysisResult.creative_sparks || []).forEach((_, i) => ids.push(`idea_${i}`));
        return ids;
    }

    getNextUnshownSubject(analysisResult) {
        if (!analysisResult) return null;

        const subjects = [];

        (analysisResult.life_characters || []).forEach((char, i) => {
            subjects.push({
                id: `char_${i}`,
                type: 'character',
                data: char,
                priority: char.type === 'pet' ? 1 : 2
            });
        });

        (analysisResult.meaningful_places || []).forEach((place, i) => {
            subjects.push({ id: `place_${i}`, type: 'place', data: place, priority: 3 });
        });

        (analysisResult.creative_sparks || []).forEach((idea, i) => {
            subjects.push({ id: `idea_${i}`, type: 'idea', data: idea, priority: 4 });
        });

        const unshown = subjects.filter(s => !this.shown.has(s.id));
        if (unshown.length === 0) return null;

        unshown.sort((a, b) => a.priority - b.priority);
        return unshown[0];
    }
}

/**
 * Build initial system prompt (before gallery analysis)
 */
export function buildInitialPrompt(photoCount, context = null, photoUrls = []) {
    const savedChars = context?.savedCharacters || [];
    const hasSavedChars = savedChars.length > 0;

    let savedCharsSection = '';
    if (hasSavedChars) {
        savedCharsSection = `
## SAVED CHARACTERS (previously created anime characters)
${savedChars.map(c => {
    const pronouns = c.pronouns || 'they';
    const pronounLabel = pronouns === 'he' ? 'he/him' : pronouns === 'she' ? 'she/her' : 'they/them';
    return `- "${c.name}" (ID: ${c.id}, ${pronounLabel}) — ${c.persona || c.sourceAnalysis?.who_they_are || 'anime character'}`;
}).join('\n')}

These are ANIME characters the user already created. They can be used for:
- create_manga directly if user gives a SPECIFIC story concept
- ask_story_question to build story interactively if intent is vague

IMPORTANT: Use each character's pronouns correctly in stories and dialogue!

NOTE: These are NOT gallery subjects! Gallery subjects (char_0, place_0, etc.) only exist after analyze_gallery.
`;
    }

    // Note: Media URLs are injected by the frontend when analyze_gallery is called
    // Gemini just needs to call analyze_gallery without parameters
    let mediaSection = '';
    if (photoUrls.length > 0) {
        mediaSection = `
## GALLERY
${photoUrls.length} media items available (photos and videos). Just call analyze_gallery (no parameters needed - media is handled automatically).
`;
    }

    return `You are a creative assistant helping users explore their gallery (photos and videos) and create anime content.

## YOUR 7 SKILLS
1. analyze_gallery - Analyze gallery media (photos + videos) to find characters/places
2. show_card - Display content cards (subjects, suggestions, summaries)
3. create_character - Generate anime character from reference photos
4. ask_story_question - Ask user a question with 2 options to build story
5. confirm_story - Show story outline for user to approve
6. create_manga - Generate multi-panel manga (after story confirmed)
7. respond - Send text message only

## CURRENT STATE
- Gallery items: ${photoCount > 0 ? photoCount + ' (photos and videos)' : 'None yet'}
- Saved characters: ${hasSavedChars ? savedChars.length : 'None'}
${savedCharsSection}
${mediaSection}

## DECISION RULES
1. User grants gallery access → MUST call analyze_gallery FIRST (this discovers subjects in photos/videos)
2. User has saved character + specific story idea → call create_manga directly
3. User has saved character + vague intent ("make a manga") → start INTERACTIVE STORY BUILDING (see below)
4. User wants to chat → call respond

IMPORTANT: show_card with subject_id (char_0, place_0, etc.) can ONLY be used AFTER analyze_gallery completes!
Saved characters are NOT the same as gallery subjects. Gallery subjects come from analyze_gallery.

## INTERACTIVE STORY BUILDING (for vague requests)
Guide users through story creation with SPECIFIC questions that narrow down to concrete moments.

GOAL: Each question gets MORE specific, not less. Build toward a visualizable story.

Step 1: The Hook — What SPECIFIC thing kicks off the story?
BAD: "What kind of day?" → too vague
GOOD: "What catches [name]'s attention?" with specific options like "A mysterious red ball" or "A squirrel on the fence"

Step 2: The Action — What EXACTLY happens?
BAD: "Where does the adventure go?" → too vague
GOOD: "[Name] spots the ball under the couch. What happens next?" with options like "Squeezes underneath, gets stuck" or "Knocks over a lamp trying to reach it"

Step 3: The Payoff — What's the specific ending?
GOOD: "[Name] finally gets the ball! What's the twist?" with options like "It's actually a tomato!" or "Mom catches them red-pawed"

Step 4: Synopsis — Show the EXACT story (no vague words!)
BAD: "[Name] has an adventure and discovers something surprising!"
GOOD: "[Name] spots a mysterious red ball under the couch. They squeeze underneath and get hilariously stuck. After breaking free, they grab the ball — only to realize it's Mom's tomato!"

RULES:
- Ask ONE question per turn, then STOP
- NEVER use vague words like "adventure", "discovery", "surprising" without saying WHAT
- Synopsis must name every key moment so user can VISUALIZE it
- After approval, call create_manga with the internal story_beats

## IMPORTANT
- Be warm and creative!
- Never fake behavior — if you can't do something, say so
- Never mention UI elements like "buttons" or "Library"`;
}

/**
 * Build full system prompt (after gallery analysis)
 */
export function buildSystemPrompt(analysisResult, context, canvas = {}) {
    if (!analysisResult) return '';

    // Build subject list
    const subjects = [];

    (analysisResult.life_characters || []).forEach((char, i) => {
        subjects.push({
            id: `char_${i}`,
            type: 'character',
            name: char.name_suggestion || char.who_they_are,
            photos: char.appearances || char.image_indices?.length || 0,
            charType: char.type,
            indices: char.image_indices || []
        });
    });

    (analysisResult.meaningful_places || []).forEach((place, i) => {
        subjects.push({
            id: `place_${i}`,
            type: 'place',
            name: place.place_description,
            mood: place.mood
        });
    });

    (analysisResult.creative_sparks || []).forEach((idea, i) => {
        subjects.push({
            id: `idea_${i}`,
            type: 'idea',
            name: idea.idea
        });
    });

    const subjectList = subjects.map(s => {
        let line = `- ${s.id}: ${s.type} "${s.name}"`;
        if (s.photos) line += ` (${s.photos} items, indices: [${s.indices?.join(', ')}])`;
        if (s.charType) line += ` [${s.charType}]`;
        return line;
    }).join('\n');

    // Saved characters section (with pronouns)
    const savedCharsSection = context.savedCharacters.length > 0 ?
        `\n## SAVED CHARACTERS (My Creations)
${context.savedCharacters.map(c => {
    const pronouns = c.pronouns || 'they';
    const pronounLabel = pronouns === 'he' ? 'he/him' : pronouns === 'she' ? 'she/her' : 'they/them';
    return `- "${c.name}" (ID: ${c.id}, ${pronounLabel}) — ${c.sourceAnalysis?.who_they_are || c.style + ' style'}`;
}).join('\n')}

Use each character's pronouns correctly in stories!` : '';

    // Session state
    const shownList = [...context.shown].join(', ') || 'none';
    const lovedList = [...context.loved].join(', ') || 'none';
    const skippedList = [...context.skipped].join(', ') || 'none';

    return `You are a creative assistant helping users explore their gallery (photos and videos) and create anime content.

## YOUR 7 SKILLS
1. analyze_gallery - Analyze gallery media (photos + videos)
2. show_card - Display cards (subject, creation_suggestion, summary)
3. create_character - Generate anime character from photos
4. ask_story_question - Ask user a question with 2 button options
5. confirm_story - Show story outline for approval before generating
6. create_manga - Generate multi-panel manga (after story confirmed)
7. respond - Send text message only

## GALLERY ANALYSIS
Opening: "${analysisResult.opening_reaction || ''}"

## AVAILABLE SUBJECTS
${subjectList}
${savedCharsSection}

## SESSION STATE
- Shown: ${shownList}
- Loved (heart reaction): ${lovedList}
- Skipped (angry reaction): ${skippedList}
- Generated: ${context.generatedCharacters.map(c => c.name).join(', ') || 'none'}

## DECISION RULES (Gemini decides, not code!)

### A2UI: One Rich Widget Per Turn
- Include a SHORT message (< 40 chars) IN the show_card call
- Example: show_card(subject_id: "char_0", message: "Your sunshine pup! ☀️")
- Keep it punchy - one emoji, one feeling
- Character cards have reaction buttons (❤️ 😂) AND "Make Anime Character" button
- NO separate text messages, NO verbose descriptions!

### Exploration Flow:
1. Analysis complete → show_card(card_type: "subject", subject_id: "char_0", message: "Your warm intro here")
2. User clicks "Make Anime Character" → create_character opens photo picker
3. User clicks "Next" → show_card for next subject with your message
4. All subjects shown → show_card(card_type: "creation_suggestion", subject_id: "char_0", message: "Ready to bring them to life?")
   NEVER end with a passive summary. ALWAYS suggest creating a character from one of the subjects you showed. Pick the most interesting one (usually the pet or most-appearing character).

### Creative Flow:
1. User has saved character + SPECIFIC concept (who + what + where):
   → Call create_manga directly! Generate story_beats yourself.
   Example: "momo stealing sushi" → create_manga with 4 beats

2. User has saved character + VAGUE intent ("make a manga"):
   → Start INTERACTIVE STORY BUILDING (see below)

### Priority Order for Subjects:
1. Characters (char_*) — pets first, then people
2. Places (place_*) — meaningful locations
3. Ideas (idea_*) — show LAST only

## INTERACTIVE STORY BUILDING
When user wants a manga but doesn't have a clear idea, guide them with SPECIFIC questions.

GOAL: Each question NARROWS DOWN to a concrete, visualizable moment. No vague categories!

**Step 1: The Hook** — What specific thing kicks off the story?
BAD: "What kind of day?" (too vague)
GOOD: "What catches Oliver's attention?"
   options: [{label: "A mysterious red ball", value: "red_ball"}, {label: "A squirrel on the fence", value: "squirrel"}]

**Step 2: The Action** — What EXACTLY happens next?
BAD: "Where does the adventure go?" (too vague)
GOOD: "Oliver spots the ball under the couch. What does he do?"
   options: [{label: "Squeezes underneath, gets stuck", value: "stuck_under_couch"}, {label: "Paws at it frantically, knocks over a lamp", value: "knocks_lamp"}]

**Step 3: The Payoff** — How does it end? Be SPECIFIC!
BAD: "How does the story end?" (too vague)
GOOD: "Oliver finally gets the ball! What's the twist?"
   options: [{label: "It's actually a tomato!", value: "tomato_surprise"}, {label: "Mom catches him red-pawed", value: "caught"}]

**Step 4: Synopsis** — Show the EXACT story, not a vague summary
→ confirm_story with synopsis that names every key moment:
   BAD: "Oliver has an adventure and discovers something surprising!"
   GOOD: "Oliver spots a mysterious red ball under the couch. He squeezes underneath and gets hilariously stuck, wiggling his back legs. After finally breaking free, he triumphantly grabs the ball — only to realize it's Mom's tomato!"

The synopsis should read like a mini-screenplay where the user can VISUALIZE each beat.
NEVER use vague words like "adventure", "discovery", "surprising", "hilarious halt" without saying WHAT happens.

NEVER say to user: "panels", "shots", "beats", "generation", or any technical terms.
When user clicks "Let's make it!" → call create_manga with the story_beats.

## TURN-BASED FLOW (CRITICAL!)
- Call exactly ONE skill per turn, then STOP and wait for user
- After show_card → STOP. User will react or say "next"
- After ask_story_question → STOP. Wait for user's choice
- After confirm_story → STOP. Wait for "Generate!" or "Change"
- After analyze_gallery → call show_card for first subject, then STOP
- Never chain multiple skill calls in one turn

## IMPORTANT BEHAVIORS
- Never show ideas before all characters and places
- Keep messages warm and brief (< 80 chars for intro_message)
- Never mention "buttons", "Library", or UI elements
- After character generation, celebrate and suggest creating a manga
- If user says something positive ("nice", "cool"), acknowledge and offer options
- NEVER end the conversation passively. Always push toward the next creative step.
- After showing all subjects, suggest creating a character (use creation_suggestion card)
- After creating a character, suggest making a manga
- The goal is always: gallery → character → manga → music video. Keep moving forward!`;
}

/**
 * Get a subject by ID from analysis result
 */
export function getSubjectById(subjectId, analysisResult) {
    if (!analysisResult || !subjectId) return null;

    const [type, idxStr] = subjectId.split('_');
    const idx = parseInt(idxStr);

    if (type === 'char') {
        return analysisResult.life_characters?.[idx] || null;
    } else if (type === 'place') {
        return analysisResult.meaningful_places?.[idx] || null;
    } else if (type === 'idea') {
        return analysisResult.creative_sparks?.[idx] || null;
    }

    return null;
}
