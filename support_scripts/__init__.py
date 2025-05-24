from typing import Self
from datetime import datetime
from string import ascii_letters, digits as str_digits
import os

from PyQt5.QtCore import QCoreApplication


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


def check_text(text: str) -> str:
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


def check_date_format(sample, column, format_):
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
    bool
        That tells if the sample had the correct format
    """
    try:
        first_row = True
        second_row = True
        for row in sample:
            if first_row:
                heading_row = row
                first_row = False
            else:
                if second_row:
                    sec_data = datetime.strptime(row[heading_row.index(column)], format_)
                    second_row = False
                datetime.strptime(row[heading_row.index(column)], format_)
        return [True, sec_data]
    except ValueError:
        return [False]


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
