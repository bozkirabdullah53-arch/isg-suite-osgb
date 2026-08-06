import {describe,expect,it,vi} from 'vitest';
import {
  asDocumentRows,
  categoriesForKind,
  formatDocumentBytes,
  newIdempotencyKey,
  normalizeCategoryForKind,
  safeDocumentFilename,
  validateDocumentFile,
  validityLabel,
  validityTone,
} from './personnel_profile_documents_logic';

describe('personnel profile document UI logic',()=>{
  it('normalizes API item envelopes',()=>{
    expect(asDocumentRows({items:[{id:1}]})).toEqual([{id:1}]);
    expect(asDocumentRows(null)).toEqual([]);
  });

  it('keeps category compatible with document kind',()=>{
    expect(normalizeCategoryForKind('cv','diploma')).toBe('cv');
    expect(normalizeCategoryForKind('certificate','first_aid_certificate')).toBe('first_aid_certificate');
    expect(categoriesForKind('profile_photo').map(([id])=>id)).toEqual(['profile_photo']);
  });

  it('rejects oversized and incompatible files before upload',()=>{
    expect(validateDocumentFile({name:'cv.exe',size:120},'cv')).toContain('desteklenmeyen');
    expect(validateDocumentFile({name:'photo.jpg',size:6*1024*1024},'profile_photo')).toContain('5 MB');
    expect(validateDocumentFile({name:'cv.pdf',size:1000},'cv')).toBe('');
  });

  it('formats sizes and status labels',()=>{
    expect(formatDocumentBytes(2048)).toBe('2 KB');
    expect(validityLabel('expiring_soon')).toContain('30 gün');
    expect(validityTone('expired')).toBe('danger');
  });

  it('builds a safe filename without personal path data',()=>{
    expect(safeDocumentFilename({title:'İlk Yardımcı Belgesi / 2026',version:2,file_extension:'.pdf'}))
      .toBe('Ilk-Yardimci-Belgesi-2026-v2.pdf');
  });

  it('uses browser UUID when available',()=>{
    const original=globalThis.crypto;
    Object.defineProperty(globalThis,'crypto',{value:{randomUUID:vi.fn(()=> '11111111-1111-4111-a111-111111111111')},configurable:true});
    expect(newIdempotencyKey()).toBe('11111111-1111-4111-a111-111111111111');
    Object.defineProperty(globalThis,'crypto',{value:original,configurable:true});
  });
});
