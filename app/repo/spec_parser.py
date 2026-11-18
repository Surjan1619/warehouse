"""
Reading a supplier's specification (an Excel .xlsx / .xlsm file) into rows.

Pure functions, no database: `parse_specification(data)` returns what the
document says and how each row would go into stock. Matching rows against the
catalogue and putting them into stock is done in `document_import`.

The file is read as what it is, a zip of XML parts, with the standard library
only. Macros in .xlsm files are never run: only cell values are read.

What is expected of the document (as in the specifications of the supplier):
- somewhere a cell "Спецификация № 618E/7 от 03.08.2026г." gives the number and date;
- a header row with at least "Наименование", "Ед. изм." and "Кол-во";
  "Код", "Артикул", "Цвет", "Длина" are used when present;
- item rows follow the header up to the "Итого" row.

A row with a length (in metres) and the unit "м" is cuttable stock: its quantity
is metres in total and becomes quantity / length identical pieces. Any other row
is a piece good counted in its own unit ("шт", "пар", "кмт"): 100 pairs stay 100.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
from xml.etree import ElementTree

from app.core.errors import DomainError

MAX_FILE_BYTES = 5 * 1024 * 1024
# A real specification unpacks to a few hundred kilobytes; this stops zip bombs
MAX_PART_BYTES = 20 * 1024 * 1024
MAX_ROWS = 2000

STOCK = "stock"
GOODS = "goods"

PIECE_UNITS = ("шт", "пар", "кмт")
METRES = "м"

# Problems with a row; the row is shown but cannot be put into stock
NO_NAME = "no_name"
NO_QUANTITY = "no_quantity"
BAD_LENGTH = "bad_length"
UNKNOWN_UNIT = "unknown_unit"
METRES_WITHOUT_LENGTH = "metres_without_length"
NOT_WHOLE_PIECES = "not_whole_pieces"
FRACTIONAL_QUANTITY = "fractional_quantity"

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

# Header titles, compared without case, spaces and dots
_COLUMNS = {
    "code": ("код",),
    "article": ("артикул",),
    "name": ("наименование",),
    "color": ("цвет",),
    "length": ("длина",),
    "unit": ("едизм", "единицаизмерения", "едизмерения"),
    "quantity": ("колво", "количество"),
}
_REQUIRED = ("name", "unit", "quantity")

_SPEC_RE = re.compile(r"Спецификация\s*№\s*(\S+)\s+от\s+(\d{1,2})\.(\d{1,2})\.(\d{4})", re.IGNORECASE)
_SUPPLIER_LABEL = "поставщик"


@dataclass
class SpecRow:
    """One item row of the document and what it would become in stock."""

    line: int  # the row number in Excel, to find it in the file
    code: str | None
    article: str | None
    name: str
    color: str | None
    unit: str
    quantity: Decimal | None
    length_mm: int | None
    kind: str | None = None  # STOCK or GOODS; None when the row has a problem
    pieces: int | None = None  # STOCK: how many pieces of length_mm
    count: int | None = None  # GOODS: how many units
    problem: str | None = None

    @property
    def title(self) -> str:
        """Name for a new material or product: "Шина направляющая GR90x34IE, цвет 213"."""
        text = self.name
        if self.article and self.article not in text:
            text = f"{text} {self.article}"
        if self.color:
            text = f"{text}, цвет {self.color}"
        return text[:100]


@dataclass
class Specification:
    number: str | None
    date: date | None
    supplier: str | None
    rows: list[SpecRow] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Every row can go into stock."""
        return bool(self.rows) and all(row.problem is None for row in self.rows)


# --- Reading the workbook ---

def _read_part(archive: zipfile.ZipFile, name: str) -> bytes:
    info = archive.getinfo(name)
    if info.file_size > MAX_PART_BYTES:
        raise DomainError("The file is too large", status_code=422)
    data = archive.read(name)
    # Cell values never need a DTD; refusing it rules out entity expansion tricks
    if b"<!DOCTYPE" in data[:2048].upper() or b"<!ENTITY" in data.upper():
        raise DomainError("Not an Excel file", status_code=422)
    return data


