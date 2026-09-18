# İşyeri Yedekleri Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** İşyeri kullanıcısının yalnız kendi firmasının verilerini sol menüden şifreli olarak yedekleyip indirebilmesini ve sistemin her gece 30 gün saklamalı otomatik firma yedekleri üretmesini sağlamak.

**Architecture:** Mevcut `EisaArchiveRecord`, şifreleme, checksum ve arşiv güvenliği korunacak; v4 firma yedeği ayrı ve açık bir domain kayıt listesiyle üretilecek. Yeni `/workplace-backups` API'si hedef firmayı oturumdan türetecek, Render Cron ise aynı servisi kullanıcı endpoint'ine uğramadan bütün aktif firmalar için idempotent biçimde çalıştıracak.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL/SQLite testleri, ReportLab mevcut bağımlılıkları, React 19, Vite, Vitest, Render Blueprint/Cron.

**Spec:** `docs/superpowers/specs/2026-09-18-workplace-backups-design.md`

## Global Constraints

- Otomatik yedek her gece Türkiye saatiyle 02.00'de çalışır.
- Tamamlanmış otomatik yedekler 30 gün tutulur; manuel yedekler otomatik silinmez.
- Her yedek tam olarak bir `company_id` kapsamındadır; OSGB geneli yedek işyeri API'sinden üretilemez.
- İşyeri kullanıcısına canlı geri yükleme veya yedek silme yetkisi verilmez.
- Şifreleme ve SHA-256 doğrulaması mevcut güvenlik servislerinden yeniden kullanılır.
- Sağlık alanları veritabanında tutulduğu biçimde yedeklenir; sırlar, parolalar ve oturum belirteçleri dışarı aktarılmaz.
- `WORKPLACE_BACKUPS_ENABLED=false` iken menü gizli, yeni API uçları 404 ve cron no-op olur.
- Mevcut `/archives` API'si, v3 yedekleri ve çalışan modüller geriye uyumlu kalır.
- Üretim kodu yalnız önce başarısız olduğu görülen testten sonra yazılır.

---

## Dosya haritası

- `backend/app/models/entities.py`: yedek kaynağı/durumu ve idempotency alanları.
- `backend/alembic/versions/0114_workplace_backups.py`: geriye uyumlu nullable sütunlar ve indeks.
- `backend/app/core/config.py`: özellik bayrağı, saklama günü ve zamanlama ayarları.
- `backend/app/services/workplace_backup.py`: firma kapsamı, v4 arşiv üretimi, atomik yazma, saklama ve gece orkestrasyonu.
- `backend/app/api/workplace_backups.py`: yalnız bağlı firma için listeleme, durum, manuel oluşturma, indirme ve içerik özeti.
- `backend/app/main.py`: yeni router kaydı.
- `backend/scripts/workplace_backup_cron.py`: Render Cron giriş noktası.
- `backend/tests/test_workplace_backup_service.py`: kapsam, v4 içerik, idempotency, hata izolasyonu ve retention.
- `backend/tests/test_workplace_backups_api.py`: rol ve çapraz firma güvenliği.
- `frontend/src/workplace_backups_logic.js`: API yanıtı normalizasyonu ve görünüm yardımcıları.
- `frontend/src/workplace_backups_logic.test.js`: istemci birim testleri.
- `frontend/src/workplace_backups.jsx`: Yedeklerim sayfası.
- `frontend/src/workplace_backups.css`: sayfaya özel stiller.
- `frontend/src/main.jsx`: menü, sayfa kaydı ve Güvenlik sayfasındaki tekrarın kaldırılması.
- `render.yaml`: her gece çalışan Cron Job ve güvenli varsayılan ayarlar.

---

### Task 1: Geriye uyumlu yedek çalışma metadatası

**Files:**
- Modify: `backend/app/models/entities.py`
- Create: `backend/alembic/versions/0114_workplace_backups.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_workplace_backup_service.py`

**Interfaces:**
- Produces: `BackupSource`, `BackupStatus`, `EisaArchiveRecord.backup_source`, `backup_status`, `started_at`, `completed_at`, `error_summary`, `schedule_key`.
- Produces: `workplace_backups_active() -> bool`.

