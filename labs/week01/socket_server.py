"""Week 1 lab: TCP server that answers one request per line."""
import socket

HOST, PORT = "127.0.0.1", 9009
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(1)
    print(f"[server] listening on {HOST}:{PORT}")
    conn, addr = srv.accept()
    with conn:
        print(f"[server] connection from {addr}")
        data = conn.recv(1024)
        print(f"[server] received: {data!r}")
        conn.sendall(b"ACK:" + data.upper())
        print("[server] served request, shutting down")
