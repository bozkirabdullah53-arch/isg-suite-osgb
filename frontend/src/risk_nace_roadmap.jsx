import React from 'react';

const STATUS_STYLES = {
  verified: {background: '#dcfce7', border: '#86efac', color: '#166534'},
  review_required: {background: '#fef3c7', border: '#fcd34d', color: '#92400e'},
  missing: {background: '#fee2e2', border: '#fca5a5', color: '#991b1b'},
  invalid: {background: '#fee2e2', border: '#fca5a5', color: '#991b1b'},
};

function StatusBadge({status, label}) {
  const style = STATUS_STYLES[status] || STATUS_STYLES.review_required;
  return (
    <span className="risk-nace-status" style={{
      display: 'inline-flex', alignItems: 'center', gap: 6, borderRadius: 999,
      padding: '5px 10px', border: `1px solid ${style.border}`,
      background: style.background, color: style.color, fontSize: 12, fontWeight: 800,
    }}>
      <span className="risk-nace-status-dot" style={{background: style.color}} />
      {label || 'NACE durumu'}
    </span>
  );
}

function ModulePill({value}) {
  if (!value) return null;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', borderRadius: 999,
      background: '#eef5fb', color: '#36536f', padding: '3px 8px', fontSize: 11,
    }}>
      {value}
    </span>
  );
}

function IdentityCard({data}) {
  const identity = data?.identity || {};
  const workplace = data?.workplace || {};
  const code = identity.code || workplace.nace_code || data?.entered_nace_code || '—';
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
      gap: 10, padding: 12, borderRadius: 12, background: '#f7fbff', border: '1px solid #d7e7f4',
    }}>
      <div><small style={{color: '#6b8298'}}>Firma / İşyeri</small><strong style={{display: 'block', color: '#123b5d'}}>{workplace.name || data?.company_name || '—'}</strong></div>
      <div><small style={{color: '#6b8298'}}>SGK sicil numarası</small><strong style={{display: 'block', color: '#123b5d'}}>{workplace.sgk_registry_no || '—'}</strong></div>
      <div><small style={{color: '#6b8298'}}>NACE kodu</small><strong style={{display: 'block', color: '#123b5d'}}>{code}</strong></div>
      <div style={{gridColumn: 'span 2'}}><small style={{color: '#6b8298'}}>Faaliyet</small><strong style={{display: 'block', color: '#123b5d', fontWeight: 650}}>{identity.description || 'Tam katalog açıklaması bulunmuyor.'}</strong></div>
      <div><small style={{color: '#6b8298'}}>Bölüm</small><strong style={{display: 'block', color: '#123b5d'}}>{identity.section_code ? `${identity.section_code} · ${identity.section_name || ''}` : '—'}</strong></div>
      <div><small style={{color: '#6b8298'}}>Tehlike sınıfı</small><strong style={{display: 'block', color: '#123b5d'}}>{identity.hazard_class || workplace.hazard_class || '—'}</strong></div>
    </div>
  );
}

function Coverage({coverage}) {
  if (!coverage) return null;
  const metrics = [
    ['Risk kaydı', coverage.risk_records],
    ['Bölüm', coverage.departments],
    ['Açık DÖF', coverage.open_dofs],
    ['Tamamlanan DÖF', coverage.completed_dofs],
  ];
  return (
    <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: 8}}>
      {metrics.map(([label, value]) => (
        <div key={label} style={{padding: '9px 10px', borderRadius: 10, background: '#f8fafc', border: '1px solid #e2e8f0'}}>
          <small style={{display: 'block', color: '#64748b'}}>{label}</small>
          <strong style={{fontSize: 19, color: '#123b5d'}}>{value ?? 0}</strong>
        </div>
      ))}
    </div>
  );
}

