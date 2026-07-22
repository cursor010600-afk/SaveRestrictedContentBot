# Coursesbuying
# Don't Remove Credit
# Telegram Channel @Coursesbuying

import re
from urllib.parse import unquote


BOT_DEEPLINK_RE = re.compile(r'^(?:https?://)?t\.me/(?P<bot>[^/?]+)\?start=(?P<payload>.+)$', re.I)
PUBLIC_LINK_RE = re.compile(r'^(?:https?://)?t\.me/(?P<chat>[A-Za-z0-9_]+)/(?P<start>\d+)(?:-(?P<end>\d+))?(?:\?single)?$', re.I)
PRIVATE_LINK_RE = re.compile(r'^(?:https?://)?t\.me/c/(?P<chat>\d+)/(?P<start>\d+)(?:-(?P<end>\d+))?(?:\?single)?$', re.I)
BATCH_LINK_RE = re.compile(r'^(?:https?://)?t\.me/b/(?P<chat>[A-Za-z0-9_]+)/(?P<start>\d+)(?:-(?P<end>\d+))?(?:\?single)?$', re.I)
SHORT_RANGE_RE = re.compile(r'^(?P<start>\d+)(?:-(?P<end>\d+))?$', re.I)


def normalize_reference_text(text: str) -> str:
    text = unquote((text or '').strip())
    text = text.replace('https://', '').replace('http://', '')
    if text.startswith('telegram.me/'):
        text = 't.me/' + text[len('telegram.me/'):]
    return text


def parse_reference_text(text: str, last_chat=None):
    """Parse supported Telegram links or ordered bulk ranges.

    Supports:
    - Bot deep links with `?start=` payloads — if the payload is itself a
      valid Telegram reference it is handled as usual; otherwise the link
      is treated as a **bot deep-link interaction** where the bot
      automatically opens the target bot, sends ``/start <payload>`` and
      saves every response.
    - Public message links like ``t.me/channel/123-130``
    - Private/c links like ``t.me/c/123456789/123-130``
    - Batch links like ``t.me/b/username/123-130``
    - Short ranges like ``123-130`` when ``last_chat`` is available
    """
    normalized = normalize_reference_text(text)

    deep_link = BOT_DEEPLINK_RE.match(normalized)
    if deep_link:
        bot_username = deep_link.group('bot')
        raw_payload = deep_link.group('payload')
        payload_normalized = normalize_reference_text(raw_payload)

        # Check whether the payload itself is a standard reference
        # (backward-compatible behaviour).
        inner = payload_normalized
        if inner.startswith('t.me/'):
            inner = inner[5:]

        is_std = (
            PRIVATE_LINK_RE.match(f't.me/{inner}')
            or BATCH_LINK_RE.match(f't.me/{inner}')
            or PUBLIC_LINK_RE.match(f't.me/{inner}')
            or (SHORT_RANGE_RE.match(inner) and last_chat is not None)
        )

        if is_std:
            # Existing behaviour: treat the inner payload as the reference
            normalized = payload_normalized
        else:
            return {
                'kind': 'bot_deeplink',
                'bot': bot_username,
                'payload': raw_payload,
            }

    if normalized.startswith('t.me/'):
        normalized = normalized[5:]

    match = PRIVATE_LINK_RE.match(f't.me/{normalized}')
    if match:
        return {
            'kind': 'private',
            'chat': int(f"-100{match.group('chat')}"),
            'start': int(match.group('start')),
            'end': int(match.group('end') or match.group('start')),
        }

    match = BATCH_LINK_RE.match(f't.me/{normalized}')
    if match:
        return {
            'kind': 'batch',
            'chat': match.group('chat'),
            'start': int(match.group('start')),
            'end': int(match.group('end') or match.group('start')),
        }

    match = PUBLIC_LINK_RE.match(f't.me/{normalized}')
    if match:
        return {
            'kind': 'public',
            'chat': match.group('chat'),
            'start': int(match.group('start')),
            'end': int(match.group('end') or match.group('start')),
        }

    match = SHORT_RANGE_RE.match(normalized)
    if match and last_chat:
        return {
            'kind': last_chat.get('kind', 'public'),
            'chat': last_chat.get('chat'),
            'start': int(match.group('start')),
            'end': int(match.group('end') or match.group('start')),
        }

    return None