def _column_index(ref: str) -> int:
    """"C12" -> 3."""
    index = 0
    for char in ref:
        if not char.isalpha():
            break
        index = index * 26 + (ord(char.upper()) - ord("A") + 1)
    return index


def _row_number(ref: str) -> int:
    digits = "".join(char for char in ref if char.isdigit())
    return int(digits) if digits else 0


def _first_sheet(archive: zipfile.ZipFile) -> str:
    """Path of the first worksheet, as the workbook lists them."""
    workbook = ElementTree.fromstring(_read_part(archive, "xl/workbook.xml"))
    rels = ElementTree.fromstring(_read_part(archive, "xl/_rels/workbook.xml.rels"))
    targets = {rel.get("Id"): rel.get("Target") for rel in rels.iter(f"{_PKG_REL_NS}Relationship")}
    sheets = workbook.find(f"{_NS}sheets")
    if sheets is None or len(sheets) == 0:
        raise DomainError("The file has no sheets", status_code=422)
    target = targets.get(sheets[0].get(f"{_REL_NS}id")) or ""
    target = target.lstrip("/")
    return target if target.startswith("xl/") else f"xl/{target}"


def read_cells(data: bytes) -> dict[int, dict[int, str]]:
    """The first sheet as {row number: {column number: text}}; empty cells are left out."""
    if len(data) > MAX_FILE_BYTES:
        raise DomainError("The file is too large", status_code=422)
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile:
        raise DomainError("Not an Excel file", status_code=422) from None
    try:
        with archive:
            names = set(archive.namelist())
            strings: list[str] = []
            if "xl/sharedStrings.xml" in names:
                for item in ElementTree.fromstring(_read_part(archive, "xl/sharedStrings.xml")).iter(f"{_NS}si"):
                    strings.append("".join(t.text or "" for t in item.iter(f"{_NS}t")))
            sheet = _first_sheet(archive)
            if sheet not in names:
                raise DomainError("Not an Excel file", status_code=422)
            root = ElementTree.fromstring(_read_part(archive, sheet))
    except (KeyError, ElementTree.ParseError):
        raise DomainError("Not an Excel file", status_code=422) from None

    cells: dict[int, dict[int, str]] = {}
    for row in root.iter(f"{_NS}row"):
        for cell in row.iter(f"{_NS}c"):
            ref = cell.get("r") or ""
            kind = cell.get("t")
            value = cell.find(f"{_NS}v")
            if kind == "inlineStr":
                text = "".join(t.text or "" for t in cell.iter(f"{_NS}t"))
            elif value is None or value.text is None:
                continue
            elif kind == "s":
                try:
                    text = strings[int(value.text)]
                except (ValueError, IndexError):
                    continue
            else:
                text = value.text
            text = text.strip()
            if text:
                cells.setdefault(_row_number(ref), {})[_column_index(ref)] = text
        if len(cells) > MAX_ROWS:
            raise DomainError("The file is too large", status_code=422)
    return cells


# --- Understanding the document ---

def _key(text: str) -> str:
    return re.sub(r"[\s.\-]", "", text).lower()


def _find_header(cells: dict[int, dict[int, str]]) -> tuple[int, dict[str, int]]:
    for number in sorted(cells):
        found: dict[str, int] = {}
        for column, text in cells[number].items():
            key = _key(text)
            for name, titles in _COLUMNS.items():
                if key in titles and name not in found:
                    found[name] = column
        if all(name in found for name in _REQUIRED):
            return number, found
    raise DomainError("No table of goods in the file", status_code=422)


def _empty(text: str | None) -> bool:
    return text is None or text.strip() in ("", "-", "—", "–")


