import socket
import sys


try:
    with socket.create_connection(("localhost", 8501), timeout=3):
        sys.exit(0)

except Exception:
    sys.exit(1)
