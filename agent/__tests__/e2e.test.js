/**
 * End-to-End Session Tests
 *
 * Complete user journeys from photo access to final creation.
 * Each session represents a different "what if the user did X?" scenario.
 *
 * All sessions start the same way (grant photo access) but branch based on
 * different user choices: loving vs skipping characters, making comics vs scenes, etc.
 *
 * REQUIRES: Real Gemini API (run with: npm run test:integration)
 */

import { describe, it, expect, vi, afterAll } from 'vitest';
import { AgentBrain } from '../brain.js';
import { AgentContext } from '../context.js';
import { createMockAnalysisResponse, createMockSavedCharacter } from './fixtures/mockResponses.js';
import { PHOTO_SETS } from './fixtures/photoSets.js';
import { TrajectoryCollector } from './helpers/trajectoryCollector.js';
import { HTMLReporter } from './helpers/htmlReporter.js';
import {
  createMockApiKeyGetter,
  createMockSessionStateGetter,
  createMockSkillExecutor
} from './setup.js';

// Skip all tests if real API not available
const USE_REAL_API = globalThis.isRealApiEnabled?.() || false;
const describeE2E = USE_REAL_API ? describe : describe.skip;

// Single reporter for all sessions
const reporter = new HTMLReporter();
reporter.setTitle('E2E Session Transcripts');

/**
 * Helper: Create a configured AgentBrain for testing
 */
function createTestBrain(context, sessionState, skillCalls) {
  const executor = vi.fn(async (name, args) => {
    skillCalls.push({ name, args, timestamp: Date.now() });

    switch (name) {
      case 'analyze_gallery':
        return { success: true, analysisResult: sessionState.analysisResult };
      case 'generate_comic':
        return { success: true, panels: ['panel1.png', 'panel2.png', 'panel3.png', 'panel4.png'] };
      case 'generate_scene':
        return { success: true, imageUrl: 'generated_scene.png' };
      default:
        return { success: true };
    }
  });

  return new AgentBrain({
    getApiKey: createMockApiKeyGetter('real'),
    context,
    getSessionState: () => sessionState,
    onSkillExecute: executor,
    onTextResponse: vi.fn(),
    onTechFlow: vi.fn()
  });
}

/**
 * Helper: Record agent response to trajectory
 */
function recordResponse(trajectory, skillCalls, lastSkillCount) {
  const newCalls = skillCalls.slice(lastSkillCount);
  for (const call of newCalls) {
    trajectory.agentResponse({
      type: 'function',
      name: call.name,
      args: call.args
    });
    trajectory.skillResult(call.name, { success: true });
  }
  return skillCalls.length;
}

