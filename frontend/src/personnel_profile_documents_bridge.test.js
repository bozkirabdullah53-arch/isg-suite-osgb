import {afterEach,describe,expect,it} from 'vitest';
import {personnelProfileDocumentsBridgeTestables} from './personnel_profile_documents_bridge';

const {
  parseVisibleProfileId,
  documentsTabIsActive,
  findDocumentsPlaceholder,
}=personnelProfileDocumentsBridgeTestables;

afterEach(()=>{document.body.innerHTML=''});

describe('personnel profile documents bridge',()=>{
  it('resolves only the visible profile pill',()=>{
    document.body.innerHTML='<div id="root"><span class="ppm-status ppm-status--info">Profil #42</span></div>';
    expect(parseVisibleProfileId(document.querySelector('#root'))).toBe(42);
  });

  it('requires the documents tab to be active',()=>{
    document.body.innerHTML='<div id="root"><nav class="ppm-tabs"><button>Genel Bakış</button><button class="is-active">Belgeler</button></nav></div>';
    expect(documentsTabIsActive(document.querySelector('#root'))).toBe(true);
    document.querySelector('.is-active').classList.remove('is-active');
    expect(documentsTabIsActive(document.querySelector('#root'))).toBe(false);
  });

  it('finds only the document capability placeholder',()=>{
    document.body.innerHTML='<div id="root"><div class="ppm-tab-content"><div class="ppm-capability-notice">Kontrollü Paylaşım</div><div class="ppm-capability-notice">Sertifikalar ve Belgeler</div></div></div>';
    expect(findDocumentsPlaceholder(document.querySelector('#root'))?.textContent).toContain('Sertifikalar');
  });
});
