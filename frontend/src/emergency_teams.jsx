import React, {useEffect, useMemo, useState} from 'react';
import {
  AlertTriangle,
  Download,
  FileText,
  Plus,
  RefreshCw,
  ShieldAlert,
  Trash2,
  Upload,
  UserPlus,
  Users,
} from 'lucide-react';
import {api, downloadFile, uploadFile} from './api';

const CERT_BADGE = {
  green: {label: 'Geçerli', cls: 'badge-ok'},
  yellow: {label: '30 gün içinde', cls: 'badge-warn'},
  red: {label: 'Süresi dolmuş', cls: 'badge-danger'},
  grey: {label: 'Kayıt yok', cls: 'badge-muted'},
};

const TEAM_TONE = {
  ok: 'badge-ok',
  warn: 'badge-warn',
  danger: 'badge-danger',
  muted: 'badge-muted',
};

function certBadge(status) {
  const c = CERT_BADGE[status] || CERT_BADGE.grey;
  return <span className={`status-badge ${c.cls}`}>{c.label}</span>;
}

function teamStatusBadge(status) {
  if (!status) return null;
  const cls = TEAM_TONE[status.tone] || 'badge-muted';
  return <span className={`status-badge ${cls}`}>{status.label}</span>;
}

const emptyTeam = {type_id: '', name: '', min_members: '', notes: ''};
const emptyMember = {
  team_id: '',
  employee_id: '',
  membership: 'asil',
  is_leader: false,
  role_title: '',
  shift: '',
  phone: '',
  email: '',
  section: '',
  personnel_no: '',
  assign_start: '',
  letter_date: '',
  letter_no: '',
  assigned_by: '',
  notes: '',
};
const emptyTraining = {
  training_type: '',
  provider: '',
  trainer: '',
  training_date: '',
  duration_hours: '',
  certificate_no: '',
  valid_until: '',
  first_aid_cert_no: '',
  first_aid_center: '',
  first_aid_start: '',
  first_aid_end: '',
  refresh_date: '',
  notes: '',
};

function Kpi({label, value, tone}) {
  const color = tone === 'danger' ? '#b91c1c' : tone === 'warn' ? '#b45309' : '#0f172a';
  return (
    <div
      style={{
        flex: '1 1 130px',
        minWidth: 120,
        background: '#fff',
        border: '1px solid #e2e8f0',
        borderRadius: 10,
        padding: '12px 14px',
      }}
    >
      <div style={{fontSize: 12, color: '#64748b'}}>{label}</div>
      <div style={{fontSize: 22, fontWeight: 700, color}}>{value}</div>
    </div>
  );
}

