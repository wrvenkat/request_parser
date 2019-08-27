# -*- coding: utf-8 -*-

import codecs
import datetime
import locale
import warnings
from decimal import Decimal

from urllib.parse import quote, unquote

class DjangoUnicodeDecodeError(UnicodeDecodeError):
    def __init__(self, obj, *args):
        self.obj = obj
        super().__init__(*args)

    def __str__(self):
        return '%s. You passed in %r (%s)' % (super().__str__(), self.obj, type(self.obj))

def force_text(s, encoding='utf-8', strings_only=False, errors='strict'):
    return force_str(s, encoding, strings_only, errors)


_PROTECTED_TYPES = (
    type(None), int, float, Decimal, datetime.datetime, datetime.date, datetime.time,
)


def is_protected_type(obj):
    """Determine if the object instance is of a protected type.

    Objects of protected types are preserved as-is when passed to
    force_str(strings_only=True).
    """
    return isinstance(obj, _PROTECTED_TYPES)


def force_str(s, encoding='utf-8', strings_only=False, errors='strict'):
    """
    Similar to smart_str(), except that lazy instances are resolved to
    strings, rather than kept as lazy objects.

    If strings_only is True, don't convert (some) non-string-like objects.
    """
    # Handle the common case first for performance reasons.
    if issubclass(type(s), str):
        return s
    if strings_only and is_protected_type(s):
        return s
    try:
        if isinstance(s, bytes):
            s = str(s, encoding, errors)
        else:
            s = str(s)
    except UnicodeDecodeError as e:
        raise DjangoUnicodeDecodeError(s, *e.args)
    return s


def iri_to_uri(iri):
    """
    Convert an Internationalized Resource Identifier (IRI) portion to a URI
    portion that is suitable for inclusion in a URL.

    This is the algorithm from section 3.1 of RFC 3987, slightly simplified
    since the input is assumed to be a string rather than an arbitrary byte
    stream.

    Take an IRI (string or UTF-8 bytes, e.g. '/I ♥ Django/' or
    b'/I \xe2\x99\xa5 Django/') and return a string containing the encoded
    result with ASCII chars only (e.g. '/I%20%E2%99%A5%20Django/').
    """
    # The list of safe characters here is constructed from the "reserved" and
    # "unreserved" characters specified in sections 2.2 and 2.3 of RFC 3986:
    #     reserved    = gen-delims / sub-delims
    #     gen-delims  = ":" / "/" / "?" / "#" / "[" / "]" / "@"
    #     sub-delims  = "!" / "$" / "&" / "'" / "(" / ")"
    #                   / "*" / "+" / "," / ";" / "="
    #     unreserved  = ALPHA / DIGIT / "-" / "." / "_" / "~"
    # Of the unreserved characters, urllib.parse.quote() already considers all
    # but the ~ safe.
    # The % character is also added to the list of safe characters here, as the
    # end of section 3.1 of RFC 3987 specifically mentions that % must not be
    # converted.
    if iri is None:
        return iri
    #WARNING: The following 2 line might come to bite back - have to pay some attentions
    #elif isinstance(iri, Promise):
    #else:
    #    iri = str(iri)
    return quote(iri, safe="/#%[]=:;$&()+,!?*@'~")

def uri_to_iri(uri):
    """
    Does the opposite of iri_to_uri()
    """
    if not uri:
        return uri
    
    if not isinstance(uri, str):
        uri = uri.decode('utf-8')
    
    #encode the provided bytes/string to UTF-8
    #uri = str(uri).encode('utf-8')

    # unquote(uri) decodes to UNICODE code point, SEE: https://en.wikipedia.org/wiki/List_of_Unicode_characters
    # We then re-encode the UNICODE to UTF-8 for Python use.
    return unquote(uri).encode('utf-8')

def escape_uri_path(path, encode_percent=True):
    """
    Escape the unsafe characters from the path portion of a Uniform Resource
    Identifier (URI).
    """
    # These are the "reserved" and "unreserved" characters specified in
    # sections 2.2 and 2.3 of RFC 2396:
    #   reserved    = ";" | "/" | "?" | ":" | "@" | "&" | "=" | "+" | "$" | ","
    #   unreserved  = alphanum | mark
    #   mark        = "-" | "_" | "." | "!" | "~" | "*" | "'" | "(" | ")"
    # The list of safe characters here is constructed subtracting ";", "=",
    # and "?" according to section 3.3 of RFC 2396.
    # The reason for not subtracting and escaping "/" is that we are escaping
    # the entire path, not a path segment.
    if encode_percent:
        return quote(path, safe="/:@&+$,-_.!~*'()")
    else:
        return quote(path, safe="/:@&+$,-_.!~*'()%")