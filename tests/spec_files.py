"""Specifications for tests: the supplier's real files and small made-up ones."""
import io
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

FIXTURES = Path(__file__).parent / "fixtures"
RUB = FIXTURES / "spec_618E_7_rub.xlsm"
EUR = FIXTURES / "spec_618E_7_eur.xlsm"

HEADER = ["№", "Код", "Артикул", "Наименование", "Цвет", "Длина", "Ед. изм.", "Кол-во"]


def _column(index: int) -> str:
    letters = ""
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(ord("A") + rest) + letters
    return letters


def make_xlsx(rows: list[list], sheet_extra: str = "") -> bytes:
    """A minimal workbook with one sheet; strings are inline, numbers are numbers."""
    xml_rows = []
    for r, row in enumerate(rows, start=1):
        cells = []
        for c, value in enumerate(row, start=1):
            if value is None:
                continue
            ref = f"{_column(c)}{r}"
            if isinstance(value, (int, float)):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        xml_rows.append(f'<row r="{r}">{"".join(cells)}</row>')
    sheet = (
        f'<?xml version="1.0" encoding="UTF-8"?>{sheet_extra}'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(xml_rows)}</sheetData></worksheet>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Лист1" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()


def make_spec(items: list[list], number: str = "T-1", day: str = "01.09.2026") -> bytes:
    """A specification in the supplier's layout with the given item rows (without the "№" column)."""
    rows = [
        ["Поставщик-продавец (Грузоотправитель):"],
        ['ООО "Поставщик"'],
        [],
        [f"Спецификация № {number} от {day}г."],
        HEADER,
        *[[i, *item] for i, item in enumerate(items, start=1)],
        ["Итого:"],
        ["Срок поставки до:", None, None, "01.12.2026"],
    ]
    return make_xlsx(rows)
