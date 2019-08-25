import re
import html.entities

_entity_re = re.compile(r"&(#?[xX]?(?:[0-9a-fA-F]+|\w{1,8}));")

def _replace_entity(match):
    text = match.group(1)
    if text[0] == '#':
        text = text[1:]
        try:
            if text[0] in 'xX':
                c = int(text[1:], 16)
            else:
                c = int(text)
            return chr(c)
        except ValueError:
            return match.group(0)
    else:
        try:
            return chr(html.entities.name2codepoint[text])
        except (ValueError, KeyError):
            return match.group(0)

def unescape_entities(text):
    return _entity_re.sub(_replace_entity, str(text))