- [ ] **Step 1: Model ve bayrak beklentisini yazan başarısız testi ekle**

```python
def test_workplace_backup_defaults_and_force_off(monkeypatch):
    row = EisaArchiveRecord(
        kind=ArchiveKind.TENANT_BACKUP,
        storage_path="x.zip",
        company_id=10,
    )
    assert row.backup_source == BackupSource.MANUAL
    assert row.backup_status == BackupStatus.COMPLETED
    monkeypatch.setattr(settings, "workplace_backups_enabled", True)
    monkeypatch.setattr(settings, "workplace_backups_force_off", True)
    assert workplace_backups_active() is False
```

- [ ] **Step 2: Testin eksik enum/alan nedeniyle başarısız olduğunu doğrula**

Run: `cd backend && pytest tests/test_workplace_backup_service.py::test_workplace_backup_defaults_and_force_off -q`

Expected: FAIL; `BackupSource` veya alanlar henüz tanımlı değil.

- [ ] **Step 3: Enum, nullable sütunlar ve ayarları ekle**

```python
class BackupSource(str, enum.Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"

class BackupStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
```

`EisaArchiveRecord` üzerine enum varsayılanları, zamanlar, 1000 karakterlik hata
özeti ve nullable/unique `schedule_key` ekle. Config varsayılanları:

```python
workplace_backups_enabled: bool = False
workplace_backups_force_off: bool = False
workplace_backup_retention_days: int = 30
workplace_backup_hour_tr: int = 2
```

Migration mevcut satırları `manual/completed` olarak backfill etsin; `schedule_key`
için unique indeks kullansın ve downgrade yalnız eklenen alanları kaldırsın.

- [ ] **Step 4: Model testi ve Alembic head kontrolünü çalıştır**

Run: `cd backend && pytest tests/test_workplace_backup_service.py::test_workplace_backup_defaults_and_force_off -q && alembic heads`

Expected: PASS ve tek head `0114_workplace_backups`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/entities.py backend/app/core/config.py backend/alembic/versions/0114_workplace_backups.py backend/tests/test_workplace_backup_service.py
git commit -m "feat: add workplace backup execution metadata"
```

---

### Task 2: Firma kapsamlı v4 yedek üreticisi

**Files:**
- Create: `backend/app/services/workplace_backup.py`
- Test: `backend/tests/test_workplace_backup_service.py`
- Modify: `backend/app/services/archive_store.py`

**Interfaces:**
- Consumes: Task 1 enum ve model alanları.
- Produces: `create_company_backup(db: Session, *, company_id: int, actor_user_id: int | None, source: BackupSource, schedule_key: str | None = None) -> EisaArchiveRecord`.
- Produces: `read_company_backup_manifest(row: EisaArchiveRecord) -> dict[str, object]`.

- [ ] **Step 1: İki firmalı sızıntı testini önce yaz**

```python
def test_v4_backup_contains_only_target_company(db, tmp_path, monkeypatch):
    first, second = seed_two_companies_with_all_domains(db)
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path / "backups"))
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    row = create_company_backup(
        db, company_id=first.id, actor_user_id=None,
        source=BackupSource.MANUAL,
    )
    payload = decrypt_and_read_backup(row)
    assert payload["manifest.json"]["format_version"] == 4
    assert payload["manifest.json"]["companies"] == [{"id": first.id, "name": first.name}]
    assert str(second.id) not in json.dumps(payload, ensure_ascii=False)
```

Fixture; personel, sağlık, risk, eğitim, DÖF, KKD, yıllık plan, kurul, tatbikat,
acil durum, izin, taşeron ve ziyaretçi alanlarının her iki firma kaydını üretmeli.

- [ ] **Step 2: Testi çalıştırıp servis eksikliğiyle başarısız olduğunu doğrula**

Run: `cd backend && pytest tests/test_workplace_backup_service.py::test_v4_backup_contains_only_target_company -q`

Expected: FAIL; `create_company_backup` tanımlı değil.

- [ ] **Step 3: Açık domain registry ve serializer'ları uygula**

```python
@dataclass(frozen=True)
class BackupDomain:
    name: str
    filename: str
    load: Callable[[Session, int], Sequence[object]]
    serialize: Callable[[Sequence[object]], object]