describeE2E('E2E Sessions', () => {

  /**
   * SESSION A: Happy Explorer
   * User loves the first character immediately, creates a comic
   */
  it('Session A: Happy Explorer → Love first → Comic', async () => {
    const trajectory = new TrajectoryCollector('Session A: Happy Explorer');
    const context = new AgentContext();
    const skillCalls = [];

    const mockAnalysis = createMockAnalysisResponse({
      characterCount: 3,
      characterType: 'pet',
      photosPerCharacter: 5
    });
    mockAnalysis.life_characters[0].name_suggestion = 'Mochi';
    mockAnalysis.life_characters[1].name_suggestion = 'Whiskers';
    mockAnalysis.life_characters[2].name_suggestion = 'Shadow';

    const sessionState = {
      analysisResult: null,
      photoUrls: PHOTO_SETS.petsOnly.photos,
      canvas: { characters: [], places: [], ideas: [] }
    };

    const brain = createTestBrain(context, sessionState, skillCalls);
    let lastSkillCount = 0;

    // ═══════════════════════════════════════════════════════════════
    // STEP 1: User grants photo access
    // ═══════════════════════════════════════════════════════════════
    trajectory.userAction('📸 Granted photo access');
    await brain.chat('[User granted photo access]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    expect(skillCalls.some(s => s.name === 'analyze_gallery')).toBe(true);

    // ═══════════════════════════════════════════════════════════════
    // STEP 2: Analysis completes, agent shows first character
    // ═══════════════════════════════════════════════════════════════
    sessionState.analysisResult = mockAnalysis;

    trajectory.userAction('Analysis complete - ready to explore');
    await brain.chat('[analysis_complete, gallery analyzed, found 3 characters: Mochi, Whiskers, Shadow]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    // ═══════════════════════════════════════════════════════════════
    // STEP 3: User LOVES first character (Mochi) ❤️
    // ═══════════════════════════════════════════════════════════════
    context.markShown('char_0');
    context.loved.add('char_0');

    trajectory.userAction('❤️ Loved Mochi');
    await brain.chat('[User reacted ❤️ on char_0 (Mochi)]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    // ═══════════════════════════════════════════════════════════════
    // STEP 4: User accepts creation suggestion
    // ═══════════════════════════════════════════════════════════════
    trajectory.userAction('Tapped "Create with Mochi"');
    await brain.chat('[User accepted creation suggestion for char_0 (Mochi)]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    // ═══════════════════════════════════════════════════════════════
    // STEP 5: Photos selected, character generated
    // ═══════════════════════════════════════════════════════════════
    const savedChar = createMockSavedCharacter({ id: 'mochi_001', name: 'Mochi' });
    context.updateSavedCharacters([savedChar]);
    context.recordGeneration('char_0', 'Mochi');

    trajectory.userAction('Selected 5 photos → Character generated');
    trajectory.captureContext(context);

    // ═══════════════════════════════════════════════════════════════
    // STEP 6: User clicks "Make a Manga"
    // ═══════════════════════════════════════════════════════════════
    trajectory.userAction('Tapped "Make a Manga"');
    await brain.chat('[clicked "Make a Manga" for character "Mochi" (ID: mochi_001)]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    // ═══════════════════════════════════════════════════════════════
    // STEP 7: User selects story option → Comic generated!
    // ═══════════════════════════════════════════════════════════════
    trajectory.userAction('Selected "A Day of Adventure" story');
    await brain.chat('[User selected "A Day of Adventure" for a 4-panel comic with Mochi. Story beats: Wake up → Explore → Challenge → Victory. Generate the comic now!]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    // Verify journey
    const skills = skillCalls.map(s => s.name);
    trajectory.decision(`Journey complete: ${skills.join(' → ')}`);

    reporter.addTrajectory(trajectory.toJSON());
  }, 60000);

  /**
   * SESSION B: Picky User
   * User skips first two characters, loves the third one, makes a scene
   */
  it('Session B: Picky User → Skip → Skip → Love → Scene', async () => {
    const trajectory = new TrajectoryCollector('Session B: Picky User');
    const context = new AgentContext();
    const skillCalls = [];

    const mockAnalysis = createMockAnalysisResponse({
      characterCount: 4,
      characterType: 'pet',
      photosPerCharacter: 5
    });
    mockAnalysis.life_characters[0].name_suggestion = 'Grumpy';
    mockAnalysis.life_characters[1].name_suggestion = 'Boring';
    mockAnalysis.life_characters[2].name_suggestion = 'Luna';  // The one they'll love!
    mockAnalysis.life_characters[3].name_suggestion = 'Max';

    const sessionState = {
      analysisResult: mockAnalysis,
      photoUrls: PHOTO_SETS.petsOnly.photos,
      canvas: { characters: [], places: [], ideas: [] }
    };

    const brain = createTestBrain(context, sessionState, skillCalls);
    let lastSkillCount = 0;

    // ═══════════════════════════════════════════════════════════════
    // STEP 1: User grants photo access
    // ═══════════════════════════════════════════════════════════════
    trajectory.userAction('📸 Granted photo access');
    await brain.chat('[User granted photo access]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);

    // ═══════════════════════════════════════════════════════════════
    // STEP 2: Analysis ready, start exploring
    // ═══════════════════════════════════════════════════════════════
    trajectory.userAction('Analysis complete - 4 characters found');
    await brain.chat('[analysis_complete, found: Grumpy, Boring, Luna, Max]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    // ═══════════════════════════════════════════════════════════════
    // STEP 3: User SKIPS first character (Grumpy) 😠
    // ═══════════════════════════════════════════════════════════════
    context.markShown('char_0');
    context.skipped.add('char_0');

    trajectory.userAction('😠 Skipped Grumpy');
    await brain.chat('[User reacted 😠 on char_0 (Grumpy)]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    // ═══════════════════════════════════════════════════════════════
    // STEP 4: User SKIPS second character (Boring) 😠
    // ═══════════════════════════════════════════════════════════════
    context.markShown('char_1');
    context.skipped.add('char_1');

    trajectory.userAction('😠 Skipped Boring');
    await brain.chat('[User reacted 😠 on char_1 (Boring)]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    // ═══════════════════════════════════════════════════════════════
    // STEP 5: User LOVES third character (Luna) ❤️
    // ═══════════════════════════════════════════════════════════════
    context.markShown('char_2');
    context.loved.add('char_2');

    trajectory.userAction('❤️ Loved Luna!');
    await brain.chat('[User reacted ❤️ on char_2 (Luna)]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    // ═══════════════════════════════════════════════════════════════
    // STEP 6: User accepts creation, chooses SCENE instead of comic
    // ═══════════════════════════════════════════════════════════════
    const savedChar = createMockSavedCharacter({ id: 'luna_001', name: 'Luna' });
    context.updateSavedCharacters([savedChar]);
    context.recordGeneration('char_2', 'Luna');

    trajectory.userAction('Character saved → Tapped "Create a Scene"');
    await brain.chat('[clicked "Create a Scene" for character "Luna" (ID: luna_001)]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    // ═══════════════════════════════════════════════════════════════
    // STEP 7: User picks scene style → Scene generated!
    // ═══════════════════════════════════════════════════════════════
    trajectory.userAction('Selected "Golden Hour Portrait"');
    await brain.chat('[User selected "Golden Hour Portrait" scene for Luna: Warm sunset lighting in a magical meadow. Generate the scene now!]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    const skills = skillCalls.map(s => s.name);
    trajectory.decision(`Journey: Skipped 2, loved 1, made scene → ${skills.join(' → ')}`);

    reporter.addTrajectory(trajectory.toJSON());
  }, 60000);

  /**
   * SESSION C: Curious Explorer
   * User explores multiple characters, asks questions, then creates
   */
  it('Session C: Curious Explorer → Questions → Multiple chars → Comic', async () => {
    const trajectory = new TrajectoryCollector('Session C: Curious Explorer');
    const context = new AgentContext();
    const skillCalls = [];
    const textResponses = [];

    const mockAnalysis = createMockAnalysisResponse({
      characterCount: 3,
      characterType: 'pet',
      photosPerCharacter: 5
    });
    mockAnalysis.life_characters[0].name_suggestion = 'Mochi';
    mockAnalysis.life_characters[1].name_suggestion = 'Tofu';
    mockAnalysis.life_characters[2].name_suggestion = 'Bean';

    const sessionState = {
      analysisResult: mockAnalysis,
      photoUrls: PHOTO_SETS.petsOnly.photos,
      canvas: { characters: [], places: [], ideas: [] }
    };

    const executor = vi.fn(async (name, args) => {
      skillCalls.push({ name, args, timestamp: Date.now() });
      return { success: true };
    });

    const brain = new AgentBrain({
      getApiKey: createMockApiKeyGetter('real'),
      context,
      getSessionState: () => sessionState,
      onSkillExecute: executor,
      onTextResponse: (text) => textResponses.push(text),
      onTechFlow: vi.fn()
    });
    let lastSkillCount = 0;

    // ═══════════════════════════════════════════════════════════════
    // STEP 1: User grants photo access
    // ═══════════════════════════════════════════════════════════════
    trajectory.userAction('📸 Granted photo access');
    await brain.chat('[User granted photo access]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);

    // ═══════════════════════════════════════════════════════════════
    // STEP 2: Analysis ready
    // ═══════════════════════════════════════════════════════════════
    trajectory.userAction('Analysis complete');
    await brain.chat('[analysis_complete, found: Mochi, Tofu, Bean]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    // ═══════════════════════════════════════════════════════════════
    // STEP 3: User asks a QUESTION instead of reacting
    // ═══════════════════════════════════════════════════════════════
    trajectory.userAction('Asked: "What can I make with these characters?"');
    await brain.chat('[User message: "What can I make with these characters?"]');

    // Record any text response
    if (textResponses.length > 0) {
      trajectory.agentResponse({
        type: 'text',
        content: textResponses[textResponses.length - 1]
      });
    }
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    // ═══════════════════════════════════════════════════════════════
    // STEP 4: User loves MULTIPLE characters
    // ═══════════════════════════════════════════════════════════════
    context.markShown('char_0');
    context.loved.add('char_0');

    trajectory.userAction('❤️ Loved Mochi');
    await brain.chat('[User reacted ❤️ on char_0 (Mochi)]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);

    context.markShown('char_1');
    context.loved.add('char_1');

    trajectory.userAction('❤️ Loved Tofu too!');
    await brain.chat('[User reacted ❤️ on char_1 (Tofu)]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    // ═══════════════════════════════════════════════════════════════
    // STEP 5: User wants to create with BOTH characters
    // ═══════════════════════════════════════════════════════════════
    const mochi = createMockSavedCharacter({ id: 'mochi_001', name: 'Mochi' });
    const tofu = createMockSavedCharacter({ id: 'tofu_001', name: 'Tofu' });
    context.updateSavedCharacters([mochi, tofu]);

    trajectory.userAction('Asked: "Can I make a comic with both Mochi and Tofu?"');
    await brain.chat('[User message: "Can I make a comic with both Mochi and Tofu together?"]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    // ═══════════════════════════════════════════════════════════════
    // STEP 6: Generate comic with both
    // ═══════════════════════════════════════════════════════════════
    trajectory.userAction('Selected "Friendship Adventure" for Mochi & Tofu');
    await brain.chat('[User wants a 4-panel comic with both Mochi and Tofu. Theme: "Friendship Adventure". Story: They meet → Play together → Get into mischief → Happy ending. Generate now!]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    const skills = skillCalls.map(s => s.name);
    trajectory.decision(`Curious path: questions + multiple chars → ${skills.join(' → ')}`);

    reporter.addTrajectory(trajectory.toJSON());
  }, 60000);

  /**
   * SESSION D: Returning User
   * User already has saved characters, comes back to create more
   */
  it('Session D: Returning User → Uses saved character → New comic', async () => {
    const trajectory = new TrajectoryCollector('Session D: Returning User');
    const context = new AgentContext();
    const skillCalls = [];
    const textResponses = [];

    // Pre-existing saved characters from previous session
    const existingChars = [
      createMockSavedCharacter({ id: 'old_mochi', name: 'Mochi' }),
      createMockSavedCharacter({ id: 'old_whiskers', name: 'Whiskers' })
    ];
    context.updateSavedCharacters(existingChars);

    const mockAnalysis = createMockAnalysisResponse({
      characterCount: 2,
      characterType: 'pet'
    });

    const sessionState = {
      analysisResult: mockAnalysis,
      photoUrls: PHOTO_SETS.petsOnly.photos,
      canvas: { characters: existingChars, places: [], ideas: [] }
    };

    const executor = vi.fn(async (name, args) => {
      skillCalls.push({ name, args, timestamp: Date.now() });
      return { success: true };
    });

    const brain = new AgentBrain({
      getApiKey: createMockApiKeyGetter('real'),
      context,
      getSessionState: () => sessionState,
      onSkillExecute: executor,
      onTextResponse: (text) => textResponses.push(text),
      onTechFlow: vi.fn()
    });
    let lastSkillCount = 0;

    // ═══════════════════════════════════════════════════════════════
    // STEP 1: Returning user opens app (no photo access needed)
    // ═══════════════════════════════════════════════════════════════
    trajectory.userAction('Opened app (has 2 saved characters)');
    trajectory.captureContext(context);

    // ═══════════════════════════════════════════════════════════════
    // STEP 2: User asks what they can do
    // ═══════════════════════════════════════════════════════════════
    trajectory.userAction('Asked: "What can I do with my characters?"');
    await brain.chat('[User message: "What can I do with Mochi and Whiskers?"]');

    if (textResponses.length > 0) {
      trajectory.agentResponse({
        type: 'text',
        content: textResponses[textResponses.length - 1]
      });
    }
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    // ═══════════════════════════════════════════════════════════════
    // STEP 3: User wants a comic with old character
    // ═══════════════════════════════════════════════════════════════
    trajectory.userAction('Said: "Make a comic with Mochi about a rainy day"');
    await brain.chat('[User message: "Make a comic with Mochi about a rainy day adventure"]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    // ═══════════════════════════════════════════════════════════════
    // STEP 4: Agent develops story and generates
    // ═══════════════════════════════════════════════════════════════
    trajectory.userAction('Confirmed story idea');
    await brain.chat('[User confirmed "Rainy Day Adventure" - 4 panels: Mochi sees rain → Hesitates at door → Plays in puddles → Cozy dry-off. Generate!]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    const skills = skillCalls.map(s => s.name);
    trajectory.decision(`Returning user: started with saved chars → ${skills.join(' → ')}`);

    reporter.addTrajectory(trajectory.toJSON());
  }, 60000);

  /**
   * SESSION E: Explorer Who Doesn't Create
   * User browses all characters but doesn't commit to creation
   */
  it('Session E: Window Shopper → Explores all → Wraps up', async () => {
    const trajectory = new TrajectoryCollector('Session E: Window Shopper');
    const context = new AgentContext();
    const skillCalls = [];

    const mockAnalysis = createMockAnalysisResponse({
      characterCount: 3,
      characterType: 'pet',
      photosPerCharacter: 3  // Few photos = no creation suggestion
    });
    mockAnalysis.life_characters[0].name_suggestion = 'Fluffy';
    mockAnalysis.life_characters[1].name_suggestion = 'Spots';
    mockAnalysis.life_characters[2].name_suggestion = 'Mittens';

    const sessionState = {
      analysisResult: mockAnalysis,
      photoUrls: PHOTO_SETS.minimal.photos,
      canvas: { characters: [], places: [], ideas: [] }
    };

    const brain = createTestBrain(context, sessionState, skillCalls);
    let lastSkillCount = 0;

    // ═══════════════════════════════════════════════════════════════
    // STEP 1: User grants access
    // ═══════════════════════════════════════════════════════════════
    trajectory.userAction('📸 Granted photo access');
    await brain.chat('[User granted photo access]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);

    trajectory.userAction('Analysis complete');
    await brain.chat('[analysis_complete, found: Fluffy, Spots, Mittens]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    // ═══════════════════════════════════════════════════════════════
    // STEP 2-4: User views all characters without strong reactions
    // ═══════════════════════════════════════════════════════════════
    context.markShown('char_0');
    trajectory.userAction('Viewed Fluffy (no reaction)');
    await brain.chat('[User viewed char_0 (Fluffy), no reaction, moved on]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);

    context.markShown('char_1');
    trajectory.userAction('Viewed Spots (no reaction)');
    await brain.chat('[User viewed char_1 (Spots), no reaction, moved on]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);

    context.markShown('char_2');
    trajectory.userAction('Viewed Mittens (no reaction)');
    await brain.chat('[User viewed char_2 (Mittens), no reaction - all characters seen]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    // ═══════════════════════════════════════════════════════════════
    // STEP 5: All explored, session wraps up
    // ═══════════════════════════════════════════════════════════════
    trajectory.userAction('Explored everything, no creation');
    await brain.chat('[All characters explored. User has not loved any. What should we do?]');
    lastSkillCount = recordResponse(trajectory, skillCalls, lastSkillCount);
    trajectory.captureContext(context);

    const skills = skillCalls.map(s => s.name);
    trajectory.decision(`Window shopper: browsed all, created nothing → ${skills.join(' → ')}`);

    reporter.addTrajectory(trajectory.toJSON());
  }, 60000);

});

// Generate single report with all sessions
afterAll(() => {
  try {
    reporter.saveToFile('./test-reports/e2e-sessions.html');
    console.log('\n📱 E2E Session Report: ./test-reports/e2e-sessions.html');
    console.log('   Open to see complete user journeys as phone transcripts\n');
  } catch (err) {
    console.warn('⚠️  Could not generate report:', err.message);
  }
});