def _decimal(text: str | None) -> Decimal | None:
    if _empty(text):
        return None
    try:
        value = Decimal(text.replace(",", ".").replace(" ", "").replace(" ", ""))
    except InvalidOperation:
        return None
    # Excel keeps 448.5 as 448.49999999999994 now and then
    return value.quantize(Decimal("0.000001")).normalize()


def _whole(value: Decimal) -> int | None:
    return int(value) if value == value.to_integral_value() else None


def _classify(row: SpecRow, length_text: str | None) -> None:
    if not row.name:
        row.problem = NO_NAME
        return
    if row.quantity is None or row.quantity <= 0:
        row.problem = NO_QUANTITY
        return
    if not _empty(length_text) and row.length_mm is None:
        row.problem = BAD_LENGTH
        return
    if row.unit == METRES:
        if row.length_mm is None:
            row.problem = METRES_WITHOUT_LENGTH
            return
        pieces = row.quantity * 1000 / row.length_mm
        if _whole(pieces) is None:
            row.problem = NOT_WHOLE_PIECES
            return
        row.kind, row.pieces = STOCK, int(pieces)
        return
    if row.unit not in PIECE_UNITS:
        row.problem = UNKNOWN_UNIT
        return
    count = _whole(row.quantity)
    if count is None:
        row.problem = FRACTIONAL_QUANTITY
        return
    row.kind, row.count = GOODS, count


def _length_mm(text: str | None) -> int | None:
    metres = _decimal(text)
    if metres is None or metres <= 0:
        return None
    return _whole(metres * 1000)


def _unit(text: str | None) -> str:
    unit = (text or "").strip().lower().rstrip(".")
    return {"штук": "шт", "штука": "шт", "пара": "пар", "пары": "пар", "компл": "кмт", "к-т": "кмт", "кт": "кмт",
            "метр": METRES, "m": METRES}.get(unit, unit)


def _heading(cells: dict[int, dict[int, str]], header_row: int) -> tuple[str | None, date | None, str | None]:
    number = spec_date = supplier = None
    rows = sorted(r for r in cells if r < header_row)
    for index, row_number in enumerate(rows):
        for column, text in sorted(cells[row_number].items()):
            match = _SPEC_RE.search(text)
            if match and number is None:
                number = match.group(1)
                day, month, year = (int(match.group(i)) for i in (2, 3, 4))
                try:
                    spec_date = date(year, month, day)
                except ValueError:
                    spec_date = None
            if supplier is None and _key(text).startswith(_SUPPLIER_LABEL) and index + 1 < len(rows):
                below = cells[rows[index + 1]].get(column)
                if below:
                    supplier = below.splitlines()[0][:255]
    return number, spec_date, supplier


def parse_specification(data: bytes) -> Specification:
    cells = read_cells(data)
    header_row, columns = _find_header(cells)
    number, spec_date, supplier = _heading(cells, header_row)
    spec = Specification(number=number, date=spec_date, supplier=supplier)

    def get(row: dict[int, str], name: str) -> str | None:
        column = columns.get(name)
        return row.get(column) if column else None

    for line in sorted(r for r in cells if r > header_row):
        row = cells[line]
        first = row.get(min(row)) if row else ""
        if _key(first).startswith("итого"):
            break
        name = (get(row, "name") or "").strip()
        quantity_text = get(row, "quantity")
        if not name and _empty(quantity_text):
            continue  # a blank or a remark row inside the table
        length_text = get(row, "length")
        code, article, color = (get(row, key) for key in ("code", "article", "color"))
        item = SpecRow(
            line=line,
            code=None if _empty(code) else code.strip()[:50],
            article=None if _empty(article) else article.strip()[:50],
            name=name[:100],
            color=None if _empty(color) else color.strip()[:50],
            unit=_unit(get(row, "unit")),
            quantity=_decimal(quantity_text),
            length_mm=_length_mm(length_text),
        )
        _classify(item, length_text)
        spec.rows.append(item)

    if not spec.rows:
        raise DomainError("No goods in the file", status_code=422)
    return spec