COMPANY_BACKUP_DOMAINS: tuple[BackupDomain, ...] = (
    BackupDomain("employees", "employees.json", load_employees, serialize_employees),
    BackupDomain("health_records", "health_records.json", load_health, serialize_health),
    # Tasarım belgesindeki her firma alanı burada açıkça kayıt edilir.
)
```

Her loader `company_id` filtresini kendi sorgusunda uygulasın. Alt kayıtlar
eğitim/kurul gibi üst kayıt kimliklerinden türetilsin. Kullanıcı, parola,
refresh token, MFA sırrı ve uygulama secret'ı için domain tanımlanmasın.

- [ ] **Step 4: Atomik arşiv üretimi ve mevcut kripto yardımcılarını bağla**

Geçici dosyayı aynı klasörde `.partial-{uuid4().hex}.zip` olarak oluştur; manifest ve
domain JSON dosyaları ile yalnız `uploads/{company_id}/` altındaki dosyaları
ekle. Başarıda mevcut `_maybe_encrypt_file`, `_checksum` ve `_rel_store`
yardımcılarını kullanıp nihai ada `Path.replace()` uygula. Hata halinde partial
dosyayı kaldır, satırı `FAILED` yap ve 1000 karakteri aşmayan hata özeti yaz.

- [ ] **Step 5: Sızıntı, içerik ve hata testlerini çalıştır**

Run: `cd backend && pytest tests/test_workplace_backup_service.py -k "v4 or target_company or partial" -q`

Expected: PASS; ikinci firmanın benzersiz kimliği/adı hiçbir JSON veya dosya
yolunda bulunmaz, partial arşiv kalmaz.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/workplace_backup.py backend/app/services/archive_store.py backend/tests/test_workplace_backup_service.py
git commit -m "feat: create isolated v4 workplace backups"
```

---

### Task 3: Gece orkestrasyonu, idempotency ve 30 günlük saklama

**Files:**
- Modify: `backend/app/services/workplace_backup.py`
- Create: `backend/scripts/workplace_backup_cron.py`
- Test: `backend/tests/test_workplace_backup_service.py`

**Interfaces:**
- Produces: `run_scheduled_company_backups(db_factory: Callable[[], Session], *, now: datetime) -> BackupRunSummary`.
- Produces: `purge_expired_scheduled_backups(db: Session, *, cutoff: datetime) -> PurgeSummary`.
- `BackupRunSummary` alanları: `companies_seen`, `created`, `skipped`, `failed`, `purged`.

- [ ] **Step 1: Aynı gün tekrarı, firma hata izolasyonu ve retention testlerini yaz**

```python
def test_nightly_backup_is_idempotent_and_continues_after_company_failure(...):
    summary = run_scheduled_company_backups(factory, now=datetime(2026, 9, 18, 23, 0))
    again = run_scheduled_company_backups(factory, now=datetime(2026, 9, 18, 23, 5))
    assert summary.created == 2
    assert summary.failed == 1
    assert again.created == 0
    assert again.skipped == 2

def test_retention_deletes_only_old_completed_scheduled_backups(...):
    result = purge_expired_scheduled_backups(db, cutoff=datetime(2026, 8, 19))
    assert result.deleted == 1
    assert manual_backup_path.exists()
    assert failed_backup_row_is_preserved(db)
```

- [ ] **Step 2: Testlerin eksik orkestratör nedeniyle başarısız olduğunu doğrula**

Run: `cd backend && pytest tests/test_workplace_backup_service.py -k "nightly or retention" -q`

Expected: FAIL; orkestrasyon fonksiyonları yok.

- [ ] **Step 3: Firma başına session ve kararlı schedule key uygula**

```python
def schedule_key(company_id: int, now: datetime) -> str:
    tr_day = now.astimezone(ZoneInfo("Europe/Istanbul")).date().isoformat()
    return f"company:{company_id}:daily:{tr_day}"
```

