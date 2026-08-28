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

// Uzaktan eğitim katalog video yönetimi: yayımlanmış videoyu aktif eğitimden
// kaldırmaya izin ver ve video işleme tamamlanana kadar katalog kartını otomatik
// yenile. Backend eski video/progress kayıtlarını tarihçe için korur.
const remoteJsxPath = path.resolve('src/remote_basic_ohs_training.jsx');
let remoteText = fs.readFileSync(remoteJsxPath, 'utf8');

remoteText = remoteText.replace(
  "if (!canEditContent || !selectedPackage || HISTORICAL_VIDEO_STATUSES.includes(video.status)) return;",
  "if (!canEditContent || !selectedPackage || video.status === 'archived') return;",
);
remoteText = remoteText.replace(
  'if (!window.confirm(`"${video.title}" taslak videosu silinsin mi?`)) return;',
  "const historical = ['published', 'unpublished'].includes(video.status);\n    if (!window.confirm(historical ? `\"${video.title}\" aktif eğitimden kaldırılsın mı? Eski kayıt ve izleme geçmişi korunacaktır.` : `\"${video.title}\" taslak videosu silinsin mi?`)) return;",
);
remoteText = remoteText.replace(
  "setMessage(out.storage_cleanup_pending ? 'Video silindi; depolama temizliği sıraya alındı.' : 'Taslak video silindi.');",
  "setMessage(out.historical_record_preserved ? (out.message || 'Video aktif eğitimden kaldırıldı; eski kayıt ve izleme geçmişi korundu.') : out.storage_cleanup_pending ? 'Video silindi; depolama temizliği sıraya alındı.' : 'Taslak video silindi.');",
);
remoteText = remoteText.replace(
  "directContentEdit && !HISTORICAL_VIDEO_STATUSES.includes(video.status)",
  "directContentEdit && video.status !== 'archived'",
);
remoteText = remoteText.replace(
  '>Taslak videoyu sil</button>',
  ">{['published', 'unpublished'].includes(video.status) ? 'Videoyu sil' : 'Taslak videoyu sil'}</button>",
);

if (!remoteText.includes('remote-catalog-processing-poll')) {
  const pollingMarker = "  useEffect(() => { if (selectedId) loadPackage(selectedId); }, [selectedId]);\n";
  const pollingBlock = `  useEffect(() => {\n    // remote-catalog-processing-poll\n    const hasPendingVideo = (selectedPackage?.sections || []).some((section) =>\n      (section.videos || []).some((video) => ['uploading', 'processing'].includes(video.status)),\n    );\n    if (!selectedId || !hasPendingVideo) return undefined;\n    const timer = window.setTimeout(() => { void loadPackage(selectedId); }, 2500);\n    return () => window.clearTimeout(timer);\n  }, [selectedId, selectedPackage]);\n`;
  remoteText = remoteText.replace(pollingMarker, pollingMarker + pollingBlock);
}

fs.writeFileSync(remoteJsxPath, remoteText, 'utf8');

// Katalog bölüm sıralama köprüsünde sürüklenen kart hedefin yerine DOM'da
// taşındığında drop olayı bazen doğrudan sürüklenen karta düşüyor. Eski kod bu
// durumda dragend aşamasında değişikliği geri alıyordu. Dragend'de DOM sırası
// gerçekten değişmişse aynı güvenli PATCH çağrısını çalıştırarak sıralamayı
// kalıcılaştır; başarılı bir drop zaten state'i temizlediği için iki kez kayıt olmaz.
const reorderBridgePath = path.resolve('src/remote_training_package_management_bridge.js');
let reorderBridgeText = fs.readFileSync(reorderBridgePath, 'utf8');
if (!reorderBridgeText.includes('remote-section-dragend-persist-fallback')) {
  const oldDragEnd = `    handle.addEventListener('dragend', () => {\n      if (draggingSectionRoot && !dragDropCommitted && dragStartSectionContainer && dragStartSectionOrder) {\n        applySectionOrder(dragStartSectionContainer, dragStartSectionOrder);\n      }\n      clearDragState();\n    });`;
  const newDragEnd = `    handle.addEventListener('dragend', () => {\n      // remote-section-dragend-persist-fallback\n      const container = dragStartSectionContainer;\n      const previousOrder = dragStartSectionOrder ? [...dragStartSectionOrder] : [];\n      const nextOrder = container ? sectionOrderFromDom(container) : [];\n      const changed = Boolean(\n        draggingSectionRoot\n        && !dragDropCommitted\n        && container\n        && previousOrder.length\n        && nextOrder.length\n        && previousOrder.join(',') !== nextOrder.join(',')\n      );\n      if (changed) {\n        clearDragState();\n        void persistSectionOrder(detail, container, previousOrder, nextOrder);\n        return;\n      }\n      if (draggingSectionRoot && !dragDropCommitted && container && previousOrder.length) {\n        applySectionOrder(container, previousOrder);\n      }\n      clearDragState();\n    });`;
  if (!reorderBridgeText.includes(oldDragEnd)) {
    throw new Error('Remote training section dragend block was not found; build stopped to avoid an unsafe partial patch.');
  }
  reorderBridgeText = reorderBridgeText.replace(oldDragEnd, newDragEnd);
  fs.writeFileSync(reorderBridgePath, reorderBridgeText, 'utf8');
}

console.log('Training exam button and remote-training video controls activated.');