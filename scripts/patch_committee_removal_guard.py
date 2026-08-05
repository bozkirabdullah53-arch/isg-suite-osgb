from pathlib import Path

path = Path("frontend/src/ohs_committee_page.jsx")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        "import React, {useEffect, useMemo, useState} from 'react';",
        "import React, {useEffect, useMemo, useRef, useState} from 'react';",
    ),
    (
        "  const [removingMember, setRemovingMember] = useState(null);\n",
        "  const [removingMember, setRemovingMember] = useState(null);\n"
        "  const removalInFlight = useRef(false);\n",
    ),
    (
        "    if (!removingMember || busy) return;\n",
        "    if (!removingMember || busy || removalInFlight.current) return;\n",
    ),
    (
        "    setBusy(true); setErr(''); setSuccess('');\n"
        "    try {\n"
        "      const result = await api(`/ohs-committee/members/${removingMember.id}/remove`, {\n",
        "    removalInFlight.current = true;\n"
        "    setBusy(true); setErr(''); setSuccess('');\n"
        "    try {\n"
        "      const result = await api(`/ohs-committee/members/${removingMember.id}/remove`, {\n",
    ),
    (
        "    } finally {\n"
        "      setBusy(false);\n"
        "    }\n"
        "  }\n\n"
        "  async function saveMeeting(event) {\n",
        "    } finally {\n"
        "      removalInFlight.current = false;\n"
        "      setBusy(false);\n"
        "    }\n"
        "  }\n\n"
        "  async function saveMeeting(event) {\n",
    ),
]
for old, new in replacements:
    if old in text:
        text = text.replace(old, new, 1)
    elif new not in text:
        raise SystemExit(f"marker not found: {old[:100]!r}")

path.write_text(text, encoding="utf-8")
print("committee removal guard applied")
