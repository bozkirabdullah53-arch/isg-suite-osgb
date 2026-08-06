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
// Render static-site builds do not allow the root/su step used by --with-deps.
// Install the browser binary only; missing runtime libraries still fail the actual
// Playwright launch below, so the browser regression gate remains fail-closed.
run('npx', ['playwright', 'install', 'chromium']);
console.log('Running OSGB-only desktop, mobile and document browser regressions...');
run('npx', [
  'playwright',
  'test',
  'e2e/personnel-profile-sidebar.spec.js',
  'e2e/personnel-profile-documents.spec.js',
]);
