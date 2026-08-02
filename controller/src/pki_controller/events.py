from __future__ import annotations

import datetime as dt
import json
import sys
from typing import Any


def emit(event: str, **fields: Any) -> None:
    record = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    print(json.dumps(record, separators=(",", ":")), file=sys.stdout, flush=True)

