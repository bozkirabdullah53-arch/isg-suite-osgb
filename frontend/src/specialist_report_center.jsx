import React, {useEffect, useMemo, useState} from 'react';
import {BarChart3, Building2, Download, RefreshCw} from 'lucide-react';
import {api, downloadFile} from './api';
import {persistSelectedCompanyId} from './nace_context';

const MODULE_FOR_CHECK = {
  training_compliance: 'training',
  ppe_register: 'ppe',
  periodic_control: 'periyodik_kontrol',
  workplace_measurement: 'ortam_olcum',
  emergency_plan: 'acil_plan',
  emergency_team: 'acil_ekipler',
  drill: 'tatbikat',
  ohs_committee: 'isg_kurulu',
};

const MODULE_LABEL = {
  training: 'Eğitimler',
  ppe: 'KKD Takip',
  periyodik_kontrol: 'Periyodik Kontrol',
  ortam_olcum: 'Ortam Ölçüm',
  acil_plan: 'Acil Durum Planı',
  acil_ekipler: 'Acil Ekipler',
  tatbikat: 'Tatbikat',
  isg_kurulu: 'İSG Kurulu',
  risk: 'Risk Analizi',
};

const OFFICIAL_ISG_REGULATIONS_URL = 'https://isgdb.saglik.gov.tr/TR-114278/yonetmelikler.html?Sayfa=1';
const OFFICIAL_EQUIPMENT_REGULATIONS_URL = 'https://isekipmanlari.csgb.gov.tr/mevzuat.aspx';
const OFFICIAL_LAW_6331_URL = 'https://www.mevzuat.gov.tr/MevzuatMetin/1.5.6331-20150404.pdf';

const LEGAL_REFERENCE_BY_CHECK = {
  training_compliance: {
    label: '6331 sayılı İSG Kanunu',
    url: OFFICIAL_LAW_6331_URL,
  },
  ppe_register: {
    label: 'KKD mevzuatı',
    url: OFFICIAL_ISG_REGULATIONS_URL,
  },
  periodic_control: {
    label: 'İş ekipmanları mevzuatı',
    url: OFFICIAL_EQUIPMENT_REGULATIONS_URL,
  },
  workplace_measurement: {
    label: 'İSG yönetmelikleri listesi',
    url: OFFICIAL_ISG_REGULATIONS_URL,
  },
  emergency_plan: {
    label: 'Acil durum mevzuatı',
    url: OFFICIAL_ISG_REGULATIONS_URL,
  },
  emergency_team: {
    label: 'Acil durum mevzuatı',
    url: OFFICIAL_ISG_REGULATIONS_URL,
  },
  drill: {
    label: 'Acil durum mevzuatı',
    url: OFFICIAL_ISG_REGULATIONS_URL,
  },
  ohs_committee: {
    label: 'İSG yönetmelikleri listesi',
    url: OFFICIAL_ISG_REGULATIONS_URL,
  },
};

function legalReference(checkCode) {
  return LEGAL_REFERENCE_BY_CHECK[checkCode] || {
    label: 'Resmî İSG mevzuat listesi',
    url: OFFICIAL_ISG_REGULATIONS_URL,
  };
}

function LegalLink({reference}) {
  if (!reference?.url) return null;
  return (
    <a
      href={reference.url}
      target="_blank"
      rel="noreferrer"
      style={{fontSize: 11, color: '#0369a1', fontWeight: 700, whiteSpace: 'nowrap'}}
    >
      Resmî kaynağı aç ↗
    </a>
  );
}

function Metric({label, value, tone}) {
  return (
    <article className="metric" style={{borderTop: '3px solid ' + (tone || '#0f766e')}}>
      <span>{label}</span>
      <strong>{value ?? '—'}</strong>
    </article>
  );
}

