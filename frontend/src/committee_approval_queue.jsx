import React, {useEffect, useMemo, useState} from 'react';
import {CheckCircle2, Clock3, Download, Eye, FileSignature, RefreshCw, Send, ShieldCheck, XCircle} from 'lucide-react';
import {api, downloadFile} from './api';
import {AppModal} from './ui_modal';
import {downloadBase64Pdf, probeIsgSigner, signPdfWithIsgSigner} from './isg_signer_agent';
import './committee-workflow.css';

const STATUS_LABELS = {
  draft: 'Taslak',
  incomplete: 'Eksik Kurul',
  waiting_for_review: 'İnceleme Bekliyor',
  waiting_for_approval: 'Onay Bekliyor',
  approved: 'Onaylandı',
  rejected: 'Reddedildi',
  revision_required: 'Yeniden Onay Gerekli',
  waiting_for_signature: 'İmza Bekliyor',
  not_signed: 'İmzalanmadı',
  signed: 'İmzalandı',
  in_progress: 'Devam Ediyor',
  locked: 'Tamamlandı',
  active: 'Sırası Geldi',
  pending: 'Bekliyor',
};

function statusLabel(value) {
  return STATUS_LABELS[value] || value || '—';
}

function statusTone(value) {
  if (['approved', 'signed', 'locked'].includes(value)) return 'success';
  if (['rejected', 'invalidated'].includes(value)) return 'danger';
  if (['incomplete', 'revision_required'].includes(value)) return 'warning';
  if (['waiting_for_review', 'waiting_for_approval', 'waiting_for_signature', 'in_progress', 'active'].includes(value)) return 'info';
  return 'neutral';
}

function StatusPill({value}) {
  return <span className={`committee-flow-status is-${statusTone(value)}`}>{statusLabel(value)}</span>;
}

function apiUrl(path) {
  const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  const base = isLocal
    ? `${window.location.protocol}//${window.location.hostname}:8000/api/v1`
    : `${window.location.origin}/api/v1`;
  return `${base}${path.replace(/^\/api\/v1/, '')}`;
}

async function fetchPdfBuffer(path) {
  const token = localStorage.getItem('isg_token');
  const response = await fetch(apiUrl(path), {
    headers: token ? {Authorization: `Bearer ${token}`} : {},
    credentials: 'include',
  });
  if (!response.ok) {
    let message = `PDF alınamadı (${response.status}).`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch { /* response is not JSON */ }
    throw new Error(message);
  }
  return response.arrayBuffer();
}

