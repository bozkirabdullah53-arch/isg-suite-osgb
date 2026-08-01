import fs from 'node:fs';
import path from 'node:path';

const cssPath = path.resolve('src/training_pro.css');
const importLine = "@import './training_colors.css';";

if (!fs.existsSync(cssPath)) {
  throw new Error(`training_pro.css bulunamadı: ${cssPath}`);
}

const current = fs.readFileSync(cssPath, 'utf8');
if (!current.includes(importLine)) {
  fs.writeFileSync(cssPath, `${importLine}\n${current}`, 'utf8');
  console.log('Eğitim lacivert-yeşil tema override dosyası bağlandı.');
} else {
  console.log('Eğitim tema override dosyası zaten bağlı.');
}
