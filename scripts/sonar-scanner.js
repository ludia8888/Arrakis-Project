#!/usr/bin/env node

const scanner = require('sonarqube-scanner').default;
const path = require('path');

// Load environment variables
require('dotenv').config();

const serverUrl = process.env.SONAR_HOST_URL || 'http://localhost:9000';
const token = process.env.SONAR_TOKEN;

if (!token) {
  console.error('❌ SONAR_TOKEN is not set in environment variables');
  console.error('   Please set it in your .env file or export it');
  process.exit(1);
}

console.log('🚀 Starting SonarQube analysis...');
console.log(`   Server: ${serverUrl}`);
console.log(`   Project: arrakis-project`);

scanner(
  {
    serverUrl,
    token,
    options: {
      'sonar.projectKey': 'arrakis-project',
      'sonar.projectName': 'Arrakis Project',
      'sonar.projectVersion': '1.0.0',
      'sonar.sources': 'packages/backend/src,packages/frontend/src,packages/shared/src,packages/contracts/src',
      'sonar.exclusions': '**/*.test.ts,**/*.test.tsx,**/*.spec.ts,**/__tests__/**,**/node_modules/**,**/dist/**,**/coverage/**,**/*.d.ts,**/migrations/**',
      'sonar.tests': 'packages/backend/src,packages/frontend/src,packages/shared/src',
      'sonar.test.inclusions': '**/*.test.ts,**/*.test.tsx,**/*.spec.ts,**/__tests__/**',
      'sonar.javascript.lcov.reportPaths': 'packages/backend/coverage/lcov.info,packages/frontend/coverage/lcov.info,packages/shared/coverage/lcov.info',
      'sonar.typescript.tsconfigPath': 'tsconfig.json',
      'sonar.sourceEncoding': 'UTF-8',
      'sonar.scm.provider': 'git',
    },
  },
  () => {
    console.log('✅ SonarQube analysis completed');
    console.log(`📊 View results at: ${serverUrl}/dashboard?id=arrakis-project`);
  },
  (error) => {
    console.error('❌ SonarQube analysis failed:', error);
    process.exit(1);
  }
);