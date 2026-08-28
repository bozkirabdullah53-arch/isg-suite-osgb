import {api, API_URL, uploadFile} from './api';

window.__ISG_REMOTE_TRAINING_CLEAN_MANAGER__ = true;

const C = '/trainings/remote/catalog/packages';
const S = 'rt-clean-style';
const A = 'data-rt-clean';
const H = 'rt-clean-host';
const PACKAGE_ID_ATTR = 'data-remote-catalog-package-id';
let rows = [];
let id = null;
let detail = null;
let timer = null;
let pollTimer = null;
let busy = false;
let forking = null;
let allowed = null;

const L = {
  draft: 'Taslak',
  uploading: 'Yükleniyor',
  processing: 'İşleniyor',
  processing_failed: 'İşleme başarısız',
  ready_for_review: 'Yayıma hazır',
  published: 'Yayında',
  unpublished: 'Yayında değil',
  archived: 'Arşivlendi',
};

const esc = (v) => String(v ?? '')
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;');

const abs = (p) => /^https?:\/\//i.test(String(API_URL || ''))
  ? new URL(p, `${API_URL}/`).toString()
  : new URL(p, `${location.origin}${API_URL || '/api/v1'}`).toString();

function css() {
  if (document.getElementById(S)) return;
  const x = document.createElement('style');
  x.id = S;
  x.textContent = `.${H}>:not([${A}]){display:none!important}.rtc{color:#173b57}.rtc *{box-sizing:border-box}.rtc-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;padding-bottom:13px;border-bottom:1px solid #e3edf3}.rtc h3{margin:3px 0 4px;font-size:21px}.rtc-k{font-size:11px;font-weight:850;letter-spacing:.08em;color:#0f766e}.rtc-meta,.rtc-note{color:#60798b;font-size:12px}.rtc-meta{display:flex;gap:7px;flex-wrap:wrap}.rtc-actions,.rtc-sec-actions,.rtc-va{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}.rtc button{min-height:34px;padding:7px 10px;border:1px solid #bfd0dd;border-radius:8px;background:#fff;color:#173b57;font:inherit;font-size:12px;font-weight:800;cursor:pointer}.rtc button:hover:not(:disabled){border-color:#2696a0}.rtc button:disabled{opacity:.55}.rtc .pri{background:#0f766e;border-color:#0f766e;color:#fff}.rtc .pub{background:#f2fff5;border-color:#9acdad;color:#17643a}.rtc .bad{background:#fff8f7;border-color:#e5aaa5;color:#ad2e25}.rtc-note{margin-top:11px;padding:9px 11px;border:1px solid #cfe3e7;border-radius:9px;background:#f7fcfd;line-height:1.45}.rtc-list{display:grid;gap:10px;margin-top:12px}.rtc-sec{border:1px solid #dbe5ef;border-radius:10px;overflow:hidden;background:#fff}.rtc-sec.drag{opacity:.5}.rtc-sec.over{outline:2px solid #18a3a5;outline-offset:2px}.rtc-sec-head{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:10px 11px;background:#fbfdff;border-bottom:1px solid #edf2f6}.rtc-sec-id{display:flex;gap:8px;align-items:center;min-width:0}.rtc-grab{width:32px;min-width:32px!important;padding:0!important;border-style:dashed!important;color:#0f766e!important;cursor:grab!important}.rtc-sec-name strong,.rtc-v strong{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.rtc-sec-name span,.rtc-v span{display:block;margin-top:2px;color:#6a8090;font-size:11px}.rtc-sec-body{padding:9px 11px 11px}.rtc-upload{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:2px 0 9px;color:#60798b;font-size:12px}.rtc-vlist{display:grid;gap:6px}.rtc-v{display:grid;grid-template-columns:minmax(160px,1fr) auto;gap:9px;align-items:center;padding:8px 9px;border:1px solid #e4edf3;border-radius:8px;background:#f9fbfd}.rtc-va button{min-height:30px;padding:5px 7px;font-size:11px}.rtc-empty{padding:18px;text-align:center;color:#60798b;border:1px dashed #bfd0dd;border-radius:9px}.rtc-pop{position:fixed;inset:0;z-index:10170;display:grid;place-items:center;padding:20px;background:rgba(7,25,39,.58)}.rtc-box{width:min(560px,96vw);max-height:92vh;overflow:auto;background:#fff;border-radius:14px;box-shadow:0 22px 65px rgba(7,30,48,.28)}.rtc-box-h{display:flex;justify-content:space-between;gap:10px;padding:15px 17px 11px;border-bottom:1px solid #e6edf3}.rtc-box-h h3{margin:0;font-size:18px}.rtc-close{border:0!important;font-size:22px!important}.rtc-form{padding:15px 17px}.rtc-form label{display:block;margin-bottom:10px;font-size:12px;font-weight:800}.rtc-form input,.rtc-form textarea{display:block;width:100%;margin-top:5px;padding:9px;border:1px solid #bfd0dd;border-radius:8px;font:inherit}.rtc-form textarea{min-height:80px}.rtc-form-a{display:flex;justify-content:flex-end;gap:7px}.rtc-preview{width:min(900px,96vw)}.rtc-preview video{width:100%;max-height:75vh;background:#000;display:block}.rtc-toast{position:fixed;right:20px;bottom:20px;z-index:10190;max-width:min(500px,90vw);padding:11px 13px;border-radius:9px;background:#0f766e;color:#fff;font-size:12px;font-weight:800}.rtc-toast.err{background:#b42318}@media(max-width:820px){.rtc-head,.rtc-v{display:grid}.rtc-actions,.rtc-va,.rtc-sec-actions{justify-content:flex-start}.rtc-sec-head{align-items:flex-start}}`;
  document.head.appendChild(x);
}

