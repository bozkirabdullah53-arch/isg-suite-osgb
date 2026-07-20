import React from 'react';
import {X} from 'lucide-react';

/** Belgelerin yürürlük / revizyon tarihi */
export const LEGAL_DOCS_VERSION = '20.07.2026';
export const LEGAL_PROVIDER = 'EİSA PROGRAMLAMA';
export const LEGAL_PRODUCT = 'İSG Suite';

/**
 * OSGB Başvuru — Hizmet ve Kullanım Sözleşmesi
 * (SaaS abonelik / platform kullanımı; 6331 kapsamındaki yasal yükümlülükler OSGB’de kalır.)
 */
export const SERVICE_AGREEMENT = {
  id: 'service-agreement',
  title: 'İSG Suite Hizmet ve Kullanım Sözleşmesi',
  shortTitle: 'Hizmet Sözleşmesi',
  version: LEGAL_DOCS_VERSION,
  sections: [
    {
      heading: '1. Taraflar',
      body: `${LEGAL_PROVIDER} (“Sağlayıcı”), ${LEGAL_PRODUCT} yazılım platformunu (“Platform”) bulut hizmeti (SaaS) olarak sunar. Başvuru formunu dolduran ve onaylayan OSGB / işletme (“Müşteri”), Platform’a erişim ve kullanım talebinde bulunur. Bu Sözleşme, başvuru onayı ve deneme süresinin başlaması ile birlikte taraflar arasında bağlayıcı hale gelir.`,
    },
    {
      heading: '2. Konu ve kapsam',
      body: `Bu Sözleşme’nin konusu; Müşteri’nin İş Sağlığı ve Güvenliği süreçlerini dijital ortamda planlaması, takip etmesi ve belgelendirmesine yardımcı olmak üzere Platform’un sağlanmasıdır. Platform; işyeri / görevlendirme / saha ziyareti / performans ve benzeri operasyonel kayıtların tutulmasına imkân tanır. Platform bir danışmanlık, denetim veya resmi belge onay hizmeti değildir; resmi mercilere sunulacak belgelerin doğruluğu, zamanında hazırlanması ve yasal uygunluğu Müşteri’nin sorumluluğundadır.`,
    },
    {
      heading: '3. Başvuru, deneme ve abonelik',
      body: `Müşteri, başvuru formunda verdiği bilgilerin doğru ve güncel olduğunu beyan eder. Sağlayıcı başvuruyu inceler; uygun bulması hâlinde Müşteri’ye yönetici hesabı açılır ve on (10) günlük deneme süresi başlar. Deneme süresi sonunda abonelik/paket koşulları ayrıca bildirilir veya mevcut paket üzerinden devam edilir. Deneme veya abonelik süresi içinde Müşteri, Platform’u yalnızca kendi OSGB faaliyetleri kapsamında kullanabilir.`,
    },
    {
      heading: '4. Müşteri’nin yükümlülükleri',
      body: `Müşteri; (a) kullanıcı hesaplarını yetkili personelle sınırlı tutmayı, (b) şifre ve erişim bilgilerini gizli tutmayı, (c) Platform’a yüklenen / girilen verilerin doğruluğunu sağlamayı, (d) 6331 sayılı İş Sağlığı ve Güvenliği Kanunu ile ilgili mevzuattan doğan yükümlülüklerini Platform kullanımına rağmen kendi bünyesinde yerine getirmeyi, (e) üçüncü kişilerin (müşteri işyerleri, çalışanlar, profesyoneller) kişisel verilerini mevzuata uygun işlemeyi, (f) Platform’u kötüye kullanmamayı, tersine mühendislik yapmamayı ve yetkisiz erişim denememeyi kabul eder.`,
    },
    {
      heading: '5. Sağlayıcı’nın yükümlülükleri',
      body: `Sağlayıcı; Platform’u makul özenle işletmeyi, makul ölçüde erişilebilir tutmayı, güvenlik ve yedekleme konusunda sektörel iyi uygulamaları gözetmeyi, abonelik kapsamında tanımlanan destek kanallarını sunmayı taahhüt eder. Planlı bakım, mücbir sebep, üçüncü taraf altyapı (barındırma, ağ) kesintileri nedeniyle oluşabilecek geçici erişim kısıtlarından Sağlayıcı, kusuru olmadığı ölçüde sorumlu tutulamaz.`,
    },
    {
      heading: '6. Veri, gizlilik ve KVKK',
      body: `Müşteri hesabı ve başvuru bilgileri bakımından Sağlayıcı, ilgili mevzuat çerçevesinde veri sorumlusu veya işleyen sıfatıyla hareket edebilir. Müşteri’nin Platform’a girdiği üçüncü kişi verileri (çalışan, işyeri, profesyonel vb.) bakımından Müşteri veri sorumlusudur; Sağlayıcı, bu verileri yalnızca hizmetin sunulması amacıyla ve Müşteri’nin talimatları doğrultusunda işler. Ayrıntılar “Kişisel Verilerin Korunması Aydınlatma Metni”nde yer alır. Taraflar, birbirinden öğrendikleri ticari sırları izinsiz üçüncü kişilere açıklamaz.`,
    },
    {
      heading: '7. Fikri mülkiyet',
      body: `Platform’un yazılımı, arayüzü, dokümantasyonu, markası ve içerik tasarımı Sağlayıcı’ya aittir. Müşteri’ye yalnızca abonelik süresiyle sınırlı, devredilemez, münhasır olmayan bir kullanım hakkı tanınır. Müşteri’nin Platform’a girdiği kendi verilerinin mülkiyeti Müşteri’de kalır; hizmet sona erdiğinde makul süre içinde dışa aktarma imkânı sunulmaya çalışılır.`,
    },
    {
      heading: '8. Sorumluluk sınırı',
      body: `Platform bir yönetim aracıdır; İş Sağlığı ve Güvenliği mevzuatına uyum, resmi bildirim, risk değerlendirmesi, eğitim, sağlık gözetimi ve benzeri yasal yükümlülüklerin yerine getirilmesinden doğan sonuçlar Müşteri’ye aittir. Sağlayıcı; dolaylı zarar, kâr kaybı, veri kaybı (yedekleme dışında kalan Müşteri kaynaklı kayıplar), idari para cezası veya üçüncü kişi taleplerinden, kanunen zorunlu haller dışında sorumlu değildir. Her hâlükârda Sağlayıcı’nın toplam sorumluluğu, olaydan önceki on iki (12) ayda Müşteri’nin Platform için ödediği bedelle sınırlıdır (deneme döneminde bedel yoksa makul bir üst sınır uygulanır).`,
    },
    {
      heading: '9. Askıya alma ve fesih',
      body: `Müşteri Sözleşme’yi ihlal ederse, güvenlik riski oluşursa veya ödeme yükümlülüğü yerine getirilmezse Sağlayıcı erişimi geçici olarak askıya alabilir. Taraflardan her biri, yazılı bildirimle aboneliği sona erdirebilir; yürürlükteki paket koşullarında belirtilen ihbar süreleri saklıdır. Fesih, doğmuş alacak ve gizlilik yükümlülüklerini ortadan kaldırmaz.`,
    },
    {
      heading: '10. Uygulanacak hukuk ve yetki',
      body: `Bu Sözleşme Türkiye Cumhuriyeti hukukuna tabidir. Uyuşmazlıklarda öncelikle iyi niyetle müzakere edilir; çözülemezse İstanbul (Çağlayan) mahkemeleri ve icra daireleri yetkilidir.`,
    },
    {
      heading: '11. Yürürlük',
      body: `Müşteri, başvuru formunda “Sözleşmeyi kabul ediyorum” seçeneğini işaretleyerek bu metni okuduğunu, anladığını ve kabul ettiğini beyan eder. Sağlayıcı, metni güncelleyebilir; önemli değişiklikler Müşteri’ye Platform veya e-posta yoluyla duyurulur. Revizyon tarihi: ${LEGAL_DOCS_VERSION}.`,
    },
  ],
};

