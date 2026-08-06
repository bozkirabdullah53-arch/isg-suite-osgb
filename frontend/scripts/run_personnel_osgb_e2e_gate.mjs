import {spawnSync} from 'node:child_process';

const serviceName = String(process.env.RENDER_SERVICE_NAME || '').trim();
const branch = String(process.env.RENDER_GIT_BRANCH || '').trim();
const isStaging = serviceName === 'isg-suite-web-staging' || branch === 'staging';

if (!isStaging) {
  console.log('OSGB professional card Playwright gate skipped outside staging.');
  process.exit(0);
}

function run(command, args) {
  const result = spawnSync(command, args, {
    stdio: 'inherit',
    shell: process.platform === 'win32',
    env: process.env,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status || 1);
}

console.log('Installing Chromium in the staging build user cache...');
run('npx', ['playwright', 'install', 'chromium']);
console.log('Running serialized OSGB-only desktop, mobile and document browser regressions...');
run('npx', [
  'playwright',
  'test',
  '--workers=1',
  '--reporter=list',
  'e2e/personnel-profile-sidebar.spec.js',
  'e2e/personnel-profile-documents.spec.js',
]);
