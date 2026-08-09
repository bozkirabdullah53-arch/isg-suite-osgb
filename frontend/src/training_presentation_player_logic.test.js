import {describe, expect, it} from 'vitest';
import {
  INSTRUCTOR_UI_V2,
  instructorBulletPresentation,
  localizeInstructorText,
  normalizeInstructorManifest,
  playerIndexForKey,
} from './training_presentation_player_logic';

function manifest() {
  return {
    content_hash: 'a'.repeat(64),
    nace_snapshot: {nace_code: '27.20.01', nace_description: 'Akümülatör parçaları imalatı'},
    rendering: {instructor_mode_ui: INSTRUCTOR_UI_V2},
    coverage_v2: {phase9_supported_count: 5, phase9_full_profile: true},
    traceability: {
      version: 'presentation-question-traceability-v1',
      coverage: {
        question_total: 20,
        linked_questions: 20,
        source_linked_questions: 20,
        orphan_questions: 0,
        cross_sector_fallback: false,
        status: 'passed',
      },
      question_links: Array.from({length: 20}, (_, index) => ({
        slide_positions: [index < 5 ? 1 : 2],
      })),
    },
    slides: [
      {
        position: 1,
        title: 'Temel',
        section_id: 'foundation_ohs',
        source_refs: ['tr-law-6331'],
        content_blocks: [{type: 'tehlike', value: 'Tehlike örneği'}],
      },
      {
        position: 2,
        title: 'Kurşun',
        section_id: 'work_specific_topics',
        source_refs: ['csgb-training-guide'],
        content_blocks: [{type: 'kontrol_tedbiri', value: 'Kaynağında kontrol'}],
      },
    ],
  };
}

describe('Eğitmen Modu manifesti', () => {
  it('20/20 coverage manifestini sunum modeline dönüştürür', () => {
    const result = normalizeInstructorManifest(manifest());
    expect(result.coverage).toEqual({total: 20, linked: 20, sourced: 20, orphan: 0});
    expect(result.slides[0].linkedQuestionCount).toBe(5);
    expect(result.slides[1].linkedQuestionCount).toBe(15);
    expect(result.slides[1].bullets[0]).toContain('Kontrol tedbiri');
    expect(result.uiVersion).toBe(INSTRUCTOR_UI_V2);
    expect(result.coverageV2.phase9_full_profile).toBe(true);
  });

  it('kart sunumu için içerik türünü güvenli biçimde sınıflandırır', () => {
    expect(instructorBulletPresentation('Tehlike: Düşme riski')).toEqual({
      kind: 'hazard',
      label: 'Tehlike',
      text: 'Düşme riski',
    });
    expect(instructorBulletPresentation('Kontrol tedbiri: Korkuluk kullan')).toEqual({
      kind: 'control',
      label: 'Kontrol tedbiri',
      text: 'Korkuluk kullan',
    });
    expect(instructorBulletPresentation('Serbest eğitim notu')).toEqual({
      kind: 'context',
      label: 'Eğitim notu',
      text: 'Serbest eğitim notu',
    });
  });

  it('kullanıcıya görünen İngilizce alan adlarını Türkçeleştirir', () => {
    const value = manifest();
    value.slides[0].content_blocks.push({type: 'training_date', value: '2026-08-09'});
    value.slides[0].content_blocks.push({type: 'frozen_training_topic', value: 'Battery charging and emergency exit'});
    const result = normalizeInstructorManifest(value);
    expect(result.slides[0].bullets).toContain('Eğitim tarihi: 2026-08-09');
    expect(result.slides[0].bullets).toContain('akü şarjı and acil çıkış');
    expect(result.slides[0].bullets.join(' ')).not.toMatch(/training date/i);
    expect(localizeInstructorText('Personal protective equipment')).toBe('kişisel koruyucu donanım (KKD)');
  });

  it('v2 işareti olmayan tarihsel manifesti v1 olarak bırakır', () => {
    const value = manifest();
    delete value.rendering;
    delete value.coverage_v2;
    const result = normalizeInstructorManifest(value);
    expect(result.uiVersion).toBe('instructor-mode-v1');
    expect(result.coverageV2).toBe(null);
  });

  it('eksik coverage için fail-closed olur', () => {
    const value = manifest();
    value.traceability.coverage.linked_questions = 19;
    expect(() => normalizeInstructorManifest(value)).toThrow(/kapsam doğrulaması/);
  });

  it('klavye gezinmesini sınırlar', () => {
    expect(playerIndexForKey('ArrowRight', 0, 3)).toBe(1);
    expect(playerIndexForKey('End', 0, 3)).toBe(2);
    expect(playerIndexForKey('ArrowRight', 2, 3)).toBe(2);
    expect(playerIndexForKey('Home', 2, 3)).toBe(0);
  });
});
