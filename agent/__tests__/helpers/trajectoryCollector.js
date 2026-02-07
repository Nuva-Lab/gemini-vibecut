/**
 * Trajectory Collector
 *
 * Collects agent interaction trajectory for analysis and reporting.
 * Records the complete flow of user actions → agent responses → skill executions.
 *
 * Usage:
 *   const trajectory = new TrajectoryCollector('test-name');
 *   trajectory.userAction('[User granted photo access]');
 *   trajectory.agentResponse({ type: 'function', name: 'highlight_subject', args: {...} });
 *   trajectory.skillResult('highlight_subject', { success: true });
 *   trajectory.captureContext(context);
 *
 * At the end of the test, call trajectory.toJSON() to get exportable data.
 */

export class TrajectoryCollector {
  /**
   * Create a new trajectory collector
   * @param {string} testName - Name of the test being tracked
   */
  constructor(testName) {
    this.testName = testName;
    this.startTime = Date.now();
    this.steps = [];
    this.contextSnapshots = [];
    this.metadata = {
      // Auto-detect if real API is being used
      usedRealApi: globalThis.isRealApiEnabled?.() || false
    };
  }

  /**
   * Record a user action
   * @param {string} action - Description of the user action
   * @param {object} metadata - Additional metadata about the action
   */
  userAction(action, metadata = {}) {
    this.steps.push({
      type: 'user',
      timestamp: Date.now() - this.startTime,
      action,
      ...metadata
    });
  }

  /**
   * Record an agent response
   * @param {object} response - The response object from AgentBrain.chat()
   */
  agentResponse(response) {
    this.steps.push({
      type: 'agent',
      timestamp: Date.now() - this.startTime,
      responseType: response.type,
      skillName: response.name || null,
      skillArgs: response.args || null,
      textContent: response.content || null,
      error: response.error || null
    });
  }

  /**
   * Record raw agent response before processing
   * @param {object} rawResponse - Raw Gemini API response
   */
  rawApiResponse(rawResponse) {
    this.steps.push({
      type: 'api_response',
      timestamp: Date.now() - this.startTime,
      hasFunctionCall: !!rawResponse?.candidates?.[0]?.content?.parts?.find(p => p.functionCall),
      hasText: !!rawResponse?.candidates?.[0]?.content?.parts?.find(p => p.text)
    });
  }

  /**
   * Snapshot the current context state
   * @param {AgentContext} context - The context to snapshot
   */
  captureContext(context) {
    this.contextSnapshots.push({
      timestamp: Date.now() - this.startTime,
      shown: [...(context.shown || [])],
      loved: [...(context.loved || [])],
      skipped: [...(context.skipped || [])],
      savedCharacters: context.savedCharacters?.length || 0,
      generatedCharacters: context.generatedCharacters?.length || 0,
      pendingStory: context.pendingStory ? {
        type: context.pendingStory.type,
        characterName: context.pendingStory.characterName,
        status: context.pendingStory.status
      } : null,
      pendingSkill: context.pendingSkill ? context.pendingSkill.type : null
    });
  }

  /**
   * Record a skill execution result
   * @param {string} skillName - Name of the skill
   * @param {object} result - Result of the skill execution
   */
  skillResult(skillName, result) {
    this.steps.push({
      type: 'skill_result',
      timestamp: Date.now() - this.startTime,
      skillName,
      success: result.success ?? true,
      resultSummary: this._summarizeResult(result)
    });
  }

  /**
   * Record a decision point (for agentic behavior analysis)
   * @param {string} decision - Description of the decision made
   * @param {object} options - Available options at this point
   */
  decisionPoint(decision, options = {}) {
    this.steps.push({
      type: 'decision',
      timestamp: Date.now() - this.startTime,
      decision,
      availableOptions: options.available || [],
      chosenOption: options.chosen || null,
      rationale: options.rationale || null
    });
  }

  /**
   * Record a decision (alias for decisionPoint with simpler signature)
   * @param {string} decision - Description of the decision made
   * @param {string} rationale - Why this decision was made
   */
  decision(decision, rationale = '') {
    this.steps.push({
      type: 'decision',
      timestamp: Date.now() - this.startTime,
      decision,
      rationale
    });
  }

  /**
   * Add custom metadata to the trajectory
   * @param {string} key - Metadata key
   * @param {any} value - Metadata value
   */
  addMetadata(key, value) {
    this.metadata[key] = value;
  }

  /**
   * Summarize a result object for display
   * @private
   */
  _summarizeResult(result) {
    if (typeof result === 'string') return result.slice(0, 100);
    if (result.message) return result.message;
    if (result.error) return `Error: ${result.error}`;
    return JSON.stringify(result).slice(0, 100);
  }

  /**
   * Generate a summary of the trajectory
   * @private
   */
  _generateSummary() {
    const userActions = this.steps.filter(s => s.type === 'user');
    const agentResponses = this.steps.filter(s => s.type === 'agent');
    const skillResults = this.steps.filter(s => s.type === 'skill_result');
    const skillCalls = agentResponses.filter(s => s.skillName);

    return {
      totalSteps: this.steps.length,
      userActions: userActions.length,
      agentResponses: agentResponses.length,
      skillsCalled: skillCalls.map(s => s.skillName),
      uniqueSkills: [...new Set(skillCalls.map(s => s.skillName))],
      successfulSkills: skillResults.filter(s => s.success).length,
      failedSkills: skillResults.filter(s => !s.success).length,
      contextSnapshots: this.contextSnapshots.length
    };
  }

  /**
   * Export trajectory as JSON
   * @returns {object} Complete trajectory data
   */
  toJSON() {
    return {
      testName: this.testName,
      startTime: this.startTime,
      duration: Date.now() - this.startTime,
      stepCount: this.steps.length,
      steps: this.steps,
      contextSnapshots: this.contextSnapshots,
      metadata: this.metadata,
      summary: this._generateSummary()
    };
  }

  /**
   * Get a human-readable summary string
   * @returns {string} Summary of the trajectory
   */
  getSummaryString() {
    const summary = this._generateSummary();
    return [
      `Test: ${this.testName}`,
      `Duration: ${Date.now() - this.startTime}ms`,
      `Steps: ${summary.totalSteps}`,
      `User actions: ${summary.userActions}`,
      `Skills called: ${summary.uniqueSkills.join(', ') || 'none'}`,
      `Success rate: ${summary.successfulSkills}/${summary.successfulSkills + summary.failedSkills}`
    ].join('\n');
  }
}

/**
 * Create a trajectory collector and register it for report generation
 * @param {string} testName - Name of the test
 * @returns {TrajectoryCollector} New trajectory collector
 */
export function createTrajectory(testName) {
  return new TrajectoryCollector(testName);
}