Aktif firmaları kimlik sırasıyla sayfalı oku. Her firma için ayrı Session aç;
`IntegrityError` unique `schedule_key` yarışında skip sayılsın. Bir firma
hatasını kaydet, rollback yap ve sonraki firmayla devam et.

- [ ] **Step 4: Güvenli retention ve CLI girişini uygula**

Yalnız `TENANT_BACKUP + SCHEDULED + COMPLETED + completed_at < cutoff`
satırlarını işle. Dosya silinemezse satırı silme. CLI özellik kapalıysa JSON
`{"status":"disabled"}` yazıp 0 döndürsün; açıkken özet JSON yazsın ve yalnız
sistemsel başlangıç hatasında non-zero çıksın.

- [ ] **Step 5: Orkestrasyon testlerini çalıştır**

Run: `cd backend && pytest tests/test_workplace_backup_service.py -k "nightly or retention or schedule" -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/workplace_backup.py backend/scripts/workplace_backup_cron.py backend/tests/test_workplace_backup_service.py
git commit -m "feat: schedule and retain workplace backups"
```

---

### Task 4: Firma kimliğini istemciden kabul etmeyen işyeri API'si

**Files:**
- Create: `backend/app/api/workplace_backups.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_workplace_backups_api.py`

**Interfaces:**
- Consumes: `create_company_backup`, `read_company_backup_manifest`, mevcut checksum/resolve yardımcıları.
- Produces: `GET /workplace-backups`, `GET /workplace-backups/status`, `POST /workplace-backups`, `GET /workplace-backups/{id}/download`, `GET /workplace-backups/{id}/contents`.

- [ ] **Step 1: Yetki ve çapraz firma API testlerini yaz**

```python
def test_workplace_manager_can_backup_only_bound_company(client, seeded_users):
    token = login(client, seeded_users.workplace_manager)
    created = client.post("/api/v1/workplace-backups", headers=token, json={})
    assert created.status_code in (200, 202)
    rows = client.get("/api/v1/workplace-backups", headers=token).json()
    assert {row["company_id"] for row in rows} == {seeded_users.company_a.id}

def test_cross_company_backup_download_is_rejected(client, seeded_users, company_b_backup):
    response = client.get(
        f"/api/v1/workplace-backups/{company_b_backup.id}/download",
        headers=login(client, seeded_users.company_a_manager),
    )
    assert response.status_code in (403, 404)
```

Ayrıca hedef `company_id` içeren POST gövdesinin 422 olduğunu, restore yolu
bulunmadığını ve flag kapalıyken uçların 404 döndüğünü test et.

- [ ] **Step 2: Testleri çalıştırıp 404 ile başarısız olduklarını doğrula**

Run: `cd backend && pytest tests/test_workplace_backups_api.py -q`

Expected: FAIL; router henüz kayıtlı değil.

- [ ] **Step 3: Firma kapsamı çözümleyicisi ve router'ı uygula**

```python
def require_bound_workplace(user: User = Depends(get_current_user)) -> User:
    if not workplace_backups_active():
        raise HTTPException(404, "İşyeri yedekleri etkin değil.")
    if user.role not in {UserRole.COMPANY_ADMIN, UserRole.WORKPLACE_MANAGER} or not user.company_id:
        raise HTTPException(403, "Bu işlem yalnız bağlı işyeri hesabına açıktır.")
    return user
```

Her sorguda `EisaArchiveRecord.company_id == user.company_id` uygula. POST
şeması hedef kimliği içermesin. Liste varsayılan olarak son 500 kaydı tarih
azalan sırada döndürsün. `contents` yalnız doğrulanmış manifest özetini dönsün.

- [ ] **Step 4: API testlerini ve mevcut arşiv testlerini çalıştır**

Run: `cd backend && pytest tests/test_workplace_backups_api.py tests/test_archive_store.py tests/test_backup_restore.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/workplace_backups.py backend/app/main.py backend/tests/test_workplace_backups_api.py
git commit -m "feat: expose tenant-safe workplace backup API"
```

---

### Task 5: Sol menüde Yedeklerim sayfası

