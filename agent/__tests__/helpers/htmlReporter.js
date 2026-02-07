/**
 * Session Transcript Reporter
 *
 * Generates HTML that looks like scrolling through an actual phone session.
 * Shows the conversation as it would appear to a user, not test metadata.
 */

import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { dirname } from 'path';

export class HTMLReporter {
  constructor() {
    this.sessions = [];
    this.title = 'Agent Session Transcripts';
  }

  setTitle(title) {
    this.title = title;
  }

  /**
   * Add a session transcript
   * @param {object} session - Session data with steps
   */
  addTrajectory(session) {
    this.sessions.push(session);
  }

  addTrajectories(sessions) {
    this.sessions.push(...sessions);
  }

  generateReport() {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${this.title}</title>
  <style>
    :root {
      --bg: #000;
      --card-bg: #1c1c1e;
      --text: #fff;
      --text-dim: #8e8e93;
      --user-bubble: #0a84ff;
      --agent-bubble: #2c2c2e;
      --skill-color: #30d158;
      --error-color: #ff453a;
      --border: #38383a;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'SF Pro', sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
    }

    .container {
      max-width: 480px;
      margin: 0 auto;
      padding: 0;
    }

    /* Phone frame simulation */
    .phone-frame {
      background: var(--bg);
      border-radius: 40px;
      margin: 20px auto;
      padding: 20px 0;
      max-width: 420px;
      box-shadow: 0 0 0 14px #1c1c1e, 0 0 0 16px #000;
    }

    .session {
      margin-bottom: 40px;
    }

    .session-header {
      text-align: center;
      padding: 20px;
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      background: var(--bg);
      z-index: 10;
    }

    .session-title {
      font-size: 17px;
      font-weight: 600;
    }

    .session-meta {
      font-size: 12px;
      color: var(--text-dim);
      margin-top: 4px;
    }

    .session-status {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 10px;
      font-size: 11px;
      margin-left: 8px;
    }

    .session-status.real-api { background: var(--skill-color); color: #000; }
    .session-status.fallback { background: var(--error-color); color: #fff; }

    .chat-container {
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    /* Message bubbles */
    .message {
      max-width: 85%;
      padding: 10px 14px;
      border-radius: 18px;
      font-size: 15px;
      line-height: 1.4;
      word-wrap: break-word;
    }

    .message.user {
      align-self: flex-end;
      background: var(--user-bubble);
      color: white;
      border-bottom-right-radius: 4px;
    }

    .message.agent {
      align-self: flex-start;
      background: var(--agent-bubble);
      color: var(--text);
      border-bottom-left-radius: 4px;
    }

    .message.system {
      align-self: center;
      background: transparent;
      color: var(--text-dim);
      font-size: 13px;
      padding: 8px;
    }

    /* Skill calls - show as special cards */
    .skill-call {
      align-self: flex-start;
      background: var(--card-bg);
      border: 1px solid var(--skill-color);
      border-radius: 12px;
      padding: 12px;
      max-width: 90%;
    }

    .skill-call .skill-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }

    .skill-call .skill-icon {
      width: 28px;
      height: 28px;
      background: var(--skill-color);
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
    }

    .skill-call .skill-name {
      color: var(--skill-color);
      font-weight: 600;
      font-size: 14px;
    }

    .skill-call .skill-args {
      font-family: 'SF Mono', monospace;
      font-size: 12px;
      color: var(--text-dim);
      background: rgba(0,0,0,0.3);
      padding: 8px;
      border-radius: 6px;
      overflow-x: auto;
    }

    .skill-call .skill-result {
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px solid var(--border);
      font-size: 13px;
      color: var(--text-dim);
    }

    /* UI Card simulation (what user would see) */
    .ui-card {
      align-self: flex-start;
      background: var(--card-bg);
      border-radius: 16px;
      overflow: hidden;
      max-width: 280px;
      margin: 4px 0;
    }

    .ui-card .card-image {
      width: 100%;
      height: 160px;
      background: linear-gradient(135deg, #2c2c2e, #1c1c1e);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 48px;
    }

    .ui-card .card-content {
      padding: 12px;
    }

    .ui-card .card-title {
      font-weight: 600;
      font-size: 15px;
    }

    .ui-card .card-subtitle {
      font-size: 13px;
      color: var(--text-dim);
      margin-top: 4px;
    }

    .ui-card .card-actions {
      display: flex;
      gap: 8px;
      margin-top: 12px;
    }

    .ui-card .card-btn {
      flex: 1;
      padding: 8px;
      border-radius: 8px;
      text-align: center;
      font-size: 13px;
      font-weight: 500;
    }

    .ui-card .card-btn.primary {
      background: var(--user-bubble);
      color: white;
    }

    .ui-card .card-btn.secondary {
      background: var(--agent-bubble);
      color: var(--text);
    }

    /* Context snapshot */
    .context-snapshot {
      align-self: center;
      background: rgba(255,149,0,0.15);
      border: 1px dashed rgba(255,149,0,0.5);
      border-radius: 8px;
      padding: 8px 12px;
      font-size: 11px;
      color: #ff9500;
      margin: 8px 0;
    }

    /* Decision point */
    .decision {
      align-self: center;
      background: rgba(175,82,222,0.15);
      border-radius: 8px;
      padding: 8px 12px;
      font-size: 12px;
      color: #af52de;
      text-align: center;
      max-width: 90%;
    }

    /* Timestamp */
    .timestamp {
      align-self: center;
      font-size: 11px;
      color: var(--text-dim);
      margin: 12px 0 4px;
    }

    /* Error state */
    .error-banner {
      background: var(--error-color);
      color: white;
      padding: 12px;
      text-align: center;
      font-size: 13px;
    }

    /* Summary footer */
    .session-footer {
      padding: 16px;
      border-top: 1px solid var(--border);
      text-align: center;
    }

    .session-footer .stat {
      display: inline-block;
      margin: 0 12px;
      font-size: 13px;
    }

    .session-footer .stat-value {
      font-weight: 600;
      color: var(--skill-color);
    }

    @media (max-width: 500px) {
      .phone-frame {
        border-radius: 0;
        box-shadow: none;
        margin: 0;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    ${this.sessions.map(s => this._renderSession(s)).join('')}
  </div>
</body>
</html>`;
  }

  _renderSession(session) {
    const usedRealApi = session.metadata?.usedRealApi || false;
    const summary = session.summary || {};

    return `
    <div class="phone-frame">
      <div class="session">
        <div class="session-header">
          <div class="session-title">${this._escape(session.testName)}</div>
          <div class="session-meta">
            ${session.duration}ms
            <span class="session-status ${usedRealApi ? 'real-api' : 'fallback'}">
              ${usedRealApi ? '🤖 Gemini API' : '⚠️ Fallback'}
            </span>
          </div>
        </div>

        ${!usedRealApi ? `
        <div class="error-banner">
          ⚠️ This session used FALLBACK mode, not real Gemini API
        </div>
        ` : ''}

        <div class="chat-container">
          ${this._renderMessages(session)}
        </div>

        <div class="session-footer">
          <span class="stat">Skills: <span class="stat-value">${summary.uniqueSkills?.length || 0}</span></span>
          <span class="stat">Steps: <span class="stat-value">${session.stepCount}</span></span>
        </div>
      </div>
    </div>`;
  }

  _renderMessages(session) {
    let html = '';
    let lastTimestamp = 0;

    for (const step of session.steps || []) {
      // Add timestamp if significant gap
      if (step.timestamp - lastTimestamp > 1000) {
        html += `<div class="timestamp">${this._formatTime(step.timestamp)}</div>`;
      }
      lastTimestamp = step.timestamp;

      html += this._renderStep(step);
    }

    // Add context snapshots at the end as summary
    if (session.contextSnapshots?.length > 0) {
      const final = session.contextSnapshots[session.contextSnapshots.length - 1];
      html += this._renderContextSummary(final);
    }

    return html;
  }

  _renderStep(step) {
    switch (step.type) {
      case 'user':
        return `<div class="message user">${this._formatUserAction(step.action)}</div>`;

      case 'agent':
        if (step.skillName) {
          return this._renderSkillCall(step);
        } else if (step.textContent) {
          return `<div class="message agent">${this._escape(step.textContent)}</div>`;
        }
        return '';

      case 'skill_result':
        return this._renderSkillResult(step);

      case 'decision':
        return `<div class="decision">💭 ${this._escape(step.decision)}</div>`;

      default:
        return '';
    }
  }

  _renderSkillCall(step) {
    const skillIcons = {
      'analyze_gallery': '🔍',
      'highlight_subject': '✨',
      'suggest_creation': '🎨',
      'collect_references': '📸',
      'generate_anime': '🎬',
      'wrap_up_exploration': '🎉',
      'use_saved_character': '👤',
      'develop_story': '📖',
      'generate_comic': '📚',
      'generate_scene': '🖼️'
    };

    const icon = skillIcons[step.skillName] || '⚡';

    return `
    <div class="skill-call">
      <div class="skill-header">
        <div class="skill-icon">${icon}</div>
        <div class="skill-name">${step.skillName}</div>
      </div>
      ${step.skillArgs ? `
      <div class="skill-args">${this._formatArgs(step.skillArgs)}</div>
      ` : ''}
    </div>`;
  }

  _renderSkillResult(step) {
    // Show as a simulated UI card for visual skills
    if (['highlight_subject', 'suggest_creation'].includes(step.skillName)) {
      return `
      <div class="ui-card">
        <div class="card-image">🐱</div>
        <div class="card-content">
          <div class="card-title">${step.skillName === 'suggest_creation' ? 'Create with this character?' : 'Character Found'}</div>
          <div class="card-subtitle">${this._escape(step.resultSummary)}</div>
          <div class="card-actions">
            <div class="card-btn primary">❤️</div>
            <div class="card-btn secondary">😠</div>
          </div>
        </div>
      </div>`;
    }

    // For other skills, just show the result inline
    return `<div class="message system">✅ ${this._escape(step.resultSummary)}</div>`;
  }

  _renderContextSummary(snapshot) {
    return `
    <div class="context-snapshot">
      📊 Final State: ${snapshot.shown?.length || 0} shown,
      ${snapshot.loved?.length || 0} ❤️,
      ${snapshot.skipped?.length || 0} 😠,
      ${snapshot.savedCharacters || 0} saved
    </div>`;
  }

  _formatUserAction(action) {
    // Convert action strings to more readable format
    const cleaned = action
      .replace(/^\[/, '')
      .replace(/\]$/, '')
      .replace('User ', '')
      .replace('clicked ', 'Tapped ')
      .replace('reacted ❤️', '❤️ Loved')
      .replace('reacted 😠', '😠 Skipped')
      .replace('granted photo access', '📸 Allowed photo access')
      .replace('message:', 'Said:');

    return this._escape(cleaned);
  }

  _formatArgs(args) {
    if (!args) return '';
    const entries = Object.entries(args);
    if (entries.length === 0) return '(no args)';

    return entries
      .map(([k, v]) => {
        const val = typeof v === 'string' ? v : JSON.stringify(v);
        const truncated = val.length > 50 ? val.slice(0, 47) + '...' : val;
        return `${k}: ${truncated}`;
      })
      .join('\n');
  }

  _formatTime(ms) {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  _escape(str) {
    if (typeof str !== 'string') return String(str);
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  saveToFile(filepath) {
    const dir = dirname(filepath);
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true });
    }
    writeFileSync(filepath, this.generateReport(), 'utf8');
  }
}

export function createReporter(title = 'Agent Session Transcripts') {
  const reporter = new HTMLReporter();
  reporter.setTitle(title);
  return reporter;
}
