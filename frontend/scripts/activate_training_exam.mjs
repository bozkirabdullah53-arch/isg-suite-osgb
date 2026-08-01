import fs from 'node:fs';
import path from 'node:path';

const jsxPath = path.resolve('src/training.jsx');
let text = fs.readFileSync(jsxPath, 'utf8');

if (!text.includes('onDownloadExam,')) {
  text = text.replace(
    '  onDownloadAttendance,\n  onSaveAndPrepare,',
    '  onDownloadAttendance,\n  onDownloadExam,\n  onSaveAndPrepare,'
  );
}

if (!text.includes("dlBusy === 'exam'")) {
  const marker = `        {ready ? (\n          <button\n            type="button"\n            className="education-output-button education-output-button--attendance"`;
  const insert = `        {ready ? (\n          <button\n            type="button"\n            className="education-output-button education-output-button--exam"\n            disabled={!!dlBusy}\n            onClick={onDownloadExam}\n          >\n            <ShieldCheck size={18} />\n            {dlBusy === 'exam' ? 'Hazırlanıyor…' : 'Sınav Oluştur (15 Soru)'}\n          </button>\n        ) : (\n          <div className="education-output-disabled" aria-disabled="true">\n            Sınav Oluştur (15 Soru)\n          </div>\n        )}\n`;
  text = text.replace(marker, insert + marker);
}

if (!text.includes('async function downloadExam(id)')) {
  const marker = '  async function downloadCertificates(id) {';
  const fn = `  async function downloadExam(id) {\n    setDlBusy('exam');\n    try {\n      await downloadFile(\`/trainings/\${id}/exam.pdf\`, \`egitim-\${id}-isg-sinavi.pdf\`);\n    } catch (x) {\n      setErr('Sınav PDF oluşturulamadı: ' + (x.message || x));\n    } finally {\n      setDlBusy('');\n    }\n  }\n\n`;
  text = text.replace(marker, fn + marker);
}

if (!text.includes('onDownloadExam={() => downloadExam(savedTrainingId)}')) {
  text = text.replace(
    '            onDownloadAttendance={() => downloadAttendance(savedTrainingId)}\n            onSaveAndPrepare=',
    '            onDownloadAttendance={() => downloadAttendance(savedTrainingId)}\n            onDownloadExam={() => downloadExam(savedTrainingId)}\n            onSaveAndPrepare='
  );
}

fs.writeFileSync(jsxPath, text, 'utf8');

const cssPath = path.resolve('src/training_pro.css');
let css = fs.readFileSync(cssPath, 'utf8');
const cssBlock = `\n.training-pro .education-output-button--exam {\n  background: linear-gradient(135deg, #0f766e 0%, #0b2e4f 100%);\n  box-shadow: 0 10px 22px rgba(15, 118, 110, 0.18);\n}\n.training-pro .education-output-row {\n  grid-template-columns: repeat(3, minmax(0, 1fr));\n}\n`;
if (!css.includes('.education-output-button--exam')) css += cssBlock;
fs.writeFileSync(cssPath, css, 'utf8');
console.log('Training exam button activated.');
