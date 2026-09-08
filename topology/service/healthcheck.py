import socket

for port in (8080, 9000, 9090):
    with socket.create_connection(("127.0.0.1", port), timeout=1):
        pass