function RiskDomains({items, title}) {
  return (
    <div>
      <h4 style={{margin: '0 0 8px', color: '#123b5d'}}>{title}</h4>
      {items?.length ? (
        <div style={{display: 'flex', flexWrap: 'wrap', gap: 7}}>
          {items.map((item) => (
            <span key={`${item.kind || 'technical'}-${item.key}`} title={item.description} style={{
              display: 'inline-flex', alignItems: 'center', gap: 5, borderRadius: 999,
              background: item.kind === 'special' ? '#fff7ed' : '#eef5fb',
              border: `1px solid ${item.kind === 'special' ? '#fed7aa' : '#cfe3f2'}`,
              color: item.kind === 'special' ? '#9a3412' : '#36536f', padding: '6px 10px', fontSize: 12,
            }}>
              {item.label || item.key}
            </span>
          ))}
        </div>
      ) : (
        <p style={{margin: 0, color: '#64748b', fontSize: 13}}>Bu NACE için kontrollü teknik eşleştirme yok; uzman saha incelemesi gerekiyor.</p>
      )}
    </div>
  );
}

export function NaceRoadmapSummary({data, loading, error, onOpen}) {
  if (loading) {
    return <section className="risk-panel" style={{marginBottom: 16}}><p style={{margin: 0, color: '#64748b'}}>NACE risk kapsamı yükleniyor…</p></section>;
  }
  if (error) {
    return (
      <section className="risk-panel" style={{marginBottom: 16, border: '1px solid #fca5a5'}}>
        <strong style={{color: '#991b1b'}}>NACE risk kapsamı okunamadı.</strong>
        <p style={{margin: '5px 0 0', color: '#7f1d1d', fontSize: 13}}>Mevcut risk kayıtları etkilenmedi. Ayrıntıyı açıp tekrar deneyin.</p>
      </section>
    );
  }
  if (!data) return null;
  const identity = data.identity || {};
  const workplace = data.workplace || {};
  const domains = [...(data.technical_risk_tags || []), ...(data.special_risks || [])];
  const naceCode = identity.code || workplace.nace_code || data.entered_nace_code || 'NACE kodu yok';
  const workplaceName = workplace.name || data.company_name || 'İşyeri';
  return (
    <section className="risk-panel risk-nace-summary" style={{marginBottom: 16}}>
      <div className="risk-nace-summary-head">
        <div className="risk-nace-summary-heading">
          <span className="risk-nace-eyebrow">NACE KAPSAMI · SEÇİLİ İŞYERİ</span>
          <h2>NACE risk kapsamı</h2>
          <p>{identity.description || 'Kod doğrulaması gerekiyor'}</p>
        </div>
        <StatusBadge status={data.status} label={data.status_label} />
      </div>

      <div className="risk-nace-identity-strip">
        <div className="risk-nace-workplace">
          <span>İşyeri</span>
          <strong>{workplaceName}</strong>
        </div>
        <div className="risk-nace-meta-item">
          <span>SGK sicil numarası</span>
          <strong>{workplace.sgk_registry_no || '—'}</strong>
        </div>
        <div className="risk-nace-meta-item">
          <span>NACE kodu</span>
          <strong>{naceCode}</strong>
        </div>
      </div>

      <div className="risk-nace-summary-body">
        <div className="risk-nace-stat-grid">
          <div className="risk-nace-stat">
            <strong>{domains.length}</strong>
            <span>Kontrollü risk başlığı</span>
          </div>
          <div className="risk-nace-stat">
            <strong>{data.report_checklist?.length || 0}</strong>
            <span>Rapor kontrol maddesi</span>
          </div>
        </div>

        {data.next_action && (
          <div className="risk-nace-next-step">
            <span className="risk-nace-next-label">SONRAKİ ADIM</span>
            <p>{data.next_action}</p>
          </div>
        )}

        <button type="button" className="btn btn-ghost btn-sm risk-nace-detail-button" onClick={onOpen}>
          Ayrıntılı NACE yol haritası <span aria-hidden="true">↗</span>
        </button>
      </div>
    </section>
  );
}

