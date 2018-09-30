from string import ascii_letters, digits as str_digits
from datetime import datetime


def check_text(text):
    """Checks that the text only contains ascii letters and numbers"""
    only_char = ''
    for letter in text:
        if letter in ascii_letters:
            only_char += letter
        elif letter in str_digits:
            only_char += letter
        elif letter == ' ':
            only_char += '_'
        else:
            only_char += "_"
    return only_char.lower()


def isfloat(x):
    """Checks if the inserted value is of float type"""
    try:
        a = float(x)
    except (ValueError, OverflowError, TypeError):
        return False
    else:
        return True


def isint(x):
    """Checks if the inserted value is of int type"""
    try:
        a = float(x)
        b = int(a)
    except (ValueError, OverflowError, TypeError):
        return False
    else:
        return a == b


def check_date_format(sample, column, format_):
    """Checks that the date format matches the selected format

    :param sample, the sample of the data including a heading row
    :param column, the column in the heading row containing the date
    :param format_, the format of the date"""
    try:
        first_row = True
        for row in sample:
            if first_row:
                heading_row = row
                first_row = False
            else:
                datetime.strptime(row[heading_row.index(column)], format_)
        return True
    except ValueError:
        return False
