from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import textwrap

W,H=1080,1920
OUT=Path('promo_render'); OUT.mkdir(exist_ok=True)
INK='#123B59'; MUTED='#5E7485'; BORDER='#DBE5EF'; ACCENT='#0B7285'; ACCENT2='#3AAEB7'; WHITE='#FFFFFF'; BG='#F4FAFC'; PALE='#E7F8F8'; GREEN='#16A34A'; GREENBG='#DCFCE7'; RED='#B91C1C'; REDBG='#FEE2E2'; BLUEBG='#E0F2FE'; DARK='#072B3A'
REG='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'; BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def F(n,b=False): return ImageFont.truetype(BOLD if b else REG,n)
def grad(c1,c2):
    a=Image.new('RGB',(W,H),c1); b=Image.new('RGB',(W,H),c2); m=Image.new('L',(1,H)); p=m.load()
    for y in range(H): p[0,y]=int(255*y/(H-1))
    return Image.composite(b,a,m.resize((W,H))).convert('RGBA')
def base(dark=False):
    im=grad('#082936','#0B4C5A') if dark else grad('#F9FCFD','#EDF7FA')
    glow=Image.new('RGBA',(W,H),(0,0,0,0)); g=ImageDraw.Draw(glow); g.ellipse((700,-180,1270,400),fill=(58,190,195,38 if dark else 24)); glow=glow.filter(ImageFilter.GaussianBlur(45)); im.alpha_composite(glow); return im
def wrap(draw,text,font,maxw):
    out=[]; line=''
    for w in text.split():
        t=(line+' '+w).strip()
        if draw.textbbox((0,0),t,font=font)[2]<=maxw: line=t
        else:
            if line: out.append(line)
            line=w
    if line: out.append(line)
    return out
def txt(draw,x,y,text,font,fill,maxw,sp=8):
    for line in wrap(draw,text,font,maxw): draw.text((x,y),line,font=font,fill=fill); y+=font.size+sp
    return y
def card(draw,box,fill=WHITE,outline=BORDER,r=26): draw.rounded_rectangle(box,r,fill=fill,outline=outline,width=2)
def pill(draw,box,text,bg=PALE,fg=ACCENT,fs=20):
    draw.rounded_rectangle(box,999,fill=bg); x0,y0,x1,y1=box; f=F(fs,True); bb=draw.textbbox((0,0),text,font=f); draw.text((x0+(x1-x0-bb[2])/2,y0+(y1-y0-bb[3])/2-4),text,font=f,fill=fg)
def brand(draw,dark,idx):
    c=WHITE if dark else INK; draw.rounded_rectangle((70,60,140,130),18,fill=ACCENT2); draw.line((88,96,103,112,125,83),fill=WHITE,width=9); draw.text((165,62),'İSG SUITE',font=F(34,True),fill=c); draw.text((165,104),'UZAKTAN EĞİTİM',font=F(17,True),fill='#CBE7EC' if dark else MUTED); draw.text((930,80),f'{idx:02d}/12',font=F(19,True),fill='#A9D1D8' if dark else MUTED)
def head(draw,title,sub,idx,dark=False):
    brand(draw,dark,idx); y=205; col=WHITE if dark else INK; y=txt(draw,70,y,title,F(64,True),col,930,4); y+=18; txt(draw,70,y,sub,F(26), '#CBE7EC' if dark else MUTED,930,5)
def caption(draw,s,dark=False):
    y=1680; draw.rounded_rectangle((55,y,1025,1845),28,fill=(9,47,62,245) if dark else (255,255,255,245),outline=ACCENT2,width=2); draw.text((82,y+22),'TÜRKÇE SESLENDİRME',font=F(15,True),fill='#77D5DC' if dark else ACCENT2); txt(draw,82,y+54,s,F(27,True),WHITE if dark else INK,900,4)

