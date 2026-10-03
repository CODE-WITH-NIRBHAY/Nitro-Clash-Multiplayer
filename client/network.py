import json
import socket
import threading
import time
from copy import deepcopy


PROTOCOL_VERSION = 3


class NetworkClient:
    """Small thread-safe TCP client using newline-delimited JSON."""

    def __init__(self, host="127.0.0.1", port=5000, timeout=5.0):
        self.host = str(host)
        self.port = int(port)
        self.timeout = float(timeout)

        self.socket = None
        self.connected = False
        self.player_id = None
        self.slot = 1
        self.phase = "offline"
        self.error = None
        self.server_offset_ms = 0.0

        self._send_lock = threading.Lock()
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None

        self._players = {}
        self._remote_states = {}
        self._race_start_ms = None
        self._race_id = 0
        self._results = []

    def connect(self):
        self.disconnect(silent=True)
        self.error = None
        self._stop.clear()

        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            sock.settimeout(None)
            self.socket = sock
            self.connected = True
            self.phase = "connecting"

            self._thread = threading.Thread(
                target=self._receive_loop,
                name="nitro-network-recv",
                daemon=True,
            )
            self._thread.start()

            if not self.send({"type": "hello", "protocol": PROTOCOL_VERSION}):
                self.error = self.error or "Could not send hello message."
                self.disconnect(silent=True)
                return False

            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                with self._lock:
                    if self.player_id is not None:
                        return True
                    connected = self.connected
                if not connected:
                    break
                time.sleep(0.01)

            self.error = self.error or "Server did not send a welcome message."
            self.disconnect(silent=True)
            return False

        except OSError as exc:
            self.error = str(exc)
            self.connected = False
            self.phase = "offline"
            return False

    def _receive_loop(self):
        buffer = b""
        sock = self.socket

        try:
            while not self._stop.is_set() and sock is not None:
                data = sock.recv(65536)
                if not data:
                    break
                buffer += data

                while b"\n" in buffer:
                    raw_line, buffer = buffer.split(b"\n", 1)
                    if not raw_line.strip():
                        continue
                    try:
                        message = json.loads(raw_line.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue
                    self._handle_message(message)

        except OSError as exc:
            if not self._stop.is_set():
                self.error = str(exc)
        finally:
            with self._lock:
                self.connected = False
                if self.phase not in {"offline", "results"}:
                    self.phase = "disconnected"

    def _handle_message(self, message):
        message_type = message.get("type")
        now_ms = time.time() * 1000.0

        with self._lock:
            if message_type == "welcome":
                self.player_id = int(message["player_id"])
                self.slot = int(message.get("slot", self.player_id))
                server_time = float(message.get("server_time_ms", now_ms))
                self.server_offset_ms = server_time - now_ms
                self.phase = message.get("phase", "lobby")

            elif message_type == "room":
                players = {}
                for item in message.get("players", []):
                    try:
                        pid = int(item["id"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    players[pid] = deepcopy(item)
                self._players = players
                self.phase = message.get("phase", self.phase)

            elif message_type == "race_start":
                self._race_id = int(message.get("race_id", self._race_id + 1))
                self._race_start_ms = float(message.get("start_at_ms", now_ms))
                self.phase = "countdown"

            elif message_type == "state":
                try:
                    pid = int(message["player_id"])
                except (KeyError, TypeError, ValueError):
                    return
                if pid != self.player_id:
                    self._remote_states[pid] = deepcopy(message)

            elif message_type == "finish":
                try:
                    pid = int(message["player_id"])
                except (KeyError, TypeError, ValueError):
                    return
                if pid != self.player_id:
                    existing = self._remote_states.get(pid, {"player_id": pid})
                    existing["finished"] = True
                    existing["finish_time_ms"] = message.get("finish_time_ms")
                    self._remote_states[pid] = existing

            elif message_type == "results":
                self._results = deepcopy(message.get("results", []))
                self.phase = "results"

            elif message_type == "race_reset":
                self._race_start_ms = None
                self._results = []
                self._remote_states.clear()
                self.phase = "lobby"

            elif message_type == "error":
                self.error = str(message.get("message", "Server error"))

    def send(self, message):
        sock = self.socket
        if not self.connected or sock is None:
            return False

        payload = (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            with self._send_lock:
                sock.sendall(payload)
            return True
        except OSError as exc:
            self.error = str(exc)
            self.connected = False
            return False

    def set_profile(self, name, vehicle, colour):
        return self.send({
            "type": "profile",
            "name": str(name)[:16],
            "vehicle": str(vehicle),
            "colour": str(colour),
        })

    def set_ready(self, ready):
        return self.send({"type": "ready", "ready": bool(ready)})

    def request_start(self):
        return self.send({"type": "start"})

    def send_state(self, car):
        return self.send({
            "type": "state",
            "x": float(car.x),
            "y": float(car.y),
            "rotation": float(car.rotation) % 360.0,
            "speed": float(car.speed),
            "lap": int(car.lap),
            "finished": bool(car.finished),
            "finish_time_ms": car.finish_time_ms,
        })

    def send_finish(self, finish_time_ms):
        return self.send({"type": "finish", "finish_time_ms": float(finish_time_ms)})

    def request_reset(self):
        return self.send({"type": "reset"})

    def get_players(self):
        with self._lock:
            return deepcopy(self._players)

    def get_remote_states(self):
        with self._lock:
            return deepcopy(self._remote_states)

    def get_results(self):
        with self._lock:
            return deepcopy(self._results)

    def get_server_time_ms(self):
        return time.time() * 1000.0 + self.server_offset_ms

    def get_race_start_ms(self):
        with self._lock:
            return self._race_start_ms

    def get_race_time_seconds(self):
        start = self.get_race_start_ms()
        if start is None:
            return 0.0
        return max(0.0, (self.get_server_time_ms() - start) / 1000.0)

    def disconnect(self, silent=False):
        was_connected = self.connected
        self._stop.set()
        self.connected = False
        self.phase = "offline"
        sock = self.socket
        self.socket = None
        self.player_id = None

        with self._lock:
            self._players.clear()
            self._remote_states.clear()
            self._race_start_ms = None
            self._results.clear()

        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

        if not silent and was_connected:
            print("[NETWORK] Disconnected.")