/**
 * KVKK Aydınlatma Metni (6698 sayılı Kanun)
 */
export const PRIVACY_NOTICE = {
  id: 'privacy-kvkk',
  title: 'Kişisel Verilerin Korunması Aydınlatma Metni',
  shortTitle: 'KVKK Aydınlatma Metni',
  version: LEGAL_DOCS_VERSION,
  sections: [
    {
      heading: '1. Veri sorumlusu',
      body: `${LEGAL_PROVIDER} (“Şirket”), ${LEGAL_PRODUCT} platformu kapsamında OSGB başvurusu ve hesap yönetimi süreçlerinde kişisel verilerinizi 6698 sayılı Kişisel Verilerin Korunması Kanunu (“KVKK”) uyarınca işlemektedir. İletişim: Platform üzerindeki destek / bildirim kanalları ve başvuru formunda belirtilen e-posta adresi.`,
    },
    {
      heading: '2. İşlenen kişisel veriler',
      body: `Başvuru ve hesap süreçlerinde; kimlik (ad soyad), iletişim (e-posta, telefon, adres), iş / kurum bilgileri (OSGB unvanı, yetki no, vergi no, sorumlu müdür), işlem güvenliği (IP, oturum, log) ve başvuru notları işlenebilir. Platform kullanımı sırasında Müşteri tarafından girilen çalışan / işyeri / profesyonel verileri, Müşteri’nin talimatı ve sorumluluğu altında barındırılır.`,
    },
    {
      heading: '3. İşleme amaçları ve hukuki sebepler',
      body: `Verileriniz; başvurunun değerlendirilmesi, sözleşme kurulması ve ifası, deneme / abonelik yönetimi, kimlik doğrulama, destek, faturalama, bilgi güvenliği, yasal yükümlülüklerin yerine getirilmesi ve meşru menfaat kapsamında (dolandırıcılığın önlenmesi, hizmet kalitesi) işlenir. Hukuki sebepler: KVKK m.5/2 (sözleşmenin kurulması-ifası, hukuki yükümlülük, meşru menfaat) ve gerektiğinde açık rıza.`,
    },
    {
      heading: '4. Aktarım',
      body: `Verileriniz; barındırma / e-posta / güvenlik altyapısı sağlayan iş ortaklarına (yurt içi veya yeterli koruma / taahhütname ile yurt dışı), zorunlu hallerde yetkili kamu kurumlarına ve hukuki danışmanlara aktarılabilir. Aktarımlarda KVKK’nın aktarım hükümlerine uyulur.`,
    },
    {
      heading: '5. Saklama süresi',
      body: `Başvuru ve hesap verileri; ilişkinin devamı süresince ve sonrasında mevzuattaki zamanaşımı / saklama süreleri (ticari defter, uyuşmazlık, güvenlik logları vb.) kadar saklanır; süre bitiminde silinir, yok edilir veya anonim hale getirilir.`,
    },
    {
      heading: '6. Haklarınız',
      body: `KVKK m.11 kapsamında; verilerinizin işlenip işlenmediğini öğrenme, bilgi talep etme, düzeltme, silme / yok etme, aktarılan üçüncü kişilere bildirilmesini isteme, itiraz ve zararın giderilmesini talep etme haklarına sahipsiniz. Taleplerinizi kimliğinizi doğrulayacak şekilde Şirket’e iletebilirsiniz. Şikâyet hakkınız için Kişisel Verileri Koruma Kurulu’na başvurabilirsiniz.`,
    },
    {
      heading: '7. Onayın anlamı',
      body: `Başvuru formunda “Kişisel verilerimin korunmasını kabul ediyorum” seçeneğini işaretlemeniz; bu Aydınlatma Metni’ni okuduğunuzu ve başvuru / hesap süreçlerindeki işleme faaliyetleri hakkında bilgilendirildiğinizi gösterir. Revizyon tarihi: ${LEGAL_DOCS_VERSION}.`,
    },
  ],
};

