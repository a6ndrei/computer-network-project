import json
import socket
import sys
import threading

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9000

SEPARATOR = "─" * 55


def receiver(sock: socket.socket, stop_event: threading.Event):
    """
    Thread care asculta in permanenta raspunsuri/notificari de la server.
    Afiseaza mesajele primite fara a bloca thread-ul principal.
    """
    buffer = ""
    try:
        while not stop_event.is_set():
            try:
                chunk = sock.recv(4096)
            except OSError:
                break
            if not chunk:
                print("\n[CLIENT] Server-ul a inchis conexiunea.")
                stop_event.set()
                break
            buffer += chunk.decode("utf-8")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if line:
                    _display_message(json.loads(line))
    except Exception as e:
        if not stop_event.is_set():
            print(f"\n[CLIENT] Eroare primire: {e}")
        stop_event.set()


def _display_message(msg: dict):
    """Afiseaza un mesaj/notificare intr-un format lizibil."""
    if "event" in msg:
        event = msg["event"]
        pid   = msg.get("product_id", "?")
        print(f"\n{'':>2} NOTIFICARE – produsul #{pid} a fost {('MODIFICAT' if event == 'updated' else 'STERS')}!")
        if event == "updated" and "product" in msg:
            _print_product(msg["product"])
        print("  > ", end="", flush=True)
        return

    status = msg.get("status", "")
    if status == "error":
        print(f"\n   Eroare: {msg.get('message', 'necunoscuta')}")
        return

    if "products" in msg:
        products = msg["products"]
        if not products:
            print("\n  (niciun produs gasit in intervalul cerut)")
        else:
            print(f"\n  {len(products)} produs(e) selectat(e):")
            print(f"  {SEPARATOR}")
            for p in products:
                _print_product(p)
        return

    if "product" in msg:
        print("\n   Produs actualizat:")
        _print_product(msg["product"])
        return

    if "message" in msg:
        print(f"\n   {msg['message']}")


def _print_product(p: dict):
    print(f"  ID={p['id']}  Nume={p['name']}  Pret={p['price']:.2f} RON  Stoc={p['stock']}")



def send(sock: socket.socket, data: dict):
    raw = json.dumps(data, ensure_ascii=False) + "\n"
    sock.sendall(raw.encode("utf-8"))



MENU = f"""
{SEPARATOR}
  1. Selecteaza TOATE produsele
  2. Selecteaza produs dupa ID
  3. Selecteaza produse intr-un interval de ID-uri
  4. Actualizeaza un produs
  5. Sterge un produs
  0. Iesire
{SEPARATOR}"""


def run_menu(sock: socket.socket, stop_event: threading.Event):
    while not stop_event.is_set():
        print(MENU)
        choice = input("  > ").strip()

        if stop_event.is_set():
            break

        if choice == "1":
            send(sock, {"cmd": "select"})

        elif choice == "2":
            pid = _read_int("  ID produs: ")
            if pid is None:
                continue
            send(sock, {"cmd": "select", "id": pid})

        elif choice == "3":
            id_min = _read_int("  ID minim: ")
            if id_min is None:
                continue
            id_max = _read_int("  ID maxim: ")
            if id_max is None:
                continue
            send(sock, {"cmd": "select", "id_min": id_min, "id_max": id_max})

        elif choice == "4":
            pid = _read_int("  ID produs de actualizat: ")
            if pid is None:
                continue
            name = input("  Nume nou: ").strip()
            price = _read_float("  Pret nou (RON): ")
            if price is None:
                continue
            stock = _read_int("  Stoc nou: ")
            if stock is None:
                continue
            send(sock, {"cmd": "update", "id": pid, "name": name, "price": price, "stock": stock})

        elif choice == "5":
            pid = _read_int("  ID produs de sters: ")
            if pid is None:
                continue
            confirm = input(f"  Esti sigur ca vrei sa stergi produsul #{pid}? (da/nu): ").strip().lower()
            if confirm == "da":
                send(sock, {"cmd": "delete", "id": pid})
            else:
                print("  Stergere anulata.")

        elif choice == "0":
            send(sock, {"cmd": "quit"})
            stop_event.set()
            break

        else:
            print("    Optiune invalida. Alege un numar din meniu.")

        
        import time; time.sleep(0.3)

def _read_int(prompt: str):
    try:
        return int(input(prompt).strip())
    except ValueError:
        print("    Trebuie sa introduci un numar intreg.")
        return None


def _read_float(prompt: str):
    try:
        return float(input(prompt).strip().replace(",", "."))
    except ValueError:
        print("    Trebuie sa introduci un numar (ex: 12.50).")
        return None

def main():
    host = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT

    print(f"[CLIENT] Conectare la {host}:{port} ...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
    except ConnectionRefusedError:
        print(f"[CLIENT] Nu ma pot conecta la {host}:{port}. Serverul pornit?")
        sys.exit(1)

    print("[CLIENT] Conectat! Asteapta meniu ...")

    stop_event = threading.Event()

    recv_thread = threading.Thread(target=receiver, args=(sock, stop_event), daemon=True)
    recv_thread.start()

    try:
        run_menu(sock, stop_event)
    except (KeyboardInterrupt, EOFError):
        print("\n[CLIENT] Intrerupt de utilizator.")
        send(sock, {"cmd": "quit"})
    finally:
        stop_event.set()
        try:
            sock.close()
        except OSError:
            pass
        print("[CLIENT] Conexiune inchisa.")


if __name__ == "__main__":
    main()
