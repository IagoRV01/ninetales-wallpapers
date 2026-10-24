"""Small dependency-free translation layer; Spanish message IDs remain stable."""
from __future__ import annotations

import json
import os
from pathlib import Path

LANGUAGES = {'auto': 'Sistema', 'es': 'Español', 'en': 'English', 'fr': 'Français', 'pt': 'Português'}
_directory = Path(__file__).parent / 'locales'
_language = 'es'
_catalog = {}


def resolve_language(value='auto', environment=None):
    environment = os.environ if environment is None else environment
    if value == 'auto':
        value = next((environment.get(k) for k in ('LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG') if environment.get(k)), 'en')
    value = str(value).split(':')[0].split('.')[0].replace('-', '_').split('_')[0].lower()
    return value if value in ('es', 'en', 'fr', 'pt') else 'en'


def configure(value='auto'):
    global _language, _catalog
    _language = resolve_language(value)
    try:
        _catalog = json.loads((_directory / (_language + '.json')).read_text())
    except (OSError, ValueError):
        _catalog = {}
    return _language


def t(message, **values):
    translated = _catalog.get(message, message)
    return translated.format(**values) if values else translated


def localize(message):
    """Translate supervisor/error templates whose values arrive over the state file."""
    if message in _catalog:
        return t(message)
    import re
    import string
    for template in _catalog:
        parts = list(string.Formatter().parse(template))
        if not any(name for _, name, _, _ in parts):
            continue
        pattern = ''.join(re.escape(literal) + ('(?P<' + name + '>.+?)' if name else '')
                          for literal, name, _, _ in parts)
        match = re.fullmatch(pattern, message, re.DOTALL)
        if match:
            return t(template, **match.groupdict())
    return message