function toast(message, error = false) {
  document.querySelector('.rtc-toast')?.remove();
  const node = document.createElement('div');
  node.className = `rtc-toast${error ? ' err' : ''}`;
  node.textContent = message;
  document.body.appendChild(node);
  setTimeout(() => node.remove(), error ? 6000 : 3800);
}

const root = () => [...document.querySelectorAll('section')].find((section) => {
  const text = section.textContent || '';
  return text.includes('Uzaktan Eğitim Paket Kataloğu') && text.includes('Sektör eğitim paketleri');
});
const grid = () => root()?.querySelector('.remote-training-manager-grid');
const host = () => grid()?.children?.[1];
const cards = () => grid()?.children?.[0]
  ? [...grid().children[0].querySelectorAll('button')].filter((button) => button.querySelector('strong'))
  : [];

function bindCardIds() {
  cards().forEach((button, index) => {
    const packageId = Number(rows[index]?.id || 0);
    if (packageId > 0) button.setAttribute(PACKAGE_ID_ATTR, String(packageId));
    else button.removeAttribute(PACKAGE_ID_ATTR);
  });
}

async function ok() {
  if (allowed !== null) return allowed;
  try {
    const user = await api('/auth/me');
    allowed = user?.role === 'company_admin' && Number(user?.osgb_id || 0) > 0 && !user?.company_id;
    return allowed;
  } catch {
    allowed = false;
    return false;
  }
}

async function load() {
  rows = await api(C);
  if (!Array.isArray(rows)) rows = [];
  bindCardIds();
  return rows;
}

function visibleDetailTitle() {
  const h = host();
  if (!h) return '';
  return [...h.querySelectorAll('h4')]
    .map((node) => node.textContent?.trim() || '')
    .find(Boolean) || '';
}

function chosen() {
  if (id && rows.some((row) => Number(row.id) === Number(id))) return Number(id);
  bindCardIds();

  const pressed = cards().find((button) => button.getAttribute('aria-pressed') === 'true');
  const pressedId = Number(pressed?.getAttribute(PACKAGE_ID_ATTR) || 0);
  if (pressedId > 0 && rows.some((row) => Number(row.id) === pressedId)) {
    id = pressedId;
    return id;
  }

  const title = visibleDetailTitle();
  if (title) {
    const matches = rows.filter((row) => String(row.title || '').trim() === title);
    if (matches.length === 1) {
      id = Number(matches[0].id);
      return id;
    }
  }

  // Preserve the old first-load behavior without inspecting CSS/theme state.
  id = Number(rows[0]?.id || 0) || null;
  return id;
}

