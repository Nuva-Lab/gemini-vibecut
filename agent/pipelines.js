/**
 * Pipeline System for Creative Agent
 *
 * Pipelines track the inputs needed for asset creation.
 * They DON'T contain decision logic - that's Gemini's job.
 * They DO track what's been collected vs what's still missing.
 */

/**
 * Pipeline definitions
 *
 * Each pipeline has:
 * - required: inputs that MUST be provided before creation
 * - optional: nice-to-have inputs with defaults
 * - createSkill: the skill to call when all required inputs are collected
 */
export const PIPELINES = {
    character: {
        required: ['reference_photos', 'name'],
        optional: ['persona', 'style'],
        defaults: { style: 'anime' },
        createSkill: 'create_character'
    },
    comic: {
        required: ['character_id', 'story_beats'],
        optional: ['style', 'dialogues'],
        defaults: { style: 'manga' },
        createSkill: 'create_comic'
    },
    scene: {
        required: ['character_id', 'scene_description'],
        optional: ['mood'],
        defaults: { mood: 'happy' },
        createSkill: 'create_scene'
    }
};

/**
 * Pipeline instance - tracks collected inputs for one creation
 */
export class Pipeline {
    constructor(type, initialInputs = {}) {
        if (!PIPELINES[type]) {
            throw new Error(`Unknown pipeline type: ${type}`);
        }
        this.type = type;
        this.definition = PIPELINES[type];
        this.inputs = { ...this.definition.defaults, ...initialInputs };
        this.createdAt = new Date().toISOString();
    }

    /**
     * Add or update an input
     */
    setInput(key, value) {
        this.inputs[key] = value;
    }

    /**
     * Check if pipeline has all required inputs
     */
    isReady() {
        return this.getMissing().length === 0;
    }

    /**
     * Get list of missing required inputs
     */
    getMissing() {
        return this.definition.required.filter(key => !this.inputs[key]);
    }

    /**
     * Get list of collected required inputs
     */
    getCollected() {
        return this.definition.required.filter(key => this.inputs[key]);
    }

    /**
     * Get display summary of pipeline status
     */
    getSummary() {
        const collected = this.getCollected();
        const missing = this.getMissing();

        let summary = `${this.type}: `;
        const parts = [];

        for (const key of this.definition.required) {
            if (this.inputs[key]) {
                // Show what was collected
                let displayValue = this.inputs[key];
                if (Array.isArray(displayValue)) {
                    displayValue = `${displayValue.length} items`;
                } else if (typeof displayValue === 'object') {
                    displayValue = displayValue.name || displayValue.id || 'set';
                }
                parts.push(`${key} ✓ (${displayValue})`);
            } else {
                parts.push(`${key} ✗ MISSING`);
            }
        }

        return summary + parts.join(', ');
    }

    /**
     * Get the inputs formatted for the create skill
     */
    getSkillArgs() {
        return { ...this.inputs };
    }
}

/**
 * PipelineManager - manages active pipelines across the session
 */
export class PipelineManager {
    constructor() {
        this.pipelines = new Map(); // id -> Pipeline
        this.nextId = 1;
    }

    /**
     * Start a new pipeline
     * @returns {string} Pipeline ID
     */
    start(type, initialInputs = {}) {
        const id = `pipeline_${this.nextId++}`;
        this.pipelines.set(id, new Pipeline(type, initialInputs));
        return id;
    }

    /**
     * Get a pipeline by ID
     */
    get(id) {
        return this.pipelines.get(id);
    }

    /**
     * Get the most recent pipeline of a given type
     */
    getLatestByType(type) {
        let latest = null;
        for (const pipeline of this.pipelines.values()) {
            if (pipeline.type === type) {
                if (!latest || pipeline.createdAt > latest.createdAt) {
                    latest = pipeline;
                }
            }
        }
        return latest;
    }

    /**
     * Update pipeline inputs
     */
    update(id, key, value) {
        const pipeline = this.pipelines.get(id);
        if (pipeline) {
            pipeline.setInput(key, value);
        }
    }

    /**
     * Remove a pipeline (after creation or cancel)
     */
    remove(id) {
        this.pipelines.delete(id);
    }

    /**
     * Clear all pipelines
     */
    clear() {
        this.pipelines.clear();
        this.nextId = 1;
    }

    /**
     * Get context string for all active pipelines
     * This is included in the system prompt for Gemini
     */
    getContextString() {
        if (this.pipelines.size === 0) {
            return 'No active creations in progress.';
        }

        const summaries = [];
        for (const [id, pipeline] of this.pipelines) {
            summaries.push(`[${id}] ${pipeline.getSummary()}`);
        }
        return summaries.join('\n');
    }

    /**
     * Check if any pipeline is ready for creation
     */
    getReadyPipelines() {
        const ready = [];
        for (const [id, pipeline] of this.pipelines) {
            if (pipeline.isReady()) {
                ready.push({ id, pipeline });
            }
        }
        return ready;
    }
}

/**
 * Build pipeline context for inclusion in system prompt
 *
 * @param {PipelineManager} manager - The pipeline manager
 * @returns {string} - Formatted context string
 */
export function buildPipelineContext(manager) {
    if (!manager || manager.pipelines.size === 0) {
        return '';
    }

    let context = '## ACTIVE CREATIONS (Pipelines)\n';
    context += 'These are creations in progress. When all required inputs are collected, call the create skill.\n\n';
    context += manager.getContextString();

    const ready = manager.getReadyPipelines();
    if (ready.length > 0) {
        context += '\n\n⚡ READY TO CREATE:\n';
        for (const { id, pipeline } of ready) {
            context += `- [${id}] ${pipeline.type} has all inputs → call ${pipeline.definition.createSkill}\n`;
        }
    }

    return context;
}
