import React, { useEffect, useState } from 'react';
import { api } from './api';
import { Msg, Page, RefreshButton, SearchBar, SimpleSubscriptionList, SubscriptionDetailModal } from './eisa';

export function EisaIndividualSubscriptionsPage() {
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [detail, setDetail] = useState(null);

  const load = async () => {
    setBusy(true);
    setMsg('');
    try {
      const params = new URLSearchParams();
      if (q.trim()) params.set('q', q.trim());
      const data = await api(`/eisa/individual-subscriptions${params.toString() ? `?${params}` : ''}`);
      setRows((Array.isArray(data) ? data : []).map((row) => ({
        ...row,
        kind: 'individual',
        display_name: row.specialist_name || row.osgb_name,
      })));
    } catch (e) {
      setRows([]);
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { void load(); }, []);

  async function deleteIndividual(row) {
    const specialistName = String(row.specialist_name || row.osgb_name || '').trim();
    const osgbId = row.osgb_id;
    const userId = row.user_id;
    if (!specialistName || (!osgbId && !userId)) {
      setMsg('Silme işlemi için uzman kaydı doğrulanamadı.');
      return;
    }
    if (!window.confirm(
      `“${specialistName}” bireysel üyeliği kaldırılsın mı?\n\nHesap listeden çıkarılır ve giriş kapanır.`,
    )) return;
    setBusy(true);
    setMsg('');
    try {
      if (osgbId) {
        try {
          await api(`/eisa/osgb-users/${osgbId}`, { method: 'DELETE' });
        } catch (e) {
          if (!userId) throw e;
          await api(`/eisa/individual-subscriptions/${userId}`, { method: 'DELETE' });
        }
      } else {
        await api(`/eisa/individual-subscriptions/${userId}`, { method: 'DELETE' });
      }
      setDetail(null);
      await load();
      setMsg(`“${specialistName}” bireysel üye kaldırıldı.`);
    } catch (e) {
      setMsg(e.message || 'Üye silinemedi.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Page title="Bireysel Abonelik" action={<RefreshButton busy={busy} onClick={load} />}>
      <p style={{ marginTop: 0, color: '#64748b' }}>
        Bireysel üyeler listede görünür. Satıra tıklayınca kullanıcı bilgisi açılır.
      </p>
      <div className="eisa-toolbar">
        <SearchBar value={q} onChange={setQ} placeholder="Uzman adı, e-posta, belge no…" />
        <button type="button" disabled={busy} onClick={load}>Ara</button>
      </div>
      <Msg text={msg} />
      <SimpleSubscriptionList
        title="Bireysel üyeler"
        empty="Bireysel üye yok."
        rows={rows}
        busy={busy}
        onOpen={setDetail}
      />
      <SubscriptionDetailModal
        row={detail}
        busy={busy}
        onClose={() => setDetail(null)}
        onDelete={deleteIndividual}
      />
    </Page>
  );
}