async function get(force = false) {
  if (!rows.length || force) await load();
  const packageId = chosen();
  if (!packageId) return null;
  if (!force && detail && Number(detail.id) === packageId) return detail;
  detail = await api(`${C}/${packageId}`);
  return detail;
}

function sibling(source) {
  return rows.find((row) => !row.is_shared && (
    (source.code && row.code === source.code)
    || String(row.title || '').trim().toLowerCase() === String(source.title || '').trim().toLowerCase()
  ));
}

async function select(packageId) {
  await load();
  id = Number(packageId);
  detail = null;
  const button = cards().find((card) => Number(card.getAttribute(PACKAGE_ID_ATTR) || 0) === id);
  button?.click();
}

async function editable(current = detail) {
  if (!current) throw Error('Eğitim paketi seçilmedi.');
  if (!current.is_shared) return current;
  if (forking) return forking;
  forking = (async () => {
    await load();
    let privatePackage = sibling(current);
    if (!privatePackage) {
      const created = await api(`${C}/${current.id}/fork`, {method: 'POST', _retries: 0});
      privatePackage = {id: created.id};
    }
    await select(privatePackage.id);
    detail = await api(`${C}/${privatePackage.id}`);
    id = Number(privatePackage.id);
    toast('Düzenleme hazır; değişiklikler yalnız bu OSGB için uygulanacak.');
    return detail;
  })().finally(() => { forking = null; });
  return forking;
}

function sectionFor(currentDetail, sourceSection) {
  if (!currentDetail || !sourceSection) return null;
  const sections = currentDetail.sections || [];
  const sourceId = Number(sourceSection.id || 0);
  if (sourceId > 0) {
    const byId = sections.find((item) => Number(item.id) === sourceId);
    if (byId) return byId;
  }
  const code = String(sourceSection.code || '').trim();
  if (!code) return null;
  const matches = sections.filter((item) => String(item.code || '').trim() === code);
  return matches.length === 1 ? matches[0] : null;
}

function videoFor(section, sourceVideo) {
  if (!section || !sourceVideo) return null;
  const videos = section.videos || [];
  const sourceId = Number(sourceVideo.id || 0);
  if (sourceId > 0) {
    const byId = videos.find((item) => Number(item.id) === sourceId);
    if (byId) return byId;
  }

  // A shared package fork receives new database ids. Match the copied video by
  // immutable-ish revision metadata, never by mutable order_index.
  const title = String(sourceVideo.title || '').trim();
  const originalName = String(sourceVideo.original_file_name || '').trim();
  const revision = Number(sourceVideo.revision_no || 1);
  const current = Boolean(sourceVideo.is_current);
  const composite = videos.filter((item) => (
    String(item.title || '').trim() === title
    && String(item.original_file_name || '').trim() === originalName
    && Number(item.revision_no || 1) === revision
    && Boolean(item.is_current) === current
  ));
  if (composite.length === 1) return composite[0];

  const titleMatches = videos.filter((item) => String(item.title || '').trim() === title);
  return titleMatches.length === 1 ? titleMatches[0] : null;
}

async function targets(sourceSection, sourceVideo) {
  const currentDetail = await editable();
  const section = sourceSection ? sectionFor(currentDetail, sourceSection) : null;
  const video = sourceVideo ? videoFor(section, sourceVideo) : null;
  if (sourceSection && !section) throw Error('Bölüm güvenli biçimde eşleştirilemedi.');
  if (sourceVideo && !video) throw Error('Video güvenli biçimde eşleştirilemedi.');
  return [currentDetail, section, video];
}

async function mutate(fn, message) {
  if (busy) return undefined;
  busy = true;
  draw(true);
  try {
    const out = await fn();
    toast(typeof message === 'function' ? message(out) : message);
    await load();
    detail = null;
    await draw(true);
    return out;
  } catch (error) {
    toast(error?.message || 'İşlem tamamlanamadı.', true);
    throw error;
  } finally {
    busy = false;
    draw(true);
  }
}