caps=[
'İş sağlığı ve güvenliği eğitimlerini tek merkezden yönetin.',
'İ S G Suite Uzaktan Eğitim ile süreci baştan sona dijitalleştirin.',
'Sektörünüze uygun eğitim paketini seçin.',
'Firmanızı belirleyin ve doğru paketi hazırlayın.',
'Çalışanları seçin, son tarihi belirleyin ve eğitimi atayın.',
'Çalışanlar eğitimlerine bilgisayar, tablet veya telefondan erişsin.',
'Videolar sıralı ilerlesin; izleme durumu yüzde yüz takip edilsin.',
'Zorunlu içerik tamamlanmadan final sınavı açılmasın.',
'Final sınavında yüzde yetmiş başarı kriteri uygulansın.',
'Başarılı çalışan için sertifika ve belge akışı devreye girsin.',
'Yaklaşan, devam eden ve geciken eğitimleri tek ekrandan izleyin.',
'Daha profesyonel İSG yönetimi. Hemen keşfedin: isgsuite nokta tr.'
]

def scene(i):
    dark=i in (1,6,8,12); im=base(dark); d=ImageDraw.Draw(im)
    titles=[
    ('İSG EĞİTİMİ\nTEK MERKEZDE','Firma, çalışan, eğitim, sınav ve belge akışı.'),
    ('UZAKTAN EĞİTİM\nTEK AKIŞTA','Katalogdan sertifikaya kadar bütün süreç.'),
    ('SEKTÖRÜNE UYGUN\nEĞİTİM PAKETİ','Hazır katalogdan doğru içeriği seç.'),
    ('DOĞRU FİRMA.\nDOĞRU SEKTÖR.','Kontrollü ve net program hazırlama.'),
    ('ÇALIŞANLARI SEÇ.\nEĞİTİMİ ATA.','Son tarih ve durum takibi aynı ekranda.'),
    ('EĞİTİM\nHER YERDE','Bilgisayar, tablet ve telefondan erişim.'),
    ('VİDEO İLERLEMESİ\nKONTROL ALTINDA','Sıralı izleme ve yüzde yüz takip.'),
    ('ÖNCE EĞİTİM.\nSONRA SINAV.','Zorunlu içerik bitmeden sınav kilitli.'),
    ('SONUÇ ANINDA\nGÖRÜNÜR','Başarı kriteri sistem tarafından uygulanır.'),
    ('EĞİTİM TAMAM.\nBELGE HAZIR.','Sertifika ve eğitim belgesi akışı.'),
    ('TAKİP EKRANI\nHEP GÜNCEL','Durumları tek bakışta görün.'),
    ('DAHA DÜZENLİ.\nDAHA PROFESYONEL.','İş sağlığı ve güvenliği yönetiminde dijital kontrol.')][i-1]
    head(d,*titles,i,dark)
    if i==1:
        card(d,(125,700,955,1450),'#FFFFFF'); d.text((180,755),'UZAKTAN EĞİTİM KONTROL PANELİ',font=F(27,True),fill=ACCENT)
        items=[('FİRMA','128'),('ÇALIŞAN','1.246'),('EĞİTİM','84'),('SINAV','Aktif')]
        for k,(a,b) in enumerate(items):
            x=180+(k%2)*340; y=880+(k//2)*210; card(d,(x,y,x+295,y+165),'#F8FCFD'); d.text((x+30,y+28),a,font=F(18,True),fill=MUTED); d.text((x+30,y+70),b,font=F(42,True),fill=INK)
    elif i==2:
        card(d,(100,650,980,1435)); steps=['Katalog','Firma','Çalışan','Takip'];
        for k,s in enumerate(steps):
            x=145+k*210; d.ellipse((x,790,x+70,860),fill=ACCENT2); d.text((x+24,805),str(k+1),font=F(24,True),fill=WHITE); d.text((x-10,895),s,font=F(22,True),fill=INK)
            if k<3:d.line((x+70,825,x+195,825),fill='#A5D4D8',width=8)
        pill(d,(190,1090,890,1160),'KATALOG  →  ATAMA  →  TAKİP  →  BELGE',PALE,ACCENT,20)
    elif i==3:
        sec=['İNŞAAT','METAL-MAKİNE','LOJİSTİK','GIDA','KİMYASAL / BOYA','SAĞLIK']
        for k,s in enumerate(sec):
            x=80+(k%2)*470; y=590+(k//2)*280; card(d,(x,y,x+420,y+225)); d.text((x+35,y+45),f'{k+1:02d}',font=F(28,True),fill=ACCENT2); d.text((x+35,y+95),s,font=F(24,True),fill=INK); pill(d,(x+35,y+155,x+240,y+205),'Paketi görüntüle',PALE,ACCENT,16)
    elif i==4:
        vals=[('01','FİRMA','Örnek Firma A.Ş.'),('02','PAKET','Akü - Batarya'),('03','HAZIRLA','Firma programı')]
        for k,(n,a,b) in enumerate(vals):
            x=90+k*320; card(d,(x,690,x+275,1160)); d.ellipse((x+35,730,x+105,800),fill=ACCENT2 if k<2 else GREEN); d.text((x+54,745),n,font=F(20,True),fill=WHITE); d.text((x+35,835),a,font=F(18,True),fill=MUTED); txt(d,x+35,885,b,F(29,True),INK,210,4)
            if k<2:d.text((x+280,890),'→',font=F(44,True),fill='#8BC9CF')
        pill(d,(170,1240,910,1310),'KONTROL YÖNETİCİDE',BLUEBG,'#075985',21)
    elif i==5:
        card(d,(85,620,995,1450)); d.text((130,675),'Çalışan Atama',font=F(35,True),fill=INK); rows=[('AY','Ayşe Yılmaz','Başlamadı'),('MK','Mehmet Kaya','Devam ediyor'),('CD','Can Demir','Yaklaşan')]
        y=785
        for ini,n,st in rows:
            card(d,(130,y,950,y+145),'#FBFDFE'); d.ellipse((155,y+35,225,y+105),fill=ACCENT2); d.text((170,y+55),ini,font=F(18,True),fill=WHITE); d.text((255,y+30),n,font=F(27,True),fill=INK); d.text((255,y+78),'Temel İSG • Son tarih: 30.09.2026',font=F(18),fill=MUTED); pill(d,(700,y+45,920,y+100),st,PALE,ACCENT,16); y+=170
        d.rounded_rectangle((130,1305,950,1380),18,fill=ACCENT); d.text((335,1324),'EĞİTİMİ ATA',font=F(25,True),fill=WHITE)
    elif i==6:
        card(d,(265,575,815,1510),'#071F2A',None,58); d.rounded_rectangle((290,605,790,1480),46,fill='#F8FCFD'); d.text((335,690),'Eğitimlerim',font=F(37,True),fill=INK); card(d,(330,790,750,1125)); d.text((365,845),'TEMEL İSG EĞİTİMİ',font=F(20,True),fill=ACCENT); d.text((365,900),'Akü - Batarya',font=F(30,True),fill=INK); pill(d,(365,975,575,1030),'Devam ediyor',BLUEBG,'#075985',16); d.text((365,1060),'2 / 4 video',font=F(20),fill=MUTED); d.rounded_rectangle((330,1190,750,1260),18,fill=ACCENT); d.text((445,1210),'DEVAM ET',font=F(21,True),fill=WHITE)
    elif i==7:
        card(d,(85,610,995,1450)); d.rounded_rectangle((130,670,950,1080),24,fill='#0B2936'); d.polygon([(500,810),(500,945),(630,878)],fill=WHITE); d.rounded_rectangle((160,1010,920,1038),12,fill=GREEN); d.text((842,960),'100%',font=F(24,True),fill=WHITE); y=1140
        for n,s in enumerate(['İSG Temelleri','Riskler','Acil Durum','Sektörel Konular'],1): d.ellipse((150,y,195,y+45),fill=GREEN); d.text((164,y+5),'✓',font=F(23,True),fill=WHITE); d.text((220,y+7),s,font=F(22,True),fill=INK); y+=72
    elif i==8:
        card(d,(140,650,940,1410)); d.ellipse((460,760,620,920),fill=GREEN); d.text((500,788),'✓',font=F(64,True),fill=WHITE); d.text((330,970),'EĞİTİM TAMAMLANDI',font=F(30,True),fill=INK); d.rounded_rectangle((400,1090,680,1260),28,fill=ACCENT); d.text((474,1145),'SINAV',font=F(31,True),fill=WHITE); pill(d,(360,1310,720,1370),'Final sınavı açıldı',GREENBG,'#166534',19)
    elif i==9:
        card(d,(120,640,960,1420)); d.ellipse((180,760,520,1100),fill='#EAF2F5'); d.pieslice((180,760,520,1100),-90,205,fill=GREEN); d.ellipse((245,825,455,1035),fill=WHITE); d.text((275,885),'82%',font=F(58,True),fill=INK); d.text((270,965),'BAŞARILI',font=F(20,True),fill=GREEN); d.text((585,810),'Final Sınavı',font=F(33,True),fill=INK); pill(d,(585,880,850,940),'Geçme: %70',GREENBG,'#166534',20); d.text((585,1010),'10 soru',font=F(25,True),fill=INK); d.text((585,1060),'8 doğru',font=F(25,True),fill=INK); d.text((585,1110),'2 yanlış',font=F(25,True),fill=INK)
    elif i==10:
        card(d,(190,590,890,1460),'#FFFEFA'); d.rectangle((220,630,860,660),fill=ACCENT); d.text((275,730),'EĞİTİM SERTİFİKASI',font=F(39,True),fill=INK); d.text((320,800),'İş Sağlığı ve Güvenliği',font=F(23),fill=MUTED); d.line((270,865,810,865),fill=BORDER,width=3); d.text((285,935),'Katılımcı',font=F(17,True),fill=MUTED); d.text((285,970),'Örnek Çalışan',font=F(30,True),fill=INK); d.text((285,1060),'Temel İSG • Uzaktan',font=F(27,True),fill=INK); pill(d,(285,1300,620,1360),'Belge akışı hazır',PALE,ACCENT,18)
    elif i==11:
        st=[('YAKLAŞAN','12',ACCENT,PALE),('DEVAM EDEN','8','#075985',BLUEBG),('SÜRESİ GEÇEN','2',RED,REDBG),('TAMAMLANAN','46','#166534',GREENBG)]
        for k,(a,b,fg,bg) in enumerate(st):
            x=90+(k%2)*475; y=620+(k//2)*245; card(d,(x,y,x+425,y+205)); d.text((x+35,y+35),a,font=F(18,True),fill=MUTED); d.text((x+35,y+78),b,font=F(62,True),fill=fg); pill(d,(x+255,y+120,x+390,y+165),'Detay',bg,fg,16)
        card(d,(90,1140,990,1480)); d.text((130,1185),'Bugünkü eğitim hareketleri',font=F(28,True),fill=INK); yy=1260
        for s in ['Akü-Batarya • 3 çalışan','Metal-Makine • 8 çalışan','Temel Ortak İSG • 12 çalışan']: d.ellipse((135,yy+5,155,yy+25),fill=ACCENT2); d.text((175,yy),s,font=F(21,True),fill=INK); yy+=75
    else:
        d.text((70,360),'İSG YÖNETİMİNDE',font=F(34,True),fill='#8CE0E3'); d.text((70,425),'DİJİTAL KONTROL',font=F(66,True),fill=WHITE); card(d,(70,740,1010,1140)); d.text((120,805),'HEMEN KEŞFEDİN',font=F(22,True),fill=ACCENT); d.text((120,865),'www.isgsuite.tr',font=F(54,True),fill=INK); pill(d,(120,970,620,1035),'Eğitimler  ›  Uzaktan Eğitim',PALE,ACCENT,18); d.rounded_rectangle((150,1260,930,1395),28,fill=ACCENT2); d.text((255,1300),'İ S G SUITE • UZAKTAN EĞİTİM',font=F(26,True),fill=WHITE)
    caption(d,caps[i-1],dark); im.convert('RGB').save(OUT/f'scene_{i:02d}.png',quality=95)

for i in range(1,13): scene(i)
print('12 scenes rendered')
