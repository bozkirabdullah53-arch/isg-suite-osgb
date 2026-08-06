import {readFileSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const target = fileURLToPath(new URL('../src/personnel_profile_readonly_bridge.js', import.meta.url));
let source = readFileSync(target, 'utf8');
let changed = false;

const patches = [
  {
    before: "let attaching = false;",
    after: "let attaching = false;\nlet attachPending = false;",
  },
  {
    before: "async function attach() {\n  if (attaching) return;\n  attaching = true;",
    after: "async function attach() {\n  if (attaching) {\n    attachPending = true;\n    return;\n  }\n  attaching = true;",
  },
  {
    before: "  } finally {\n    attaching = false;\n  }\n}",
    after: "  } finally {\n    attaching = false;\n    if (attachPending) {\n      attachPending = false;\n      scheduleAttach();\n    }\n  }\n}",
  },
];

for (const {before, after} of patches) {
  if (source.includes(after)) continue;
  if (!source.includes(before)) {
    throw new Error(`Personnel profile attach race patch target not found: ${before.split('\n')[0]}`);
  }
  source = source.replace(before, after);
  changed = true;
}

if (changed) {
  writeFileSync(target, source, 'utf8');
  console.log('Personnel profile attach pending-rerun guard applied.');
} else {
  console.log('Personnel profile attach pending-rerun guard already present.');
}
