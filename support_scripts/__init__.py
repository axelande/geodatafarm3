from typing import Self
from datetime import datetime
from string import ascii_letters, digits as str_digits
import os

from qgis.PyQt.QtCore import QCoreApplication

# Read text files as utf-8-sig, never plain utf-8: a byte order mark
# survives into the heading read from the file but not into the combo box
# the user picks a column from - Qt's line edit drops the zero width mark -
# and check_text() then turns it into a leading underscore on one side only,
# so the two names for the same column no longer match. On a file without a
# mark utf-8-sig behaves exactly like utf-8.
TEXT_ENCODING = 'utf-8-sig'


class TR:
    def __init__(self: Self, class_name: str='GeoDataFarm') -> None:
        self.class_name =class_name

    def tr(self: Self, message: str) -> str:
        """Get the translation for a string using Qt translation API.
        We implement this ourselves since we do not inherit QObject.

        Parameters
        ----------
        message: str, String for translation.

        Returns
        -------
        QString
            Translated version of message.
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate(self.class_name, message)


def check_text(text: str, allow_first_digit: bool=False) -> str:
    """Checks that the text only contains ascii letters and numbers

    Parameters
    ----------
    text: str

    Returns
    -------
    str
        A text string with only ascii letters and numbers but starting with a number
    """
    only_char = ''
    for i, letter in enumerate(text):
        if letter in ascii_letters:
            only_char += letter
        elif allow_first_digit and i == 0 and letter in str_digits:
            only_char += letter
        elif i > 0 and letter in str_digits:
            only_char += letter
        elif letter == '%':
            only_char += 'pct'
        elif letter == '1':
            only_char += 'one'
        elif letter == '/':
            only_char += '_per_'
        elif letter == ' ':
            only_char += '_'
        else:
            only_char += "_"
    return only_char.lower()


def isfloat(x: str) -> bool:
    """Checks if the inserted value is of float type

    Parameters
    ----------
    x: str

    Returns
    -------
    bool
    """
    try:
        a = float(x)
    except (ValueError, OverflowError, TypeError):
        return False
    else:
        return True


def db_rows(result) -> list:
    """Normalises a ``DB.execute_and_return()`` result to always be a
    list of rows.

    On failure (with ``return_failure=False``, the default), that method
    returns a plain error *string* instead of rows - ``'There were an
    error..'`` in test mode, or nothing at all otherwise (it shows the
    error itself and returns the same string). A bare ``result or []``
    guard doesn't catch this, since a non-empty string is truthy: the
    caller ends up iterating it character by character, each character
    then failing to unpack/index as if it were a row - a confusing
    IndexError/ValueError far from the real cause. Wrap every
    ``execute_and_return`` call site that iterates its result with this
    instead of ``result or []``.

    Parameters
    ----------
    result

    Returns
    -------
    list
    """
    return result if isinstance(result, list) else []


def isint(x: str) -> bool:
    """Checks if the inserted value is of int type

    Parameters
    ----------
    x: str

    Returns
    -------
    bool
    """
    try:
        a = float(x)
        b = int(a)
    except (ValueError, OverflowError, TypeError):
        return False
    else:
        return a == b


def check_date_format(sample: list, column: str,
                      format_: str) -> tuple[bool, datetime | None, str]:
    """Checks that the date format matches the selected format

    Parameters
    ----------
    sample: list
        the sample of the data including a heading row
    column: str
        the column in the heading row containing the date
    format_: str
        the format of the date

    Returns
    -------
    tuple[bool, datetime | None, str]
        Whether the sample matched the format, the first date read from it,
        and - when it did not match - what stood in the way. Saying only that
        the format was wrong leaves the one person who can fix it guessing at
        which column and which value were meant.
    """
    heading_row = sample[0] if sample else []
    if column not in heading_row:
        return False, None, (f'no column named "{column}" among '
                             f'{len(heading_row)} columns: {heading_row}')
    index = heading_row.index(column)
    first_date = None
    for number, row in enumerate(sample[1:], start=2):
        if index >= len(row) or not row[index].strip():
            # An export can carry a unit row right under the heading, and rows
            # that only report a sensor reading can leave the stamp out. The
            # import drops those rows, so they must not condemn the format.
            continue
        value = row[index].strip().strip('"')
        try:
            date = datetime.strptime(value, format_)
        except ValueError:
            return False, None, (f'row {number} of column "{column}" holds '
                                 f'"{value}", which is not "{format_}"')
        if first_date is None:
            first_date = date
    if first_date is None:
        return False, None, f'column "{column}" holds no date at all'
    return True, first_date, ''


def error_in_sign(sign):
    if sign in ['+', '-', '*', '/']:
        return False
    return True

def getfile_insensitive(path: str) -> str:
    directory, filename = os.path.split(path)
    directory, filename = (directory or '.'), filename.lower()
    for f in os.listdir(directory):
        newpath = os.path.join(directory, f)
        if os.path.isfile(newpath) and f.lower() == filename:
            return newpath
    return "Not found"
