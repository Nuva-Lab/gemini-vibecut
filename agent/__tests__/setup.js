/**
 * Test setup: Global mocks and helpers for agent brain tests
 *
 * This file runs before all tests and sets up the environment.
 *
 * Environment:
 *   - GOOGLE_API_KEY: Loaded from .env, enables real API testing
 *   - Set USE_REAL_API=true to run integration tests with actual Gemini API
 */
import { vi, beforeEach, afterEach } from 'vitest';

// Store for trajectory data that can be accessed after tests
globalThis.__trajectoryStore = [];

// Real API key from environment (loaded via vitest.config.js)
const REAL_API_KEY = process.env.GOOGLE_API_KEY || null;

// Flag to control whether tests use real API
const USE_REAL_API = process.env.USE_REAL_API === 'true';

// Log API status at test startup
if (REAL_API_KEY) {
  console.log('✅ GOOGLE_API_KEY found in environment');
  if (USE_REAL_API) {
    console.log('🌐 USE_REAL_API=true — Integration tests will call Gemini API');
  } else {
    console.log('🔒 USE_REAL_API not set — Using fallback mode (set USE_REAL_API=true for API tests)');
  }
} else {
  console.log('⚠️  No GOOGLE_API_KEY found — All tests will use fallback mode');
}

/**
 * Add trajectory to global store for report generation
 */
globalThis.addTrajectory = (trajectory) => {
  globalThis.__trajectoryStore.push(trajectory);
};

/**
 * Get all trajectories (used by report generator)
 */
globalThis.getTrajectories = () => {
  return globalThis.__trajectoryStore;
};

/**
 * Check if real API is available and enabled
 */
globalThis.isRealApiEnabled = () => {
  return REAL_API_KEY && USE_REAL_API;
};

/**
 * Get the real API key (for integration tests)
 */
globalThis.getRealApiKey = () => {
  return REAL_API_KEY;
};

// Reset mocks before each test
beforeEach(() => {
  vi.clearAllMocks();
});

// Clean up after each test
afterEach(() => {
  vi.restoreAllMocks();
});

/**
 * Create a mock API key getter
 * @param {string|null} key - API key to return, or null for fallback mode
 *                           Use 'real' to use the actual GOOGLE_API_KEY
 */
export function createMockApiKeyGetter(key = null) {
  if (key === 'real') {
    return vi.fn(() => REAL_API_KEY);
  }
  return vi.fn(() => key);
}

/**
 * Create a mock session state getter
 * @param {object} overrides - Override specific state values
 */
export function createMockSessionStateGetter(overrides = {}) {
  return vi.fn(() => ({
    analysisResult: null,
    canvas: { characters: [], places: [], ideas: [] },
    photoUrls: [],
    ...overrides
  }));
}

/**
 * Create a mock skill executor
 * Records all skill executions for verification
 */
export function createMockSkillExecutor() {
  const executions = [];

  const executor = vi.fn(async (skillName, args) => {
    executions.push({ skillName, args, timestamp: Date.now() });

    // Return appropriate mock results based on skill
    switch (skillName) {
      case 'analyze_gallery':
        return { success: true, analysisResult: {} };
      case 'highlight_subject':
        return { success: true };
      case 'suggest_creation':
        return { success: true };
      case 'collect_references':
        return { success: true };
      case 'generate_anime':
        return { success: true, imageUrl: 'mock://generated.png' };
      case 'wrap_up_exploration':
        return { success: true };
      case 'use_saved_character':
        return { success: true };
      case 'develop_story':
        return { success: true };
      case 'generate_comic':
        return { success: true, panels: [] };
      case 'generate_scene':
        return { success: true, imageUrl: 'mock://scene.png' };
      default:
        return { success: false, error: `Unknown skill: ${skillName}` };
    }
  });

  executor.getExecutions = () => executions;
  executor.reset = () => { executions.length = 0; };

  return executor;
}

/**
 * Create a mock text response handler
 */
export function createMockTextResponseHandler() {
  const responses = [];

  const handler = vi.fn((text) => {
    responses.push({ text, timestamp: Date.now() });
  });

  handler.getResponses = () => responses;
  handler.reset = () => { responses.length = 0; };

  return handler;
}

/**
 * Create a mock tech flow logger
 */
export function createMockTechFlowLogger() {
  const logs = [];

  const logger = vi.fn((type, category, message) => {
    logs.push({ type, category, message, timestamp: Date.now() });
  });

  logger.getLogs = () => logs;
  logger.reset = () => { logs.length = 0; };

  return logger;
}

/**
 * Utility to wait for async operations
 */
export function waitFor(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
