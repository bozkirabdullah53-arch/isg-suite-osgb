import React, {useEffect, useMemo, useState} from 'react';
import {CheckCircle2, ClipboardList, Plus, RefreshCw, ShieldCheck, XCircle} from 'lucide-react';
import {api} from './api';
import {
  allowedActions,
  channelLabel,
  dataSubjectKindOptions,
  entityTypeLabel,
  formatDateTime,
  requestKindLabel,
  requesterTypeLabel,
  slaLabel,
  slaState,
  statusLabel,
} from './change_requests_logic';
import './change_requests.css';

const OPEN_STATUSES = ['submitted', 'verified', 'approved'];

/**
 * İBYS Değişiklik Talebi ekranı (§3-§5).
 *
 * Talep açma, doğrulama, onay, uygulama, red ve KVKK veri sahibi başvuruları.
 * 4 göz prensibi backend'de zorlanır; burada yalnızca yetkisiz düğmeler gizlenir.
 */
export function ChangeRequestsPage({user}) {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [filter, setFilter] = useState('');
  const [detail, setDetail] = useState(null);
  const [form, setForm] = useState({
    kind: 'correction',
    target_entity_type: 'employee',
    target_entity_id: '',
    field_name: '',
    old_value: '',
    requested_value: '',
    justification: '',
    company_id: '',
  });

  const isDataSubject = form.kind === 'data_subject';

  async function load() {
    setError('');
    try {
      const query = filter ? `?status=${encodeURIComponent(filter)}` : '';
      setRows((await api(`/change-requests${query}`)) || []);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    load();
  }, [filter]);

  const overdueCount = useMemo(
    () => rows.filter((row) => slaState(row).state === 'overdue').length,
    [rows],
  );

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setNotice('');
    try {
      if (isDataSubject) {
        await api('/change-requests/data-subject', {
          method: 'POST',
          body: JSON.stringify({
            request_kind: form.kind,
            company_id: Number(form.company_id),
            employee_id: form.target_entity_id ? Number(form.target_entity_id) : null,
            target_entity_type: 'employee',
            target_entity_id: form.target_entity_id || null,
            field_name: form.field_name || null,
            old_value: form.old_value || null,
            requested_value: form.requested_value || '-',
            justification: form.justification,
          }),
        });
      } else {
        await api('/change-requests', {
          method: 'POST',
          body: JSON.stringify({
            target_entity_type: form.target_entity_type,
            target_entity_id: form.target_entity_id || null,
            field_name: form.field_name || null,
            old_value: form.old_value || null,
            requested_value: form.requested_value,
            justification: form.justification,
            company_id: form.company_id ? Number(form.company_id) : null,
          }),
        });
      }
      setNotice('Talep oluşturuldu ve numara atandı.');
      setForm({...form, target_entity_id: '', field_name: '', old_value: '', requested_value: '', justification: ''});
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function act(row, action) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      if (action === 'reject') {
        const reason = window.prompt('Reddetme gerekçesi (en az 10 karakter):');
        if (!reason) return;
        await api(`/change-requests/${row.id}/reject`, {method: 'POST', body: JSON.stringify({reason})});
      } else if (action === 'cancel') {
        await api(`/change-requests/${row.id}/cancel`, {method: 'POST', body: JSON.stringify({note: 'Kullanıcı iptal etti.'})});
      } else {
        await api(`/change-requests/${row.id}/${action}`, {method: 'POST', body: JSON.stringify({})});
      }
      setNotice(`İşlem tamamlandı: ${action}`);
      await load();
      if (detail?.id === row.id) setDetail(await api(`/change-requests/${row.id}`));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function openDetail(row) {
    setError('');
    try {
      setDetail(await api(`/change-requests/${row.id}`));
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="change-requests-page">
      <div className="change-requests-head">
        <div>
          <h1>Değişiklik Talepleri</h1>
          <p>Veri düzeltme, silme ve KVKK başvurularını gerekçeli, onaylı ve kayıtlı biçimde yönetin.</p>
        </div>
        <button type="button" className="secondary" onClick={load} disabled={busy}>
          <RefreshCw size={16}/> Yenile
        </button>
      </div>

      {error && <div className="alert error">{error}</div>}
      {notice && <div className="alert success">{notice}</div>}

      <div className="cr-policy">
        <ShieldCheck size={22}/>
        <div>
          <strong>4 göz prensibi ve denetim izi</strong>
          <span>
            Talebi açan kişi kendi talebini onaylayamaz; doğrulayan onaylayamaz; onaylayan uygulayamaz.
            Her adım denetim kaydına (audit_logs) yazılır ve değişiklikler geri alınamaz biçimde izlenir.
          </span>
          <span>Son tarihi geçen açık talep: <strong>{overdueCount}</strong></span>
        </div>
      </div>

      <form className="cr-form" onSubmit={submit}>
        <h2><Plus size={16}/> Yeni talep</h2>
        <div className="cr-grid">
          <label>Talep türü
            <select value={form.kind} onChange={(e) => setForm({...form, kind: e.target.value})}>
              <option value="correction">Veri düzeltme</option>
              <option value="data_subject">KVKK veri sahibi başvurusu</option>
            </select>
          </label>
          {isDataSubject && (
            <label>Başvuru konusu
              <select value={form.request_kind || 'access'} onChange={(e) => setForm({...form, request_kind: e.target.value})}>
                {dataSubjectKindOptions().map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
          )}
          <label>Hedef kayıt türü
            <select
              value={form.target_entity_type}
              disabled={isDataSubject}
              onChange={(e) => setForm({...form, target_entity_type: e.target.value})}
            >
              <option value="employee">Personel</option>
              <option value="company">İşyeri</option>
              <option value="incident">Olay / İş Kazası</option>
            </select>
          </label>
          <label>Kayıt numarası (ID)
            <input
              value={form.target_entity_id}
              onChange={(e) => setForm({...form, target_entity_id: e.target.value})}
              placeholder="örn. 145"
              required={isDataSubject}
            />
          </label>
          <label>Alan adı
            <input
              value={form.field_name}
              onChange={(e) => setForm({...form, field_name: e.target.value})}
              placeholder="örn. job_title"
              disabled={isDataSubject}
            />
          </label>
          <label>Mevcut değer
            <input value={form.old_value} onChange={(e) => setForm({...form, old_value: e.target.value})}/>
          </label>
          <label>İstenen yeni değer
            <input
              value={form.requested_value}
              onChange={(e) => setForm({...form, requested_value: e.target.value})}
              required={!isDataSubject}
            />
          </label>
          <label>Firma numarası (ID)
            <input
              value={form.company_id}
              onChange={(e) => setForm({...form, company_id: e.target.value})}
              placeholder="örn. 12"
            />
          </label>
        </div>
        <label className="cr-full">Gerekçe (zorunlu, en az 10 karakter)
          <textarea
            rows={3}
            value={form.justification}
            onChange={(e) => setForm({...form, justification: e.target.value})}
            required
            minLength={10}
            placeholder="Talebin yasal veya operasyonel gerekçesini yazın."
          />
        </label>
        <button type="submit" disabled={busy}>{busy ? 'Gönderiliyor…' : 'Talebi oluştur'}</button>
      </form>

      <div className="cr-toolbar">
        <label>Durum filtresi
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="">Tümü</option>
            {OPEN_STATUSES.map((status) => <option key={status} value={status}>{statusLabel(status)}</option>)}
            <option value="applied">Uygulandı</option>
            <option value="rejected">Reddedildi</option>
            <option value="cancelled">İptal Edildi</option>
          </select>
        </label>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Talep No</th><th>Kapsam</th><th>Tür</th><th>Durum</th><th>SLA</th><th>İşlem</th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? rows.map((row) => {
              const actions = allowedActions(row, user || {});
              return (
                <tr key={row.id}>
                  <td><button type="button" className="link" onClick={() => openDetail(row)}>{row.request_no}</button></td>
                  <td>{entityTypeLabel(row.target_entity_type)}<small>{requesterTypeLabel(row.requester_type)}</small></td>
                  <td>{row.request_kind ? requestKindLabel(row.request_kind) : (row.field_name || '—')}<small>{channelLabel(row.channel)}</small></td>
                  <td><span className={`cr-state ${row.status}`}>{statusLabel(row.status)}</span></td>
                  <td><span className={`cr-sla ${slaState(row).state}`}>{slaLabel(row)}</span></td>
                  <td className="cr-actions">
                    {actions.includes('verify') && <button type="button" className="mini" onClick={() => act(row, 'verify')}><CheckCircle2 size={14}/> Doğrula</button>}
                    {actions.includes('approve') && <button type="button" className="mini" onClick={() => act(row, 'approve')}><CheckCircle2 size={14}/> Onayla</button>}
                    {actions.includes('apply') && <button type="button" className="mini" onClick={() => act(row, 'apply')}><ClipboardList size={14}/> Uygula</button>}
                    {actions.includes('reject') && <button type="button" className="mini secondary" onClick={() => act(row, 'reject')}><XCircle size={14}/> Reddet</button>}
                    {actions.includes('cancel') && <button type="button" className="mini secondary" onClick={() => act(row, 'cancel')}>İptal</button>}
                    {!actions.length && <span className="muted">İşlem yok</span>}
                  </td>
                </tr>
              );
            }) : <tr><td colSpan="6" className="empty">Talep bulunamadı.</td></tr>}
          </tbody>
        </table>
      </div>

      {detail && (
        <div className="cr-detail">
          <div className="cr-detail-head">
            <h3>{detail.request_no} · {statusLabel(detail.status)}</h3>
            <button type="button" className="mini secondary" onClick={() => setDetail(null)}>Kapat</button>
          </div>
          <p><strong>Gerekçe:</strong> {detail.justification}</p>
          <p><strong>İstenen değer:</strong> {detail.requested_value}</p>
          <p><strong>Eski değer:</strong> {detail.old_value || '—'}</p>
          <h4>Durum geçmişi</h4>
          <ul className="cr-timeline">
            {(detail.events || []).map((event) => (
              <li key={event.id}>
                <span>{formatDateTime(event.created_at)}</span>
                <strong>{statusLabel(event.to_status)}</strong>
                {event.note && <em>{event.note}</em>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
