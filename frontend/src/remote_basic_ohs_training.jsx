import React, {useEffect, useMemo, useRef, useState} from 'react';
import {api, API_URL, downloadFile, uploadFile} from './api';
import './remote_basic_ohs_training.css';

const MANAGE_ROLES = ['global_admin', 'company_admin', 'safety_specialist'];
const CONTENT_EDIT_ROLES = ['global_admin', 'company_admin'];
const HISTORICAL_VIDEO_STATUSES = ['published', 'unpublished', 'archived'];
const REMOTE_TRAINING_CANONICAL_TITLE = 'Basic Occupational Health and Safety Training';
const REMOTE_TRAINING_DISPLAY_TITLE = 'Temel İş Sağlığı ve Güvenliği Eğitimi';
const EMPLOYEE_TRAINING_DISPLAY_TITLE = 'Eğitimlerim';
const REMOTE_SECTOR_LABELS = {
  common: 'Temel Ortak İSG',
  construction: 'İnşaat',
  battery: 'Akü ve Otomotiv',
  foundry: 'Döküm',
  metal: 'Metal',
  logistics: 'Lojistik',
  food: 'Gıda',
  chemical: 'Kimyasal/Boya',
  mining: 'Maden/Agrega',
  road: 'Yol/Asfalt/Altyapı',
  office: 'Ofis/Genel İşyerleri',
  working_at_height: 'Yüksekte Çalışma',
};
const REMOTE_PACKAGE_LABELS = {
  'common-basic-ohs': 'Ortak Temel İSG',
  'construction-ohs': 'İnşaat',
  'metal-machine-ohs': 'Metal-Makine',
  'battery-production-ohs': 'Akü-Batarya',
  'food-production-ohs': 'Gıda',
  'logistics-warehouse-transport-ohs': 'Lojistik',
  'chemical-paint-production-ohs': 'Kimyasal/Boya',
  'open-mine-quarry-aggregate-ohs': 'Maden/Agrega',
  'road-asphalt-infrastructure-ohs': 'Yol/Asfalt/Altyapı',
  'office-general-ohs': 'Ofis/Genel İşyerleri',
  'working-at-height-ohs': 'Yüksekte Çalışma İSG Paketi',
};
const REMOTE_PACKAGE_SECTOR_CODES = {
  'common-basic-ohs': 'common',
  'construction-ohs': 'construction',
  'metal-machine-ohs': 'metal',
  'battery-production-ohs': 'battery',
  'food-production-ohs': 'food',
  'logistics-warehouse-transport-ohs': 'logistics',
  'chemical-paint-production-ohs': 'chemical',
  'open-mine-quarry-aggregate-ohs': 'mining',
  'road-asphalt-infrastructure-ohs': 'road',
  'office-general-ohs': 'office',
  'working-at-height-ohs': 'working_at_height',
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

export function canEditRemoteContent(user) {
  // OSGB yöneticisi firma seçimiyle ilişkilendirilmiş olsa bile içerik
  // yönetebilir; kapsamı backend ayrıca doğrular. Uzman yalnızca önizler.
  return CONTENT_EDIT_ROLES.includes(user?.role)
    && (user?.role === 'global_admin' || Boolean(user?.osgb_id || user?.company_id));
}

function statusLabel(value) {
  return STATUS_LABELS[value] || value || '—';
}

function localizedTrainingTitle(value) {
  return String(value || '').trim() === REMOTE_TRAINING_CANONICAL_TITLE
    ? REMOTE_TRAINING_DISPLAY_TITLE
    : value;
}

function employeeAssignmentTitle(assignment) {
  return localizedTrainingTitle(assignment?.program?.title)
    || assignment?.program?.training_type
    || 'Atanan eğitim';
}

function employeeAssignmentKind(assignment) {
  const packageCode = assignment?.program?.source_catalog_code;
  if (packageCode && REMOTE_PACKAGE_LABELS[packageCode]) return REMOTE_PACKAGE_LABELS[packageCode];
  return assignment?.program?.training_type === REMOTE_TRAINING_CANONICAL_TITLE
    ? 'Uzaktan eğitim'
    : assignment?.program?.training_type || 'Eğitim';
}

function dateKey(value) {
  const raw = String(value || '').slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : '';
}

function localDateKey(value = new Date()) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function formatEmployeeDate(value) {
  const key = dateKey(value);
  if (!key) return 'Belirlenmedi';
  const [year, month, day] = key.split('-').map(Number);
  return new Intl.DateTimeFormat('tr-TR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(new Date(year, month - 1, day));
}

export function employeeAssignmentTimeline(assignment, now = new Date()) {
  if (assignment?.status === 'completed' || assignment?.summary?.complete) {
    return {key: 'completed', label: 'Tamamlandı', tone: 'success', rank: 5};
  }
  const dueDate = dateKey(assignment?.due_date);
  const today = localDateKey(now);
  if (dueDate && dueDate < today) {
    return {key: 'overdue', label: 'Süresi geçmiş', tone: 'danger', rank: 0};
  }
  if (dueDate && dueDate === today) {
    return {key: 'due', label: 'Süresi bugün', tone: 'warning', rank: 1};
  }
  if (dueDate && dueDate > today) {
    return {key: 'upcoming', label: 'Yaklaşan', tone: 'info', rank: 3};
  }
  if (assignment?.status === 'in_progress') {
    return {key: 'in_progress', label: 'Devam ediyor', tone: 'accent', rank: 2};
  }
  return {key: 'not_started', label: 'Başlamadı', tone: 'muted', rank: 4};
}

function employeeAssignmentProgress(assignment) {
  const summary = assignment?.summary || {};
  const completed = Number(summary.completed_video_count || 0);
  const required = Number(summary.required_video_count || 0);
  const exam = summary.exam_required
    ? (summary.exam_passed ? 'Sınav başarılı' : 'Sınav bekliyor')
    : 'Sınav zorunlu değil';
  return `${completed}/${required} video · ${exam}`;
}

export function sortEmployeeAssignments(rows, now = new Date()) {
  return [...(rows || [])].sort((left, right) => {
    const leftTimeline = employeeAssignmentTimeline(left, now);
    const rightTimeline = employeeAssignmentTimeline(right, now);
    const rankDelta = leftTimeline.rank - rightTimeline.rank;
    if (rankDelta) return rankDelta;
    return String(right.assigned_at || '').localeCompare(String(left.assigned_at || ''))
      || Number(right.id || 0) - Number(left.id || 0);
  });
}

function programTitleKey(value) {
  return localizedTrainingTitle(value)
    .toLocaleLowerCase('tr-TR')
    .replace(/\s+/g, ' ')
    .trim();
}

const PROGRAM_STATUS_PRIORITY = {
  published: 5,
  ready_for_review: 4,
  draft: 3,
  unpublished: 2,
  archived: 1,
};

function compactProgramRows(rows) {
  const groups = new Map();
  for (const row of rows || []) {
    const sourceKey = row.source_catalog_package_id
      ? `catalog:${row.source_catalog_package_id}`
      : `legacy:${programTitleKey(row.title)}`;
    const group = groups.get(sourceKey) || [];
    group.push(row);
    groups.set(sourceKey, group);
  }
  return [...groups.values()].map((group) => {
    const sorted = [...group].sort((left, right) => {
      const statusDelta = (PROGRAM_STATUS_PRIORITY[right.status] || 0) - (PROGRAM_STATUS_PRIORITY[left.status] || 0);
      if (statusDelta) return statusDelta;
      const dateDelta = String(right.updated_at || right.created_at || '').localeCompare(String(left.updated_at || left.created_at || ''));
      return dateDelta || Number(right.id || 0) - Number(left.id || 0);
    });
    return {row: sorted[0], hidden: sorted.slice(1)};
  });
}

function sectorLabel(code) {
  return REMOTE_SECTOR_LABELS[code] || code || 'Sektör belirtilmemiş';
}

function packageDistributionState(packageRow, rollout) {
  // Keep older API responses usable while the additive metadata rolls out.
  if (!rollout || !Array.isArray(rollout.package_codes)) {
    return {allowed: true, label: 'Firma bazlı atama açık'};
  }
  if (rollout.force_off || !rollout.enabled) {
    return {allowed: false, label: 'Firma ataması kapalı'};
  }
  if (!rollout.package_codes.includes(packageRow?.code)) {
    return {allowed: false, label: 'Bu paket dağıtıma kapalı'};
  }
  return {allowed: true, label: rollout.company_allowlist_configured ? 'İzinli firma kontrolü' : 'Firma bazlı atama açık'};
}

function packageAutomaticExamReady(packageRow) {
  // Older API responses do not have the additive readiness field yet.
  return packageRow?.automatic_exam_ready !== false;
}

function packageAutomaticExamCount(packageRow) {
  if (!packageAutomaticExamReady(packageRow)) return 0;
  if (packageRow?.automatic_exam_question_count != null) return Number(packageRow.automatic_exam_question_count);
  return packageRow?.requires_final_exam === false ? 0 : 10;
}

function rolloutPackageLabel(code) {
  return REMOTE_PACKAGE_LABELS[code] || code || 'paket';
}

function packageSectorLabel(code) {
  return sectorLabel(REMOTE_PACKAGE_SECTOR_CODES[code] || code);
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
  return value ? <div role="alert" aria-live="assertive" style={{color: '#b42318', margin: '10px 0', fontWeight: 600}}>{value}</div> : null;
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
  const [assignmentFilter, setAssignmentFilter] = useState('all');
  const [assignment, setAssignment] = useState(null);
  const [activeVideo, setActiveVideo] = useState(null);
  const [playbackUrl, setPlaybackUrl] = useState('');
  const [exam, setExam] = useState(null);
  const [answers, setAnswers] = useState({});
  const [checkpointAnswers, setCheckpointAnswers] = useState({});
  const [checkpointResults, setCheckpointResults] = useState({});
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [videoLoading, setVideoLoading] = useState(false);
  const lastSentAt = useRef(0);
  const playbackPrefetches = useRef(new Map());
  const playbackRequestVersion = useRef(0);

  async function loadAssignments() {
    setBusy(true);
    setError('');
    try {
      const rows = await api('/trainings/remote/my-assignments');
      const next = Array.isArray(rows) ? rows : [];
      setAssignments(next);
      setSelectedId((current) => {
        if (current && next.some((row) => String(row.id) === String(current))) return current;
        return next.length ? String(next[0].id) : '';
      });
      if (!next.length) {
        setAssignment(null);
        setActiveVideo(null);
        setPlaybackUrl('');
        playbackPrefetches.current.clear();
      }
    } catch (err) {
      setError(err.message || 'Atamalar alınamadı.');
    } finally {
      setBusy(false);
    }
  }

  async function loadAssignment(id) {
    if (!id) return;
    setBusy(true);
    setError('');
    playbackRequestVersion.current += 1;
    playbackPrefetches.current.clear();
    try {
      const row = await api(`/trainings/remote/assignments/${Number(id)}`);
      setAssignment(row);
      const videos = programVideoRows(row.program);
      const nextVideo = videos.find((video) => !row.video_progress?.some((progress) => progress.video_id === video.id && progress.status === 'completed')) || videos[0] || null;
      setActiveVideo((current) => videos.find((video) => video.id === current?.id) || nextVideo);
      setPlaybackUrl('');
      setVideoLoading(false);
      setExam(null);
      setAnswers({});
      setCheckpointAnswers({});
      setCheckpointResults({});
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

  function playbackUrlFor(video, assignmentId) {
    if (!video || !assignmentId) return Promise.reject(new Error('Video oynatma bilgisi eksik.'));
    const key = `${assignmentId}:${video.id}`;
    const cached = playbackPrefetches.current.get(key);
    if (cached) return cached;
    const request = api(
      `/trainings/remote/videos/${video.id}/playback?assignment_id=${assignmentId}`,
    )
      .then((out) => apiAbsoluteUrl(out.url))
      .catch((err) => {
        playbackPrefetches.current.delete(key);
        throw err;
      });
    playbackPrefetches.current.set(key, request);
    return request;
  }

  async function openVideo(video) {
    if (!assignment || !video) return;
    if (!isVideoUnlocked(video)) {
      setError('Bu ders kilitli. Önce sıradaki önceki videoyu tamamlayın.');
      return;
    }
    setActiveVideo(video);
    setPlaybackUrl('');
    setError('');
    setVideoLoading(true);
    const requestVersion = ++playbackRequestVersion.current;
    try {
      const url = await playbackUrlFor(video, assignment.id);
      if (requestVersion === playbackRequestVersion.current) setPlaybackUrl(url);
    } catch (err) {
      if (requestVersion === playbackRequestVersion.current) setError(err.message || 'Video oynatma bağlantısı alınamadı.');
    } finally {
      if (requestVersion === playbackRequestVersion.current) setVideoLoading(false);
    }
  }

  async function saveProgress(eventType, currentTarget) {
    if (!assignment || !activeVideo || !currentTarget) return;
    const now = Date.now();
    if (eventType === 'progress' && now - lastSentAt.current < 5000) return;
    lastSentAt.current = now;
    try {
      const mediaPosition = Number(
        eventType === 'ended' && Number.isFinite(Number(currentTarget.duration))
          ? currentTarget.duration
          : currentTarget.currentTime || 0,
      );
      const out = await api(
        `/trainings/remote/assignments/${assignment.id}/videos/${activeVideo.id}/progress`,
        {
          method: 'POST',
          body: JSON.stringify({
            position_seconds: mediaPosition,
            event_type: eventType,
            device_info: navigator.userAgent.slice(0, 500),
          }),
        },
      );
      if (strictSequence && typeof out.accepted_position_seconds === 'number' && Math.abs(Number(currentTarget.currentTime || 0) - out.accepted_position_seconds) > 1.5) {
        currentTarget.currentTime = out.accepted_position_seconds;
      }
      setAssignment((current) => {
        if (!current) return current;
        const progress = [...(current.video_progress || [])];
        const index = progress.findIndex((row) => row.video_id === activeVideo.id);
        const nextProgress = {
          ...(index >= 0 ? progress[index] : {}),
          video_id: activeVideo.id,
          status: out.status,
          watched_percentage: out.watched_percentage,
          last_position_seconds: out.accepted_position_seconds ?? out.position_seconds,
        };
        if (index >= 0) progress[index] = nextProgress;
        else progress.push(nextProgress);
        return {...current, summary: out.summary, video_progress: progress};
      });
      if (out.status === 'completed') setMessage('Video tamamlanması güvenli ilerleme kaydıyla işlendi.');
      if (eventType === 'ended' && out.status === 'completed') {
        const orderedVideos = programVideoRows(assignment.program);
        const currentIndex = orderedVideos.findIndex((video) => video.id === activeVideo.id);
        const nextVideo = currentIndex >= 0 ? orderedVideos[currentIndex + 1] : null;
        if (nextVideo) {
          void playbackUrlFor(nextVideo, assignment.id).catch(() => {});
          setMessage('Video tamamlandı. Sonraki ders hazırlandı.');
        }
      }
      if (eventType === 'ended' && out.status !== 'completed') {
        setMessage('Video sonu kaydı alındı; son bölümün tamamı henüz doğrulanmadı.');
      }
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

  const videos = useMemo(() => programVideoRows(assignment?.program), [assignment]);
  const strictSequence = assignment?.program?.policy_mode === 'strict' && assignment?.program?.sequence_enforced;
  const firstIncompleteIndex = strictSequence
    ? videos.findIndex((video) => !assignment?.video_progress?.some((progress) => progress.video_id === video.id && progress.status === 'completed'))
    : -1;
  function isVideoUnlocked(video) {
    if (!strictSequence) return true;
    const index = videos.findIndex((row) => row.id === video.id);
    if (firstIncompleteIndex < 0) return true;
    const completed = assignment?.video_progress?.some((progress) => progress.video_id === video.id && progress.status === 'completed');
    return completed || index <= firstIncompleteIndex;
  }
  const currentProgress = assignment?.video_progress?.find((row) => row.video_id === activeVideo?.id);
  const checkpointQuestions = assignment?.program?.checkpoint_questions || [];
  const automaticExam = assignment?.program?.automatic_final_exam;
  const automaticExamCount = automaticExam?.automatic ? automaticExam.question_count : 0;
  const completionThresholdPercent = assignment?.program?.completion_threshold_percent || (strictSequence ? 100 : 90);
  const progressRule = strictSequence
    ? `videoları ileri sarmadan %${completionThresholdPercent} izleyin`
    : `videoları %${completionThresholdPercent} tamamlayın`;
  const orderedAssignments = useMemo(() => sortEmployeeAssignments(assignments), [assignments]);
  const visibleAssignments = useMemo(
    () => orderedAssignments.filter((row) => assignmentFilter === 'all' || employeeAssignmentTimeline(row).key === assignmentFilter),
    [assignmentFilter, orderedAssignments],
  );
  const assignmentFilterOptions = [
    {key: 'all', label: 'Tümü'},
    {key: 'upcoming', label: 'Yaklaşan'},
    {key: 'due', label: 'Süresi bugün'},
    {key: 'overdue', label: 'Süresi geçmiş'},
    {key: 'completed', label: 'Tamamlanan'},
  ];
  const assignmentCounts = useMemo(() => {
    const counts = {all: assignments.length, upcoming: 0, due: 0, overdue: 0, completed: 0};
    assignments.forEach((row) => {
      const key = employeeAssignmentTimeline(row).key;
      if (Object.prototype.hasOwnProperty.call(counts, key)) counts[key] += 1;
    });
    return counts;
  }, [assignments]);

  return (
    <section className="remote-training-card" style={cardStyle} aria-label="Çalışan uzaktan eğitim paneli">
      <div style={{display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap'}}>
        <div>
          <div style={{fontSize: 12, color: '#547187', fontWeight: 700, letterSpacing: '.03em'}}>ÇALIŞAN EĞİTİM VE SINAV SAYFASI</div>
          <h3 style={{margin: '4px 0 4px'}}>{EMPLOYEE_TRAINING_DISPLAY_TITLE}</h3>
          <p style={{margin: 0, color: '#5e7485', fontSize: 13}}>Size atanmış tüm eğitimleri, son tarihlerini, ilerlemenizi, sınavlarınızı ve tamamlanan belgelerinizi burada görürsünüz.</p>
        </div>
        <button type="button" onClick={loadAssignments} disabled={busy}>Eğitimleri yenile</button>
      </div>
      <ErrorText value={error} />
      {message && <div role="status" aria-live="polite" style={{color: '#087443', margin: '10px 0', fontWeight: 600}}>{message}</div>}
      {assignments.length > 0 && (
        <div className="remote-training-assignment-overview" aria-label="Size atanmış tüm eğitimler">
          <div className="remote-training-assignment-overview-heading">
            <div>
              <strong>Atanan tüm eğitimler</strong>
              <span>{assignments.length} eğitim</span>
            </div>
            <div className="remote-training-assignment-filters" role="group" aria-label="Eğitim durumuna göre filtrele">
              {assignmentFilterOptions.map((option) => (
                <button
                  key={option.key}
                  type="button"
                  className={assignmentFilter === option.key ? 'active' : ''}
                  aria-pressed={assignmentFilter === option.key}
                  onClick={() => setAssignmentFilter(option.key)}
                >
                  {option.label} ({assignmentCounts[option.key]})
                </button>
              ))}
            </div>
          </div>
          <div className="remote-training-assignment-list">
            {visibleAssignments.map((row) => {
              const timeline = employeeAssignmentTimeline(row);
              const selected = String(row.id) === String(selectedId);
              return (
                <button
                  key={row.id}
                  type="button"
                  className={`remote-training-assignment-item${selected ? ' selected' : ''}`}
                  aria-pressed={selected}
                  onClick={() => setSelectedId(String(row.id))}
                  disabled={busy}
                >
                  <span className="remote-training-assignment-item-main">
                    <strong>{employeeAssignmentTitle(row)}</strong>
                    <span>{employeeAssignmentKind(row)}{row.workplace_name_snapshot ? ` · ${row.workplace_name_snapshot}` : ''}</span>
                  </span>
                  <span className={`remote-training-assignment-pill ${timeline.tone}`}>{timeline.label}</span>
                  <span className="remote-training-assignment-item-meta">
                    <span>{employeeAssignmentProgress(row)}</span>
                    <span>{row.due_date ? `Son tarih: ${formatEmployeeDate(row.due_date)}` : 'Son tarih belirlenmedi'}</span>
                    <span>{row.assigned_at ? `Atanma: ${formatEmployeeDate(row.assigned_at)}` : ''}</span>
                  </span>
                </button>
              );
            })}
            {!visibleAssignments.length && <p className="remote-training-assignment-empty">Bu duruma ait atanmış eğitim bulunmuyor.</p>}
          </div>
        </div>
      )}
      {!assignments.length && !busy && <p style={{color: '#5e7485'}}>Henüz size atanmış eğitim yok. Yeni bir eğitim atandığında burada görünecek.</p>}
      {assignment && (
        <>
          <div className="remote-training-selected-assignment" style={{marginTop: 16, padding: 12, borderRadius: 10, background: '#f4f8fb'}}>
            <div className="remote-training-selected-assignment-heading">
              <div>
                <span className="remote-training-selected-label">SEÇİLİ EĞİTİM</span>
                <strong>{employeeAssignmentTitle(assignment)}</strong>
                <span>{employeeAssignmentKind(assignment)}{assignment.workplace_name_snapshot ? ` · ${assignment.workplace_name_snapshot}` : ''}</span>
              </div>
              <span className={`remote-training-assignment-pill ${employeeAssignmentTimeline(assignment).tone}`}>{employeeAssignmentTimeline(assignment).label}</span>
            </div>
            <ProgressBadge assignment={assignment} />
            <div style={{marginTop: 6, color: '#36556d', fontSize: 12}}>
              Ders kapsamı: <strong>{assignment.sector_names?.length ? assignment.sector_names.join(', ') : 'Eski kayıt — tüm yayımlanmış içerik'}</strong>
            </div>
            <div style={{marginTop: 4, color: '#36556d', fontSize: 12}}>
              Atanma tarihi: <strong>{formatEmployeeDate(assignment.assigned_at)}</strong> · Son tarih: <strong>{formatEmployeeDate(assignment.due_date)}</strong>
            </div>
            <div className="remote-training-employee-rule" role="note">
              <strong>{strictSequence ? 'Zorunlu akış:' : 'Tamamlama:'}</strong> {progressRule}
              {assignment.summary?.exam_required && <> → <strong>{automaticExamCount ? `${automaticExamCount} soruluk otomatik final sınavı` : 'final sınavı'}</strong> → geçmek için en az <strong>%{automaticExam?.passing_score || assignment.program?.passing_score || 70}</strong>.</>}
            </div>
            {assignment.snapshot_warnings?.length > 0 && <p style={{margin: '8px 0 0', color: '#9a3412', fontSize: 12}}>Belge snapshot uyarısı: {assignment.snapshot_warnings.join(' ')}</p>}
          </div>
          <div className="remote-training-content-grid" style={{gap: 16, marginTop: 16}}>
            <div>
              <div style={{fontWeight: 700, marginBottom: 8}}>Ders videoları</div>
              {videos.map((video) => {
                const progress = assignment.video_progress?.find((row) => row.video_id === video.id);
                const unlocked = isVideoUnlocked(video);
                return (
                  <button key={video.id} type="button" disabled={!unlocked || busy} onClick={() => openVideo(video)} style={{display: 'block', textAlign: 'left', width: '100%', marginBottom: 8, padding: 10, borderRadius: 9, border: `1px solid ${activeVideo?.id === video.id ? '#2474a8' : '#dbe5ef'}`, background: unlocked ? (activeVideo?.id === video.id ? '#edf7ff' : '#fff') : '#f3f4f6', color: unlocked ? '#172b4d' : '#94a3b8', cursor: unlocked ? 'pointer' : 'not-allowed', opacity: unlocked ? 1 : .75}}>
                    <strong style={{display: 'block'}}>{video.title}</strong>
                    <span style={{fontSize: 12, color: unlocked ? '#5e7485' : '#94a3b8'}}>{video.section_title} · {progress?.status === 'completed' ? 'Tamamlandı' : unlocked ? `${Math.round(progress?.watched_percentage || 0)}%` : 'Kilitli — önceki ders bekleniyor'}</span>
                  </button>
                );
              })}
              {!videos.length && <p style={{color: '#9a3412'}}>Yayımlanmış video bulunmuyor.</p>}
              {assignment.summary?.exam_required && <button type="button" onClick={loadExam} disabled={busy || (strictSequence && (!assignment.summary?.required_videos_complete || !assignment.summary?.required_checkpoints_complete))} style={{marginTop: 8}}>{automaticExamCount ? `Final sınavını aç (${automaticExamCount} soru)` : 'Final sınavını aç'}</button>}
              {strictSequence && (!assignment.summary?.required_videos_complete || !assignment.summary?.required_checkpoints_complete) && <div style={{fontSize: 12, color: '#795500', marginTop: 7}}>Final sınavı tüm zorunlu videolar ve video içi kontrol soruları tamamlanınca açılır.</div>}
            </div>
            <div>
              {activeVideo && playbackUrl ? (
                <>
                  <video
                    key={playbackUrl}
                    src={playbackUrl}
                    controls
                    controlsList="nodownload noplaybackrate"
                    disablePictureInPicture
                    playsInline
                    style={{width: '100%', maxHeight: 430, background: '#102b3d', borderRadius: 10}}
                    onPlay={(event) => saveProgress('start', event.currentTarget)}
                    onPause={(event) => saveProgress('pause', event.currentTarget)}
                    onTimeUpdate={(event) => saveProgress('progress', event.currentTarget)}
                    onEnded={(event) => saveProgress('ended', event.currentTarget)}
                    onRateChange={(event) => { if (event.currentTarget.playbackRate !== 1) event.currentTarget.playbackRate = 1; }}
                    onSeeking={(event) => {
                      if (strictSequence && currentProgress && Math.abs(event.currentTarget.currentTime - Number(currentProgress.last_position_seconds || 0)) > 3) {
                        event.currentTarget.currentTime = Number(currentProgress.last_position_seconds || 0);
                      }
                    }}
                    onLoadedMetadata={(event) => {
                      const saved = Number(currentProgress?.last_position_seconds || 0);
                      if (saved > 0 && saved < event.currentTarget.duration - 1) {
                        event.currentTarget.currentTime = saved;
                      } else if (
                        currentProgress?.status !== 'completed'
                        && saved >= event.currentTarget.duration - 8
                        && saved < event.currentTarget.duration + 2
                      ) {
                        // Recover old mobile records that reached the end but
                        // missed the final ``ended`` request. The next play
                        // emits a real ended event without replaying the file.
                        event.currentTarget.currentTime = Math.max(0, event.currentTarget.duration - 0.05);
                      }
                    }}
                  />
                  <div style={{fontSize: 12, color: '#5e7485', marginTop: 8}}>Kaldığınız yer: {Math.round(currentProgress?.last_position_seconds || 0)} sn · Eşik: {completionThresholdPercent}%</div>
                </>
              ) : <div style={{minHeight: 180, display: 'grid', placeItems: 'center', border: '1px dashed #b9cad8', borderRadius: 10, color: '#5e7485'}}>{videoLoading ? 'Video hazırlanıyor…' : 'İzlemek için bir video seçin.'}</div>}
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
              <h4 style={{margin: '0 0 4px'}}>Final sınavı — {exam.questions.length} soru</h4>
              <p style={{margin: '0 0 12px', color: '#5e7485', fontSize: 12}}>Her soruyu yanıtlayın. Geçme puanı: <strong>%{exam.passing_score || 70}</strong>. Başarılı olduğunuzda eğitim tamamlanır.</p>
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
              <h4 style={{margin: '0 0 8px'}}>Katılım belgesi</h4>
              <p style={{margin: 0, color: '#496174', fontSize: 12}}>Eğitim tamamlandı. Katılım belgesi çalışan hesabından indirilmez; iş güvenliği uzmanı yönetim ekranındaki rapordan alır ve arşivler.</p>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function CatalogManagerPanel({companyId = '', branchId = '', onCompanyChange, onBranchChange, onPrepared, rollout = null, canEditContent = false, canEditSharedContent = false}) {
  const [packages, setPackages] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [selectedPackage, setSelectedPackage] = useState(null);
  const [selectedPackageIds, setSelectedPackageIds] = useState([]);
  const [sectionCode, setSectionCode] = useState('');
  const [sectionTitle, setSectionTitle] = useState('');
  const [uploadTitles, setUploadTitles] = useState({});
  const [companies, setCompanies] = useState([]);
  const [branches, setBranches] = useState([]);
  const [busy, setBusy] = useState(false);
  const [uploadingCatalogSectionId, setUploadingCatalogSectionId] = useState(null);
  const [uploadingCatalogVideoId, setUploadingCatalogVideoId] = useState(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const uploadInputRefs = useRef({});
  const quickUploadInputRef = useRef(null);

  async function loadPackages() {
    try {
      const rows = await api('/trainings/remote/catalog/packages');
      const next = Array.isArray(rows) ? rows : [];
      setPackages(next);
      if (!selectedId && next[0]?.id) setSelectedId(String(next[0].id));
    } catch (err) {
      setError(err.message || 'Merkezi eğitim paketleri alınamadı.');
    }
  }

  async function loadCompanies() {
    try {
      const rows = await api('/companies');
      setCompanies(Array.isArray(rows) ? rows : []);
    } catch (_err) {
      setCompanies([]);
    }
  }

  async function loadBranches(cid = companyId) {
    if (!cid) {
      setBranches([]);
      return;
    }
    try {
      const rows = await api(`/branches?company_id=${Number(cid)}`);
      setBranches(Array.isArray(rows) ? rows.filter((row) => row.is_active !== false) : []);
    } catch (_err) {
      setBranches([]);
    }
  }

  async function loadPackage(id = selectedId) {
    if (!id) return;
    try {
      setSelectedPackage(await api(`/trainings/remote/catalog/packages/${Number(id)}`));
    } catch (err) {
      setError(err.message || 'Merkezi eğitim paketi alınamadı.');
    }
  }

  useEffect(() => { loadPackages(); loadCompanies(); }, []);
  useEffect(() => { loadBranches(); }, [companyId]);
  useEffect(() => { if (selectedId) loadPackage(selectedId); }, [selectedId]);

  async function refresh() {
    await loadPackages();
    await loadPackage();
  }

  async function createSection() {
    if (!canEditContent) return;
    const code = sectionCode.trim();
    const title = sectionTitle.trim();
    if (!selectedPackage || code.length < 2 || title.length < 2) {
      setError('Bölüm kodu ve bölüm adı birlikte girilmelidir.');
      return;
    }
    setBusy(true); setError(''); setMessage('');
    try {
      await api(`/trainings/remote/catalog/packages/${selectedPackage.id}/sections`, {
        method: 'POST',
        body: JSON.stringify({code, title, is_required: true}),
      });
      setSectionCode(''); setSectionTitle('');
      await loadPackage(selectedPackage.id); await loadPackages();
      setMessage('Bölüm oluşturuldu. Şimdi bu bölümün yanındaki video yükleme düğmesini kullanabilirsiniz.');
    } catch (err) { setError(err.message || 'Bölüm oluşturulamadı.'); }
    finally { setBusy(false); }
  }

  async function uploadCatalogVideo(section, file, revisionOf = null, titleOverride = '') {
    if (!canEditContent || !selectedPackage || !file) return;
    const uploadSectionId = Number(section.id);
    const uploadVideoId = revisionOf ? Number(revisionOf.id) : null;
    const defaultTitle = file.name.replace(/\.[^.]+$/, '') || 'Eğitim videosu';
    const title = (String(titleOverride || '').trim() || uploadTitles[section.id] || defaultTitle).trim();
    const fields = {
      title,
      order_index: revisionOf?.order_index || (section.videos || []).length + 1,
      is_required: true,
      ...(revisionOf ? {revision_of_id: revisionOf.id} : {}),
    };
    setBusy(true);
    setUploadingCatalogSectionId(uploadSectionId);
    setUploadingCatalogVideoId(uploadVideoId);
    setError('');
    setMessage(`"${file.name}" ${section.title} bölümüne yükleniyor. Lütfen sayfayı kapatmayın.`);
    try {
      await uploadFile(`/trainings/remote/catalog/sections/${section.id}/videos`, file, fields);
      await loadPackage(selectedPackage.id); await loadPackages();
      setMessage(revisionOf ? `${section.title} bölümünün yeni sürümü yüklendi. Kontrol edip “Video yayımla” düğmesine basın.` : `${section.title} bölümüne video eklendi. İşleme tamamlanınca durum “İncelemeye hazır” olur.`);
    } catch (err) { setError(err.message || 'Video yüklenemedi.'); }
    finally {
      setBusy(false);
      setUploadingCatalogSectionId(null);
      setUploadingCatalogVideoId(null);
    }
  }

  async function videoAction(video, action) {
    if (!canEditContent) return;
    setBusy(true); setError(''); setMessage('');
    try {
      await api(`/trainings/remote/catalog/videos/${video.id}/${action}`, {method: 'POST'});
      await loadPackage(selectedPackage.id); await loadPackages();
      setMessage(action === 'publish' ? 'Video yayımlandı.' : action === 'retry-processing' ? 'Video yeniden işleme alındı.' : 'Video durumu güncellendi.');
    } catch (err) { setError(err.message || 'Video işlemi başarısız.'); }
    finally { setBusy(false); }
  }

  async function previewCatalogVideo(video) {
    setBusy(true); setError('');
    try {
      const out = await api(`/trainings/remote/catalog/videos/${video.id}/playback`);
      const previewWindow = window.open(apiAbsoluteUrl(out.url), '_blank', 'noopener,noreferrer');
      if (!previewWindow) setMessage('Önizleme bağlantısı üretildi; tarayıcı açılır pencereyi engelledi.');
    } catch (err) { setError(err.message || 'Video önizlemesi açılamadı.'); }
    finally { setBusy(false); }
  }

  async function deleteCatalogVideo(video) {
    if (!canEditContent || !selectedPackage || HISTORICAL_VIDEO_STATUSES.includes(video.status)) return;
    if (!window.confirm(`"${video.title}" taslak videosu silinsin mi?`)) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const out = await api(`/trainings/remote/catalog/videos/${video.id}`, {method: 'DELETE'});
      await loadPackage(selectedPackage.id); await loadPackages();
      setMessage(out.storage_cleanup_pending ? 'Video silindi; depolama temizliği sıraya alındı.' : 'Taslak video silindi.');
    } catch (err) { setError(err.message || 'Video silinemedi.'); }
    finally { setBusy(false); }
  }

  async function packageAction(action) {
    if (!selectedPackage || !canEditContent) return;
    setBusy(true); setError(''); setMessage('');
    try {
      await api(`/trainings/remote/catalog/packages/${selectedPackage.id}/${action}`, {method: 'POST'});
      await loadPackage(selectedPackage.id); await loadPackages();
      if (action === 'publish') {
        const distribution = packageDistributionState(selectedPackage, rollout);
        setMessage(
          distribution.allowed
            ? 'Merkezi paket yayımlandı. Firma ve sektör seçimini yaparak atayabilirsiniz.'
            : 'Merkezi paket yayımlandı. Firma ataması için dağıtım ayarının açılması gerekir.',
        );
      } else {
        setMessage('Paket durumu güncellendi.');
      }
    } catch (err) { setError(err.message || 'Paket işlemi başarısız.'); }
    finally { setBusy(false); }
  }

  async function forkPackage() {
    if (!selectedPackage || !selectedPackage.is_shared || !canEditContent || canEditSharedContent) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const out = await api('/trainings/remote/catalog/packages/' + selectedPackage.id + '/fork', {method: 'POST'});
      if (!out?.id) throw new Error('OSGB özel kopyası oluşturuldu ancak yeni paket seçilemedi.');
      const forkedId = String(out.id);
      setSelectedId(forkedId);
      await loadPackages();
      await loadPackage(forkedId);
      setMessage('OSGB özel paketiniz oluşturuldu ve seçildi. Şimdi “Yeni ders bölümü oluştur” alanından bölüm ekleyebilirsiniz; ortak hazır paket değişmedi.');
    } catch (err) { setError(err.message || 'OSGB özel paket oluşturulamadı.'); }
    finally { setBusy(false); }
  }

  const directContentEdit = Boolean(
    canEditContent && selectedPackage && (canEditSharedContent || !selectedPackage.is_shared),
  );

  function togglePackageSelection(packageId) {
    setSelectedPackageIds((current) => current.includes(String(packageId))
      ? current.filter((id) => id !== String(packageId))
      : [...current, String(packageId)]);
  }

  async function materializeSelectedPackages() {
    const selected = packages.filter((item) => selectedPackageIds.includes(String(item.id)));
    setMessage('');
    if (!companyId) {
      setError('Önce firma seçin.');
      return;
    }
    if (!selected.length) {
      setError('En az bir eğitim paketi işaretleyin.');
      return;
    }
    const notPublished = selected.filter((item) => item.status !== 'published');
    if (notPublished.length) {
      setError(`Henüz yayımlanmamış paketler var: ${notPublished.map((item) => item.title).join(', ')}`);
      return;
    }
    const notReady = selected.filter((item) => !packageAutomaticExamReady(item));
    if (notReady.length) {
      setError(notReady.map((item) => item.automatic_exam_warning || `${item.title}: onaylı soru paketi hazır değil.`).join(' '));
      return;
    }
    const distributionBlocked = selected.filter((item) => !packageDistributionState(item, rollout).allowed);
    if (distributionBlocked.length) {
      setError(
        `Dağıtıma kapalı paketler firmaya hazırlanamaz: ${distributionBlocked.map((item) => item.title).join(', ')}. ` +
        'Firma atama ayarını açın veya yayımlanmış başka bir paket seçin.',
      );
      return;
    }
    setBusy(true); setError(''); setMessage('');
    const created = [];
    const failed = [];
    try {
      for (const item of selected) {
        try {
          await api(`/trainings/remote/catalog/packages/${item.id}/materialize`, {
            method: 'POST',
            // A package snapshot copies the published video files.  Keep this
            // mutation alive long enough for the server to commit; never retry
            // it automatically because the server already makes it idempotent.
            timeoutMs: 180_000,
            _retries: 0,
            body: JSON.stringify({company_id: Number(companyId), branch_id: branchId ? Number(branchId) : null}),
          });
          created.push(item.title);
        } catch (err) {
          failed.push(`${item.title}: ${err.message || 'atanamadı'}`);
        }
      }
      await refresh();
      onPrepared?.();
      setSelectedPackageIds([]);
      if (failed.length) {
        setError(`${created.length} paket hazırlandı. Tamamlanamayanlar: ${failed.join(' · ')}`);
      } else {
        setMessage(`${created.length} paket seçilen firma/işyerine yayımlandı; yeni bölümler ve 10 soruluk final sınavı çalışan atamasına hazır. Aşağıdaki çalışan atama bölümünden personeli seçebilirsiniz.`);
      }
    } catch (err) { setError(err.message || 'Paketler firmaya hazırlanamadı.'); }
    finally { setBusy(false); }
  }

  return (
    <section className="remote-training-card" style={cardStyle} aria-label="Merkezi uzaktan eğitim paket kataloğu">
      <div style={{display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap'}}>
        <div>
          <div style={{fontSize: 12, color: '#0b7285', fontWeight: 800, letterSpacing: '.03em'}}>MERKEZİ EĞİTİM PAKETLERİ</div>
          <h3 style={{margin: '4px 0'}}>Uzaktan Eğitim Paket Kataloğu</h3>
          <p style={{margin: 0, color: '#5e7485', fontSize: 13}}>Ortak hazır paketleri inceleyin; isterseniz OSGB özel kopyası oluşturup yalnız kendi OSGB’nize bölüm ve video ekleyin.</p>
        </div>
        <button type="button" onClick={refresh} disabled={busy}>Paketleri yenile</button>
      </div>
      <ErrorText value={error} />
      {message && <div role="status" aria-live="polite" style={{color: '#087443', margin: '10px 0', fontWeight: 600}}>{message}</div>}
      <div className="remote-training-rollout-note" role="note">
        <strong>Firma bazlı manuel atama:</strong>{' '}
        {rollout?.enabled && !rollout?.force_off
          ? `Yayımlanmış paketler arasından sektör seçimini siz yaparsınız: ${rollout.package_codes?.map(rolloutPackageLabel).join(', ') || 'dağıtıma açık paketler'}.`
          : 'İçerik hazırlama açıktır; firma ve sektör ataması için dağıtım ayarı henüz etkin değil.'}
        {rollout?.company_allowlist_configured && ' Ek olarak izinli firma listesi kontrol edilir.'}
      </div>
      <div style={{marginTop: 14, padding: 14, border: '2px solid #7c3aed', borderRadius: 10, background: '#faf5ff'}} aria-label="Firma ve sektör atama merkezi">
        <div style={{display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center'}}>
          <div>
            <strong style={{display: 'block', color: '#4c1d95', fontSize: 16}}>Firma ve sektör atama</strong>
            <span style={{display: 'block', color: '#6b21a8', fontSize: 12, marginTop: 4}}>Önce firmayı seçin, sonra o firmaya açılacak sektör eğitim paketlerini işaretleyin.</span>
          </div>
          <select value={companyId} onChange={(event) => { onCompanyChange?.(event.target.value); onBranchChange?.(''); }} disabled={busy} aria-label="Atama yapılacak firma">
            <option value="">1. Firma seçin</option>
            {companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
          </select>
        </div>
        <div style={{display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 9}}>
          <strong style={{color: '#4c1d95'}}>2. İşyeri/şube:</strong>
          <select value={branchId} onChange={(event) => onBranchChange?.(event.target.value)} disabled={busy || !companyId} aria-label="Eğitim atanacak işyeri veya şube">
            <option value="">Firma geneli / işyeri seçilmedi</option>
            {branches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
          </select>
          {companyId && !branches.length && <span style={{fontSize: 12, color: '#6b21a8'}}>Bu firmada aktif işyeri/şube kaydı yok; firma geneli kullanılacak.</span>}
        </div>
        <div style={{display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 11}}>
          <strong style={{color: '#4c1d95'}}>3. Eğitim paketlerini seçin:</strong>
          <span style={{fontSize: 12, color: '#6b21a8'}}>{selectedPackageIds.length} paket seçildi</span>
          <button type="button" onClick={() => setSelectedPackageIds(packages.filter((item) => item.status === 'published' && packageAutomaticExamReady(item) && packageDistributionState(item, rollout).allowed).map((item) => String(item.id)))} disabled={busy} style={{fontSize: 12}}>Atamaya açık yayımlanmışları seç</button>
          {selectedPackageIds.length > 0 && <button type="button" onClick={() => setSelectedPackageIds([])} disabled={busy} style={{fontSize: 12}}>Seçimi temizle</button>}
          <button type="button" onClick={materializeSelectedPackages} disabled={busy} title={!companyId ? 'Önce firma seçin' : !selectedPackageIds.length ? 'Önce atamaya açık yayımlanmış bir sektör paketi seçin' : 'Seçilen sektör paketlerini firmaya hazırlayın'} style={{marginLeft: 'auto', minHeight: 42, padding: '10px 16px', color: '#fff', background: busy ? '#a78bfa' : '#6d28d9', border: '1px solid #5b21b6', borderRadius: 8, fontWeight: 800, cursor: busy ? 'wait' : 'pointer'}}>
            {busy ? 'Hazırlanıyor…' : 'Seçilen eğitimleri hazırla'}
          </button>
        </div>
        <div style={{marginTop: 8, color: '#795500', fontSize: 12}}>Bu adım çalışanlara eğitim başlatmaz. Firma sürümü hazırlanırken <strong>10 soruluk final sınavı ve %70 geçme kuralı otomatik eklenir</strong>; çalışan ataması aşağıdaki <strong>4. Çalışanlara eğitim ve sınav ataması</strong> bölümünden yapılır.</div>
        <div role="status" aria-live="polite" style={{marginTop: 6, color: '#4c1d95', fontSize: 12, fontWeight: 700}}>
          {!companyId ? 'Atama için önce firma seçin.' : !selectedPackageIds.length ? 'Atama için yayımlanmış bir paketin kutusunu işaretleyin.' : `${selectedPackageIds.length} paket atamaya hazır.`}
        </div>
      </div>
      <div className="remote-training-manager-grid" style={{gap: 16, marginTop: 14}}>
        <div style={{border: '1px solid #dbe5ef', borderRadius: 10, padding: 12, background: '#fbfdff'}}>
          <h4 style={{margin: '0 0 6px'}}>Sektör eğitim paketleri</h4>
          <div style={{fontSize: 12, color: '#5e7485', marginBottom: 10}}>Paketi incelemek için karta, seçtiğiniz sektörü firmaya atamak için kutucuğa tıklayın. Ortak hazır paketler tüm abonelik OSGB’lerde aynıdır.</div>
          {packages.map((item) => (
            <div key={item.id} style={{display: 'flex', gap: 8, alignItems: 'flex-start', padding: 10, marginBottom: 8, borderRadius: 9, border: `1px solid ${String(item.id) === String(selectedId) ? '#0b9ca8' : '#dbe5ef'}`, background: String(item.id) === String(selectedId) ? '#e9fbfc' : '#fff'}}>
              <input type="checkbox" checked={selectedPackageIds.includes(String(item.id))} onChange={() => togglePackageSelection(item.id)} disabled={busy || item.status !== 'published' || !packageAutomaticExamReady(item) || !packageDistributionState(item, rollout).allowed} title={item.status !== 'published' ? 'Önce bu paketi yayımlayın' : !packageAutomaticExamReady(item) ? (item.automatic_exam_warning || 'Onaylı soru paketi hazır değil') : packageDistributionState(item, rollout).allowed ? 'Bu sektörü seçilen firmaya ata' : 'Firma ataması açılmadan firmaya hazırlanamaz'} aria-label={`${item.title} sektör paketini firmaya seç`} style={{marginTop: 3}} />
              <button type="button" onClick={() => setSelectedId(String(item.id))} style={{display: 'block', flex: 1, textAlign: 'left', padding: 0, border: 0, background: 'transparent', cursor: 'pointer'}}>
                <strong style={{display: 'block'}}>{item.title}</strong>
                <span style={{display: 'block', fontSize: 12, color: '#5e7485', marginTop: 3}}>{item.is_shared ? 'Ortak hazır paket' : 'OSGB özel paket'} · {statusLabel(item.status)} · {item.video_count || 0} video</span>
                <span style={{display: 'block', fontSize: 11, color: packageAutomaticExamReady(item) ? '#496174' : '#b42318', marginTop: 3}}>{item.published_video_count || 0} yayımlanmış · {item.section_count || 0} bölüm · {packageAutomaticExamReady(item) ? `${packageAutomaticExamCount(item)} otomatik soru` : 'Otomatik soru paketi eksik'}</span>
                {item.status === 'published' && <span className={packageDistributionState(item, rollout).allowed ? 'remote-training-package-ready' : 'remote-training-package-locked'}>{packageDistributionState(item, rollout).label}</span>}
              </button>
            </div>
          ))}
          {!packages.length && <p style={{color: '#5e7485'}}>Paket kataloğu hazırlanıyor…</p>}
        </div>
        <div style={{border: '1px solid #dbe5ef', borderRadius: 10, padding: 14, background: '#fff'}}>
          {selectedPackage ? (
            <>
              <div style={{display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap'}}>
                <div><h4 style={{margin: 0}}>{selectedPackage.title}</h4><div style={{fontSize: 12, color: '#5e7485', marginTop: 4}}>Sektör: {packageSectorLabel(selectedPackage.code)} · {statusLabel(selectedPackage.status)} · {selectedPackage.video_count || 0} video · {selectedPackage.section_count || 0} bölüm</div>{packageAutomaticExamReady(selectedPackage) ? <div className="remote-training-exam-auto-note">Otomatik final sınavı: <strong>{packageAutomaticExamCount(selectedPackage)} soru</strong> · geçme puanı <strong>%{selectedPackage.automatic_exam_passing_score || 70}</strong></div> : <div className="remote-training-exam-validation-warning">{selectedPackage.automatic_exam_warning || 'Otomatik final soru paketi hazır değil.'}</div>}{selectedPackage.status === 'published' && <div className={packageDistributionState(selectedPackage, rollout).allowed ? 'remote-training-package-ready' : 'remote-training-package-locked'}>{packageDistributionState(selectedPackage, rollout).label}</div>}</div>
                <div style={{display: 'flex', gap: 6, flexWrap: 'wrap'}}>
                  {selectedPackage.is_shared && canEditContent && !canEditSharedContent && selectedPackage.status !== 'archived' && <button type="button" onClick={forkPackage} disabled={busy} aria-label="Bölüm eklemeye başla; OSGB özel kopyası oluştur" title="Ortak pakete dokunulmaz; yalnız sizin OSGB’nize özel kopya oluşturulur ve bölüm ekleme alanı açılır." style={{color: '#fff', background: busy ? '#7aa6a3' : '#0f766e', borderColor: '#0f766e', fontWeight: 800}}>{busy ? 'Özel kopya hazırlanıyor…' : 'Bölüm eklemeye başla'}</button>}
                  {directContentEdit && ['draft', 'unpublished'].includes(selectedPackage.status) && <button type="button" onClick={() => packageAction('ready-for-review')} disabled={busy}>İncelemeye hazır</button>}
                  {directContentEdit && ['ready_for_review', 'unpublished'].includes(selectedPackage.status) && <button type="button" onClick={() => packageAction('publish')} disabled={busy}>Paketi yayımla</button>}
                  {directContentEdit && selectedPackage.status === 'published' && <button type="button" onClick={() => packageAction('unpublish')} disabled={busy}>Yayından kaldır</button>}
                  {directContentEdit && !['archived'].includes(selectedPackage.status) && <button type="button" onClick={() => packageAction('archive')} disabled={busy}>Arşivle</button>}
                  {directContentEdit && selectedPackage.status === 'archived' && <button type="button" onClick={() => packageAction('restore')} disabled={busy}>Paketi düzenlemeye aç</button>}
                </div>
              </div>
              <div style={{marginTop: 12, padding: 11, borderRadius: 8, background: '#f2f9fc', color: '#36556d', fontSize: 12}}><strong>İş akışı:</strong> Bölüm → Video seç ve yükle → İşleme/inceleme → Video yayımla → Firma/işyeri seçip eğitim kutucuğunu işaretle. {packageAutomaticExamReady(selectedPackage) ? `Yayınlanan programa ${packageAutomaticExamCount(selectedPackage)} onaylı final sorusu ve %${selectedPackage.automatic_exam_passing_score || 70} geçme kuralı otomatik eklenir.` : 'Onaylı soru paketi hazır olmadığı için bu paket firma programına hazırlanamaz.'}</div>
              {selectedPackage.is_shared && <div style={{marginTop: 12, padding: 11, borderRadius: 8, background: '#fff8e8', color: '#795500', fontSize: 12}}>
                {canEditContent && !canEditSharedContent
                  ? selectedPackage.status === 'published'
                    ? <><strong>OSGB olarak bölüm eklemek için:</strong> Önce yukarıdaki <strong>“Bölüm eklemeye başla”</strong> düğmesine basın. Sistem yalnız sizin OSGB’nize ait özel bir kopya oluşturur; ardından bu alanda <strong>“Yeni ders bölümü oluştur”</strong> formu açılır. Ortak paket ve diğer OSGB’ler etkilenmez.</>
                    : <><strong>OSGB özel hazırlığı:</strong> Bu ortak paket henüz yayımlanmamış. <strong>“Bölüm eklemeye başla”</strong> düğmesi sizin OSGB’nize özel bir taslak kopya oluşturur; ardından bölüm ve videoları ekleyip kendi paketinizi yayıma hazırlayabilirsiniz. Ortak paket ve diğer OSGB’ler etkilenmez.</>
                  : <><strong>Ortak hazır paket:</strong> Bu paket tüm aktif EİSA aboneliği olan OSGB’lerde aynıdır. Uzmanlar içeriği değiştiremez; OSGB yöneticisi kendi kopyasını oluşturup yalnız kendi OSGB’sinde düzenleyebilir.</>}
              </div>}
              <div style={{marginTop: 12, padding: 11, borderRadius: 8, background: '#effcfc', color: '#36556d', fontSize: 12}}><strong>Video yükleme:</strong> Her ders bölümünün altındaki tek <strong>Video seç ve yükle</strong> düğmesini kullanın. Yayımlanmış paketlere de yeni video/bölüm ekleyebilirsiniz; mevcut yayımlanmış videoyu değiştirmek için satırdaki <strong>Yeni sürüm yükle</strong> düğmesini kullanın.</div>
              {directContentEdit && <>
{selectedPackage.status === 'archived'
                ? <div style={{marginTop: 14, padding: 12, border: '1px solid #f2c46d', borderRadius: 9, background: '#fff8e8'}}>
                    <strong style={{display: 'block', color: '#795500'}}>Bu paket arşivlenmiş</strong>
                    <span style={{display: 'block', color: '#795500', fontSize: 12, marginTop: 4}}>Yeni bölüm veya video eklemek için paketi düzenlemeye açın. Mevcut firma sürümleri, çalışan atamaları ve ilerleme kayıtları değişmez.</span>
                    <button type="button" onClick={() => packageAction('restore')} disabled={busy} style={{marginTop: 9}}>Paketi düzenlemeye aç</button>
                  </div>
                : <div style={{marginTop: 14, padding: 12, border: '1px solid #dbe5ef', borderRadius: 9, background: '#fbfdff'}}>
                    <strong>Yeni ders bölümü oluştur</strong>
                    <span style={{display: 'block', color: '#5e7485', fontSize: 12, marginTop: 4}}>Örneğin YÜK-11 — Dikey ve yatay yaşam hatları. Bölümü bir kez oluşturduktan sonra hemen altındaki video düğmesinden yükleyebilirsiniz.</span>
                    <div style={{display: 'flex', gap: 7, flexWrap: 'wrap', marginTop: 8}}><input value={sectionCode} onChange={(event) => setSectionCode(event.target.value)} placeholder="Bölüm kodu: YÜK-11" aria-label="Yeni bölüm kodu" style={{maxWidth: 170}} /><input value={sectionTitle} onChange={(event) => setSectionTitle(event.target.value)} placeholder="Bölüm adı" aria-label="Yeni bölüm adı" style={{minWidth: 220, flex: 1}} /><button type="button" onClick={createSection} disabled={busy}>Bölümü oluştur</button></div>
                  </div>}
</>}
              {(selectedPackage.sections || []).map((section) => (
                <div key={section.id} style={{borderTop: '1px solid #e5edf3', paddingTop: 12, marginTop: 12}}>
                  <div style={{display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap'}}><div><strong>{section.code} · {section.title}</strong><span style={{display: 'block', fontSize: 12, color: '#5e7485', marginTop: 3}}>{section.videos?.length || 0} video · {section.status === 'active' ? 'Aktif' : 'Arşivlendi'}</span></div></div>
                  {directContentEdit && selectedPackage.status !== 'archived' && section.status === 'active' && <div style={{marginTop: 9, padding: 10, border: '2px dashed #54a8c5', borderRadius: 9, background: '#f7fcff'}}>
                    <div style={{display: 'flex', gap: 7, flexWrap: 'wrap', alignItems: 'center'}}><input value={uploadTitles[section.id] || ''} onChange={(event) => setUploadTitles((current) => ({...current, [section.id]: event.target.value}))} placeholder="Video adı (boş bırakılırsa dosya adı)" aria-label={`${section.title} video adı`} style={{minWidth: 240, flex: 1}} /><input ref={(node) => {uploadInputRefs.current[section.id] = node;}} id={`remote-catalog-video-upload-${section.id}`} type="file" accept="video/mp4,video/webm,video/quicktime,.m4v" aria-label={`${section.title} video dosyası`} style={{position: 'absolute', width: 1, height: 1, padding: 0, margin: -1, overflow: 'hidden', clip: 'rect(0, 0, 0, 0)', whiteSpace: 'nowrap', border: 0}} onChange={(event) => {const file = event.target.files?.[0]; event.target.value = ''; if (file) uploadCatalogVideo(section, file);}} /><label htmlFor={`remote-catalog-video-upload-${section.id}`} aria-disabled={busy} onClick={(event) => {if (busy) event.preventDefault();}} style={{minHeight: 42, padding: '10px 14px', color: '#fff', background: busy ? '#7faec2' : '#1479a6', border: '1px solid #0d5d83', borderRadius: 8, fontWeight: 700, display: 'inline-flex', alignItems: 'center', cursor: busy ? 'wait' : 'pointer'}}>{uploadingCatalogSectionId === Number(section.id) && !uploadingCatalogVideoId ? 'Bu bölüm yükleniyor…' : 'Video seç ve yükle'}</label></div>
                  </div>}
                  {(section.videos || []).map((video) => <div key={video.id} style={{marginTop: 8, padding: 10, borderRadius: 8, background: '#f7fafc', display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap'}}>
                    <div style={{minWidth: 240, flex: 1}}><strong>{video.title}</strong><div style={{fontSize: 12, color: '#5e7485', marginTop: 3}}>{statusLabel(video.status)} · {video.duration_seconds ? `${video.duration_seconds} sn` : 'süre bekleniyor'} · rev. {video.revision_no}</div>{video.processing_error && <div style={{fontSize: 12, color: '#b42318', marginTop: 3}}>{video.processing_error}</div>}</div>
                    <div style={{display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center'}}>
                      {directContentEdit && video.status === 'published' && video.is_current && selectedPackage.status !== 'archived' && <><input ref={(node) => {uploadInputRefs.current[`revision-${video.id}`] = node;}} id={`remote-catalog-video-revision-${video.id}`} type="file" accept="video/mp4,video/webm,video/quicktime,.m4v" aria-label={`${video.title} yeni sürüm dosyası`} style={{position: 'absolute', width: 1, height: 1, padding: 0, margin: -1, overflow: 'hidden', clip: 'rect(0, 0, 0, 0)', whiteSpace: 'nowrap', border: 0}} onChange={(event) => {const file = event.target.files?.[0]; event.target.value = ''; if (file) uploadCatalogVideo(section, file, video);}} /><label htmlFor={`remote-catalog-video-revision-${video.id}`} aria-disabled={busy} onClick={(event) => {if (busy) event.preventDefault();}} style={{display: 'inline-flex', alignItems: 'center', minHeight: 42, padding: '10px 14px', color: '#075985', background: busy ? '#d7edf8' : '#e8f6ff', border: '2px solid #72b9d7', borderRadius: 8, fontWeight: 700, cursor: busy ? 'wait' : 'pointer'}}>{uploadingCatalogVideoId === Number(video.id) ? 'Yeni sürüm yükleniyor…' : 'Yeni sürüm yükle'}</label></>}
                      {directContentEdit && video.status === 'ready_for_review' && <button type="button" onClick={() => videoAction(video, 'publish')} disabled={busy}>Video yayımla</button>}
                      {['ready_for_review', 'published', 'unpublished'].includes(video.status) && <button type="button" onClick={() => previewCatalogVideo(video)} disabled={busy}>Önizle</button>}
                      {directContentEdit && video.status === 'published' && <button type="button" onClick={() => videoAction(video, 'unpublish')} disabled={busy}>Yayından kaldır</button>}
                      {directContentEdit && ['published', 'unpublished'].includes(video.status) && <button type="button" onClick={() => videoAction(video, 'archive')} disabled={busy}>Arşivle</button>}
                      {directContentEdit && video.status === 'processing_failed' && <button type="button" onClick={() => videoAction(video, 'retry-processing')} disabled={busy}>Yeniden işle</button>}
                      {directContentEdit && !HISTORICAL_VIDEO_STATUSES.includes(video.status) && <button type="button" onClick={() => deleteCatalogVideo(video)} disabled={busy} style={{color: '#b42318', background: '#fff5f4', border: '1px solid #e39b93'}}>Taslak videoyu sil</button>}
                    </div>
                  </div>)}
                </div>
              ))}
              {!selectedPackage.sections?.length && <p style={{marginTop: 14, color: '#5e7485'}}>Bu pakette henüz bölüm yok. Yukarıdaki alandan ilk bölümü ekleyin.</p>}
            </>
          ) : <p style={{color: '#5e7485'}}>Soldan bir eğitim paketi seçin.</p>}
        </div>
      </div>
    </section>
  );
}

function ManagerPanel({user, initialCompanyId = '', initialBranchId = '', onCompanyChange, onBranchChange, refreshToken = 0, canEditContent = false}) {
  const [companies, setCompanies] = useState([]);
  const [branches, setBranches] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [companyId, setCompanyId] = useState('');
  const [branchId, setBranchId] = useState('');
  const [programs, setPrograms] = useState([]);
  const [program, setProgram] = useState(null);
  const [automaticExamQuestions, setAutomaticExamQuestions] = useState([]);
  const [savingAutomaticQuestionId, setSavingAutomaticQuestionId] = useState(null);
  const [automaticQuestionSaveStates, setAutomaticQuestionSaveStates] = useState({});
  const [sectionTitle, setSectionTitle] = useState('');
  const [selectedEmployees, setSelectedEmployees] = useState([]);
  const [assignmentDueDate, setAssignmentDueDate] = useState('');
  const [employeeUsers, setEmployeeUsers] = useState([]);
  const [employeeAccess, setEmployeeAccess] = useState([]);
  const [accessEmployeeId, setAccessEmployeeId] = useState('');
  const [accessUserId, setAccessUserId] = useState('');
  const [provisionEmployeeId, setProvisionEmployeeId] = useState('');
  const [provisionEmail, setProvisionEmail] = useState('');
  const [provisionedCredentials, setProvisionedCredentials] = useState(null);
  const [busy, setBusy] = useState(false);
  const [uploadingSectionId, setUploadingSectionId] = useState(null);
  const [uploadingVideoId, setUploadingVideoId] = useState(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [assignmentNotice, setAssignmentNotice] = useState(null);
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
  const [showOldPrograms, setShowOldPrograms] = useState(false);
  const uploadInputRefs = useRef({});

  const compactPrograms = useMemo(() => compactProgramRows(programs), [programs]);
  const duplicateProgramCount = useMemo(
    () => compactPrograms.reduce((total, item) => total + item.hidden.length, 0),
    [compactPrograms],
  );
  const scopeSectorOptions = sectorScope?.catalog_fixed && sectorScope.catalog_sector_code
    ? sectorScope.sectors.filter((sector) => sector.code === sectorScope.catalog_sector_code)
    : (sectorScope?.sectors || []);
  const catalogSectorCode = sectorScope?.catalog_fixed && sectorScope.catalog_sector_code
    ? sectorScope.catalog_sector_code
    : '';
  const catalogSectorName = catalogSectorCode ? sectorLabel(catalogSectorCode) : '';
  const catalogProgramHasSections = (program?.sections || []).length > 0;
  const programAssignmentCount = Number(program?.assignment_count || 0);
  const programContentLocked = program?.status === 'published' && programAssignmentCount > 0;
  const visibleProgramSections = useMemo(() => {
    const sections = program?.sections || [];
    if (!catalogSectorCode) return sections;
    return sections.filter((section) => !section.sector_code || section.sector_code === catalogSectorCode);
  }, [program, catalogSectorCode]);
  const sectionCreateHint = catalogSectorCode === 'working_at_height'
    ? 'Yüksekte Çalışma paketi seçili. Örnek: “YÜK-11 · Dikey ve yatay yaşam hatları”.'
    : catalogSectorCode
      ? `Yalnızca ${catalogSectorName} paketiyle ilgili yeni bir bölüm ekleyin.`
      : 'Yeni bölüm adını yazın ve ilgili eğitim kapsamını seçin.';
  const visibleEmployees = useMemo(
    () => branchId
      ? employees.filter((row) => String(row.branch_id || '') === String(branchId))
      : employees,
    [branchId, employees],
  );

  async function loadCompanies() {
    const rows = await api('/companies');
    const next = Array.isArray(rows) ? rows : [];
    setCompanies(next);
    const defaultId = next.find((row) => String(row.id) === String(initialCompanyId))?.id
      || next.find((row) => String(row.id) === String(user?.company_id))?.id
      || next[0]?.id;
    if (defaultId && !companyId) setCompanyId(String(defaultId));
  }

  async function loadPrograms(cid = companyId) {
    if (!cid) return;
    const rows = await api(`/trainings/remote/programs?company_id=${Number(cid)}`);
    setPrograms(Array.isArray(rows) ? rows : []);
  }

  async function loadBranches(cid = companyId) {
    if (!cid) {
      setBranches([]);
      return;
    }
    try {
      const rows = await api(`/branches?company_id=${Number(cid)}`);
      setBranches(Array.isArray(rows) ? rows.filter((row) => row.is_active !== false) : []);
    } catch (_err) {
      setBranches([]);
    }
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
    setSectionTitle('');
    setAssignmentNotice(null);
    setAutomaticExamQuestions(row.automatic_final_exam?.questions || []);
    setAutomaticQuestionSaveStates({});
    setBranchId(row.branch_id ? String(row.branch_id) : '');
    onBranchChange?.(row.branch_id ? String(row.branch_id) : '');
    const scope = await api(`/trainings/remote/programs/${Number(id)}/sectors`);
    setSectorScope(scope);
    const selectedCodes = scope.catalog_fixed && scope.catalog_sector_code
      ? [scope.catalog_sector_code]
      : (scope.mode === 'scoped' ? (scope.selected_sector_codes || []) : ['common']);
    const defaultSector = selectedCodes[0] || 'common';
    setSelectedSectorCodes(selectedCodes);
    setSectionSectorCode(defaultSector);
    setExamSectorCode(defaultSector);
    setCheckpointDraft((current) => ({...current, sector_code: defaultSector}));
    await loadEmployees(row.company_id);
    await loadEmployeeAccess(row.company_id);
    await loadQuestionBank();
  }

  function updateAutomaticExamQuestion(questionId, field, value) {
    setAutomaticQuestionSaveStates((current) => ({...current, [questionId]: null}));
    setAutomaticExamQuestions((current) => current.map((question) => (
      question.id === questionId ? {...question, [field]: value} : question
    )));
  }

  function updateAutomaticExamOption(questionId, option, value) {
    setAutomaticQuestionSaveStates((current) => ({...current, [questionId]: null}));
    setAutomaticExamQuestions((current) => current.map((question) => (
      question.id === questionId
        ? {...question, options: {...question.options, [option]: value}}
        : question
    )));
  }

  async function saveAutomaticExamQuestion(question) {
    if (!program || !question) return;
    const rejectQuestionSave = (text) => {
      setAutomaticQuestionSaveStates((current) => ({...current, [question.id]: 'error'}));
      setError(text);
    };
    const text = String(question.question_text || '').trim();
    const options = Object.fromEntries(['A', 'B', 'C', 'D'].map((key) => [
      key,
      String(question.options?.[key] || '').trim(),
    ]));
    if (text.length < 3 || Object.values(options).some((value) => !value)) {
      rejectQuestionSave('Final sorusunda metin ile A, B, C ve D seçenekleri boş bırakılamaz.');
      return;
    }
    if (new Set(Object.values(options).map((value) => value.toLocaleLowerCase('tr-TR'))).size !== 4) {
      rejectQuestionSave('Final sorusunun A, B, C ve D seçenekleri birbirinden farklı olmalıdır.');
      return;
    }
    setBusy(true); setSavingAutomaticQuestionId(question.id); setError(''); setMessage('');
    setAutomaticQuestionSaveStates((current) => ({...current, [question.id]: 'saving'}));
    try {
      await api(`/trainings/remote/programs/${program.id}/final-exam-questions/${question.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          question_text: text,
          options,
          correct_option: question.correct_option,
          explanation: question.explanation || null,
        }),
      });
      setMessage(`${question.order_index}. final sorusu kaydedildi. Yayınlamadan önce 10 sorunun tamamını kontrol edin.`);
      try {
        await loadDetail(program.id);
      } catch (refreshError) {
        setError(`Soru kaydedildi ancak liste yenilenemedi: ${refreshError.message || 'sayfayı yenileyin.'}`);
      }
      setAutomaticQuestionSaveStates((current) => ({...current, [question.id]: 'saved'}));
    } catch (err) {
      setAutomaticQuestionSaveStates((current) => ({...current, [question.id]: 'error'}));
      setError(err.message || 'Final sorusu kaydedilemedi.');
    }
    finally { setBusy(false); setSavingAutomaticQuestionId(null); }
  }

  useEffect(() => {
    loadCompanies().catch((err) => setError(err.message || 'Firma listesi alınamadı.'));
  }, []);

  useEffect(() => {
    if (!companyId) return;
    loadBranches(companyId);
    loadPrograms(companyId).catch((err) => setError(err.message || 'Eğitim listesi alınamadı.'));
    loadEmployees(companyId).catch((err) => setError(err.message || 'Çalışan listesi alınamadı.'));
    loadEmployeeAccess(companyId);
  }, [companyId]);

  useEffect(() => {
    if (!companyId || !refreshToken) return;
    loadPrograms(companyId).catch((err) => setError(err.message || 'Yeni hazırlanan eğitim listesi alınamadı.'));
  }, [refreshToken]);

  useEffect(() => {
    if (initialBranchId && branches.some((row) => String(row.id) === String(initialBranchId))) {
      setBranchId(String(initialBranchId));
    }
  }, [initialBranchId, branches]);

  useEffect(() => {
    if (!initialCompanyId || !companies.some((row) => String(row.id) === String(initialCompanyId))) return;
    setCompanyId(String(initialCompanyId));
  }, [initialCompanyId, companies]);

  async function createSection() {
    if (!program) return;
    if (programContentLocked) {
      setError('Bu yayımlanmış firma sürümüne çalışan ataması yapıldığı için yeni bölüm eklenemez. Yeni bölümü merkezi katalogdaki pakete ekleyin.');
      return;
    }
    const title = sectionTitle.trim();
    if (title.length < 2) {
      setError('Yeni bölüm için ilgili bölüm adını yazın.');
      return;
    }
    setBusy(true); setError('');
    try {
      await api(`/trainings/remote/programs/${program.id}/sections`, {method: 'POST', body: JSON.stringify({title, sector_code: sectionSectorCode})});
      await loadDetail(program.id); setMessage('Bölüm eklendi.');
    } catch (err) { setError(err.message || 'Bölüm eklenemedi.'); } finally { setBusy(false); }
  }

  async function saveSectorScope() {
    if (!program) return;
    setBusy(true); setError('');
    try {
      const sectorCodes = sectorScope?.catalog_fixed && sectorScope.catalog_sector_code
        ? [sectorScope.catalog_sector_code]
        : selectedSectorCodes;
      const out = await api(`/trainings/remote/programs/${program.id}/sectors`, {method: 'PUT', body: JSON.stringify({sector_codes: sectorCodes})});
      setSectorScope(out);
      setSelectedSectorCodes(out.selected_sector_codes || []);
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

  async function uploadVideo(section, file, revisionOf = null) {
    if (!file || !program) return;
    if (!revisionOf && programContentLocked) {
      setError('Bu yayımlanmış firma sürümüne çalışan ataması yapıldığı için yeni video eklenemez. Yeni videoyu merkezi katalogdaki ilgili bölüme ekleyin.');
      return;
    }
    const revisionFields = revisionOf ? {revision_of_id: revisionOf.id} : {};
    setBusy(true); setUploadingSectionId(section.id); setUploadingVideoId(revisionOf?.id || null); setError(''); setMessage(revisionOf ? `"${file.name}" yeni sürüm olarak yükleniyor. Eski video şimdilik çalışanlara açık.` : `"${file.name}" yükleniyor. Lütfen bu sayfayı kapatmayın.`);
    try {
      await uploadFile(`/trainings/remote/sections/${section.id}/videos`, file, {title: file.name.replace(/\.[^.]+$/, '') || 'Temel İSG video dersi', order_index: revisionOf?.order_index || ((section.videos || []).length + 1), ...revisionFields});
      await loadDetail(program.id); setMessage(revisionOf ? 'Yeni video sürümü yüklendi. Kontrol et; doğruysa yeni sürümün yanındaki Video yayımla düğmesine bas.' : 'Video yüklendi; durum işleniyor veya incelemeye hazır olabilir.');
    } catch (err) { setError(err.message || 'Video yüklenemedi.'); } finally { setBusy(false); setUploadingSectionId(null); setUploadingVideoId(null); }
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
    setBusy(true); setError(''); setMessage('');
    try {
      await api(`/trainings/remote/programs/${program.id}/${action}`, {method: 'POST'});
      await loadDetail(program.id); await loadPrograms(program.company_id);
      setMessage(action === 'publish' ? 'Eğitim yayımlandı ve çalışan atamasına açıldı.' : action === 'ready-for-review' ? 'Eğitim incelemeye hazır olarak işaretlendi.' : 'Eğitim durumu güncellendi.');
    } catch (err) { setError(err.message || 'Eğitim işlemi başarısız.'); } finally { setBusy(false); }
  }

  async function assign() {
    if (!program || !selectedEmployees.length) {
      const text = 'En az bir çalışan seçin.';
      setAssignmentNotice({kind: 'error', text});
      setError(text);
      return;
    }
    setBusy(true); setError(''); setAssignmentNotice(null);
    try {
      const out = await api(`/trainings/remote/programs/${program.id}/assign`, {method: 'POST', body: JSON.stringify({employee_ids: selectedEmployees.map(Number), branch_id: branchId ? Number(branchId) : null, due_date: assignmentDueDate || null})});
      const createdCount = Number(out.created_count) || 0;
      const skippedCount = Array.isArray(out.skipped_employee_ids) ? out.skipped_employee_ids.length : 0;
      const text = createdCount === 0 && skippedCount > 0
        ? `Seçilen ${skippedCount} çalışanın mevcut ataması zaten vardı; yeni kayıt oluşturulmadı.`
        : `${createdCount} çalışana eğitim ve sınav atandı${skippedCount ? `; ${skippedCount} mevcut atama korundu` : ''}.`;
      setAssignmentNotice({kind: 'success', text});
      setMessage(text);
      setSelectedEmployees([]);
      setAssignmentDueDate('');
    } catch (err) {
      const text = err.message || 'Çalışan ataması yapılamadı.';
      setAssignmentNotice({kind: 'error', text});
      setError(text);
    } finally { setBusy(false); }
  }

  function toggleEmployee(employeeId) {
    const id = Number(employeeId);
    setAssignmentNotice(null);
    setSelectedEmployees((current) => current.includes(id)
      ? current.filter((item) => item !== id)
      : [...current, id]);
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

  async function provisionEmployeeAccount() {
    if (!companyId || !provisionEmployeeId || !provisionEmail.trim()) return setError('Çalışan ve e-posta birlikte girilmelidir.');
    setBusy(true); setError(''); setMessage(''); setProvisionedCredentials(null);
    try {
      const out = await api('/trainings/remote/employee-access/provision', {
        method: 'POST',
        body: JSON.stringify({company_id: Number(companyId), employee_id: Number(provisionEmployeeId), email: provisionEmail.trim()}),
      });
      setProvisionedCredentials(out);
      setProvisionEmployeeId('');
      setProvisionEmail('');
      await loadEmployeeAccess(companyId);
      setMessage('Çalışan hesabı oluşturuldu ve personel kaydıyla eşleştirildi.');
    } catch (err) { setError(err.message || 'Çalışan hesabı oluşturulamadı.'); }
    finally { setBusy(false); }
  }

  async function createCheckpointQuestion() {
    if (!program) return;
    const text = checkpointDraft.question_text.trim();
    const options = Object.fromEntries(Object.entries(checkpointDraft.options).map(([key, value]) => [key, value.trim()]));
    if (text.length < 3 || Object.values(options).some((value) => value.length < 1)) return setError('Video içi soru ve dört seçenek birlikte doldurulmalıdır.');
    setBusy(true); setError('');
    try {
      await api(`/trainings/remote/programs/${program.id}/checkpoint-questions`, {method: 'POST', body: JSON.stringify({question_text: text, options, correct_option: checkpointDraft.correct_option, sector_code: checkpointDraft.sector_code, video_id: checkpointDraft.video_id ? Number(checkpointDraft.video_id) : null, order_index: (program.checkpoint_questions || []).length + 1, is_required: true})});
      setCheckpointDraft({question_text: '', options: {A: '', B: '', C: '', D: ''}, correct_option: 'A', video_id: '', sector_code: sectorScope?.catalog_fixed ? sectorScope.catalog_sector_code : (selectedSectorCodes[0] || 'common')});
      await loadDetail(program.id);
      setMessage('Video içi kontrol sorusu eklendi.');
    } catch (err) { setError(err.message || 'Video içi soru eklenemedi.'); } finally { setBusy(false); }
  }

  async function linkExamQuestion() {
    if (!program || !examQuestionId) return setError('Bağlanacak yayımlanmış soru ID değerini seçin.');
    const position = Math.max(0, ...(program.exam_question_links || []).map((link) => Number(link.position) || 0)) + 1;
    setBusy(true); setError('');
    try {
      await api(`/trainings/remote/programs/${program.id}/exam/questions`, {method: 'POST', body: JSON.stringify({question_id: Number(examQuestionId), position, sector_code: examSectorCode})});
      setExamQuestionId('');
      await loadDetail(program.id);
      setMessage('Mevcut soru bankası sorusu final sınavına bağlandı.');
    } catch (err) { setError(err.message || 'Soru bankası sorusu bağlanamadı.'); } finally { setBusy(false); }
  }

  async function unlinkExamQuestion(link) {
    if (!program || !link) return;
    const confirmed = window.confirm(`Soru #${link.question_id} final sınavından çıkarılsın mı?`);
    if (!confirmed) return;
    setBusy(true); setError(''); setMessage('');
    try {
      await api(`/trainings/remote/programs/${program.id}/exam/questions/${link.id}`, {method: 'DELETE'});
      await loadDetail(program.id);
      setMessage('Soru final sınavından çıkarıldı.');
    } catch (err) { setError(err.message || 'Soru sınavdan çıkarılamadı.'); } finally { setBusy(false); }
  }

  async function showReport() {
    if (!program) return;
    setBusy(true); setError('');
    try {
      const nextReport = await api(`/trainings/remote/programs/${program.id}/report`);
      setReport(nextReport);
      window.setTimeout(() => document.getElementById('remote-training-report')?.scrollIntoView({behavior: 'smooth', block: 'start'}), 60);
    } catch (err) { setError(err.message || 'Rapor alınamadı.'); } finally { setBusy(false); }
  }

  async function downloadParticipationDocument(row) {
    if (!row?.id || row.status !== 'completed') return;
    setBusy(true); setError(''); setMessage('');
    try {
      await downloadFile(`/trainings/remote/assignments/${row.id}/certificate.pdf`, `uzaktan-egitim-belgesi-${row.id}.pdf`);
      setMessage(`${row.employee_name || 'Çalışan'} için uzaktan eğitim belgesi alındı. PDF'yi arşivleyebilirsiniz.`);
    } catch (err) {
      setError(err.message || 'Uzaktan eğitim belgesi alınamadı.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section style={{display: 'grid', gap: 16}} aria-label="Firma çalışanlarının eğitim ve sınav ataması yönetimi">
      <div style={cardStyle}>
        <div style={{display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap'}}>
          <div><div style={{fontSize: 12, color: '#547187', fontWeight: 700}}>FİRMA EĞİTİM VE SINAV YÖNETİMİ</div><h3 style={{margin: '4px 0'}}>Firma/işyeri personeline eğitim atayın</h3><p style={{margin: 0, color: '#5e7485', fontSize: 13}}>Firma ve işyerini seçin, hazır programı açın, giriş hesabı olmayan personel için hesabı oluşturun ve eğitimi tek seçimle atayın. Katalog programlarında 10 final sorusu otomatik hazırdır.</p></div>
          <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center'}}>
            <select value={companyId} onChange={(event) => {setCompanyId(event.target.value); setBranchId(''); onBranchChange?.(''); onCompanyChange?.(event.target.value); setProgram(null); setAutomaticExamQuestions([]);}} aria-label="Firma seçin"><option value="">Firma seçin</option>{companies.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select>
            <select value={branchId} onChange={(event) => {setBranchId(event.target.value); onBranchChange?.(event.target.value); setSelectedEmployees([]);}} disabled={!companyId} aria-label="Personel ve eğitim işyeri seçin"><option value="">Firma geneli / işyeri seçilmedi</option>{branches.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select>
          </div>
        </div>
        <div style={{marginTop: 12, padding: 10, borderRadius: 8, background: '#effcfc', color: '#36556d', fontSize: 12}}><strong>Yeni paket oluşturma burada yapılmaz.</strong> Yeni bir eğitim paketi için üstteki merkezi katalogdan ilerleyin. Böylece aynı eğitim adıyla tekrar tekrar taslak oluşmaz.</div>
        <ErrorText value={error} />
        {message && <div role="status" aria-live="polite" style={{color: '#087443', marginTop: 8, fontWeight: 600}}>{message}</div>}
      </div>

      <div className="remote-training-manager-grid" style={{gap: 16}}>
        <div style={cardStyle}>
          <h4 style={{marginTop: 0}}>Firmaya atanmış sektör eğitimleri</h4>
          <div style={{fontSize: 12, color: '#5e7485', marginBottom: 10}}>Bu listede yalnızca seçtiğiniz firmaya hazırlanmış eğitimler görünür. Eski aynı adlı taslaklar silinmez; isterseniz geçmişten açabilirsiniz.</div>
          {(showOldPrograms ? programs.map((row) => ({row, hidden: []})) : compactPrograms).map(({row, hidden}) => <div key={row.id} style={{marginBottom: 8}}>
            <button type="button" onClick={() => loadDetail(row.id)} style={{display: 'block', width: '100%', textAlign: 'left', padding: 10, borderRadius: 9, border: `1px solid ${program?.id === row.id ? '#2474a8' : '#dbe5ef'}`, background: program?.id === row.id ? '#edf7ff' : '#fff'}}><strong>{localizedTrainingTitle(row.title)}</strong><span style={{display: 'block', fontSize: 12, color: '#5e7485'}}>{row.source_catalog_code ? `Sektör: ${packageSectorLabel(row.source_catalog_code)} · ` : ''}{statusLabel(row.status)} · sürüm {row.revision_no}</span>{row.source_catalog_package_id && <span style={{display: 'block', fontSize: 11, color: '#087443', marginTop: 3}}>Merkezi katalogdan bu firmaya atanmış</span>}</button>
            {!showOldPrograms && hidden.length > 0 && <div style={{fontSize: 11, color: '#795500', padding: '4px 8px'}}>Bu adla {hidden.length} eski taslak gizlendi.</div>}
          </div>)}
          {duplicateProgramCount > 0 && <button type="button" onClick={() => setShowOldPrograms((current) => !current)} style={{fontSize: 12, marginTop: 2}}>{showOldPrograms ? 'Eski kayıtları gizle' : `Eski/tekrarlı kayıtları göster (${duplicateProgramCount})`}</button>}
          {!programs.length && <p style={{color: '#5e7485'}}>Bu firmada uzaktan eğitim taslağı yok.</p>}
        </div>
        <div style={cardStyle}>
          {program ? (
            <>
              <div style={{display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap'}}><div><h4 style={{margin: 0}}>{localizedTrainingTitle(program.title)}</h4><div style={{fontSize: 12, color: '#5e7485'}}>{program.source_catalog_code ? `Atanan sektör: ${packageSectorLabel(program.source_catalog_code)} · ` : ''}{statusLabel(program.status)} · video %{program.completion_threshold_percent} · sınav %{program.passing_score}</div></div><div style={{display: 'flex', gap: 6, flexWrap: 'wrap'}}>{canEditContent && <><button type="button" onClick={() => programAction('ready-for-review')} disabled={busy}>İncelemeye hazır</button><button type="button" onClick={() => programAction('publish')} disabled={busy}>Yayımla</button></>}<button type="button" onClick={showReport} disabled={busy} title="Çalışanların durumunu ve belge PDF çıktısını açar">Belge / Rapor çıktıları</button></div></div>
              <div id="remote-training-certificate-output" style={{marginTop: 12, padding: '12px 14px', border: '1px solid #8cc6dc', borderRadius: 10, background: '#f6fcff'}} aria-label="Uzaktan eğitim belge çıktıları">
                <div style={{display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center', flexWrap: 'wrap'}}>
                  <div>
                    <strong style={{color: '#123b59'}}>Uzaktan eğitim belge çıktısı</strong>
                    <div style={{marginTop: 4, fontSize: 12, color: '#496174'}}>Tamamlanan ve final sınavından geçen çalışanlar için PDF burada açılır.</div>
                  </div>
                  <button type="button" onClick={showReport} disabled={busy} style={{minHeight: 40, padding: '8px 14px', fontWeight: 800}}>Belge listesini aç</button>
                </div>
                <div style={{marginTop: 8, fontSize: 12, color: '#795500'}}>Tamamlanmayan eğitimlerde belge üretilemez; çalışan başarıyla tamamladığında satırdaki indirme düğmesi aktif olur.</div>
              </div>
              {canEditContent && <>
<div style={{marginTop: 14, padding: 16, border: '2px solid #2474a8', borderRadius: 12, background: '#f4fbff'}} aria-labelledby="remote-video-help-title">
                <h4 id="remote-video-help-title" style={{margin: 0, color: '#123b59', fontSize: 17}}>Video yükleme ve silme — çok kolay</h4>
                <ol style={{margin: '10px 0 8px', paddingLeft: 22, color: '#36556d', lineHeight: 1.65}}>
                  <li>Bölüm yoksa önce bölüm adını yazıp <strong>Bölüm ekle</strong> düğmesine bas.</li>
                  <li>İlgili bölümdeki büyük <strong>Video seç ve yükle</strong> düğmesine bas.</li>
                  <li>Bilgisayarındaki videoyu seç. Yükleme bitene kadar bekle.</li>
                  <li>Video geldiğinde satırdaki <strong>Kaydet</strong>, <strong>Önizle</strong> ve durumuna göre <strong>Video yayımla</strong> düğmelerini kullan.</li>
                  <li>Yanlış taslak yüklediysen kırmızı <strong>Taslak videoyu sil</strong> düğmesine bas. Yayımlanmış videoyu değiştireceksen mavi <strong>Yeni sürüm yükle</strong> düğmesini kullan.</li>
                </ol>
                <div style={{padding: '9px 11px', borderRadius: 8, background: '#fff8e8', color: '#795500', fontSize: 12}}><strong>Önemli:</strong> Güncelleme yapılabilir. Eski yayımlanmış video geçmişte saklanır; yeni sürüm kontrol edilip yayımlanana kadar çalışan eski videoyu görmeye devam eder.</div>
              </div>
              {program.source_catalog_package_id && <div style={{marginTop: 12, padding: '10px 12px', border: '1px solid #b9e3c8', borderRadius: 9, background: '#f2fff6', color: '#17643a', fontSize: 12}}><strong>Kolay kullanım:</strong> Bu eğitim merkezi katalogdaki <strong>{localizedTrainingTitle(program.title)}</strong> paketinden hazırlandı. Bölümlerin sektörü otomatik bağlanır; bölümleri tek tek düzeltmeniz gerekmez.</div>}
              {program.status === 'published' && <div style={{marginTop: 10, padding: '10px 12px', border: '1px solid #f2c46d', borderRadius: 9, background: '#fff8e8', color: '#795500', fontSize: 12}}><strong>Yayımlanmış program:</strong> {programContentLocked ? <>Bu firma sürümünde <strong>{programAssignmentCount}</strong> çalışan ataması var. Yeni bölüm/video bu sürüme eklenmez; çalışanların mevcut ilerleme kayıtları korunur. <a href="#remote-training-catalog" onClick={(event) => scrollRemoteTrainingSection(event, 'remote-training-catalog')} style={{color: '#075985', fontWeight: 700}}>Yüksekte Çalışma merkezi kataloğuna git</a> ve yeni içeriği oradan yayımlayın.</> : <>Henüz çalışan ataması yapılmadıysa yeni bölüm ve video ekleyebilirsiniz. Atama yapıldığında bu firma sürümü korunur; yeni içerik için merkezi katalogdaki paketi kullanın.</>}</div>}
              {(program.automatic_final_exam?.automatic || (program.source_catalog_code && program.automatic_final_exam?.enabled)) && <div className="remote-training-exam-review" aria-label="Otomatik final sınavı soru inceleme alanı">
                <div className="remote-training-exam-auto-note-large">
                  <strong>{program.automatic_final_exam.question_count === (program.automatic_final_exam.required_question_count || 10) ? 'Final sınavı otomatik hazırlandı' : 'Final sınavı otomatik hazırlanamadı'} — {program.automatic_final_exam.question_count}/{program.automatic_final_exam.required_question_count || 10} soru</strong>
                  <span>Sorular yalnızca seçilen sektör eğitim paketinden alınır. Yayımlamadan önce metin, seçenekler ve doğru cevap yetkili kullanıcı tarafından incelenebilir. Geçme puanı %{program.automatic_final_exam.passing_score || 70}.</span>
                </div>
                {(program.automatic_final_exam.validation_errors || []).map((warning) => <div key={warning} className="remote-training-exam-validation-warning" role="alert">{warning}</div>)}
                {automaticExamQuestions.map((question, index) => {
                  const locked = ['published', 'archived'].includes(program.status);
                  const saveState = automaticQuestionSaveStates[question.id];
                  const saving = savingAutomaticQuestionId === question.id;
                  return <div key={question.id} className="remote-training-exam-question-editor">
                    <div className="remote-training-exam-question-heading"><strong>{index + 1}. Final sorusu</strong><span>{locked ? 'Yayımlandı — salt okunur' : 'Taslak — düzenlenebilir'}</span></div>
                    <textarea value={question.question_text || ''} onChange={(event) => updateAutomaticExamQuestion(question.id, 'question_text', event.target.value)} disabled={locked} rows={3} aria-label={`${index + 1}. final sorusu`} />
                    <div className="remote-training-exam-options-editor">
                      {['A', 'B', 'C', 'D'].map((option) => <label key={option}><span>{option}</span><input value={question.options?.[option] || ''} onChange={(event) => updateAutomaticExamOption(question.id, option, event.target.value)} disabled={locked} aria-label={`${index + 1}. final sorusu ${option} seçeneği`} /></label>)}
                    </div>
                    <div className="remote-training-exam-question-footer">
                      <label>Doğru cevap <select value={question.correct_option || 'A'} onChange={(event) => updateAutomaticExamQuestion(question.id, 'correct_option', event.target.value)} disabled={locked} aria-label={`${index + 1}. final sorusu doğru cevap`}><option value="A">A</option><option value="B">B</option><option value="C">C</option><option value="D">D</option></select></label>
                      <input value={question.explanation || ''} onChange={(event) => updateAutomaticExamQuestion(question.id, 'explanation', event.target.value)} disabled={locked} placeholder="Açıklama (isteğe bağlı)" aria-label={`${index + 1}. final sorusu açıklaması`} />
                      <button type="button" onClick={() => saveAutomaticExamQuestion(question)} disabled={locked || busy || saving}>
                        {saving ? 'Kaydediliyor…' : saveState === 'saved' ? 'Kaydedildi ✓' : 'Soruyu kaydet'}
                      </button>
                      {saveState === 'saved' && <span className="remote-training-question-save-state is-saved" role="status" aria-live="polite">Bu soru kaydedildi.</span>}
                      {saveState === 'error' && <span className="remote-training-question-save-state is-error" role="alert">Kayıt başarısız; üstteki açıklamayı kontrol edin.</span>}
                    </div>
                  </div>;
                })}
                {!automaticExamQuestions.length && <div className="remote-training-exam-validation-warning" role="alert">Onaylı soru paketi okunamadı; rastgele veya genel soru oluşturulmadı. Paket yöneticisi düzeltilmeden eğitim yayımlanamaz.</div>}
              </div>}
              {sectorScope && <div style={{marginTop: 14, padding: 14, border: '1px solid #b9d8e8', borderRadius: 10, background: '#f4fbff'}}>
                <div style={{display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap', alignItems: 'center'}}>
                  <div><strong>Firma için sektör / ders kapsamı</strong><div style={{fontSize: 12, color: '#5e7485', marginTop: 4}}>Tüm dersler tek katalogda tutulur. Çalışana atama yapıldığında yalnızca burada seçilen sektörler açılır ve sınav soruları aynı kapsamdan gelir.</div></div>
                  <button type="button" onClick={saveSectorScope} disabled={busy || ['published', 'archived'].includes(program.status)}>{sectorScope.catalog_fixed ? 'Katalog kapsamını onayla' : 'Firma ders kapsamını kaydet'}</button>
                </div>
                {sectorScope.catalog_fixed && <div style={{marginTop: 10, padding: 9, borderRadius: 7, background: '#eaf8ef', color: '#17643a', fontSize: 12}}><strong>Merkezi paket kapsamı sabit:</strong> Bu kart yalnızca <strong>{sectorLabel(sectorScope.catalog_sector_code)}</strong> dersidir. Ortak Temel İSG ve diğer sektörler ayrı eğitim kartlarından atanır.</div>}
                {sectorScope.mode === 'legacy' && <div style={{marginTop: 10, padding: 8, borderRadius: 7, background: '#fff8e8', color: '#8a5a00', fontSize: 12}}>Bu eski taslakta sektör kapsamı henüz kaydedilmemiş. Mevcut atamalar eski davranışla korunur; yeni atamalardan önce kapsamı kaydetmeniz önerilir.</div>}
                <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 8, marginTop: 12}}>
                  {sectorScope.sectors.map((sector) => {
                    const checked = selectedSectorCodes.includes(sector.code);
                    const catalogDisabled = sectorScope.catalog_fixed;
                    return <label key={sector.code} style={{display: 'block', padding: 10, border: `1px solid ${checked ? '#37a6c6' : '#dbe5ef'}`, borderRadius: 8, background: checked ? '#fff' : '#fafcfe', cursor: catalogDisabled || sector.locked ? 'default' : 'pointer', opacity: catalogDisabled && !checked ? .7 : 1}}>
                      <input type="checkbox" checked={checked} disabled={catalogDisabled || sector.locked || busy || ['published', 'archived'].includes(program.status)} onChange={() => setSelectedSectorCodes((current) => current.includes(sector.code) ? current.filter((code) => code !== sector.code) : [...current, sector.code])} /> <strong>{sector.label}</strong>
                      <span style={{display: 'block', color: '#5e7485', fontSize: 11, marginTop: 4}}>{sector.description}</span>
                      <span style={{display: 'block', color: '#496174', fontSize: 11, marginTop: 5}}>{sector.section_count} bölüm · {sector.video_count} video · {sector.question_count} soru</span>
                    </label>;
                  })}
                </div>
                <div style={{fontSize: 12, color: '#36556d', marginTop: 10}}>Seçili kapsam: <strong>{selectedSectorCodes.map(sectorLabel).join(', ') || 'Henüz seçilmedi'}</strong></div>
              </div>}
              <div style={{marginTop: 14, padding: 14, border: '1px solid #dbe5ef', borderRadius: 10, background: '#fbfdff'}}>
                <strong style={{display: 'block', color: '#123b59', fontSize: 15}}>{catalogProgramHasSections ? 'İsteğe bağlı yeni ders bölümü' : 'Yeni ders bölümü ekle'}</strong>
                <span style={{display: 'block', color: '#5e7485', fontSize: 12, marginTop: 4}}>{programContentLocked ? 'Bu firma sürümü çalışan ataması nedeniyle sabittir. Yeni içeriği merkezi katalogdaki Yüksekte Çalışma paketine ekleyin.' : sectionCreateHint}</span>
                {programContentLocked
                  ? <div role="status" style={{marginTop: 10, padding: '10px 12px', borderRadius: 8, background: '#fff8e8', color: '#795500', fontSize: 12}}>
                      Bu firma sürümünde <strong>{programAssignmentCount}</strong> çalışan ataması var; yeni bölüm bu sürüme eklenemez. <a href="#remote-training-catalog" onClick={(event) => scrollRemoteTrainingSection(event, 'remote-training-catalog')} style={{color: '#075985', fontWeight: 700}}>Merkezi katalogdaki pakete git</a>.
                    </div>
                  : <div style={{display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 10}}>
                      <input value={sectionTitle} onChange={(event) => setSectionTitle(event.target.value)} aria-label="Yeni ders bölümü adı" placeholder={catalogSectorCode ? `${catalogSectorName} bölüm adı` : 'Bölüm adı yazın'} />
                      {catalogSectorCode
                        ? <span style={{padding: '9px 10px', border: '1px solid #b9d8e8', borderRadius: 7, background: '#f4fbff', color: '#36556d', fontSize: 12}}>Bölüm kapsamı: <strong>{catalogSectorName}</strong></span>
                        : <label style={{display: 'flex', alignItems: 'center', gap: 5}}>Bölümün sektörü <select value={sectionSectorCode} onChange={(event) => setSectionSectorCode(event.target.value)}>{scopeSectorOptions.map((sector) => <option key={sector.code} value={sector.code}>{sector.label}</option>)}</select></label>}
                      <button type="button" onClick={createSection} disabled={busy || program.status === 'archived' || sectionTitle.trim().length < 2} style={{minHeight: 44, padding: '10px 16px', fontWeight: 700}}>{catalogProgramHasSections ? 'Özel bölüm ekle' : 'Bölüm ekle'}</button>
                    </div>}
              </div>
              {program.sections?.length > 0 && visibleProgramSections.length === 0 && <div role="status" style={{marginTop: 10, padding: 10, borderRadius: 8, background: '#fff8e8', color: '#795500', fontSize: 12}}>Seçili paket kapsamı dışında kalan eski bölüm kayıtları gizlendi. Mevcut çalışan atamalarına dokunulmadı.</div>}
              {visibleProgramSections.map((section) => (
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
                    {programContentLocked
                      ? <div role="status" style={{padding: '10px 12px', borderRadius: 8, background: '#fff8e8', color: '#795500', fontSize: 12, maxWidth: 420}}>
                          Bu firma sürümünde çalışan ataması bulunduğu için yeni video eklenemez. <a href="#remote-training-catalog" onClick={(event) => scrollRemoteTrainingSection(event, 'remote-training-catalog')} style={{color: '#075985', fontWeight: 700}}>Yeni videoyu merkezi katalogdaki ilgili bölüme yükleyin</a>.
                        </div>
                      : <label htmlFor={`remote-video-upload-${section.id}`} aria-disabled={busy || program.status === 'archived'} onClick={(event) => {if (busy || program.status === 'archived') event.preventDefault();}} style={{minHeight: 48, padding: '12px 18px', fontSize: 15, fontWeight: 700, color: '#fff', background: busy || program.status === 'archived' ? '#7faec2' : '#1479a6', border: '1px solid #0d5d83', borderRadius: 8, cursor: busy || program.status === 'archived' ? 'wait' : 'pointer', display: 'inline-flex', alignItems: 'center'}}>
                          {uploadingSectionId === section.id ? 'Video yükleniyor…' : 'Video seç ve yükle'}
                        </label>}
                  </div>
                  <div style={{display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 8}}><label style={{fontSize: 12, color: '#496174'}}>Bölüm sektörü <select value={sectionSectorDrafts[section.id] || (sectorScope?.catalog_fixed ? sectorScope.catalog_sector_code : section.sector_code) || 'common'} onChange={(event) => setSectionSectorDrafts((current) => ({...current, [section.id]: event.target.value}))}>{scopeSectorOptions.map((sector) => <option key={sector.code} value={sector.code}>{sector.label}</option>)}</select></label><button type="button" onClick={() => saveSectionSector(section)} disabled={busy || ['published', 'archived'].includes(program.status)}>Sektörü kaydet</button></div>
                  {(section.videos || []).map((video) => (
                    <div key={video.id} style={{marginTop: 8, padding: 10, borderRadius: 8, background: '#f7fafc', display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap'}}>
                      <div style={{minWidth: 240, flex: 1}}>
                        <input value={Object.prototype.hasOwnProperty.call(videoTitles, video.id) ? videoTitles[video.id] : video.title} onChange={(event) => setVideoTitles((current) => ({...current, [video.id]: event.target.value}))} aria-label={`${video.title} video başlığı`} style={{width: '100%'}} />
                        <div style={{fontSize: 12, color: '#5e7485'}}>{statusLabel(video.status)} · {video.duration_seconds ? `${video.duration_seconds} sn` : 'süre bekleniyor'} · rev. {video.revision_no}</div>
                        {video.processing_error && <div style={{fontSize: 12, color: '#b42318'}}>{video.processing_error}</div>}
                      </div>
                      <div style={{display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center'}}>
                        {video.status === 'published' && video.is_current && program.status !== 'archived' && <>
                          <input
                            ref={(node) => { uploadInputRefs.current[`revision-${video.id}`] = node; }}
                            id={`remote-video-revision-${video.id}`}
                            type="file"
                            accept="video/mp4,video/webm,video/quicktime,.m4v"
                            aria-label={`${video.title} için yeni video sürümü seç`}
                            style={{position: 'absolute', width: 1, height: 1, padding: 0, margin: -1, overflow: 'hidden', clip: 'rect(0, 0, 0, 0)', whiteSpace: 'nowrap', border: 0}}
                            onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ''; if (file) uploadVideo(section, file, video); }}
                          />
                          <label htmlFor={`remote-video-revision-${video.id}`} aria-disabled={busy} onClick={(event) => {if (busy) event.preventDefault();}} style={{minHeight: 42, padding: '10px 14px', color: '#075985', background: busy ? '#d7edf8' : '#e8f6ff', border: '2px solid #72b9d7', borderRadius: 8, fontWeight: 700, cursor: busy ? 'wait' : 'pointer', display: 'inline-flex', alignItems: 'center'}}>
                            {uploadingVideoId === video.id ? 'Yeni sürüm yükleniyor…' : 'Yeni sürüm yükle'}
                          </label>
                        </>}
                        <button type="button" onClick={() => saveVideo(video)} disabled={busy || program.status === 'archived' || HISTORICAL_VIDEO_STATUSES.includes(video.status)}>Kaydet</button>
                        {['ready_for_review', 'published', 'unpublished'].includes(video.status) && <button type="button" onClick={() => previewVideo(video)} disabled={busy}>Önizle</button>}
                        {video.status === 'ready_for_review' && <button type="button" onClick={() => videoAction(video, 'publish')} disabled={busy}>Video yayımla</button>}
                        {video.status === 'processing_failed' && <button type="button" onClick={() => videoAction(video, 'retry-processing')} disabled={busy}>Yeniden işle</button>}
                        {!HISTORICAL_VIDEO_STATUSES.includes(video.status) && <button type="button" onClick={() => deleteVideo(video)} disabled={busy || program.status === 'archived'} style={{minHeight: 42, padding: '10px 14px', color: '#b42318', background: '#fff5f4', border: '2px solid #e39b93', borderRadius: 8, fontWeight: 700}} aria-label={`${video.title} taslak videosunu sil`}>Taslak videoyu sil</button>}
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
                  <label>Sektör <select value={checkpointDraft.sector_code} onChange={(event) => setCheckpointDraft((current) => ({...current, sector_code: event.target.value}))}>{scopeSectorOptions.map((sector) => <option key={sector.code} value={sector.code}>{sector.label}</option>)}</select></label>
                  <button type="button" onClick={createCheckpointQuestion} disabled={busy || ['published', 'archived'].includes(program.status)}>Soruyu kaydet</button>
                </div>
                {(program.checkpoint_questions || []).length > 0 && <div style={{fontSize: 12, color: '#496174', marginTop: 8}}>{program.checkpoint_questions.length} video içi kontrol sorusu tanımlı.</div>}
              </div>
              {!program.source_catalog_code && !program.automatic_final_exam?.automatic && <div style={{borderTop: '1px solid #e5edf3', marginTop: 16, paddingTop: 12}}>
                <strong>Final sınavı — mevcut soru bankası</strong>
                <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8}}>
                  {questionBank.length > 0 ? <select value={examQuestionId} onChange={(event) => setExamQuestionId(event.target.value)} aria-label="Soru bankası sorusu"><option value="">Yayımlanmış soru seçin</option>{questionBank.map((question) => <option key={question.id} value={question.id}>#{question.id} · {question.question_text.slice(0, 90)}</option>)}</select> : <input type="number" min="1" value={examQuestionId} onChange={(event) => setExamQuestionId(event.target.value)} placeholder="Yayımlanmış soru ID" aria-label="Yayımlanmış soru ID" />}
                  <label>Soru sektörü <select value={examSectorCode} onChange={(event) => setExamSectorCode(event.target.value)}>{scopeSectorOptions.map((sector) => <option key={sector.code} value={sector.code}>{sector.label}</option>)}</select></label>
                  <button type="button" onClick={linkExamQuestion} disabled={busy || ['published', 'archived'].includes(program.status)}>Soruyu sınava bağla</button>
                </div>
                {(program.exam_question_links || []).length > 0 && <div style={{display: 'grid', gap: 6, marginTop: 8}}>{program.exam_question_links.map((link) => <div key={link.id} style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap', padding: '8px 10px', borderRadius: 7, background: '#f4f8fb', color: '#496174', fontSize: 12}}><span><strong>Soru #{link.question_id}</strong> · {sectorLabel(link.sector_code)} · sıra {link.position}</span><button type="button" onClick={() => unlinkExamQuestion(link)} disabled={busy || ['published', 'archived'].includes(program.status)}>Sınavdan çıkar</button></div>)}</div>}
              </div>}
              </>}
<div style={{borderTop: '1px solid #e5edf3', marginTop: 16, paddingTop: 12}}>
                <strong>Çalışan giriş hesabı eşleştirme</strong>
                <p style={{margin: '6px 0', color: '#5e7485', fontSize: 12}}>Eğitim ve sınav atayacağınız personel için aşağıdan doğrudan salt-okunur hesap oluşturabilirsiniz. Hesap oluşturulunca geçici parola yalnızca bir kez gösterilir; çalışan ilk girişte değiştirmeden eğitime başlayamaz.</p>
                <div style={{display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap'}}>
                  <select value={provisionEmployeeId} onChange={(event) => setProvisionEmployeeId(event.target.value)} aria-label="Yeni giriş için personel seçin"><option value="">Yeni hesap için personel seçin</option>{visibleEmployees.map((row) => <option key={row.id} value={row.id}>{row.full_name}</option>)}</select>
                  <input type="email" value={provisionEmail} onChange={(event) => setProvisionEmail(event.target.value)} placeholder="Çalışanın e-posta adresi" aria-label="Çalışan e-posta adresi" />
                  <button type="button" onClick={provisionEmployeeAccount} disabled={busy || !provisionEmployeeId || !provisionEmail.trim()}>Hesap oluştur ve eşleştir</button>
                </div>
                {provisionedCredentials && <div style={{marginTop: 9, padding: 10, borderRadius: 8, background: '#fff8e8', border: '1px solid #f2c46d', color: '#795500', fontSize: 12}}>
                  <strong>Geçici giriş bilgisi — yalnızca şimdi gösteriliyor:</strong><br />
                  Kullanıcı adı: <code>{provisionedCredentials.email}</code><br />
                  Geçici parola: <code style={{userSelect: 'all'}}>{provisionedCredentials.temporary_password}</code><br />
                  Bu bilgiyi güvenli kanaldan çalışana iletin; ilk girişte değiştirmesi zorunludur.
                </div>}
                <div style={{display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap'}}>
                  <select value={accessEmployeeId} onChange={(event) => setAccessEmployeeId(event.target.value)} aria-label="Giriş için personel seçin"><option value="">Personel seçin</option>{visibleEmployees.map((row) => <option key={row.id} value={row.id}>{row.full_name}</option>)}</select>
                  <select value={accessUserId} onChange={(event) => setAccessUserId(event.target.value)} aria-label="Personel giriş hesabı seçin"><option value="">Giriş hesabı seçin</option>{employeeUsers.map((row) => <option key={row.id} value={row.id}>{row.full_name} · {row.email}</option>)}</select>
                  <button type="button" onClick={saveEmployeeAccess} disabled={busy || !accessEmployeeId || !accessUserId}>Hesabı eşleştir</button>
                </div>
                {employeeAccess.length > 0 && <div style={{fontSize: 12, color: '#496174', marginTop: 8}}>Eşleştirilmiş çalışan hesabı: {employeeAccess.length}</div>}
              </div>
              <div style={{borderTop: '1px solid #e5edf3', marginTop: 16, paddingTop: 12}}>
                <strong>2. Personel seçin ve eğitim/sınav ataması yapın</strong>
                <p style={{margin: '6px 0', color: '#5e7485', fontSize: 12}}>Atama sırasında yukarıda kaydedilen sektör kapsamı çalışana sabitlenir. Çalışan yalnızca bu kapsamın videolarını ve final sınavı sorularını görür; burada seçim yapılmadan hiçbir çalışana otomatik atama yapılmaz.</p>
                <label style={{display: 'inline-flex', alignItems: 'center', gap: 8, marginTop: 4, color: '#36556d', fontSize: 13}}>Eğitim son tarihi <input type="date" value={assignmentDueDate} onChange={(event) => setAssignmentDueDate(event.target.value)} aria-label="Eğitim son tarihi" /><span style={{fontSize: 12, color: '#5e7485'}}>Boş bırakırsanız son tarih belirlenmez.</span></label>
                <div className="remote-training-employee-picker-toolbar">
                  <span><strong>{selectedEmployees.length}</strong> personel seçildi{branchId ? ` · ${visibleEmployees.length} kişi bu işyerinde` : ''}</span>
                  <button type="button" onClick={() => { setAssignmentNotice(null); setSelectedEmployees(visibleEmployees.map((row) => Number(row.id))); }} disabled={busy || !visibleEmployees.length}>Listedeki hepsini seç</button>
                  <button type="button" onClick={() => { setAssignmentNotice(null); setSelectedEmployees([]); }} disabled={busy || !selectedEmployees.length}>Seçimi temizle</button>
                </div>
                <div className="remote-training-employee-picker" role="group" aria-label="Eğitim ve sınav atanacak personeller">
                  {visibleEmployees.map((row) => <label className="remote-training-employee-option" key={row.id}>
                    <input type="checkbox" checked={selectedEmployees.includes(Number(row.id))} onChange={() => toggleEmployee(row.id)} disabled={busy} />
                    <span><strong>{row.full_name}</strong>{row.email && <small>{row.email}</small>}</span>
                  </label>)}
                  {!visibleEmployees.length && <span className="remote-training-employee-empty">{branchId ? 'Seçilen işyerinde aktif personel bulunamadı.' : 'Bu firmada aktif personel bulunamadı.'}</span>}
                </div>
                {assignmentNotice && <div role={assignmentNotice.kind === 'error' ? 'alert' : 'status'} aria-live="polite" style={{marginTop: 10, padding: '10px 12px', borderRadius: 8, background: assignmentNotice.kind === 'error' ? '#fff1f0' : '#ecfdf5', color: assignmentNotice.kind === 'error' ? '#b42318' : '#087443', border: `1px solid ${assignmentNotice.kind === 'error' ? '#e39b93' : '#9bd5b1'}`, fontSize: 13, fontWeight: 600}}>
                  <strong>{assignmentNotice.kind === 'error' ? 'Atama yapılamadı:' : 'Atama onayı:'}</strong> {assignmentNotice.text}
                </div>}
                {!assignmentNotice && !selectedEmployees.length && <div style={{marginTop: 10, color: '#795500', fontSize: 12}}>Atama için önce listeden en az bir personelin kutusunu işaretleyin.</div>}
                <button type="button" onClick={assign} disabled={busy || !selectedEmployees.length} style={{marginTop: 10}}>Seçilen personele eğitim ve sınav ata</button>
              </div>
            </>
          ) : <p style={{color: '#5e7485'}}>Detay ve video yaşam döngüsünü görmek için bir taslak seçin.</p>}
        </div>
      </div>
      {report && <div id="remote-training-report" style={cardStyle}><h4 style={{marginTop: 0}}>Uzaktan eğitim raporu ve belgelendirme</h4><p style={{margin: '6px 0 10px', color: '#496174', fontSize: 12}}>Başarılı çalışanlar için çıktı, yüz yüze eğitimde kullanılan mevcut belge şablonuyla aynı düzen ve imza alanlarıyla hazırlanır; belgede eğitim şekli <strong>Uzaktan Eğitim</strong> olarak görünür.</p><div style={{display: 'flex', gap: 14, flexWrap: 'wrap', color: '#496174'}}><span>Atama: <strong>{report.assignment_count}</strong></span><span>Ortalama video ilerlemesi: <strong>%{report.average_video_progress_percent}</strong></span><span>Sınav denemesi: <strong>{report.exam_attempt_count}</strong></span><span>Uzaktan eğitim belgesi: <strong>{report.participation_document_count ?? report.certificate_count}</strong></span></div>{(report.rows || []).length > 0 && <div style={{overflowX: 'auto', marginTop: 10}}><table style={{width: '100%'}}><thead><tr><th>Çalışan</th><th>Durum</th><th>Kimlik snapshot</th><th>İlerleme</th><th>Belge</th></tr></thead><tbody>{report.rows.map((row) => <tr key={row.id}><td>{row.employee_name}</td><td>{statusLabel(row.status)}</td><td>{row.workplace_name_snapshot || '—'} · {row.nace_code_snapshot || 'NACE yok'} · {row.hazard_class_snapshot || 'Tehlike sınıfı yok'}</td><td>{row.summary?.completed_video_count || 0}/{row.summary?.required_video_count || 0}</td><td>{row.status === 'completed' ? <button type="button" onClick={() => downloadParticipationDocument(row)} disabled={busy}>Uzaktan Eğitim belgesini al</button> : <button type="button" disabled style={{fontSize: 12, padding: '6px 9px', color: '#5e7485', background: '#f1f5f9', border: '1px solid #cbd5e1', borderRadius: 7}} title="Tüm videolar ve en az %70 final sınavı tamamlanınca aktif olur">Belge çıktısı eğitim tamamlanınca açılır</button>}</td></tr>)}</tbody></table></div>}</div>}
    </section>
  );
}


function scrollRemoteTrainingSection(event, sectionId) {
  event.preventDefault();
  event.stopPropagation();
  const target = document.getElementById(sectionId);
  if (!target) return;
  if (target instanceof HTMLDetailsElement) target.open = true;
  target.scrollIntoView({behavior: 'smooth', block: 'start'});
}

function remoteCertificateGroupKey(row) {
  return JSON.stringify([
    row.company_id,
    row.employee_id,
    row.branch_id || '',
    row.workplace_name_snapshot || '',
    row.sgk_registration_number_snapshot || '',
    row.nace_code_snapshot || '',
    row.nace_description_snapshot || '',
    row.hazard_class_snapshot || '',
  ]);
}

function combineRemoteCertificateRows(rows) {
  const groups = new Map();
  (rows || []).forEach((row) => {
    const key = remoteCertificateGroupKey(row);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  });

  const statusPriority = ['failed', 'expired', 'in_progress', 'not_started', 'completed'];
  return [...groups.values()].map((items) => {
    const first = items[0];
    const titles = [];
    items.forEach((item) => {
      const title = String(item.program_title || '').trim();
      if (title && !titles.includes(title)) titles.push(title);
    });
    const summaries = items.map((item) => item.summary || {});
    const statuses = new Set(items.map((item) => item.status));
    const status = statusPriority.find((value) => statuses.has(value)) || first.status;
    const allCompleted = items.every((item) => item.status === 'completed');
    const certificateReady = allCompleted && items.every((item) => item.certificate_ready);
    const scores = items
      .map((item) => Number(item.examination_score))
      .filter((value) => Number.isFinite(value));
    const averageScore = scores.length
      ? Math.round(scores.reduce((sum, value) => sum + value, 0) / scores.length)
      : null;
    const summary = {
      ...first.summary,
      required_video_count: summaries.reduce((sum, item) => sum + Number(item.required_video_count || 0), 0),
      completed_video_count: summaries.reduce((sum, item) => sum + Number(item.completed_video_count || 0), 0),
      required_videos_complete: summaries.every((item) => item.required_videos_complete),
      required_checkpoint_count: summaries.reduce((sum, item) => sum + Number(item.required_checkpoint_count || 0), 0),
      required_checkpoints_complete: summaries.every((item) => item.required_checkpoints_complete),
      exam_required: summaries.some((item) => item.exam_required),
      exam_passed: summaries.every((item) => item.exam_passed),
      complete: summaries.every((item) => item.complete),
      status,
      exam_score: averageScore,
    };
    return {
      ...first,
      assignment_ids: items.map((item) => item.id),
      assignment_count: items.length,
      program_count: titles.length || items.length,
      program_titles: titles,
      program_title: titles.join(' + ') || first.program_title,
      status,
      assigned_at: items.map((item) => item.assigned_at).filter(Boolean).sort()[0] || first.assigned_at,
      completed_at: items.map((item) => item.completed_at).filter(Boolean).sort().slice(-1)[0] || null,
      summary,
      certificate_ready: certificateReady,
      examination_score: averageScore,
      certificate_block_reason: allCompleted
        ? (certificateReady ? null : 'Belge için tarihsel işyeri ve NACE bilgileri eksik.')
        : 'Tek PDF belge için bu çalışanın tüm eğitim paketleri tamamlanmalıdır.',
    };
  });
}


function RemoteCertificateHub() {
  const [companies, setCompanies] = useState([]);
  const [companyId, setCompanyId] = useState('');
  // Belge merkezi arşiv mantığıyla tamamlanan belgeleri önce gösterir; diğer durumlar isteğe bağlı filtrelenebilir.
  const [status, setStatus] = useState('completed');
  const [query, setQuery] = useState('');
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function load() {
    setBusy(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (companyId) params.set('company_id', companyId);
      // Status and search are applied after grouping so one employee never
      // appears as two partial certificate rows.
      const [companyRows, documentRows] = await Promise.all([
        api('/companies'),
        api('/trainings/remote/certificates' + (params.toString() ? '?' + params.toString() : '')),
      ]);
      setCompanies(Array.isArray(companyRows) ? companyRows : []);
      setRows(Array.isArray(documentRows) ? documentRows : []);
    } catch (err) {
      setError(err.message || 'Uzaktan eğitim belge listesi alınamadı.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load().catch(() => {});
    // Firma ve durum filtresi değişince listeyi yenile; arama metni için Ara düğmesi kullanılır.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId, status]);

  async function download(row) {
    if (!row?.certificate_ready) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await downloadFile(
        '/trainings/remote/assignments/' + row.id + '/certificate.pdf',
        'uzaktan-egitim-belgesi-' + row.id + '.pdf',
      );
      setMessage((row.company_name || 'Firma') + ' · ' + (row.employee_name || 'Çalışan') + ' için ' + (row.program_count || 1) + ' eğitimi içeren tek PDF belge indirildi.');
    } catch (err) {
      setError(err.message || 'Belge PDF’i alınamadı.');
    } finally {
      setBusy(false);
    }
  }

  const groupedRows = useMemo(() => combineRemoteCertificateRows(rows), [rows]);
  const visibleRows = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase('tr-TR');
    return groupedRows.filter((row) => {
      const statusMatches = !status || status === 'all' || row.status === status;
      const searchMatches = !needle || [
        row.company_name,
        row.employee_name,
        row.program_title,
        row.branch_name,
      ].some((value) => String(value || '').toLocaleLowerCase('tr-TR').includes(needle));
      return statusMatches && searchMatches;
    });
  }, [groupedRows, query, status]);
  const completedCount = visibleRows.reduce(
    (total, row) => total + (row.status === 'completed' ? (row.assignment_count || 1) : 0),
    0,
  );
  const readyCount = visibleRows.filter((row) => row.certificate_ready).length;
  const selectedCompany = companies.find((company) => String(company.id) === String(companyId));
  const selectedCompanyName = selectedCompany?.name || 'Seçilen firma';
  const emptyMessage = busy
    ? 'Belgeler yükleniyor…'
    : companyId
      ? `“${selectedCompanyName}” firmasına ait tamamlanmış eğitim belgesi bulunamadı.`
      : status === 'completed'
        ? 'Henüz tamamlanmış uzaktan eğitim belgesi bulunmuyor.'
        : 'Bu filtrelerle eşleşen uzaktan eğitim kaydı bulunamadı.';

  return (
    <section id="remote-training-certificate-hub" style={cardStyle} aria-label="Uzaktan eğitim belgeleri merkezi">
      <div style={{display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'flex-start'}}>
        <div>
          <div style={{fontSize: 12, color: '#0b7f83', fontWeight: 800, letterSpacing: '.04em'}}>BELGE VE ARŞİV MERKEZİ</div>
          <h3 style={{margin: '4px 0'}}>Tamamlanmış uzaktan eğitim belgeleri</h3>
          <p style={{margin: 0, color: '#496174', fontSize: 13}}>
            Tamamlanan ve final sınavını geçen çalışanların belgelerini burada bulun ve indirin.
            Bu ekran çalışanların kendi eğitim ekranından ayrıdır.
          </p>
        </div>
        <div style={{display: 'flex', gap: 8, flexWrap: 'wrap'}}>
          <span style={{padding: '7px 10px', borderRadius: 999, background: '#ecfdf5', color: '#087443', fontWeight: 800, fontSize: 12}}>
            {readyCount} belge hazır
          </span>
          <span style={{padding: '7px 10px', borderRadius: 999, background: '#eff6ff', color: '#1d4ed8', fontWeight: 800, fontSize: 12}}>
            {completedCount} eğitim tamamlandı
          </span>
        </div>
      </div>

      <div role="note" style={{marginTop: 14, padding: '11px 13px', borderRadius: 10, border: '1px solid #b9e3c8', background: '#f2fff6', color: '#17643a', fontSize: 12}}>
        <strong>Belgeyi doğru kaydı seçerek alın:</strong> Her satır tek bir <strong>firma + işyeri/şube + çalışan</strong> kapsamıdır.
        Önce firma ve işyeri adını kontrol edin; aynı çalışan için aynı işyeri kapsamındaki tamamlanmış uzaktan eğitim paketleri
        <strong>tek PDF belgede birleşir</strong>. PDF indirme düğmesi yalnızca tüm videolar ve final sınavı başarıyla tamamlanınca açılır.
        İş güvenliği uzmanı, sadece aktif olarak görevlendirildiği firmaların belgelerini görebilir ve indirebilir.
      </div>

      <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginTop: 14, padding: 10, borderRadius: 10, background: '#f7fbfd'}}>
        <select value={companyId} onChange={(event) => setCompanyId(event.target.value)} aria-label="Belge firması">
          <option value="">Tüm erişebildiğim firmalar</option>
          {companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
        </select>
        <select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Belge durumu">
          <option value="all">Tüm durumlar</option>
          <option value="completed">Tamamlanan belgeler (arşiv)</option>
          <option value="in_progress">Devam ediyor</option>
          <option value="not_started">Başlamadı</option>
          <option value="failed">Başarısız</option>
          <option value="expired">Süresi geçti</option>
        </select>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => { if (event.key === 'Enter') load().catch(() => {}); }}
          placeholder="Firma, çalışan veya eğitim ara..."
          aria-label="Uzaktan eğitim belge araması"
          style={{minWidth: 240, flex: 1}}
        />
        <button type="button" onClick={() => load()} disabled={busy}>Ara</button>
        <button type="button" onClick={() => load()} disabled={busy}>Yenile</button>
      </div>

      {error && <div role="alert" style={{marginTop: 10, color: '#b42318', fontWeight: 700}}>{error}</div>}
      {message && <div role="status" aria-live="polite" style={{marginTop: 10, color: '#087443', fontWeight: 700}}>{message}</div>}
      <div role="status" aria-live="polite" style={{marginTop: 10, padding: '9px 12px', borderRadius: 9, background: '#f8fafc', color: '#496174', fontSize: 12}}>
        {companyId
          ? <><strong>{selectedCompanyName}</strong> seçildi. Bu firmaya ait tamamlanmış belgeler ve eğitim kapsamları aşağıda listelenir.</>
          : 'Firma seçerek yalnızca o firmaya ait tamamlanmış eğitim belgelerini ve PDF dökümlerini görebilirsiniz.'}
      </div>

      <div style={{overflowX: 'auto', marginTop: 12}}>
        <table style={{width: '100%'}}>
          <thead>
            <tr>
              <th>Firma / İşyeri</th>
              <th>Eğitim / belge kapsamı</th>
              <th>Çalışan</th>
              <th>Durum / İlerleme</th>
              <th>Sınav</th>
              <th>Belge</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => (
              <tr key={row.id}>
                <td>
                  <div style={{fontSize: 11, color: '#0b7f83', fontWeight: 800, letterSpacing: '.04em'}}>FİRMA / İŞYERİ</div>
                  <strong>{row.company_name || 'Firma bilgisi yok'}</strong>
                  <small style={{display: 'block', color: '#5e7485'}}>İşyeri: {row.branch_name || 'Firma geneli'}</small>
                  <small style={{display: 'block', color: '#5e7485'}}>
                    {row.nace_code_snapshot || 'NACE yok'} · {row.hazard_class_snapshot || 'Tehlike sınıfı yok'}
                  </small>
                </td>
                <td>
                  <div style={{display: 'grid', gap: 4}}>
                    {(row.program_titles?.length ? row.program_titles : [row.program_title]).map((title, index) => (
                      <strong key={title + '-' + index}>{localizedTrainingTitle(title)}</strong>
                    ))}
                  </div>
                  <small style={{display: 'block', color: '#5e7485', marginTop: 3}}>
                    Uzaktan eğitim · {row.program_count > 1 ? row.program_count + ' eğitim · tek PDF belge' : (row.source_catalog_revision_no ? 'Katalog sürümü ' + row.source_catalog_revision_no : 'Firma programı')}
                  </small>
                </td>
                <td>{row.employee_name}</td>
                <td>
                  <strong>{statusLabel(row.status)}</strong>
                  <small style={{display: 'block', color: '#5e7485'}}>
                    {(row.summary?.completed_video_count || 0) + '/' + (row.summary?.required_video_count || 0) + ' video'}
                  </small>
                </td>
                <td>{row.examination_score == null ? '—' : '%' + row.examination_score}</td>
                <td>
                  {row.certificate_ready ? (
                    <button
                      type="button"
                      onClick={() => download(row)}
                      disabled={busy}
                      title={(row.company_name || 'Firma') + ' · ' + (row.employee_name || 'Çalışan') + ' PDF belgesi'}
                    >
                      PDF belgeyi al
                    </button>
                  ) : (
                    <span title={row.certificate_block_reason || 'Eğitim tamamlanınca açılır'} style={{color: '#795500', fontSize: 12}}>
                      Belge henüz hazır değil
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {!visibleRows.length && (
              <tr>
                <td colSpan={6} style={{padding: 18, textAlign: 'center', color: '#5e7485'}}>
                  {emptyMessage}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div style={{marginTop: 10, color: '#5e7485', fontSize: 12}}>
        Listeyi kullanırken önce <strong>Firma / İşyeri</strong> ve <strong>Çalışan</strong> alanlarını kontrol edin.
        Bu merkezdeki PDF, rastgele bir çalışana verilecek belge değildir; seçtiğiniz satırın firma ve çalışan kapsamına aittir.
        Yetki kuralı: OSGB yöneticisi kendi OSGB’sini, uzman ise yalnızca aktif görevlendirmesinin bulunduğu firmaları görür.
      </div>
    </section>
  );
}

function RemoteTrainingGuide() {
  return (
    <details className="remote-training-guide" id="remote-training-guide" open>
      <summary className="remote-training-guide-summary">
        <span className="remote-training-guide-icon" aria-hidden="true">✓</span>
        <span className="remote-training-guide-heading">
          <strong>Uzaktan Eğitim Kullanım Rehberi</strong>
          <small>Uzmanı içerik hazırlamadan katılım belgesi arşivine kadar yönlendiren 8 adım</small>
        </span>
        <span className="remote-training-guide-count">8 adım</span>
      </summary>
      <div className="remote-training-guide-body">
        <p className="remote-training-guide-intro">Bu sırayı takip edin. Her adım tamamlanmadan sonraki adıma geçmeyin; yeşil onay mesajı gördüğünüzde işlem tamamdır.</p>
        <ol className="remote-training-guide-steps">
          <li>
            <span className="remote-training-guide-step-number">1</span>
            <div><strong>Videoları hazırlayın</strong><p>Merkezi katalogdan eğitim paketini seçin. Bölümleri oluşturun, her bölümün kendi <b>Video seç ve yükle</b> düğmesiyle videoyu yükleyin. Durum <b>Yayımlandı</b> olana kadar bekleyin.</p></div>
          </li>
          <li>
            <span className="remote-training-guide-step-number">2</span>
            <div><strong>Firmayı ve sektörleri seçin</strong><p>Firma / sektör alanında firmayı seçin. Örneğin Erdil Akü için <b>Ortak Temel İSG</b> ve <b>Akü-Batarya</b> kutularını işaretleyip <b>Seçilen sektörleri firmaya ata</b> düğmesine basın.</p></div>
          </li>
          <li>
            <span className="remote-training-guide-step-number">3</span>
            <div><strong>Ders kapsamını kontrol edin</strong><p>Firmaya hazırlanan programı açın. <b>Firma için sektör / ders kapsamı</b> bölümünde çalışana açılacak kapsamı kontrol edin ve <b>Firma ders kapsamını kaydet</b> düğmesine basın.</p></div>
          </li>
          <li>
            <span className="remote-training-guide-step-number">4</span>
            <div><strong>Eğitimi yayımlayın</strong><p>Videolarda hata veya <b>İşleniyor</b> durumu kalmadığını kontrol edin. Programdaki <b>Yayımla</b> düğmesine basın. Üstte <b>Eğitim yayımlandı ve çalışan atamasına açıldı</b> mesajını görmeden atama yapmayın.</p></div>
          </li>
          <li>
            <span className="remote-training-guide-step-number">5</span>
            <div><strong>Çalışan giriş hesabını hazırlayın</strong><p><b>Çalışan giriş hesabı eşleştirme</b> bölümünde hesabı olmayan personel için hesap oluşturun veya mevcut hesabı eşleştirin. Geçici parolayı güvenli kanaldan iletin; çalışan ilk girişte parolasını değiştirmelidir.</p></div>
          </li>
          <li>
            <span className="remote-training-guide-step-number">6</span>
            <div><strong>Çalışanı eğitime atayın</strong><p><b>Personel seçin ve eğitim/sınav ataması yapın</b> bölümünde personelin kutusunu işaretleyin. Sayaç 1 veya daha fazla olmalı. İsterseniz son tarih girin, sonra <b>Seçilen personele eğitim ve sınav ata</b> düğmesine basın. Aynı bölümde yeşil <b>Atama onayı</b> mesajını görün.</p></div>
          </li>
          <li>
            <span className="remote-training-guide-step-number">7</span>
            <div><strong>Çalışan videoları tamamlasın</strong><p>Çalışan kendi hesabıyla <b>Çalışan Eğitimleri</b> sayfasına girer. Kendisine atanmış tüm eğitimleri görür ve videoları ileri sarmadan, sırayla ve %100 tamamlar. Bir video bitmeden sonraki bölüm açılmaz.</p></div>
          </li>
          <li>
            <span className="remote-training-guide-step-number">8</span>
            <div><strong>Sınavı tamamlayın, katılım belgesini uzman alsın</strong><p>Tüm videolar bitince final sınavı açılır. Çalışan en az <b>%70</b> almalıdır. Başarılı sonuçtan sonra katılım belgesi oluşur; iş güvenliği uzmanı <b>Rapor</b> düğmesinden belgeyi alır ve arşivler.</p></div>
          </li>
        </ol>
        <div className="remote-training-guide-note"><strong>En önemli ayrım:</strong> Firma / sektör ataması yalnızca eğitimi o firmaya hazırlar. Çalışana eğitim başlatan işlem, aşağıdaki personel kutusunu işaretleyip <b>Seçilen personele eğitim ve sınav ata</b> düğmesine basmaktır.</div>
        <div className="remote-training-guide-links">
          <a href="#remote-training-catalog" onClick={(event) => scrollRemoteTrainingSection(event, 'remote-training-catalog')}>İçerik ve sektör seçimine git</a>
          <a href="#remote-training-assignment-manager" onClick={(event) => scrollRemoteTrainingSection(event, 'remote-training-assignment-manager')}>Çalışan atamasına git</a>
          <a href="#remote-training-employee-preview" onClick={(event) => scrollRemoteTrainingSection(event, 'remote-training-employee-preview')}>Çalışan ekranını önizle</a>
        </div>
      </div>
    </details>
  );
}

export function RemoteBasicOhsTrainingPanel({user}) {
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState('');
  const [selectedCompanyId, setSelectedCompanyId] = useState('');
  const [selectedBranchId, setSelectedBranchId] = useState('');
  const [programRefreshToken, setProgramRefreshToken] = useState(0);
  const canManage = MANAGE_ROLES.includes(user?.role);
  const canEditContent = canEditRemoteContent(user);
  const canEditSharedContent = user?.role === 'global_admin';

  useEffect(() => {
    api('/trainings/remote/meta').then(setMeta).catch((err) => setError(err.message || 'Uzaktan eğitim modülü yüklenemedi.'));
  }, []);

  if (error) return <section className="remote-training-panel remote-training-card" style={cardStyle}><ErrorText value={error} /></section>;
  if (!meta) return <section className="remote-training-panel remote-training-card" style={cardStyle}>Uzaktan eğitim modülü yükleniyor…</section>;
  if (!meta.enabled) return <section className="remote-training-panel remote-training-card" style={cardStyle}>{REMOTE_TRAINING_DISPLAY_TITLE} modülü henüz etkin değil.</section>;
  if (!canManage) {
    if (meta.can_view_employee_panel) return <div className="remote-training-panel"><EmployeePanel /></div>;
    return <section className="remote-training-panel remote-training-card" style={cardStyle}>
      <strong>Çalışan eğitimleri</strong>
      <p style={{marginBottom: 0, color: '#5e7485'}}>Bu hesapta görüntülenecek bir çalışan eğitimi bulunmuyor veya erişim henüz eşleştirilmedi.</p>
    </section>;
  }
  return <div className="remote-training-panel" style={{display: 'grid', gap: 16}}>
    <div className="remote-training-guide-launcher" role="region" aria-label="Uzaktan eğitim başlangıç rehberi">
      <div className="remote-training-guide-launcher-content">
        <span className="remote-training-guide-kicker">UZMAN EKRANI · HIZLI BAŞLANGIÇ</span>
        <strong>Uzaktan eğitimi başlatmak için adım adım ilerleyin</strong>
        <span>Video yükleme, firma kapsamı, çalışan ataması, sınav ve katılım belgesi arşivi tek rehberde.</span>
      </div>
      <a className="remote-training-guide-launcher-link" href="#remote-training-guide" onClick={(event) => scrollRemoteTrainingSection(event, 'remote-training-guide')}>
        <span aria-hidden="true">✦</span><span>Adım adım rehberi aç</span><span aria-hidden="true">↓</span>
      </a>
    </div>
    <RemoteTrainingGuide />
    <RemoteCertificateHub />
    <div className="remote-training-flow" aria-label="Uzaktan eğitim yaşam döngüsü">
      <a className="remote-training-flow-item" href="#remote-training-catalog" onClick={(event) => scrollRemoteTrainingSection(event, 'remote-training-catalog')}><span>1</span><div><strong>Video ekle</strong><small>Paketi seçin, videoları bölümlere yükleyin.</small></div></a>
      <a className="remote-training-flow-item" href="#remote-training-catalog" onClick={(event) => scrollRemoteTrainingSection(event, 'remote-training-catalog')}><span>2</span><div><strong>Firma / işyeri seç</strong><small>Eğitim kutucuklarını işaretleyip hazırlayın.</small></div></a>
      <a className="remote-training-flow-item" href="#remote-training-assignment-manager" onClick={(event) => scrollRemoteTrainingSection(event, 'remote-training-assignment-manager')}><span>3</span><div><strong>Personel ata</strong><small>Giriş hesabını eşleyip programı atayın.</small></div></a>
      <a className="remote-training-flow-item" href="#remote-training-employee-preview" onClick={(event) => scrollRemoteTrainingSection(event, 'remote-training-employee-preview')}><span>4</span><div><strong>Çalışan tamamlasın</strong><small>%100 video + sınavda en az %70.</small></div></a>
      <a className="remote-training-flow-item" href="#remote-training-certificate-hub" onClick={(event) => scrollRemoteTrainingSection(event, 'remote-training-certificate-hub')}><span>5</span><div><strong>Belgeyi al</strong><small>Başarılı çalışanın PDF belgesini indirin.</small></div></a>
    </div>
    {canManage && <div id="remote-training-catalog"><CatalogManagerPanel companyId={selectedCompanyId} branchId={selectedBranchId} onCompanyChange={(value) => { setSelectedCompanyId(value); setSelectedBranchId(''); }} onBranchChange={setSelectedBranchId} onPrepared={() => setProgramRefreshToken((value) => value + 1)} rollout={meta.strict_policy} canEditContent={canEditContent} canEditSharedContent={canEditSharedContent} /></div>}
    {canManage && <details open id="remote-training-assignment-manager">
      <summary style={{cursor: 'pointer', fontWeight: 800, color: '#123b59', padding: '8px 2px'}}>Firma eğitim atama ve çalışan takip yönetimi</summary>
      <div style={{marginTop: 12}}><ManagerPanel user={user} initialCompanyId={selectedCompanyId} initialBranchId={selectedBranchId} onCompanyChange={(value) => { setSelectedCompanyId(value); setSelectedBranchId(''); }} onBranchChange={setSelectedBranchId} refreshToken={programRefreshToken} canEditContent={canEditContent} /></div>
    </details>}
    {canManage && <details className="remote-training-employee-preview" id="remote-training-employee-preview">
      <summary style={{cursor: 'pointer', fontWeight: 800, color: '#123b59', padding: '8px 2px'}}>Çalışan ekranı önizlemesi / kendi eğitimlerim</summary>
      <div style={{marginTop: 12}}><EmployeePanel /></div>
    </details>}
  </div>;
}
