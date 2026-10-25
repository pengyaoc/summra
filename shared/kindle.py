"""Detect a Kindle e-ink reader's browser.

E-ink Kindles send a `Kindle/x.y` token (Paperwhite, Oasis, Scribe, Keyboard).
Fire tablets are LCD Android tablets: they send `Silk`, a `KF…` model code
or (first generation) `Kindle Fire`, and keep the normal site.
"""
import re

_KINDLE = re.compile(r'\bKindle\b')
_FIRE = re.compile(r'Silk|Kindle Fire|\bKF[A-Z]{2,5}\b|Android \d')


def is_kindle_user_agent(user_agent):
    ua = user_agent or ''
    return bool(_KINDLE.search(ua)) and not _FIRE.search(ua)
