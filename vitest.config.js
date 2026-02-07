import { defineConfig } from 'vitest/config';
import { config } from 'dotenv';

// Load .env file
config();

export default defineConfig({
  test: {
    environment: 'node',
    include: ['agent/__tests__/**/*.test.js'],
    globals: true,
    setupFiles: ['agent/__tests__/setup.js'],
    reporters: ['verbose'],
    testTimeout: 30000, // Increased for API calls
    // Output directory for custom reports
    outputFile: {
      json: 'test-reports/results.json'
    },
    // Make env vars available
    env: {
      GOOGLE_API_KEY: process.env.GOOGLE_API_KEY
    }
  }
});
