from string import ascii_letters, digits as str_digits


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
    except (ValueError, OverflowError):
        return False
    else:
        return True


def isint(x):
    """Checks if the inserted value is of int type"""
    try:
        a = float(x)
        b = int(a)
    except (ValueError, OverflowError):
        return False
    else:
        return a == b

