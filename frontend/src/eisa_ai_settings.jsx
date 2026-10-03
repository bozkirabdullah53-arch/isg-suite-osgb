import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, Eye, EyeOff, KeyRound, RotateCcw, Sparkles, TestTube2 } from 'lucide-react';
import { api } from './api';
import { Msg, Page, RefreshButton } from './eisa.jsx';

function providerMap(catalog) {
  return Object.fromEntries((Array.isArray(catalog) ? catalog : []).map((item) => [item.id, item]));
}

function sourceLabel(source) {
  return source === 'global_panel' ? 'EİSA Global paneli' : 'Mevcut sunucu / environment ayarı';
}

export function EisaAiSettingsPage() {
  const [settings, setSettings] = useState(null);
  const [form, setForm] = useState(null);
  const [apiKey, setApiKey] = useState('');
  const [clearApiKey, setClearApiKey] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [testResult, setTestResult] = useState(null);

  const catalog = useMemo(() => providerMap(settings?.provider_catalog), [settings]);

  function syncForm(data) {
    setSettings(data);
    setForm({
      enabled: Boolean(data?.enabled),
      provider: data?.provider || 'heuristic',
      model: data?.model || '',
      base_url: data?.base_url || '',
      timeout_sec: Number(data?.timeout_sec || 30),
    });
    setApiKey('');
    setClearApiKey(false);
  }

  const load = async () => {
    setBusy(true);
    setMsg('');
    try {
      const data = await api('/eisa/ai-settings');
      syncForm(data);
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { void load(); }, []);

  function chooseProvider(provider) {
    const meta = catalog[provider] || {};
    setForm((prev) => ({
      ...prev,
      provider,
      base_url: provider === 'custom_openai'
        ? (prev?.provider === 'custom_openai' ? prev.base_url : '')
        : (meta.base_url || ''),
      model: meta.default_model || (provider === prev?.provider ? prev.model : ''),
    }));
    setApiKey('');
    setClearApiKey(false);
    setTestResult(null);
  }

  async function save(e) {
    e.preventDefault();
    if (!form) return;
    setBusy(true);
    setMsg('');
    setTestResult(null);
    try {
      const body = {
        enabled: Boolean(form.enabled),
        provider: form.provider,
        model: form.model || null,
        base_url: form.base_url || null,
        timeout_sec: Number(form.timeout_sec || 30),
        clear_api_key: Boolean(clearApiKey),
      };
      if (apiKey.trim()) body.api_key = apiKey.trim();
      const data = await api('/eisa/ai-settings', {
        method: 'PUT',
        body: JSON.stringify(body),
      });
      syncForm(data);
      setMsg('Ayarlar kaydedildi ve aktif edildi. Bu ekrandan istediğiniz zaman tekrar değiştirebilirsiniz.');
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function testConnection() {
    setBusy(true);
    setMsg('');
    setTestResult(null);
    try {
      const result = await api('/eisa/ai-settings/test', { method: 'POST' });
      setTestResult(result);
      setMsg(result?.message || 'Bağlantı testi başarılı.');
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function resetToEnvironment() {
    if (!window.confirm(
      'Global paneldeki AI yönlendirme ayarları kaldırılsın ve uygulama mevcut sunucu/environment ayarlarına dönsün mü?\n\nÇalışan risk kayıtları, fotoğraflar ve raporlar silinmez.',
    )) return;
    setBusy(true);
    setMsg('');
    setTestResult(null);
    try {
      const data = await api('/eisa/ai-settings/reset', { method: 'POST' });
      syncForm(data);
      setMsg('Global AI panel ayarları kaldırıldı; mevcut sunucu ayarlarına dönüldü.');
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!settings || !form) {
    return <Page title="Yapay Zekâ Yönetimi"><p>Yükleniyor…</p></Page>;
  }

  const selected = catalog[form.provider] || {};
  const requiresKey = Boolean(selected.requires_api_key);
  const selectedKeyConfigured = Boolean(selected.api_key_configured);
  const fixedBase = form.provider !== 'custom_openai' && !['heuristic', 'yolo'].includes(form.provider);
  const localProvider = ['heuristic', 'yolo'].includes(form.provider);

  return (
    <Page
      title="Yapay Zekâ Yönetimi"
      action={<RefreshButton busy={busy} onClick={load} />}
    >
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
        gap: 12,
        marginBottom: 18,
      }}>
        <article className="metric">
          <span>Yönetim kaynağı</span>
          <strong>{sourceLabel(settings.source)}</strong>
        </article>
        <article className="metric">
          <span>Aktif sağlayıcı</span>
          <strong>{catalog[settings.provider]?.label || settings.provider}</strong>
        </article>
        <article className="metric">
          <span>Aktif sağlayıcı anahtarı</span>
          <strong>{settings.api_key_configured ? 'Güvenli kayıtlı / mevcut' : 'Kayıtlı değil'}</strong>
        </article>
        <article className="metric">
          <span>Çalışma durumu</span>
          <strong>{settings.force_off ? 'Acil kapatma aktif' : (settings.ready ? 'Hazır' : 'Hazır değil')}</strong>
        </article>
      </div>

      <div style={{
        padding: 14,
        border: '1px solid #bfdbfe',
        background: '#eff6ff',
        borderRadius: 12,
        marginBottom: 18,
      }}>
        <strong>Bu ayarları istediğiniz zaman değiştirebilirsiniz.</strong>
        <p style={{ margin: '6px 0 0', color: '#475569' }}>
          Sağlayıcı, model, API adresi, zaman aşımı ve kullanım durumunu değiştirip yeniden “Kaydet”
          diyebilirsiniz. Kaydettiğiniz yeni değerler sonraki AI çağrılarında geçerli olur. API anahtarı
          güvenlik nedeniyle ekranda geri gösterilmez; alanı boş bırakırsanız seçili sağlayıcının kayıtlı
          anahtarı korunur, yeni anahtar girerseniz güvenli biçimde güncellenir.
        </p>
        {!settings.managed && (
          <p style={{ margin: '6px 0 0', color: '#475569' }}>
            İlk kayda kadar mevcut AI/environment ayarları aynen çalışmaya devam eder.
          </p>
        )}
      </div>

      {settings.force_off && (
        <div className="error" style={{ marginBottom: 18 }}>
          Sunucudaki VISION_ANALYSIS_FORCE_OFF acil kapatma anahtarı aktif. Paneldeki seçimler
          kaydedilebilir ancak bu anahtar kaldırılmadan dış AI analizi çalışmaz.
        </div>
      )}

      <Msg text={msg} />

      <form className="form-grid" onSubmit={save} style={{ maxWidth: 760 }}>
        <label className="field" style={{ gridColumn: '1 / -1' }}>
          <span>Yapay zekâ kullanım durumu</span>
          <select
            value={form.enabled ? 'on' : 'off'}
            onChange={(e) => setForm({ ...form, enabled: e.target.value === 'on' })}
          >
            <option value="on">Aktif — son kullanıcı seçilen AI'ı kullanır</option>
            <option value="off">Pasif — fotoğraf AI analizi kapalı</option>
          </select>
        </label>

        <label className="field">
          <span>Sağlayıcı</span>
          <select value={form.provider} onChange={(e) => chooseProvider(e.target.value)}>
            {(settings.provider_catalog || []).map((item) => (
              <option key={item.id} value={item.id}>{item.label}</option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Model</span>
          <input
            value={form.model}
            disabled={localProvider}
            placeholder={selected.default_model || 'örn. sağlayıcı model adı'}
            onChange={(e) => setForm({ ...form, model: e.target.value })}
          />
        </label>

        <label className="field" style={{ gridColumn: '1 / -1' }}>
          <span>API Base URL</span>
          <input
            value={form.base_url}
            disabled={fixedBase || localProvider}
            placeholder={form.provider === 'custom_openai' ? 'https://api.saglayici.com/v1' : ''}
            onChange={(e) => setForm({ ...form, base_url: e.target.value })}
          />
          {fixedBase && (
            <small style={{ color: '#64748b' }}>
              Güvenlik için bu sağlayıcının resmi API adresi sabittir.
            </small>
          )}
        </label>

        <label className="field" style={{ gridColumn: '1 / -1' }}>
          <span>API anahtarı {requiresKey ? '*' : ''}</span>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              type={showApiKey ? 'text' : 'password'}
              value={apiKey}
              disabled={!requiresKey}
              autoComplete="new-password"
              placeholder={
                requiresKey
                  ? (selectedKeyConfigured
                    ? 'Yeni anahtar girmezseniz bu sağlayıcının mevcut şifreli anahtarı korunur'
                    : 'Bu sağlayıcıya ait API anahtarını buraya girin')
                  : 'Bu sağlayıcı API anahtarı kullanmaz'
              }
              onChange={(e) => {
                setApiKey(e.target.value);
                if (e.target.value) setClearApiKey(false);
              }}
            />
            <button
              type="button"
              className="secondary"
              disabled={!requiresKey}
              title={showApiKey ? 'Anahtarı gizle' : 'Anahtarı göster'}
              onClick={() => setShowApiKey((v) => !v)}
            >
              {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          <small style={{ color: '#64748b' }}>
            Her sağlayıcının anahtarı ayrı tutulur. Anahtar yalnızca backend'e gönderilir,
            şifreli saklanır ve kayıt sonrası tekrar tarayıcıya gönderilmez.
          </small>
        </label>

        {requiresKey && selectedKeyConfigured && (
          <div className="field" style={{ gridColumn: '1 / -1' }}>
            <span>Bu sağlayıcının mevcut anahtarı</span>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={clearApiKey}
                onChange={(e) => setClearApiKey(e.target.checked)}
                style={{ width: 18, height: 18 }}
              />
              <span>Kaydedilmiş API anahtarını sil</span>
            </label>
          </div>
        )}

        <label className="field">
          <span>Zaman aşımı (saniye)</span>
          <input
            type="number"
            min="5"
            max="120"
            value={form.timeout_sec}
            onChange={(e) => setForm({ ...form, timeout_sec: e.target.value })}
          />
        </label>

        <div className="field">
          <span>Güvenli fallback</span>
          <div style={{
            minHeight: 42,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            color: '#475569',
          }}>
            <CheckCircle2 size={18} />
            Dış API hata verirse mevcut heuristik analiz korunur.
          </div>
        </div>

        <div className="form-actions" style={{ gridColumn: '1 / -1', gap: 8, flexWrap: 'wrap' }}>
          <button type="submit" disabled={busy}>
            <KeyRound size={16} /> Kaydet
          </button>
          <button
            type="button"
            className="secondary"
            disabled={busy || !settings.managed}
            onClick={testConnection}
          >
            <TestTube2 size={16} /> Bağlantıyı Test Et
          </button>
          <button
            type="button"
            className="secondary"
            disabled={busy || !settings.managed}
            onClick={resetToEnvironment}
          >
            <RotateCcw size={16} /> Sunucu Ayarlarına Dön
          </button>
        </div>
      </form>

      {testResult && (
        <div style={{
          marginTop: 18,
          padding: 14,
          border: '1px solid #bbf7d0',
          background: '#f0fdf4',
          borderRadius: 12,
        }}>
          <strong>Bağlantı başarılı</strong>
          <p style={{ margin: '6px 0 0', color: '#475569' }}>
            {catalog[testResult.provider]?.label || testResult.provider}
            {testResult.model ? ` · ${testResult.model}` : ''}
            {Number.isFinite(testResult.latency_ms) ? ` · ${testResult.latency_ms} ms` : ''}
          </p>
        </div>
      )}

      <div style={{
        marginTop: 24,
        paddingTop: 18,
        borderTop: '1px solid #dbe5ea',
        color: '#64748b',
        maxWidth: 820,
      }}>
        <p style={{ margin: 0 }}>
          <Sparkles size={16} style={{ verticalAlign: 'text-bottom', marginRight: 6 }} />
          Son kullanıcı sağlayıcı veya API anahtarı görmez. Fotoğraf analizi yine aynı İSG Suite
          ekranından yapılır; backend burada seçtiğiniz sağlayıcıya yönlendirir.
        </p>
      </div>
    </Page>
  );
}
