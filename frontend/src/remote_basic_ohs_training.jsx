import React, {useEffect, useMemo, useRef, useState} from 'react';
import {api, API_URL, downloadFile, uploadFile} from './api';

const MANAGE_ROLES = ['global_admin', 'company_admin', 'safety_specialist'];
const HISTORICAL_VIDEO_STATUSES = ['published', 'unpublished', 'archived'];
const REMOTE_TRAINING_CANONICAL_TITLE = 'Basic Occupational Health and Safety Training';
const REMOTE_TRAINING_DISPLAY_TITLE = 'Temel İş Sağlığı ve Güvenliği Eğitimi';
const REMOTE_SECTOR_LABELS = {
  common: 'Temel Ortak İSG',
  construction: 'İnşaat',
  battery: 'Akü ve Otomotiv',
  foundry: 'Döküm',
  metal: 'Metal',
  logistics: 'Lojistik',
};
const STATUS_LABELS = {
  draft: 'Taslak',
  uploading: 'Yükleniyor',
  processing: 'İşleniyor',
  processing_failed: 'İşleme başarısız',
  ready_for_review: 'İncelemeye hazır',
  published: 'Yayımlandı',
  unpublished: 'Yayından kaldırıldı',
  archived: 'Arşivlendi',
  not_started: 'Başlamadı',
  in_progress: 'Devam ediyor',
  completed: 'Tamamlandı',
};

const cardStyle = {
  border: '1px solid #dbe5ef',
  borderRadius: 14,
  background: '#fff',
  padding: 16,
  boxShadow: '0 3px 12px rgba(15, 35, 55, .05)',
};

function statusLabel(value) {
  return STATUS_LABELS[value] || value || '—';
}

function localizedTrainingTitle(value) {
  return String(value || '').trim() === REMOTE_TRAINING_CANONICAL_TITLE
    ? REMOTE_TRAINING_DISPLAY_TITLE
    : value;
}

function sectorLabel(code) {
  return REMOTE_SECTOR_LABELS[code] || code || 'Sektör belirtilmemiş';
}

