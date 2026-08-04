/** @vitest-environment happy-dom */

import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {LOGIN_SHOWCASE_SLIDES, LoginShowcase} from './login_showcase';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

describe('LoginShowcase', () => {
  let container;
  let root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.useRealTimers();
  });

  it('10 benzersiz platform özelliğini sunar', () => {
    expect(LOGIN_SHOWCASE_SLIDES).toHaveLength(10);
    expect(new Set(LOGIN_SHOWCASE_SLIDES.map((slide) => slide.title)).size).toBe(10);

    act(() => root.render(React.createElement(LoginShowcase)));

    expect(container.querySelector('.login-showcase')?.getAttribute('aria-label')).toBe('İSG Suite özellikleri');
    expect(container.querySelectorAll('[role="tab"]')).toHaveLength(10);
    expect(container.querySelector('h2')?.textContent).toBe(LOGIN_SHOWCASE_SLIDES[0].title);
  });

  it('ileri ve geri kontrolleriyle slayt değiştirir', () => {
    act(() => root.render(React.createElement(LoginShowcase)));

    act(() => {
      container.querySelector('[aria-label="Sonraki özellik"]').click();
    });
    expect(container.querySelector('h2')?.textContent).toBe(LOGIN_SHOWCASE_SLIDES[1].title);

    act(() => {
      container.querySelector('[aria-label="Önceki özellik"]').click();
    });
    expect(container.querySelector('h2')?.textContent).toBe(LOGIN_SHOWCASE_SLIDES[0].title);
  });

  it('6,5 saniye sonra otomatik olarak ilerler', () => {
    vi.useFakeTimers();
    act(() => root.render(React.createElement(LoginShowcase)));

    act(() => vi.advanceTimersByTime(6500));

    expect(container.querySelector('h2')?.textContent).toBe(LOGIN_SHOWCASE_SLIDES[1].title);
  });

  it('masaüstü, tablet ve mobil kurallarını yalnızca vitrin sınıflarıyla sınırlar', () => {
    const css = readFileSync(join(process.cwd(), 'src/login_showcase.css'), 'utf8');

    expect(css).toMatch(/position:\s*absolute/);
    expect(css).toMatch(/@media \(max-width:\s*1279px\)/);
    expect(css).toMatch(/@media \(max-width:\s*620px\)/);
    expect(css).toMatch(/@media \(max-height:\s*760px\) and \(max-width:\s*1279px\)/);
    expect(css).toMatch(/@media \(prefers-reduced-motion:\s*reduce\)/);
    expect(css).toMatch(/\.login-showcase \+ \.login-wrap \{ width:\s*392px; \}/);
    expect(css).toMatch(/\.login-showcase \{ top:\s*50%; \}/);
    expect(css).toMatch(/\.login-showcase \+ \.login-wrap \.login-card \{[\s\S]*min-height:\s*478px;/);
    expect(css).toMatch(/\.login-showcase \+ \.login-wrap \.login-brand--card \{[\s\S]*margin-top:\s*auto;/);
    expect(css).not.toMatch(/\.login-shell/);
  });
});
