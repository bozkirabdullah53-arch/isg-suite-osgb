import React, { useEffect, useState } from 'react';
import { Inbox, Mail, Search } from 'lucide-react';
import { api } from './api';
import { AppModal } from './ui_modal';
import { MetricGrid, Msg, Page, RefreshButton, StatusBadge } from './eisa';
import { EisaInboxPanel } from './eisa_inbox';

const EVENT_LABELS = {
  password_reset: 'Şifre sıfırlama',
  osgb_account_approved: 'OSGB hesabı onayı',
  eisa_notification: 'EİSA bildirimi',
  annual_evaluation: 'Yıllık değerlendirme',
  'annual_evaluation_submit-specialist': 'Yıllık değerlendirme · hekim onayı',
  'annual_evaluation_approve-physician': 'Yıllık değerlendirme · işveren onayı',
  'annual_evaluation_approve-employer': 'Yıllık değerlendirme · tamamlandı',
  'annual_evaluation_request-revision': 'Yıllık değerlendirme · revizyon',
  generic: 'Genel e-posta',
};

const EVENT_OPTIONS = [
  ['password_reset', EVENT_LABELS.password_reset],
  ['osgb_account_approved', EVENT_LABELS.osgb_account_approved],
  ['eisa_notification', EVENT_LABELS.eisa_notification],
  ['annual_evaluation_submit-specialist', EVENT_LABELS['annual_evaluation_submit-specialist']],
  ['annual_evaluation_approve-physician', EVENT_LABELS['annual_evaluation_approve-physician']],
  ['annual_evaluation_approve-employer', EVENT_LABELS['annual_evaluation_approve-employer']],
  ['annual_evaluation_request-revision', EVENT_LABELS['annual_evaluation_request-revision']],
  ['generic', EVENT_LABELS.generic],
];

const PROVIDER_LABELS = {
  resend_smtp: 'Resend SMTP',
  smtp: 'SMTP',
};

function eventLabel(value) {
  if (EVENT_LABELS[value]) return EVENT_LABELS[value];
  if (value?.startsWith('annual_evaluation_')) {
    return `Yıllık değerlendirme · ${value.slice('annual_evaluation_'.length)}`;
  }
  return value || '—';
}

function dateLabel(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('tr-TR');
}

function providerLabel(value) {
  return PROVIDER_LABELS[value] || value || '—';
}

