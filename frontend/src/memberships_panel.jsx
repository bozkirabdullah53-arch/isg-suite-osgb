import {useEffect, useState} from 'react';
import {api} from './api';

/** P1-04: Üyelik özeti + admin listeleri. */
export function MembershipsPanel({user}) {
  const [me, setMe] = useState(null);
  const [org, setOrg] = useState([]);
  const [wp, setWp] = useState([]);
  const [msg, setMsg] = useState('');
  const canAdmin = user?.role === 'global_admin' || user?.role === 'company_admin';

  useEffect(() => {
    api('/memberships/me')
      .then(setMe)
      .catch((e) => setMsg(e.message));
    if (canAdmin) {
      api('/memberships/organization')
        .then(setOrg)
        .catch(() => {});
      api('/memberships/workplace')
        .then(setWp)
        .catch(() => {});
    }
  }, [canAdmin]);

  return (
    <section className="panel" style={{marginTop: 16}}>
      <h3>Üyelikler (P1-04)</h3>
      <p style={{marginTop: 0, color: '#64748b', fontSize: 14}}>
        Çoklu OSGB/işyeri üyelik modeli. Satır yoksa klasik kullanıcı alanları kullanılır.
      </p>
      {msg && <p style={{color: '#b91c1c'}}>{msg}</p>}
      {me && (
        <div style={{fontSize: 14, marginBottom: 12}}>
          Kaynak: <strong>{me.source}</strong> · OSGB: {(me.osgb_ids || []).join(', ') || '—'} ·
          İşyeri: {(me.company_ids || []).join(', ') || '—'} · Org satır: {me.organization_rows} ·
          İşyeri satır: {me.workplace_rows}
        </div>
      )}
      {canAdmin && (
        <div style={{display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))'}}>
          <div>
            <h4 style={{margin: '0 0 8px'}}>OSGB üyelikleri</h4>
            <ul style={{margin: 0, paddingLeft: 18, fontSize: 13}}>
              {org.slice(0, 20).map((r) => (
                <li key={r.id}>
                  user #{r.user_id} → OSGB #{r.osgb_id} ({r.role}){r.is_active ? '' : ' [pasif]'}
                </li>
              ))}
              {!org.length && <li style={{color: '#64748b'}}>Kayıt yok</li>}
            </ul>
          </div>
          <div>
            <h4 style={{margin: '0 0 8px'}}>İşyeri üyelikleri</h4>
            <ul style={{margin: 0, paddingLeft: 18, fontSize: 13}}>
              {wp.slice(0, 20).map((r) => (
                <li key={r.id}>
                  user #{r.user_id} → firma #{r.company_id} ({r.role}){r.is_active ? '' : ' [pasif]'}
                </li>
              ))}
              {!wp.length && <li style={{color: '#64748b'}}>Kayıt yok</li>}
            </ul>
          </div>
        </div>
      )}
    </section>
  );
}
