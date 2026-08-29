import {useEffect, useState} from "react";
import {api} from "./api";

const cards = [["employee_count", "Aktif çalışan"], ["open_risks", "Açık risk"], ["open_dofs", "Açık DÖF"], ["overdue_dofs", "Geciken DÖF"], ["upcoming_health_30d", "30 günde sağlık"], ["training_completion_rate", "Eğitim tamamlanma %"], ["field_inspections", "Saha denetimi"], ["active_work_permits", "Aktif çalışma izni"]];

export function CustomerPortalPage() {
  const [companies, setCompanies] = useState([]), [companyId, setCompanyId] = useState(""), [summary, setSummary] = useState(null), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  useEffect(() => { api("/companies").then((data) => setCompanies(Array.isArray(data) ? data : data.items || [])).catch((ex) => setError(ex.message)); }, []);
  async function load(id = companyId) { if (!id) return; setBusy(true); setError(""); try { setSummary(await api(`/customer-portal/${id}/summary`)); } catch (ex) { setError(ex.message); setSummary(null); } finally { setBusy(false); } }
  useEffect(() => { if (companyId) void load(companyId); }, [companyId]);
  const kpis = summary?.kpis || {};
  return <section className="page-shell"><div className="page-title"><h3>Müşteri Portalı</h3><span className="badge ok">Salt okunur</span></div><section className="panel">{error && <p className="error">{error}</p>}<label className="field"><span>Firma / işyeri seçin</span><select value={companyId} onChange={(event) => setCompanyId(event.target.value)}><option value="">Seçiniz</option>{companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}</select></label>{busy && <p>Özet yükleniyor…</p>}{summary && <><p>Veri tarihi: {summary.as_of} · Hassas çalışan ve klinik detaylar gösterilmez.</p><div className="report-grid">{cards.map(([key, label]) => <article className="metric" key={key}><span>{label}</span><strong>{kpis[key] ?? 0}{key === "training_completion_rate" ? "%" : ""}</strong></article>)}</div></>}</section></section>;
}
