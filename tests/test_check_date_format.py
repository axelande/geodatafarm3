import csv
from datetime import datetime

from ..support_scripts.__init__ import (TEXT_ENCODING, check_date_format,
                                        check_text)

FORMAT = '%Y-%m-%d %H:%M:%S'


def test_a_matching_sample_returns_the_first_date():
    sample = [['date', 'yield'],
              ['2024-09-01 10:00:00', '12'],
              ['2024-09-01 10:00:01', '13']]

    assert check_date_format(sample, 'date', FORMAT) == (
        True, datetime(2024, 9, 1, 10, 0, 0), '')


def test_a_unit_row_under_the_heading_does_not_condemn_the_format():
    """Machine exports often put a row of units right below the heading, and
    rows that only carry a sensor reading can leave the stamp out."""
    sample = [['date', 'yield'],
              ['', 't/ha'],
              ['2024-09-01 10:00:00', '12'],
              ['', '13']]

    assert check_date_format(sample, 'date', FORMAT) == (
        True, datetime(2024, 9, 1, 10, 0, 0), '')


def test_a_date_that_does_not_match_the_format_names_the_value():
    sample = [['date'], ['01/09/2024 10:00:00']]

    is_ok, first_date, problem = check_date_format(sample, 'date', FORMAT)

    assert (is_ok, first_date) == (False, None)
    assert '01/09/2024 10:00:00' in problem and FORMAT in problem


def test_one_unparsable_row_among_good_ones_names_its_row():
    sample = [['date'], ['2024-09-01 10:00:00'], ['nonsense']]

    is_ok, _, problem = check_date_format(sample, 'date', FORMAT)

    assert is_ok is False
    assert 'row 3' in problem and 'nonsense' in problem


def test_a_missing_column_says_so_and_lists_what_is_there():
    sample = [['other'], ['2024-09-01 10:00:00']]

    is_ok, _, problem = check_date_format(sample, 'date', FORMAT)

    assert is_ok is False
    assert 'no column named "date"' in problem and 'other' in problem


def test_a_sample_holding_no_date_at_all_is_rejected():
    for sample in ([['date']], [['date'], [''], ['   ']],
                   [['pad', 'date'], ['too short']]):
        is_ok, first_date, problem = check_date_format(sample, 'date', FORMAT)
        assert (is_ok, first_date) == (False, None)
        assert 'no date at all' in problem


def test_every_branch_returns_a_triple_the_callers_can_unpack():
    for sample in ([], [['date']], [['date'], ['nope']],
                   [['date'], ['2024-09-01 10:00:00']]):
        is_ok, first_date, problem = check_date_format(sample, 'date', FORMAT)
        assert isinstance(is_ok, bool)
        assert first_date is None or isinstance(first_date, datetime)
        assert isinstance(problem, str)
        assert bool(problem) is not is_ok


def test_a_byte_order_mark_does_not_hide_the_first_column(tmp_path):
    """A file saved with a byte order mark used to lose its first column.

    The mark survives into the heading read from the file, where check_text
    turns it into a leading underscore, but not into the name the combo box
    hands back - Qt's line edit drops the zero width mark - so the import
    looked up a column name the heading no longer had. Reading the file as
    utf-8-sig keeps the mark out of both.
    """
    path = tmp_path / 'with_bom.csv'
    path.write_text('date;yield\n2024-09-01 10:00:00;12\n', encoding='utf-8-sig')

    with open(path, encoding=TEXT_ENCODING, newline='') as handle:
        rows = list(csv.reader(handle, delimiter=';'))
    sample = [[check_text(column) for column in rows[0]]] + rows[1:]

    assert sample[0] == ['date', 'yield']
    is_ok, first_date, problem = check_date_format(sample, check_text('date'),
                                                   FORMAT)
    assert (is_ok, first_date, problem) == (True, datetime(2024, 9, 1, 10, 0), '')