function pop(title, body, cls = '') {
  document.querySelector('.rtc-pop')?.remove();
  const panel = document.createElement('div');
  panel.className = 'rtc-pop';
  panel.innerHTML = `<div class="rtc-box ${cls}"><div class="rtc-box-h"><h3>${esc(title)}</h3><button class="rtc-close">×</button></div><div class="rtc-box-b"></div></div>`;
  document.body.appendChild(panel);
  panel.querySelector('.rtc-box-b').append(body);
  panel.querySelector('.rtc-close').onclick = () => panel.remove();
  panel.onclick = (event) => { if (event.target === panel) panel.remove(); };
  return panel;
}

function sectionForm(sourceSection) {
  const form = document.createElement('form');
  form.className = 'rtc-form';
  form.innerHTML = `<label>Bölüm kodu<input name="code" required maxlength="64"></label><label>Bölüm adı<input name="title" required maxlength="220"></label><label>Açıklama<textarea name="description"></textarea></label><div class="rtc-form-a"><button type="button">Vazgeç</button><button class="pri" type="submit">Kaydet</button></div>`;
  if (sourceSection) {
    form.code.value = sourceSection.code || '';
    form.title.value = sourceSection.title || '';
    form.description.value = sourceSection.description || '';
  }
  const panel = pop(sourceSection ? 'Bölümü düzenle' : 'Yeni bölüm ekle', form);
  form.querySelector('[type=button]').onclick = () => panel.remove();
  form.onsubmit = async (event) => {
    event.preventDefault();
    const code = form.code.value.trim();
    const title = form.title.value.trim();
    if (code.length < 2 || title.length < 2) return toast('Bölüm kodu ve adı gereklidir.', true);
    try {
      const current = await editable();
      if (sourceSection) {
        const section = sectionFor(current, sourceSection);
        if (!section) throw Error('Bölüm güvenli biçimde eşleştirilemedi.');
        await api(`/trainings/remote/catalog/sections/${section.id}`, {
          method: 'PATCH',
          _retries: 0,
          body: JSON.stringify({
            code,
            title,
            description: form.description.value.trim() || null,
            is_required: true,
          }),
        });
      } else {
        await api(`${C}/${current.id}/sections`, {
          method: 'POST',
          _retries: 0,
          body: JSON.stringify({
            code,
            title,
            description: form.description.value.trim() || null,
            is_required: true,
          }),
        });
      }
      id = Number(current.id);
      panel.remove();
      toast(sourceSection ? 'Bölüm güncellendi.' : 'Bölüm eklendi.');
      await load();
      detail = null;
      draw(true);
    } catch (error) {
      toast(error?.message || 'Bölüm kaydedilemedi.', true);
    }
  };
}

function pick(callback) {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'video/mp4,video/webm,video/quicktime,.m4v';
  input.style.display = 'none';
  input.onchange = () => {
    const file = input.files?.[0];
    input.remove();
    if (file) callback(file);
  };
  document.body.append(input);
  input.click();
}

async function upload(sourceSection, file, sourceVideo = null) {
  return mutate(async () => {
    const [current, section, video] = await targets(sourceSection, sourceVideo);
    const title = video?.title || sourceVideo?.title || file.name.replace(/\.[^.]+$/, '') || 'Eğitim videosu';
    const order = video?.order_index || Math.max(0, ...(section.videos || []).map((item) => Number(item.order_index) || 0)) + 1;
    id = Number(current.id);
    return uploadFile(`/trainings/remote/catalog/sections/${section.id}/videos`, file, {
      title,
      order_index: Number(order),
      is_required: true,
      ...(video ? {revision_of_id: video.id} : {}),
    });
  }, sourceVideo
    ? 'Yeni sürüm yüklendi. Kontrol edip yayımlayın.'
    : 'Video yüklendi. İşleme tamamlanınca yayımlayabilirsiniz.');
}

async function action(sourceSection, sourceVideo, actionName) {
  return mutate(async () => {
    const [current, , video] = await targets(sourceSection, sourceVideo);
    id = Number(current.id);
    return api(`/trainings/remote/catalog/videos/${video.id}/${actionName}`, {method: 'POST', _retries: 0});
  }, (out) => actionName === 'publish'
    ? `Video yayımlandı${Number(out?.live_synced_program_count || 0) ? `; ${out.live_synced_program_count} aktif eğitim güncellendi` : ''}.`
    : actionName === 'unpublish'
      ? 'Video yayından kaldırıldı.'
      : 'İşlem tamamlandı.');
}

