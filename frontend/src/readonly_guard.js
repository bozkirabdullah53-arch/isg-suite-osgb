const READ_ONLY_MARKERS = [
  'Salt okunur mod: abonelik süresi doldu',
  'Abonelik süresi doldu veya askıda',
  'Veri girişi kapalı',
];

const WRITE_BUTTON_RE = /^(firma ekle|işyeri ekle|profesyonel ekle|i̇sg profesyoneli ekle|görevlendirme ekle|kaydet|sil|pasife al|aktife al|aktifleştir|onayla|reddet|gönder|yükle|defter kaydı)$/i;

function isReadOnlyPage() {
  const text = document.body?.innerText || '';
  return READ_ONLY_MARKERS.some((marker) => text.includes(marker));
}

function setDisabled(el, disabled) {
  if (!(el instanceof HTMLElement)) return;
  if (disabled) {
    if (!el.dataset.subscriptionReadonly) {
      el.dataset.subscriptionReadonly = '1';
      el.dataset.subscriptionWasDisabled = el.disabled ? '1' : '0';
    }
    el.disabled = true;
    el.setAttribute('aria-disabled', 'true');
    el.title = 'Abonelik askıda veya süresi dolmuş. Salt okunur mod.';
  } else if (el.dataset.subscriptionReadonly === '1') {
    if (el.dataset.subscriptionWasDisabled !== '1') el.disabled = false;
    el.removeAttribute('aria-disabled');
    delete el.dataset.subscriptionReadonly;
    delete el.dataset.subscriptionWasDisabled;
  }
}

function applyReadOnlyGuard() {
  const blocked = isReadOnlyPage();
  document.documentElement.classList.toggle('subscription-readonly', blocked);

  document.querySelectorAll('button').forEach((button) => {
    const label = (button.innerText || button.textContent || '').trim().replace(/\s+/g, ' ');
    if (WRITE_BUTTON_RE.test(label) || /\b(Ekle|Kaydet|Sil|Gönder|Yükle)\b/i.test(label)) {
      setDisabled(button, blocked);
    }
  });

  document.querySelectorAll('.modal, [role="dialog"]').forEach((modal) => {
    const warning = modal.innerText || '';
    if (!blocked && !READ_ONLY_MARKERS.some((marker) => warning.includes(marker))) return;
    modal.querySelectorAll('input, select, textarea, button[type="submit"]').forEach((el) => setDisabled(el, true));
  });
}

function addStagingReviewerForm() {
  const isStaging = window.location.hostname === 'isg-suite-web-staging.onrender.com';
  const onSettings = window.location.hash.includes('m=eisa_system_settings');
  if (!isStaging || !onSettings || document.getElementById('staging-global-admin-form')) return;

  const panel = document.querySelector('main .panel, .content .panel, section.panel');
  if (!panel) return;

  const wrapper = document.createElement('section');
  wrapper.id = 'staging-global-admin-form';
  wrapper.style.cssText = 'max-width:720px;margin:0 0 28px;padding:20px;border:1px solid #99f6e4;border-radius:16px;background:#f0fdfa;';
  wrapper.innerHTML = `
    <h4 style="margin:0 0 6px">Staging Global Yönetici Ekle</h4>
    <p style="margin:0 0 16px;color:#64748b">Yalnız staging test ortamında ikinci onay yöneticisi oluşturur. Canlı sistemi etkilemez.</p>
    <form id="staging-global-admin-create" class="form-grid" autocomplete="off">
      <label class="field"><span>Ad Soyad</span><input name="full_name" value="Staging Reviewer" required minlength="2" maxlength="160"></label>
      <label class="field"><span>E-posta</span><input name="email" type="email" value="staging.reviewer@isgsuite.tr" required></label>
      <label class="field"><span>Şifre</span><input name="password" type="password" required minlength="10" maxlength="128" autocomplete="new-password"></label>
      <label class="field"><span>Şifre Tekrar</span><input name="confirm_password" type="password" required minlength="10" maxlength="128" autocomplete="new-password"></label>
      <div class="form-actions"><button type="submit">Global Yönetici Oluştur</button></div>
      <p id="staging-global-admin-message" style="margin:4px 0 0"></p>
    </form>`;

  panel.prepend(wrapper);

  wrapper.querySelector('form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('button[type="submit"]');
    const message = form.querySelector('#staging-global-admin-message');
    const values = new FormData(form);
    const password = String(values.get('password') || '');
    const confirmPassword = String(values.get('confirm_password') || '');
    if (password !== confirmPassword) {
      message.textContent = 'Şifre ve tekrar alanı aynı değil.';
      message.style.color = '#b91c1c';
      return;
    }

    button.disabled = true;
    message.textContent = 'Hesap oluşturuluyor…';
    message.style.color = '#475569';
    try {
      const token = localStorage.getItem('isg_token');
      if (!token) throw new Error('Oturum anahtarı bulunamadı. Yeniden giriş yapın.');
      const response = await fetch('https://isg-suite-api-staging.onrender.com/api/v1/users', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          full_name: String(values.get('full_name') || '').trim(),
          email: String(values.get('email') || '').trim().toLowerCase(),
          password,
          role: 'global_admin',
          company_id: null,
        }),
      });
      let body = null;
      try { body = await response.json(); } catch { body = null; }
      if (!response.ok) {
        const detail = typeof body?.detail === 'string' ? body.detail : `İşlem başarısız (${response.status}).`;
        throw new Error(detail);
      }
      message.textContent = `${body.email} hesabı başarıyla oluşturuldu.`;
      message.style.color = '#166534';
      form.querySelector('input[name="password"]').value = '';
      form.querySelector('input[name="confirm_password"]').value = '';
    } catch (error) {
      message.textContent = error?.message || 'Hesap oluşturulamadı.';
      message.style.color = '#b91c1c';
    } finally {
      button.disabled = false;
    }
  });
}

let scheduled = false;
function scheduleGuard() {
  if (scheduled) return;
  scheduled = true;
  queueMicrotask(() => {
    scheduled = false;
    applyReadOnlyGuard();
    addStagingReviewerForm();
  });
}

document.addEventListener('DOMContentLoaded', scheduleGuard);
window.addEventListener('hashchange', scheduleGuard);
new MutationObserver(scheduleGuard).observe(document.documentElement, {
  childList: true,
  subtree: true,
  characterData: true,
});

document.addEventListener('submit', (event) => {
  if (!isReadOnlyPage()) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}, true);

scheduleGuard();
