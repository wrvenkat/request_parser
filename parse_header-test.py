from urllib import unquote

def parse_header(line):
    """
    Parse the header into a key-value.

    Input (line): bytes, output: str for key/name, bytes for values which
    will be decoded later.
    """
    plist = _parse_header_params(b';' + line)
    key = plist.pop(0).lower().decode('ascii')
    pdict = {}
    for p in plist:
        i = p.find(b'=')
        if i >= 0:
            has_encoding = False
            name = p[:i].strip().lower().decode('ascii')
            if name.endswith('*'):
                # Lang/encoding embedded in the value (like "filename*=UTF-8''file.ext")
                # http://tools.ietf.org/html/rfc2231#section-4
                name = name[:-1]
                if p.count(b"'") == 2:
                    has_encoding = True
            value = p[i + 1:].strip()
            if has_encoding:
                encoding, lang, value = value.split(b"'")
                #value = unquote(value.decode(), encoding=encoding.decode())
                #WARNING: Usage of unquote without an explicit encoding argument
                #will come back to bite us. Investigate.
                value = unquote(value.decode())
            if len(value) >= 2 and value[:1] == value[-1:] == b'"':
                value = value[1:-1]
                value = value.replace(b'\\\\', b'\\').replace(b'\\"', b'"')
            pdict[name] = value
    return key, pdict

def _parse_header_params(s):
    plist = []
    while s[:1] == b';':
        s = s[1:]
        end = s.find(b';')
        while end > 0 and s.count(b'"', 0, end) % 2:
            end = s.find(b';', end + 1)
        if end < 0:
            end = len(s)
        f = s[:end]
        plist.append(f.strip())
        s = s[end:]
    return plist

s = 'multipart/form-data"; jhkh; boundary=---------------------------9051914041"544843365972754266; boundary=-----------12312312'

print parse_header(s)