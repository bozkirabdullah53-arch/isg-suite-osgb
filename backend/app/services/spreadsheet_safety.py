"""Shared export boundary: stored text must never become spreadsheet code."""
from __future__ import annotations

import csv
from openpyxl import Workbook


def safe_csv_value(value):
    if not isinstance(value, str):
        return value
    if value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


class SafeCsvWriter:
    def __init__(self, stream):
        self._writer = csv.writer(stream)

    def writerow(self, values):
        return self._writer.writerow([safe_csv_value(value) for value in values])


def save_export_workbook(workbook: Workbook, destination) -> None:
    """These reports export values, not executable formulas.

    Preserve the exact text and all numeric/date types, styles and validation.
    Explicit string cells also protect formula text assigned through ws.append.
    Conditional formatting and validation formulas are left intact.
    """
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = "s"
    workbook.save(destination)
