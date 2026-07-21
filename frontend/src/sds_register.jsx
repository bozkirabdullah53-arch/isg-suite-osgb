import React, {useEffect, useState} from 'react';
import {Beaker, Plus, RefreshCw, Tag, Upload} from 'lucide-react';
import {api, uploadFile} from './api';

function Modal({title, close, children}) {
  return (
    <div className="modal-bg" onClick={close}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button type="button" className="secondary mini" onClick={close}>Kapat</button>
        </div>
        {children}
      </div>
    </div>
  );
}

function Field({label, children, ...rest}) {
  if (children) {
    return (
      <label className="field">
        <span>{label}</span>
        {children}
      </label>
    );
  }
  return (
    <label className="field">
      <span>{label}</span>
      <input {...rest} />
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
  const canEdit = user.role === 'safety_specialist' || user.role === 'global_admin';
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
        <Modal title="Yeni Kimyasal Ürün" close={() => setOpen(false)}>
          <form className="form-grid" onSubmit={save}>
            <Field label="Firma">
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
              required
              value={form.product_name}
              onChange={(e) => setForm({...form, product_name: e.target.value})}
            />
            <Field
              label="CAS (isteğe bağlı)"
              placeholder="örn. 67-64-1"
              value={form.cas_number}
              onChange={(e) => setForm({...form, cas_number: e.target.value})}
            />
            <Field
              label="Sonraki gözden geçirme"
              type="date"
              value={form.next_review_date}
              onChange={(e) => setForm({...form, next_review_date: e.target.value})}
            />
            <label className="field" style={{flexDirection: 'row', alignItems: 'center', gap: 8}}>
              <input
                type="checkbox"
                checked={!!form.has_sds_file}
                onChange={(e) => setForm({...form, has_sds_file: e.target.checked})}
              />
              <span>SDS dosyası mevcut (bayrak)</span>
            </label>
            <Field
              label="Not"
              value={form.notes}
              onChange={(e) => setForm({...form, notes: e.target.value})}
            />
            <div className="form-actions">
              <button type="submit" disabled={busy}>Kaydet</button>
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
