import React, {useEffect, useMemo, useRef, useState} from 'react';
import {
  Archive,
  AlertTriangle,
  BarChart3,
  BookOpenCheck,
  CheckCircle2,
  CopyPlus,
  Database,
  FileDown,
  ExternalLink,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Search,
  Send,
  ShieldCheck,
  Target,
  Trash2,
  UploadCloud,
  X,
} from 'lucide-react';
import {api} from './api';
import {
  QUESTION_STATUS,
  SCOPE_LABELS,
  emptyQuestionDraft,
  newScope,
  newSource,
  questionDraftPayload,
  questionToDraft,
  validateQuestionDraft,
} from './training_question_bank_logic.js';
import {
  buildSmartSectorIndex,
  coveragePagination,
  smartCoverageSummary,
  smartReadinessForItem,
} from './training_question_bank_coverage_logic.js';
import './training_question_bank_premium.css';

const STATUS_FILTERS = [
  {value: '', label: 'Tümü'},
  {value: 'draft', label: 'Taslak'},
  {value: 'in_review', label: 'İncelemede'},
  {value: 'published', label: 'Yayımlandı'},
  {value: 'retired', label: 'Kaldırıldı'},
];

const OPTION_KEYS = ['A', 'B', 'C', 'D'];
const HAZARDS = ['Az Tehlikeli', 'Tehlikeli', 'Çok Tehlikeli'];
const COVERAGE_PAGE_SIZE = 50;

function safeDraft(raw) {
  try {
    const parsed = JSON.parse(raw || 'null');
    if (!parsed?.draft) return null;
    return {
      draft: {...emptyQuestionDraft(), ...parsed.draft},
      editingId: Number(parsed.editingId) || null,
    };
  } catch {
    return null;
  }
}

function statusClass(status) {
  return `qb-status qb-status--${status || 'draft'}`;
}

function formatDate(value) {
  if (!value) return '—';
  try {
    return new Intl.DateTimeFormat('tr-TR', {dateStyle: 'medium'}).format(new Date(value));
  } catch {
    return String(value).slice(0, 10);
  }
}

function formatCount(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString('tr-TR') : '—';
}