async function delVideo(sourceSection, sourceVideo) {
  if (!confirm(`“${sourceVideo.title}” videosu silinsin mi?\n\nYayımlanmışsa aktif eğitimden kaldırılır; geçmiş kayıt korunur.`)) return;
  return mutate(async () => {
    const [current, , video] = await targets(sourceSection, sourceVideo);
    id = Number(current.id);
    return api(`/trainings/remote/catalog/videos/${video.id}`, {method: 'DELETE', _retries: 0});
  }, (out) => out?.message || 'Video silindi.');
}

async function delSec(sourceSection) {
  if (!confirm(`“${sourceSection.code} · ${sourceSection.title}” bölümü silinsin mi?`)) return;
  return mutate(async () => {
    const [current, section] = await targets(sourceSection);
    id = Number(current.id);
    return api(`/trainings/remote/catalog/sections/${section.id}`, {method: 'DELETE', _retries: 0});
  }, 'Bölüm silindi.');
}

async function preview(video) {
  try {
    const out = await api(`/trainings/remote/catalog/videos/${video.id}/playback`);
    const wrapper = document.createElement('div');
    wrapper.className = 'rtc-preview';
    wrapper.innerHTML = `<video controls autoplay src="${esc(abs(out.url))}"></video>`;
    pop(video.title || 'Önizleme', wrapper, 'rtc-preview');
  } catch (error) {
    toast(error?.message || 'Önizleme açılamadı.', true);
  }
}

async function packageAction(actionName) {
  return mutate(async () => {
    const current = await editable();
    id = Number(current.id);
    return api(`${C}/${current.id}/${actionName}`, {method: 'POST', _retries: 0});
  }, actionName === 'publish' ? 'Paket yayımlandı.' : 'Paket durumu güncellendi.');
}

async function reorder(codes) {
  return mutate(async () => {
    const current = await editable();
    const byCode = new Map((current.sections || []).map((section) => [String(section.code || ''), Number(section.id)]));
    const sectionIds = codes.map((code) => byCode.get(String(code))).filter(Boolean);
    if (sectionIds.length !== (current.sections || []).length || new Set(sectionIds).size !== sectionIds.length) {
      throw Error('Bölüm sırası güvenli biçimde doğrulanamadı.');
    }
    id = Number(current.id);
    return api(`${C}/${current.id}/sections/order`, {
      method: 'PATCH',
      _retries: 0,
      body: JSON.stringify({section_ids: sectionIds}),
    });
  }, 'Bölüm sırası kaydedildi.');
}

function videoButtons(video, disabled) {
  const actions = [];
  if (['ready_for_review', 'published', 'unpublished'].includes(video.status)) {
    actions.push(`<button data-va="preview" ${disabled}>Önizle</button>`);
  }
  if (['published', 'unpublished'].includes(video.status) && video.is_current) {
    actions.push(`<button data-va="replace" title="Videoyu değiştir" ${disabled}>Yeni sürüm yükle</button>`);
  }
  if (video.status === 'ready_for_review') actions.push(`<button class="pub" data-va="publish" ${disabled}>Yayımla</button>`);
  if (video.status === 'published') actions.push(`<button data-va="unpublish" ${disabled}>Yayından kaldır</button>`);
  if (video.status === 'processing_failed') actions.push(`<button data-va="retry-processing" ${disabled}>Yeniden işle</button>`);
  actions.push(`<button class="bad" data-va="delete" ${disabled}>Sil</button>`);
  return actions.join('');
}

