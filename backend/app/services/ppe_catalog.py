"""PRO KKD kategori / tür kataloğu."""

KKD_KATEGORILERI: dict[str, list[str]] = {
    "Baş Koruyucular": [
        "Baret", "Elektrikçi Bareti", "Dağcı Bareti", "Vizörlü Baret", "Kaynakçı Başlığı", "Darbe Koruyucu Şapka",
    ],
    "Göz ve Yüz Koruyucular": [
        "Koruyucu Gözlük", "Toz Gözlüğü", "Kimyasal Gözlük", "Kaynak Gözlüğü", "Kaynak Maskesi",
        "Şeffaf Yüz Siperi", "Taşlama Siperi", "Elektrik Ark Siperi",
    ],
    "Solunum Koruyucular": [
        "Cerrahi Maske", "FFP1 Maske", "FFP2 Maske", "FFP3 Maske", "Yarım Yüz Maske", "Tam Yüz Gaz Maskesi",
        "Organik Buhar Filtresi", "Asit Gaz Filtresi", "Amonyak Filtresi", "Kombine Filtre", "Toz Filtresi",
        "Motorlu Solunum Sistemi", "Temiz Hava Beslemeli Maske",
    ],
    "İşitme Koruyucular": [
        "Kulak Tıkacı", "Kulaklık", "Baret Tipi Kulaklık", "Elektronik Gürültü Önleyici Kulaklık",
    ],
    "El Koruyucular": [
        "Pamuk Eldiven", "Deri Eldiven", "Nitril Eldiven", "Lateks Eldiven", "PVC Eldiven", "Kimyasal Eldiven",
        "Kaynakçı Eldiveni", "Kesilmeye Dayanıklı Eldiven", "Isıya Dayanıklı Eldiven", "Soğuk Ortam Eldiveni",
        "Elektrikçi Eldiveni", "Titreşim Önleyici Eldiven",
    ],
    "Vücut Koruyucular": [
        "İş Önlüğü", "İş Elbisesi", "İş Pantolonu", "İş Montu", "İş Tişörtü", "Reflektif Yelek", "Reflektif Mont",
        "Yağmurluk", "Kimyasal Koruyucu Tulum", "Tek Kullanımlık Tulum", "Kaynakçı Deri Önlüğü",
        "Isı Koruyucu Elbise", "Alüminize Elbise", "Soğuk Hava Elbisesi", "Antistatik Elbise",
        "Ark Flash Elbisesi", "Gıda Önlüğü",
    ],
    "Ayak Koruyucular": [
        "İş Ayakkabısı S1", "İş Ayakkabısı S1P", "İş Ayakkabısı S2", "İş Ayakkabısı S3", "İş Ayakkabısı S5",
        "Çelik Burunlu Bot", "Diz Altı Çizme", "PVC Çizme", "Kimyasal Çizme", "Elektrikçi Ayakkabısı",
        "Kaymaz Ayakkabı", "Gıda Çizmesi", "Dielektrik Bot",
    ],
    "Yüksekte Çalışma": [
        "Emniyet Kemeri", "Paraşüt Tipi Emniyet Kemeri", "Çift Kollu Lanyard", "Tek Kollu Lanyard",
        "Şok Emicili Lanyard", "Yaşam Hattı Halatı", "Düşüş Durdurucu", "Karabina", "Ankraj Sapanı",
        "Ankraj Noktası", "Kurtarma Kiti", "İniş Cihazı",
    ],
    "Elektrik İşleri": [
        "İzole Halı", "İzole Eldiven", "İzole Ayakkabı", "Ark Flash Siperi", "Ark Flash Elbisesi",
        "Gerilim Dedektörü", "İzole Çubuk",
    ],
    "Kimyasal Çalışmalar": [
        "Kimyasal Tulum", "Kimyasal Çizme", "Kimyasal Eldiven", "Kimyasal Gözlük", "Kimyasal Siperi", "Solunum Seti",
    ],
    "Kaynak İşleri": [
        "Kaynak Maskesi", "Kaynak Gözlüğü", "Kaynak Eldiveni", "Kaynak Kolluğu", "Kaynak Tozluğu",
        "Deri Önlük", "Kaynak Ceketi",
    ],
    "İnşaat": [
        "İnşaat Bareti", "Reflektif Yelek", "İş Ayakkabısı S3", "Emniyet Kemeri", "Toz Maskesi", "Dizlik", "Eldiven",
    ],
    "Forklift / Lojistik": ["Reflektif Yelek", "Çelik Burunlu Ayakkabı", "Eldiven", "Baret", "Yağmurluk"],
    "Laboratuvar": ["Laboratuvar Önlüğü", "Kimyasal Eldiven", "Kimyasal Gözlük", "Yüz Siperi", "Solunum Maskesi"],
    "Gıda": ["Bone", "Galoş", "Kolluk", "Önlük", "Maske", "Kaymaz Ayakkabı"],
    "Diğer": ["Diğer KKD"],
}

STATUS_LABELS = {
    "teslim": "Teslim Edildi",
    "yenilenecek": "Yenilenecek",
    "iade": "İade Alındı",
    "kayip": "Kayıp / Hasarlı",
}


def catalog_payload() -> dict:
    return {
        "categories": [
            {"name": name, "types": types}
            for name, types in KKD_KATEGORILERI.items()
        ],
        "statuses": [
            {"code": code, "label": label}
            for code, label in STATUS_LABELS.items()
        ],
    }


def status_label(code: str | None) -> str:
    return STATUS_LABELS.get((code or "teslim").strip(), "Teslim Edildi")
