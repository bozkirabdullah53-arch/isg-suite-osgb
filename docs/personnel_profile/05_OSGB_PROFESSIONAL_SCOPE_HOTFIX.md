# OSGB profesyonel dijital kart kapsam düzeltmesi

## Kesin kapsam

Dijital Personel Kartı OSGB ekranında yalnız OSGB'nin kendi aktif İSG profesyonelleri için çalışır:

- İş güvenliği uzmanı
- İşyeri hekimi
- Diğer sağlık personeli

Hizmet verilen işyerlerinin `Employee` kayıtları OSGB kart listesine alınmaz. Bir profesyonelin herhangi bir işyerine atanmış olması OSGB kadrosunda görünme şartı değildir; kaynak kayıt `isg_professionals.osgb_id` değeridir.

## Korunan alanlar

- İşyeri personel ekranları değiştirilmez.
- Mevcut çalışan, eğitim, sağlık ve görevlendirme akışları değiştirilmez.
- Önceden oluşturulmuş işyeri çalışanı profil kökleri silinmez; OSGB arayüzünden erişilmez.
- Değişiklik veri silmez.
