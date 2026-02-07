/**
 * Agent Brain — 100% Agentic Architecture
 *
 * Gemini is the SOLE decision maker. No fallback behavior.
 * All next-step logic is determined by Gemini, not if/else.
 *
 * This module handles:
 * 1. Conversation history management
 * 2. Gemini API calls with function calling
 * 3. Skill dispatch and execution
 * 4. Error display (no fake intelligence on failure)
 */

import { skillFunctions, validateSkillArgs } from './skills.js';
import { buildSystemPrompt, buildInitialPrompt, getSubjectById } from './context.js';
import { PipelineManager, buildPipelineContext } from './pipelines.js';

// API endpoint (proxied through backend - no API key needed in frontend)
const AGENT_CHAT_ENDPOINT = '/api/agent/chat';

/**
 * Agent Brain - Gemini-first architecture
 */
export class AgentBrain {
    constructor(config) {
        // Note: No API key needed - calls are proxied through backend
        this.context = config.context;
        this.getSessionState = config.getSessionState;
        this.onSkillExecute = config.onSkillExecute;
        this.onTextResponse = config.onTextResponse;
        this.onError = config.onError || ((msg) => console.error('[AgentBrain]', msg));
        this.onTechFlow = config.onTechFlow || (() => {});

        this.conversationHistory = [];
        this.pipelines = new PipelineManager();
    }

    reset() {
        this.conversationHistory = [];
        this.pipelines.clear();
        this.context.reset();
    }

