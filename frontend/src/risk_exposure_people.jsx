import React, {useEffect, useMemo, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {AlertTriangle, Download, GraduationCap, Search, Users, X} from 'lucide-react';
import {api} from './api';
import {exposureTrainingCsv, scopedMatches, validSelectedIds, visibleExposurePeople} from './risk_exposure_logic';

export function RiskExposurePeople({companyId, hazardType, riskId, onClose}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [filterRisk, setFilterRisk] = useState(riskId ? String(riskId) : '');
  const [query, setQuery] = useState('');
  const [includeUnmatched, setIncludeUnmatched] = useState(false);
  const [selected, setSelected] = useState([]);
  const [trainingOpen, setTrainingOpen] = useState(false);
  const [programs, setPrograms] = useState([]);
  const [programId, setProgramId] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [reviewed, setReviewed] = useState(false);
  const [trainingBusy, setTrainingBusy] = useState(false);
  const [trainingError, setTrainingError] = useState('');
  const [success, setSuccess] = useState('');
  const panel = useRef(null);
  const alive = useRef(true);
  const assigning = useRef(false);

  useEffect(() => {
    alive.current = true;
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    panel.current?.focus();
    return () => {
      alive.current = false;
      document.body.style.overflow = overflow;
      if (previous?.isConnected) previous.focus();
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({company_id: companyId});
    if (hazardType) params.set('hazard_type', hazardType);
    if (riskId) params.set('risk_id', String(riskId));
    api(`/risks/analytics/exposures?${params}`, {cache: 'no-store'}).then((result) => {
      if (cancelled) return;
      if (String(result.company?.id) !== String(companyId)) throw new Error('İşyeri kapsamı değişti. Listeyi yeniden açın.');
      setData(result);
    }).catch((err) => { if (!cancelled) setError(err.message || 'Çalışan listesi alınamadı.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [companyId, hazardType, riskId]);

  const risks = useMemo(() => new Map((data?.risks || []).map((risk) => [risk.id, risk])), [data]);
  const people = visibleExposurePeople(data, {riskId: filterRisk, query, includeUnmatched});
  const scopedRisks = (data?.risks || []).filter((risk) => !filterRisk || String(risk.id) === filterRisk);
  const pendingRisks = scopedRisks.filter((risk) => risk.source !== 'personnel_match');
  const reviewRisks = scopedRisks.filter((risk) => risk.hazard_type === 'other');
  const scopedCount = (data?.employees || []).filter((person) => scopedMatches(person, filterRisk).length).length;
  const ids = validSelectedIds(data, selected);
  const selectedProgram = programs.find((program) => String(program.id) === programId);
  const branchMismatch = selectedProgram?.branch_id && (data?.employees || []).some((person) => ids.includes(Number(person.id)) && Number(person.branch_id) !== Number(selectedProgram.branch_id));

  function select(next) {
    setSelected(next);
    setReviewed(false);
    setSuccess('');
    setTrainingError('');
  }

  function keyDown(event) {
    if (event.key === 'Escape' && !assigning.current) { event.stopPropagation(); onClose(); }
    if (event.key !== 'Tab') return;
    const targets = [...panel.current.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), summary, [tabindex="0"]')].filter((node) => node.getClientRects().length);
    const first = targets[0], last = targets[targets.length - 1];
    if (!first) { event.preventDefault(); return; }
    if (event.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && (document.activeElement === last || document.activeElement === panel.current)) { event.preventDefault(); first.focus(); }
  }

  function download() {
    const blob = new Blob([exposureTrainingCsv(data, ids, filterRisk)], {type: 'text/csv;charset=utf-8;'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `risk_egitim_listesi_${companyId}.csv`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function prepareTraining() {
    setTrainingOpen(true);
    setTrainingBusy(true);
    setTrainingError('');
    try {
      const rows = await api(`/trainings/remote/programs?company_id=${companyId}&status=published`);
      if (!alive.current) return;
      setPrograms((Array.isArray(rows) ? rows : []).filter((program) => String(program.company_id) === String(companyId) && program.status === 'published'));
    } catch (err) {
      if (alive.current) setTrainingError(err.message || 'Eğitim paketleri alınamadı.');
    } finally { if (alive.current) setTrainingBusy(false); }
  }

  async function assignTraining(event) {
    event.preventDefault();
    if (assigning.current || !reviewed || !ids.length || !selectedProgram || branchMismatch || success) return;
    assigning.current = true;
    setTrainingBusy(true);
    setTrainingError('');
    try {
      const result = await api(`/trainings/remote/programs/${selectedProgram.id}/assign`, {
        method: 'POST', _retries: 0,
        body: JSON.stringify({employee_ids: ids, branch_id: selectedProgram.branch_id || null, due_date: dueDate || null}),
      });
      if (!alive.current) return;
      setSuccess(`${result.created_count || 0} çalışan için eğitim atandı. ${result.skipped_employee_ids?.length || 0} çalışanın mevcut ataması korundu.`);
      setReviewed(false);
    } catch (err) { if (alive.current) setTrainingError(err.message || 'Eğitim atanamadı.'); }
    finally { assigning.current = false; if (alive.current) setTrainingBusy(false); }
  }

  return createPortal(
    <div className="ra-people-backdrop" onKeyDown={keyDown}>
      <section className="ra-people-dialog" ref={panel} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="ra-people-title" aria-describedby="ra-people-description">
        <div className="ra-people-head">
          <div><span><Users size={17} /> RİSK VE ÇALIŞANLAR</span><h2 id="ra-people-title">{data?.scope?.label || 'Çalışan listesi'}</h2><p>{data?.company?.name || 'İşyeri bilgileri yükleniyor…'}</p></div>
          <button type="button" className="ra-people-close" aria-label="Çalışan listesini kapat" onClick={onClose} disabled={trainingBusy}><X size={22} /></button>
        </div>
        <div className="ra-people-body">
          <p id="ra-people-description" className="ra-people-guidance">Bu kişiler otomatik eşleşme adaylarıdır; doğrulanmış maruziyet listesi değildir. Eğitim için yapılan işi ve saha kapsamını kontrol edin. Aday bulunmaması, maruziyet olmadığı anlamına gelmez.</p>
          {loading && <p role="status">Çalışanlar ve eşleşme gerekçeleri hazırlanıyor…</p>}
          {error && <p className="ra-people-error" role="alert">{error}</p>}
          {data && <>
            <div className="ra-people-metrics"><div><strong>{scopedCount}</strong><span>Otomatik çalışan adayı</span></div><div><strong>{scopedRisks.length}</strong><span>İlgili risk kaydı</span></div><div><strong>{pendingRisks.length}</strong><span>Çalışanı belirlenemeyen kayıt</span></div><div><strong>{ids.length}</strong><span>Eğitim için seçilen</span></div></div>
            <div className="ra-people-filters">
              <label><span>Risk / faaliyet</span><select value={filterRisk} disabled={Boolean(riskId) || trainingBusy} onChange={(event) => { setFilterRisk(event.target.value); select([]); }}><option value="">Bu kapsamdaki tüm riskler</option>{(data.risks || []).map((risk) => <option key={risk.id} value={risk.id}>{risk.risk_code} · {risk.hazard} · {risk.activity || risk.department || ''}</option>)}</select></label>
              <label><span>Çalışan ara</span><div className="ra-people-search"><Search size={16} /><input aria-label="Ad, bölüm veya görev ara" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Ad, bölüm veya görev" /></div></label>
            </div>
            {filterRisk && <div className="ra-people-risk-summary"><strong>{risks.get(Number(filterRisk))?.hazard}</strong><p>{risks.get(Number(filterRisk))?.risk_definition}</p><small>{risks.get(Number(filterRisk))?.department} · {risks.get(Number(filterRisk))?.activity}</small></div>}
            {reviewRisks.length > 0 && <details className="ra-people-pending" open><summary><AlertTriangle size={16} /> {reviewRisks.length} kaydın tehlike türü inceleme bekliyor</summary><div>{reviewRisks.map((risk) => <p key={risk.id}><strong>{risk.risk_code} · {risk.hazard}</strong><br />{risk.classification_note}</p>)}</div></details>}
            {pendingRisks.length > 0 && <details className="ra-people-pending"><summary><AlertTriangle size={16} /> {pendingRisks.length} kayıtta çalışanları belirlemek gerekiyor</summary><div>{pendingRisks.map((risk) => <p key={risk.id}><strong>{risk.risk_code} · {risk.hazard}</strong><br />{risk.activity} · {risk.source === 'reported' ? `Beyan edilen sayı: ${risk.reported_worker_count}; kişi bağlantısı yok.` : 'Bölüm/görev bilgileriyle çalışan bulunamadı.'}</p>)}</div></details>}
            <div className="ra-people-selection"><label><input type="checkbox" checked={includeUnmatched} disabled={trainingBusy} onChange={(event) => setIncludeUnmatched(event.target.checked)} /> Eğitim listesine manuel eklemek için diğer aktif çalışanları da göster</label><div><button type="button" disabled={!people.length || trainingBusy} onClick={() => select([...new Set([...ids, ...people.map((person) => Number(person.id))])])}>Görünenleri seç ({people.length})</button><button type="button" disabled={!ids.length || trainingBusy} onClick={() => select([])}>Seçimi temizle</button></div></div>
            <div className="ra-people-list">
              {people.map((person) => {
                const matches = scopedMatches(person, filterRisk);
                return <article key={person.id} className={ids.includes(Number(person.id)) ? 'is-selected' : ''}>
                  <label className="ra-person-identity"><input type="checkbox" aria-label={`${person.full_name} eğitim için seç`} checked={ids.includes(Number(person.id))} disabled={trainingBusy} onChange={(event) => select(event.target.checked ? [...ids, Number(person.id)] : ids.filter((id) => id !== Number(person.id)))} /><div><strong>{person.full_name || 'Ad bilgisi eksik'}</strong><span>{person.department || 'Bölüm belirtilmemiş'} · {person.job_title || 'Görev belirtilmemiş'}</span></div></label>
                    {matches.length ? <details className="ra-person-reasons"><summary>{matches.length} risk ve eşleşme gerekçesi</summary><div>{matches.map((match) => { const risk = risks.get(match.risk_id); return <div key={match.risk_id}><strong>{risk?.risk_code} · {risk?.hazard}</strong><p>{risk?.activity} · {risk?.risk_definition}</p><small>{match.match_level || 'eşleşme'} · {match.match_score || 0}/100</small><ul>{match.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></div>; })}</div></details> : <span className="ra-person-manual">Otomatik eşleşme yok · manuel eğitim seçimi</span>}
                </article>;
              })}
              {!people.length && <p className="ra-people-empty">Bu filtreyle eşleşen çalışan bulunamadı. Bölüm ve görev bilgilerini kontrol edin; gerekiyorsa diğer aktif çalışanları göstererek eğitim listesine ekleyin.</p>}
            </div>
            {trainingOpen && <form className="ra-people-training" onSubmit={assignTraining}>
              <h3><GraduationCap size={20} /> Seçilen çalışanlar için eğitim</h3><p>İşyerine tanımlanmış, bu riskin sonuçlarını ve korunma yöntemlerini kapsayan uygun paketi seçin. Yeni bir paket gerekiyorsa mevcut eğitim yönetiminden hazırlayın.</p>
              <label><span>Eğitim paketi</span><select value={programId} disabled={trainingBusy} onChange={(event) => { setProgramId(event.target.value); setReviewed(false); setSuccess(''); }} required><option value="">Uygun eğitimi seçin</option>{programs.map((program) => <option key={program.id} value={program.id}>{program.title}</option>)}</select></label>
              {!trainingBusy && !programs.length && !trainingError && <p>Bu işyerine tanımlanmış yayımlanmış eğitim paketi bulunamadı. Seçili listeyi indirerek eğitim hazırlığında kullanabilirsiniz.</p>}
              <label><span>Tamamlama tarihi (isteğe bağlı)</span><input type="date" value={dueDate} disabled={trainingBusy} onChange={(event) => { setDueDate(event.target.value); setReviewed(false); }} /></label>
              {branchMismatch && <p className="ra-people-error">Bu paket belirli bir şubeye ait. Seçilen çalışanları paketin şubesiyle uyumlu hale getirin.</p>}
              <label className="ra-people-review"><input type="checkbox" checked={reviewed} disabled={trainingBusy || Boolean(success)} onChange={(event) => setReviewed(event.target.checked)} /> Seçilen {ids.length} çalışanı ve eğitim içeriğinin bu risk kapsamına uygunluğunu kontrol ettim.</label>
              {trainingError && <p className="ra-people-error" role="alert">{trainingError}</p>}{success && <p className="ra-people-success" role="status">{success}</p>}
              <button className="ra-people-primary" type="submit" disabled={trainingBusy || !ids.length || !programId || !reviewed || Boolean(branchMismatch) || Boolean(success)}>{trainingBusy ? 'İşlem sürüyor…' : `Seçilen ${ids.length} kişiye eğitimi ata`}</button>
            </form>}
          </>}
        </div>
        <div className="ra-people-footer"><span>{ids.length} çalışan seçildi · seçimler bu eğitim hazırlığına aittir</span><div><button type="button" onClick={download} disabled={!data || !ids.length || trainingBusy}><Download size={16} /> Eğitim listesini indir</button>{data?.can_assign_training && <button type="button" className="ra-people-primary" onClick={prepareTraining} disabled={!ids.length || trainingBusy || trainingOpen}><GraduationCap size={17} /> Eğitime hazırla</button>}</div></div>
      </section>
    </div>, document.body,
  );
}
