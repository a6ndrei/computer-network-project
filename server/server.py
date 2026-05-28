import os
import signal
import socket
import sys
import threading

from database import Database
from client_handler import ClientHandler

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 9000))


def main():
    db = Database()

    
    subscriptions: dict = {}          
    subs_lock     = threading.Lock()

    all_handlers: list = []            
    handlers_lock = threading.Lock()

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(10)
    print(f"[SERVER] Asculta pe {HOST}:{PORT} ...")

    
    def shutdown(sig, frame):
        print("\n[SERVER] Oprire in curs ...")
        server_sock.close()
        with handlers_lock:
            for h in list(all_handlers):
                try:
                    h.conn.close()
                except OSError:
                    pass
        print("[SERVER] Oprit.")
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        try:
            conn, addr = server_sock.accept()
        except OSError:
            break  

        handler = ClientHandler(
            conn, addr, db,
            subscriptions, subs_lock,
            all_handlers, handlers_lock,
        )

        with handlers_lock:
            all_handlers.append(handler)

        handler.start()


if __name__ == "__main__":
    main()
