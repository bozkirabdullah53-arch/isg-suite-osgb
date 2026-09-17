import React, {useEffect, useState} from 'react';
import {
  Beaker,
  Building2,
  CalendarClock,
  Download,
  FileCheck2,
  Hash,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
  Tag,
  Upload,
} from 'lucide-react';
import {api, downloadFile, uploadFile} from './api';
import {AppModal} from './ui_modal';
import {isWorkplaceAccountUser} from './workplace_user_policy';
import './sds_register.css';

function Modal({title, close, children, className = ''}) {
  return (
    <AppModal title={title} close={close} className={className}>
      {children}
    </AppModal>
  );
}

function Field({label, children, className = '', hint = '', icon: Icon, requiredLabel = false, ...rest}) {
  const required = requiredLabel || !!rest.required;
  if (children) {
    return (
      <label className={`field sds-modern-field${className ? ` ${className}` : ''}`}>
        <span className="sds-modern-field-label">
          {Icon ? <Icon size={15} aria-hidden="true" /> : null}
          <span>{label}{required ? <b aria-hidden="true">*</b> : null}</span>
        </span>
        {children}
        {hint ? <small className="sds-field-hint">{hint}</small> : null}
      </label>
    );
  }
  return (
    <label className={`field sds-modern-field${className ? ` ${className}` : ''}`}>
      <span className="sds-modern-field-label">
        {Icon ? <Icon size={15} aria-hidden="true" /> : null}
        <span>{label}{required ? <b aria-hidden="true">*</b> : null}</span>
      </span>
      <input {...rest} />
      {hint ? <small className="sds-field-hint">{hint}</small> : null}
    </label>
  );
}

function reviewBadge(status) {
  if (status === 'overdue') return <span className="status-badge badge-danger">Gecikmiş</span>;
  if (status === 'due_soon') return <span className="status-badge badge-warn">Yaklaşıyor</span>;
  if (status === 'ok') return <span className="status-badge badge-ok">Güncel</span>;
  return <span className="status-badge badge-muted">Tarih yok</span>;
}

const empty = {
  company_id: '',
  product_name: '',
  cas_number: '',
  has_sds_file: false,
  next_review_date: '',
  notes: '',
};

