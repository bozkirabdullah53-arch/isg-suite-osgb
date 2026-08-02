import React, {useEffect, useMemo, useRef, useState} from 'react';
import {
  Archive,
  BookOpenCheck,
  CheckCircle2,
  CopyPlus,
  Database,
  ExternalLink,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Search,
  Send,
  ShieldCheck,
  Trash2,
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

const STATUS_FILTERS = [
  {value: '', label: 'Tümü'},
  {value: 'draft', label: 'Taslak'},
  {value: 'in_review', label: 'İncelemede'},
  {value: 'published', label: 'Yayımlandı'},
  {value: 'retired', label: 'Kaldırıldı'},
];

const OPTION_KEYS = ['A', 'B', 'C', 'D'];
const HAZARDS = ['Az Tehlikeli', 'Tehlikeli', 'Çok Tehlikeli'];

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

export function TrainingQuestionBank({user, sectors = []}) {
  const formRef = useRef(null);
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

  useEffect(() => {
    loadQuestions();
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
          <div className="hero-chip"><ShieldCheck size={15} /> Kaynaklı ve denetlenebilir içerik</div>
          <h1>NACE uyumlu eğitim soru bankası</h1>
          <p>
            Sorular yalnız doğrulanabilir kaynakla kaydedilir, ikinci bir yönetici onayından sonra sınav havuzuna girer.
            Yayımlanan içerik değiştirilemez; düzeltmeler yeni sürüm olarak hazırlanır.
          </p>
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
              {sectors.slice(0, 1500).map((sector) => (
                <option key={sector.code || sector.nace} value={sector.code || sector.nace}>
                  {sector.nace ? `${sector.nace} · ` : ''}{sector.label || sector.name}
                </option>
              ))}
            </datalist>
            <datalist id="qb-nace-options">
              {sectors.slice(0, 1500).filter((sector) => sector.nace).map((sector) => (
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
              value={draft.reviewer_note} placeholder="Uzmanın veya ikinci yöneticinin kontrol etmesi gereken notlar"
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
              const ownQuestion = Number(row.created_by_id) === Number(user?.id);
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
                  {row.status === 'in_review' && ownQuestion && (
                    <div className="qb-four-eyes"><ShieldCheck size={15} /> Bu soruyu yayımlamak için ikinci bir global yönetici gerekir.</div>
                  )}
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
                    {row.status === 'in_review' && !ownQuestion && (
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
