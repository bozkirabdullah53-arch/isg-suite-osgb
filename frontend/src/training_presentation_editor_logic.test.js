import {describe, expect, it} from 'vitest';
import {
  buildPresentationEditPayload,
  canEditPresentationRole,
  editorSlides,
  lessonPointsFromText,
  pickEditableVersion,
} from './training_presentation_editor_logic';

describe('training presentation editor logic', () => {
  it('allows only instructor/management roles', () => {
    expect(canEditPresentationRole('safety_specialist')).toBe(true);
    expect(canEditPresentationRole('workplace_physician')).toBe(true);
    expect(canEditPresentationRole('company_admin')).toBe(true);
    expect(canEditPresentationRole('read_only')).toBe(false);
  });

  it('normalizes lesson lines and caps them at eight', () => {
    const rows = lessonPointsFromText('1. Bir\n- İki\n• Üç\n4) Dört');
    expect(rows).toEqual(['Bir', 'İki', 'Üç', 'Dört']);
  });

  it('selects latest version without mutating history', () => {
    const rows = [{id: 1, version: 1, status: 'approved'}, {id: 3, version: 3, status: 'draft'}, {id: 2, version: 2, status: 'generated'}];
    expect(pickEditableVersion(rows)?.id).toBe(3);
    expect(rows[0].id).toBe(1);
  });

  it('builds append-only existing-slide payload', () => {
    const payload = buildPresentationEditPayload({
      position: 4,
      title: 'Güncel başlık',
      mode: 'append',
      lessonPoints: 'Tehlikeyi tanı\nKontrolü doğrula',
      scenario: 'Örnek vaka',
      keyTakeaway: 'Ana mesaj',
      instructorNote: 'Bu noktada sahadan örnek ver.',
      autoEnrich: true,
    });
    expect(payload.slide_updates).toHaveLength(1);
    expect(payload.slide_updates[0].position).toBe(4);
    expect(payload.slide_updates[0].lesson_points).toHaveLength(2);
    expect(payload.auto_enrich_teaching_v3).toBe(true);
  });

  it('builds a new-slide payload', () => {
    const payload = buildPresentationEditPayload({
      title: 'Ek uygulama örneği',
      lessonPoints: 'Birinci adım',
      autoEnrich: true,
    }, {newSlide: true});
    expect(payload.slide_updates).toEqual([]);
    expect(payload.append_slides[0].title).toBe('Ek uygulama örneği');
  });

  it('sorts slide summary by position', () => {
    expect(editorSlides({slides: [{position: 2, title: 'B'}, {position: 1, title: 'A'}]}).map((x) => x.title)).toEqual(['A', 'B']);
  });
});