export function SdsRegisterPage({user}) {
  const canEdit = user.role === 'safety_specialist'
    || user.role === 'global_admin'
    || isWorkplaceAccountUser(user);
  const [companies, setCompanies] = useState([]);
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(null);
  const [catalog, setCatalog] = useState([]);
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const [ghsRow, setGhsRow] = useState(null);
  const [ghsSelected, setGhsSelected] = useState([]);
  const [form, setForm] = useState({...empty, company_id: user.company_id || ''});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');

  async function load(nextQ = q) {
    setBusy(true);
    setErr('');
    try {
      const qs = nextQ.trim() ? `?q=${encodeURIComponent(nextQ.trim())}` : '';
      const [c, r, s, meta] = await Promise.all([
        api('/companies'),
        api(`/sds${qs}`),
        api('/sds/due-summary'),
        api('/sds/meta'),
      ]);
      setCompanies(c);
      setRows(r);
      setSummary(s);
      setCatalog(meta?.ghs_pictograms || []);
    } catch (e) {
      setErr(e.message || 'SDS sicili yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function save(e) {
    e.preventDefault();
    setErr('');
    setBusy(true);
    try {
      await api('/sds', {
        method: 'POST',
        body: JSON.stringify({
          company_id: Number(form.company_id),
          product_name: form.product_name,
          cas_number: form.cas_number || null,
          has_sds_file: !!form.has_sds_file,
          next_review_date: form.next_review_date || null,
          notes: form.notes || null,
        }),
      });
      setOpen(false);
      setForm({...empty, company_id: user.company_id || form.company_id || ''});
      setMsg('Kimyasal ürün eklendi.');
      await load();
    } catch (ex) {
      setErr(ex.message || 'Kayıt başarısız.');
    } finally {
      setBusy(false);
    }
  }

  async function ensureDocAndUpload(row, file) {
    if (!file) return;
    setBusy(true);
    setErr('');
    setMsg('');
    try {
      let linked = row;
      if (!row.document_id) {
        linked = await api(`/sds/${row.id}/ensure-document`, {method: 'POST'});
      }
      await uploadFile(`/files/documents/${linked.document_id}`, file);
      const marked = await api(`/sds/${row.id}/mark-sds-uploaded`, {method: 'POST'});
      setMsg(`SDS yüklendi: ${marked.product_name}`);
      await load();
    } catch (ex) {
      setErr(ex.message || 'SDS yükleme başarısız.');
    } finally {
      setBusy(false);
    }
  }

  async function ensureDocOnly(row) {
    setBusy(true);
    setErr('');
    try {
      await api(`/sds/${row.id}/ensure-document`, {method: 'POST'});
      setMsg('Doküman kaydı hazır — SDS dosyasını yükleyebilirsiniz.');
      await load();
    } catch (ex) {
      setErr(ex.message || 'Doküman oluşturulamadı.');
    } finally {
      setBusy(false);
    }
  }

  function openGhs(row) {
    setGhsRow(row);
    setGhsSelected([...(row.ghs_selected || [])]);
  }

  function toggleGhs(code) {
    setGhsSelected((prev) => (
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    ));
  }

  async function saveGhs(e) {
    e.preventDefault();
    if (!ghsRow) return;
    setBusy(true);
    setErr('');
    try {
      await api(`/sds/${ghsRow.id}/ghs-checklist`, {
        method: 'PUT',
        body: JSON.stringify({selected: ghsSelected}),
      });
      setMsg(`Tehlike etiketi güncellendi: ${ghsRow.product_name}`);
      setGhsRow(null);
      await load();
    } catch (ex) {
      setErr(ex.message || 'Etiket kaydı başarısız.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-title">
        <h3>SDS / PKD Sicili</h3>
        <div className="actions">
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => {
              const stamp = new Date().toISOString().slice(0, 10);
              downloadFile(
                `/sds/export.xlsx${q.trim() ? `?q=${encodeURIComponent(q.trim())}` : ''}`,
                `sds-sicili-${stamp}.xlsx`,
              ).catch((e) => setErr(e.message || 'Excel indirilemedi.'));
            }}
          >
            <Download size={16} /> Excel Rapor
          </button>
          <button type="button" className="secondary" disabled={busy} onClick={() => void load()}>
            <RefreshCw size={16} /> Yenile
          </button>
          {canEdit && (
            <button type="button" disabled={busy} onClick={() => setOpen(true)}>
              <Plus size={16} /> Yeni Ürün
            </button>
          )}
        </div>
      </div>

      <section className="panel" style={{marginBottom: 16}}>
        <p style={{margin: '0 0 12px', color: '#475569', fontSize: 14, lineHeight: 1.5}}>
          Saha kimyasal ürün sicili: ürün adı, isteğe bağlı CAS, SDS dosya durumu, gözden geçirme tarihi
          ve GHS/CLP tehlike etiketi checklist. Dosya yükleme Dokümanlar altyapısını kullanır.
        </p>
        {summary && (
          <div className="report-grid" style={{marginBottom: 0}}>
            <div className="metric"><strong>{summary.total}</strong><span>Toplam ürün</span></div>
            <div className="metric"><strong>{summary.with_sds}</strong><span>SDS var</span></div>
            <div className="metric"><strong>{summary.missing_sds}</strong><span>SDS eksik</span></div>
            <div className="metric"><strong>{summary.with_ghs_label ?? 0}</strong><span>Etiket işaretli</span></div>
            <div className="metric"><strong>{summary.due_soon}</strong><span>Yaklaşan</span></div>
            <div className="metric"><strong>{summary.overdue}</strong><span>Gecikmiş</span></div>
          </div>
        )}
      </section>

      <div className="search">
        <Beaker size={16} />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void load()}
          placeholder="Ürün veya CAS ara…"
        />
        <button type="button" className="secondary mini" onClick={() => void load()}>Ara</button>
      </div>

      {err && <p style={{color: '#b91c1c'}}>{err}</p>}
      {msg && <p style={{color: '#08744f'}}>{msg}</p>}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Ürün</th>
              <th>CAS</th>
              <th>SDS</th>
              <th>GHS</th>
              <th>Gözden geçirme</th>
              <th>Durum</th>
              {canEdit && <th>İşlem</th>}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={canEdit ? 7 : 6}>Kayıt yok.</td></tr>
            ) : rows.map((r) => (
              <tr key={r.id}>
                <td>{r.product_name}</td>
                <td>{r.cas_number || '—'}</td>
                <td>{r.has_sds_file ? 'Var' : 'Yok'}</td>
                <td>{r.ghs_count ? `${r.ghs_count} piktogram` : '—'}</td>
                <td>{r.next_review_date || '—'}</td>
                <td>{reviewBadge(r.review_status)}</td>
                {canEdit && (
                  <td>
                    <div style={{display: 'flex', gap: 6, flexWrap: 'wrap'}}>
                      <button type="button" className="mini secondary" disabled={busy} onClick={() => openGhs(r)}>
                        <Tag size={14} /> Etiket
                      </button>
                      {!r.document_id && (
                        <button type="button" className="mini secondary" disabled={busy} onClick={() => void ensureDocOnly(r)}>
                          Doküman oluştur
                        </button>
                      )}
                      <label className="mini secondary" style={{cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4}}>
                        <Upload size={14} /> SDS yükle
                        <input
                          type="file"
                          accept=".pdf,.doc,.docx,.png,.jpg,.jpeg"
                          style={{display: 'none'}}
                          disabled={busy}
                          onChange={(e) => {
                            const f = e.target.files?.[0];
                            e.target.value = '';
                            if (f) void ensureDocAndUpload(r, f);
                          }}
                        />
                      </label>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {open && (
        <Modal
          className="sds-product-modal"
          title={(
            <span className="sds-modal-heading">
              <span className="sds-modal-heading-icon" aria-hidden="true"><Beaker size={22} /></span>
              <span>
                <strong>Yeni Kimyasal Ürün</strong>
                <small>SDS siciline güvenli ve izlenebilir ürün kaydı</small>
              </span>
            </span>
          )}
          close={() => setOpen(false)}
        >
          <form className="sds-product-form" onSubmit={save}>
            <div className="sds-modal-intro">
              <span className="sds-modal-intro-icon" aria-hidden="true"><ShieldCheck size={21} /></span>
              <span className="sds-modal-intro-copy">
                <strong>Ürün ve takip bilgileri</strong>
                <small>Kimyasalı tanımlayın; SDS durumu ve gözden geçirme tarihini kaydedin.</small>
              </span>
              <span className="sds-required-note"><b>*</b> Zorunlu alan</span>
            </div>

            <div className="sds-product-grid">
              <Field label="Firma" icon={Building2} requiredLabel>
                <select
                  required
                  value={form.company_id}
                  onChange={(e) => setForm({...form, company_id: e.target.value})}
                >
                  <option value="">Seçiniz</option>
                  {companies.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </Field>
              <Field
                label="Ürün adı"
                icon={Beaker}
                required
                placeholder="Örn. Aseton"
                value={form.product_name}
                onChange={(e) => setForm({...form, product_name: e.target.value})}
              />
              <Field
                label="CAS (isteğe bağlı)"
                icon={Hash}
                placeholder="Örn. 67-64-1"
                value={form.cas_number}
                onChange={(e) => setForm({...form, cas_number: e.target.value})}
              />
              <Field
                label="Sonraki gözden geçirme"
                icon={CalendarClock}
                type="date"
                value={form.next_review_date}
                onChange={(e) => setForm({...form, next_review_date: e.target.value})}
              />
              <label className={`sds-file-card${form.has_sds_file ? ' is-active' : ''}`}>
                <input
                  className="sds-toggle-input"
                  type="checkbox"
                  checked={!!form.has_sds_file}
                  onChange={(e) => setForm({...form, has_sds_file: e.target.checked})}
                />
                <span className="sds-file-card-icon" aria-hidden="true"><FileCheck2 size={21} /></span>
                <span className="sds-file-card-copy">
                  <strong>SDS dosyası mevcut</strong>
                  <small>Güvenlik bilgi formu hazırsa bu seçeneği etkinleştirin.</small>
                </span>
                <span className="sds-toggle-ui" aria-hidden="true"><span /></span>
              </label>
              <Field label="Not" className="sds-notes-field">
                <textarea
                  rows={3}
                  placeholder="Ürün, kullanım alanı veya takip süreciyle ilgili kısa not ekleyin…"
                  value={form.notes}
                  onChange={(e) => setForm({...form, notes: e.target.value})}
                />
              </Field>
            </div>

            <div className="sds-product-actions">
              <button
                type="button"
                className="sds-cancel-button"
                disabled={busy}
                onClick={() => setOpen(false)}
              >
                Vazgeç
              </button>
              <button type="submit" className="sds-save-button" disabled={busy}>
                <Save size={17} aria-hidden="true" />
                {busy ? 'Kaydediliyor…' : 'Ürünü Kaydet'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {ghsRow && (
        <Modal title={`Tehlike etiketi — ${ghsRow.product_name}`} close={() => setGhsRow(null)}>
          <form onSubmit={saveGhs}>
            <p style={{marginTop: 0, color: '#475569', fontSize: 14}}>
              GHS/CLP piktogram checklist (stub). Sahada etiket üzerindeki işaretleri seçin.
            </p>
            <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16}}>
              {(catalog.length ? catalog : []).map((p) => (
                <label key={p.code} style={{display: 'flex', gap: 8, alignItems: 'center', fontSize: 14}}>
                  <input
                    type="checkbox"
                    checked={ghsSelected.includes(p.code)}
                    onChange={() => toggleGhs(p.code)}
                  />
                  <span><strong>{p.code}</strong> — {p.label}</span>
                </label>
              ))}
            </div>
            <div className="form-actions">
              <button type="submit" disabled={busy}>Kaydet</button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
