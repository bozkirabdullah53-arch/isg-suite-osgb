import React, {useCallback, useEffect, useState} from 'react';
import {
  ArrowLeft,
  ArrowRight,
  CalendarRange,
  CheckCircle2,
  ExternalLink,
  Filter,
  RefreshCw,
  RotateCcw,
  Search,
} from 'lucide-react';
import {api} from './api';
import {AppModal} from './ui_modal';
import {workplaceDateText} from './workplace_alert_center';
import {
  buildObligationQuery,
  consumeSelectedObligation,
  defaultObligationFilters,
  obligationDaysText,
  obligationStatusLabel,
} from './workplace_obligations';
import './workplace_status.css';

const STATUS_CARDS = [
  {code: 'overdue', label: 'Gecikmiş'},
  {code: 'very_soon', label: 'Çok Yakın (0–7 gün)'},
  {code: 'approaching', label: 'Yaklaşıyor (8–30 gün)'},
  {code: 'completed', label: 'Tamamlandı'},
];

function StatusBadge({status}) {
  return <span className={`obligation-status obligation-status--${status}`}>{obligationStatusLabel(status)}</span>;
}

export function WorkplaceObligationCenter({companyId, companyName, canOpenModule, onOpenModule}) {
  const [filters, setFilters] = useState(() => defaultObligationFilters());
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [feed, setFeed] = useState(null);
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);

  const load = useCallback(async () => {
    if (!companyId) return;
    setBusy(true);
    setError('');
    try {
      const query = buildObligationQuery(filters, page, pageSize);
      const body = await api(`/companies/${companyId}/status/obligations?${query}`);
      setFeed(body);
      const serverPage = Number(body?.pagination?.page || 1);
      if (serverPage !== page) setPage(serverPage);
    } catch (err) {
      setError(err.message || 'Yükümlülükler yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }, [companyId, filters, page, pageSize, reload]);

  useEffect(() => {
    setFilters(defaultObligationFilters());
    setPage(1);
    setFeed(null);
    setError('');
    setSelected(consumeSelectedObligation(companyId));
  }, [companyId]);

  useEffect(() => { void load(); }, [load]);

  function updateFilter(key, value) {
    setPage(1);
    setFilters((current) => ({...current, [key]: value}));
  }

  function toggleStatus(status) {
    updateFilter('status', filters.status === status ? '' : status);
  }

  function resetFilters() {
    setPage(1);
    setFilters(defaultObligationFilters());
  }

  const summary = feed?.summary || {};
  const pagination = feed?.pagination || {};
  const rows = Array.isArray(feed?.items) ? feed.items : [];

  return (
    <section className="panel workplace-obligation-center" aria-busy={busy}>
      <div className="workplace-obligation-head">
        <div>
          <span className="workplace-obligation-eyebrow"><CalendarRange size={15}/> YÜKÜMLÜLÜK TAKVİMİ</span>
          <h3>Yaklaşan, gecikmiş ve tamamlanan kayıtlar</h3>
          <p>Gecikmişler önce gelir. Çok Yakın 0–7 gün, Yaklaşıyor 8–30 gün aralığıdır.</p>
        </div>
        <button type="button" className="mini secondary" disabled={busy} onClick={() => setReload((value) => value + 1)}>
          <RefreshCw size={14}/> Yenile
        </button>
      </div>

      <div className="workplace-obligation-metrics" aria-label="Yükümlülük durum özeti">
        {STATUS_CARDS.map((item) => (
          <button
            type="button"
            key={item.code}
            className={`workplace-obligation-metric workplace-obligation-metric--${item.code}${filters.status === item.code ? ' is-active' : ''}`}
            onClick={() => toggleStatus(item.code)}
            aria-pressed={filters.status === item.code}
          >
            <span>{item.label}</span>
            <strong>{summary[item.code] ?? 0}</strong>
          </button>
        ))}
      </div>

      <div className="workplace-obligation-filters">
        <label>
          <span>Şube</span>
          <select value={filters.branch_id} onChange={(event) => updateFilter('branch_id', event.target.value)}>
            <option value="">Tüm şubeler ve işyeri geneli</option>
            {(feed?.branches || []).map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
          </select>
        </label>
        <label>
          <span>Kategori</span>
          <select value={filters.category} onChange={(event) => updateFilter('category', event.target.value)}>
            <option value="">Tüm kategoriler</option>
            {(feed?.categories || []).map((category) => (
              <option key={category.code} value={category.code}>{category.label} ({category.count})</option>
            ))}
          </select>
        </label>
        <label>
          <span>Durum</span>
          <select value={filters.status} onChange={(event) => updateFilter('status', event.target.value)}>
            <option value="">Tüm durumlar</option>
            {(feed?.statuses || []).map((status) => (
              <option key={status.code} value={status.code}>{status.label} ({status.count})</option>
            ))}
          </select>
        </label>
        <label>
          <span>Başlangıç</span>
          <input type="date" value={filters.date_from} onChange={(event) => updateFilter('date_from', event.target.value)}/>
        </label>
        <label>
          <span>Bitiş</span>
          <input type="date" value={filters.date_to} onChange={(event) => updateFilter('date_to', event.target.value)}/>
        </label>
        <label>
          <span>Sayfa boyutu</span>
          <select value={pageSize} onChange={(event) => { setPage(1); setPageSize(Number(event.target.value)); }}>
            {[10, 25, 50, 100].map((size) => <option key={size} value={size}>{size} kayıt</option>)}
          </select>
        </label>
        <div className="workplace-obligation-filter-actions">
          <button type="button" className="mini secondary" onClick={resetFilters}><RotateCcw size={14}/> Sıfırla</button>
          <button type="button" className="mini secondary" onClick={() => updateFilter('date_to', '')}><Filter size={14}/> Tüm tarihler</button>
        </div>
      </div>

      {error && <div className="workplace-obligation-error" role="alert">{error}</div>}
      {!error && busy && !feed && <p className="loading">Yükümlülükler taranıyor…</p>}

      {!error && feed && (
        <>
          <div className="workplace-obligation-result-line">
            <span><Search size={14}/> {pagination.total ?? 0} kayıt bulundu</span>
            {summary.scheduled > 0 && <span>{summary.scheduled} ileri tarihli kayıt mevcut</span>}
          </div>
          <div className="table-wrap workplace-obligation-table-wrap">
            <table className="workplace-obligation-table">
              <thead>
                <tr>
                  <th>Durum</th>
                  <th>İşyeri / Şube</th>
                  <th>Kategori</th>
                  <th>Kayıt</th>
                  <th>Tarih</th>
                  <th>Süre</th>
                  <th>Sorumlu</th>
                  <th>İşlem</th>
                </tr>
              </thead>
              <tbody>
                {rows.length ? rows.map((row) => (
                  <tr key={row.key} className={`obligation-row obligation-row--${row.status}`}>
                    <td><StatusBadge status={row.status}/></td>
                    <td><strong>{companyName || feed.company?.name}</strong><small>{row.branch_name || 'İşyeri geneli'}</small></td>
                    <td>{row.category_label}</td>
                    <td><strong>{row.title}</strong><small>{row.source}</small></td>
                    <td>{workplaceDateText(row.due_date)}</td>
                    <td><strong>{obligationDaysText(row)}</strong></td>
                    <td>{row.responsible_role}</td>
                    <td><button type="button" className="mini secondary" onClick={() => setSelected(row)}>Kaydı aç</button></td>
                  </tr>
                )) : (
                  <tr><td colSpan={8} className="empty"><CheckCircle2 size={18}/> Seçili filtrelerde yükümlülük bulunamadı.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="workplace-obligation-pagination">
            <button type="button" className="mini secondary" disabled={!pagination.has_previous || busy} onClick={() => setPage((value) => Math.max(1, value - 1))}>
              <ArrowLeft size={14}/> Önceki
            </button>
            <span>Sayfa {pagination.page || 1} / {pagination.total_pages || 1}</span>
            <button type="button" className="mini secondary" disabled={!pagination.has_next || busy} onClick={() => setPage((value) => value + 1)}>
              Sonraki <ArrowRight size={14}/>
            </button>
          </div>
        </>
      )}

      {selected && (
        <AppModal title="Yükümlülük kaydı" close={() => setSelected(null)} wide>
          <div className="workplace-obligation-detail">
            <div className="workplace-obligation-detail-head">
              <StatusBadge status={selected.status}/>
              <span>{selected.category_label}</span>
            </div>
            <h3>{selected.title}</h3>
            {selected.detail && <p>{selected.detail}</p>}
            <dl>
              <div><dt>İşyeri</dt><dd>{companyName || feed?.company?.name || '—'}</dd></div>
              <div><dt>Şube</dt><dd>{selected.branch_name || 'İşyeri geneli'}</dd></div>
              <div><dt>Kaynak</dt><dd>{selected.source}</dd></div>
              <div><dt>Tarih</dt><dd>{workplaceDateText(selected.due_date)}</dd></div>
              <div><dt>Süre durumu</dt><dd>{obligationDaysText(selected)}</dd></div>
              <div><dt>Sorumlu</dt><dd>{selected.responsible_role}</dd></div>
              <div><dt>Kayıt türü</dt><dd>{selected.target?.entity_type || '—'}{selected.target?.record_id ? ` #${selected.target.record_id}` : ''}</dd></div>
            </dl>
            <p className="workplace-obligation-detail-note">
              Bu pencere kaynak kaydı salt okunur gösterir. Kaynak modüldeki mevcut görüntüleme ve değiştirme yetkileri aynen korunur.
            </p>
            <div className="form-actions">
              <button type="button" className="secondary" onClick={() => setSelected(null)}>Kapat</button>
              {selected.target?.module && canOpenModule?.(selected.target.module) && (
                <button type="button" onClick={() => onOpenModule?.(selected.target.module, selected.target)}>
                  <ExternalLink size={15}/> Kaynak modüle git
                </button>
              )}
            </div>
          </div>
        </AppModal>
      )}
    </section>
  );
}

export default WorkplaceObligationCenter;