export function TrainingQuestionBank({user, sectors = []}) {
  const formRef = useRef(null);
  const importInputRef = useRef(null);
  const storageKey = `isg_training_question_draft_v1_${user?.id || 'admin'}`;
  const [questions, setQuestions] = useState([]);
  const [draft, setDraft] = useState(emptyQuestionDraft);
  const [editingId, setEditingId] = useState(null);
  const [draftLoaded, setDraftLoaded] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(false);
  const [actionBusy, setActionBusy] = useState('');
  const [errors, setErrors] = useState([]);
  const [notice, setNotice] = useState('');
  const [coverage, setCoverage] = useState(null);
  const [coverageBusy, setCoverageBusy] = useState(false);
  const [coverageFilter, setCoverageFilter] = useState('all');
  const [coverageQuery, setCoverageQuery] = useState('');
  const [coverageOffset, setCoverageOffset] = useState(0);

  useEffect(() => {
    const saved = safeDraft(localStorage.getItem(storageKey));
    if (saved) {
      setDraft(saved.draft);
      setEditingId(saved.editingId);
      setNotice('Tarayıcıda korunan taslağınız geri yüklendi.');
    }
    setDraftLoaded(true);
  }, [storageKey]);

  useEffect(() => {
    if (!draftLoaded) return;
    try {
      localStorage.setItem(storageKey, JSON.stringify({draft, editingId}));
    } catch {
      /* Tarayıcı depolaması kapalıysa form yine bellekte korunur. */
    }
  }, [draft, editingId, draftLoaded, storageKey]);

  async function loadQuestions() {
    setBusy(true);
    setErrors([]);
    try {
      const rows = await api('/question-bank/questions');
      setQuestions(Array.isArray(rows) ? rows : []);
    } catch (error) {
      setErrors([error.message || 'Soru bankası alınamadı.']);
    } finally {
      setBusy(false);
    }
  }

  async function loadCoverage(filter = coverageFilter, queryValue = coverageQuery, offsetValue = coverageOffset) {
    setCoverageBusy(true);
    try {
      const params = new URLSearchParams({
        status: filter,
        limit: String(COVERAGE_PAGE_SIZE),
        offset: String(Math.max(0, Number(offsetValue) || 0)),
      });
      if (queryValue.trim()) params.set('q', queryValue.trim());
      const report = await api(`/question-bank/coverage?${params.toString()}`);
      setCoverage(report || null);
      setCoverageOffset(Math.max(0, Number(report?.offset ?? offsetValue) || 0));
    } catch (error) {
      setErrors((current) => [...new Set([...current, error.message || 'NACE kapsama raporu alınamadı.'])]);
    } finally {
      setCoverageBusy(false);
    }
  }

  useEffect(() => {
    loadQuestions();
    loadCoverage('all', '', 0);
  }, []);

  const metrics = useMemo(() => {
    const counts = {draft: 0, in_review: 0, published: 0, retired: 0};
    questions.forEach((row) => {
      if (Object.hasOwn(counts, row.status)) counts[row.status] += 1;
    });
    return counts;
  }, [questions]);

  const filteredQuestions = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase('tr');
    return questions.filter((row) => {
      if (statusFilter && row.status !== statusFilter) return false;
      if (!needle) return true;
      const haystack = `${row.question_code || ''} ${row.topic_code || ''} ${row.topic_label || ''} ${row.question_text || ''}`
        .toLocaleLowerCase('tr');
      return haystack.includes(needle);
    });
  }, [questions, query, statusFilter]);

  const smartSectorIndex = useMemo(() => buildSmartSectorIndex(sectors), [sectors]);
  const smartSummary = useMemo(() => smartCoverageSummary(sectors), [sectors]);
  const coveragePage = useMemo(() => coveragePagination(coverage, COVERAGE_PAGE_SIZE), [coverage]);
  const catalogCountsMatch = Number(coverage?.nace_total || 0) > 0
    && smartSummary.catalogCount === Number(coverage?.nace_total || 0);
  const smartReadyCount = catalogCountsMatch ? smartSummary.readyCount : null;
  const smartCoveragePercent = catalogCountsMatch && Number(coverage?.nace_total || 0) > 0
    ? Math.round((smartSummary.readyCount / Number(coverage.nace_total)) * 100)
    : 0;

  function clearDraft({silent = false} = {}) {
    setDraft(emptyQuestionDraft());
    setEditingId(null);
    setErrors([]);
    if (!silent) setNotice('Yeni ve boş bir soru taslağı açıldı.');
    try {
      localStorage.removeItem(storageKey);
    } catch {
      /* ignore */
    }
  }

  function patchDraft(key, value) {
    setDraft((current) => ({...current, [key]: value}));
  }

  function patchOption(key, value) {
    setDraft((current) => ({...current, options: {...current.options, [key]: value}}));
  }

  function patchScope(index, key, value) {
    setDraft((current) => ({
      ...current,
      scopes: current.scopes.map((scope, i) => {
        if (i !== index) return scope;
        if (key === 'type') return newScope(value);
        return {...scope, [key]: value};
      }),
    }));
  }

  function patchSource(index, key, value) {
    setDraft((current) => ({
      ...current,
      sources: current.sources.map((source, i) => (i === index ? {...source, [key]: value} : source)),
    }));
  }

  function downloadImportTemplate() {
    const sample = questionDraftPayload({
      ...emptyQuestionDraft(),
      question_code: 'ORNEK-SIL-001',
      topic_code: 'KONU-KODU',
      topic_label: 'Konu adı',
      question_text: 'Bu örnek satırı silip açık ve tek anlamlı soru metnini yazın.',
      options: {A: 'Doğru seçenek', B: 'Yanlış seçenek 1', C: 'Yanlış seçenek 2', D: 'Yanlış seçenek 3'},
      answer_explanation: 'Doğru cevabın mevzuata ve güvenli uygulamaya dayanan gerekçesini yazın.',
      scopes: [{type: 'nace', value: '30.11'}],
      sources: [{
        title: 'Resmî kaynak adı',
        url: 'https://www.resmigazete.gov.tr/',
        reference: 'Madde / bölüm',
        effective_date: '',
      }],
    });
    const blob = new Blob([JSON.stringify({items: [sample]}, null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'isg-soru-bankasi-sablonu.json';
    link.click();
    URL.revokeObjectURL(url);
  }

  async function importQuestionFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setErrors([]);
    setNotice('');
    try {
      if (file.size > 3 * 1024 * 1024) throw new Error('İçe aktarma dosyası en fazla 3 MB olabilir.');
      const parsed = JSON.parse(await file.text());
      const items = Array.isArray(parsed) ? parsed : parsed?.items;
      if (!Array.isArray(items) || items.length < 1 || items.length > 500) {
        throw new Error('Dosya 1–500 soru içeren bir JSON listesi olmalıdır.');
      }
      if (!window.confirm(`${items.length} soru yalnız taslak olarak içe aktarılacak. Devam edilsin mi?`)) return;
      setActionBusy('import');
      const result = await api('/question-bank/imports/questions', {
        method: 'POST',
        body: JSON.stringify({items}),
      });
      setNotice(`${result.created} soru taslak olarak içe aktarıldı. Hiçbiri otomatik yayımlanmadı.`);
      await loadQuestions();
    } catch (error) {
      setErrors([error.message || 'Soru dosyası içe aktarılamadı. Mevcut sorular değiştirilmedi.']);
    } finally {
      setActionBusy('');
      if (importInputRef.current) importInputRef.current.value = '';
    }
  }

  function editQuestion(row, nextVersion = false) {
    setDraft(questionToDraft(row, {nextVersion}));
    setEditingId(nextVersion ? null : row.id);
    setErrors([]);
    setNotice(
      nextVersion
        ? `${row.question_code} için ${Number(row.version) + 1}. sürüm taslağı açıldı.`
        : `${row.question_code} düzenleme formuna alındı. Kaydettiğinizde durum yeniden “Taslak” olur.`,
    );
    requestAnimationFrame(() => formRef.current?.scrollIntoView({behavior: 'smooth', block: 'start'}));
  }

  async function saveQuestion(event) {
    event.preventDefault();
    setNotice('');
    const found = validateQuestionDraft(draft);
    if (found.length) {
      setErrors(found);
      return;
    }
    setActionBusy('save');
    setErrors([]);
    try {
      const payload = questionDraftPayload(draft);
      if (editingId) {
        delete payload.question_code;
        delete payload.version;
      } else {
        delete payload.reviewer_note;
      }
      const row = await api(
        editingId ? `/question-bank/questions/${editingId}` : '/question-bank/questions',
        {
          method: editingId ? 'PATCH' : 'POST',
          body: JSON.stringify(payload),
        },
      );
      clearDraft({silent: true});
      setNotice(`${row.question_code} sürüm ${row.version} taslak olarak güvenle kaydedildi.`);
      await loadQuestions();
    } catch (error) {
      setErrors([error.message || 'Soru kaydedilemedi. Girdiğiniz bilgiler silinmedi.']);
    } finally {
      setActionBusy('');
    }
  }

  async function runAction(row, action) {
    const labels = {
      submit: 'incelemeye gönderildi',
      publish: 'yayımlandı',
      retire: 'kullanımdan kaldırıldı',
    };
    if (action === 'publish' && !window.confirm('Bu soruyu onaylayıp sınav havuzunda yayımlamak istiyor musunuz?')) return;
    if (action === 'retire' && !window.confirm('Bu soru yeni sınavlarda kullanılmayacak. Devam edilsin mi?')) return;
    setActionBusy(`${action}-${row.id}`);
    setErrors([]);
    setNotice('');
    try {
      const updated = await api(`/question-bank/questions/${row.id}/${action}`, {method: 'POST'});
      setNotice(`${updated.question_code} ${labels[action]}.`);
      await loadQuestions();
      await loadCoverage();
    } catch (error) {
      setErrors([error.message || 'İşlem tamamlanamadı.']);
    } finally {
      setActionBusy('');
    }
  }

  return (
    <div className="question-bank" aria-label="Eğitim soru bankası yönetimi">
      <section className="qb-hero">
        <div>
          <div className="hero-chip"><ShieldCheck size={15} /> Denetlenebilir içerik + akıllı soru üretimi</div>
          <h1>İSG soru bankası ve akıllı sınav motoru</h1>
          <p>
            Yönetilen sorular editoryal onay akışında korunur. Sınav motoru doğrulanmış NACE ve işe özgü eğitim
            konularına göre gerekli sektörel soruları otomatik tamamlayabilir.
          </p>
          <div className="qb-hero-actions">
            <button type="button" onClick={downloadImportTemplate}><FileDown size={16} /> JSON şablonu</button>
            <button type="button" onClick={() => importInputRef.current?.click()} disabled={!!actionBusy}>
              <UploadCloud size={16} /> {actionBusy === 'import' ? 'İçe aktarılıyor…' : 'Toplu taslak yükle'}
            </button>
            <input ref={importInputRef} type="file" accept="application/json,.json" hidden
              onChange={importQuestionFile} />
          </div>
        </div>
        <div className="qb-hero-mark" aria-hidden="true"><Database size={38} /></div>
      </section>

      <section className="qb-metrics" aria-label="Soru bankası özeti">
        {[
          ['draft', 'Taslak', metrics.draft],
          ['in_review', 'İncelemede', metrics.in_review],
          ['published', 'Yayımlanmış', metrics.published],
          ['retired', 'Kaldırılmış', metrics.retired],
        ].map(([key, label, value]) => (
          <div className="qb-metric" key={key}>
            <span className={statusClass(key)}>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </section>

      <section className="panel-card qb-coverage qb-smart-coverage" aria-label="NACE akıllı soru kapsamı">
        <div className="qb-card-head">
          <div>
            <div className="section-title">Akıllı sınav motoru</div>
            <h2>{formatCount(coverage?.nace_total)} NACE için otomatik soru kapsaması</h2>
            <p className="tp-help">
              Yönetilen soru bankası ile sınav anındaki exact-NACE üretimi birlikte izlenir. Yönetilen havuz az
              olduğunda doğrulanmış NACE ve 5 işe özgü konu üzerinden 15 sektörel soru otomatik üretilebilir.
            </p>
          </div>
          <button type="button" className="qb-icon-button" onClick={() => loadCoverage()} disabled={coverageBusy}
            title="Kapsama raporunu yenile">
            <RefreshCw size={18} className={coverageBusy ? 'qb-spin' : ''} />
          </button>
        </div>

        <div className="qb-smart-engine" role="status" aria-live="polite">
          <div className="qb-smart-engine-icon"><ShieldCheck size={23} /></div>
          <div className="qb-smart-engine-copy">
            <span className="qb-smart-engine-kicker">Exact-NACE otomatik tamamlama</span>
            <strong>Soru sayısı düşük diye eğitim akışı durmaz; uygun NACE kaydında akıllı motor devreye girer.</strong>
            <p>
              Motor 5 sabit temel soruya ek olarak doğrulanmış NACE ve eğitimde dondurulmuş 5 işyeri konusundan
              15 işe özgü soru üretir. Editoryal soru bankası ise ayrıca denetlenebilir biçimde büyümeye devam eder.
            </p>
          </div>
          <div className="qb-smart-engine-badges">
            <span className="qb-smart-badge qb-smart-badge--success"><CheckCircle2 size={14} /> Otomatik motor aktif</span>
            <span className="qb-smart-badge"><Target size={14} /> 15 işe özgü soru</span>
          </div>
        </div>

        <div className="qb-coverage-summary">
          <div><BarChart3 size={20} /><span><strong>{formatCount(coverage?.nace_total)}</strong> Resmî NACE</span></div>
          <div className="is-smart"><ShieldCheck size={20} /><span><strong>{smartReadyCount == null ? '…' : formatCount(smartReadyCount)}</strong> Akıllı üretime hazır</span></div>
          <div className="is-managed"><BookOpenCheck size={20} /><span><strong>{formatCount(coverage?.published_question_total)}</strong> Yönetilen yayımlanmış soru</span></div>
          <div className="is-strong"><Target size={20} /><span><strong>{formatCount(coverage?.release_ready_count)}</strong> Güçlü yönetilen havuz</span></div>
        </div>

        <div className="qb-coverage-progress" aria-label="Akıllı soru üretim kapsaması">
          <span style={{width: `${smartCoveragePercent}%`}} />
        </div>

        <form className="qb-coverage-toolbar" onSubmit={(event) => {
          event.preventDefault();
          setCoverageOffset(0);
          loadCoverage(coverageFilter, coverageQuery, 0);
        }}>
          <div className="qb-search">
            <Search size={17} />
            <input value={coverageQuery} onChange={(event) => setCoverageQuery(event.target.value)}
              placeholder="NACE kodu, faaliyet veya profil ara" />
          </div>
          <select className="tp-select" value={coverageFilter} onChange={(event) => {
            const value = event.target.value;
            setCoverageFilter(value);
            setCoverageOffset(0);
            loadCoverage(value, coverageQuery, 0);
          }}>
            <option value="all">Tüm NACE faaliyetleri</option>
            <option value="blocked">Akıllı motor takviyesi</option>
            <option value="exam_ready">Yönetilen havuz hazır</option>
            <option value="release_ready">Güçlü yönetilen havuz</option>
          </select>
          <button type="submit" className="btn-outline-premium" disabled={coverageBusy}>Ara</button>
        </form>

        <div className="qb-coverage-table-wrap">
          <table className="qb-coverage-table">
            <thead><tr><th>NACE / faaliyet</th><th>Profil</th><th>Yönetilen havuz</th><th>Akıllı motor</th><th>Durum</th></tr></thead>
            <tbody>
              {coverageBusy ? (
                <tr><td colSpan="5" className="qb-table-empty">Kapsam hesaplanıyor…</td></tr>
              ) : !coverage?.items?.length ? (
                <tr><td colSpan="5" className="qb-table-empty">Bu filtrede NACE kaydı bulunamadı.</td></tr>
              ) : coverage.items.map((item) => {
                const smart = smartReadinessForItem(item, smartSectorIndex);
                const stateClass = item.release_ready
                  ? 'qb-coverage-state is-strong'
                  : item.ready
                    ? 'qb-coverage-state is-minimum'
                    : smart.ready
                      ? 'qb-coverage-state is-smart'
                      : 'qb-coverage-state is-review';
                const stateLabel = item.release_ready
                  ? 'Güçlü havuz'
                  : item.ready
                    ? 'Yönetilen hazır'
                    : smart.ready
                      ? 'Akıllı hazır'
                      : 'İnceleme gerekli';
                return (
                  <tr key={item.code}>
                    <td><strong>{item.nace}</strong><span>{item.name}</span><small>{item.hazard}</small></td>
                    <td>{item.profile}</td>
                    <td>
                      <div className="qb-managed-counts" title="Ortak / Teknik / Sektör yayımlanmış soru sayıları">
                        <span>O {item.available?.common ?? 0}</span>
                        <span>T {item.available?.technical ?? 0}</span>
                        <span>S {item.available?.sector ?? 0}</span>
                      </div>
                    </td>
                    <td>
                      {smart.ready ? (
                        <div className="qb-smart-cell">
                          <span className="qb-smart-cell-icon"><CheckCircle2 size={16} /></span>
                          <span><strong>{smart.questionCount} işe özgü soru</strong><small>{smart.topicCount} sabit işyeri konusu + NACE</small></span>
                        </div>
                      ) : (
                        <div className="qb-smart-cell is-review">
                          <span className="qb-smart-cell-icon"><AlertTriangle size={16} /></span>
                          <span><strong>Konu kontrolü gerekli</strong><small>{smart.topicCount}/5 işyeri konusu hazır</small></span>
                        </div>
                      )}
                    </td>
                    <td><span className={stateClass}>{stateLabel}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {coverage && (
          <div className="qb-coverage-pagination" aria-label="NACE sayfalama">
            <div className="qb-page-info">
              <strong>Sayfa {coveragePage.currentPage} / {coveragePage.totalPages}</strong>
              {' · '}{formatCount(coveragePage.total)} kayıt
              {coveragePage.total > 0 && ` · ${formatCount(coveragePage.offset + 1)}–${formatCount(Math.min(coveragePage.offset + coveragePage.limit, coveragePage.total))}`}
            </div>
            <div className="qb-page-actions">
              <button type="button" className="qb-page-button" disabled={coverageBusy || !coveragePage.hasPrevious}
                onClick={() => loadCoverage(coverageFilter, coverageQuery, coveragePage.previousOffset)}>
                Önceki
              </button>
              <button type="button" className="qb-page-button" disabled={coverageBusy || !coveragePage.hasNext}
                onClick={() => loadCoverage(coverageFilter, coverageQuery, coveragePage.nextOffset)}>
                Sonraki
              </button>
            </div>
          </div>
        )}

        <p className="qb-coverage-footnote">
          Yönetilen havuz sayıları yalnız onaylanıp yayımlanmış editoryal soruları gösterir. “Akıllı hazır”, NACE kataloğunda
          5 işe özgü konu bulunduğunu ve exact-NACE motorunun sınav için 15 işe özgü soru üretebildiğini ifade eder.
        </p>
      </section>

      {errors.length > 0 && (
        <div className="tp-alert err qb-error-summary" role="alert">
          <strong>İşlem tamamlanmadı. Bilgileriniz korunuyor:</strong>
          <ul>{errors.map((error) => <li key={error}>{error}</li>)}</ul>
        </div>
      )}
      {notice && <div className="tp-alert ok" role="status">{notice}</div>}

      <div className="qb-layout">
        <form className="panel-card qb-form" onSubmit={saveQuestion} ref={formRef} noValidate>
          <div className="qb-card-head">
            <div>
              <div className="section-title">{editingId ? 'Taslağı düzenle' : 'Yeni soru'}</div>
              <h2>{editingId ? `Soru #${editingId}` : 'Kaynaklı soru taslağı'}</h2>
              <p className="tp-help">Form otomatik korunur. Hata oluşursa doğru bilgileriniz silinmez.</p>
            </div>
            {editingId && (
              <button type="button" className="qb-icon-button" onClick={() => clearDraft()} title="Düzenlemeyi kapat">
                <X size={18} />
              </button>
            )}
          </div>

          <div className="tp-grid-2">
            <div>
              <label className="tp-label" htmlFor="qb-code">Soru kodu *</label>
              <input id="qb-code" className="tp-input" maxLength={60} value={draft.question_code}
                disabled={!!editingId} placeholder="Örn: NACE-30.11-001"
                onChange={(e) => patchDraft('question_code', e.target.value.toUpperCase())} />
            </div>
            <div>
              <label className="tp-label" htmlFor="qb-version">Sürüm *</label>
              <input id="qb-version" className="tp-input" type="number" min="1" step="1" value={draft.version}
                disabled={!!editingId} onChange={(e) => patchDraft('version', e.target.value)} />
            </div>
          </div>

          <div className="tp-grid-2">
            <div>
              <label className="tp-label" htmlFor="qb-topic-code">Konu kodu *</label>
              <input id="qb-topic-code" className="tp-input" maxLength={100} value={draft.topic_code}
                placeholder="Örn: KKD" onChange={(e) => patchDraft('topic_code', e.target.value)} />
            </div>
            <div>
              <label className="tp-label" htmlFor="qb-topic-label">Konu adı *</label>
              <input id="qb-topic-label" className="tp-input" maxLength={300} value={draft.topic_label}
                placeholder="Kişisel koruyucu donanımlar" onChange={(e) => patchDraft('topic_label', e.target.value)} />
            </div>
          </div>

          <div>
            <label className="tp-label" htmlFor="qb-question">Soru metni *</label>
            <textarea id="qb-question" className="tp-input qb-textarea" maxLength={2000} value={draft.question_text}
              placeholder="Tek anlamlı, açık ve sektöre uygun soru yazın."
              onChange={(e) => patchDraft('question_text', e.target.value)} />
          </div>

          <fieldset className="qb-fieldset">
            <legend>Cevap seçenekleri ve doğru cevap *</legend>
            <div className="qb-options">
              {OPTION_KEYS.map((key) => (
                <label className={'qb-option' + (draft.correct_option === key ? ' is-correct' : '')} key={key}>
                  <input type="radio" name="correct-option" value={key} checked={draft.correct_option === key}
                    onChange={() => patchDraft('correct_option', key)} aria-label={`${key} doğru cevap`} />
                  <span>{key}</span>
                  <input className="tp-input" value={draft.options[key]} maxLength={1000}
                    placeholder={`${key} seçeneği`} onChange={(e) => patchOption(key, e.target.value)} />
                </label>
              ))}
            </div>
            <p className="tp-help">Doğru cevabın yanındaki yuvarlağı seçin. Seçenekler birbirinden farklı olmalıdır.</p>
          </fieldset>

          <div>
            <label className="tp-label" htmlFor="qb-explanation">Doğru cevabın gerekçesi *</label>
            <textarea id="qb-explanation" className="tp-input qb-textarea qb-textarea--small" maxLength={4000}
              value={draft.answer_explanation} placeholder="Neden doğru olduğunu mevzuat ve uygulama açısından açıklayın."
              onChange={(e) => patchDraft('answer_explanation', e.target.value)} />
          </div>

          <fieldset className="qb-fieldset">
            <div className="qb-fieldset-head">
              <strong className="qb-fieldset-title">Kapsam *</strong>
              <button type="button" className="qb-link-button"
                onClick={() => patchDraft('scopes', [...draft.scopes, newScope('nace')])}>
                <Plus size={15} /> Kapsam ekle
              </button>
            </div>
            <datalist id="qb-sector-options">
              {sectors.map((sector) => (
                <option key={sector.code || sector.nace} value={sector.code || sector.nace}>
                  {sector.nace ? `${sector.nace} · ` : ''}{sector.label || sector.name}
                </option>
              ))}
            </datalist>
            <datalist id="qb-nace-options">
              {sectors.filter((sector) => sector.nace).map((sector) => (
                <option key={`${sector.nace}-${sector.code}`} value={sector.nace}>{sector.label || sector.name}</option>
              ))}
            </datalist>
            {draft.scopes.map((scope, index) => (
              <div className="qb-repeat-row" key={`${index}-${scope.type}`}>
                <select className="tp-select" value={scope.type} onChange={(e) => patchScope(index, 'type', e.target.value)}>
                  {Object.entries(SCOPE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
                {scope.type === 'common' ? (
                  <input className="tp-input" value="Tüm sektörler (*)" readOnly aria-label="Ortak kapsam" />
                ) : scope.type === 'hazard' ? (
                  <select className="tp-select" value={scope.value} onChange={(e) => patchScope(index, 'value', e.target.value)}>
                    <option value="">Tehlike sınıfını seçin</option>
                    {HAZARDS.map((hazard) => <option key={hazard}>{hazard}</option>)}
                  </select>
                ) : (
                  <input className="tp-input" value={scope.value}
                    list={scope.type === 'nace' ? 'qb-nace-options' : 'qb-sector-options'}
                    placeholder={scope.type === 'nace' ? 'Örn: 30.11' : 'Sektör kodu seçin'}
                    onChange={(e) => patchScope(index, 'value', e.target.value)} />
                )}
                <button type="button" className="qb-icon-button qb-icon-button--danger" title="Kapsamı kaldır"
                  disabled={draft.scopes.length === 1}
                  onClick={() => patchDraft('scopes', draft.scopes.filter((_, i) => i !== index))}>
                  <Trash2 size={17} />
                </button>
              </div>
            ))}
            <p className="tp-help">NACE değeri alt faaliyetleri kapsayabilir: “30.11” seçimi 30.11 ile başlayan kodlara uygulanır.</p>
          </fieldset>

          <fieldset className="qb-fieldset">
            <div className="qb-fieldset-head">
              <strong className="qb-fieldset-title">Doğrulanabilir kaynaklar *</strong>
              <button type="button" className="qb-link-button"
                onClick={() => patchDraft('sources', [...draft.sources, newSource()])}>
                <Plus size={15} /> Kaynak ekle
              </button>
            </div>
            {draft.sources.map((source, index) => (
              <div className="qb-source" key={index}>
                <div className="qb-source-head">
                  <strong>Kaynak {index + 1}</strong>
                  <button type="button" className="qb-icon-button qb-icon-button--danger" title="Kaynağı kaldır"
                    disabled={draft.sources.length === 1}
                    onClick={() => patchDraft('sources', draft.sources.filter((_, i) => i !== index))}>
                    <Trash2 size={16} />
                  </button>
                </div>
                <input className="tp-input" value={source.title} maxLength={300} placeholder="Resmî kaynağın adı"
                  onChange={(e) => patchSource(index, 'title', e.target.value)} />
                <input className="tp-input" type="url" value={source.url} maxLength={1000}
                  placeholder="https://..." onChange={(e) => patchSource(index, 'url', e.target.value)} />
                <div className="tp-grid-2">
                  <input className="tp-input" value={source.reference} maxLength={300}
                    placeholder="Madde / bölüm / sayfa" onChange={(e) => patchSource(index, 'reference', e.target.value)} />
                  <input className="tp-input" type="date" value={source.effective_date}
                    onChange={(e) => patchSource(index, 'effective_date', e.target.value)} />
                </div>
              </div>
            ))}
          </fieldset>

          <div>
            <label className="tp-label" htmlFor="qb-note">İnceleme notu</label>
            <textarea id="qb-note" className="tp-input qb-textarea qb-textarea--small" maxLength={4000}
              value={draft.reviewer_note} placeholder="Sınavı hazırlayan İş Güvenliği Uzmanının inceleme notu"
              onChange={(e) => patchDraft('reviewer_note', e.target.value)} />
          </div>

          <div className="qb-form-actions">
            <button type="submit" className="btn-premium" disabled={!!actionBusy}>
              <Save size={17} /> {actionBusy === 'save' ? 'Kaydediliyor…' : editingId ? 'Taslağı güncelle' : 'Taslak olarak kaydet'}
            </button>
            <button type="button" className="btn-outline-premium" onClick={() => clearDraft()} disabled={!!actionBusy}>
              Temizle
            </button>
          </div>
        </form>

        <section className="panel-card qb-list-panel">
          <div className="qb-card-head">
            <div>
              <div className="section-title">Kontrollü havuz</div>
              <h2>Sorular ve onay durumu</h2>
              <p className="tp-help">Yalnız yayımlanmış sorular sınav üretiminde kullanılabilir.</p>
            </div>
            <button type="button" className="qb-icon-button" onClick={loadQuestions} disabled={busy} title="Listeyi yenile">
              <RefreshCw size={18} className={busy ? 'qb-spin' : ''} />
            </button>
          </div>

          <div className="qb-toolbar">
            <div className="qb-search">
              <Search size={17} />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Kod, konu veya soru ara" />
            </div>
            <div className="qb-filters" aria-label="Durum filtresi">
              {STATUS_FILTERS.map((item) => (
                <button type="button" key={item.value || 'all'}
                  className={statusFilter === item.value ? 'active' : ''}
                  onClick={() => setStatusFilter(item.value)}>
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="qb-list" aria-live="polite">
            {busy ? (
              <div className="qb-empty"><RefreshCw size={24} className="qb-spin" /> Sorular yükleniyor…</div>
            ) : filteredQuestions.length === 0 ? (
              <div className="qb-empty"><BookOpenCheck size={30} /> Bu filtrede henüz soru bulunmuyor.</div>
            ) : filteredQuestions.map((row) => {
              return (
                <article className="qb-question-card" key={row.id}>
                  <div className="qb-question-top">
                    <div>
                      <div className="qb-question-code">{row.question_code} <span>v{row.version}</span></div>
                      <h3>{row.question_text}</h3>
                    </div>
                    <span className={statusClass(row.status)}>{QUESTION_STATUS[row.status] || row.status}</span>
                  </div>
                  <div className="qb-question-meta">
                    <span>{row.topic_label}</span>
                    <span>Güncelleme: {formatDate(row.updated_at)}</span>
                  </div>
                  <div className="qb-scope-chips">
                    {(row.scopes || []).map((scope) => (
                      <span key={`${scope.type}-${scope.value}`}>{SCOPE_LABELS[scope.type] || scope.type}: {scope.value}</span>
                    ))}
                  </div>
                  <details className="qb-details">
                    <summary>Cevap, gerekçe ve kaynakları göster</summary>
                    <div className="qb-answer-grid">
                      {OPTION_KEYS.map((key) => (
                        <div key={key} className={row.correct_option === key ? 'is-correct' : ''}>
                          <strong>{key}</strong> {row.options?.[key]}
                        </div>
                      ))}
                    </div>
                    <p><strong>Gerekçe:</strong> {row.answer_explanation}</p>
                    <ul className="qb-source-links">
                      {(row.sources || []).map((source, index) => (
                        <li key={`${source.url}-${index}`}>
                          <a href={source.url} target="_blank" rel="noreferrer">
                            {source.title} · {source.reference} <ExternalLink size={13} />
                          </a>
                        </li>
                      ))}
                    </ul>
                  </details>
                  <div className="qb-card-actions">
                    {['draft', 'in_review'].includes(row.status) && (
                      <button type="button" onClick={() => editQuestion(row)}><Pencil size={15} /> Düzenle</button>
                    )}
                    {row.status === 'draft' && (
                      <button type="button" className="primary" disabled={!!actionBusy}
                        onClick={() => runAction(row, 'submit')}>
                        <Send size={15} /> {actionBusy === `submit-${row.id}` ? 'Gönderiliyor…' : 'İncelemeye gönder'}
                      </button>
                    )}
                    {row.status === 'in_review' && (
                      <button type="button" className="success" disabled={!!actionBusy}
                        onClick={() => runAction(row, 'publish')}>
                        <CheckCircle2 size={15} /> {actionBusy === `publish-${row.id}` ? 'Yayımlanıyor…' : 'Onayla ve yayımla'}
                      </button>
                    )}
                    {row.status === 'published' && (
                      <button type="button" disabled={!!actionBusy} onClick={() => runAction(row, 'retire')}>
                        <Archive size={15} /> {actionBusy === `retire-${row.id}` ? 'Kaldırılıyor…' : 'Kullanımdan kaldır'}
                      </button>
                    )}
                    {['published', 'retired'].includes(row.status) && (
                      <button type="button" onClick={() => editQuestion(row, true)}><CopyPlus size={15} /> Yeni sürüm</button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
}
