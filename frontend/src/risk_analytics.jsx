import React, {useEffect, useMemo, useRef, useState} from 'react';
import {
  Accessibility,
  Activity,
  AlertTriangle,
  BarChart3,
  Beaker,
  Brain,
  Building2,
  Info,
  RefreshCw,
  ShieldCheck,
  Users,
} from 'lucide-react';
import {api} from './api';
import {persistSelectedCompanyId, readPersistedCompanyId} from './nace_context';
import './risk_analytics.css';

const TYPE_ICONS = {
  physical: Activity,
  chemical: Beaker,
  biological: ShieldCheck,
  ergonomic: Accessibility,
  psychosocial: Brain,
  other: AlertTriangle,
};

function number(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return '0';
  return new Intl.NumberFormat('tr-TR', {maximumFractionDigits: 1}).format(parsed);
}

function percent(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return '0%';
  return `${new Intl.NumberFormat('tr-TR', {maximumFractionDigits: 1}).format(parsed)}%`;
}

function exposureSourceLabel(source) {
  if (source === 'reported') return 'risk kaydı';
  if (source === 'personnel_match') return 'personel eşleşmesi';
  return 'eşleşme bekliyor';
}

function StatusPill({status, label}) {
  const tone = status === 'verified' ? 'is-success' : status === 'missing' || status === 'invalid' ? 'is-danger' : 'is-warning';
  return <span className={`ra-status-pill ${tone}`}><span />{label || 'NACE durumu'}</span>;
}

function TypeIcon({type}) {
  const Icon = TYPE_ICONS[type] || AlertTriangle;
  return <Icon size={18} strokeWidth={2.2} aria-hidden="true" />;
}

function MetricCard({icon: Icon, label, value, note, tone = 'teal'}) {
  return (
    <article className={`ra-metric-card ra-metric-card--${tone}`}>
      <div className="ra-metric-icon"><Icon size={18} aria-hidden="true" /></div>
      <div className="ra-metric-copy">
        <span>{label}</span>
        <strong>{value}</strong>
        {note && <small>{note}</small>}
      </div>
    </article>
  );
}

function DistributionBar({item, rank}) {
  const width = Math.max(0, Math.min(100, Number(item.percentage) || 0));
  return (
    <div className="ra-distribution-row">
      <div className="ra-distribution-label">
        <span className="ra-rank">{rank}</span>
        <span className="ra-type-icon" style={{color: item.color}}><TypeIcon type={item.hazard_type || item.key} /></span>
        <div>
          <strong>{item.label}</strong>
          <small>{item.category || `${number(item.risk_count)} risk kaydı`}</small>
        </div>
      </div>
      <div className="ra-distribution-track" aria-label={`${item.label}: ${percent(item.percentage)}`}>
        <span style={{width: `${width}%`, background: item.color || '#0f766e'}} />
      </div>
      <div className="ra-distribution-value">
        <strong>{percent(item.percentage)}</strong>
        <small>{number(item.risk_count)} kayıt</small>
      </div>
    </div>
  );
}

function RiskTypeCard({item}) {
  return (
    <article className="ra-type-card" style={{'--ra-type-color': item.color || '#64748b'}}>
      <div className="ra-type-card-head">
        <span className="ra-type-card-icon"><TypeIcon type={item.key} /></span>
        <div><strong>{item.label}</strong><small>{item.description}</small></div>
      </div>
      <div className="ra-type-card-stats">
        <div><strong>{number(item.risk_count)}</strong><span>Risk kaydı</span></div>
        <div><strong>{number(item.exposed_worker_count)}</strong><span>Maruz kalan çalışan sayısı</span></div>
        <div><strong>{percent(item.percentage)}</strong><span>Dominans payı</span></div>
      </div>
    </article>
  );
}

