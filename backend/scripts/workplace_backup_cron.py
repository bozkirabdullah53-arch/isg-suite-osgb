import json
from dataclasses import asdict
from datetime import datetime
from urllib.request import Request, urlopen
from app.core.config import settings, workplace_backups_active
from app.core.database import SessionLocal
from app.services.workplace_backup import run_scheduled_company_backups
def main():
    if not workplace_backups_active(): print('{"status":"disabled"}'); return 0
    if settings.workplace_backup_trigger_url:
        request = Request(
            settings.workplace_backup_trigger_url,
            method="POST",
            headers={"X-Workplace-Backup-Token": settings.workplace_backup_cron_token},
        )
        with urlopen(request, timeout=3600) as response:
            print(response.read().decode("utf-8"))
        return 0
    print(json.dumps(asdict(run_scheduled_company_backups(SessionLocal, now=datetime.utcnow())), separators=(",", ":"), sort_keys=True)); return 0
if __name__ == "__main__": raise SystemExit(main())
