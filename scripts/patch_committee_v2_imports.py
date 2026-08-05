from pathlib import Path

path = Path("frontend/src/main.jsx")
text = path.read_text(encoding="utf-8")

old_eyas = "import {EyasDigitalApprovalPage} from './eyas_digital_approval';"
new_eyas = "import {EyasDigitalApprovalPage} from './eyas_digital_approval_v2';"
if old_eyas in text:
    text = text.replace(old_eyas, new_eyas, 1)
elif new_eyas not in text:
    raise SystemExit("EYAS import marker not found")

if "  OhsCommitteePage,\n" in text:
    text = text.replace("  OhsCommitteePage,\n", "", 1)

committee_import = "import {OhsCommitteePage} from './ohs_committee_page';"
if committee_import not in text:
    marker = "} from './compliance_registers';"
    if marker not in text:
        raise SystemExit("compliance_registers import marker not found")
    text = text.replace(marker, f"{marker}\n{committee_import}", 1)

path.write_text(text, encoding="utf-8")
print("committee v2 imports applied")