export function SpecialistReportCenterPage({onNavigate}) {
  const [data, setData] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [companyId, setCompanyId] = useState('');
  const [companiesBusy, setCompaniesBusy] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function load(id = companyId) {
    if (!id) {
      setData(null);
      return;
    }
    setBusy(true);
    setError('');
    try {
      setData(await api('/reports/specialist-summary?company_id=' + encodeURIComponent(id)));
    } catch (e) {
      setData(null);
      setError(e.message || 'Uzman raporu yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    setCompaniesBusy(true);
    api('/companies?active=true').then((rows) => {
      if (cancelled) return;
      setCompanies(Array.isArray(rows) ? rows : []);
      // Rapor merkezi her açılışta açık kapsam ister; tek işyeri olsa bile
      // otomatik seçim yapılmaz ve firma seçilmeden rapor verisi yüklenmez.
      setCompanyId('');
      setData(null);
      persistSelectedCompanyId('');
      window.dispatchEvent(new CustomEvent('isg:nace-context-reset', {
        detail: {source: 'specialist-report-center'},
      }));
    }).catch((e) => {
      if (cancelled) return;
      setCompanies([]);
      setError(e.message || 'Atanmış işyerleri yüklenemedi.');
    }).finally(() => {
      if (!cancelled) setCompaniesBusy(false);
    });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (companyId) void load(companyId);
    else setData(null);
  }, [companyId]);

  const totals = data?.totals || {};
  const reportCompanies = data?.companies || [];
  const events = data?.events || [];
  const eventGroups = useMemo(() => events.slice(0, 24), [events]);
  const selectedCompany = companies.find((row) => String(row.id) === String(companyId)) || null;

  function chooseCompany(value) {
    const next = String(value || '');
    const selected = companies.find((row) => String(row.id) === next);
    setCompanyId(next);
    setData(null);
    setError('');
    persistSelectedCompanyId(next);
    window.dispatchEvent(new CustomEvent('isg:company-selected', {
      detail: next ? {companyId: next, company: selected} : {},
    }));
  }

  async function exportReport() {
    if (!companyId) {
      setError('Rapor indirmek için önce firma / işyeri seçiniz.');
      return;
    }
    try {
      await downloadFile(
        '/reports/specialist-summary.txt?company_id=' + encodeURIComponent(companyId),
        'uzman-raporu-' + companyId + '-' + new Date().toISOString().slice(0, 10) + '.txt',
      );
    } catch (e) {
      setError(e.message || 'Rapor indirilemedi.');
    }
  }

  return (
    <>
      <div className="page-title">
        <h3 style={{display: 'flex', alignItems: 'center', gap: 8}}><BarChart3 size={22} /> Uzman Rapor Merkezi</h3>
        <div className="actions" style={{gap: 8}}>
          <button type="button" className="secondary" disabled={busy || !companyId} onClick={() => void load()}>
            <RefreshCw size={16} /> Yenile
          </button>
          <button type="button" disabled={busy || !companyId || !data} onClick={() => void exportReport()}>
            <Download size={16} /> TXT indir
          </button>
        </div>
      </div>

      <section className="panel" style={{marginBottom: 16}}>
        <p style={{margin: 0, color: '#475569', lineHeight: 1.5}}>
          Yalnız aktif görevlendirmeli işyerlerinizin sağlık dışı İSG görünümüdür. Klinik sağlık
          kayıtları bu rapora ve uzman rolüne dahil edilmez.
        </p>
        {error && <p className="error" style={{marginBottom: 0}}>{error}</p>}
      </section>


      <section className="panel" style={{marginBottom: 16, border: '1px solid #b9d4ea', background: 'linear-gradient(135deg,#f8fcff 0%,#eef8f8 100%)'}}>
        <div style={{display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', alignItems: 'flex-end'}}>
          <div style={{minWidth: 240, flex: '1 1 320px'}}>
            <div style={{display: 'flex', alignItems: 'center', gap: 8, color: '#0f766e', fontSize: 12, fontWeight: 800, letterSpacing: '.04em'}}>
              <Building2 size={17} /> AKTİF İŞYERİ KAPSAMI
            </div>
            <h3 style={{margin: '6px 0 4px'}}>Firma / işyeri seçiniz</h3>
            <p style={{margin: 0, color: '#64748b', fontSize: 13}}>
              Rapor merkezi yalnız seçtiğiniz işyerinin verilerini gösterir. Firma seçilmeden hiçbir rapor verisi yüklenmez.
            </p>
          </div>
          <label className="field" style={{margin: 0, minWidth: 280, flex: '1 1 340px'}}>
            <span>Firma / işyeri</span>
            <select value={companyId} onChange={(e) => chooseCompany(e.target.value)} disabled={companiesBusy || !companies.length}>
              <option value="">{companiesBusy ? 'İşyerleri yükleniyor…' : 'Firma seçiniz'}</option>
              {companies.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
        </div>
        {selectedCompany && (
          <div style={{display: 'flex', gap: 18, flexWrap: 'wrap', marginTop: 14, paddingTop: 12, borderTop: '1px solid #d6e8eb', fontSize: 13, color: '#475569'}}>
            <span><strong style={{color: '#123b5d'}}>Seçili firma:</strong> {selectedCompany.name}</span>
            <span><strong style={{color: '#123b5d'}}>NACE:</strong> {selectedCompany.nace_code || '—'}</span>
            <span><strong style={{color: '#123b5d'}}>Tehlike:</strong> {selectedCompany.hazard_class || 'Belirlenmedi'}</span>
          </div>
        )}
      </section>

      {!companyId ? (
        <section className="panel" style={{marginBottom: 16, textAlign: 'center', padding: '38px 24px'}}>
          <Building2 size={38} color="#0f766e" style={{marginBottom: 8}} />
          <h3 style={{margin: '0 0 6px'}}>Başlamak için firma seçiniz</h3>
          <p style={{margin: 0, color: '#64748b', fontSize: 14}}>
            Uzman Rapor Merkezi, firma seçildikten sonra yalnız o işyerinin sayaçlarını, uygunluk durumunu ve aksiyonlarını getirir.
          </p>
        </section>
      ) : (
        <>
      <div className="cards" style={{marginBottom: 16}}>
        <Metric label="İşyeri" value={totals.workplaces} />
        <Metric label="Aktif çalışan" value={totals.employees} />
        <Metric label="Açık risk" value={totals.open_risks} tone="#dc2626" />
        <Metric label="Açık olay" value={totals.open_incidents} tone="#d97706" />
        <Metric label="KKD zimmet" value={totals.active_ppe} tone="#7c3aed" />
        <Metric label="Yaklaşan / geciken" value={totals.overdue_or_due} tone="#b91c1c" />
      </div>

      <section className="panel" style={{marginBottom: 16}}>
        <h4 style={{margin: '0 0 12px'}}>İşyeri uygunluk özeti</h4>
        <div className="table-wrap">
          <table>
            <thead><tr><th>İşyeri</th><th>NACE / tehlike</th><th>Çalışan</th><th>Açık risk</th><th>Kontrol</th><th>Mevzuat</th><th>İşlem</th></tr></thead>
            <tbody>
              {reportCompanies.length ? reportCompanies.map((row) => {
                const failedChecks = (row.checks || []).filter((check) => !check.passed);
                return (
                  <tr key={row.company_id}>
                    <td><strong>{row.company_name}</strong><br /><span style={{fontSize: 12, color: row.state === 'ok' ? '#166534' : '#b91c1c'}}>{row.state === 'ok' ? 'Uygun' : 'İşlem gerekli'}</span></td>
                    <td>{row.nace_code || '—'}<br /><span style={{fontSize: 12, color: '#64748b'}}>{row.hazard_class || '—'}</span></td>
                    <td>{row.employees}</td>
                    <td>{row.open_risks}</td>
                    <td>{row.checks_failed} başarısız<br /><span style={{fontSize: 12, color: '#64748b'}}>{row.due_count} yaklaşan/geciken</span></td>
                    <td>
                      {failedChecks.length ? (
                        <div style={{display: 'grid', gap: 5}}>
                          {failedChecks.slice(0, 3).map((check) => (
                            <div key={check.code}>
                              <div style={{fontSize: 12, color: '#334155'}}>{check.legal || check.title}</div>
                              <LegalLink reference={legalReference(check.code)} />
                            </div>
                          ))}
                          {failedChecks.length > 3 && (
                            <span style={{fontSize: 11, color: '#64748b'}}>+{failedChecks.length - 3} dayanak</span>
                          )}
                        </div>
                      ) : (
                        <span style={{fontSize: 12, color: '#166534'}}>Kontroller uygun</span>
                      )}
                    </td>
                    <td>
                      <div className="actions" style={{gap: 6, flexWrap: 'wrap'}}>
                        <button type="button" className="mini secondary" onClick={() => onNavigate?.('customer_360', {companyId: row.company_id})}>İşyeri</button>
                        <button type="button" className="mini" onClick={() => onNavigate?.('risk')}>Risk</button>
                        <button type="button" className="mini secondary" onClick={() => onNavigate?.('training')}>Eğitim</button>
                      </div>
                    </td>
                  </tr>
                );
              }) : <tr><td colSpan={7} className="empty">Atanmış aktif işyeri bulunamadı.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <h4 style={{margin: '0 0 12px'}}>Öncelikli aksiyonlar</h4>
        {busy && !data ? <p className="empty">Yükleniyor…</p> : eventGroups.length ? (
          <div style={{display: 'grid', gap: 8}}>
            {eventGroups.map((event, index) => {
              const module = MODULE_FOR_CHECK[event.check_code] || 'risk';
              const reference = legalReference(event.check_code);
              return (
                <article key={event.company_id + '-' + event.check_code + '-' + event.due_date + '-' + index} style={{display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', padding: '10px 12px', border: '1px solid #e2e8f0', borderRadius: 10, background: '#f8fafc'}}>
                  <div>
                    <strong>{event.title}</strong>
                    <div style={{fontSize: 13, color: '#64748b'}}>{event.company_name} · {event.detail}{event.due_date ? ' · Termin ' + event.due_date : ''}</div>
                    <div style={{marginTop: 4}}><LegalLink reference={reference} /></div>
                  </div>
                  <div className="actions" style={{gap: 6, flexWrap: 'wrap'}}>
                    <button type="button" className="mini secondary" onClick={() => onNavigate?.('customer_360', {companyId: event.company_id})}>İşyeri</button>
                    <button type="button" className="mini" onClick={() => onNavigate?.(module)}>Aç: {MODULE_LABEL[module] || module}</button>
                  </div>
                </article>
              );
            })}
          </div>
        ) : <p className="empty">Yaklaşan veya geciken aksiyon bulunamadı.</p>}
      </section>
        </>
      )}
    </>
  );
}
