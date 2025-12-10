# -*- encoding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import re


def flatten(domain):
    for tok in domain:
        if isinstance(tok, list):
            for sub in flatten(tok):
                yield sub
        else:
            yield tok

def _make_mutable(domain):
    out = []
    for tok in domain:
        if isinstance(tok, tuple):
            out.append(list(tok))
        elif isinstance(tok, list):
            if len(tok) == 3 and not any(isinstance(x, list) for x in tok):
                out.append(tok[:])
            else:
                out.append(_make_mutable(tok))
        else:
            out.append(tok)                  # '|', '&', '!' …
    return out


pattern_type = type(re.compile(''))