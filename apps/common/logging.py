import json
import logging
import os
import re
import traceback
from datetime import datetime, timezone

from .request_context import get_request_id


_SENSITIVE_PATTERNS = (
    (re.compile(r'(?i)\bBearer\s+\S+'), 'Bearer [REDACTED]'),
    (re.compile(r'\bcoin\.jwt\.[A-Za-z0-9._~-]+'), 'coin.jwt.[REDACTED]'),
    (re.compile(r'(?i)\b(?:redis|rediss|postgres|postgresql)://\S+'), '[REDACTED_URL]'),
    (re.compile(r'(?i)\b(password|passwd|secret|token)=\S+'), r'\1=[REDACTED]'),
)


def redact(value):
    result = str(value)
    for pattern, replacement in _SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


class SafeLogFilter(logging.Filter):
    def filter(self, record):
        record.msg = redact(record.getMessage())
        record.args = ()
        request_id = get_request_id()
        if request_id == '-':
            request_id = getattr(getattr(record, 'request', None), 'request_id', '-')
        record.request_id = request_id
        return True


class JSONFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': redact(record.getMessage()),
            'request_id': getattr(record, 'request_id', '-'),
        }
        if record.exc_info:
            payload['exception_type'] = record.exc_info[0].__name__
            payload['frames'] = [
                {'file': os.path.basename(frame.filename), 'line': frame.lineno, 'function': frame.name}
                for frame in traceback.extract_tb(record.exc_info[2])[-8:]
            ]
        return json.dumps(payload, ensure_ascii=False)
