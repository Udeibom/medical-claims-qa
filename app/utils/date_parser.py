"""
Utility for light date parsing from text.
We only handle common formats like:
  - 10/06/2023
  - 10-06-2023
  - June 10, 2023
  - 2023-06-10
No heavy NLP, just regex and datetime.strptime.
"""

import re
from datetime import datetime
from typing import Optional


def parse_date(text: str) -> Optional[str]:
    """
    Extract a date-like pattern from text and return ISO 'YYYY-MM-DD'.
    Returns None if no valid date found.
    """
    if not text:
        return None

    # possible matches: 2023-06-10, 10/06/2023, 10-06-2023, 10 June 2023
    patterns = [
        r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})",       # yyyy-mm-dd
        r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",     # dd-mm-yyyy or dd/mm/yyyy
        r"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",   # 10 June 2023
    ]

    for p in patterns:
        m = re.search(p, text)
        if not m:
            continue
        s = m.group(1).strip()
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d/%m/%y", "%d %B %Y", "%d %b %Y"):
            try:
                dt = datetime.strptime(s, fmt)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                continue
    return None