**Files:**
- Create: `frontend/src/workplace_backups_logic.js`
- Create: `frontend/src/workplace_backups_logic.test.js`
- Create: `frontend/src/workplace_backups.jsx`
- Create: `frontend/src/workplace_backups.css`
- Modify: `frontend/src/main.jsx`
- Modify: `frontend/eslint.config.js`

**Interfaces:**
- Produces: `normalizeWorkplaceBackups(payload)`, `formatBackupSize(bytes)`, `backupSourceLabel(source)`, `backupStatusLabel(status)`.
- Consumes: `/workplace-backups` API uçları ve mevcut `api`, `downloadFile`, `Page`, `Table` bileşenleri.

- [ ] **Step 1: Normalizasyon ve menü politikası testlerini yaz**

```javascript
it('normalizes scheduled backup state without company selectors', () => {
  const result = normalizeWorkplaceBackups([{id: 7, backup_source: 'scheduled', size_bytes: 2048}]);
  expect(result[0].sourceLabel).toBe('Otomatik');
  expect(result[0].sizeLabel).toBe('2 KB');
});

it('shows backups only to company-bound workplace roles', () => {
  expect(workplaceModulesForUser(boundWorkplaceUser)).toContain('workplace_backups');
  expect(modulesForUser(unboundCompanyAdmin)).not.toContain('workplace_backups');
});
```

- [ ] **Step 2: Testleri çalıştırıp eksik modül nedeniyle başarısızlığı doğrula**

Run: `cd frontend && npm test -- --run src/workplace_backups_logic.test.js src/workplace_user_policy.test.js`

Expected: FAIL; yardımcılar ve menü anahtarı yok.

- [ ] **Step 3: Saf yardımcıları ve sayfayı uygula**

Sayfa açılışta liste ve status'u paralel yüklesin. `Şimdi Yedekle` onayından
sonra POST atsın; 202 ise mevcut job status örüntüsüyle sonucu beklesin,
ardından listeyi yenilesin. Tablo sütunları tarih, kaynak, durum, boyut,
bütünlük ve işlemler olsun. İndir yalnız `completed`, İçeriği Gör salt okunur
manifest modalı için etkin olsun. Firma seçici veya restore/sil düğmesi ekleme.

- [ ] **Step 4: Menü ve tekrar kaldırma değişikliğini uygula**

`menuCatalog.workplace_backups = ['Yedeklerim', Download]` ekle ve yalnız bağlı
işyeri modül listelerine yerleştir. `pages` haritasına `WorkplaceBackupsPage`
ekle. Güvenlik sayfasındaki `Kurum Yedekleme` bölümünü işyeri hesapları için
render etme; global/OSGB mevcut görünümünü koru.

- [ ] **Step 5: İstemci testleri ve lint çalıştır**

Run: `cd frontend && npm test -- --run src/workplace_backups_logic.test.js src/workplace_user_policy.test.js && npx eslint src/workplace_backups_logic.js src/workplace_backups_logic.test.js src/workplace_backups.jsx`

Expected: PASS ve 0 error.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/workplace_backups_logic.js frontend/src/workplace_backups_logic.test.js frontend/src/workplace_backups.jsx frontend/src/workplace_backups.css frontend/src/main.jsx frontend/eslint.config.js
git commit -m "feat: add workplace backup center"
```

---

### Task 6: Render gece görevi ve güvenli dağıtım ayarları

**Files:**
- Modify: `render.yaml`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_render_workplace_backup_blueprint.py`

**Interfaces:**
- Consumes: `python -m scripts.workplace_backup_cron`.
- Produces: Render Cron `isg-suite-workplace-backups-nightly` with schedule `0 23 * * *`.

- [ ] **Step 1: Blueprint sözleşme testini yaz**

```python
def test_render_has_nightly_workplace_backup_cron():
    blueprint = yaml.safe_load(Path("../render.yaml").read_text())
    cron = next(s for s in blueprint["services"] if s["name"] == "isg-suite-workplace-backups-nightly")
    assert cron["type"] == "cron"
    assert cron["schedule"] == "0 23 * * *"
    assert cron["startCommand"] == "python -m scripts.workplace_backup_cron"
```

