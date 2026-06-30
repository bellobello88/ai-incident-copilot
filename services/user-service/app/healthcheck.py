import sys
import urllib.request


try:
    with urllib.request.urlopen("http://localhost:8000/health", timeout=3) as response:
        if response.status == 200:
            sys.exit(0)

    sys.exit(1)

except Exception:
    sys.exit(1)
