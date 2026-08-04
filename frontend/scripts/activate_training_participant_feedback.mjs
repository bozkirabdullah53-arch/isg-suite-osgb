import fs from 'node:fs';

const path = 'src/training.jsx';
let text = fs.readFileSync(path, 'utf8');

const oldBlock = `              <button
                type="button"
                className="btn-outline-premium"
                disabled={busy}
                onClick={applyCheckedEmployees}
              >
                <Users size={18} style={{verticalAlign: -3, marginRight: 6}} />
                Seçilen Personelleri Eğitime Ekle
              </button>
              <div className="tp-help" style={{textAlign: 'center'}}>
                PC seçeneği Excel/CSV dosyasını okur. Ortak Personel seçeneği yalnızca yukarıda
                işaretlediğiniz çalışanları kullanır; tüm liste için «Tümünü Seç».
              </div>`;

const newBlock = `              <button
                type="button"
                className="btn-outline-premium"
                disabled={busy}
                onClick={applyCheckedEmployees}
              >
                <Users size={18} style={{verticalAlign: -3, marginRight: 6}} />
                Seçilen Personelleri Eğitime Ekle
              </button>
              {excelInfo && excelPreview.length === 0 && /ortak personel/i.test(excelInfo) && (
                <div
                  role="status"
                  aria-live="polite"
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 10,
                    padding: '12px 14px',
                    border: '1px solid #86efac',
                    borderRadius: 12,
                    background: '#f0fdf4',
                    color: '#166534',
                  }}
                >
                  <CheckCircle2 size={20} style={{flex: '0 0 auto', marginTop: 1}} />
                  <div>
                    <strong style={{display: 'block'}}>{excelInfo}</strong>
                    <span style={{fontSize: 13}}>
                      Seçim eğitim formuna aktarıldı. Kalıcı kayıt ve PDF için aşağıdaki
                      «Eğitimi Kaydet ve PDF Hazırla» düğmesine basın.
                    </span>
                  </div>
                </div>
              )}
              <div className="tp-help" style={{textAlign: 'center'}}>
                PC seçeneği Excel/CSV dosyasını okur. Ortak Personel seçeneği yalnızca yukarıda
                işaretlediğiniz çalışanları kullanır; tüm liste için «Tümünü Seç».
              </div>`;

if (!text.includes(newBlock)) {
  if (!text.includes(oldBlock)) {
    throw new Error('Participant action block not found');
  }
  text = text.replace(oldBlock, newBlock);
}

fs.writeFileSync(path, text, 'utf8');
console.log('Inline participant selection feedback activated.');
