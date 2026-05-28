import json
import socket
import threading


class ClientHandler(threading.Thread):
    def __init__(self, conn: socket.socket, addr, db, subscriptions: dict, subs_lock: threading.Lock, all_handlers: list, handlers_lock: threading.Lock):
        super().__init__(daemon=True)
        self.conn = conn
        self.addr = addr
        self.db = db

        
        self.subscriptions = subscriptions
        self.subs_lock = subs_lock

        self.all_handlers = all_handlers
        self.handlers_lock = handlers_lock

        self._send_lock = threading.Lock()  

    def run(self):
        print(f"[SERVER] Client conectat: {self.addr}")
        buffer = ""
        try:
            self.conn.settimeout(None)  
            while True:
                chunk = self.conn.recv(4096)
                if not chunk:
                    break  
                buffer += chunk.decode("utf-8")
               
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._process(line)
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        finally:
            self._cleanup()
            print(f"[SERVER] Client deconectat: {self.addr}")

    

    def _process(self, raw: str):
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            self._send({"status": "error", "message": "JSON invalid"})
            return

        cmd = msg.get("cmd", "").lower()

        if cmd == "select":
            self._handle_select(msg)
        elif cmd == "update":
            self._handle_update(msg)
        elif cmd == "delete":
            self._handle_delete(msg)
        elif cmd == "quit":
            self._send({"status": "ok", "message": "La revedere!"})
            self.conn.close()
        else:
            self._send({"status": "error", "message": f"Comanda necunoscuta: '{cmd}'"})

    

    def _handle_select(self, msg: dict):
        
        if "id" in msg:
            
            try:
                pid = int(msg["id"])
            except (ValueError, TypeError):
                self._send({"status": "error", "message": "Campul 'id' trebuie sa fie intreg."})
                return
            products = []
            p = self.db.get_by_id(pid)
            if p:
                products = [p]
        elif "id_min" in msg and "id_max" in msg:
            
            try:
                id_min = int(msg["id_min"])
                id_max = int(msg["id_max"])
            except (ValueError, TypeError):
                self._send({"status": "error", "message": "Campurile 'id_min'/'id_max' trebuie sa fie intregi."})
                return
            if id_min > id_max:
                self._send({"status": "error", "message": "id_min trebuie sa fie <= id_max."})
                return
            products = self.db.get_range(id_min, id_max)
        else:
            
            products = self.db.get_all()

        with self.subs_lock:
            for p in products:
                pid = p["id"]
                if pid not in self.subscriptions:
                    self.subscriptions[pid] = set()
                self.subscriptions[pid].add(self)

        self._send({"status": "ok", "products": products})

   

    def _handle_update(self, msg: dict):
        
        try:
            pid   = int(msg["id"])
            name  = str(msg["name"]).strip()
            price = float(msg["price"])
            stock = int(msg["stock"])
        except (KeyError, ValueError, TypeError) as e:
            self._send({"status": "error", "message": f"Campuri lipsa sau invalide: {e}"})
            return
        if not name:
            self._send({"status": "error", "message": "Campul 'name' nu poate fi gol."})
            return
        if price < 0:
            self._send({"status": "error", "message": "Pretul nu poate fi negativ."})
            return
        if stock < 0:
            self._send({"status": "error", "message": "Stocul nu poate fi negativ."})
            return

        updated = self.db.update(pid, name, price, stock)
        if updated is None:
            self._send({"status": "error", "message": f"Produsul cu id={pid} nu exista."})
            return

        self._send({"status": "ok", "product": updated})

        
        self._notify_subscribers(pid, "updated", updated)

   

    def _handle_delete(self, msg: dict):
        try:
            pid = int(msg["id"])
        except (KeyError, ValueError, TypeError):
            self._send({"status": "error", "message": "Campul 'id' trebuie sa fie intreg."})
            return

        deleted = self.db.delete(pid)
        if not deleted:
            self._send({"status": "error", "message": f"Produsul cu id={pid} nu exista."})
            return

        self._send({"status": "ok", "message": f"Produsul {pid} a fost sters."})

       
        self._notify_subscribers(pid, "deleted", None)
        with self.subs_lock:
            self.subscriptions.pop(pid, None)

    def _notify_subscribers(self, product_id: int, event: str, product):
        with self.subs_lock:
            subscribers = set(self.subscriptions.get(product_id, set()))

        notification = {"event": event, "product_id": product_id}
        if product is not None:
            notification["product"] = product

        for handler in subscribers:
            if handler is not self: 
                handler._send(notification)

    def _send(self, data: dict):
        """Serializeaza si trimite un mesaj JSON (newline-terminated)."""
        try:
            raw = json.dumps(data, ensure_ascii=False) + "\n"
            with self._send_lock:
                self.conn.sendall(raw.encode("utf-8"))
        except (BrokenPipeError, OSError):
            pass  

  

    def _cleanup(self):
        
        with self.subs_lock:
            empty_keys = []
            for pid, handlers in self.subscriptions.items():
                handlers.discard(self)
                if not handlers:
                    empty_keys.append(pid)
            for pid in empty_keys:
                del self.subscriptions[pid]
        with self.handlers_lock:
            try:
                self.all_handlers.remove(self)
            except ValueError:
                pass
        try:
            self.conn.close()
        except OSError:
            pass