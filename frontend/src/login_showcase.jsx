import React, {useEffect, useRef, useState} from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BarChart3,
  BellRing,
  BookOpenCheck,
  CheckCircle2,
  ClipboardCheck,
  CloudCog,
  Clock3,
  HeartPulse,
  Layers3,
  ShieldCheck,
} from 'lucide-react';
import './login_showcase.css';

const ROTATION_MS = 6500;
const INTERACTION_PAUSE_MS = 10000;

export const LOGIN_SHOWCASE_SLIDES = [
  {
    eyebrow: 'TEK MERKEZDEN YÖNETİM',
    title: 'Tüm İSG süreçleri tek platformda',
    description: 'Risk, eğitim, sağlık, doküman ve saha süreçlerini dağınıklıktan kurtarın; işyerinizin güncel durumunu tek ekrandan yönetin.',
    Icon: Layers3,
    metric: '10+ süreç',
    metricLabel: 'birbiriyle bağlantılı',
    tone: 'teal',
  },
  {
    eyebrow: 'ÖNLEYİCİ GÜVENLİK',
    title: 'Kazadan önce riski görün',
    description: 'Tehlikeleri kayıt altına alın, risk seviyelerini izleyin ve önleyici faaliyetleri doğru zamanda devreye alın.',
    Icon: ShieldCheck,
    metric: '5×5',
    metricLabel: 'izlenebilir risk matrisi',
    tone: 'cyan',
  },
  {
    eyebrow: 'EĞİTİM YÖNETİMİ',
    title: 'Eğitim takibini sadeleştirin',
    description: 'Katılım, sınav, sertifika ve yenileme tarihlerini çalışan bazında yönetin; eksikleri saniyeler içinde görün.',
    Icon: BookOpenCheck,
    metric: '%100',
    metricLabel: 'belgeli eğitim takibi',
    tone: 'green',
  },
  {
    eyebrow: 'OLAY VE RAMAK KALA',
    title: 'Her olaydan kurumsal öğrenme üretin',
    description: 'Kaza ve ramak kala kayıtlarını kök neden analiziyle değerlendirin, benzer olayların tekrarını önleyin.',
    Icon: AlertTriangle,
    metric: '7/24',
    metricLabel: 'olay kayıt disiplini',
    tone: 'amber',
  },
  {
    eyebrow: 'DÖF / CAPA KONTROLÜ',
    title: 'Düzeltici faaliyetleri sonuca ulaştırın',
    description: 'Sorumlu, termin, kanıt ve kapanış durumlarını birlikte takip edin; açık işleri gözden kaçırmayın.',
    Icon: ClipboardCheck,
    metric: 'Tek akış',
    metricLabel: 'sorumludan kapanışa',
    tone: 'blue',
  },
  {
    eyebrow: 'SAĞLIK GÖZETİMİ',
    title: 'Muayene tarihlerini düzen içinde yönetin',
    description: 'İşe giriş ve periyodik muayeneleri yetki seviyelerine uygun izleyin; yaklaşan kontrolleri zamanında planlayın.',
    Icon: HeartPulse,
    metric: 'Gizli',
    metricLabel: 'rol bazlı sağlık erişimi',
    tone: 'rose',
  },
  {
    eyebrow: 'AKILLI HATIRLATMALAR',
    title: 'Kritik tarihleri sistem takip etsin',
    description: 'Eğitim, muayene, kontrol ve belge süreleri yaklaşırken bildirim alın; gecikmeleri oluşmadan yönetin.',
    Icon: BellRing,
    metric: '30 gün',
    metricLabel: 'erken uyarı görünümü',
    tone: 'violet',
  },
  {
    eyebrow: 'ANLIK RAPORLAMA',
    title: 'Performansı gerçek verilerle görün',
    description: 'Güncel göstergeler, açık işler ve tamamlanma oranlarıyla İSG performansını anlaşılır panolardan izleyin.',
    Icon: BarChart3,
    metric: 'Canlı',
    metricLabel: 'işyeri durum özeti',
    tone: 'cyan',
  },
  {
    eyebrow: 'GÜVENLİ BULUT ALTYAPISI',
    title: 'Yetkiniz kadar görün, her yerden erişin',
    description: 'Rol ve işyeri bazlı erişimle bilgileri koruyun; masaüstü, tablet ve mobil cihazlardan güvenle çalışın.',
    Icon: CloudCog,
    metric: 'RBAC',
    metricLabel: 'yetki seviyeli erişim',
    tone: 'blue',
  },
  {
    eyebrow: 'DAHA GÜVENLİ İŞYERLERİ',
    title: 'Zamandan kazanın, güvenliği güçlendirin',
    description: 'Tekrarlayan işleri azaltın, ekiplerinizi aynı düzende buluşturun ve sürdürülebilir bir güvenlik kültürü oluşturun.',
    Icon: Clock3,
    metric: 'Daha az',
    metricLabel: 'tekrar ve operasyon yükü',
    tone: 'green',
  },
];

