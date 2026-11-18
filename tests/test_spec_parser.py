"""Reading a supplier's specification: on the real files and on made-up ones."""
from collections import Counter
from datetime import date
from decimal import Decimal

import pytest

from app.core.errors import DomainError
from app.repo import spec_parser as sp
from tests.spec_files import EUR, RUB, make_spec, make_xlsx


def by_line(spec, line):
    [row] = [r for r in spec.rows if r.line == line]
    return row


def test_real_specification_heading():
    spec = sp.parse_specification(RUB.read_bytes())
    assert spec.number == "618E/7"
    assert spec.date == date(2026, 8, 3)
    assert spec.supplier == 'ООО"Алютех Инкорпорейтед"'
    assert len(spec.rows) == 38  # rows 10..47, up to "Итого"
    assert spec.ok


def test_metres_become_pieces_of_the_given_length():
    spec = sp.parse_specification(RUB.read_bytes())
    profile = by_line(spec, 19)  # AG/77, 3045 m by 7 m
    assert (profile.code, profile.article, profile.color, profile.unit) == ("303001113", "AG/77", "113", "м")
    assert (profile.kind, profile.length_mm, profile.pieces) == (sp.STOCK, 7000, 435)
    box = by_line(spec, 27)  # SB45/300, 448.5 m by 6,5 m
    assert (box.length_mm, box.quantity, box.pieces) == (6500, Decimal("448.5"), 69)
    assert box.title == "Короб защитный роллетный SB45/300, цвет 213"

    stock = [r for r in spec.rows if r.kind == sp.STOCK]
    assert len(stock) == 21
    assert sum(r.pieces for r in stock) == 3075


def test_pairs_and_sets_keep_their_number():
    spec = sp.parse_specification(RUB.read_bytes())
    roller = by_line(spec, 10)
    assert (roller.kind, roller.unit, roller.count, roller.length_mm) == (sp.GOODS, "пар", 100, None)
    drive = by_line(spec, 42)
    assert (drive.unit, drive.count, drive.color) == ("кмт", 60, None)
    assert drive.title == "Внутривальный электропривод AM2-PP/60-15"
    assert {r.unit for r in spec.rows if r.kind == sp.GOODS} == {"шт", "пар", "кмт"}


def test_both_currencies_are_the_same_delivery():
    rub = sp.parse_specification(RUB.read_bytes())
    eur = sp.parse_specification(EUR.read_bytes())
    assert (rub.number, rub.date) == (eur.number, eur.date)

    def content(spec):
        return Counter((r.code, r.unit, r.quantity, r.length_mm) for r in spec.rows)

    # The rows come in a different order, the goods are the same
    assert content(rub) == content(eur)


def test_rows_with_problems_are_kept_and_marked():
    data = make_spec([
        ["1", "A/1", "Профиль", "113", "7", "м", 100],  # 100 m by 7 m is not whole pieces
        ["2", "B/1", "Ролик", "-", "-", "рулон", 5],
        ["3", "C/1", "Профиль", "113", "-", "м", 50],
        ["4", "D/1", "Пружина", "-", "-", "шт", 2.5],
        ["5", "E/1", "Шина", "-", "семь", "м", 14],
        ["6", "F/1", "Капсула", "-", "-", "шт", None],
        ["7", "G/1", "Профиль", "113", "6,5", "м", 13],
    ])
    spec = sp.parse_specification(data)
    assert [r.problem for r in spec.rows] == [
        sp.NOT_WHOLE_PIECES, sp.UNKNOWN_UNIT, sp.METRES_WITHOUT_LENGTH, sp.FRACTIONAL_QUANTITY,
        sp.BAD_LENGTH, sp.NO_QUANTITY, None,
    ]
    assert spec.rows[-1].pieces == 2
    assert not spec.ok
    assert (spec.number, spec.date, spec.supplier) == ("T-1", date(2026, 9, 1), 'ООО "Поставщик"')


def test_columns_are_found_by_their_titles():
    # Another order of columns and no code or colour: still read
    data = make_xlsx([
        ["Кол-во", "Ед. изм.", "Наименование"],
        [3, "шт.", "Мотор"],
        ["Итого:"],
    ])
    [row] = sp.parse_specification(data).rows
    assert (row.name, row.unit, row.count, row.code, row.kind) == ("Мотор", "шт", 3, None, sp.GOODS)


@pytest.mark.parametrize(
    "data, message",
    [
        (b"not a zip at all", "Not an Excel file"),
        (make_xlsx([["Просто текст"]]), "No table of goods in the file"),
        (make_xlsx([["Наименование", "Ед. изм.", "Кол-во"], ["Итого:"]]), "No goods in the file"),
        (make_xlsx([["x"]], sheet_extra='<!DOCTYPE lol [<!ENTITY a "aaaa">]>'), "Not an Excel file"),
        (b"0" * (sp.MAX_FILE_BYTES + 1), "The file is too large"),
    ],
)
def test_unreadable_files_are_refused(data, message):
    with pytest.raises(DomainError) as error:
        sp.parse_specification(data)
    assert error.value.status_code == 422
    assert error.value.detail == message
