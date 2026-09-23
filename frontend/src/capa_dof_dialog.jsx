import React, {useEffect, useRef, useState} from 'react';
import {api} from './api';
import {AppModal} from './ui_modal';
import {canManageDof, capaStatus, formatCapaDate} from './capa_actions';

function localToday() {
  const value = new Date();
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
}

export function CapaDofDialog({row, user, companyName, close, onSaved}) {
  const risk = row.source_type === 'risk';
  const editable = canManageDof(user) && !row.is_completed;
  const initial = risk ? {
    description: row.title || '', responsible_person: row.responsible || '',
    responsible_department: row.responsible_department || '', term_date: row.term || '',
  } : {
    finding: row.title || '', corrective_action: row.action || '',
    preventive_action: row.preventive_action || '', root_cause: row.root_cause || '',
    responsible_person: row.responsible || '', term_date: row.term || '', priority: row.priority || 'Orta',
  };
  const [form, setForm] = useState(initial);
  const [closing, setClosing] = useState(false);
  const [note, setNote] = useState('');
  const [approver, setApprover] = useState(user.full_name || '');
  const [completionDate, setCompletionDate] = useState(localToday);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef(false);
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const dirty = Object.keys(initial).some((key) => form[key] !== initial[key]);
  const endpoint = `/${risk ? 'risks' : 'incidents'}/${row.parent_id}/dofs/${row.id}`;
  const status = capaStatus(row);
  const change = (key) => (event) => setForm({...form, [key]: event.target.value});

  async function submit(event, complete = false) {
    event.preventDefault();
    if (!editable || pending.current || !row.parent_id || !row.id) return;
    if (complete && (!note.trim() || (!risk && !approver.trim()))) {
      setError('Tamamlanma bilgilerini doldurunuz.');
      return;
    }
    pending.current = true;
    setBusy(true);
    setError('');
    const changes = Object.fromEntries(Object.entries(form)
      .filter(([key, value]) => value !== initial[key])
      .map(([key, value]) => [key, value.trim() || null]));
    const body = complete ? {
      completion_date: completionDate,
      ...(risk ? {completion_note: note.trim()} : {effectiveness_note: note.trim(), close_approval: approver.trim()}),
    } : changes;
    try {
      await api(endpoint + (complete ? '/complete' : ''), {method: complete ? 'POST' : 'PATCH', body: JSON.stringify(body)});
      if (active.current) onSaved(complete ? 'DÖF tamamlandı. Liste ve gecikme sayıları güncellendi.' : 'DÖF değişiklikleri kaydedildi.');
    } catch (failure) {
      if (active.current) setError(failure.message || 'DÖF işlemi kaydedilemedi.');
    } finally {
      pending.current = false;
      if (active.current) setBusy(false);
    }
  }

  return <AppModal title={`DÖF · ${row.code}`} close={busy ? undefined : close} wide>
    <p>{companyName || 'Seçili firma'} · {row.source} · {row.parent}</p>
    <p><span className={`status-badge ${status.tone}`}>{status.label}</span> {row.parentSummary}</p>
    {row.source_term && <p style={{fontSize: 13}}>Excel’deki termin: <strong>{row.source_term}</strong></p>}
    {error && <div className="error" role="alert">{error}</div>}
    <form onSubmit={(event) => submit(event)}>
      <fieldset disabled={!editable || busy || closing} style={{border: 0, padding: 0, minWidth: 0}}>
        <div className="form-grid">
          <label className="field" style={{gridColumn: '1 / -1'}}><span>{risk ? 'Faaliyet / yapılacak iş' : 'Tespit edilen uygunsuzluk'}</span>
            <textarea aria-label="DÖF açıklaması" rows={3} required minLength={risk ? 3 : 10} maxLength={2000}
              value={risk ? form.description : form.finding} onChange={change(risk ? 'description' : 'finding')} />
          </label>
          {!risk && <>
            <label className="field"><span>Düzeltici faaliyet</span><textarea required minLength={10} maxLength={2000} value={form.corrective_action} onChange={change('corrective_action')} /></label>
            <label className="field"><span>Önleyici faaliyet</span><textarea required minLength={10} maxLength={2000} value={form.preventive_action} onChange={change('preventive_action')} /></label>
            <label className="field"><span>Kök neden</span><textarea maxLength={2000} value={form.root_cause} onChange={change('root_cause')} /></label>
            <label className="field"><span>Öncelik</span><select value={form.priority} onChange={change('priority')}>
              {['Düşük', 'Orta', 'Yüksek', 'Acil', 'Kritik'].map((value) => <option key={value}>{value}</option>)}
            </select></label>
          </>}
          <label className="field"><span>Sorumlu</span><input aria-label="DÖF sorumlusu" required={!risk} maxLength={risk ? 150 : 160} value={form.responsible_person} onChange={change('responsible_person')} /></label>
          {risk && <label className="field"><span>Sorumlu bölüm</span><input maxLength={150} value={form.responsible_department} onChange={change('responsible_department')} /></label>}
          <label className="field"><span>Termin tarihi</span><input aria-label="DÖF termin tarihi" type="date" required={!risk} value={form.term_date} onChange={change('term_date')} />
            {!form.term_date && <small>{row.term_kind === 'continuous' ? 'Sürekli izleme; sabit bitiş tarihi yok.' : 'Termin tarihi belirlenmedi.'}</small>}
          </label>
        </div>
      </fieldset>
      {editable && !closing && <div className="form-actions">
        <button type="submit" disabled={busy || !dirty}>{busy ? 'Kaydediliyor…' : 'Değişiklikleri kaydet'}</button>
        <button type="button" className="secondary" disabled={busy || dirty} onClick={() => setClosing(true)}>DÖF’ü tamamla</button>
        {dirty && <small>Tamamlamadan önce değişiklikleri kaydedin.</small>}
      </div>}
    </form>
    {editable && closing && <form onSubmit={(event) => submit(event, true)} style={{marginTop: 18}}>
      <h4>Tamamlanma bilgileri</h4>
      <div className="form-grid">
        <label className="field"><span>Tamamlanma tarihi</span><input aria-label="Tamamlanma tarihi" type="date" required min="2000-01-01" max={localToday()} value={completionDate} disabled={busy} onChange={(event) => setCompletionDate(event.target.value)} /></label>
        {!risk && <label className="field"><span>Kapatan kişi</span><input required maxLength={160} value={approver} disabled={busy} onChange={(event) => setApprover(event.target.value)} /></label>}
        <label className="field" style={{gridColumn: '1 / -1'}}><span>Yapılan işlem / kapanış notu</span><textarea aria-label="Kapanış notu" rows={3} required minLength={10} maxLength={2000} value={note} disabled={busy} onChange={(event) => setNote(event.target.value)} /></label>
      </div>
      <div className="form-actions"><button type="submit" disabled={busy}>{busy ? 'Kaydediliyor…' : 'Tamamlandı olarak kaydet'}</button><button type="button" className="secondary" disabled={busy} onClick={() => setClosing(false)}>Geri</button></div>
    </form>}
    {row.is_completed && <div style={{marginTop: 16}}>
      <strong>Tamamlanma tarihi: {formatCapaDate(row.completion_date)}</strong>
      {row.completion_note && <p style={{whiteSpace: 'pre-wrap'}}>{row.completion_note}</p>}
      {row.close_approval && <p>Kapatan kişi: {row.close_approval}</p>}
    </div>}
  </AppModal>;
}
