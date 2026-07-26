import React,{useEffect,useRef,useState} from 'react';
import jsQR from 'jsqr';
import {QrCode,ScanLine} from 'lucide-react';

/**
 * Mobil saha QR kamera okuyucu — mevcut ziyaret/tamamlama akışına dokunmaz.
 * Destek yoksa veya izin reddedilirse üst bileşen yapıştırma alanını kullanır.
 */
export function SiteQrCameraModal({open,mode,onClose,onDetected}){
  const videoRef=useRef(null);
  const canvasRef=useRef(null);
  const streamRef=useRef(null);
  const rafRef=useRef(0);
  const lockedRef=useRef(false);
  const onDetectedRef=useRef(onDetected);
  const[hint,setHint]=useState('Kameraya izin verin; QR’ı çerçeveye tutun.');
  const[camErr,setCamErr]=useState('');
  onDetectedRef.current=onDetected;

  useEffect(()=>{
    if(!open) return undefined;
    lockedRef.current=false;
    setCamErr('');
    setHint(
      mode==='out'?'Çıkış için işyeri QR’sını okutun.'
      :mode==='visit'||mode==='complete'?'İşyeri QR’sını çerçeveye tutun.'
      :'Giriş için işyeri QR’sını okutun.'
    );
    let cancelled=false;

    async function start(){
      try{
        if(!navigator.mediaDevices?.getUserMedia){
          setCamErr('Bu cihazda kamera API’si yok. Kod yapıştırma alanını kullanın.');
          return;
        }
        const stream=await navigator.mediaDevices.getUserMedia({
          audio:false,
          video:{facingMode:{ideal:'environment'},width:{ideal:1280},height:{ideal:720}},
        });
        if(cancelled){
          stream.getTracks().forEach(t=>t.stop());
          return;
        }
        streamRef.current=stream;
        const video=videoRef.current;
        if(!video) return;
        video.srcObject=stream;
        await video.play();
        const tick=()=>{
          if(cancelled||lockedRef.current) return;
          const v=videoRef.current;
          const c=canvasRef.current;
          if(v&&c&&v.readyState>=2){
            const w=v.videoWidth;
            const h=v.videoHeight;
            if(w&&h){
              c.width=w;c.height=h;
              const ctx=c.getContext('2d',{willReadFrequently:true});
              ctx.drawImage(v,0,0,w,h);
              const img=ctx.getImageData(0,0,w,h);
              const code=jsQR(img.data,w,h,{inversionAttempts:'dontInvert'});
              if(code?.data){
                lockedRef.current=true;
                setHint('QR okundu…');
                onDetectedRef.current?.(String(code.data).trim());
                return;
              }
            }
          }
          rafRef.current=requestAnimationFrame(tick);
        };
        rafRef.current=requestAnimationFrame(tick);
      }catch(ex){
        setCamErr(ex?.message||'Kamera açılamadı. Yapıştırma alanını kullanın.');
      }
    }
    start();

    return ()=>{
      cancelled=true;
      if(rafRef.current) cancelAnimationFrame(rafRef.current);
      if(streamRef.current){
        streamRef.current.getTracks().forEach(t=>t.stop());
        streamRef.current=null;
      }
    };
  },[open,mode]);

  if(!open) return null;
  return (
    <div className="modal-bg" style={{zIndex:50}} onMouseDown={e=>{if(e.target===e.currentTarget) onClose?.()}}>
      <section className="modal" style={{maxWidth:520,width:'min(96vw,520px)'}}>
        <header style={{display:'flex',alignItems:'center',gap:10}}>
          <span style={{display:'inline-flex',color:'#0f766e'}} aria-hidden>
            {mode==='out'?<ScanLine size={22}/>:<QrCode size={22}/>}
          </span>
          <h3 style={{flex:1,margin:0}}>
            {mode==='out'?'Çıkış — QR okut'
              :mode==='visit'||mode==='complete'?'İşyeri QR okut'
              :'Giriş — QR okut'}
          </h3>
          <button type="button" className="icon" onClick={onClose} aria-label="Kapat">×</button>
        </header>
        <div style={{display:'grid',gap:10}}>
          <p style={{margin:0,color:'#64748b',fontSize:14}}>{hint}</p>
          {camErr?(
            <p style={{margin:0,color:'#b91c1c',fontSize:14}}>{camErr}</p>
          ):(
            <div style={{position:'relative',borderRadius:12,overflow:'hidden',background:'#0f172a',aspectRatio:'3/4',maxHeight:'60vh'}}>
              <video ref={videoRef} playsInline muted style={{width:'100%',height:'100%',objectFit:'cover'}}/>
              <div style={{
                pointerEvents:'none',position:'absolute',inset:'18%',
                border:'2px solid rgba(45,212,191,.95)',borderRadius:12,
                boxShadow:'0 0 0 999px rgba(15,23,42,.35)',
              }}/>
            </div>
          )}
          <canvas ref={canvasRef} style={{display:'none'}}/>
          <div className="form-actions">
            <button type="button" className="secondary" onClick={onClose}>İptal / Yapıştır</button>
          </div>
        </div>
      </section>
    </div>
  );
}
