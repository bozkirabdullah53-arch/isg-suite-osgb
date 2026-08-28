import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const target = path.resolve(here, '../src/remote_training_clean_manager_bridge.js');
const broken = "if(!b)return,0;";
const fixed = "if(!b)return;";

let source = fs.readFileSync(target, 'utf8');
if (source.includes(broken)) {
  source = source.replace(broken, fixed);
  fs.writeFileSync(target, source, 'utf8');
  console.log('Remote training clean manager syntax hotfix applied.');
} else if (!source.includes(fixed)) {
  throw new Error('Remote training clean manager hotfix target was not found.');
} else {
  console.log('Remote training clean manager syntax is already fixed.');
}

execFileSync(process.execPath, ['--check', target], {stdio: 'inherit'});