export function EisaEmailCenterPage() {
  const [summary, setSummary] = useState(null);
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: 25, pages: 0 });
  const [filters, setFilters] = useState({ q: '', status: '', event_type: '' });
  const [applied, setApplied] = useState({ q: '', status: '', event_type: '' });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [detail, setDetail] = useState(null);
  const [section, setSection] = useState('sent');
  const [inboxRefreshToken, setInboxRefreshToken] = useState(0);

  async function load(page = 1, nextFilters = applied) {
    setBusy(true);
    setMsg('');
    try {
      const params = new URLSearchParams({ page: String(page), page_size: '25' });
      if (nextFilters.q.trim()) params.set('q', nextFilters.q.trim());
      if (nextFilters.status) params.set('status', nextFilters.status);
      if (nextFilters.event_type) params.set('event_type', nextFilters.event_type);
      const [nextSummary, nextData] = await Promise.all([
        api('/eisa/emails/summary'),
        api(`/eisa/emails?${params.toString()}`),
      ]);
      setSummary(nextSummary);
      setData(nextData);
    } catch (error) {
      setMsg(error.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(); }, []);

  function submit(event) {
    event.preventDefault();
    const next = { ...filters };
    setApplied(next);
    void load(1, next);
  }

  function resetFilters() {
    const next = { q: '', status: '', event_type: '' };
    setFilters(next);
    setApplied(next);
    void load(1, next);
  }

  return (
    <Page
      title="E-posta Merkezi"
      action={(
        <div className="actions">
          <RefreshButton busy={busy} onClick={() => section === 'sent' ? load(data.page) : setInboxRefreshToken((value) => value + 1)} />
        </div>
      )}
    >
      <Msg text={msg} />
      <div className="actions" style={{ marginBottom: 18 }} role="tablist" aria-label="E-posta bölümleri">
        <button type="button" className={section === 'sent' ? '' : 'secondary'} onClick={() => setSection('sent')} role="tab" aria-selected={section === 'sent'}>
          <Mail size={16} /> Gönderilenler
        </button>
        <button type="button" className={section === 'inbox' ? '' : 'secondary'} onClick={() => setSection('inbox')} role="tab" aria-selected={section === 'inbox'}>
          <Inbox size={16} /> Gelen Kutusu {summary?.inbox_unread ? `(${summary.inbox_unread})` : ''}
        </button>
      </div>
      {summary && (
        <>
          <MetricGrid items={[
            { label: 'Toplam kayıt', value: summary.total },
            { label: 'Başarılı', value: summary.sent },
            { label: 'Başarısız', value: summary.failed },
            { label: 'Son 24 saat', value: summary.last_24_hours },
          ]} />
          <div
            role="status"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '12px 14px',
              marginBottom: 16,
              borderRadius: 12,
              border: `1px solid ${summary.smtp_configured ? '#bbf7d0' : '#fde68a'}`,
              background: summary.smtp_configured ? '#f0fdf4' : '#fffbeb',
              color: summary.smtp_configured ? '#166534' : '#92400e',
            }}
          >
            <Mail size={18} />
            <span>
              Sağlayıcı: <strong>{providerLabel(summary.provider)}</strong>
              {' · '}
              {summary.smtp_configured
                ? 'E-posta gönderim ayarları hazır.'
                : 'SMTP ayarları hazır değil; denemeler başarısız olarak kaydedilir.'}
            </span>
          </div>
        </>
      )}

      {section === 'inbox' && <EisaInboxPanel active refreshToken={inboxRefreshToken} />}

      {section === 'sent' && <>
      <form className="form-grid" onSubmit={submit} style={{ marginBottom: 18 }}>
        <label className="field" style={{ minWidth: 220 }}>
          <span>Arama</span>
          <input
            value={filters.q}
            onChange={(event) => setFilters({ ...filters, q: event.target.value })}
            placeholder="Alıcı, konu veya olay…"
          />
        </label>
        <label className="field">
          <span>Durum</span>
          <select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}>
            <option value="">Tüm durumlar</option>
            <option value="sent">Başarılı</option>
            <option value="failed">Başarısız</option>
            <option value="queued">Kuyrukta</option>
          </select>
        </label>
        <label className="field">
          <span>Olay türü</span>
          <select value={filters.event_type} onChange={(event) => setFilters({ ...filters, event_type: event.target.value })}>
            <option value="">Tüm olaylar</option>
            {EVENT_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <div className="form-actions" style={{ alignSelf: 'end', display: 'flex', gap: 8 }}>
          <button type="submit" disabled={busy}><Search size={16} /> Filtrele</button>
          <button type="button" className="secondary" disabled={busy} onClick={resetFilters}>Temizle</button>
        </div>
      </form>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Tarih</th>
              <th>Olay</th>
              <th>Alıcı</th>
              <th>Konu</th>
              <th>Sağlayıcı</th>
              <th>Durum</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.items.length ? data.items.map((row) => (
              <tr key={row.id}>
                <td>{dateLabel(row.created_at)}</td>
                <td>{eventLabel(row.event_type)}</td>
                <td>
                  <strong>{row.recipient_name || '—'}</strong>
                  <br />
                  <small>{row.recipient_email || 'Alıcı yok'}</small>
                </td>
                <td>{row.subject || '—'}</td>
                <td>{providerLabel(row.provider)}</td>
                <td><StatusBadge status={row.status} /></td>
                <td>
                  <button type="button" className="secondary mini" onClick={() => setDetail(row)}>Detay</button>
                </td>
              </tr>
            )) : (
              <tr><td colSpan={7} className="empty">E-posta kaydı bulunamadı.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="actions" style={{ justifyContent: 'space-between', marginTop: 14 }}>
        <span className="muted">{data.total} kayıt · Sayfa {data.pages ? data.page : 0}/{data.pages || 0}</span>
        <div className="actions">
          <button type="button" className="secondary" disabled={busy || data.page <= 1} onClick={() => load(data.page - 1)}>Önceki</button>
          <button type="button" className="secondary" disabled={busy || !data.pages || data.page >= data.pages} onClick={() => load(data.page + 1)}>Sonraki</button>
        </div>
      </div>

      {detail && (
        <AppModal title={`E-posta kaydı #${detail.id}`} close={() => setDetail(null)}>
          <div className="form-grid">
            <p><strong>Olay:</strong> {eventLabel(detail.event_type)}</p>
            <p><strong>Alıcı:</strong> {detail.recipient_name || '—'} · {detail.recipient_email || '—'}</p>
            <p><strong>Konu:</strong> {detail.subject || '—'}</p>
            <p><strong>Sağlayıcı:</strong> {providerLabel(detail.provider)}</p>
            <p><strong>Oluşturulma:</strong> {dateLabel(detail.created_at)}</p>
            <p><strong>Gönderim:</strong> {dateLabel(detail.sent_at)}</p>
            <p><strong>İlişkili kayıt:</strong> {detail.related_type || '—'} / {detail.related_id || '—'}</p>
            {detail.error_code && <p><strong>Hata kodu:</strong> {detail.error_code}</p>}
            {detail.error_message && <p><strong>Hata açıklaması:</strong> {detail.error_message}</p>}
            <p className="muted" style={{ marginBottom: 0 }}>
              Güvenlik nedeniyle e-posta gövdesi, parola ve sıfırlama tokenı saklanmaz.
            </p>
          </div>
        </AppModal>
      )}
      </>}
    </Page>
  );
}
