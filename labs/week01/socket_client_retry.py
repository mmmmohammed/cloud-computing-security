"""Fixed client: explicit timeout plus bounded retry with backoff."""
import socket, time

ATTEMPTS, BACKOFF = 3, 0.5

for attempt in range(1, ATTEMPTS + 1):
    try:
        with socket.create_connection(("127.0.0.1", 9009), timeout=2) as s:
            s.sendall(b"hello distributed world")
            print(f"[client] attempt {attempt}: reply:", s.recv(1024))
            break
    except (ConnectionRefusedError, socket.timeout) as e:
        print(f"[client] attempt {attempt} failed: {e!r}")
        if attempt < ATTEMPTS:
            time.sleep(BACKOFF * attempt)
else:
    print("[client] giving up after retries")
