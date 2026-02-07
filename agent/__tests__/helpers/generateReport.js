#!/usr/bin/env node
/**
 * Report Generator Script
 *
 * Reads test results and generates HTML trajectory reports.
 * Run with: node agent/__tests__/helpers/generateReport.js
 */

import { readFileSync, writeFileSync, existsSync, readdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { HTMLReporter } from './htmlReporter.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = join(__dirname, '../../..');
const reportsDir = join(projectRoot, 'test-reports');
const trajectoriesDir = join(reportsDir, 'trajectories');

/**
 * Main function to generate reports
 */
async function main() {
  console.log('🔍 Scanning for trajectory files...');

  // Check if trajectories directory exists
  if (!existsSync(trajectoriesDir)) {
    console.log('ℹ️  No trajectories directory found. Run tests first with npm test');
    return;
  }

  // Find all trajectory JSON files
  const trajectoryFiles = readdirSync(trajectoriesDir)
    .filter(f => f.endsWith('.json'));

  if (trajectoryFiles.length === 0) {
    console.log('ℹ️  No trajectory files found. Run tests first.');
    return;
  }

  console.log(`📊 Found ${trajectoryFiles.length} trajectory files`);

  // Group trajectories by test file
  const groupedTrajectories = {};

  for (const file of trajectoryFiles) {
    const filepath = join(trajectoriesDir, file);
    const content = readFileSync(filepath, 'utf8');

    try {
      const trajectory = JSON.parse(content);
      const testFile = trajectory.metadata?.testFile || 'unknown';

      if (!groupedTrajectories[testFile]) {
        groupedTrajectories[testFile] = [];
      }
      groupedTrajectories[testFile].push(trajectory);
    } catch (err) {
      console.warn(`⚠️  Failed to parse ${file}: ${err.message}`);
    }
  }

  // Generate reports for each group
  for (const [testFile, trajectories] of Object.entries(groupedTrajectories)) {
    const reporter = new HTMLReporter();
    const reportName = testFile.replace('.test.js', '');
    reporter.setTitle(`Agent Brain Tests: ${reportName}`);
    reporter.addTrajectories(trajectories);

    const outputPath = join(reportsDir, `${reportName}.html`);
    reporter.saveToFile(outputPath);
    console.log(`✅ Generated: ${outputPath}`);
  }

  // Generate combined report
  const allTrajectories = Object.values(groupedTrajectories).flat();
  if (allTrajectories.length > 0) {
    const combinedReporter = new HTMLReporter();
    combinedReporter.setTitle('Agent Brain Tests: Complete Report');
    combinedReporter.addTrajectories(allTrajectories);

    const combinedPath = join(reportsDir, 'index.html');
    combinedReporter.saveToFile(combinedPath);
    console.log(`✅ Generated combined report: ${combinedPath}`);
  }

  console.log('\n🎉 Report generation complete!');
  console.log(`   Open ${join(reportsDir, 'index.html')} to view`);
}

main().catch(console.error);