    /**
     * Main chat function — ALWAYS calls Gemini via backend proxy (no fallback)
     */
    async chat(userMessage) {
        // Add user message to history
        this.conversationHistory.push({
            role: 'user',
            parts: [{ text: userMessage }]
        });

        try {
            const sessionState = this.getSessionState();

            // Build context-aware system prompt
            const systemPrompt = this.buildFullSystemPrompt(sessionState);

            this.onTechFlow('api', 'Gemini Call', 'Sending to Gemini...');

            // Call backend proxy (uses server's API key from .env)
            const response = await fetch(AGENT_CHAT_ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    contents: this.conversationHistory,
                    system_instruction: systemPrompt,
                    tools: skillFunctions
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`API error ${response.status}: ${errorText.slice(0, 200)}`);
            }

            const data = await response.json();
            return this.handleResponse(data);

        } catch (error) {
            console.error('[AgentBrain] Error:', error);
            return this.showError(`Something went wrong: ${error.message}`);
        }
    }

    /**
     * Build complete system prompt with all context
     */
    buildFullSystemPrompt(sessionState) {
        const analysisResult = sessionState.analysisResult;
        const photoUrls = sessionState.photoUrls || [];

        // Base prompt depends on whether we have analysis
        let basePrompt;
        if (analysisResult) {
            basePrompt = buildSystemPrompt(analysisResult, this.context, sessionState.canvas);
        } else {
            // Pass photo URLs so Gemini knows what to pass to analyze_gallery
            basePrompt = buildInitialPrompt(photoUrls.length, this.context, photoUrls);
        }

        // Add pipeline context if any creations are in progress
        const pipelineContext = buildPipelineContext(this.pipelines);

        if (pipelineContext) {
            basePrompt += '\n\n' + pipelineContext;
        }

        return basePrompt;
    }

    /**
     * Handle Gemini response
     */
    async handleResponse(data) {
        const candidate = data.candidates?.[0];
        const content = candidate?.content;

        // Handle malformed function call
        if (candidate?.finishReason === 'MALFORMED_FUNCTION_CALL') {
            const parsed = this.parseTextFunctionCall(candidate.finishMessage);
            if (parsed) {
                return this.executeFunctionCall(parsed.name, parsed.args);
            }
            return this.showError('Gemini returned an invalid response. Please try again.');
        }

        if (!content?.parts) {
            return this.showError('No response from Gemini. Please try again.');
        }

        // Check for function call
        const functionCallPart = content.parts.find(p => p.functionCall);

        if (functionCallPart) {
            const { name, args } = functionCallPart.functionCall;
            // Pass the entire part to preserve thought_signature
            return this.executeFunctionCall(name, args || {}, functionCallPart);
        }

        // Text response
        const text = content.parts.find(p => p.text)?.text || '';
        this.conversationHistory.push({
            role: 'model',
            parts: [{ text }]
        });

        if (text) {
            this.onTextResponse(text);
        }

        return { type: 'text', content: text };
    }

    /**
     * Execute a function call from Gemini
     * @param {string} name - Function name
     * @param {object} args - Function arguments
     * @param {object} originalPart - Original part from Gemini (includes thought_signature)
     */
    async executeFunctionCall(name, args, originalPart) {
        // Add function call to history - use original part to preserve thought_signature
        this.conversationHistory.push({
            role: 'model',
            parts: [originalPart || { functionCall: { name, args } }]
        });

        // Validate
        const validation = validateSkillArgs(name, args);
        if (!validation.valid) {
            console.warn(`[AgentBrain] Invalid args for ${name}:`, validation.missing);
        }

        // Execute the skill
        const result = await this.executeSkill(name, args);

        // Add function response to history (must come right after function call)
        this.conversationHistory.push({
            role: 'user',
            parts: [{ functionResponse: { name, response: result } }]
        });

        this.onTechFlow('agentic', 'Skill Executed', `<strong>${name}</strong>`);

        // TURN-BASED FLOW: Some skills should stop and wait for user input
        // Only continue automatically for skills that need processing (like analyze_gallery)
        const waitForUserSkills = [
            'show_card',           // Showed something, wait for reaction
            'create_character',    // Started generation, wait for completion
            'create_manga',        // Started generation, wait for completion
            'ask_story_question',  // Asked a question, wait for answer
            'confirm_story',       // Showed outline, wait for confirmation
            'respond'              // Said something, wait for reply
        ];

        if (waitForUserSkills.includes(name)) {
            // Don't auto-continue - wait for user's next action
            return { type: 'skill', skill: name, result };
        }

        // For skills like analyze_gallery, continue so Gemini can process the result
        return await this.continueAfterFunctionCall();
    }

    /**
     * Continue conversation after function response
     */
    async continueAfterFunctionCall() {
        try {
            const sessionState = this.getSessionState();
            const systemPrompt = this.buildFullSystemPrompt(sessionState);

            // Debug: log conversation history
            console.log('[AgentBrain] continueAfterFunctionCall - history length:', this.conversationHistory.length);
            this.conversationHistory.forEach((msg, i) => {
                const parts = msg.parts?.map(p => {
                    if (p.text) return `text(${p.text.length})`;
                    if (p.functionCall) return `funcCall(${p.functionCall.name})`;
                    if (p.functionResponse) return `funcResp(${p.functionResponse.name})`;
                    return 'unknown';
                });
                console.log(`  [${i}] role=${msg.role}, parts=${JSON.stringify(parts)}`);
            });

            const response = await fetch(AGENT_CHAT_ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    contents: this.conversationHistory,
                    system_instruction: systemPrompt,
                    tools: skillFunctions
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`API error ${response.status}: ${errorText.slice(0, 200)}`);
            }

            const data = await response.json();
            return this.handleResponse(data);

        } catch (error) {
            console.error('[AgentBrain] Error continuing after function:', error);
            return this.showError(`Something went wrong: ${error.message}`);
        }
    }

    /**
     * Execute a skill by name
     */
    async executeSkill(name, args) {
        const sessionState = this.getSessionState();
        const analysisResult = sessionState.analysisResult;

        switch (name) {
            case 'analyze_gallery': {
                // Inject photo URLs from session state (not from Gemini args)
                const photoUrls = sessionState.photoUrls || [];
                await this.onSkillExecute('analyze_gallery', { photo_urls: photoUrls });
                return { success: true, message: `Analyzed ${photoUrls.length} photos` };
            }

            case 'show_card': {
                const { card_type, subject_id, content, message } = args;

                // Handle different card types
                if (card_type === 'subject' && subject_id) {
                    const subject = getSubjectById(subject_id, analysisResult);
                    if (subject) {
                        this.context.markShown(subject_id);
                        await this.onSkillExecute('show_card', {
                            card_type: 'subject',
                            subject_id,
                            subject,
                            message,
                            hasMore: this.context.hasUnshownSubjects(analysisResult)
                        });
                        return { success: true, message: `Showed ${subject_id}` };
                    }
                }

                // Generic card display
                await this.onSkillExecute('show_card', { card_type, content, message });
                return { success: true, message: `Showed ${card_type} card` };
            }

            case 'create_character': {
                const { subject_id, photo_indices, name: charName } = args;
                await this.onSkillExecute('create_character', {
                    subject_id,
                    photo_indices,
                    name: charName
                });
                return { success: true, message: 'Character generation started' };
            }

            case 'create_manga': {
                const { character_ids, story_beats, dialogues, style } = args;

                // Resolve all character IDs to character objects
                const ids = Array.isArray(character_ids) ? character_ids : [character_ids];
                const characters = ids
                    .map(id => this.context.savedCharacters.find(c => c.id === id))
                    .filter(c => c != null);

                if (characters.length === 0) {
                    return { success: false, error: `No characters found for IDs: ${ids.join(', ')}` };
                }

                console.log(`[AgentBrain] create_manga with ${characters.length} characters: ${characters.map(c => c.name).join(', ')}`);

                await this.onSkillExecute('create_manga', {
                    characters,  // Array of character objects
                    panel_count: story_beats.length,
                    story_beats,
                    dialogues: dialogues || [],
                    style: style || 'manga'
                });

                return { success: true, message: `Generated ${story_beats.length}-panel manga with ${characters.length} characters` };
            }

            case 'ask_story_question': {
                const { character_id, question, options, story_context } = args;

                // Handle multi-character IDs - use first character for now
                const firstId = character_id?.includes(',')
                    ? character_id.split(',')[0].trim()
                    : character_id;
                const character = this.context.savedCharacters.find(c => c.id === firstId);

                await this.onSkillExecute('ask_story_question', {
                    character,
                    question,
                    options,
                    story_context
                });

                return { success: true, message: 'Asked story question' };
            }

            case 'confirm_story': {
                const { character_id, synopsis, story_beats, dialogues } = args;

                // Handle multi-character IDs - use first character for now
                const firstId = character_id?.includes(',')
                    ? character_id.split(',')[0].trim()
                    : character_id;
                const character = this.context.savedCharacters.find(c => c.id === firstId);

                await this.onSkillExecute('confirm_story', {
                    character,
                    synopsis,
                    story_beats,
                    dialogues
                });

                return { success: true, message: 'Story confirmed, ready to generate' };
            }

            case 'respond': {
                const { message } = args;
                if (message) {
                    this.onTextResponse(message);
                }
                return { success: true, message: 'Responded' };
            }

            default:
                return { success: false, error: `Unknown skill: ${name}` };
        }
    }

    /**
     * Show error to user (no fake behavior)
     */
    showError(message) {
        this.onError(message);
        this.onTextResponse(`⚠️ ${message}`);
        return { type: 'error', error: message };
    }

    /**
     * Parse text-based function call from malformed Gemini output
     */
    parseTextFunctionCall(finishMessage) {
        if (!finishMessage) return null;

        try {
            const match = finishMessage.match(/call:default_api:(\w+)\{(.+)/);
            if (!match) return null;

            const name = match[1];
            let argsStr = match[2];

            // Balance braces
            let braceCount = 1;
            for (const char of argsStr) {
                if (char === '{') braceCount++;
                if (char === '}') braceCount--;
            }
            while (braceCount > 0) {
                argsStr += '}';
                braceCount--;
            }

            let args = {};
            try {
                args = JSON.parse('{' + argsStr);
            } catch {
                args = {};
            }

            return { name, args };
        } catch {
            return null;
        }
    }
}

/**
 * Factory function
 */
export function createAgentBrain(config) {
    return new AgentBrain(config);
}
