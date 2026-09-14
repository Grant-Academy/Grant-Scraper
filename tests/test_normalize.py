import pytest

from grantscrape.normalize import (
    parse_amount,
    extract_year,
    guess_recipient_type,
    squash_ws,
    find_amounts,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("€ 3.500", 3500),          # Huber: euro sign, dot thousands
        ("3 700 €", 3700),          # Linnamo: space thousands
        ("10,000 €", 10000),        # Linnamo: comma thousands
        ("1000€", 1000),            # Muinaismuisto: no separator
        ("2000 €", 2000),
        ("€ 116.030", 116030),
        ("26 000 euroa", 26000),    # prose 'euroa'
        ("1 500,00 €", 1500),       # decimal comma cents
        ("12.500,50 €", 12500),     # dot thousands + decimal comma
    ],
)
def test_parse_amount_formats(raw, expected):
    assert parse_amount(raw) == (expected, "EUR")


def test_parse_amount_returns_none_when_no_number():
    assert parse_amount("ei summaa") == (None, None)


def test_parse_amount_none_input():
    assert parse_amount(None) == (None, None)


def test_extract_year_from_heading():
    assert extract_year("Myönnetyt apurahat 2024") == 2024


def test_extract_year_ignores_non_year_numbers():
    assert extract_year("3 700 € vuonna 2021") == 2021
    assert extract_year("116.030 €") is None


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Laura Rämä", "person"),
        ("Oblivia & KlangLab", "group"),
        ("Sananveisto -työryhmä", "group"),
        ("Airo, Henri (Medianomi / AMK) ja työryhmä", "group"),
        ("Teatteri Metamorfoosi ry", "organisation"),
        ("Suomen Muinaismuistosäätiö", "organisation"),
        ("Kuopion Kaupunginorkesteri", "organisation"),
        ("Tanssiyhdistys Liike", "organisation"),
        ("Firma Oy", "organisation"),
    ],
)
def test_guess_recipient_type(name, expected):
    assert guess_recipient_type(name) == expected


def test_squash_ws_collapses_whitespace_and_nbsp():
    assert squash_ws("  Laura  Rämä \n –  € 3.500 ") == "Laura Rämä – € 3.500"


def test_find_amounts_lists_euro_amounts_in_text():
    text = "Laura Rämä – € 3.500 – esitystaide\nHeli – 2000 € – musiikki\nno money here"
    assert find_amounts(text) == ["€ 3.500", "2000 €"]


def test_squash_ws_normalises_unicode_to_nfc():
    assert squash_ws("Häkkinen") == "Häkkinen"


def test_parse_amount_accepts_e_abbreviation():
    assert parse_amount("3000 e") == (3000, "EUR")
    assert find_amounts("tutkimukseen 2 500 e. Toinen") == ["2 500 e"]
