import React, {Component, useEffect, useMemo, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {ArrowRight, ChevronRight, CircleHelp, Compass, Loader2, MessageCircle, Mic, Send, ShieldCheck, Sparkles, Square, Target, Volume2, VolumeX, X} from 'lucide-react';
import {api} from './api';
import {assistantFeatureEnabled, getAssistantPageContext, getAssistantPageDefinition} from './contextual_assistant_registry';
import './contextual_assistant.css';

export function highlightTarget(targetId) { if (!targetId || typeof document === 'undefined') return false; const target = document.querySelector(`[data-ai-action="${String(targetId).replace(/"/g, '\\"')}"]`); if (!target) return false; target.classList.remove('ai-assistant-target-highlight'); void target.offsetWidth; target.classList.add('ai-assistant-target-highlight'); target.scrollIntoView?.({behavior: 'smooth', block: 'center'}); window.setTimeout(() => target.classList.remove('ai-assistant-target-highlight'), 4200); return true; }
function OhsCharacter({state = 'idle', compact = false}) { return <div className={`ohs-character ohs-character--${state}${compact ? ' ohs-character--compact' : ''}`} aria-hidden="true"><div className="ohs-character__helmet"><span /></div><div className="ohs-character__head"><i /><b /><em /></div><div className="ohs-character__vest"><span /><strong /><small /></div><div className="ohs-character__clipboard" /></div>; }
function actionLabel(action) { return action?.label || (action?.type === 'navigate' ? 'Beni oraya götür' : 'Bana göster'); }
class AssistantErrorBoundary extends Component { constructor(props) { super(props); this.state = {failed: false}; } static getDerivedStateFromError() { return {failed: true}; } render() { return this.state.failed ? null : this.props.children; } }

export function browserSpeechRecognition(scope = typeof window === 'undefined' ? null : window) {
  return scope?.SpeechRecognition || scope?.webkitSpeechRecognition || null;
}

export function speechRecognitionErrorMessage(code) {
  if (code === 'not-allowed' || code === 'service-not-allowed') return 'Mikrofon izni verilmedi. Adres çubuğundaki kilit simgesinden bu site için mikrofona izin verin.';
  if (code === 'audio-capture') return 'Mikrofon bulunamadı veya başka bir uygulama tarafından kullanılıyor.';
  if (code === 'network') return 'Tarayıcının ses tanıma servisine ulaşılamadı. İnternet bağlantınızı kontrol edip tekrar deneyin.';
  if (code === 'no-speech') return 'Ses algılanamadı. Mikrofona daha yakın konuşup tekrar deneyin.';
  return 'Sesli soru alınamadı. Sorunuzu yazabilirsiniz.';
}

export function firstAutoAction(actions, allowedModules = []) {
  return (Array.isArray(actions) ? actions : []).find((action) => {
    if (!action?.autoExecute) return false;
    if (action.type === 'show' && action.targetId) return true;
    if (action.type === 'navigate' && action.moduleId && allowedModules.includes(action.moduleId)) return true;
    return false;
  }) || null;
}

export function spokenReply(result) {
  const spoken = String(result?.spoken || '').trim();
  if (spoken) return spoken;
  return String(result?.message || '').trim();
}

export function isCoarsePointer(scope = typeof window === 'undefined' ? null : window) {
  return Boolean(scope?.matchMedia?.('(pointer: coarse)').matches);
}

export function autoActionDelayMs({fromVoice = false, coarsePointer = false} = {}) {
  if (coarsePointer) return 650;
  return fromVoice ? 1200 : 350;
}

export function pickTurkishVoice(voices = []) {
  return (Array.isArray(voices) ? voices : []).find((voice) => String(voice?.lang || '').toLowerCase().startsWith('tr')) || null;
}

export function unlockSpeechSynthesis(scope = typeof window === 'undefined' ? null : window) {
  const synthesis = scope?.speechSynthesis;
  if (!synthesis || typeof scope.SpeechSynthesisUtterance !== 'function') return false;
  try {
    const utterance = new scope.SpeechSynthesisUtterance(' ');
    utterance.volume = 0;
    utterance.rate = 1;
    utterance.lang = 'tr-TR';
    synthesis.speak(utterance);
    return true;
  } catch {
    return false;
  }
}

export function shouldUseBrowserSpeech(scope = typeof window === 'undefined' ? null : window) {
  return Boolean(browserSpeechRecognition(scope));
}

export function isTranscriptionUnavailable(message) {
  return /sesli soru servisi|kullanılamıyor|transcri/i.test(String(message || ''));
}

function Panel({active, user, allowedModules, onNavigate}) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [characterState, setCharacterState] = useState('idle');
  const [voiceOutput, setVoiceOutput] = useState(true);
  const [listening, setListening] = useState(false);
  const [voiceInputSupported, setVoiceInputSupported] = useState(false);
  const abortRef = useRef(null);
  const recognitionRef = useRef(null);
  const recorderRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const audioChunksRef = useRef([]);
  const voiceTimerRef = useRef(null);
  const voiceCancelledRef = useRef(false);
  const pendingSpeechRef = useRef(null);
  const speechUnlockedRef = useRef(false);
  const listRef = useRef(null);
  const lastPageRef = useRef(active);
  const page = useMemo(() => getAssistantPageDefinition(active), [active]);

  useEffect(() => {
    const supported = typeof window !== 'undefined'
      && typeof navigator !== 'undefined'
      && Boolean(browserSpeechRecognition(window) || (navigator.mediaDevices?.getUserMedia && window.MediaRecorder));
    setVoiceInputSupported(supported);
    return () => {
      voiceCancelledRef.current = true;
      const recognition = recognitionRef.current;
      recognitionRef.current = null;
      if (recognition) {
        recognition.onresult = null;
        recognition.onerror = null;
        recognition.onend = null;
        try { recognition.abort(); } catch { /* ignore */ }
      }
      const recorder = recorderRef.current;
      if (recorder && recorder.state !== 'inactive') {
        try { recorder.stop(); } catch { /* ignore */ }
      }
      if (voiceTimerRef.current) window.clearTimeout(voiceTimerRef.current);
      mediaStreamRef.current?.getTracks?.().forEach((track) => track.stop());
      mediaStreamRef.current = null;
      window.speechSynthesis?.cancel?.();
    };
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const timer = window.setTimeout(() => setCharacterState('idle'), 850);
    setCharacterState('pointing');
    return () => window.clearTimeout(timer);
  }, [active, open]);

  useEffect(() => {
    if (!open || lastPageRef.current === active) return;
    lastPageRef.current = active;
    setMessages((current) => [...current, {role: 'assistant', text: `Sayfa değişti: artık ${page.title} ekranındasınız. Önceki yanıtlar önceki sayfanın bağlamındaydı.`}]);
  }, [active, open, page.title]);

  useEffect(() => {
    listRef.current?.scrollTo({top: listRef.current.scrollHeight, behavior: 'smooth'});
  }, [messages, busy]);

  useEffect(() => () => abortRef.current?.abort(), []);

  if (!assistantFeatureEnabled() || !user || !active) return null;

  function openPanel() {
    setOpen(true);
    setError('');
    setMessages((current) => current.length ? current : [{role: 'assistant', text: `Merhaba, ${page.title} sayfasındasınız. ${page.purpose} Bu ekranda ne yapmak istediğinizi yazın; mevcut sayfaya göre yönlendireyim.`}]);
  }

  function clearVoiceResources() {
    if (voiceTimerRef.current) window.clearTimeout(voiceTimerRef.current);
    voiceTimerRef.current = null;
    mediaStreamRef.current?.getTracks?.().forEach((track) => track.stop());
    mediaStreamRef.current = null;
    recorderRef.current = null;
    audioChunksRef.current = [];
  }

  function stopVoiceCapture({cancel = false} = {}) {
    if (cancel) voiceCancelledRef.current = true;
    const recognition = recognitionRef.current;
    if (recognition) {
      if (cancel) {
        recognition.onresult = null;
        recognition.onerror = null;
        recognition.onend = null;
        recognitionRef.current = null;
      }
      try { cancel ? recognition.abort() : recognition.stop(); } catch { recognitionRef.current = null; }
      return;
    }
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      try { recorder.stop(); } catch { clearVoiceResources(); }
    } else {
      clearVoiceResources();
    }
  }

  function closePanel({cancelSpeech = true} = {}) {
    abortRef.current?.abort();
    stopVoiceCapture({cancel: true});
    if (cancelSpeech) {
      pendingSpeechRef.current = null;
      window.speechSynthesis?.cancel?.();
    }
    setOpen(false);
    setBusy(false);
    setListening(false);
    setCharacterState('idle');
  }

  function unlockVoiceOutput() {
    if (speechUnlockedRef.current || typeof window === 'undefined') return;
    speechUnlockedRef.current = unlockSpeechSynthesis(window);
  }

  function speak(text, {onEnd, force = false} = {}) {
    const finish = () => { onEnd?.(); };
    if ((!voiceOutput && !force) || typeof window === 'undefined' || !window.speechSynthesis || !text) {
      finish();
      return;
    }
    window.speechSynthesis.cancel();
    const token = {};
    pendingSpeechRef.current = token;
    const utterance = new SpeechSynthesisUtterance(String(text));
    utterance.lang = 'tr-TR';
    utterance.rate = 0.95;
    const turkishVoice = pickTurkishVoice(window.speechSynthesis.getVoices?.() || []);
    if (turkishVoice) utterance.voice = turkishVoice;
    utterance.onstart = () => setCharacterState('speaking');
    const complete = () => {
      if (pendingSpeechRef.current !== token) return;
      pendingSpeechRef.current = null;
      window.clearTimeout(watchdog);
      setCharacterState('idle');
      finish();
    };
    const watchdog = window.setTimeout(complete, Math.min(7000, Math.max(1600, String(text).length * 70)));
    utterance.onend = complete;
    utterance.onerror = complete;
    window.speechSynthesis.speak(utterance);
  }

  async function toggleListening() {
    if (!voiceInputSupported || typeof window === 'undefined' || typeof navigator === 'undefined') {
      setError('Bu cihazda sesli soru alınamıyor. Sorunuzu yazabilirsiniz.');
      return;
    }
    if (listening) {
      stopVoiceCapture();
      return;
    }

    unlockVoiceOutput();
    voiceCancelledRef.current = false;
    setError('');
    if (startBrowserRecognition()) return;
    await startServerRecording();
  }

  function startBrowserRecognition({retry = 0} = {}) {
    const Recognition = browserSpeechRecognition(window);
    if (!Recognition) return false;
    const recognition = new Recognition();
    let completed = false;
    let failed = false;
    let stopping = false;
    recognition.lang = 'tr-TR';
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.maxAlternatives = 3;
    recognitionRef.current = recognition;
    recognition.onstart = () => {
      setListening(true);
      setCharacterState('listening');
    };
    recognition.onresult = (event) => {
      let transcript = '';
      const results = event.results || [];
      for (let index = 0; index < results.length; index += 1) {
        const result = results[index];
        if (result?.isFinal) transcript += String(result?.[0]?.transcript || '');
      }
      transcript = transcript.trim() || String(results?.[0]?.[0]?.transcript || '').trim();
      if (!transcript || voiceCancelledRef.current) return;
      completed = true;
      recognitionRef.current = null;
      setListening(false);
      setInput('');
      void sendQuestion(transcript, {fromVoice: true});
    };
    recognition.onerror = (event) => {
      const code = String(event?.error || '');
      if (voiceCancelledRef.current) {
        failed = true;
        recognitionRef.current = null;
        setListening(false);
        return;
      }
      if (code === 'no-speech' && retry < 2) {
        recognitionRef.current = null;
        window.setTimeout(() => startBrowserRecognition({retry: retry + 1}), 120);
        return;
      }
      failed = true;
      recognitionRef.current = null;
      setListening(false);
      if ((code === 'network' || code === 'service-not-allowed') && navigator.mediaDevices?.getUserMedia && window.MediaRecorder) {
        void startServerRecording();
        return;
      }
      setCharacterState('warning');
      setError(speechRecognitionErrorMessage(code));
    };
    recognition.onend = () => {
      if (recognitionRef.current === recognition) recognitionRef.current = null;
      if (completed || failed || stopping || voiceCancelledRef.current) {
        if (!completed) setListening(false);
        return;
      }
      if (retry < 2) {
        startBrowserRecognition({retry: retry + 1});
        return;
      }
      setListening(false);
      setCharacterState('warning');
      setError('Ses algılanamadı. Mikrofon düğmesine basıp tekrar konuşun.');
    };
    const stop = recognition.stop.bind(recognition);
    recognition.stop = () => {
      stopping = true;
      stop();
    };
    try {
      recognition.start();
      return true;
    } catch {
      recognitionRef.current = null;
      return false;
    }
  }

  async function startServerRecording() {
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({audio: true});
      if (voiceCancelledRef.current) {
        stream.getTracks?.().forEach((track) => track.stop());
        return;
      }
      const mimeType = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/ogg',
      ].find((type) => !window.MediaRecorder.isTypeSupported || window.MediaRecorder.isTypeSupported(type));
      const recorder = new window.MediaRecorder(stream, mimeType ? {mimeType} : undefined);
      const recordedType = mimeType || recorder.mimeType || 'audio/webm';
      mediaStreamRef.current = stream;
      audioChunksRef.current = [];
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data?.size) audioChunksRef.current.push(event.data);
      };
      recorder.onerror = () => {
        voiceCancelledRef.current = true;
        clearVoiceResources();
        setListening(false);
        setCharacterState('warning');
        setError('Mikrofon kaydı alınamadı. Sorunuzu yazabilirsiniz.');
      };
      recorder.onstop = async () => {
        const blob = new Blob(audioChunksRef.current, {type: recorder.mimeType || recordedType});
        const cancelled = voiceCancelledRef.current;
        clearVoiceResources();
        setListening(false);
        if (cancelled) return;
        if (!blob.size) {
          setCharacterState('warning');
          setError('Ses kaydı boş geldi. Daha sonra tekrar deneyin veya sorunuzu yazın.');
          return;
        }

        setCharacterState('thinking');
        const extension = recordedType.includes('ogg') ? 'ogg' : recordedType.includes('mp4') ? 'm4a' : 'webm';
        const formData = new FormData();
        formData.append('file', blob, `voice.${extension}`);
        try {
          const result = await api('/assistant/transcribe', {
            method: 'POST',
            body: formData,
            timeoutMs: 60000,
            _retries: 0,
          });
          const transcript = String(result?.text || '').trim();
          if (!transcript) throw new Error('Ses çözümlenemedi. Sorunuzu yazabilirsiniz.');
          setInput('');
          setError('');
          void sendQuestion(transcript, {fromVoice: true});
        } catch (exception) {
          const message = String(exception?.message || '');
          if (isTranscriptionUnavailable(message) && startBrowserRecognition()) return;
          setError(isTranscriptionUnavailable(message)
            ? 'Sesli soru servisi hazır değil. Mikrofon düğmesine basıp tekrar konuşun veya sorunuzu yazın.'
            : (message || 'Sesli soru alınamadı. Sorunuzu yazabilirsiniz.'));
          setCharacterState('warning');
        }
      };
      recorder.start(250);
      setListening(true);
      setCharacterState('listening');
      voiceTimerRef.current = window.setTimeout(() => {
        if (recorderRef.current === recorder && recorder.state === 'recording') recorder.stop();
      }, isCoarsePointer(window) ? 12000 : 30000);
    } catch (exception) {
      stream?.getTracks?.().forEach((track) => track.stop());
      clearVoiceResources();
      setListening(false);
      setCharacterState('warning');
      const code = String(exception?.name || '');
      setError(code === 'NotAllowedError'
        ? 'Mikrofon izni verilmedi. Adres çubuğundaki kilit simgesinden bu site için mikrofona izin verin.'
        : code === 'NotFoundError'
          ? 'Mikrofon bulunamadı. Cihaz mikrofonunu kontrol edip tekrar deneyin.'
          : 'Mikrofon başlatılamadı. Sorunuzu yazabilirsiniz.');
    }
  }

  async function sendQuestion(question = input, options = {}) {
    const text = String(question || '').trim();
    if (!text || busy) return;
    const fromVoice = Boolean(options.fromVoice);
    setInput('');
    setError('');
    setMessages((current) => [...current, {role: 'user', text}]);
    setBusy(true);
    setCharacterState('thinking');
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const result = await api('/assistant/contextual', {
        method: 'POST',
        body: JSON.stringify({question: text, context: getAssistantPageContext(active, user, allowedModules)}),
        timeoutMs: 30000,
        _retries: 0,
        signal: controller.signal,
      });
      const responseText = result?.message || 'Bu işlem için doğrulanmış bir açıklama bulunamadı.';
      const speechText = spokenReply(result) || responseText;
      const autoAction = firstAutoAction(result?.actions, allowedModules);
      setMessages((current) => [...current, {role: 'assistant', text: responseText, source: result?.source, actions: result?.actions || []}]);
      setCharacterState('speaking');
      speak(speechText, {force: fromVoice});
      if (autoAction) {
        window.setTimeout(() => {
          runAction(autoAction, {auto: true});
        }, autoActionDelayMs({fromVoice, coarsePointer: isCoarsePointer(window)}));
      }
    } catch (exception) {
      if (exception?.name !== 'AbortError') {
        setError('Asistan geçici olarak kullanılamıyor. Uygulamayı normal şekilde kullanmaya devam edebilirsiniz.');
        setCharacterState('warning');
      }
    } finally {
      abortRef.current = null;
      setBusy(false);
    }
  }

  function runAction(action, {auto = false} = {}) {
    let moved = false;
    if (action?.type === 'show') {
      if (action.moduleId && action.moduleId !== active && allowedModules.includes(action.moduleId)) {
        onNavigate?.(action.moduleId);
        window.setTimeout(() => highlightTarget(action.targetId), 450);
        setCharacterState('success');
        moved = true;
      } else if (!highlightTarget(action.targetId)) {
        setError('Bu hedef mevcut sayfada şu anda görünür değil.');
      } else {
        setCharacterState('pointing');
        moved = true;
      }
    } else if (action?.type === 'navigate' && allowedModules.includes(action.moduleId)) {
      onNavigate?.(action.moduleId);
      setCharacterState('success');
      moved = true;
    }
    if (moved && (auto || isCoarsePointer(window))) closePanel({cancelSpeech: false});
  }

  return <>
    <button type="button" className="contextual-assistant-launcher" onClick={() => { unlockVoiceOutput(); openPanel(); }} aria-label="İSG Asistanını aç" aria-expanded={open}>
      <OhsCharacter state="idle" compact />
      <span className="contextual-assistant-launcher__badge"><Sparkles size={12} /></span>
    </button>
    {open && <>
      <button type="button" className="contextual-assistant-backdrop" onClick={closePanel} aria-label="İSG Asistanını kapat" />
      <aside className="contextual-assistant-panel" role="dialog" aria-modal="true" aria-labelledby="contextual-assistant-title">
        <header className="contextual-assistant-head">
          <div className="contextual-assistant-head__identity">
            <OhsCharacter state={characterState} compact />
            <div><span className="contextual-assistant-eyebrow"><ShieldCheck size={13} /> İSG rehberliği</span><h2 id="contextual-assistant-title">İSG Asistanı</h2><p>Doğrulanmış uygulama yardımı</p></div>
          </div>
          <button type="button" className="contextual-assistant-close" onClick={closePanel} aria-label="İSG Asistanını kapat"><X size={19} /></button>
        </header>
        <div className="contextual-assistant-context" role="status"><Compass size={16} /><span>Şu an: <strong>{page.title}</strong><small>{page.purpose}</small></span></div>
        <div className="contextual-assistant-messages" ref={listRef} aria-live="polite">
          {messages.map((message, index) => <article key={`${message.role}-${index}`} className={`contextual-assistant-message contextual-assistant-message--${message.role}`}>
            <div className="contextual-assistant-message__icon">{message.role === 'assistant' ? <Sparkles size={14} /> : <MessageCircle size={14} />}</div>
            <div><p>{message.text}</p>{message.source && <small className="contextual-assistant-source">{message.source === 'ai' ? 'AI + uygulama bağlamı' : 'Doğrulanmış uygulama bilgisi'}</small>}{message.actions?.length > 0 && <div className="contextual-assistant-actions">{message.actions.map((action, actionIndex) => <button type="button" key={`${action.type}-${actionIndex}`} onClick={() => runAction(action)}><Target size={14} />{actionLabel(action)}<ChevronRight size={13} /></button>)}</div>}</div>
          </article>)}
          {busy && <div className="contextual-assistant-thinking"><OhsCharacter state="thinking" compact /><span>Sayfayı ve izinlerinizi kontrol ediyorum<Loader2 size={14} /></span></div>}
        </div>
        <div className="contextual-assistant-suggestions"><span><CircleHelp size={14} /> Önerilen sorular</span><div>{page.suggestions.slice(0, 3).map((question) => <button type="button" key={question} onClick={() => void sendQuestion(question)} disabled={busy}>{question}<ArrowRight size={13} /></button>)}</div></div>
        {error && <div className="contextual-assistant-error" role="alert">{error}</div>}
        <form className="contextual-assistant-composer" onSubmit={(event) => { event.preventDefault(); void sendQuestion(); }}>
          <label htmlFor="contextual-assistant-input" className="sr-only">İSG Asistanına soru yazın</label>
          <textarea id="contextual-assistant-input" value={input} onChange={(event) => { setInput(event.target.value); setCharacterState(event.target.value ? 'listening' : 'idle'); }} placeholder="Bu sayfada ne yapmak istiyorsunuz?" rows={2} maxLength={2000} disabled={busy || listening} />
          <div className="contextual-assistant-voice-actions">
            <button type="button" className={`contextual-assistant-voice-button${listening ? ' is-active' : ''}`} onClick={() => void toggleListening()} disabled={busy || !voiceInputSupported} aria-label={listening ? 'Sesli soru kaydı durdur' : 'Sesli soru kaydı başlat'} title={voiceInputSupported ? (listening ? 'Kaydı durdur' : 'Sesli soru sor') : 'Bu cihazda mikrofon kaydı desteklenmiyor'}>{listening ? <Square size={17} /> : <Mic size={17} />}</button>
            <button type="button" className={`contextual-assistant-voice-button${voiceOutput ? ' is-active' : ''}`} onClick={() => { setVoiceOutput((current) => !current); if (voiceOutput) window.speechSynthesis?.cancel?.(); }} aria-label={voiceOutput ? 'Sesli yanıtı kapat' : 'Sesli yanıtı aç'} title="Sesli yanıtı aç/kapat">{voiceOutput ? <Volume2 size={17} /> : <VolumeX size={17} />}</button>
            <button type="submit" aria-label="Soruyu gönder" disabled={busy || listening || !input.trim()}>{busy ? <Loader2 className="contextual-assistant-spin" size={18} /> : <Send size={18} />}</button>
          </div>
        </form>
        <footer className="contextual-assistant-footnote">{voiceInputSupported ? (listening ? 'Dinliyorum. Bitince mikrofon düğmesine tekrar dokunun.' : 'Mikrofonu açıp söyleyin; asistan teyit eder ve yetkiniz olan sayfayı açar.') : 'Bu cihazda mikrofon kullanılamıyor; yazılı asistan kullanılabilir.'} Sunucu kaydı kullanılırsa ses saklanmaz.</footer>
      </aside>
    </>}
  </>;
}
export function ContextualAssistant(props) {
  const assistant = <AssistantErrorBoundary><Panel {...props} /></AssistantErrorBoundary>;
  return typeof document === 'undefined' ? assistant : createPortal(assistant, document.body);
}