export function NaceRoadmapPanel({data, loading, error, onRefresh}) {
  if (loading) return <section className="panel"><p style={{margin: 0, color: '#64748b'}}>NACE yol haritası hazırlanıyor…</p></section>;
  if (error) {
    return (
      <section className="panel">
        <div className="error">NACE yol haritası yüklenemedi: {error}</div>
        {onRefresh && <button type="button" className="btn btn-ghost btn-sm" onClick={onRefresh} style={{marginTop: 10}}>Tekrar dene</button>}
      </section>
    );
  }
  if (!data) return <section className="panel"><p style={{margin: 0, color: '#64748b'}}>Firma seçildiğinde NACE yol haritası görünür.</p></section>;

  const identity = data.identity || {};
  const coverage = data.coverage || {};
  return (
    <section>
      <div className="risk-section-title">
        NACE Yol Haritası
        <span>Seçilen işyeri için risk analizi kapsamı ve mevzuat kontrol listesi</span>
      </div>
      <section className="panel" style={{marginBottom: 16}}>
        <div style={{display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'flex-start', marginBottom: 12}}>
          <div>
            <h3 style={{margin: 0}}>NACE kimliği ve güvenli kullanım sınırı</h3>
            <p style={{margin: '5px 0 0', color: '#64748b', fontSize: 13}}>Seçilen firma kartındaki NACE ve SGK sicil bilgisi otomatik alınır; NACE yalnızca başlangıç kapsamıdır ve saha doğrulaması yapılmadan otomatik risk üretmez.</p>
          </div>
          <div style={{display: 'flex', gap: 8, alignItems: 'center'}}>
            <StatusBadge status={data.status} label={data.status_label} />
            {onRefresh && <button type="button" className="btn btn-ghost btn-sm" onClick={onRefresh}>Yenile</button>}
          </div>
        </div>
        <IdentityCard data={data} />
        {(data.warnings || []).map((warning) => <div key={warning} style={{marginTop: 8, padding: '8px 10px', borderRadius: 9, background: '#fff7ed', border: '1px solid #fed7aa', color: '#9a3412', fontSize: 12.5}}>{warning}</div>)}
      </section>

      <section className="panel" style={{marginBottom: 16}}>
        <h3 style={{margin: '0 0 4px'}}>NACE'ye göre kontrol edilecek risk alanları</h3>
        <p style={{margin: '0 0 12px', color: '#64748b', fontSize: 13}}>Başlıklar öneri/kapsam listesidir. Her biri bölüm ve gerçek faaliyet üzerinden uzman tarafından doğrulanır.</p>
        <RiskDomains items={data.technical_risk_tags} title="Teknik risk başlıkları" />
        <div style={{height: 1, background: '#e2e8f0', margin: '16px 0'}} />
        <RiskDomains items={data.special_risks} title="Özel risk senaryoları" />
        {!!data.related_hazard_categories?.length && <p style={{margin: '14px 0 0', color: '#64748b', fontSize: 12.5}}><strong>İlgili tehlike kütüphanesi alanları:</strong> {data.related_hazard_categories.join(' · ')}</p>}
      </section>

      <section className="panel" style={{marginBottom: 16}}>
        <h3 style={{margin: '0 0 4px'}}>Risk analizi raporunda bulunması gerekenler</h3>
        <p style={{margin: '0 0 12px', color: '#64748b', fontSize: 13}}>Mevzuat başlıkları rapor kapsamını kontrol etmek içindir; resmi değerlendirme ekip ve işveren onayı ile tamamlanır.</p>
        <div style={{display: 'grid', gap: 9}}>
          {(data.report_checklist || []).map((item, index) => (
            <div key={item.key} style={{display: 'grid', gridTemplateColumns: '30px 1fr auto', gap: 9, alignItems: 'start', padding: '9px 10px', borderRadius: 9, background: '#f8fafc', border: '1px solid #e2e8f0'}}>
              <strong style={{color: '#0f766e'}}>{index + 1}</strong>
              <div><strong style={{color: '#123b5d'}}>{item.title}</strong><p style={{margin: '3px 0 0', fontSize: 12.5, color: '#64748b'}}>{item.description}</p><p style={{margin: '3px 0 0', fontSize: 11.5, color: '#7c8fa3'}}>{item.legal_basis}</p></div>
              <ModulePill value={item.module} />
            </div>
          ))}
        </div>
      </section>

      <section className="panel" style={{marginBottom: 16}}>
        <h3 style={{margin: '0 0 4px'}}>Uygulama yol haritası</h3>
        <p style={{margin: '0 0 12px', color: '#64748b', fontSize: 13}}>Kapsamdan izlemeye kadar sıralı iş akışı.</p>
        <div style={{display: 'grid', gap: 10}}>
          {(data.roadmap || []).map((step, index) => (
            <div key={step.key} style={{display: 'grid', gridTemplateColumns: '34px 1fr auto', gap: 10, alignItems: 'start'}}>
              <div style={{width: 28, height: 28, borderRadius: 999, background: '#0f766e', color: '#fff', display: 'grid', placeItems: 'center', fontWeight: 800, fontSize: 12}}>{index + 1}</div>
              <div><strong style={{color: '#123b5d'}}>{step.title}</strong><p style={{margin: '3px 0 0', color: '#64748b', fontSize: 12.5}}>{step.description}</p><p style={{margin: '3px 0 0', color: '#7c8fa3', fontSize: 11.5}}>{step.legal_basis}</p></div>
              <ModulePill value={step.module} />
            </div>
          ))}
        </div>
      </section>

      <section className="panel" style={{marginBottom: 16}}>
        <h3 style={{margin: '0 0 4px'}}>Mevcut kapsam göstergesi</h3>
        <p style={{margin: '0 0 12px', color: '#64748b', fontSize: 13}}>Bu sayaçlar yol haritasını yönlendirir; kayıtların içeriği uzman doğrulamasına tabidir.</p>
        <Coverage coverage={coverage} />
        {!!coverage.gaps?.length && <div style={{marginTop: 10}}>{coverage.gaps.map((gap) => <div key={gap} style={{color: '#9a3412', background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 8, padding: '7px 9px', fontSize: 12.5, marginTop: 6}}>{gap}</div>)}</div>}
        {data.next_action && <p style={{margin: '12px 0 0', color: '#36536f', fontSize: 13}}><strong>Önerilen sonraki adım:</strong> {data.next_action}</p>}
      </section>

      <section className="panel" style={{marginBottom: 16}}>
        <h3 style={{margin: '0 0 4px'}}>Mevzuat dayanak başlıkları</h3>
        <p style={{margin: '0 0 10px', color: '#64748b', fontSize: 12.5}}>{data.regulations?.source_note}</p>
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12}}>
          <div><strong style={{color: '#123b5d'}}>Ortak mevzuat</strong><ul style={{margin: '7px 0 0', paddingLeft: 18}}>{(data.regulations?.common || []).map((item) => <li key={item} style={{marginBottom: 4, fontSize: 12.5, color: '#64748b'}}>{item}</li>)}</ul></div>
          <div><strong style={{color: '#123b5d'}}>NACE/risk alanı ile ilişkili</strong><ul style={{margin: '7px 0 0', paddingLeft: 18}}>{(data.regulations?.nace_related || []).map((item) => <li key={item} style={{marginBottom: 4, fontSize: 12.5, color: '#64748b'}}>{item}</li>)}{!data.regulations?.nace_related?.length && <li style={{fontSize: 12.5, color: '#64748b'}}>Teknik risk eşleştirmesi tamamlanınca daraltılır.</li>}</ul></div>
        </div>
      </section>
    </section>
  );
}
