import fs from 'node:fs';
import path from 'node:path';

const cssPath = path.resolve('src/training_pro.css');
const importLine = "@import './training_colors.css';";

if (!fs.existsSync(cssPath)) {
  throw new Error(`training_pro.css bulunamadı: ${cssPath}`);
}

let current = fs.readFileSync(cssPath, 'utf8');

// Eski hatalı yerleşimi temizle. Override dosyası CSS'in en sonunda olmalı;
// aksi halde training_pro.css içindeki sarı kurallar yeniden baskın gelir.
current = current
  .split('\n')
  .filter((line) => line.trim() !== importLine)
  .join('\n')
  .trimEnd();

fs.writeFileSync(cssPath, `${current}\n\n${importLine}\n`, 'utf8');
console.log('Eğitim lacivert-yeşil tema override dosyası CSS sonuna bağlandı.');
