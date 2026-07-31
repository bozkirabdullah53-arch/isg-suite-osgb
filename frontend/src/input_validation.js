/**
 * Uygulama genelinde HTML form alanları için güvenli giriş koruması.
 * Tarayıcı doğrulamasını Türkçeleştirir, tarih/saat seçicisini açar,
 * sayı alanlarında geçersiz karakterleri engeller ve metinleri temizler.
 *
 * Not: Bu katman frontend korumasıdır. Kritik alanların backend şemalarında
 * ayrıca doğrulanması zorunludur.
 */

const TURKISH_MESSAGES = {
  valueMissing: 'Bu alan zorunludur.',
  typeMismatch: 'Geçerli bir değer giriniz.',
  patternMismatch: 'Bilgiyi istenen biçimde giriniz.',
  tooLong: 'Girilen bilgi izin verilen uzunluğu aşıyor.',
  tooShort: 'Girilen bilgi çok kısa.',
  rangeUnderflow: 'Girilen değer izin verilen minimum değerden küçük.',
  rangeOverflow: 'Girilen değer izin verilen maksimum değerden büyük.',
  stepMismatch: 'Geçerli bir sayı giriniz.',
  badInput: 'Bu alana geçerli bir değer giriniz.',
};

function isFormControl(target) {
  return target instanceof HTMLInputElement
    || target instanceof HTMLTextAreaElement
    || target instanceof HTMLSelectElement;
}

function messageFor(input) {
  const v = input.validity;
  if (v.valueMissing) return input.dataset.requiredMessage || TURKISH_MESSAGES.valueMissing;
  if (v.typeMismatch) {
    if (input.type === 'email') return 'Geçerli bir e-posta adresi giriniz.';
    if (input.type === 'url') return 'Geçerli bir internet adresi giriniz.';
    return TURKISH_MESSAGES.typeMismatch;
  }
  if (v.patternMismatch) return input.dataset.patternMessage || TURKISH_MESSAGES.patternMismatch;
  if (v.tooLong) return TURKISH_MESSAGES.tooLong;
  if (v.tooShort) return TURKISH_MESSAGES.tooShort;
  if (v.rangeUnderflow) return TURKISH_MESSAGES.rangeUnderflow;
  if (v.rangeOverflow) return TURKISH_MESSAGES.rangeOverflow;
  if (v.stepMismatch) return TURKISH_MESSAGES.stepMismatch;
  if (v.badInput) return TURKISH_MESSAGES.badInput;
  return '';
}

function setTurkishValidationMessage(input) {
  input.setCustomValidity('');
  const message = messageFor(input);
  if (message) input.setCustomValidity(message);
}

function normalizeTextValue(input) {
  if (input instanceof HTMLSelectElement) return;
  if (input.type === 'password' || input.type === 'file') return;
  if (input.dataset.noTrim === 'true') return;

  // Baş/son boşlukları temizle, arka arkaya 3+ boşluğu teke indir.
  const cleaned = input.value.trim().replace(/\s{3,}/g, ' ');
  if (cleaned !== input.value) input.value = cleaned;
}

function configureInput(input) {
  if (!(input instanceof HTMLInputElement)) return;

  if (input.type === 'date') {
    input.inputMode = 'none';
    input.autocomplete = 'off';
    input.setAttribute('aria-label', input.getAttribute('aria-label') || 'Tarih seçin');
  } else if (input.type === 'time') {
    input.inputMode = 'none';
    input.autocomplete = 'off';
    input.setAttribute('aria-label', input.getAttribute('aria-label') || 'Saat seçin');
  } else if (input.type === 'number') {
    input.inputMode = input.step && input.step !== '1' ? 'decimal' : 'numeric';
  } else if (input.type === 'email') {
    input.inputMode = 'email';
    input.autocomplete = input.autocomplete || 'email';
  } else if (input.type === 'tel') {
    input.inputMode = 'tel';
    input.autocomplete = input.autocomplete || 'tel';
  }
}

function openNativePicker(input) {
  if (!(input instanceof HTMLInputElement)) return;
  if (!['date', 'time', 'datetime-local', 'month'].includes(input.type)) return;
  if (input.disabled || input.readOnly) return;
  try {
    if (typeof input.showPicker === 'function') input.showPicker();
  } catch {
    // Bazı tarayıcılar kullanıcı etkileşimi dışında showPicker çağrısını engeller.
  }
}

function blockInvalidNumberKeys(event) {
  const input = event.target;
  if (!(input instanceof HTMLInputElement) || input.type !== 'number') return;

  // Bilimsel gösterim ve işaret, yalnız açıkça izin verilmişse kullanılabilir.
  const allowNegative = Number(input.min) < 0 || input.dataset.allowNegative === 'true';
  const allowExponent = input.dataset.allowExponent === 'true';
  if (!allowExponent && (event.key === 'e' || event.key === 'E')) event.preventDefault();
  if (!allowNegative && (event.key === '-' || event.key === '+')) event.preventDefault();
}

function clampNumber(input) {
  if (!(input instanceof HTMLInputElement) || input.type !== 'number' || input.value === '') return;
  const value = Number(input.value);
  if (!Number.isFinite(value)) {
    input.value = '';
    return;
  }
  if (input.min !== '' && value < Number(input.min)) input.value = input.min;
  if (input.max !== '' && value > Number(input.max)) input.value = input.max;
}

function validateDateRange(input) {
  if (!(input instanceof HTMLInputElement) || !['date', 'time', 'datetime-local'].includes(input.type)) return;
  const compareId = input.dataset.endField || input.dataset.startField;
  if (!compareId) return;
  const other = document.getElementById(compareId);
  if (!(other instanceof HTMLInputElement) || !input.value || !other.value) return;

  const isStart = Boolean(input.dataset.endField);
  const start = isStart ? input.value : other.value;
  const end = isStart ? other.value : input.value;
  if (start > end) {
    input.setCustomValidity(isStart
      ? 'Başlangıç değeri bitiş değerinden sonra olamaz.'
      : 'Bitiş değeri başlangıç değerinden önce olamaz.');
  }
}

export function installGlobalInputGuards(root = document) {
  root.querySelectorAll('input, textarea, select').forEach(configureInput);

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (!(node instanceof Element)) continue;
        if (node.matches?.('input, textarea, select')) configureInput(node);
        node.querySelectorAll?.('input, textarea, select').forEach(configureInput);
      }
    }
  });
  observer.observe(root.documentElement || root, {childList: true, subtree: true});

  root.addEventListener('click', (event) => {
    if (event.target instanceof HTMLInputElement) openNativePicker(event.target);
  }, true);

  root.addEventListener('keydown', blockInvalidNumberKeys, true);

  root.addEventListener('input', (event) => {
    if (!isFormControl(event.target)) return;
    event.target.setCustomValidity('');
  }, true);

  root.addEventListener('change', (event) => {
    if (!isFormControl(event.target)) return;
    clampNumber(event.target);
    validateDateRange(event.target);
    setTurkishValidationMessage(event.target);
  }, true);

  root.addEventListener('blur', (event) => {
    if (!isFormControl(event.target)) return;
    normalizeTextValue(event.target);
    clampNumber(event.target);
    validateDateRange(event.target);
    setTurkishValidationMessage(event.target);
  }, true);

  root.addEventListener('invalid', (event) => {
    if (!isFormControl(event.target)) return;
    setTurkishValidationMessage(event.target);
  }, true);

  return () => observer.disconnect();
}