function html(current) {
  const disabled = busy ? 'disabled' : '';
  const sections = current.sections || [];
  const packageActionHtml = current.status === 'published'
    ? `<button data-pa="unpublish" ${disabled}>Paketi yayından kaldır</button>`
    : current.status === 'archived'
      ? `<button data-pa="restore" ${disabled}>Düzenlemeye aç</button>`
      : `<button class="pub" data-pa="publish" ${disabled}>Paketi yayımla</button>`;

  const sectionHtml = sections.map((section) => {
    const videos = section.videos || [];
    const videoHtml = videos.length
      ? videos.map((video) => `<div class="rtc-v" data-v="${video.id}"><div><strong>${esc(video.title)}</strong><span>${esc(L[video.status] || video.status)} · ${video.duration_seconds ? `${Math.round(video.duration_seconds)} sn` : 'Süre bekleniyor'} · rev. ${Number(video.revision_no) || 1}</span></div><div class="rtc-va">${videoButtons(video, disabled)}</div></div>`).join('')
      : '<div class="rtc-empty">Bu bölümde henüz video yok.</div>';
    return `<article class="rtc-sec" data-section-id="${Number(section.id)}" data-code="${esc(section.code)}"><header class="rtc-sec-head"><div class="rtc-sec-id"><button class="rtc-grab" title="Tut ve taşı" ${disabled}>⋮⋮</button><div class="rtc-sec-name"><strong>${esc(section.code)} · ${esc(section.title)}</strong><span>${videos.length} video</span></div></div><div class="rtc-sec-actions"><button data-sa="edit" ${disabled}>Düzenle</button><button class="bad" data-sa="delete" ${disabled}>Sil</button></div></header><div class="rtc-sec-body"><div class="rtc-upload"><span>Yeni video ekleyin.</span><button class="pri" data-sa="upload" ${disabled}>+ Video yükle</button></div><div class="rtc-vlist">${videoHtml}</div></div></article>`;
  }).join('');

  return `<div class="rtc" ${A}="1" data-id="${current.id}"><div class="rtc-head"><div><span class="rtc-k">OSGB EĞİTİM İÇERİK YÖNETİMİ</span><h3>${esc(current.title)}</h3><div class="rtc-meta"><span>${esc(L[current.status] || current.status)}</span><span>·</span><span>${sections.length} bölüm</span><span>·</span><span>${Number(current.video_count) || sections.reduce((count, section) => count + (section.videos?.length || 0), 0)} video</span></div></div><div class="rtc-actions"><button class="pri" data-top="add" ${current.status === 'archived' ? 'disabled' : disabled}>+ Bölüm ekle</button>${packageActionHtml}</div></div><div class="rtc-note"><strong>${current.is_shared ? 'Hazır paket.' : 'OSGB paketi.'}</strong> ${current.is_shared ? 'İlk düzenlemede sistem otomatik olarak yalnız bu OSGB’ye ait güvenli çalışma kopyasını kullanır; ek bir kopyalama adımı görmezsiniz.' : 'Değişiklikler diğer OSGB’leri etkilemez.'} Bölüm sırası için soldaki ⋮⋮ tutamacını sürükleyin.</div><div class="rtc-list">${sectionHtml || '<div class="rtc-empty">Henüz bölüm yok. “Bölüm ekle” ile başlayın.</div>'}</div></div>`;
}

function bind(element, current) {
  element.querySelector('[data-top=add]')?.addEventListener('click', () => sectionForm());
  element.querySelectorAll('[data-pa]').forEach((button) => {
    button.onclick = () => packageAction(button.dataset.pa).catch(() => {});
  });

  (current.sections || []).forEach((section) => {
    const card = element.querySelector(`.rtc-sec[data-section-id="${Number(section.id)}"]`);
    if (!card) return;
    card.querySelector('[data-sa=edit]').onclick = () => sectionForm(section);
    card.querySelector('[data-sa=delete]').onclick = () => delSec(section).catch(() => {});
    card.querySelector('[data-sa=upload]').onclick = () => pick((file) => upload(section, file).catch(() => {}));
    (section.videos || []).forEach((video) => {
      const row = card.querySelector(`[data-v="${video.id}"]`);
      row?.querySelectorAll('[data-va]').forEach((button) => {
        button.onclick = () => {
          const actionName = button.dataset.va;
          if (actionName === 'preview') preview(video);
          else if (actionName === 'replace') pick((file) => upload(section, file, video).catch(() => {}));
          else if (actionName === 'delete') delVideo(section, video).catch(() => {});
          else action(section, video, actionName).catch(() => {});
        };
      });
    });
  });
  drag(element);
}

