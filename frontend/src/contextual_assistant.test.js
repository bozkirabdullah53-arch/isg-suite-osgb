// @vitest-environment happy-dom
import {describe, expect, it} from 'vitest';
import {highlightTarget} from './contextual_assistant.jsx';

describe('contextual assistant target guidance', () => {
  it('highlights a target without clicking it', () => {
    const button = document.createElement('button');
    button.setAttribute('data-ai-action', 'employee.import_excel');
    document.body.appendChild(button);
    expect(highlightTarget('employee.import_excel')).toBe(true);
    expect(button.classList.contains('ai-assistant-target-highlight')).toBe(true);
  });
});
