"""
latex_chuan.py – BẢN PYTHON CỦA ChuanLatex.gs (Kho chung). Chép đúng từng bước để lời giải do xưởng ghi
có cùng chuẩn với lời giải do Apps Script ghi: $...$ / $$...$$, số thập phân 0,05, \\cdot, 5\\text{ cm}, 10^{-3}, không Unicode.
"""
import re

LATEX_UNICODE = {
    'α': '\\alpha', 'β': '\\beta', 'γ': '\\gamma', 'δ': '\\delta', 'ε': '\\varepsilon', 'θ': '\\theta',
    'λ': '\\lambda', 'μ': '\\mu', 'π': '\\pi', 'ρ': '\\rho', 'σ': '\\sigma', 'τ': '\\tau', 'φ': '\\varphi',
    'ω': '\\omega', 'Δ': '\\Delta', 'Ω': '\\Omega', 'Φ': '\\Phi', 'Σ': '\\Sigma', 'Θ': '\\Theta', 'Λ': '\\Lambda',
    '≈': '\\approx', '≤': '\\le ', '≥': '\\ge ', '≠': '\\ne ', '±': '\\pm ', '×': '\\times ', '·': '\\cdot ', '∙': '\\cdot ',
    '→': '\\to ', '⇒': '\\Rightarrow ', '∞': '\\infty ', '∝': '\\propto ', '−': '-', '–': '-', '°': '^\\circ ',
    '²': '^2', '³': '^3', '⁻': '^-', '¹': '^1', '⁴': '^4'
}
_RE_UNI = re.compile('[' + ''.join(LATEX_UNICODE) + ']')
_RE_DON_VI = re.compile(r'(\d(?:[.,]|\{,\})?\d*)\s+(km/h|m/s|cm|mm|km|kg|mg|ms|Hz|MHz|kHz|mA|mV|mT|kV|rad|[gmsNJWVATΩ])'
                        r'(\^\{?-?\d\}?)?(?![A-Za-z\\{])')


def chuan_hoa_toan(m):
    """Chuẩn hoá phần CÔNG THỨC THUẦN (không có dấu $ bao ngoài) – giống chuanHoaToan_."""
    s = '' if m is None else str(m)
    s = s.replace('\\\\', '\\')
    s = s.replace('{,}', ',')
    s = re.sub(r'\\text\{\s*text\{\s*', lambda _: '\\text{', s)
    s = re.sub(r'\\\\(?=[A-Za-z])', lambda _: '\\', s)
    s = _RE_UNI.sub(lambda c: LATEX_UNICODE[c.group(0)], s)
    s = re.sub(r'√\s*\(([^()]*)\)', lambda g: '\\sqrt{' + g.group(1) + '}', s)
    s = re.sub(r'√\s*([A-Za-z0-9.,]+)', lambda g: '\\sqrt{' + g.group(1) + '}', s)
    s = re.sub(r'\\[dt]frac\b', lambda _: '\\frac', s).replace('\\mathrm{', '\\text{')
    s = re.sub(r'(\d)\s*\\times\s*(?=\d)', lambda g: g.group(1) + '\\cdot ', s)
    s = re.sub(r'\s*\*\s*', lambda _: '\\cdot ', s)
    s = re.sub(r'\^\s*(-?\d{2,}|-\d)(?![\d}])', lambda g: '^{' + g.group(1) + '}', s)
    s = re.sub(r'(\d)\{,\}(?=\d)', lambda g: g.group(1) + ',', s)
    s = re.sub(r'(\d)\.(?=\d)', lambda g: g.group(1) + ',', s)
    s = _RE_DON_VI.sub(lambda g: g.group(1) + '\\text{ ' + g.group(2) + '}' + (g.group(3) or ''), s)
    s = re.sub(r'(\d)\s*\\text\{\s*', lambda g: g.group(1) + '\\text{ ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def chuan_hoa_latex(s):
    """Chuẩn hoá cả đoạn chữ lẫn công thức ($...$, $$...$$, \\(...\\), \\[...\\]) – giống chuanHoaLatex_."""
    t = '' if s is None else str(s)
    t = re.sub(r'\[\s*cite[^\]]*\]', '', t, flags=re.I)
    t = re.sub(r'\*\*|`', '', t)
    t = re.sub(r'\\(?:textbf|textit|emph)\{([^{}]*)\}', lambda g: g.group(1), t)
    t = re.sub(r'\\item\s*', '', t)
    t = re.sub(r'\\\[([\s\S]*?)\\\]', lambda g: '$$' + g.group(1) + '$$', t)
    t = re.sub(r'\\\(([\s\S]*?)\\\)', lambda g: '$' + g.group(1) + '$', t)
    t = re.sub(r'\$\$([\s\S]*?)\$\$|\$([^$\n]+?)\$',
               lambda g: '$$' + chuan_hoa_toan(g.group(1)) + '$$' if g.group(1) is not None else '$' + chuan_hoa_toan(g.group(2)) + '$', t)
    t = re.sub(r'([^\n])[ \t]*(\$\$[\s\S]*?\$\$)', lambda g: g.group(1) + '\n' + g.group(2), t)
    t = re.sub(r'(\$\$[\s\S]*?\$\$)[ \t]*(?=[A-Za-z\u00C0-\u1EF9])', lambda g: g.group(1) + '\n', t)
    t = re.sub(r'[ \t]+\n', '\n', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    t = re.sub(r'[ \t]{2,}', ' ', t)
    return t.strip()
