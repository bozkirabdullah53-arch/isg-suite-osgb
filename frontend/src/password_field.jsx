import React, {useState} from 'react';
import {Eye, EyeOff} from 'lucide-react';

/** Şifre alanı — göster/gizle. Başkasının şifresine müdahale UI'sı değildir; yalnızca kendi girişi. */
export function PasswordField({label, value, onChange, className = '', ...p}) {
  const [show, setShow] = useState(false);
  return (
    <label className={`field password-field ${className}`.trim()}>
      {label ? <span>{label}</span> : null}
      <div className="password-input-wrap">
        <input
          {...p}
          type={show ? 'text' : 'password'}
          value={value}
          onChange={onChange}
          autoComplete={p.autoComplete || 'off'}
        />
        <button
          type="button"
          className="password-toggle"
          aria-label={show ? 'Şifreyi gizle' : 'Şifreyi göster'}
          title={show ? 'Şifreyi gizle' : 'Şifreyi göster'}
          onClick={() => setShow((s) => !s)}
        >
          {show ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>
    </label>
  );
}

/** Login kartı gibi label+input düzeni (Field sınıfı olmadan). */
export function LoginPasswordInput({label, value, onChange, ...p}) {
  const [show, setShow] = useState(false);
  return (
    <>
      {label ? <label>{label}</label> : null}
      <div className="password-input-wrap">
        <input
          {...p}
          type={show ? 'text' : 'password'}
          value={value}
          onChange={onChange}
          autoComplete={p.autoComplete || 'current-password'}
        />
        <button
          type="button"
          className="password-toggle"
          aria-label={show ? 'Şifreyi gizle' : 'Şifreyi göster'}
          title={show ? 'Şifreyi gizle' : 'Şifreyi göster'}
          onClick={() => setShow((s) => !s)}
        >
          {show ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>
    </>
  );
}
