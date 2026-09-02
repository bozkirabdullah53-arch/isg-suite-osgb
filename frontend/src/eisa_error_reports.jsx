import React, { useEffect, useState } from 'react';
import { api } from './api';
import { AppModal } from './ui_modal';
import { Msg, Page, RefreshButton } from './eisa.jsx';

export function EisaErrorReportsPage() {
  const sourceLabels = {
    ui_crash: 'Sayfa çökmesi',
    api_error: 'API hatası',
    user_report: 'Kullanıcı bildirimi',
  };
  const statusLabelsMap = {
    open: 'Açık',
    investigating: 'İnceleniyor',
    resolved: 'Çözüldü',
    ignored: 'Yok sayıldı',
  };
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [status, setStatus] = useState('open');
  const [source, setSource] = useState('');
  const [q, setQ] = useState('');
  const [detail, setDetail] = useState(null);
  const [edit, setEdit] = useState({ status: 'open', admin_note: '', admin_reply: '' });

  const load = async () => {
    setBusy(true);
    setMsg('');
    try {
      const p = new URLSearchParams();
      if (status) p.set('status', status);
      if (source) p.set('source', source);
      if (q.trim()) p.set('q', q.trim());
      const data = await api(`/eisa/error-reports?${p}`);
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { void load(); }, [status, source]);

  function openDetail(row) {
    setDetail(row);
    setEdit({
      status: row.status || 'open',
      admin_note: row.admin_note || '',
      admin_reply: row.admin_reply || '',
    });
  }

  async function saveDetail(e) {
    e.preventDefault();
    if (!detail) return;
    setBusy(true);
    try {
      await api(`/eisa/error-reports/${detail.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          status: edit.status,
          admin_note: edit.admin_note || null,
          admin_reply: edit.admin_reply || null,
        }),
      });

      // Başarılı kayıt sonrası detay penceresini kapat; kullanıcı hata raporu listesinde kalsın.
      setDetail(null);
      await load();
      setMsg('Rapor güncellendi.');
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Page
      title="Hata Raporları"
      action={<RefreshButton busy={busy} onClick={load} />}
    >
      <Msg text={msg} />
      <p style={{ marginTop: 0, color: '#64748b' }}>
        Kullanıcıların yaşadığı sayfa/API hataları ve manuel sorun bildirimleri. Durum güncelleyip iç not / yanıt bırakabilirsiniz.
      </p>
      <div className="actions" style={{ marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        {[
          ['open', 'Açık'],
          ['investigating', 'İnceleniyor'],
          ['resolved', 'Çözüldü'],
          ['ignored', 'Yok sayıldı'],
          ['', 'Tümü'],
        ].map(([value, label]) => (
          <button
            key={value || 'all'}
            type="button"
            className={status === value ? '' : 'secondary'}
            onClick={() => setStatus(value)}
          >
            {label}
          </button>
        ))}
        <select value={source} onChange={(e) => setSource(e.target.value)} style={{ minWidth: 160 }}>
          <option value="">Tüm kaynaklar</option>
          <option value="ui_crash">Sayfa çökmesi</option>
          <option value="api_error">API hatası</option>
          <option value="user_report">Kullanıcı bildirimi</option>
        </select>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Ara…"
          style={{ minWidth: 180 }}
        />
        <button type="button" className="secondary" onClick={load}>Filtrele</button>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Tarih</th>
              <th>Kaynak</th>
              <th>Kullanıcı</th>
              <th>OSGB</th>
              <th>Başlık</th>
              <th>HTTP</th>
              <th>Adet</th>
              <th>Durum</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={9} style={{ color: '#64748b' }}>Kayıt yok.</td></tr>
            ) : rows.map((r) => (
              <tr key={r.id}>
                <td>{r.created_at ? new Date(r.created_at).toLocaleString('tr-TR') : '—'}</td>
                <td>{sourceLabels[r.source] || r.source}</td>
                <td>
                  <div>{r.user_email || '—'}</div>
                  <div style={{ fontSize: 12, color: '#64748b' }}>{r.user_role || ''}</div>
                </td>
                <td>{r.osgb_name || (r.osgb_id ? `#${r.osgb_id}` : '—')}</td>
                <td>{r.title}</td>
                <td>{r.http_status ? `${r.http_status} ${r.http_path || ''}` : (r.http_path || '—')}</td>
                <td>{r.occurrence_count || 1}</td>
                <td>{statusLabelsMap[r.status] || r.status}</td>
                <td>
                  <button type="button" className="secondary" onClick={() => openDetail(r)}>Detay</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {detail && (
        <AppModal
          title={`Rapor #${detail.id}`}
          close={() => setDetail(null)}
          className="error-report-modal"
        >
          <div className="error-report-modal__body">
            <section className="error-report-modal__summary" aria-label="Rapor özeti">
              <div className="error-report-modal__summary-grid">
                <div className="error-report-modal__meta">
                  <span>Kaynak</span>
                  <strong>{sourceLabels[detail.source] || detail.source || '—'}</strong>
                </div>
                <div className="error-report-modal__meta">
                  <span>OSGB</span>
                  <strong className="error-report-modal__value--wrap">{detail.osgb_name || '—'}</strong>
                </div>
                <div className="error-report-modal__meta error-report-modal__meta--wide">
                  <span>Kullanıcı</span>
                  <strong className="error-report-modal__value--wrap">{detail.user_email || '—'}</strong>
                  <small>{detail.user_role || '—'}</small>
                </div>
                <div className="error-report-modal__meta">
                  <span>Sayfa</span>
                  <strong className="error-report-modal__value--wrap">{detail.page_path || '—'}</strong>
                </div>
              </div>

              <div className="error-report-modal__request">
                <span>İstek</span>
                <code
                  title={[detail.http_method, detail.http_path, detail.http_status].filter(Boolean).join(' ') || undefined}
                >
                  {[detail.http_method, detail.http_path, detail.http_status].filter(Boolean).join(' ') || '—'}
                </code>
              </div>

              <div className="error-report-modal__message">
                <span>Mesaj</span>
                <p>{detail.message || '—'}</p>
              </div>

              {detail.user_note ? (
                <div className="error-report-modal__message">
                  <span>Kullanıcı notu</span>
                  <p>{detail.user_note}</p>
                </div>
              ) : null}

              {detail.stack_trace ? (
                <details className="error-report-modal__technical">
                  <summary>Teknik ayrıntıları göster</summary>
                  <pre>{detail.stack_trace}</pre>
                </details>
              ) : null}
            </section>

            <form className="form-grid error-report-modal__form" onSubmit={saveDetail}>
              <label className="field error-report-modal__status-field">
                <span>Durum</span>
                <select value={edit.status} onChange={(e) => setEdit({ ...edit, status: e.target.value })}>
                  {Object.entries(statusLabelsMap).map(([k, l]) => (
                    <option key={k} value={k}>{l}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>İç not (EİSA)</span>
                <textarea
                  rows={3}
                  value={edit.admin_note}
                  onChange={(e) => setEdit({ ...edit, admin_note: e.target.value })}
                />
              </label>
              <label className="field">
                <span>Kullanıcıya yanıt</span>
                <textarea
                  rows={3}
                  value={edit.admin_reply}
                  onChange={(e) => setEdit({ ...edit, admin_reply: e.target.value })}
                />
              </label>
              <div className="form-actions error-report-modal__actions">
                <button type="button" className="secondary" onClick={() => setDetail(null)}>Kapat</button>
                <button type="submit" disabled={busy}>{busy ? 'Kaydediliyor…' : 'Kaydet'}</button>
              </div>
            </form>
          </div>
        </AppModal>
      )}
    </Page>
  );
}
