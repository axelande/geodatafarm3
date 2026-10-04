"""A minimal LaTeX-subset to Office Math (OMML) converter for the paper's
display equations, so the Word file carries native, editable equations.

Supported: \\frac{a}{b}, x_{sub}, x^{sup}, \\left( ... \\right) and plain
parentheses, \\min, \\max, \\exp, \\, and \\; spacing, Greek letters via
\\alpha etc. (a few), and plain text. Anything else is emitted as text.
"""
import re
from xml.sax.saxutils import escape

M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
GREEK = {'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ', 'rho': 'ρ', 'sigma': 'σ',
         'mu': 'μ', 'theta': 'θ', 'lambda': 'λ', 'times': '×', 'cdot': '·', 'leq': '≤',
         'geq': '≥', 'sum': '∑', 'infty': '∞'}
FUNCS = ('min', 'max', 'exp', 'log', 'ln', 'sin', 'cos')


def _run(text, italic=True):
    if not text:
        return ''
    style = '' if italic else '<m:rPr><m:sty m:val="p"/></m:rPr>'
    return '<m:r>{}<m:t xml:space="preserve">{}</m:t></m:r>'.format(style, escape(text))


def _split_braces(s, i):
    """s[i] == '{'; return (content, index after the matching '}')."""
    depth, j = 0, i
    while j < len(s):
        if s[j] == '{':
            depth += 1
        elif s[j] == '}':
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return s[i + 1:], len(s)


def _read_arg(s, i):
    """An argument after _ or ^: a braced group or a single character."""
    if i < len(s) and s[i] == '{':
        return _split_braces(s, i)
    return s[i:i + 1], i + 1


def convert(expr):
    """LaTeX-subset string -> OMML inner XML (children of m:oMath)."""
    out, text, i = [], '', 0

    def flush():
        nonlocal text
        if text:
            # digits and operators upright, letters italic
            out.append(''.join(_run(ch, italic=ch.isalpha()) for ch in text))
            text = ''

    while i < len(expr):
        ch = expr[i]
        if ch == '\\':
            m = re.match(r'\\([A-Za-z]+|[,;!])', expr[i:])
            cmd = m.group(1)
            i += len(m.group(0))
            if cmd == 'frac':
                flush()
                num, i = _split_braces(expr, i)
                den, i = _split_braces(expr, i)
                out.append('<m:f><m:num>{}</m:num><m:den>{}</m:den></m:f>'.format(
                    convert(num), convert(den)))
            elif cmd in ('left', 'right'):
                # the delimiter character follows; handled by the bracket logic
                continue
            elif cmd in FUNCS:
                flush()
                out.append(_run(cmd, italic=False))
            elif cmd in (',', ';', '!'):
                text += ' '
            elif cmd in GREEK:
                text += GREEK[cmd]
            else:
                text += cmd
        elif ch == '(':
            flush()
            depth, j = 0, i
            while j < len(expr):
                if expr[j] == '(':
                    depth += 1
                elif expr[j] == ')':
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            inner = expr[i + 1:j].replace('\\right', '').replace('\\left', '')
            out.append('<m:d><m:e>{}</m:e></m:d>'.format(convert(inner)))
            i = j + 1
        elif ch in '_^':
            # the base is the whole trailing symbol (RY, GDD, Ky), not its last letter
            m = re.search(r'[A-Za-z]+$', text)
            base_text = m.group(0) if m else (text[-1] if text else '')
            text = text[:len(text) - len(base_text)] if base_text else text
            flush()
            arg, i = _read_arg(expr, i + 1)
            tag = 'sSub' if ch == '_' else 'sSup'
            part = 'sub' if ch == '_' else 'sup'
            # if the previous emitted element was a bracket or function, attach to it
            if base_text:
                base = ''.join(_run(c, italic=c.isalpha()) for c in base_text)
            elif out:
                base = out.pop()
            else:
                base = _run('')
            out.append('<m:{tag}><m:e>{base}</m:e><m:{part}>{arg}</m:{part}></m:{tag}>'.format(
                tag=tag, base=base, part=part, arg=convert(arg)))
        elif ch == ' ':
            text += ' '
            i += 1
        else:
            text += ch
            i += 1
    flush()
    return ''.join(out)


def latex_to_linear(expr):
    """The LaTeX subset used in the manuscript -> Word linear (UnicodeMath)
    text, which Word's BuildUp turns into a professional equation."""
    out = expr
    while '\\frac' in out:  # innermost fraction first: \frac{a}{b} -> (a)/(b)
        i = out.index('\\frac')
        num, j = _split_braces(out, i + 5)
        den, k = _split_braces(out, j)
        out = out[:i] + '(' + num + ')/(' + den + ')' + out[k:]
    out = out.replace('\\left', '').replace('\\right', '')
    for cmd, rep in (('\\max', 'max'), ('\\min', 'min'), ('\\exp', 'exp'),
                     ('\\,', ' '), ('\\;', ' '), ('\\!', '')):
        out = out.replace(cmd, rep)
    out = re.sub(r'_\{([^}]+)\}',
                 lambda m: '_(' + m.group(1) + ')' if len(m.group(1)) > 1 else '_' + m.group(1), out)
    out = re.sub(r'\^\{([^}]+)\}',
                 lambda m: '^(' + m.group(1) + ')' if len(m.group(1)) > 1 else '^' + m.group(1), out)
    return re.sub(r'\s+', ' ', out).strip()


def omath_paragraph_xml(expr, number=None):
    """A w:p containing an m:oMathPara with the equation, and the equation
    number right-aligned after a tab."""
    inner = convert(expr)
    num = ''
    if number is not None:
        num = ('<w:r><w:tab/></w:r><w:r><w:t xml:space="preserve">({})</w:t></w:r>'
               .format(number))
    return ('<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:m="{m}"><w:pPr><w:jc w:val="center"/><w:tabs><w:tab w:val="right" '
            'w:pos="9000"/></w:tabs></w:pPr><m:oMath>{inner}</m:oMath>{num}</w:p>'
            ).format(m=M, inner=inner, num=num)
