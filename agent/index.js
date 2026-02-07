/**
 * Agent Module Index
 *
 * Re-exports all agent components for easy importing.
 *
 * Usage:
 *   import { AgentBrain, AgentContext, skillFunctions } from '../agent/index.js';
 *   import { Workspace, getWorkspace } from '../agent/index.js';
 */

export { AgentBrain, createAgentBrain } from './brain.js';
export { AgentContext, buildSystemPrompt, buildInitialPrompt, getSubjectById } from './context.js';
export { skillFunctions, getSkillByName, validateSkillArgs } from './skills.js';
export { Workspace, getWorkspace, hasWorkspaceContent } from './workspace.js';