export function LegalDocBody({doc}) {
  if (!doc) return null;
  return (
    <div className="legal-doc-body">
      <header style={{marginBottom: 16}}>
        <h3 style={{margin: '0 0 6px', fontSize: 18}}>{doc.title}</h3>
        <p style={{margin: 0, color: '#64748b', fontSize: 13}}>
          {LEGAL_PROVIDER} · {LEGAL_PRODUCT} · Revizyon: {doc.version}
        </p>
      </header>
      {doc.sections.map((s) => (
        <section key={s.heading} style={{marginBottom: 16}}>
          <h4 style={{margin: '0 0 6px', fontSize: 14, color: '#0f766e'}}>{s.heading}</h4>
          <p style={{margin: 0, fontSize: 13.5, lineHeight: 1.65, color: '#334155', whiteSpace: 'pre-wrap'}}>
            {s.body}
          </p>
        </section>
      ))}
      <p style={{marginTop: 20, fontSize: 12, color: '#94a3b8'}}>
        Bu metin bilgilendirme ve sözleşme amaçlıdır; özel durumlarınız için hukuki danışmanlık almanız önerilir.
      </p>
    </div>
  );
}

export function LegalDocModal({doc, onClose}) {
  if (!doc) return null;
  return (
    <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <section
        className="modal"
        style={{maxWidth: 720, width: '94vw', maxHeight: '88vh', display: 'flex', flexDirection: 'column'}}
      >
        <header style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12}}>
          <h3 style={{margin: 0}}>{doc.shortTitle || doc.title}</h3>
          <button type="button" className="icon" onClick={onClose} aria-label="Kapat"><X size={18} /></button>
        </header>
        <div style={{overflow: 'auto', padding: '4px 2px 12px', flex: 1}}>
          <LegalDocBody doc={doc} />
        </div>
        <div className="form-actions" style={{borderTop: '1px solid #e2e8f0', paddingTop: 12}}>
          <button type="button" onClick={onClose}>Okudum, kapat</button>
        </div>
      </section>
    </div>
  );
}