function useReducedMotion() {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined;
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener?.('change', update);
    return () => query.removeEventListener?.('change', update);
  }, []);

  return reduced;
}

function ShowcaseVisual({slide}) {
  const {Icon} = slide;
  return (
    <div className={`login-showcase-visual login-showcase-visual--${slide.tone}`} aria-hidden="true">
      <div className="login-showcase-orbit login-showcase-orbit--outer" />
      <div className="login-showcase-orbit login-showcase-orbit--inner" />
      <div className="login-showcase-icon"><Icon strokeWidth={1.75} /></div>
      <div className="login-showcase-mini login-showcase-mini--top">
        <span /> <span /> <span />
      </div>
      <div className="login-showcase-mini login-showcase-mini--bottom">
        <CheckCircle2 size={14} />
        <span>Güncel</span>
      </div>
    </div>
  );
}

export function LoginShowcase() {
  const [index, setIndex] = useState(0);
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const [interactionPaused, setInteractionPaused] = useState(false);
  const [pageVisible, setPageVisible] = useState(true);
  const [cycle, setCycle] = useState(0);
  const interactionTimer = useRef(null);
  const reducedMotion = useReducedMotion();
  const slide = LOGIN_SHOWCASE_SLIDES[index];
  const paused = hovered || focused || interactionPaused;

  useEffect(() => {
    const update = () => setPageVisible(document.visibilityState !== 'hidden');
    update();
    document.addEventListener('visibilitychange', update);
    return () => document.removeEventListener('visibilitychange', update);
  }, []);

  useEffect(() => {
    if (paused || reducedMotion || !pageVisible) return undefined;
    const timer = window.setTimeout(() => {
      setIndex((current) => (current + 1) % LOGIN_SHOWCASE_SLIDES.length);
      setCycle((current) => current + 1);
    }, ROTATION_MS);
    return () => window.clearTimeout(timer);
  }, [index, paused, reducedMotion, pageVisible, cycle]);

  useEffect(() => () => {
    if (interactionTimer.current) window.clearTimeout(interactionTimer.current);
  }, []);

  function pauseAfterInteraction() {
    setInteractionPaused(true);
    if (interactionTimer.current) window.clearTimeout(interactionTimer.current);
    interactionTimer.current = window.setTimeout(() => setInteractionPaused(false), INTERACTION_PAUSE_MS);
  }

  function goTo(nextIndex) {
    const total = LOGIN_SHOWCASE_SLIDES.length;
    setIndex((nextIndex + total) % total);
    setCycle((current) => current + 1);
    pauseAfterInteraction();
  }

  function handleBlur(event) {
    if (!event.currentTarget.contains(event.relatedTarget)) setFocused(false);
  }

  return (
    <section
      className="login-showcase"
      aria-label="İSG Suite özellikleri"
      onPointerEnter={() => setHovered(true)}
      onPointerLeave={() => setHovered(false)}
      onFocusCapture={() => setFocused(true)}
      onBlurCapture={handleBlur}
    >
      <div className="login-showcase-glow" aria-hidden="true" />
      <div className="login-showcase-frame">
        <div className="login-showcase-topline">
          <span className="login-showcase-product"><span /> İSG Suite</span>
          <span className="login-showcase-count">{String(index + 1).padStart(2, '0')} / {LOGIN_SHOWCASE_SLIDES.length}</span>
        </div>

        <article className="login-showcase-slide" key={`${index}-${cycle}`}>
          <ShowcaseVisual slide={slide} />
          <div className="login-showcase-copy">
            <span className="login-showcase-eyebrow">{slide.eyebrow}</span>
            <h2>{slide.title}</h2>
            <p>{slide.description}</p>
            <div className="login-showcase-metric">
              <strong>{slide.metric}</strong>
              <span>{slide.metricLabel}</span>
            </div>
          </div>
        </article>

        <div className="login-showcase-footer">
          <div className="login-showcase-dots" role="tablist" aria-label="Tanıtım slaytları">
            {LOGIN_SHOWCASE_SLIDES.map((item, dotIndex) => (
              <button
                key={item.title}
                type="button"
                role="tab"
                className={dotIndex === index ? 'is-active' : ''}
                aria-selected={dotIndex === index}
                aria-label={`${dotIndex + 1}. slayt: ${item.title}`}
                onClick={() => goTo(dotIndex)}
              />
            ))}
          </div>
          <div className="login-showcase-controls">
            <button type="button" onClick={() => goTo(index - 1)} aria-label="Önceki özellik">
              <ArrowLeft size={17} />
            </button>
            <button type="button" onClick={() => goTo(index + 1)} aria-label="Sonraki özellik">
              <ArrowRight size={17} />
            </button>
          </div>
        </div>

        <div
          key={`progress-${index}-${cycle}`}
          className={`login-showcase-progress${paused || reducedMotion ? ' is-paused' : ''}`}
          aria-hidden="true"
        />
      </div>
    </section>
  );
}
