// @vitest-environment happy-dom
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {describe, expect, it} from 'vitest';
import {browserSpeechRecognition, highlightTarget, speechRecognitionErrorMessage} from './contextual_assistant.jsx';

describe('contextual assistant target guidance', () => {
  it('highlights a target without clicking it', () => {
    const button = document.createElement('button');
    button.setAttribute('data-ai-action', 'employee.import_excel');
    document.body.appendChild(button);
    expect(highlightTarget('employee.import_excel')).toBe(true);
    expect(button.classList.contains('ai-assistant-target-highlight')).toBe(true);
  });

  it('allows same-origin microphone access in the production web server policy', () => {
    const nginxConfig = readFileSync(resolve(process.cwd(), 'nginx.conf'), 'utf8');
    expect(nginxConfig).toContain('microphone=(self)');
    expect(nginxConfig).not.toContain('microphone=()');
  });

  it('uses prefixed browser speech recognition when available', () => {
    class Recognition {}
    expect(browserSpeechRecognition({webkitSpeechRecognition: Recognition})).toBe(Recognition);
    expect(browserSpeechRecognition({})).toBeNull();
  });

  it('explains browser speech recognition failures', () => {
    expect(speechRecognitionErrorMessage('not-allowed')).toContain('Mikrofon izni');
    expect(speechRecognitionErrorMessage('no-speech')).toContain('Ses algılanamadı');
    expect(speechRecognitionErrorMessage('network')).toContain('İnternet bağlantınızı');
  });
});