- [ ] **Step 2: Testi cron eksikliğiyle başarısız çalıştır**

Run: `cd backend && pytest tests/test_render_workplace_backup_blueprint.py -q`

Expected: FAIL; servis bulunamadı.

- [ ] **Step 3: Blueprint ve örnek ayarları ekle**

Cron web servisiyle aynı repo/root/runtime, `DATABASE_URL`, `BACKUP_DIR`,
`UPLOAD_DIR`, `SECRET_KEY`, `BACKUP_ENCRYPTION_KEY` ve nesne depolama ayarlarını
aynı env group/secret referanslarından alsın. İlk dağıtımda
`WORKPLACE_BACKUPS_ENABLED=false`, `WORKPLACE_BACKUP_RETENTION_DAYS=30` kullan.
Web/static frontend için `VITE_WORKPLACE_BACKUPS_ENABLED=false` ekle.

- [ ] **Step 4: Blueprint testi ve YAML parse kontrolünü çalıştır**

Run: `cd backend && pytest tests/test_render_workplace_backup_blueprint.py -q && python -c "import yaml; yaml.safe_load(open('../render.yaml', encoding='utf-8'))"`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add render.yaml backend/.env.example backend/tests/test_render_workplace_backup_blueprint.py
git commit -m "infra: schedule nightly workplace backups"
```

---

### Task 7: Uçtan uca güvenlik ve regresyon kapısı

**Files:**
- Modify only if a failing test identifies a defect in files from Tasks 1-6.
- Test: all files introduced or touched above.

**Interfaces:**
- Validates the complete feature; produces no new public interface.

- [ ] **Step 1: Hedefli backend güvenlik paketini çalıştır**

Run:

```bash
cd backend
pytest \
  tests/test_workplace_backup_service.py \
  tests/test_workplace_backups_api.py \
  tests/test_archive_store.py \
  tests/test_backup_restore.py \
  tests/test_tenant_backup_v3.py \
  -q
```

Expected: bütün testler PASS; skipped test varsa nedeni raporlanır.

- [ ] **Step 2: Frontend test, lint ve üretim derlemesini çalıştır**

Run:

```bash
cd frontend
npm test -- --run
npm run lint
npm run build
```

Expected: testlerde 0 failure, lintte 0 error, build exit 0. Mevcut uyarılar
ayrı raporlanır ve bu değişiklik yeni uyarı eklememelidir.

- [ ] **Step 3: Migration ve arşiv smoke testini çalıştır**

Run:

```bash
cd backend
alembic upgrade head
python -m scripts.workplace_backup_cron
```

Test ortamında flag kapalıysa CLI çıktısı tam olarak disabled olmalı. Flag açık
geçici veritabanı senaryosunda bir firma yedeği oluşturulmalı; manifest
`format_version=4`, `company_id` hedef firma ve checksum `ok` olmalı.

- [ ] **Step 4: Değişiklik kapsamını denetle**

Run: `git diff origin/master...HEAD --check && git status --short && git diff origin/master...HEAD --stat`

Expected: yalnız planlanan backend, frontend, migration, test, doküman ve
`render.yaml` dosyaları; üretilmiş `frontend/dist` değişikliği olmamalı.

- [ ] **Step 5: Son doğrulama commit'i (yalnız gerekli düzeltme varsa)**

```bash
git add backend/app backend/tests frontend/src render.yaml backend/.env.example
git commit -m "test: verify workplace backup rollout"
```

- [ ] **Step 6: PR ve kontrollü canlıya alma**

PR açıklamasına test çıktıları, migration, flag varsayılanları ve geri alma
adımlarını ekle. Merge sonrası önce migration ve flag kapalı smoke testini
doğrula; ardından backend ve frontend flaglerini aç. İlk manuel pilot firma
yedeğini indirip checksum/manifest kontrolü yaptıktan sonra cron servisini
etkinleştir. Çalışan modüllerde hata görülürse iki flagi kapat ve cron'u askıya
al; mevcut v3 kayıtlarını silme.