export function CommitteeApprovalQueue({user, companyId = '', compact = false, onChanged}) {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [success, setSuccess] = useState('');
  const [detail, setDetail] = useState(null);
  const [decision, setDecision] = useState(null);
  const [note, setNote] = useState('');

  const filtered = useMemo(() => {
    if (!companyId) return rows;
    return rows.filter((row) => String(row.company_id) === String(companyId));
  }, [rows, companyId]);

  async function load() {
    setBusy(true);
    setErr('');
    try {
      const data = await api('/ohs-committee/work-queue');
      setRows(Array.isArray(data) ? data : []);
      if (detail) {
        const fresh = (Array.isArray(data) ? data : []).find((row) => row.id === detail.id);
        if (fresh) setDetail(fresh);
      }
    } catch (error) {
      setErr(error.message || 'Kurul toplantısı iş kuyruğu yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function submit(row) {
    if (busy) return;
    setBusy(true); setErr(''); setSuccess('');
    try {
      await api(`/ohs-committee/meetings/${row.id}/submit-approval`, {method: 'POST'});
      setSuccess('Toplantı Uzman → Hekim → İşveren/Vekil onay akışına gönderildi.');
      await load();
      if (onChanged) onChanged();
    } catch (error) {
      setErr(error.message || 'Toplantı onaya gönderilemedi.');
    } finally {
      setBusy(false);
    }
  }

  async function decide() {
    if (!decision || busy) return;
    if (decision.action === 'reject' && !note.trim()) {
      setErr('Red veya düzeltmeye iade için gerekçe zorunludur.');
      return;
    }
    const workflowId = decision.row.approval_workflow?.id;
    if (!workflowId) {
      setErr('Aktif onay akışı bulunamadı.');
      return;
    }
    setBusy(true); setErr(''); setSuccess('');
    try {
      await api(`/eyas/workflows/${workflowId}/${decision.action === 'approve' ? 'approve' : 'reject'}`, {
        method: 'POST',
        body: JSON.stringify({
          note: note.trim() || null,
          device_note: typeof navigator !== 'undefined' ? navigator.userAgent.slice(0, 200) : null,
        }),
      });
      setDecision(null); setNote('');
      setSuccess(decision.action === 'approve' ? 'Onay adımınız tamamlandı.' : 'Toplantı gerekçeli olarak reddedildi ve taslağa döndü.');
      await load();
      if (onChanged) onChanged();
    } catch (error) {
      setErr(error.message || 'Onay işlemi tamamlanamadı.');
    } finally {
      setBusy(false);
    }
  }

  async function sign(row) {
    if (busy) return;
    setBusy(true); setErr(''); setSuccess('');
    try {
      const signer = await probeIsgSigner();
      if (!signer.ok) {
        throw new Error('OSGB Signer bağlı değil. Bu bilgisayarda signer uygulamasını açın.');
      }
      const request = await api(`/ohs-committee/meetings/${row.id}/signature-request`, {method: 'POST'});
      const source = await fetchPdfBuffer(request.source_path);
      const usePkcs11 = !!signer.data?.pkcs11_configured;
      let pin;
      if (usePkcs11) {
        pin = window.prompt('E-imza kartı PIN (yalnız bu bilgisayarda kullanılır; sunucuya gönderilmez):') || '';
        if (!pin) throw new Error('PIN girilmedi.');
      }
      const signed = await signPdfWithIsgSigner(source, {
        documentTitle: row.title,
        reason: `İSG Kurulu Toplantısı — ${row.company_name}`,
        requestToken: request.one_time_token,
        expectedSha256: request.source_sha256,
        certId: usePkcs11 ? 'pkcs11' : 'demo',
        pin,
      });
      await api('/esign/complete', {
        method: 'POST',
        body: JSON.stringify({
          one_time_token: request.one_time_token,
          signed_pdf_base64: signed.signed_pdf_base64,
          agent_mode: signed.mode,
          agent_signature_id: signed.signature_id,
          signer_cn: signed.signer?.common_name,
          signer_subject: signed.signer?.subject,
          cert_serial: signed.signer?.serial,
          cert_sha256: signed.signer?.sha256,
          mark_approval: false,
        }),
      });
      downloadBase64Pdf(signed.signed_pdf_base64, `ISG_Kurulu_Toplantisi_${row.id}_v${row.document_version}_imzali.pdf`);
      setSuccess('Elektronik imzanız doğrulandı ve belge zincirine eklendi.');
      await load();
      if (onChanged) onChanged();
    } catch (error) {
      setErr(error.message || 'Elektronik imza tamamlanamadı.');
    } finally {
      setBusy(false);
    }
  }

  function openDecision(row, action) {
    setErr('');
    setNote('');
    setDecision({row, action});
  }

  return (
    <section className={`committee-flow-shell ${compact ? 'is-compact' : ''}`}>
      <div className="committee-flow-head">
        <div>
          <span className="committee-flow-eyebrow"><ShieldCheck size={15} /> Yetkili iş kuyruğu</span>
          <h3>İSG Kurulu Onay ve İmza İşlemlerim</h3>
          <p>Yalnız görevlendirildiğiniz işyerleri ve size atanmış kurul adımları görüntülenir.</p>
        </div>
        <button type="button" className="secondary" disabled={busy} onClick={() => void load()}>
          <RefreshCw size={16} /> Yenile
        </button>
      </div>
      {err && <div className="error" role="alert">{err}</div>}
      {success && <div className="info" role="status">{success}</div>}
      <div className="committee-flow-grid">
        {filtered.length ? filtered.map((row) => (
          <article className="committee-flow-card" key={row.id}>
            <div className="committee-flow-card-top">
              <div>
                <span className="committee-flow-workplace">{row.company_name}</span>
                <h4>{row.title}</h4>
                <small>{row.meeting_date || 'Tarih yok'} · Toplantı No: {row.meeting_no || '—'} · Sürüm {row.document_version}</small>
              </div>
              <StatusPill value={row.pending_action === 'sign' ? 'waiting_for_signature' : row.approval_status} />
            </div>
            <div className="committee-flow-metrics">
              <div><span>Onay</span><strong>{statusLabel(row.approval_status)}</strong></div>
              <div><span>İmza</span><strong>{statusLabel(row.signature_status)}</strong></div>
              <div><span>Güncel adım</span><strong>{row.current_step?.role_label || '—'}</strong></div>
            </div>
            <div className="committee-flow-actions">
              <button type="button" className="secondary" onClick={() => setDetail(row)}><Eye size={15} /> Toplantıyı Aç</button>
              <button type="button" className="secondary" onClick={() => downloadFile(row.pdf_path, `ISG_Kurulu_${row.id}_v${row.document_version}.pdf`).catch((error) => setErr(error.message))}><Download size={15} /> PDF</button>
              {row.pending_action === 'submit' && row.can_manage && <button type="button" disabled={busy} onClick={() => void submit(row)}><Send size={15} /> Onaya Gönder</button>}
              {row.pending_action === 'approve' && <button type="button" disabled={busy} onClick={() => openDecision(row, 'approve')}><CheckCircle2 size={15} /> Onayla</button>}
              {row.pending_action === 'approve' && <button type="button" className="danger" disabled={busy} onClick={() => openDecision(row, 'reject')}><XCircle size={15} /> Reddet / İade</button>}
              {row.pending_action === 'sign' && <button type="button" disabled={busy} onClick={() => void sign(row)}><FileSignature size={15} /> Elektronik İmzala</button>}
              {row.pending_action === 'wait' && <span className="committee-flow-wait"><Clock3 size={15} /> Sıranız bekleniyor</span>}
            </div>
          </article>
        )) : <div className="committee-flow-empty"><CheckCircle2 size={34} /><strong>Bekleyen kurul işlemi yok</strong><span>Yeni toplantılar veya sırası gelen işlemler burada görünecek.</span></div>}
      </div>

      {detail && <AppModal title={`${detail.title} — ${detail.company_name}`} close={() => setDetail(null)} wide>
        <div className="committee-flow-detail">
          <div className="committee-flow-detail-summary">
            <div><span>Toplantı tarihi</span><strong>{detail.meeting_date || '—'}</strong></div>
            <div><span>Toplantı yeri</span><strong>{detail.location || '—'}</strong></div>
            <div><span>Belge sürümü</span><strong>v{detail.document_version}</strong></div>
            <div><span>Sonraki toplantı</span><strong>{detail.next_meeting_date || '—'}</strong></div>
          </div>
          <section><h4>Gündem</h4><p>{detail.agenda || 'Gündem kaydı bulunmuyor.'}</p></section>
          <section><h4>Kararlar</h4><p>{detail.decisions || 'Karar kaydı bulunmuyor.'}</p></section>
          <section><h4>Katılımcılar</h4><div className="committee-flow-people">{(detail.participants_snapshot || []).map((person, index) => <div key={person.identity_key || person.member_id || index}><span>{person.full_name}</span><small>{person.role_label || person.role_code}</small></div>)}</div></section>
          <section><h4>Dijital Onay Sırası</h4><div className="committee-flow-steps">{(detail.approval_workflow?.steps || []).map((step) => <div key={step.id} className={step.status}><b>{step.step_order}</b><span><strong>{step.role_label}</strong><small>{step.assignee_name || '—'} · {statusLabel(step.status)}{step.decided_at ? ` · ${step.decided_at}` : ''}</small>{step.note && <em>{step.note}</em>}</span></div>)}</div></section>
          {detail.signature_workflow && <section><h4>Elektronik İmza Sırası</h4><div className="committee-flow-steps">{detail.signature_workflow.steps.map((step) => <div key={step.id} className={step.status}><b>{step.step_order}</b><span><strong>{step.role_label}</strong><small>{step.signer_name || '—'} · {statusLabel(step.status)}{step.signed_at ? ` · ${step.signed_at}` : ''}</small></span></div>)}</div></section>}
        </div>
      </AppModal>}

      {decision && <AppModal title={decision.action === 'approve' ? 'Toplantıyı Onayla' : 'Toplantıyı Reddet / Düzeltmeye İade Et'} close={() => !busy && setDecision(null)}>
        <div className="committee-decision-dialog">
          <div className={`committee-decision-icon ${decision.action}`}>
            {decision.action === 'approve' ? <CheckCircle2 /> : <XCircle />}
          </div>
          <h3>{decision.row.title}</h3>
          <p>{decision.action === 'approve' ? 'Belgeyi incelediğinizi ve kendi onay adımınızı tamamladığınızı doğrulayın.' : 'Toplantının neden reddedildiğini veya hangi düzeltmenin gerektiğini açıkça yazın.'}</p>
          <label className="field"><span>{decision.action === 'approve' ? 'Onay notu (isteğe bağlı)' : 'Red / düzeltme gerekçesi (zorunlu)'}</span><textarea rows={4} value={note} onChange={(event) => setNote(event.target.value)} /></label>
          <div className="form-actions"><button type="button" className="secondary" disabled={busy} onClick={() => setDecision(null)}>Vazgeç</button><button type="button" className={decision.action === 'approve' ? '' : 'danger'} disabled={busy || (decision.action === 'reject' && !note.trim())} onClick={() => void decide()}>{busy ? 'İşleniyor…' : decision.action === 'approve' ? 'Onayımı Tamamla' : 'Gerekçeli Olarak İade Et'}</button></div>
        </div>
      </AppModal>}
    </section>
  );
}
