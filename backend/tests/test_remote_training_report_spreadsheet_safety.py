from io import BytesIO

from openpyxl import load_workbook

from app.services.remote_training_reports import build_employee_account_credentials_xlsx


def test_credentials_export_keeps_untrusted_text_as_text():
    payload = '=HYPERLINK("https://attacker.invalid","click")'
    output = build_employee_account_credentials_xlsx(
        [
            {
                "employee_name": payload,
                "employee_id": 7,
                "username": "=1+1",
                "temporary_password": "+cmd|' /C calc'!A0",
                "status": "@SUM(A1)",
            }
        ],
        company_name=payload,
    )

    workbook = load_workbook(BytesIO(output), data_only=False)
    sheet = workbook.active
    for coordinate, expected in {
        "A2": payload,
        "B2": payload,
        "D2": "=1+1",
        "E2": "+cmd|' /C calc'!A0",
        "F2": "@SUM(A1)",
    }.items():
        cell = sheet[coordinate]
        assert cell.value == expected
        assert cell.data_type == "s"
