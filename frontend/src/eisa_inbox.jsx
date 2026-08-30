import React, { useEffect, useState } from 'react';
import { Inbox, Search } from 'lucide-react';
import { api } from './api';
import { AppModal } from './ui_modal';
import { Msg, RefreshButton } from './eisa';

function dateLabel(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('tr-TR');
}

function inboxStatus(inbound) {
  if (!inbound?.enabled) return 'Gelen kutusu bağlantısı Render’da henüz etkinleştirilmemiş.';
  if (!inbound?.configured) return 'Gelen kutusu için IMAP kullanıcı adı ve gizli parola ayarı bekleniyor.';
  return 'İsimtescil gelen kutusu bağlantısı hazır.';
}

export function EisaInboxPanel({ active, refreshToken = 0 }) {
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: 25, pages: 0 });
  const [summary, setSummary] = useState(null);
  const [filters, setFilters] = useState({ q: '', unread_only: false });
  const [applied, setApplied] = useState({ q: '', unread_only: false });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [detail, setDetail] = useState(null);

  async function load(page = 1, nextFilters = applied) {
    setBusy(true);
    setMsg('');
    try {
      const sync = await api('/eisa/emails/inbox/sync', { method: 'POST', timeoutMs: 35_000 });
      const params = new URLSearchParams({ page: String(page), page_size: '25' });
      if (nextFilters.q.trim()) params.set('q', nextFilters.q.trim());
      if (nextFilters.unread_only) params.set('unread_only', 'true');
      const [nextSummary, nextData] = await Promise.all([
        api('/eisa/emails/summary'),
        api(`/eisa/emails/inbox?${params.toString()}`),
      ]);
      setSummary(nextSummary);
      setData(nextData);
      if (sync?.error) setMsg(sync.error);
    } catch (error) {
      setMsg(error.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (active) void load();
  }, [active, refreshToken]);

  function submit(event) {
    event.preventDefault();
    const next = { ...filters };
    setApplied(next);
    void load(1, next);
  }

  function resetFilters() {
    const next = { q: '', unread_only: false };
    setFilters(next);
    setApplied(next);
    void load(1, next);
  }

  async function openMessage(row) {
    setBusy(true);
    try {
      const message = await api(`/eisa/emails/inbox/${row.id}`);
      setDetail(message);
      if (!row.is_read) {
        await api(`/eisa/emails/inbox/${row.id}/read`, { method: 'PATCH' });
        setData((current) => ({
          ...current,
          items: current.items.map((item) => item.id === row.id ? { ...item, is_read: true } : item),
        }));
      }
    } catch (error) {
      setMsg(error.message);
    } finally {
      setBusy(false);
    }
  }

  const inbound = summary?.inbound || {};
  const configured = Boolean(inbound.configured);

  return (
    <section aria-label="Gelen e-postalar">
      <Msg text={msg} />
      <div
        role="status"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '12px 14px',
          marginBottom: 16,
          borderRadius: 12,
          border: `1px solid ${configured ? '#bbf7d0' : '#fde68a'}`,
          background: configured ? '#f0fdf4' : '#fffbeb',
          color: configured ? '#166534' : '#92400e',
        }}
      >
        <Inbox size={18} />
        <span>{inboxStatus(inbound)}{inbound.host ? ` (${inbound.host})` : ''}</span>
      </div>

      <form className="form-grid" onSubmit={submit} style={{ marginBottom: 18 }}>
        <label className="field" style={{ minWidth: 260 }}>
          <span>Gelen kutusunda ara</span>
          <input
            value={filters.q}
            onChange={(event) => setFilters({ ...filters, q: event.target.value })}
            placeholder="Gönderen, konu veya içerik…"
          />
        </label>
        <label className="field" style={{ alignSelf: 'end', display: 'flex', alignItems: 'center', gap: 8 }}>
          <input
            type="checkbox"
            checked={filters.unread_only}
            onChange={(event) => setFilters({ ...filters, unread_only: event.target.checked })}
          />
          <span>Yalnızca okunmamışlar</span>
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
              <th>Durum</th>
              <th>Tarih</th>
              <th>Gönderen</th>
              <th>Konu</th>
              <th>Ek</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.items.length ? data.items.map((row) => (
              <tr key={row.id}>
                <td>{row.is_read ? 'Okundu' : <strong>Yeni</strong>}</td>
                <td>{dateLabel(row.received_at || row.synced_at)}</td>
                <td>
                  <strong>{row.sender_name || row.sender_email || 'Bilinmeyen gönderici'}</strong>
                  {row.sender_name && <><br /><small>{row.sender_email || '—'}</small></>}
                </td>
                <td>{row.subject || '(Konu yok)'}</td>
                <td>{row.has_attachments ? `${row.attachment_count} ek` : '—'}</td>
                <td><button type="button" className="secondary mini" onClick={() => void openMessage(row)}>Aç</button></td>
              </tr>
            )) : (
              <tr><td colSpan={6} className="empty">Gelen e-posta bulunamadı.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="actions" style={{ justifyContent: 'space-between', marginTop: 14 }}>
        <span className="muted">{data.total} mesaj · {summary?.inbox_unread ?? 0} okunmamış · Sayfa {data.pages ? data.page : 0}/{data.pages || 0}</span>
        <div className="actions">
          <button type="button" className="secondary" disabled={busy || data.page <= 1} onClick={() => void load(data.page - 1)}>Önceki</button>
          <button type="button" className="secondary" disabled={busy || !data.pages || data.page >= data.pages} onClick={() => void load(data.page + 1)}>Sonraki</button>
        </div>
      </div>

      {detail && (
        <AppModal title={detail.subject || 'Gelen e-posta'} close={() => setDetail(null)}>
          <div className="form-grid">
            <p><strong>Gönderen:</strong> {detail.sender_name || '—'} · {detail.sender_email || '—'}</p>
            <p><strong>Alıcı:</strong> {detail.recipients || '—'}</p>
            <p><strong>Tarih:</strong> {dateLabel(detail.received_at || detail.synced_at)}</p>
            <p><strong>Ek:</strong> {detail.has_attachments ? `${detail.attachment_count} adet` : 'Yok'}</p>
            <div style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', maxHeight: '55vh', overflowY: 'auto', padding: 14, borderRadius: 10, background: '#f8fafc' }}>
              {detail.body_text || 'Bu e-postada okunabilir metin bulunamadı.'}
            </div>
            <p className="muted" style={{ marginBottom: 0 }}>
              Güvenlik için HTML içeriği ve ek dosyalar bu ilk sürümde çalıştırılmaz; yalnızca güvenli metin görünür.
            </p>
          </div>
        </AppModal>
      )}
    </section>
  );
}