function drag(element) {
  const box = element.querySelector('.rtc-list');
  let moving = null;
  let start = null;

  const codesFromDom = () => [...box.querySelectorAll('.rtc-sec')].map((node) => node.dataset.code);
  const clear = () => {
    element.querySelectorAll('.rtc-sec').forEach((node) => node.classList.remove('drag', 'over'));
  };

  element.querySelectorAll('.rtc-sec').forEach((card) => {
    const handle = card.querySelector('.rtc-grab');
    handle.draggable = !busy;
    handle.ondragstart = (event) => {
      if (busy) return event.preventDefault();
      moving = card;
      start = codesFromDom();
      card.classList.add('drag');
      if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
    };
    handle.ondragend = () => {
      const before = start ? [...start] : [];
      const after = codesFromDom();
      const changed = Boolean(moving && before.length && after.length && before.join(',') !== after.join(','));
      clear();
      moving = null;
      start = null;
      if (changed) reorder(after).catch(() => {});
    };
    card.ondragover = (event) => {
      if (!moving || moving === card) return;
      event.preventDefault();
      element.querySelectorAll('.rtc-sec').forEach((node) => node.classList.remove('over'));
      card.classList.add('over');
      const rect = card.getBoundingClientRect();
      const before = event.clientY < rect.top + rect.height / 2;
      box.insertBefore(moving, before ? card : card.nextSibling);
    };
    card.ondrop = (event) => {
      if (!moving) return;
      event.preventDefault();
      const codes = codesFromDom();
      clear();
      moving = null;
      start = null;
      reorder(codes).catch(() => {});
    };
  });
}

function scheduleProcessingRefresh(current) {
  clearTimeout(pollTimer);
  pollTimer = null;
  const pending = (current.sections || []).some((section) => (
    section.videos || []
  ).some((video) => ['uploading', 'processing'].includes(video.status)));
  if (pending) {
    pollTimer = setTimeout(() => {
      detail = null;
      schedule(true);
    }, 2500);
  }
}

async function draw(force = false) {
  if (!(await ok())) return;
  const h = host();
  if (!h) return;
  css();
  try {
    const current = await get(force);
    if (!current) return;
    const old = h.querySelector(`[${A}]`);
    if (!force && old && Number(old.dataset.id) === Number(current.id)) {
      scheduleProcessingRefresh(current);
      return;
    }
    h.classList.add(H);
    old?.remove();
    const wrapper = document.createElement('div');
    wrapper.innerHTML = html(current);
    const element = wrapper.firstElementChild;
    h.appendChild(element);
    bind(element, current);
    scheduleProcessingRefresh(current);
  } catch (error) {
    toast(error?.message || 'İçerik yönetimi yüklenemedi.', true);
  }
}

function schedule(force = false) {
  clearTimeout(timer);
  timer = setTimeout(() => draw(force), force ? 30 : 140);
}

document.addEventListener('click', (event) => {
  const button = event.target.closest?.('button');
  if (!button) return;

  const explicitId = Number(button.getAttribute(PACKAGE_ID_ATTR) || 0);
  if (explicitId > 0) {
    id = explicitId;
    detail = null;
    schedule(true);
    return;
  }

  const packageCards = cards();
  const index = packageCards.indexOf(button);
  if (index >= 0) {
    load().then((loadedRows) => {
      id = Number(loadedRows[index]?.id || 0) || null;
      detail = null;
      bindCardIds();
      schedule(true);
    });
    return;
  }

  if (button.textContent?.trim() === 'Paketleri yenile') {
    rows = [];
    detail = null;
    schedule(true);
  }
}, true);

new MutationObserver(() => {
  bindCardIds();
  schedule();
}).observe(document.documentElement, {childList: true, subtree: true});

addEventListener('hashchange', () => {
  clearTimeout(pollTimer);
  pollTimer = null;
  rows = [];
  id = null;
  detail = null;
  schedule(true);
});

addEventListener('isg:auth-lost', () => {
  clearTimeout(pollTimer);
  pollTimer = null;
  allowed = null;
  rows = [];
  id = null;
  detail = null;
  document.querySelectorAll(`.${H}`).forEach((node) => node.classList.remove(H));
});

schedule(true);