function apiAbsoluteUrl(path) {
  const base = String(API_URL || '');
  if (/^https?:\/\//i.test(base)) return new URL(path, `${base}/`).toString();
  return new URL(path, `${window.location.origin}${base || '/api/v1'}`).toString();
}

function programVideoRows(program) {
  return (program?.sections || []).flatMap((section) =>
    (section.videos || []).map((video) => ({...video, section_title: section.title, sector_code: section.sector_code})),
  );
}

function ErrorText({value}) {
  return value ? <div style={{color: '#b42318', margin: '10px 0', fontWeight: 600}}>{value}</div> : null;
}

function ProgressBadge({assignment}) {
  const summary = assignment?.summary || {};
  return (
    <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', fontSize: 12, color: '#496174'}}>
      <span>{summary.completed_video_count || 0}/{summary.required_video_count || 0} video tamamlandı</span>
      <span>·</span>
      <span>{summary.exam_passed ? 'Sınav başarılı' : summary.exam_required ? 'Sınav bekliyor' : 'Sınav zorunlu değil'}</span>
      <span>·</span>
      <strong style={{color: assignment?.status === 'completed' ? '#087443' : '#36556d'}}>{statusLabel(assignment?.status)}</strong>
    </div>
  );
}

function EmployeePanel() {
  const [assignments, setAssignments] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [assignment, setAssignment] = useState(null);
  const [activeVideo, setActiveVideo] = useState(null);
  const [playbackUrl, setPlaybackUrl] = useState('');
  const [exam, setExam] = useState(null);
  const [answers, setAnswers] = useState({});
  const [checkpointAnswers, setCheckpointAnswers] = useState({});
  const [checkpointResults, setCheckpointResults] = useState({});
  const [certificate, setCertificate] = useState(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const lastSentAt = useRef(0);

  async function loadAssignments() {
    try {
      const rows = await api('/trainings/remote/my-assignments');
      const next = Array.isArray(rows) ? rows : [];
      setAssignments(next);
      if (next.length && !selectedId) setSelectedId(String(next[0].id));
    } catch (err) {
      setError(err.message || 'Atamalar alınamadı.');
    }
  }

  async function loadAssignment(id) {
    if (!id) return;
    setBusy(true);
    setError('');
    try {
      const row = await api(`/trainings/remote/assignments/${Number(id)}`);
      setAssignment(row);
      const videos = programVideoRows(row.program);
      setActiveVideo((current) => videos.find((video) => video.id === current?.id) || videos[0] || null);
      setPlaybackUrl('');
      setExam(null);
      setAnswers({});
      setCheckpointAnswers({});
      setCheckpointResults({});
      setCertificate(null);
    } catch (err) {
      setError(err.message || 'Atama detayı alınamadı.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    loadAssignments();
  }, []);

  useEffect(() => {
    if (selectedId) loadAssignment(selectedId);
  }, [selectedId]);

  async function openVideo(video) {
    if (!assignment || !video) return;
    setActiveVideo(video);
    setPlaybackUrl('');
    setError('');
    try {
      const out = await api(
        `/trainings/remote/videos/${video.id}/playback?assignment_id=${assignment.id}`,
      );
      setPlaybackUrl(apiAbsoluteUrl(out.url));
    } catch (err) {
      setError(err.message || 'Video oynatma bağlantısı alınamadı.');
    }
  }

  async function saveProgress(eventType, currentTarget) {
    if (!assignment || !activeVideo || !currentTarget) return;
    const now = Date.now();
    if (eventType === 'progress' && now - lastSentAt.current < 5000) return;
    lastSentAt.current = now;
    try {
      const out = await api(
        `/trainings/remote/assignments/${assignment.id}/videos/${activeVideo.id}/progress`,
        {
          method: 'POST',
          body: JSON.stringify({
            position_seconds: Number(currentTarget.currentTime || 0),
            event_type: eventType,
            device_info: navigator.userAgent.slice(0, 500),
          }),
        },
      );
      setAssignment((current) => current ? {...current, summary: out.summary} : current);
      if (out.status === 'completed') setMessage('Video tamamlanması güvenli ilerleme kaydıyla işlendi.');
    } catch (err) {
      setError(err.message || 'Video ilerlemesi kaydedilemedi.');
    }
  }

  async function loadExam() {
    if (!assignment) return;
    setBusy(true);
    setError('');
    try {
      const out = await api(`/trainings/remote/assignments/${assignment.id}/exam`);
      setExam(out);
      setAnswers({});
    } catch (err) {
      setError(err.message || 'Sınav alınamadı.');
    } finally {
      setBusy(false);
    }
  }

  async function submitExam() {
    if (!assignment || !exam) return;
    setBusy(true);
    setError('');
    try {
      const out = await api(`/trainings/remote/assignments/${assignment.id}/exam/attempts`, {
        method: 'POST',
        body: JSON.stringify({answers}),
      });
      setMessage(`Sınav sonucu: ${out.score}/100 · ${out.passed ? 'Başarılı' : 'Başarısız'}.`);
      await loadAssignment(assignment.id);
      setExam(null);
    } catch (err) {
      setError(err.message || 'Sınav gönderilemedi.');
    } finally {
      setBusy(false);
    }
  }

  async function submitCheckpoint(question) {
    if (!assignment || !question || !checkpointAnswers[String(question.id)]) return;
    setBusy(true);
    setError('');
    try {
      const answer = checkpointAnswers[String(question.id)];
      const out = await api(
        `/trainings/remote/assignments/${assignment.id}/checkpoint-questions/${question.id}?answer=${encodeURIComponent(answer)}`,
        {method: 'POST'},
      );
      setCheckpointResults((current) => ({...current, [String(question.id)]: out.is_correct}));
      setAssignment((current) => current ? {...current, summary: out.summary} : current);
      setMessage(out.is_correct ? 'Video içi kontrol sorusu doğru yanıtlandı.' : 'Video içi kontrol sorusu kaydedildi; yanıt yanlış.');
    } catch (err) {
      setError(err.message || 'Video içi soru yanıtı kaydedilemedi.');
    } finally {
      setBusy(false);
    }
  }

  async function loadCertificate() {
    if (!assignment) return;
    setBusy(true);
    setError('');
    try {
      setCertificate(await api(`/trainings/remote/assignments/${assignment.id}/certificate`));
    } catch (err) {
      setError(err.message || 'Sertifika alınamadı.');
    } finally {
      setBusy(false);
    }
  }

  async function downloadCertificate() {
    if (!assignment) return;
    setBusy(true);
    setError('');
    try {
      await downloadFile(`/trainings/remote/assignments/${assignment.id}/certificate.pdf`, `temel-isg-sertifika-${assignment.id}.pdf`);
    } catch (err) {
      setError(err.message || 'Sertifika PDF indirilemedi.');
    } finally {
      setBusy(false);
    }
  }

  const videos = useMemo(() => programVideoRows(assignment?.program), [assignment]);
  const currentProgress = assignment?.video_progress?.find((row) => row.video_id === activeVideo?.id);
  const checkpointQuestions = assignment?.program?.checkpoint_questions || [];

  return (
    <section style={cardStyle} aria-label="Çalışan uzaktan eğitim paneli">
      <div style={{display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap'}}>
        <div>
          <div style={{fontSize: 12, color: '#547187', fontWeight: 700, letterSpacing: '.03em'}}>ÇALIŞAN PANELİ</div>
          <h3 style={{margin: '4px 0 4px'}}>{REMOTE_TRAINING_DISPLAY_TITLE}</h3>
          <p style={{margin: 0, color: '#5e7485', fontSize: 13}}>Video açılması tamamlanma sayılmaz; ilerleme ve sınav kaydı birlikte değerlendirilir.</p>
        </div>
        <select value={selectedId} onChange={(event) => setSelectedId(event.target.value)} aria-label="Uzaktan eğitim ataması">
          <option value="">Atama seçin</option>
          {assignments.map((row) => <option key={row.id} value={row.id}>{localizedTrainingTitle(row.program?.title) || `Eğitim #${row.program_id}`} · {statusLabel(row.status)}</option>)}
        </select>
      </div>
      <ErrorText value={error} />
      {message && <div style={{color: '#087443', margin: '10px 0', fontWeight: 600}}>{message}</div>}
      {!assignments.length && !busy && <p style={{color: '#5e7485'}}>Henüz size atanmış yayımlanmış uzaktan eğitim yok.</p>}
      {assignment && (
        <>
          <div style={{marginTop: 16, padding: 12, borderRadius: 10, background: '#f4f8fb'}}>
            <strong>{localizedTrainingTitle(assignment.program?.title)}</strong>
            <ProgressBadge assignment={assignment} />
            <div style={{marginTop: 6, color: '#36556d', fontSize: 12}}>
              Ders kapsamı: <strong>{assignment.sector_names?.length ? assignment.sector_names.join(', ') : 'Eski kayıt — tüm yayımlanmış içerik'}</strong>
            </div>
            {assignment.snapshot_warnings?.length > 0 && <p style={{margin: '8px 0 0', color: '#9a3412', fontSize: 12}}>Belge snapshot uyarısı: {assignment.snapshot_warnings.join(' ')}</p>}
          </div>
          <div style={{display: 'grid', gridTemplateColumns: 'minmax(220px, .8fr) minmax(320px, 1.5fr)', gap: 16, marginTop: 16}}>
            <div>
              <div style={{fontWeight: 700, marginBottom: 8}}>Ders videoları</div>
              {videos.map((video) => {
                const progress = assignment.video_progress?.find((row) => row.video_id === video.id);
                return (
                  <button key={video.id} type="button" onClick={() => openVideo(video)} style={{display: 'block', textAlign: 'left', width: '100%', marginBottom: 8, padding: 10, borderRadius: 9, border: `1px solid ${activeVideo?.id === video.id ? '#2474a8' : '#dbe5ef'}`, background: activeVideo?.id === video.id ? '#edf7ff' : '#fff', cursor: 'pointer'}}>
                    <strong style={{display: 'block'}}>{video.title}</strong>
                    <span style={{fontSize: 12, color: '#5e7485'}}>{video.section_title} · {progress?.status === 'completed' ? 'Tamamlandı' : `${Math.round(progress?.watched_percentage || 0)}%`}</span>
                  </button>
                );
              })}
              {!videos.length && <p style={{color: '#9a3412'}}>Yayımlanmış video bulunmuyor.</p>}
              {assignment.summary?.exam_required && <button type="button" onClick={loadExam} disabled={busy} style={{marginTop: 8}}>Final sınavını aç</button>}
            </div>
            <div>
              {activeVideo && playbackUrl ? (
                <>
                  <video
                    key={playbackUrl}
                    src={playbackUrl}
                    controls
                    playsInline
                    style={{width: '100%', maxHeight: 430, background: '#102b3d', borderRadius: 10}}
                    onPlay={(event) => saveProgress('start', event.currentTarget)}
                    onPause={(event) => saveProgress('pause', event.currentTarget)}
                    onTimeUpdate={(event) => saveProgress('progress', event.currentTarget)}
                    onEnded={(event) => saveProgress('ended', event.currentTarget)}
                    onLoadedMetadata={(event) => {
                      const saved = Number(currentProgress?.last_position_seconds || 0);
                      if (saved > 0 && saved < event.currentTarget.duration - 1) event.currentTarget.currentTime = saved;
                    }}
                  />
                  <div style={{fontSize: 12, color: '#5e7485', marginTop: 8}}>Kaldığınız yer: {Math.round(currentProgress?.last_position_seconds || 0)} sn · Eşik: %{assignment.program?.completion_threshold_percent || 90}</div>
                </>
              ) : <div style={{minHeight: 180, display: 'grid', placeItems: 'center', border: '1px dashed #b9cad8', borderRadius: 10, color: '#5e7485'}}>İzlemek için bir video seçin.</div>}
            </div>
          </div>
          {checkpointQuestions.length > 0 && (
            <div style={{marginTop: 18, paddingTop: 16, borderTop: '1px solid #dbe5ef'}}>
              <h4 style={{margin: '0 0 6px'}}>Video içi kontrol soruları</h4>
              <p style={{margin: '0 0 12px', color: '#5e7485', fontSize: 12}}>Soruların yanıtları çalışanın ilerleme kaydına bağlanır; doğru yanıtlar çalışan ekranında gösterilmez.</p>
              {checkpointQuestions.map((question, index) => {
                const result = checkpointResults[String(question.id)];
                return (
                  <fieldset key={question.id} style={{border: '1px solid #e5edf3', borderRadius: 9, padding: 12, margin: '0 0 10px'}}>
                    <legend style={{fontWeight: 700}}>{index + 1}. {question.question_text}{question.is_required ? ' *' : ''}</legend>
                    {Object.entries(question.options || {}).map(([key, label]) => (
                      <label key={key} style={{display: 'block', marginTop: 6}}><input type="radio" name={`remote-checkpoint-${question.id}`} checked={checkpointAnswers[String(question.id)] === key} onChange={() => setCheckpointAnswers((current) => ({...current, [String(question.id)]: key}))} /> {key}) {label}</label>
                    ))}
                    <div style={{display: 'flex', alignItems: 'center', gap: 10, marginTop: 10}}>
                      <button type="button" onClick={() => submitCheckpoint(question)} disabled={busy || !checkpointAnswers[String(question.id)]}>Yanıtı kaydet</button>
                      {typeof result === 'boolean' && <span style={{color: result ? '#087443' : '#b42318', fontSize: 12, fontWeight: 700}}>{result ? 'Doğru' : 'Yanlış'}</span>}
                    </div>
                  </fieldset>
                );
              })}
            </div>
          )}
          {exam && (
            <div style={{marginTop: 18, paddingTop: 16, borderTop: '1px solid #dbe5ef'}}>
              <h4 style={{margin: '0 0 12px'}}>Final sınavı</h4>
              {exam.questions.map((question, index) => (
                <fieldset key={question.id} style={{border: 0, padding: 0, margin: '0 0 14px'}}>
                  <legend style={{fontWeight: 700}}>{index + 1}. {question.question_text}</legend>
                  {Object.entries(question.options || {}).map(([key, label]) => (
                    <label key={key} style={{display: 'block', marginTop: 6}}><input type="radio" name={`remote-q-${question.id}`} checked={answers[String(question.id)] === key} onChange={() => setAnswers((current) => ({...current, [String(question.id)]: key}))} /> {key}) {label}</label>
                  ))}
                </fieldset>
              ))}
              <button type="button" onClick={submitExam} disabled={busy || Object.keys(answers).length !== exam.questions.length}>Sınavı gönder</button>
            </div>
          )}
          {(assignment.status === 'completed' || assignment.summary?.complete) && (
            <div style={{marginTop: 18, paddingTop: 16, borderTop: '1px solid #dbe5ef'}}>
              <h4 style={{margin: '0 0 8px'}}>Sertifika</h4>
              <div style={{display: 'flex', gap: 8, flexWrap: 'wrap'}}>
                <button type="button" onClick={loadCertificate} disabled={busy}>Sertifika bilgilerini getir</button>
                <button type="button" onClick={downloadCertificate} disabled={busy}>Sertifika PDF indir</button>
              </div>
              {certificate && <div style={{fontSize: 12, color: '#087443', marginTop: 8}}>Sertifika no: <strong>{certificate.certificate_number}</strong> · Doğrulama kodu: <strong>{certificate.verification_code}</strong></div>}
            </div>
          )}
        </>
      )}
    </section>
  );
}

function ManagerPanel({user}) {
  const [companies, setCompanies] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [companyId, setCompanyId] = useState('');
  const [programs, setPrograms] = useState([]);
  const [program, setProgram] = useState(null);
  const [title, setTitle] = useState(REMOTE_TRAINING_DISPLAY_TITLE);
  const [sectionTitle, setSectionTitle] = useState('Temel İş Sağlığı ve Güvenliği');
  const [selectedEmployees, setSelectedEmployees] = useState([]);
  const [employeeUsers, setEmployeeUsers] = useState([]);
  const [employeeAccess, setEmployeeAccess] = useState([]);
  const [accessEmployeeId, setAccessEmployeeId] = useState('');
  const [accessUserId, setAccessUserId] = useState('');
  const [busy, setBusy] = useState(false);
  const [uploadingSectionId, setUploadingSectionId] = useState(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [report, setReport] = useState(null);
  const [sectorScope, setSectorScope] = useState(null);
  const [selectedSectorCodes, setSelectedSectorCodes] = useState([]);
  const [sectionSectorCode, setSectionSectorCode] = useState('common');
  const [sectionSectorDrafts, setSectionSectorDrafts] = useState({});
  const [videoTitles, setVideoTitles] = useState({});
  const [checkpointDraft, setCheckpointDraft] = useState({question_text: '', options: {A: '', B: '', C: '', D: ''}, correct_option: 'A', video_id: '', sector_code: 'common'});
  const [questionBank, setQuestionBank] = useState([]);
  const [examQuestionId, setExamQuestionId] = useState('');
  const [examSectorCode, setExamSectorCode] = useState('common');
  const uploadInputRefs = useRef({});

  async function loadCompanies() {
    const rows = await api('/companies');
    const next = Array.isArray(rows) ? rows : [];
    setCompanies(next);
    const defaultId = next.find((row) => String(row.id) === String(user?.company_id))?.id || next[0]?.id;
    if (defaultId && !companyId) setCompanyId(String(defaultId));
  }

  async function loadPrograms(cid = companyId) {
    if (!cid) return;
    const rows = await api(`/trainings/remote/programs?company_id=${Number(cid)}`);
    setPrograms(Array.isArray(rows) ? rows : []);
  }

  async function loadEmployees(cid = companyId) {
    if (!cid) return;
    const rows = await api(`/employees?company_id=${Number(cid)}&active=true`);
    setEmployees(Array.isArray(rows) ? rows : []);
  }

  async function loadEmployeeAccess(cid = companyId) {
    if (!cid) return;
    try {
      const out = await api(`/trainings/remote/employee-access/candidates?company_id=${Number(cid)}`);
      setEmployeeUsers(Array.isArray(out?.users) ? out.users : []);
      setEmployeeAccess(Array.isArray(out?.access) ? out.access : []);
    } catch (err) {
      setEmployeeUsers([]);
      setEmployeeAccess([]);
      setError(err.message || 'Çalışan giriş hesapları alınamadı.');
    }
  }

  async function loadQuestionBank() {
    if (user?.role !== 'global_admin') return;
    try {
      const rows = await api('/question-bank/questions?status=published');
      setQuestionBank(Array.isArray(rows) ? rows : []);
    } catch (_err) {
      setQuestionBank([]);
    }
  }

  async function loadDetail(id) {
    if (!id) return;
    const row = await api(`/trainings/remote/programs/${Number(id)}`);
    setProgram(row);
    const scope = await api(`/trainings/remote/programs/${Number(id)}/sectors`);
    setSectorScope(scope);
    setSelectedSectorCodes(scope.mode === 'scoped' ? (scope.selected_sector_codes || []).filter((code) => code !== 'common') : []);
    setSectionSectorCode((scope.selected_sector_codes || ['common']).find((code) => code !== 'common') || 'common');
    setExamSectorCode((scope.selected_sector_codes || ['common'])[0] || 'common');
    await loadEmployees(row.company_id);
    await loadEmployeeAccess(row.company_id);
    await loadQuestionBank();
  }

  useEffect(() => {
    loadCompanies().catch((err) => setError(err.message || 'Firma listesi alınamadı.'));
  }, []);

  useEffect(() => {
    if (!companyId) return;
    loadPrograms(companyId).catch((err) => setError(err.message || 'Eğitim listesi alınamadı.'));
    loadEmployees(companyId).catch((err) => setError(err.message || 'Çalışan listesi alınamadı.'));
    loadEmployeeAccess(companyId);
  }, [companyId]);

  async function createProgram() {
    if (!companyId) return setError('Firma seçin.');
    setBusy(true); setError(''); setMessage('');
    try {
      const row = await api('/trainings/remote/programs', {method: 'POST', body: JSON.stringify({company_id: Number(companyId), title})});
      setMessage(`${REMOTE_TRAINING_DISPLAY_TITLE} taslağı oluşturuldu.`);
      await loadPrograms(companyId);
      await loadDetail(row.id);
    } catch (err) { setError(err.message || 'Eğitim oluşturulamadı.'); } finally { setBusy(false); }
  }

  async function createSection() {
    if (!program) return;
    setBusy(true); setError('');
    try {
      await api(`/trainings/remote/programs/${program.id}/sections`, {method: 'POST', body: JSON.stringify({title: sectionTitle, sector_code: sectionSectorCode})});
      await loadDetail(program.id); setMessage('Bölüm eklendi.');
    } catch (err) { setError(err.message || 'Bölüm eklenemedi.'); } finally { setBusy(false); }
  }

  async function saveSectorScope() {
    if (!program) return;
    setBusy(true); setError('');
    try {
      const out = await api(`/trainings/remote/programs/${program.id}/sectors`, {method: 'PUT', body: JSON.stringify({sector_codes: selectedSectorCodes})});
      setSectorScope(out);
      setSelectedSectorCodes((out.selected_sector_codes || []).filter((code) => code !== 'common'));
      setMessage('Firma ders kapsamı kaydedildi. Yeni çalışan atamalarında yalnızca bu sektörler açılacak.');
      await loadDetail(program.id);
    } catch (err) { setError(err.message || 'Firma ders kapsamı kaydedilemedi.'); } finally { setBusy(false); }
  }

  async function saveSectionSector(section) {
    if (!program) return;
    const sectorCode = sectionSectorDrafts[section.id] || section.sector_code || 'common';
    setBusy(true); setError('');
    try {
      await api(`/trainings/remote/sections/${section.id}`, {method: 'PATCH', body: JSON.stringify({sector_code: sectorCode})});
      await loadDetail(program.id);
      setMessage('Bölümün sektör kapsamı kaydedildi.');
    } catch (err) { setError(err.message || 'Bölüm sektörü kaydedilemedi.'); } finally { setBusy(false); }
  }

  async function uploadVideo(section, file) {
    if (!file || !program) return;
    setBusy(true); setUploadingSectionId(section.id); setError(''); setMessage(`"${file.name}" yükleniyor. Lütfen bu sayfayı kapatmayın.`);
    try {
      await uploadFile(`/trainings/remote/sections/${section.id}/videos`, file, {title: file.name.replace(/\.[^.]+$/, '') || 'Temel İSG video dersi'});
      await loadDetail(program.id); setMessage('Video yüklendi; durum işleniyor veya incelemeye hazır olabilir.');
    } catch (err) { setError(err.message || 'Video yüklenemedi.'); } finally { setBusy(false); setUploadingSectionId(null); }
  }

  async function videoAction(video, action) {
    setBusy(true); setError('');
    try {
      await api(`/trainings/remote/videos/${video.id}/${action}`, {method: 'POST'});
      await loadDetail(program.id); await loadPrograms(program.company_id);
      setMessage(action === 'publish' ? 'Video yayımlandı.' : action === 'retry-processing' ? 'Video yeniden işleme alındı.' : 'Video işlemi tamamlandı.');
    } catch (err) { setError(err.message || 'Video işlemi başarısız.'); } finally { setBusy(false); }
  }

  async function saveVideo(video) {
    const titleValue = (videoTitles[video.id] || video.title || '').trim();
    if (titleValue.length < 2) return setError('Video başlığı en az iki karakter olmalıdır.');
    setBusy(true); setError('');
    try {
      await api(`/trainings/remote/videos/${video.id}`, {method: 'PATCH', body: JSON.stringify({title: titleValue})});
      await loadDetail(program.id);
      setVideoTitles((current) => ({...current, [video.id]: titleValue}));
      setMessage('Video bilgisi güncellendi.');
    } catch (err) { setError(err.message || 'Video bilgisi güncellenemedi.'); } finally { setBusy(false); }
  }

  async function deleteVideo(video) {
    if (!program || HISTORICAL_VIDEO_STATUSES.includes(video.status)) return;
    const confirmed = window.confirm(`"${video.title}" taslak videosu silinsin mi? Bu işlem geri alınamaz.`);
    if (!confirmed) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const result = await api(`/trainings/remote/videos/${video.id}`, {method: 'DELETE'});
      await loadDetail(program.id);
      await loadPrograms(program.company_id);
      setMessage(result.storage_cleanup_pending ? 'Video silindi; depolama temizliği sıraya alındı.' : 'Taslak video silindi.');
    } catch (err) { setError(err.message || 'Video silinemedi.'); } finally { setBusy(false); }
  }

  async function previewVideo(video) {
    setBusy(true); setError('');
    try {
      const out = await api(`/trainings/remote/videos/${video.id}/playback?preview=true`);
      const previewWindow = window.open(apiAbsoluteUrl(out.url), '_blank', 'noopener,noreferrer');
      if (!previewWindow) setMessage('Önizleme bağlantısı üretildi; tarayıcı açılır pencereyi engelledi.');
    } catch (err) { setError(err.message || 'Video önizlemesi açılamadı.'); } finally { setBusy(false); }
  }

  async function programAction(action) {
    if (!program) return;
    setBusy(true); setError('');
    try {
      await api(`/trainings/remote/programs/${program.id}/${action}`, {method: 'POST'});
      await loadDetail(program.id); await loadPrograms(program.company_id);
      setMessage(action === 'publish' ? 'Eğitim çalışanlara açıldı.' : 'Eğitim durumu güncellendi.');
    } catch (err) { setError(err.message || 'Eğitim işlemi başarısız.'); } finally { setBusy(false); }
  }

  async function assign() {
    if (!program || !selectedEmployees.length) return setError('En az bir çalışan seçin.');
    setBusy(true); setError('');
    try {
      const out = await api(`/trainings/remote/programs/${program.id}/assign`, {method: 'POST', body: JSON.stringify({employee_ids: selectedEmployees.map(Number)})});
      setMessage(`${out.created_count || 0} çalışan atandı; ${out.skipped_employee_ids?.length || 0} mevcut atama korundu.`);
      setSelectedEmployees([]);
    } catch (err) { setError(err.message || 'Çalışan ataması yapılamadı.'); } finally { setBusy(false); }
  }

  async function saveEmployeeAccess() {
    if (!companyId || !accessEmployeeId || !accessUserId) return setError('Personel ve giriş hesabını birlikte seçin.');
    setBusy(true); setError('');
    try {
      await api('/trainings/remote/employee-access', {
        method: 'POST',
        body: JSON.stringify({company_id: Number(companyId), employee_id: Number(accessEmployeeId), user_id: Number(accessUserId)}),
      });
      await loadEmployeeAccess(companyId);
      setMessage('Çalışan giriş hesabı personel kaydıyla eşleştirildi.');
      setAccessEmployeeId('');
      setAccessUserId('');
    } catch (err) { setError(err.message || 'Çalışan hesabı eşleştirilemedi.'); } finally { setBusy(false); }
  }

  async function createCheckpointQuestion() {
    if (!program) return;
    const text = checkpointDraft.question_text.trim();
    const options = Object.fromEntries(Object.entries(checkpointDraft.options).map(([key, value]) => [key, value.trim()]));
    if (text.length < 3 || Object.values(options).some((value) => value.length < 1)) return setError('Video içi soru ve dört seçenek birlikte doldurulmalıdır.');
    setBusy(true); setError('');
    try {
      await api(`/trainings/remote/programs/${program.id}/checkpoint-questions`, {method: 'POST', body: JSON.stringify({question_text: text, options, correct_option: checkpointDraft.correct_option, sector_code: checkpointDraft.sector_code, video_id: checkpointDraft.video_id ? Number(checkpointDraft.video_id) : null, order_index: (program.checkpoint_questions || []).length + 1, is_required: true})});
      setCheckpointDraft({question_text: '', options: {A: '', B: '', C: '', D: ''}, correct_option: 'A', video_id: '', sector_code: 'common'});
      await loadDetail(program.id);
      setMessage('Video içi kontrol sorusu eklendi.');
    } catch (err) { setError(err.message || 'Video içi soru eklenemedi.'); } finally { setBusy(false); }
  }

  async function linkExamQuestion() {
    if (!program || !examQuestionId) return setError('Bağlanacak yayımlanmış soru ID değerini seçin.');
    const position = (program.exam_question_links || []).length + 1;
    setBusy(true); setError('');
    try {
      await api(`/trainings/remote/programs/${program.id}/exam/questions`, {method: 'POST', body: JSON.stringify({question_id: Number(examQuestionId), position, sector_code: examSectorCode})});
      setExamQuestionId('');
      await loadDetail(program.id);
      setMessage('Mevcut soru bankası sorusu final sınavına bağlandı.');
    } catch (err) { setError(err.message || 'Soru bankası sorusu bağlanamadı.'); } finally { setBusy(false); }
  }

  async function showReport() {
    if (!program) return;
    setBusy(true); setError('');
    try { setReport(await api(`/trainings/remote/programs/${program.id}/report`)); } catch (err) { setError(err.message || 'Rapor alınamadı.'); } finally { setBusy(false); }
  }

  return (
    <section style={{display: 'grid', gap: 16}} aria-label="Uzaktan Temel İş Sağlığı ve Güvenliği Eğitimi yönetimi">
      <div style={cardStyle}>
        <div style={{display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap'}}>
          <div><div style={{fontSize: 12, color: '#547187', fontWeight: 700}}>EĞİTİCİ / YÖNETİCİ PANELİ</div><h3 style={{margin: '4px 0'}}>{REMOTE_TRAINING_DISPLAY_TITLE}</h3><p style={{margin: 0, color: '#5e7485', fontSize: 13}}>Oluştur → Yükle → İşle → Düzenle → Önizle → Yayımla → Ata → Takip Et → Sınava Gir → Belgelendir → Raporla</p></div>
          <select value={companyId} onChange={(event) => {setCompanyId(event.target.value); setProgram(null);}} aria-label="Firma seçin"><option value="">Firma seçin</option>{companies.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select>
        </div>
        <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 14}}>
          <input value={title} onChange={(event) => setTitle(event.target.value)} style={{minWidth: 300, flex: 1}} aria-label="Eğitim başlığı" />
          <button type="button" onClick={createProgram} disabled={busy || !companyId}>Yeni Temel İSG Eğitimi Taslağı</button>
        </div>
        <ErrorText value={error} />
        {message && <div style={{color: '#087443', marginTop: 8, fontWeight: 600}}>{message}</div>}
      </div>

      <div style={{display: 'grid', gridTemplateColumns: 'minmax(220px, .7fr) minmax(420px, 1.5fr)', gap: 16}}>
        <div style={cardStyle}>
          <h4 style={{marginTop: 0}}>Eğitim taslakları</h4>
          {programs.map((row) => <button key={row.id} type="button" onClick={() => loadDetail(row.id)} style={{display: 'block', width: '100%', textAlign: 'left', padding: 10, marginBottom: 8, borderRadius: 9, border: `1px solid ${program?.id === row.id ? '#2474a8' : '#dbe5ef'}`, background: program?.id === row.id ? '#edf7ff' : '#fff'}}><strong>{localizedTrainingTitle(row.title)}</strong><span style={{display: 'block', fontSize: 12, color: '#5e7485'}}>{statusLabel(row.status)} · sürüm {row.revision_no}</span></button>)}
          {!programs.length && <p style={{color: '#5e7485'}}>Bu firmada uzaktan eğitim taslağı yok.</p>}
        </div>
        <div style={cardStyle}>
          {program ? (
            <>
              <div style={{display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap'}}><div><h4 style={{margin: 0}}>{localizedTrainingTitle(program.title)}</h4><div style={{fontSize: 12, color: '#5e7485'}}>{statusLabel(program.status)} · eşik %{program.completion_threshold_percent}</div></div><div style={{display: 'flex', gap: 6, flexWrap: 'wrap'}}><button type="button" onClick={() => programAction('ready-for-review')} disabled={busy}>İncelemeye hazır</button><button type="button" onClick={() => programAction('publish')} disabled={busy}>Yayımla</button><button type="button" onClick={showReport} disabled={busy}>Rapor</button></div></div>
              <div style={{marginTop: 14, padding: 16, border: '2px solid #2474a8', borderRadius: 12, background: '#f4fbff'}} aria-labelledby="remote-video-help-title">
                <h4 id="remote-video-help-title" style={{margin: 0, color: '#123b59', fontSize: 17}}>Video yükleme ve silme — çok kolay</h4>
                <ol style={{margin: '10px 0 8px', paddingLeft: 22, color: '#36556d', lineHeight: 1.65}}>
                  <li>Bölüm yoksa önce bölüm adını yazıp <strong>Bölüm ekle</strong> düğmesine bas.</li>
                  <li>İlgili bölümdeki büyük <strong>Video seç ve yükle</strong> düğmesine bas.</li>
                  <li>Bilgisayarındaki videoyu seç. Yükleme bitene kadar bekle.</li>
                  <li>Video geldiğinde satırdaki <strong>Kaydet</strong>, <strong>Önizle</strong> ve durumuna göre <strong>Video yayımla</strong> düğmelerini kullan.</li>
                  <li>Yanlış yüklediysen, yalnızca taslak videonun yanındaki kırmızı <strong>Taslak videoyu sil</strong> düğmesine bas ve onayla.</li>
                </ol>
                <div style={{padding: '9px 11px', borderRadius: 8, background: '#fff8e8', color: '#795500', fontSize: 12}}><strong>Önemli:</strong> Yayımlanmış videolar geçmiş kayıtları korumak için silinmez. Yanlış yüklemeyi yayımlamadan önce taslak durumundayken silebilirsin.</div>
              </div>
              {sectorScope && <div style={{marginTop: 14, padding: 14, border: '1px solid #b9d8e8', borderRadius: 10, background: '#f4fbff'}}>
                <div style={{display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap', alignItems: 'center'}}>
                  <div><strong>Firma için sektör / ders kapsamı</strong><div style={{fontSize: 12, color: '#5e7485', marginTop: 4}}>Tüm dersler tek katalogda tutulur. Çalışana atama yapıldığında yalnızca burada seçilen sektörler açılır ve sınav soruları aynı kapsamdan gelir.</div></div>
                  <button type="button" onClick={saveSectorScope} disabled={busy || ['published', 'archived'].includes(program.status)}>Firma ders kapsamını kaydet</button>
                </div>
                {sectorScope.mode === 'legacy' && <div style={{marginTop: 10, padding: 8, borderRadius: 7, background: '#fff8e8', color: '#8a5a00', fontSize: 12}}>Bu eski taslakta sektör kapsamı henüz kaydedilmemiş. Mevcut atamalar eski davranışla korunur; yeni atamalardan önce kapsamı kaydetmeniz önerilir.</div>}
                <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 8, marginTop: 12}}>
                  {sectorScope.sectors.map((sector) => {
                    const checked = sector.code === 'common' || selectedSectorCodes.includes(sector.code);
                    return <label key={sector.code} style={{display: 'block', padding: 10, border: `1px solid ${checked ? '#37a6c6' : '#dbe5ef'}`, borderRadius: 8, background: checked ? '#fff' : '#fafcfe', cursor: sector.locked ? 'default' : 'pointer'}}>
                      <input type="checkbox" checked={checked} disabled={sector.locked || busy || ['published', 'archived'].includes(program.status)} onChange={() => setSelectedSectorCodes((current) => current.includes(sector.code) ? current.filter((code) => code !== sector.code) : [...current, sector.code])} /> <strong>{sector.label}</strong>
                      <span style={{display: 'block', color: '#5e7485', fontSize: 11, marginTop: 4}}>{sector.description}</span>
                      <span style={{display: 'block', color: '#496174', fontSize: 11, marginTop: 5}}>{sector.section_count} bölüm · {sector.video_count} video · {sector.question_count} soru</span>
                    </label>;
                  })}
                </div>
                <div style={{fontSize: 12, color: '#36556d', marginTop: 10}}>Seçili kapsam: <strong>{['common', ...selectedSectorCodes].map(sectorLabel).join(', ')}</strong></div>
              </div>}
              <div style={{marginTop: 14, padding: 14, border: '1px solid #dbe5ef', borderRadius: 10, background: '#fbfdff'}}>
                <strong style={{display: 'block', color: '#123b59', fontSize: 15}}>1. Önce ders bölümü oluştur</strong>
                <span style={{display: 'block', color: '#5e7485', fontSize: 12, marginTop: 4}}>Örneğin: “Temel İSG”, “İnşaatta güvenlik” veya “Akü çalışma güvenliği”.</span>
                <div style={{display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 10}}>
                  <input value={sectionTitle} onChange={(event) => setSectionTitle(event.target.value)} aria-label="Bölüm başlığı" placeholder="Bölüm adı yazın" />
                  <label style={{display: 'flex', alignItems: 'center', gap: 5}}>Bölümün sektörü <select value={sectionSectorCode} onChange={(event) => setSectionSectorCode(event.target.value)}>{(sectorScope?.sectors || []).map((sector) => <option key={sector.code} value={sector.code}>{sector.label}</option>)}</select></label>
                  <button type="button" onClick={createSection} disabled={busy || ['published', 'archived'].includes(program.status)} style={{minHeight: 44, padding: '10px 16px', fontWeight: 700}}>Bölüm ekle</button>
                </div>
              </div>
              {(program.sections || []).map((section) => (
                <div key={section.id} style={{borderTop: '1px solid #e5edf3', paddingTop: 12, marginTop: 12}}>
                  <div style={{display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap'}}>
                    <div><strong>{section.order_index}. {section.title}</strong><span style={{display: 'block', color: '#5e7485', fontSize: 12, marginTop: 3}}>Sektör: {sectorLabel(section.sector_code)}</span></div>
                  </div>
                  <div style={{marginTop: 10, padding: 14, border: '2px dashed #54a8c5', borderRadius: 10, background: '#f7fcff', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap'}}>
                    <div>
                      <strong style={{display: 'block', color: '#123b59', fontSize: 15}}>Bu bölüme video ekle</strong>
                      <span style={{display: 'block', color: '#5e7485', fontSize: 12, marginTop: 4}}>MP4, WEBM veya MOV videonu bilgisayardan seç.</span>
                    </div>
                    <input
                      ref={(node) => { uploadInputRefs.current[section.id] = node; }}
                      id={`remote-video-upload-${section.id}`}
                      type="file"
                      accept="video/mp4,video/webm,video/quicktime,.m4v"
                      aria-label={`${section.title} bölümü için video seç`}
                      style={{position: 'absolute', width: 1, height: 1, padding: 0, margin: -1, overflow: 'hidden', clip: 'rect(0, 0, 0, 0)', whiteSpace: 'nowrap', border: 0}}
                      onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ''; if (file) uploadVideo(section, file); }}
                    />
                    <button type="button" onClick={() => uploadInputRefs.current[section.id]?.click()} disabled={busy || ['published', 'archived'].includes(program.status)} style={{minHeight: 48, padding: '12px 18px', fontSize: 15, fontWeight: 700, color: '#fff', background: '#1479a6', border: '1px solid #0d5d83', borderRadius: 8, cursor: busy ? 'wait' : 'pointer'}}>
                      {uploadingSectionId === section.id ? 'Video yükleniyor…' : 'Video seç ve yükle'}
                    </button>
                  </div>
                  <div style={{display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 8}}><label style={{fontSize: 12, color: '#496174'}}>Bölüm sektörü <select value={sectionSectorDrafts[section.id] || section.sector_code || 'common'} onChange={(event) => setSectionSectorDrafts((current) => ({...current, [section.id]: event.target.value}))}>{(sectorScope?.sectors || []).map((sector) => <option key={sector.code} value={sector.code}>{sector.label}</option>)}</select></label><button type="button" onClick={() => saveSectionSector(section)} disabled={busy || ['published', 'archived'].includes(program.status)}>Sektörü kaydet</button></div>
                  {(section.videos || []).map((video) => (
                    <div key={video.id} style={{marginTop: 8, padding: 10, borderRadius: 8, background: '#f7fafc', display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap'}}>
                      <div style={{minWidth: 240, flex: 1}}>
                        <input value={Object.prototype.hasOwnProperty.call(videoTitles, video.id) ? videoTitles[video.id] : video.title} onChange={(event) => setVideoTitles((current) => ({...current, [video.id]: event.target.value}))} aria-label={`${video.title} video başlığı`} style={{width: '100%'}} />
                        <div style={{fontSize: 12, color: '#5e7485'}}>{statusLabel(video.status)} · {video.duration_seconds ? `${video.duration_seconds} sn` : 'süre bekleniyor'} · rev. {video.revision_no}</div>
                        {video.processing_error && <div style={{fontSize: 12, color: '#b42318'}}>{video.processing_error}</div>}
                      </div>
                      <div style={{display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center'}}>
                        <button type="button" onClick={() => saveVideo(video)} disabled={busy || ['published', 'archived'].includes(program.status) || HISTORICAL_VIDEO_STATUSES.includes(video.status)}>Kaydet</button>
                        {['ready_for_review', 'published', 'unpublished'].includes(video.status) && <button type="button" onClick={() => previewVideo(video)} disabled={busy}>Önizle</button>}
                        {video.status === 'ready_for_review' && <button type="button" onClick={() => videoAction(video, 'publish')} disabled={busy}>Video yayımla</button>}
                        {video.status === 'processing_failed' && <button type="button" onClick={() => videoAction(video, 'retry-processing')} disabled={busy}>Yeniden işle</button>}
                        {!HISTORICAL_VIDEO_STATUSES.includes(video.status) && <button type="button" onClick={() => deleteVideo(video)} disabled={busy || ['published', 'archived'].includes(program.status)} style={{minHeight: 42, padding: '10px 14px', color: '#b42318', background: '#fff5f4', border: '2px solid #e39b93', borderRadius: 8, fontWeight: 700}} aria-label={`${video.title} taslak videosunu sil`}>Taslak videoyu sil</button>}
                      </div>
                    </div>
                  ))}
                </div>
              ))}
              <div style={{borderTop: '1px solid #e5edf3', marginTop: 16, paddingTop: 12}}>
                <strong>Video içi kontrol sorusu ekle</strong>
                <textarea value={checkpointDraft.question_text} onChange={(event) => setCheckpointDraft((current) => ({...current, question_text: event.target.value}))} placeholder="Kontrol sorusu" aria-label="Video içi kontrol sorusu" rows={2} style={{display: 'block', width: '100%', marginTop: 8}} />
                <div style={{display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 6, marginTop: 6}}>
                  {['A', 'B', 'C', 'D'].map((key) => <input key={key} value={checkpointDraft.options[key]} onChange={(event) => setCheckpointDraft((current) => ({...current, options: {...current.options, [key]: event.target.value}}))} placeholder={`${key} seçeneği`} aria-label={`${key} seçeneği`} />)}
                </div>
                <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginTop: 6}}>
                  <label>Doğru seçenek <select value={checkpointDraft.correct_option} onChange={(event) => setCheckpointDraft((current) => ({...current, correct_option: event.target.value}))}><option value="A">A</option><option value="B">B</option><option value="C">C</option><option value="D">D</option></select></label>
                  <label>Video <select value={checkpointDraft.video_id} onChange={(event) => setCheckpointDraft((current) => ({...current, video_id: event.target.value}))}><option value="">Genel</option>{programVideoRows(program).map((video) => <option key={video.id} value={video.id}>{video.section_title} · {video.title}</option>)}</select></label>
                  <label>Sektör <select value={checkpointDraft.sector_code} onChange={(event) => setCheckpointDraft((current) => ({...current, sector_code: event.target.value}))}>{(sectorScope?.sectors || []).map((sector) => <option key={sector.code} value={sector.code}>{sector.label}</option>)}</select></label>
                  <button type="button" onClick={createCheckpointQuestion} disabled={busy || ['published', 'archived'].includes(program.status)}>Soruyu kaydet</button>
                </div>
                {(program.checkpoint_questions || []).length > 0 && <div style={{fontSize: 12, color: '#496174', marginTop: 8}}>{program.checkpoint_questions.length} video içi kontrol sorusu tanımlı.</div>}
              </div>
              <div style={{borderTop: '1px solid #e5edf3', marginTop: 16, paddingTop: 12}}>
                <strong>Final sınavı — mevcut soru bankası</strong>
                <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8}}>
                  {questionBank.length > 0 ? <select value={examQuestionId} onChange={(event) => setExamQuestionId(event.target.value)} aria-label="Soru bankası sorusu"><option value="">Yayımlanmış soru seçin</option>{questionBank.map((question) => <option key={question.id} value={question.id}>#{question.id} · {question.question_text.slice(0, 90)}</option>)}</select> : <input type="number" min="1" value={examQuestionId} onChange={(event) => setExamQuestionId(event.target.value)} placeholder="Yayımlanmış soru ID" aria-label="Yayımlanmış soru ID" />}
                  <label>Soru sektörü <select value={examSectorCode} onChange={(event) => setExamSectorCode(event.target.value)}>{(sectorScope?.sectors || []).map((sector) => <option key={sector.code} value={sector.code}>{sector.label}</option>)}</select></label>
                  <button type="button" onClick={linkExamQuestion} disabled={busy || ['published', 'archived'].includes(program.status)}>Soruyu sınava bağla</button>
                </div>
                {(program.exam_question_links || []).length > 0 && <div style={{fontSize: 12, color: '#496174', marginTop: 8}}>{program.exam_question_links.length} mevcut soru final sınavına bağlı.</div>}
              </div>
              <div style={{borderTop: '1px solid #e5edf3', marginTop: 16, paddingTop: 12}}>
                <strong>Çalışan giriş hesabı eşleştirme</strong>
                <p style={{margin: '6px 0', color: '#5e7485', fontSize: 12}}>Önce Kullanıcılar ekranında çalışan için salt-okunur hesabı oluşturun; sonra hesabı personel kaydıyla eşleştirin.</p>
                <div style={{display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap'}}>
                  <select value={accessEmployeeId} onChange={(event) => setAccessEmployeeId(event.target.value)} aria-label="Giriş için personel seçin"><option value="">Personel seçin</option>{employees.map((row) => <option key={row.id} value={row.id}>{row.full_name}</option>)}</select>
                  <select value={accessUserId} onChange={(event) => setAccessUserId(event.target.value)} aria-label="Personel giriş hesabı seçin"><option value="">Giriş hesabı seçin</option>{employeeUsers.map((row) => <option key={row.id} value={row.id}>{row.full_name} · {row.email}</option>)}</select>
                  <button type="button" onClick={saveEmployeeAccess} disabled={busy || !accessEmployeeId || !accessUserId}>Hesabı eşleştir</button>
                </div>
                {employeeAccess.length > 0 && <div style={{fontSize: 12, color: '#496174', marginTop: 8}}>Eşleştirilmiş çalışan hesabı: {employeeAccess.length}</div>}
              </div>
              <div style={{borderTop: '1px solid #e5edf3', marginTop: 16, paddingTop: 12}}><strong>Çalışanlara ata</strong><p style={{margin: '6px 0', color: '#5e7485', fontSize: 12}}>Atama sırasında yukarıda kaydedilen sektör kapsamı çalışana sabitlenir. Çalışan yalnızca bu kapsamın videolarını ve sınav sorularını görür.</p><div style={{display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap'}}><select multiple size={5} value={selectedEmployees.map(String)} onChange={(event) => setSelectedEmployees([...event.target.selectedOptions].map((option) => Number(option.value)))} aria-label="Çalışanlar">{employees.map((row) => <option key={row.id} value={row.id}>{row.full_name}</option>)}</select><button type="button" onClick={assign} disabled={busy || !selectedEmployees.length}>Atamayı kaydet</button></div></div>
            </>
          ) : <p style={{color: '#5e7485'}}>Detay ve video yaşam döngüsünü görmek için bir taslak seçin.</p>}
        </div>
      </div>
      {report && <div style={cardStyle}><h4 style={{marginTop: 0}}>Uzaktan eğitim raporu</h4><div style={{display: 'flex', gap: 14, flexWrap: 'wrap', color: '#496174'}}><span>Atama: <strong>{report.assignment_count}</strong></span><span>Ortalama video ilerlemesi: <strong>%{report.average_video_progress_percent}</strong></span><span>Sınav denemesi: <strong>{report.exam_attempt_count}</strong></span><span>Sertifika: <strong>{report.certificate_count}</strong></span></div>{(report.rows || []).length > 0 && <div style={{overflowX: 'auto', marginTop: 10}}><table style={{width: '100%'}}><thead><tr><th>Çalışan</th><th>Durum</th><th>Kimlik snapshot</th><th>İlerleme</th></tr></thead><tbody>{report.rows.map((row) => <tr key={row.id}><td>{row.employee_name}</td><td>{statusLabel(row.status)}</td><td>{row.workplace_name_snapshot || '—'} · {row.nace_code_snapshot || 'NACE yok'} · {row.hazard_class_snapshot || 'Tehlike sınıfı yok'}</td><td>{row.summary?.completed_video_count || 0}/{row.summary?.required_video_count || 0}</td></tr>)}</tbody></table></div>}</div>}
    </section>
  );
}

export function RemoteBasicOhsTrainingPanel({user}) {
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState('');
  const canManage = MANAGE_ROLES.includes(user?.role);

  useEffect(() => {
    api('/trainings/remote/meta').then(setMeta).catch((err) => setError(err.message || 'Uzaktan eğitim modülü yüklenemedi.'));
  }, []);

  if (error) return <section style={cardStyle}><ErrorText value={error} /></section>;
  if (!meta) return <section style={cardStyle}>Uzaktan eğitim modülü yükleniyor…</section>;
  if (!meta.enabled) return <section style={cardStyle}>{REMOTE_TRAINING_DISPLAY_TITLE} pilotu henüz etkin değil.</section>;
  return <div style={{display: 'grid', gap: 16}}>{canManage && <ManagerPanel user={user} />}<EmployeePanel /></div>;
}
