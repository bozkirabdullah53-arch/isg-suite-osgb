import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {describe, expect, it} from 'vitest';

import {SymbolGlyph} from './glyphs';

describe('İlk yardım kroki işareti', () => {
  it('yeşil tabela içinde beyaz alan ve kırmızı hilal çizer', () => {
    const markup = renderToStaticMarkup(
      React.createElement(SymbolGlyph, {type: 'firstaid', size: 48}),
    );

    expect(markup).toContain('fill="#15803d"');
    expect(markup).toContain('fill="#fff"');
    expect(markup).toContain('fill="#e21b23"');
    expect(markup).toContain('transform="translate(48 0) scale(-1 1)"');
  });
});