function DonutChart({items}) {
  const active = items.filter((item) => Number(item.dominance_score) > 0);
  const background = useMemo(() => {
    if (!active.length) return 'conic-gradient(#e2e8f0 0 100%)';
    let cursor = 0;
    const stops = active.map((item, index) => {
      const start = cursor;
      const end = index === active.length - 1 ? 100 : Math.min(100, cursor + (Number(item.percentage) || 0));
      cursor = end;
      return `${item.color || '#64748b'} ${start}% ${end}%`;
    });
    return `conic-gradient(${stops.join(', ')})`;
  }, [active]);

  return (
    <div className="ra-donut-wrap">
      <div className="ra-donut" style={{background}} aria-label="Risk türleri baskınlık grafiği">
        <div><strong>{percent(active[0]?.percentage || 0)}</strong><span>en baskın tür</span></div>
      </div>
      <div className="ra-donut-legend">
        {(items || []).map((item) => (
          <div key={item.key}>
            <span style={{background: item.color || '#64748b'}} />
            <strong>{item.label}</strong>
            <small>{percent(item.percentage)}</small>
          </div>
        ))}
      </div>
    </div>
  );
}

export function RiskAnalyticsPage({user, onNavigate}) {
  const workplaceAccount = user?.role === 'company_admin' && Number(user?.company_id) > 0;
  const [companies, setCompanies] = useState([]);
  const [companyId, setCompanyId] = useState(
    workplaceAccount && user?.company_id
      ? String(user.company_id)
      : readPersistedCompanyId()
  );
  const companyIdRef = useRef(companyId);
  const [data, setData] = useState(null);
  const analyticsRequestRef = useRef(0);
  const [busy, setBusy] = useState(false);
  const [companyBusy, setCompanyBusy] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setCompanyBusy(true);
      try {
        const rows = await api('/companies');
        if (cancelled) return;
        const list = Array.isArray(rows) ? rows : [];
        setCompanies(list);
        const preferred = workplaceAccount && user?.company_id
          ? String(user.company_id)
          : readPersistedCompanyId();
        const preferredExists = preferred && list.some((item) => String(item.id) === preferred);
        const singleAssignedCompany = !preferredExists
          && !workplaceAccount
          && user?.role !== 'global_admin'
          && list.length === 1
          ? String(list[0].id)
          : '';
        const nextCompanyId = preferredExists ? preferred : singleAssignedCompany;
        if (String(companyIdRef.current || '') !== String(nextCompanyId || '')) {
          analyticsRequestRef.current += 1;
          setData(null);
          companyIdRef.current = nextCompanyId;
          setCompanyId(nextCompanyId);
        }
        if (nextCompanyId && !workplaceAccount) persistSelectedCompanyId(nextCompanyId);
        if (!nextCompanyId && !workplaceAccount) persistSelectedCompanyId('');
      } catch (loadError) {
        if (!cancelled) setError(loadError.message || 'İşyeri listesi yüklenemedi.');
      } finally {
        if (!cancelled) setCompanyBusy(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user?.company_id, user?.role]);

  useEffect(() => {
    function handleCompanySelected(event) {
      const detail = event.detail || {};
      const next = String(detail.companyId ?? detail.company?.id ?? '');
      if (!next || (workplaceAccount && next !== String(user?.company_id || ''))) return;
      companyIdRef.current = next;
      setCompanyId(next);
    }

    function handleCompanyReset() {
      if (workplaceAccount) return;
      analyticsRequestRef.current += 1;
      setCompanyId('');
      companyIdRef.current = '';
      setData(null);
    }

    window.addEventListener('isg:company-selected', handleCompanySelected);
    window.addEventListener('isg:nace-context-reset', handleCompanyReset);
    return () => {
      window.removeEventListener('isg:company-selected', handleCompanySelected);
      window.removeEventListener('isg:nace-context-reset', handleCompanyReset);
    };
  }, [user?.company_id, workplaceAccount]);

  async function loadAnalytics(id = companyId) {
    const requestId = ++analyticsRequestRef.current;
    if (!id) {
      setData(null);
      setBusy(false);
      return;
    }
    setBusy(true);
    setError('');
    setData(null);
    try {
      const result = await api(`/risks/analytics?company_id=${encodeURIComponent(id)}`);
      if (requestId === analyticsRequestRef.current) setData(result);
    } catch (loadError) {
      if (requestId === analyticsRequestRef.current) {
        setError(loadError.message || 'Risk analitiği yüklenemedi.');
      }
    } finally {
      if (requestId === analyticsRequestRef.current) setBusy(false);
    }
  }

  useEffect(() => {
    if (!companyId) {
      analyticsRequestRef.current += 1;
      setData(null);
      setBusy(false);
      setError('');
      return;
    }
    void loadAnalytics(companyId);
  }, [companyId]);

  function handleCompanyChange(event) {
    const nextCompanyId = event.target.value;
    const selected = companies.find((item) => String(item.id) === String(nextCompanyId));
    analyticsRequestRef.current += 1;
    setData(null);
    setError('');
    setBusy(false);
    setCompanyId(nextCompanyId);
    companyIdRef.current = nextCompanyId;
    persistSelectedCompanyId(nextCompanyId);
    if (selected) {
      window.dispatchEvent(new CustomEvent('isg:company-selected', {
        detail: {companyId: String(nextCompanyId), company: selected, source: 'risk-analytics'},
      }));
    } else {
      window.dispatchEvent(new CustomEvent('isg:nace-context-reset', {
        detail: {source: 'risk-analytics'},
      }));
    }
  }

  const selectedCompany = companies.find((item) => String(item.id) === String(companyId));
  const summary = data?.summary || {};
  const types = data?.risk_types || [];
  const dominantRisks = data?.dominant_risks || [];
  const potentialHazards = data?.potential_hazards || [];

  return (
    <div className="ra-page">
      <header className="ra-hero">
        <div>
          <h1><BarChart3 size={27} aria-hidden="true" /> Tehlike ve Risk Analitiği</h1>
          <p>NACE kodundan gelen aday tehlike kaynaklarını, işyerinin gerçek risk değerlendirmesi ve personel kapsamıyla birlikte izleyin; baskın riski ve maruz kalan kişi sayısını tek bakışta görün.</p>
        </div>
        <div className="ra-hero-badge"><ShieldCheck size={18} /> Salt okunur karar destek</div>
      </header>

      <section className="ra-toolbar">
        <div className="ra-workplace-identity">
          <span><Building2 size={15} /> ANALİZ KAPSAMI</span>
          <strong>{data?.company?.name || selectedCompany?.name || (companyId ? 'İşyeri' : 'İşyeri seçiniz')}</strong>
          <small>NACE ve risk kayıtları aynı işyeri kapsamından okunur.</small>
        </div>
        {workplaceAccount ? (
          <div className="ra-bound-company"><span>Bağlı işyeri</span><strong>{selectedCompany?.name || data?.company?.name || '—'}</strong></div>
        ) : (
          <label className="ra-company-select">
            <span>İşyeri seçin</span>
            <select value={companyId} onChange={handleCompanyChange} disabled={companyBusy || !companies.length}>
              <option value="">İşyeri seçiniz</option>
              {companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
            </select>
          </label>
        )}
        <div className="ra-toolbar-actions">
          {onNavigate && user?.role === 'safety_specialist' && <button type="button" className="ra-secondary-button" onClick={() => { if (companyId) persistSelectedCompanyId(companyId); onNavigate('risk'); }}>Risk kayıtlarına git</button>}
          <button type="button" className="ra-refresh-button" onClick={() => loadAnalytics()} disabled={!companyId || busy}><RefreshCw size={16} className={busy ? 'ra-spin' : ''} /> Yenile</button>
        </div>
      </section>

      {error && <div className="ra-alert ra-alert--error"><AlertTriangle size={17} /><span>{error}</span></div>}
      {busy && <div className="ra-loading"><RefreshCw size={20} className="ra-spin" /><span>İşyeri risk analitiği hazırlanıyor…</span></div>}
      {!busy && !companyId && !error && <div className="ra-empty"><Building2 size={30} /><strong>Analiz için bir işyeri seçin</strong><span>Birden fazla işyeriniz varsa kapsamı yukarıdaki seçimden belirleyin.</span></div>}

      {!busy && data && (
        <>
          <section className="ra-nace-card">
            <div className="ra-nace-main">
              <div className="ra-nace-kicker">NACE KAYNAKLI TEHLİKE KAPSAMI</div>
              <div className="ra-nace-title-row"><h2>{data.nace?.code || 'NACE kodu girilmemiş'}</h2><StatusPill status={data.nace?.status} label={data.nace?.status_label} /></div>
              <p>{data.nace?.description || 'Firma kartında tam ve doğrulanmış NACE faaliyeti bulunmuyor.'}</p>
            </div>
            <div className="ra-nace-meta">
              <div><span>Tehlike sınıfı</span><strong>{data.nace?.hazard_class || data.company?.hazard_class || '—'}</strong></div>
              <div><span>Çalışan</span><strong>{number(data.company?.active_employee_count)}</strong></div>
              <div><span>Risk kaydı</span><strong>{number(summary.risk_record_count)}</strong></div>
            </div>
          </section>

          {(data.nace_warnings || []).length > 0 && (
            <div className="ra-notice"><Info size={17} /><div>{data.nace_warnings.slice(0, 2).map((warning) => <p key={warning}>{warning}</p>)}</div></div>
          )}

          <section className="ra-metric-grid">
            <MetricCard icon={ShieldCheck} label="Baskın tehlike türü" value={summary.dominant_type || 'Henüz yok'} note={summary.dominant_risk ? `Kaynak: ${summary.dominant_risk}` : 'Risk kaydı oluştuğunda hesaplanır'} tone="teal" />
            <MetricCard icon={AlertTriangle} label="Aday tehlike kaynağı" value={number(summary.potential_hazard_count)} note="NACE profili üzerinden" tone="orange" />
            <MetricCard icon={Users} label="Riske maruz kalan çalışan sayısı" value={number(summary.unique_exposed_worker_count ?? summary.exposed_worker_count_total)} note={`${number(summary.exposure_assignments_total)} risk eşleşmesi · ${number(summary.exposure_records_matched)} personel eşleşmesi`} tone="purple" />
            <MetricCard icon={Activity} label="Risk değerlendirmesi" value={number(summary.risk_record_count)} note={`${number(summary.exposure_records_unmatched ?? summary.exposure_records_missing)} kayıtta eşleşme bekliyor`} tone="blue" />
          </section>

          <div className="ra-section-heading"><div><span>RİSK ÖNCELİKLENDİRME</span><h2>Dominant risk görünümü</h2><p>Yüzde sıralaması, risk skoru ile maruz kalan kişi sayısını birlikte dikkate alır.</p></div></div>
          <section className="ra-chart-grid">
            <article className="ra-panel ra-panel--chart">
              <div className="ra-panel-title"><div><h3>Tehlike türleri dağılımı</h3><p>Fiziksel, kimyasal, biyolojik, ergonomik ve psikososyal risklerin ağırlıklı payı</p></div><Activity size={20} /></div>
              {types.some((item) => item.risk_count > 0) ? <><DonutChart items={types} /><div className="ra-type-card-grid">{types.filter((item) => item.risk_count > 0).map((item) => <RiskTypeCard key={item.key} item={item} />)}</div></> : <div className="ra-chart-empty">Henüz işyerine ait aktif risk değerlendirmesi kaydı bulunmuyor.</div>}
            </article>
            <article className="ra-panel ra-panel--chart">
              <div className="ra-panel-title"><div><h3>En yüksek dominant riskler</h3><p>Risk kaynağı bazında ağırlıklı baskınlık sıralaması</p></div><BarChart3 size={20} /></div>
              {dominantRisks.length ? <div className="ra-distribution-list">{dominantRisks.slice(0, 8).map((item, index) => <DistributionBar key={item.key} item={{...item, label: item.label, category: `${item.hazard_type_label} · ${item.category}`}} rank={index + 1} />)}</div> : <div className="ra-chart-empty">Dominant risk grafiği için risk değerlendirmesi kaydı bekleniyor.</div>}
            </article>
          </section>

          <section className="ra-panel">
            <div className="ra-panel-title"><div><h3>NACE’ye göre olası tehlike kaynakları</h3><p>Bu başlıklar saha doğrulamasına açılan kontrollü adaylardır; gerçekleşmiş risk olarak kabul edilmez.</p></div><AlertTriangle size={20} /></div>
            {potentialHazards.length ? <div className="ra-potential-grid">{potentialHazards.map((item) => <article key={`${item.kind}-${item.key}`} className={`ra-potential-card ${item.validated ? 'is-linked' : ''}`}><div className="ra-potential-card-head"><span className="ra-potential-icon"><TypeIcon type={item.hazard_type} /></span><div><strong>{item.label}</strong><small>{item.hazard_type_label}{item.category ? ` · ${item.category}` : ''}</small></div></div><p>{item.description || 'Faaliyet ve bölüm bazında saha doğrulaması yapılmalıdır.'}</p><span className="ra-validation-badge">{item.validation_label}</span></article>)}</div> : <div className="ra-chart-empty">Bu NACE için kontrollü teknik risk eşleştirmesi bulunmuyor. Tam NACE kodunu doğrulayın.</div>}
          </section>

          <section className="ra-panel">
            <div className="ra-panel-title"><div><h3>İşyeri risk değerlendirmesi özeti</h3><p>Her satır, ilgili tehlike türüne maruz kalan çalışan sayısını gösterir. Aynı çalışan o satırda ve işyeri toplamında yalnızca bir kez sayılır; farklı tehlike türlerinde yer alabilir.</p></div><Users size={20} /></div>
            <div className="ra-table-wrap"><table className="ra-table"><thead><tr><th>Tehlike türü</th><th>Risk kaydı</th><th>Riske maruz kalan çalışan sayısı</th><th>Dominans skoru</th><th>Pay</th></tr></thead><tbody>{types.map((item) => <tr key={item.key}><td><span className="ra-table-type"><span style={{background: item.color}} />{item.label}</span></td><td>{number(item.risk_count)}</td><td>{number(item.exposed_worker_count)}</td><td>{number(item.dominance_score)}</td><td><strong>{percent(item.percentage)}</strong></td></tr>)}{!types.some((item) => item.risk_count > 0) && <tr><td colSpan="5" className="ra-table-empty">Henüz risk değerlendirmesi kaydı yok.</td></tr>}</tbody></table></div>
          </section>

          {data.observed_risks?.length > 0 && <section className="ra-panel"><div className="ra-panel-title"><div><h3>En yüksek öncelikli kayıtlar</h3><p>İlk 10 kayıt, ağırlıklı dominantlık skoruna göre sıralanır.</p></div><ShieldCheck size={20} /></div><div className="ra-observed-list">{data.observed_risks.slice(0, 10).map((item, index) => <article key={item.id || item.risk_code || index}><div className="ra-observed-rank">{String(index + 1).padStart(2, '0')}</div><div className="ra-observed-main"><strong>{item.hazard}</strong><span>{item.category} · {item.activity || 'Faaliyet belirtilmemiş'}</span></div><div className="ra-observed-score"><strong>{number(item.risk_score)}</strong><small>risk skoru</small></div><div className="ra-observed-exposure"><strong>{number(item.exposed_worker_count)}</strong><small>{exposureSourceLabel(item.exposure_count_source)}</small></div><div className="ra-observed-percent">{percent(item.percentage)}</div></article>)}</div></section>}

          <footer className="ra-methodology"><Info size={16} /><span><strong>Hesaplama notu:</strong> {data.methodology?.dominance_basis}. {data.methodology?.exposure_note}</span></footer>
        </>
      )}
    </div>
  );
}
