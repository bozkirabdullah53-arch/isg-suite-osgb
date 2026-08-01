import fs from 'node:fs';
import path from 'node:path';

const cssPath = path.resolve('src/training_pro.css');
const themePath = path.resolve('src/training_colors.css');
const startMarker = '/* TRAINING_COLOR_THEME_START */';
const endMarker = '/* TRAINING_COLOR_THEME_END */';

if (!fs.existsSync(cssPath)) {
  throw new Error(`training_pro.css bulunamadı: ${cssPath}`);
}
if (!fs.existsSync(themePath)) {
  throw new Error(`training_colors.css bulunamadı: ${themePath}`);
}

let current = fs.readFileSync(cssPath, 'utf8');
const theme = fs.readFileSync(themePath, 'utf8').trim();

// Önceki buildlerden kalan @import veya gömülü tema bloğunu temizle.
current = current
  .split('\n')
  .filter((line) => line.trim() !== "@import './training_colors.css';")
  .join('\n');

const start = current.indexOf(startMarker);
const end = current.indexOf(endMarker);
if (start !== -1 && end !== -1 && end > start) {
  current = `${current.slice(0, start)}${current.slice(end + endMarker.length)}`;
}

// @import dosyanın sonunda geçersiz sayılabildiği için kuralları doğrudan sona ekle.
const output = `${current.trimEnd()}\n\n${startMarker}\n${theme}\n${endMarker}\n`;
fs.writeFileSync(cssPath, output, 'utf8');
console.log('Eğitim lacivert-yeşil tema kuralları CSS sonuna doğrudan eklendi.');