export function EmergencyTeamsPage({user}) {
  const canEdit = user.role === 'safety_specialist' || user.role === 'global_admin';
  const [companies, setCompanies] = useState([]);
  const [companyId, setCompanyId] = useState(user.company_id || '');
  const [meta, setMeta] = useState({team_types: [], memberships: ['asil', 'yedek']});
  const [overview, setOverview] = useState(null);
  const [members, setMembers] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [filters, setFilters] = useState({q: '', team_id: '', membership: '', shift: '', cert_status: ''});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');

  const [teamModal, setTeamModal] = useState(false);
  const [teamForm, setTeamForm] = useState(emptyTeam);
  const [memberModal, setMemberModal] = useState(false);
  const [memberForm, setMemberForm] = useState(emptyMember);
  const [trainingModal, setTrainingModal] = useState(null); // assignment row
  const [trainingForm, setTrainingForm] = useState(emptyTraining);
  const [trainingFile, setTrainingFile] = useState(null);

  const companyEmployees = useMemo(
    () => employees.filter((e) => String(e.company_id) === String(companyId)),
    [employees, companyId],
  );
  const teams = overview?.teams || [];

  async function loadCompanies() {
    try {
      const c = await api('/companies');
      setCompanies(c || []);
      if (!companyId && c && c.length) setCompanyId(c[0].id);
    } catch (ex) {
      setErr(ex.message || 'Firmalar yüklenemedi.');
    }
  }

  async function loadMeta() {
    try {
      const m = await api('/emergency-teams/meta');
      setMeta(m || {team_types: []});
    } catch (_) {
      /* meta opsiyonel */
    }
  }

  function buildAssignmentQuery(cid) {
    const p = new URLSearchParams();
    p.set('company_id', cid);
    if (filters.team_id) p.set('team_id', filters.team_id);
    if (filters.q.trim()) p.set('q', filters.q.trim());
    if (filters.membership) p.set('membership', filters.membership);
    if (filters.shift.trim()) p.set('shift', filters.shift.trim());
    if (filters.cert_status) p.set('cert_status', filters.cert_status);
    return p.toString();
  }

  async function loadData(cid = companyId) {
    if (!cid) return;
    setBusy(true);
    setErr('');
    try {
      const [ov, mem, emp] = await Promise.all([
        api(`/emergency-teams/overview?company_id=${cid}`),
        api(`/emergency-teams/assignments?${buildAssignmentQuery(cid)}`),
        api('/employees'),
      ]);
      setOverview(ov);
      setMembers(mem || []);
      setEmployees(emp || []);
    } catch (ex) {
      setErr(ex.message || 'Acil durum ekipleri yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void loadCompanies();
    void loadMeta();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (companyId) void loadData(companyId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId]);

  async function reloadMembers() {
    if (!companyId) return;
    try {
      const mem = await api(`/emergency-teams/assignments?${buildAssignmentQuery(companyId)}`);
      setMembers(mem || []);
    } catch (ex) {
      setErr(ex.message || 'Üyeler yüklenemedi.');
    }
  }

  // -- Ekip oluştur --------------------------------------------------------
  async function saveTeam(e) {
    e.preventDefault();
    setErr('');
    setBusy(true);
    try {
      await api('/emergency-teams/teams', {
        method: 'POST',
        body: JSON.stringify({
          company_id: Number(companyId),
          type_id: Number(teamForm.type_id),
          name: teamForm.name,
          min_members: teamForm.min_members === '' ? null : Number(teamForm.min_members),
          notes: teamForm.notes || null,
        }),
      });
      setTeamModal(false);
      setTeamForm(emptyTeam);
      setMsg('Ekip oluşturuldu.');
      await loadData();
    } catch (ex) {
      setErr(ex.message || 'Ekip oluşturulamadı.');
    } finally {
      setBusy(false);
    }
  }

  async function createDefaultTeams() {
    // Boş durumda ilk ekipleri kur: overview zaten EDIT rollerde otomatik kurar,
    // yine de tetiklemek için yeniden yükle.
    setBusy(true);
    try {
      await loadData();
      setMsg('Varsayılan acil durum ekipleri hazırlandı.');
    } finally {
      setBusy(false);
    }
  }

  async function removeTeam(team) {
    if (!window.confirm(`“${team.name}” ekibi ve üyeleri pasife alınsın mı?`)) return;
    setBusy(true);
    try {
      await api(`/emergency-teams/teams/${team.id}`, {method: 'DELETE'});
      setMsg('Ekip silindi.');
      await loadData();
    } catch (ex) {
      setErr(ex.message || 'Silinemedi.');
    } finally {
      setBusy(false);
    }
  }

  // -- Üye ekle ------------------------------------------------------------
  function openMemberModal(teamId = '') {
    setMemberForm({...emptyMember, team_id: teamId || (teams[0]?.id ?? '')});
    setMemberModal(true);
  }

  async function saveMember(e) {
    e.preventDefault();
    setErr('');
    setBusy(true);
    try {
      await api('/emergency-teams/assignments', {
        method: 'POST',
        body: JSON.stringify({
          company_id: Number(companyId),
          team_id: Number(memberForm.team_id),
          employee_id: Number(memberForm.employee_id),
          membership: memberForm.membership,
          is_leader: !!memberForm.is_leader,
          role_title: memberForm.role_title || null,
          shift: memberForm.shift || null,
          phone: memberForm.phone || null,
          email: memberForm.email || null,
          section: memberForm.section || null,
          personnel_no: memberForm.personnel_no || null,
          assign_start: memberForm.assign_start || null,
          letter_date: memberForm.letter_date || null,
          letter_no: memberForm.letter_no || null,
          assigned_by: memberForm.assigned_by || null,
          notes: memberForm.notes || null,
        }),
      });
      setMemberModal(false);
      setMemberForm(emptyMember);
      setMsg('Ekip üyesi / destek elemanı eklendi.');
      await loadData();
    } catch (ex) {
      setErr(ex.message || 'Üye eklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  async function removeMember(row) {
    if (!window.confirm(`“${row.employee_name}” görevlendirmesi kaldırılsın mı?`)) return;
    setBusy(true);
    try {
      await api(`/emergency-teams/assignments/${row.id}`, {method: 'DELETE'});
      setMsg('Görevlendirme kaldırıldı.');
      await loadData();
    } catch (ex) {
      setErr(ex.message || 'Silinemedi.');
    } finally {
      setBusy(false);
    }
  }

  // -- Eğitim ekle ---------------------------------------------------------
  function openTrainingModal(row) {
    setTrainingForm(emptyTraining);
    setTrainingFile(null);
    setTrainingModal(row);
  }

  async function saveTraining(e) {
    e.preventDefault();
    setErr('');
    setBusy(true);
    try {
      const payload = {};
      for (const [k, v] of Object.entries(trainingForm)) {
        if (v === '' || v === null) continue;
        payload[k] = k === 'duration_hours' ? Number(v) : v;
      }
      await api(`/emergency-teams/assignments/${trainingModal.id}/trainings`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      if (trainingFile) {
        await uploadFile(`/emergency-teams/assignments/${trainingModal.id}/certificate-file`, trainingFile);
      }
      setTrainingModal(null);
      setTrainingForm(emptyTraining);
      setTrainingFile(null);
      setMsg('Eğitim / sertifika kaydedildi.');
      await loadData();
    } catch (ex) {
      setErr(ex.message || 'Eğitim kaydedilemedi.');
    } finally {
      setBusy(false);
    }
  }

  async function exportFile(kind) {
    try {
      const ext = kind === 'pdf' ? 'pdf' : 'xlsx';
      await downloadFile(
        `/emergency-teams/export.${ext}?company_id=${companyId}`,
        `acil-durum-ekipleri-${companyId}.${ext}`,
      );
    } catch (ex) {
      setErr(ex.message || 'Dışa aktarım başarısız.');
    }
  }

  async function letterPdf(row) {
    try {
      await downloadFile(
        `/emergency-teams/assignments/${row.id}/letter.pdf`,
        `gorevlendirme-yazisi-${row.id}.pdf`,
      );
    } catch (ex) {
      setErr(ex.message || 'Görevlendirme yazısı alınamadı.');
    }
  }

  const hasTeams = teams.length > 0;
  const kpi = overview?.kpis || {};

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2>
            <ShieldAlert size={22} style={{marginRight: 8, verticalAlign: 'middle'}} />
            Acil Durum Ekipleri / Destek Elemanları
          </h2>
          <p className="muted">
            Söndürme, kurtarma, koruma, ilk yardım, tahliye ve haberleşme ekipleri ile destek
            elemanı görevlendirmeleri.
          </p>
        </div>
        <div className="actions">
          {canEdit && hasTeams && (
            <>
              <button type="button" onClick={() => openMemberModal()} disabled={busy}>
                <UserPlus size={16} /> Destek Elemanı Ekle
              </button>
              <button type="button" className="secondary" onClick={() => setTeamModal(true)} disabled={busy}>
                <Plus size={16} /> Yeni Ekip
              </button>
            </>
          )}
          <button type="button" className="secondary" onClick={() => loadData()} disabled={busy}>
            <RefreshCw size={16} /> Yenile
          </button>
        </div>
      </div>

      {err && <div className="banner danger">{err}</div>}
      {msg && <div className="banner ok">{msg}</div>}

      <section className="panel" style={{marginBottom: 12}}>
        <div className="toolbar" style={{gap: 12, flexWrap: 'wrap', alignItems: 'flex-end'}}>
          <label className="field" style={{minWidth: 240}}>
            <span>İşyeri</span>
            <select value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
              <option value="">Firma seçin</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </label>
          {hasTeams && (
            <div className="actions">
              <button type="button" className="secondary mini" onClick={() => exportFile('xlsx')} disabled={busy}>
                <Download size={14} /> Excel
              </button>
              <button type="button" className="secondary mini" onClick={() => exportFile('pdf')} disabled={busy}>
                <Download size={14} /> PDF
              </button>
            </div>
          )}
        </div>

        {overview?.company && (
          <div className="muted" style={{marginTop: 10, fontSize: 13, display: 'flex', gap: 16, flexWrap: 'wrap'}}>
            <span><strong>SGK Sicil:</strong> {overview.company.sgk_registry_no || '—'}</span>
            <span><strong>Tehlike Sınıfı:</strong> {overview.company.hazard_class || '—'}</span>
            <span><strong>Personel:</strong> {overview.employee_count}</span>
            <span><strong>İSG Uzmanı:</strong> {overview.specialist_name || '—'}</span>
          </div>
        )}
      </section>

      {companyId && (
        <div style={{display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 14}}>
          <Kpi label="Ekip" value={kpi.team_count ?? 0} />
          <Kpi label="Üye" value={kpi.member_count ?? 0} />
          <Kpi label="Lider" value={kpi.leader_count ?? 0} />
          <Kpi label="Tam Ekip" value={kpi.teams_ok ?? 0} />
          <Kpi label="Kritik Ekip" value={kpi.teams_critical ?? 0} tone={kpi.teams_critical ? 'danger' : undefined} />
          <Kpi label="Belge Süresi Dolan" value={kpi.cert_expired ?? 0} tone={kpi.cert_expired ? 'danger' : undefined} />
          <Kpi label="30 Gün İçinde" value={kpi.cert_soon ?? 0} tone={kpi.cert_soon ? 'warn' : undefined} />
        </div>
      )}

      {overview?.warnings?.length > 0 && (
        <section className="panel" style={{marginBottom: 14, borderLeft: '4px solid #f59e0b'}}>
          <div style={{fontWeight: 600, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6}}>
            <AlertTriangle size={16} /> Kontrol Önerileri
          </div>
          <ul style={{margin: 0, paddingLeft: 20, fontSize: 13, color: '#475569'}}>
            {overview.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </section>
      )}

      {/* Empty state */}
      {companyId && !busy && !hasTeams && (
        <section className="panel" style={{textAlign: 'center', padding: 32}}>
          <Users size={40} style={{color: '#94a3b8', marginBottom: 12}} />
          <h3 style={{margin: '0 0 8px'}}>Henüz acil durum ekibi tanımlı değil</h3>
          <p className="muted" style={{maxWidth: 520, margin: '0 auto 16px'}}>
            Bu işyeri için söndürme, kurtarma, koruma, ilk yardım, tahliye ve haberleşme ekiplerini
            oluşturup destek elemanlarını görevlendirebilirsiniz.
          </p>
          {canEdit && (
            <button type="button" onClick={createDefaultTeams} disabled={busy}>
              <Plus size={16} /> İlk Acil Durum Ekibini Oluştur
            </button>
          )}
        </section>
      )}

      {/* Team cards grid */}
      {hasTeams && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 12,
            marginBottom: 18,
          }}
        >
          {teams.map((t) => (
            <div key={t.id} className="panel" style={{padding: 14}}>
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8}}>
                <div>
                  <div style={{fontWeight: 700}}>{t.name}</div>
                  <div className="muted" style={{fontSize: 12}}>{t.type_name || t.type_code || '—'}</div>
                </div>
                {teamStatusBadge(t.status)}
              </div>
              <div style={{display: 'flex', gap: 14, marginTop: 10, fontSize: 13}}>
                <span>Asıl: <strong>{t.asil_count}</strong></span>
                <span>Yedek: <strong>{t.yedek_count}</strong></span>
                <span className="muted">Min: {t.min_members}</span>
              </div>
              <div style={{fontSize: 12, color: '#64748b', marginTop: 6}}>
                Lider: {t.leader_name || '—'}
              </div>
              {t.warnings?.length > 0 && (
                <div style={{fontSize: 11, color: '#b45309', marginTop: 8}}>
                  {t.warnings[0]}
                </div>
              )}
              {canEdit && (
                <div className="actions" style={{marginTop: 10}}>
                  <button type="button" className="secondary mini" onClick={() => openMemberModal(t.id)}>
                    <UserPlus size={13} /> Üye
                  </button>
                  <button type="button" className="secondary mini" onClick={() => removeTeam(t)}>
                    <Trash2 size={13} /> Sil
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Members table + filters */}
      {hasTeams && (
        <section className="panel">
          <div className="toolbar" style={{gap: 8, flexWrap: 'wrap', marginBottom: 12}}>
            <input
              placeholder="Ara: ad, görev, bölüm, sicil…"
              value={filters.q}
              onChange={(e) => setFilters({...filters, q: e.target.value})}
              onKeyDown={(e) => e.key === 'Enter' && reloadMembers()}
            />
            <select value={filters.team_id} onChange={(e) => setFilters({...filters, team_id: e.target.value})}>
              <option value="">Tüm ekipler</option>
              {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
            <select value={filters.membership} onChange={(e) => setFilters({...filters, membership: e.target.value})}>
              <option value="">Asıl + Yedek</option>
              <option value="asil">Asıl</option>
              <option value="yedek">Yedek</option>
            </select>
            <select value={filters.cert_status} onChange={(e) => setFilters({...filters, cert_status: e.target.value})}>
              <option value="">Tüm belgeler</option>
              <option value="green">Geçerli</option>
              <option value="yellow">30 gün içinde</option>
              <option value="red">Süresi dolmuş</option>
              <option value="grey">Kayıt yok</option>
            </select>
            <input
              placeholder="Vardiya"
              style={{maxWidth: 120}}
              value={filters.shift}
              onChange={(e) => setFilters({...filters, shift: e.target.value})}
              onKeyDown={(e) => e.key === 'Enter' && reloadMembers()}
            />
            <button type="button" className="secondary mini" onClick={reloadMembers} disabled={busy}>Filtrele</button>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Ad Soyad</th>
                  <th>Ekip</th>
                  <th>Üyelik</th>
                  <th>Görev</th>
                  <th>Vardiya</th>
                  <th>Belge</th>
                  <th>Bitiş</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {members.length === 0 && (
                  <tr><td colSpan={8} className="muted">Bu filtreye uygun üye bulunamadı.</td></tr>
                )}
                {members.map((m) => (
                  <tr key={m.id}>
                    <td>
                      <strong>{m.employee_name}</strong>
                      {m.is_leader && <span className="status-badge badge-ok" style={{marginLeft: 6}}>Lider</span>}
                      {m.warnings?.length > 0 && (
                        <div className="muted" style={{fontSize: 11, color: '#b45309'}}>{m.warnings[0]}</div>
                      )}
                    </td>
                    <td>{m.team_name}</td>
                    <td>{m.membership === 'asil' ? 'Asıl' : 'Yedek'}</td>
                    <td>{m.role_title || '—'}</td>
                    <td>{m.shift || '—'}</td>
                    <td>{certBadge(m.cert_status)}</td>
                    <td>{m.cert_valid_until || '—'}</td>
                    <td>
                      <div className="actions">
                        <button type="button" className="secondary mini" onClick={() => letterPdf(m)}>
                          <FileText size={13} /> Yazı
                        </button>
                        {canEdit && (
                          <>
                            <button type="button" className="secondary mini" onClick={() => openTrainingModal(m)}>
                              <Plus size={13} /> Eğitim
                            </button>
                            <button type="button" className="secondary mini" onClick={() => removeMember(m)}>
                              <Trash2 size={13} /> Sil
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Modal: Yeni Ekip */}
      {teamModal && (
        <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && setTeamModal(false)}>
          <section className="modal" style={{maxWidth: 560}}>
            <header><h3>Yeni Acil Durum Ekibi</h3></header>
            <form className="form-grid" onSubmit={saveTeam}>
              <label className="field"><span>Ekip türü</span>
                <select
                  required
                  value={teamForm.type_id}
                  onChange={(e) => {
                    const t = (meta.team_types || []).find((x) => String(x.id) === e.target.value);
                    setTeamForm({...teamForm, type_id: e.target.value, name: teamForm.name || (t?.name ?? '')});
                  }}
                >
                  <option value="">Seçin</option>
                  {(meta.team_types || []).map((t) => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>
              </label>
              <label className="field"><span>Minimum üye</span>
                <input type="number" min="0" value={teamForm.min_members}
                  onChange={(e) => setTeamForm({...teamForm, min_members: e.target.value})} />
              </label>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Ekip adı</span>
                <input required value={teamForm.name} onChange={(e) => setTeamForm({...teamForm, name: e.target.value})} />
              </label>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Notlar</span>
                <textarea rows={2} value={teamForm.notes} onChange={(e) => setTeamForm({...teamForm, notes: e.target.value})} />
              </label>
              <div className="form-actions">
                <button type="button" className="secondary" onClick={() => setTeamModal(false)}>İptal</button>
                <button type="submit" disabled={busy}>Kaydet</button>
              </div>
            </form>
          </section>
        </div>
      )}

      {/* Modal: Üye ekle */}
      {memberModal && (
        <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && setMemberModal(false)}>
          <section className="modal" style={{maxWidth: 760}}>
            <header><h3>Ekip Üyesi / Destek Elemanı Ekle</h3></header>
            <form className="form-grid" onSubmit={saveMember}>
              <label className="field"><span>Ekip</span>
                <select required value={memberForm.team_id} onChange={(e) => setMemberForm({...memberForm, team_id: e.target.value})}>
                  <option value="">Seçin</option>
                  {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </label>
              <label className="field"><span>Personel</span>
                <select required value={memberForm.employee_id} onChange={(e) => setMemberForm({...memberForm, employee_id: e.target.value})}>
                  <option value="">Seçin</option>
                  {companyEmployees.map((emp) => (
                    <option key={emp.id} value={emp.id}>
                      {emp.full_name}{emp.job_title ? ` · ${emp.job_title}` : ''}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field"><span>Üyelik</span>
                <select value={memberForm.membership} onChange={(e) => setMemberForm({...memberForm, membership: e.target.value})}>
                  <option value="asil">Asıl</option>
                  <option value="yedek">Yedek</option>
                </select>
              </label>
              <label className="field" style={{flexDirection: 'row', alignItems: 'center', gap: 8}}>
                <input type="checkbox" checked={memberForm.is_leader}
                  onChange={(e) => setMemberForm({...memberForm, is_leader: e.target.checked})} />
                <span>Ekip lideri</span>
              </label>
              <label className="field"><span>Görev / Unvan</span>
                <input value={memberForm.role_title} onChange={(e) => setMemberForm({...memberForm, role_title: e.target.value})} />
              </label>
              <label className="field"><span>Vardiya</span>
                <input value={memberForm.shift} onChange={(e) => setMemberForm({...memberForm, shift: e.target.value})} />
              </label>
              <label className="field"><span>Bölüm</span>
                <input value={memberForm.section} onChange={(e) => setMemberForm({...memberForm, section: e.target.value})} />
              </label>
              <label className="field"><span>Sicil No</span>
                <input value={memberForm.personnel_no} onChange={(e) => setMemberForm({...memberForm, personnel_no: e.target.value})} />
              </label>
              <label className="field"><span>Telefon</span>
                <input value={memberForm.phone} onChange={(e) => setMemberForm({...memberForm, phone: e.target.value})} />
              </label>
              <label className="field"><span>E-posta</span>
                <input value={memberForm.email} onChange={(e) => setMemberForm({...memberForm, email: e.target.value})} />
              </label>
              <label className="field"><span>Görev başlangıç</span>
                <input type="date" value={memberForm.assign_start} onChange={(e) => setMemberForm({...memberForm, assign_start: e.target.value})} />
              </label>
              <label className="field"><span>Görev. yazı tarihi</span>
                <input type="date" value={memberForm.letter_date} onChange={(e) => setMemberForm({...memberForm, letter_date: e.target.value})} />
              </label>
              <label className="field"><span>Görev. yazı no</span>
                <input value={memberForm.letter_no} onChange={(e) => setMemberForm({...memberForm, letter_no: e.target.value})} />
              </label>
              <label className="field"><span>Görevlendiren</span>
                <input value={memberForm.assigned_by} onChange={(e) => setMemberForm({...memberForm, assigned_by: e.target.value})} />
              </label>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Notlar</span>
                <textarea rows={2} value={memberForm.notes} onChange={(e) => setMemberForm({...memberForm, notes: e.target.value})} />
              </label>
              <div className="form-actions">
                <button type="button" className="secondary" onClick={() => setMemberModal(false)}>İptal</button>
                <button type="submit" disabled={busy}>Kaydet</button>
              </div>
            </form>
          </section>
        </div>
      )}

      {/* Modal: Eğitim ekle */}
      {trainingModal && (
        <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && setTrainingModal(null)}>
          <section className="modal" style={{maxWidth: 720}}>
            <header><h3>Eğitim / Sertifika — {trainingModal.employee_name}</h3></header>
            <form className="form-grid" onSubmit={saveTraining}>
              <label className="field"><span>Eğitim türü</span>
                <input value={trainingForm.training_type} onChange={(e) => setTrainingForm({...trainingForm, training_type: e.target.value})} />
              </label>
              <label className="field"><span>Eğitim veren</span>
                <input value={trainingForm.provider} onChange={(e) => setTrainingForm({...trainingForm, provider: e.target.value})} />
              </label>
              <label className="field"><span>Eğitmen</span>
                <input value={trainingForm.trainer} onChange={(e) => setTrainingForm({...trainingForm, trainer: e.target.value})} />
              </label>
              <label className="field"><span>Eğitim tarihi</span>
                <input type="date" value={trainingForm.training_date} onChange={(e) => setTrainingForm({...trainingForm, training_date: e.target.value})} />
              </label>
              <label className="field"><span>Süre (saat)</span>
                <input type="number" min="0" step="0.5" value={trainingForm.duration_hours}
                  onChange={(e) => setTrainingForm({...trainingForm, duration_hours: e.target.value})} />
              </label>
              <label className="field"><span>Sertifika no</span>
                <input value={trainingForm.certificate_no} onChange={(e) => setTrainingForm({...trainingForm, certificate_no: e.target.value})} />
              </label>
              <label className="field"><span>Geçerlilik bitişi</span>
                <input type="date" value={trainingForm.valid_until} onChange={(e) => setTrainingForm({...trainingForm, valid_until: e.target.value})} />
              </label>
              <label className="field"><span>İlk yardım belge no</span>
                <input value={trainingForm.first_aid_cert_no} onChange={(e) => setTrainingForm({...trainingForm, first_aid_cert_no: e.target.value})} />
              </label>
              <label className="field"><span>İlk yardım merkezi</span>
                <input value={trainingForm.first_aid_center} onChange={(e) => setTrainingForm({...trainingForm, first_aid_center: e.target.value})} />
              </label>
              <label className="field"><span>İlk yardım başlangıç</span>
                <input type="date" value={trainingForm.first_aid_start} onChange={(e) => setTrainingForm({...trainingForm, first_aid_start: e.target.value})} />
              </label>
              <label className="field"><span>İlk yardım bitiş</span>
                <input type="date" value={trainingForm.first_aid_end} onChange={(e) => setTrainingForm({...trainingForm, first_aid_end: e.target.value})} />
              </label>
              <label className="field"><span>Tazeleme tarihi</span>
                <input type="date" value={trainingForm.refresh_date} onChange={(e) => setTrainingForm({...trainingForm, refresh_date: e.target.value})} />
              </label>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Belge (jpg/png/pdf)</span>
                <input type="file" accept=".jpg,.jpeg,.png,.pdf" onChange={(e) => setTrainingFile(e.target.files?.[0] || null)} />
                {trainingFile && (
                  <span className="muted" style={{fontSize: 12}}>
                    <Upload size={12} /> {trainingFile.name}
                  </span>
                )}
              </label>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Notlar</span>
                <textarea rows={2} value={trainingForm.notes} onChange={(e) => setTrainingForm({...trainingForm, notes: e.target.value})} />
              </label>
              <div className="form-actions">
                <button type="button" className="secondary" onClick={() => setTrainingModal(null)}>İptal</button>
                <button type="submit" disabled={busy}>Kaydet</button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
