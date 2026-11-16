"""Naive client: assumes the network is reliable, so it never retries."""
import socket

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect(("127.0.0.1", 9009))   # no timeout, no retry
    s.sendall(b"hello distributed world")
    print("[client] reply:", s.recv(1024))
