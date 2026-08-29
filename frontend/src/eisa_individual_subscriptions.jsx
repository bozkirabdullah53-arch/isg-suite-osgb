import React, { useEffect, useState } from 'react';
import { api } from './api';
import { Msg, Page, RefreshButton, SearchBar, StatusBadge } from './eisa';

function subscriptionEnd(row) {
  const value = row?.effective_status === 'trial' ? row?.trial_ends_at : row?.current_period_ends_at;
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleDateString('tr-TR');
}

export function EisaIndividualSubscriptionsPage() {
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const load = async () => {
    setBusy(true);
    setMsg('');
    try {
      const params = new URLSearchParams();
      if (q.trim()) params.set('q', q.trim());
      const data = await api(`/eisa/individual-subscriptions${params.toString() ? `?${params}` : ''}`);
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      setRows([]);
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { void load(); }, []);

  return (
    <Page title="Bireysel Abonelik" action={<RefreshButton busy={busy} onClick={load} />}>
      <p style={{ marginTop: 0, color: '#64748b' }}>
        Global yönetici tarafından onaylanan bireysel İş Güvenliği Uzmanları burada gösterilir.
        Bu liste OSGB aboneliklerinden tamamen ayrıdır.
      </p>
      <div className="eisa-toolbar">
        <SearchBar value={q} onChange={setQ} placeholder="Uzman adı, e-posta, belge no…" />
        <button type="button" disabled={busy} onClick={load}>Ara</button>
      </div>
      <Msg text={msg} />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Uzman</th>
              <th>Belge</th>
              <th>İletişim</th>
              <th>Paket</th>
              <th>Abonelik</th>
              <th>Kalan gün</th>
              <th>Bitiş</th>
              <th>Hesap</th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? rows.map((row) => (
              <tr key={row.id}>
                <td>{row.specialist_name || row.osgb_name || '—'}</td>
                <td>
                  <div className="eisa-cell-stack">
                    <span>{row.certificate_class || '—'}</span>
                    <small>{row.certificate_number || '—'}</small>
                  </div>
                </td>
                <td>
                  <div className="eisa-cell-stack">
                    <span>{row.specialist_email || row.contact_email || '—'}</span>
                    {(row.specialist_phone || row.contact_phone) ? <small>{row.specialist_phone || row.contact_phone}</small> : null}
                  </div>
                </td>
                <td>{row.package_name || row.plan || '—'}</td>
                <td><StatusBadge status={row.effective_status || row.status} /></td>
                <td>{row.days_remaining ?? '—'}</td>
                <td>{subscriptionEnd(row)}</td>
                <td>{row.account_active ? 'Aktif' : 'Pasif'}</td>
              </tr>
            )) : (
              <tr><td colSpan={8} className="empty">Onaylanmış bireysel abonelik bulunamadı.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Page>
  );
}
