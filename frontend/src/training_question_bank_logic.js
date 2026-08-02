export const QUESTION_STATUS = {
  draft: 'Taslak',
  in_review: 'İncelemede',
  published: 'Yayımlandı',
  retired: 'Kullanımdan kaldırıldı',
};

export const SCOPE_LABELS = {
  common: 'Ortak',
  hazard: 'Tehlike sınıfı',
  sector: 'Sektör',
  nace: 'NACE kodu',
};

export function newScope(type = 'common') {
  return {type, value: type === 'common' ? '*' : ''};
}

export function newSource() {
  return {title: '', url: '', reference: '', effective_date: ''};
}

export function emptyQuestionDraft() {
  return {
    question_code: '',
    version: 1,
    topic_code: '',
    topic_label: '',
    question_text: '',
    options: {A: '', B: '', C: '', D: ''},
    correct_option: 'A',
    answer_explanation: '',
    reviewer_note: '',
    scopes: [newScope()],
    sources: [newSource()],
  };
}

function text(value) {
  return String(value ?? '').trim();
}

export function questionToDraft(row, {nextVersion = false} = {}) {
  const options = row?.options || {};
  return {
    question_code: text(row?.question_code),
    version: Math.max(1, Number(row?.version || 1) + (nextVersion ? 1 : 0)),
    topic_code: text(row?.topic_code),
    topic_label: text(row?.topic_label),
    question_text: text(row?.question_text),
    options: {
      A: text(options.A),
      B: text(options.B),
      C: text(options.C),
      D: text(options.D),
    },
    correct_option: ['A', 'B', 'C', 'D'].includes(row?.correct_option) ? row.correct_option : 'A',
    answer_explanation: text(row?.answer_explanation),
    reviewer_note: nextVersion ? '' : text(row?.reviewer_note),
    scopes: Array.isArray(row?.scopes) && row.scopes.length
      ? row.scopes.map((scope) => ({type: scope.type, value: text(scope.value)}))
      : [newScope()],
    sources: Array.isArray(row?.sources) && row.sources.length
      ? row.sources.map((source) => ({
          title: text(source.title),
          url: text(source.url),
          reference: text(source.reference),
          effective_date: source.effective_date ? String(source.effective_date).slice(0, 10) : '',
        }))
      : [newSource()],
  };
}

export function validateQuestionDraft(draft) {
  const errors = [];
  const code = text(draft?.question_code);
  if (!/^[A-Za-z0-9_.-]{3,60}$/.test(code)) {
    errors.push('Soru kodu 3–60 karakter olmalı; yalnız harf, rakam, nokta, alt çizgi ve tire kullanılmalıdır.');
  }
  if (!Number.isInteger(Number(draft?.version)) || Number(draft.version) < 1) {
    errors.push('Soru sürümü 1 veya daha büyük bir tam sayı olmalıdır.');
  }
  if (text(draft?.topic_code).length < 2) errors.push('Konu kodu en az 2 karakter olmalıdır.');
  if (text(draft?.topic_label).length < 3) errors.push('Konu adı en az 3 karakter olmalıdır.');
  if (text(draft?.question_text).length < 12) errors.push('Soru metni en az 12 karakter olmalıdır.');

  const optionValues = ['A', 'B', 'C', 'D'].map((key) => text(draft?.options?.[key]));
  if (optionValues.some((value) => value.length < 2)) {
    errors.push('Dört seçeneğin tamamı anlamlı biçimde doldurulmalıdır.');
  } else if (new Set(optionValues.map((value) => value.toLocaleLowerCase('tr'))).size !== 4) {
    errors.push('Dört seçenek birbirinden farklı olmalıdır.');
  }
  if (!['A', 'B', 'C', 'D'].includes(draft?.correct_option)) {
    errors.push('Doğru cevap A, B, C veya D olmalıdır.');
  }
  if (text(draft?.answer_explanation).length < 12) {
    errors.push('Doğru cevabın gerekçesi en az 12 karakter olmalıdır.');
  }

  const scopes = Array.isArray(draft?.scopes) ? draft.scopes : [];
  if (!scopes.length) errors.push('En az bir soru kapsamı seçilmelidir.');
  const scopePairs = new Set();
  scopes.forEach((scope, index) => {
    const type = scope?.type;
    const value = text(scope?.value);
    if (!Object.hasOwn(SCOPE_LABELS, type)) {
      errors.push(`${index + 1}. kapsam türü geçersizdir.`);
      return;
    }
    if ((type === 'common' && value !== '*') || (type !== 'common' && !value)) {
      errors.push(`${index + 1}. kapsam değeri eksik veya geçersizdir.`);
    }
    if (type === 'nace' && value && !/^\d{2}(?:\.\d{2}){0,2}$/.test(value)) {
      errors.push(`${index + 1}. NACE kapsamı 01, 30.11 veya 30.11.01 biçiminde olmalıdır.`);
    }
    const pair = `${type}:${value.toLocaleLowerCase('tr')}`;
    if (scopePairs.has(pair)) errors.push('Aynı kapsam bir soruya iki kez eklenemez.');
    scopePairs.add(pair);
  });

  const sources = Array.isArray(draft?.sources) ? draft.sources : [];
  if (!sources.length) errors.push('En az bir doğrulanabilir kaynak eklenmelidir.');
  sources.forEach((source, index) => {
    if (text(source?.title).length < 3) errors.push(`${index + 1}. kaynak adı en az 3 karakter olmalıdır.`);
    if (!/^https:\/\/[^\s]+$/i.test(text(source?.url))) {
      errors.push(`${index + 1}. kaynak bağlantısı geçerli bir https:// adresi olmalıdır.`);
    }
    if (text(source?.reference).length < 2) {
      errors.push(`${index + 1}. kaynak için mevzuat, madde veya bölüm referansı yazılmalıdır.`);
    }
  });
  return [...new Set(errors)];
}

export function questionDraftPayload(draft) {
  return {
    question_code: text(draft.question_code).toUpperCase(),
    version: Number(draft.version),
    topic_code: text(draft.topic_code),
    topic_label: text(draft.topic_label),
    question_text: text(draft.question_text),
    options: ['A', 'B', 'C', 'D'].map((key) => text(draft.options[key])),
    correct_option: draft.correct_option,
    answer_explanation: text(draft.answer_explanation),
    reviewer_note: text(draft.reviewer_note) || null,
    scopes: draft.scopes.map((scope) => ({type: scope.type, value: text(scope.value)})),
    sources: draft.sources.map((source) => ({
      title: text(source.title),
      url: text(source.url),
      reference: text(source.reference),
      ...(source.effective_date ? {effective_date: source.effective_date} : {}),
    })),
  };
}
