import json
import math
import os
import time

import pygame

from client.network import NetworkClient
import assets.image_loader as assets
import assets.map_loader as maps


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

MAP_WIDTH = 1920
MAP_HEIGHT = 1280
FPS = 60

DEFAULT_SETTINGS = {
    "Resolution": [960, 540],
    "Server": "127.0.0.1",
    "Port": 5000,
    "Name": "Player",
    "Vehicle": "Sports Car",
    "Colour": "red",
    "Laps": 3,
}

VEHICLES = ["Family Car", "Sports Car", "Luxury Car", "Truck", "Race Car"]
COLOURS = ["red", "yellow", "green", "blue", "black"]
COLOUR_RGB = {
    "red": (255, 70, 55),
    "yellow": (255, 220, 70),
    "green": (80, 220, 120),
    "blue": (80, 160, 255),
    "black": (220, 220, 220),
}
# Tuned for deliberate, controllable arcade handling rather than the very fast
# prototype values.  (max speed, acceleration, steering speed)
VEHICLE_STATS = {
    "Family Car": (185.0, 1.55, 3.65),
    "Sports Car": (215.0, 1.75, 4.05),
    "Luxury Car": (200.0, 1.65, 3.95),
    "Truck": (165.0, 1.35, 3.20),
    "Race Car": (235.0, 1.85, 4.15),
}


def load_settings():
    data = dict(DEFAULT_SETTINGS)
    try:
        with open("settings.json", "r", encoding="utf-8") as fh:
            loaded = json.load(fh)
            if isinstance(loaded, dict):
                data.update(loaded)
    except (OSError, json.JSONDecodeError):
        pass
    return data


SETTINGS = load_settings()
WIDTH = max(640, min(int(SETTINGS.get("Resolution", [960, 540])[0]), 1920))
HEIGHT = max(360, min(int(SETTINGS.get("Resolution", [960, 540])[1]), 1080))

pygame.init()

window = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("Nitro Clash Multiplayer")
canvas = pygame.Surface((MAP_WIDTH, MAP_HEIGHT)).convert()
clock = pygame.time.Clock()

FONT_CACHE = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in FONT_CACHE:
        f = pygame.font.Font(None, size)
        f.set_bold(bold)
        FONT_CACHE[key] = f
    return FONT_CACHE[key]


def draw_text(surface, value, pos, size=32, colour=(255, 255, 255), center=True, bold=False):
    image = font(size, bold).render(str(value), True, colour)
    rect = image.get_rect()
    rect.center = pos if center else rect.center
    if not center:
        rect.topleft = pos
    surface.blit(image, rect)
    return rect


def fit_rect():
    scale = min(window.get_width() / MAP_WIDTH, window.get_height() / MAP_HEIGHT)
    draw_w = max(1, int(MAP_WIDTH * scale))
    draw_h = max(1, int(MAP_HEIGHT * scale))
    x = (window.get_width() - draw_w) // 2
    y = (window.get_height() - draw_h) // 2
    return pygame.Rect(x, y, draw_w, draw_h)


def present():
    rect = fit_rect()
    window.fill((0, 0, 0))
    window.blit(pygame.transform.smoothscale(canvas, rect.size), rect.topleft)
    pygame.display.flip()


def mouse_virtual():
    rect = fit_rect()
    mx, my = pygame.mouse.get_pos()
    if not rect.collidepoint(mx, my):
        return -1, -1
    return (
        int((mx - rect.left) * MAP_WIDTH / rect.width),
        int((my - rect.top) * MAP_HEIGHT / rect.height),
    )


def car_image(colour, vehicle, size=(46, 80)):
    try:
        image = pygame.image.load(assets.car(colour, vehicle)).convert()
        image = pygame.transform.smoothscale(image, size)
        image.set_colorkey((0, 0, 0))
        return image
    except (OSError, ValueError, pygame.error):
        surface = pygame.Surface(size, pygame.SRCALPHA)
        body = COLOUR_RGB.get(colour, (255, 255, 255))
        pygame.draw.polygon(surface, body, [
            (size[0] // 2, 0),
            (size[0] - 4, size[1] - 8),
            (size[0] // 2, size[1] - 2),
            (4, size[1] - 8),
        ])
        return surface


def load_map():
    mapping = {name: cls for name, cls in zip(maps.index, maps.objs)}
    map_obj = mapping.get("racetrack", maps.Racetrack)()

    full_map = pygame.Surface((MAP_WIDTH, MAP_HEIGHT)).convert()
    for layer in range(3):
        image = pygame.image.load(map_obj.layer(layer)).convert_alpha()
        if image.get_size() != (MAP_WIDTH, MAP_HEIGHT):
            image = pygame.transform.smoothscale(image, (MAP_WIDTH, MAP_HEIGHT))
        full_map.blit(image, (0, 0))

    track_image = pygame.image.load(map_obj.layer(2)).convert_alpha()
    if track_image.get_size() != (MAP_WIDTH, MAP_HEIGHT):
        track_image = pygame.transform.smoothscale(track_image, (MAP_WIDTH, MAP_HEIGHT))

    track_mask = pygame.mask.from_surface(track_image, 1)
    checkpoints = [pygame.Rect(*p) for p in map_obj.layer(3)]
    obstacles = [
        {"rect": pygame.Rect(*p[:4]), "kind": p[4]}
        for p in map_obj.layer(4)
    ]
    return map_obj, full_map, track_mask, checkpoints, obstacles


class LocalCar:
    def __init__(self, slot, vehicle, colour, name, map_obj, track_mask, checkpoints, obstacles, total_laps):
        self.slot = int(slot)
        self.vehicle = vehicle
        self.colour = colour
        self.name = name
        self.track_mask = track_mask
        self.checkpoints = list(checkpoints)
        self.obstacles = list(obstacles)
        self.total_laps = int(total_laps)

        px, py, rotation = map_obj.start_pos(((self.slot - 1) % 6) + 1)
        self.x = float(px)
        self.y = float(py)
        self.rotation = float(rotation)
        self.speed = 0.0
        self.lap = 0
        self.next_checkpoint = 1 if len(self.checkpoints) > 1 else 0
        self.finished = False
        self.finish_time_ms = None
        self.nitro_until = 0.0
        self.nitro_energy = 100.0
        self.image = car_image(colour, vehicle)
        self.off_track = False
        self.obstacle_hit_until = 0.0

        self.max_speed, self.accel, self.turn_speed = VEHICLE_STATS.get(
            vehicle, VEHICLE_STATS["Sports Car"]
        )

    def obstacle_hit(self, x, y):
        car_rect = self.image.get_rect(center=(round(x), round(y))).inflate(-18, -24)
        return next((item for item in self.obstacles if car_rect.colliderect(item["rect"])), None)

    @property
    def rect(self):
        return self.image.get_rect(center=(round(self.x), round(self.y)))

    def valid_position(self, x, y, rotation):
        rotated = pygame.transform.rotate(self.image, rotation)
        mask = pygame.mask.from_surface(rotated, 1)
        rect = rotated.get_rect(center=(round(x), round(y)))
        overlap = self.track_mask.overlap(mask, (rect.left, rect.top))
        return overlap is not None

    def update(self, dt, pressed_keys, race_running):
        if self.finished:
            self.speed = 0.0
            return

        if not race_running:
            self.speed *= 0.90
            return

        forward = pygame.K_w in pressed_keys or pygame.K_UP in pressed_keys
        reverse = pygame.K_s in pressed_keys or pygame.K_DOWN in pressed_keys
        left = pygame.K_a in pressed_keys or pygame.K_LEFT in pressed_keys
        right = pygame.K_d in pressed_keys or pygame.K_RIGHT in pressed_keys
        boost = pygame.K_LSHIFT in pressed_keys or pygame.K_RSHIFT in pressed_keys

        now = time.monotonic()
        if boost and forward and self.nitro_energy > 0.0:
            self.nitro_until = now + 0.12
            self.nitro_energy = max(0.0, self.nitro_energy - 34.0 * dt)
        else:
            self.nitro_energy = min(100.0, self.nitro_energy + 7.5 * dt)
        nitro = now < self.nitro_until and self.nitro_energy > 0.0

        max_speed = self.max_speed * (1.28 if nitro else 1.0)
        if forward:
            self.speed += self.accel * 60.0 * dt
        elif reverse:
            self.speed -= self.accel * 42.0 * dt
        else:
            self.speed *= max(0.0, 1.0 - 2.4 * dt)
        self.speed = max(-self.max_speed * 0.30, min(max_speed, self.speed))

        steering = (1 if left else 0) - (1 if right else 0)
        if abs(self.speed) > 8 and steering:
            # Steering becomes gentler at high speed, making corners easier to
            # hold without removing the arcade feel.
            speed_ratio = min(1.0, abs(self.speed) / max(1.0, self.max_speed))
            steer_factor = 1.08 - 0.30 * speed_ratio
            direction = 1.0 if self.speed >= 0 else -1.0
            self.rotation = (self.rotation + steering * self.turn_speed * direction * 60.0 * dt * steer_factor) % 360.0

        angle = math.radians(self.rotation - 90.0)
        distance = self.speed * dt
        nx = self.x - math.cos(angle) * distance
        ny = self.y + math.sin(angle) * distance

        hit = self.obstacle_hit(nx, ny)
        if hit:
            self.speed *= 0.42
            self.obstacle_hit_until = now + 0.18
            # Slide a little away from the obstacle instead of hard-resetting.
            nx = self.x + (nx - self.x) * 0.22
            ny = self.y + (ny - self.y) * 0.22

        if self.valid_position(nx, ny, self.rotation):
            self.x, self.y = nx, ny
            self.off_track = False
        else:
            # Track edges now feel like gravel rather than an invisible wall.
            self.speed *= 0.55
            self.off_track = True

        self.check_checkpoint()

    def check_checkpoint(self):
        if self.finished or not self.checkpoints:
            return
        target = self.checkpoints[self.next_checkpoint]
        if not self.rect.colliderect(target):
            return

        if self.next_checkpoint == 0:
            self.lap += 1
            if self.lap >= self.total_laps:
                self.finished = True
            self.next_checkpoint = 1 if len(self.checkpoints) > 1 else 0
        else:
            self.next_checkpoint += 1
            if self.next_checkpoint >= len(self.checkpoints):
                self.next_checkpoint = 0

    def draw(self, surface):
        sprite = pygame.transform.rotate(self.image, self.rotation)
        rect = sprite.get_rect(center=(round(self.x), round(self.y)))
        surface.blit(sprite, rect)

        marker = COLOUR_RGB.get(self.colour, (255, 255, 255))
        pygame.draw.polygon(surface, marker, [
            (round(self.x), rect.top - 4),
            (round(self.x) - 7, rect.top - 17),
            (round(self.x) + 7, rect.top - 17),
        ])
        draw_text(surface, self.name, (round(self.x), rect.top - 31), 20)

        if self.nitro_until > time.monotonic() and self.speed > 0:
            pygame.draw.circle(surface, (80, 190, 255), (round(self.x), round(self.y)), 30, 2)


class RemoteCar:
    def __init__(self, state):
        self.player_id = int(state["player_id"])
        self.x = float(state.get("x", 0.0))
        self.y = float(state.get("y", 0.0))
        self.tx = self.x
        self.ty = self.y
        self.rotation = float(state.get("rotation", 0.0))
        self.trotation = self.rotation
        self.lap = int(state.get("lap", 0))
        self.finished = bool(state.get("finished", False))
        self.name = "Player"
        self.vehicle = "Sports Car"
        self.colour = "red"
        self.image = car_image(self.colour, self.vehicle)

    def update_profile(self, player):
        vehicle = player.get("vehicle", self.vehicle)
        colour = player.get("colour", self.colour)
        if vehicle != self.vehicle or colour != self.colour:
            self.vehicle = vehicle
            self.colour = colour
            self.image = car_image(colour, vehicle)
        self.name = player.get("name", self.name)

    def update(self, state):
        self.tx = float(state.get("x", self.tx))
        self.ty = float(state.get("y", self.ty))
        self.trotation = float(state.get("rotation", self.trotation))
        self.lap = int(state.get("lap", self.lap))
        self.finished = bool(state.get("finished", self.finished))

    def step(self):
        self.x += (self.tx - self.x) * 0.30
        self.y += (self.ty - self.y) * 0.30
        diff = (self.trotation - self.rotation + 180.0) % 360.0 - 180.0
        self.rotation = (self.rotation + diff * 0.30) % 360.0

    def draw(self, surface):
        self.step()
        sprite = pygame.transform.rotate(self.image, self.rotation)
        if self.finished:
            sprite = sprite.copy()
            sprite.set_alpha(150)
        rect = sprite.get_rect(center=(round(self.x), round(self.y)))
        surface.blit(sprite, rect)

        marker = COLOUR_RGB.get(self.colour, (255, 255, 255))
        pygame.draw.polygon(surface, marker, [
            (round(self.x), rect.top - 4),
            (round(self.x) - 7, rect.top - 17),
            (round(self.x) + 7, rect.top - 17),
        ])
        draw_text(surface, self.name, (round(self.x), rect.top - 31), 20)


class MultiplayerGame:
    def __init__(self):
        self.network = None
        self.state = "connect"
        self.name = str(SETTINGS.get("Name", "Player"))[:16] or "Player"
        self.server_host = str(SETTINGS.get("Server", "127.0.0.1"))
        self.server_port = int(SETTINGS.get("Port", 5000))
        self.total_laps = max(1, min(int(SETTINGS.get("Laps", 3)), 20))

        self.name_cursor = True
        self.host_cursor = False
        self.editing_name = False
        self.message = ""

        self.vehicle_index = VEHICLES.index(SETTINGS["Vehicle"]) if SETTINGS.get("Vehicle") in VEHICLES else 1
        self.colour_index = COLOURS.index(SETTINGS["Colour"]) if SETTINGS.get("Colour") in COLOURS else 0
        self.ready = False

        (
            self.map_obj,
            self.map_surface,
            self.track_mask,
            self.checkpoints,
            self.obstacles,
        ) = load_map()
        self.local_car = None
        self.remote_cars = {}
        self.race_running = False
        self.last_state_send = 0.0
        self.local_finish_sent = False

        self.pressed_keys = set()

    @property
    def vehicle(self):
        return VEHICLES[self.vehicle_index]

    @property
    def colour(self):
        return COLOURS[self.colour_index]

    def connect(self):
        self.network = NetworkClient(self.server_host, self.server_port)
        if self.network.connect():
            self.network.set_profile(self.name, self.vehicle, self.colour)
            self.state = "lobby"
            self.message = "Connected. SPACE = Ready. ENTER = Start when everyone is ready."
        else:
            self.message = self.network.error or "Could not connect to server."
            self.state = "connect"

    def disconnect(self):
        if self.network:
            self.network.disconnect(silent=True)
        self.network = None
        self.remote_cars.clear()
        self.local_car = None
        self.ready = False
        self.race_running = False
        self.local_finish_sent = False
        self.pressed_keys.clear()

    def build_race(self):
        players = self.network.get_players()
        me = players.get(self.network.player_id, {})

        slot = int(me.get("slot", self.network.slot))
        self.name = me.get("name", self.name)
        if me.get("vehicle") in VEHICLES:
            self.vehicle_index = VEHICLES.index(me["vehicle"])
        if me.get("colour") in COLOURS:
            self.colour_index = COLOURS.index(me["colour"])

        self.local_car = LocalCar(
            slot,
            self.vehicle,
            self.colour,
            self.name,
            self.map_obj,
            self.track_mask,
            self.checkpoints,
            self.obstacles,
            self.total_laps,
        )

        self.remote_cars.clear()
        for pid, player in players.items():
            if pid == self.network.player_id:
                continue
            slot = int(player.get("slot", 1))
            x, y, rotation = self.map_obj.start_pos(((slot - 1) % 6) + 1)
            remote = RemoteCar({"player_id": pid, "x": x, "y": y, "rotation": rotation})
            remote.update_profile(player)
            self.remote_cars[pid] = remote

        self.race_running = False
        self.local_finish_sent = False
        self.state = "countdown"
        self.pressed_keys.clear()

    def process_network(self):
        if not self.network:
            return

        if not self.network.connected and self.state not in {"connect", "results"}:
            self.message = self.network.error or "Connection lost."
            self.disconnect()
            self.state = "connect"
            return

        players = self.network.get_players()
        present_ids = set(players)
        self.remote_cars = {pid: car for pid, car in self.remote_cars.items() if pid in present_ids and pid != self.network.player_id}

        for pid, player in players.items():
            if pid == self.network.player_id:
                continue
            remote = self.remote_cars.get(pid)
            if remote is None:
                remote = RemoteCar({"player_id": pid})
                self.remote_cars[pid] = remote
            remote.update_profile(player)

        for pid, state in self.network.get_remote_states().items():
            if pid == self.network.player_id:
                continue
            remote = self.remote_cars.get(pid)
            if remote is None:
                remote = RemoteCar(state)
                self.remote_cars[pid] = remote
            remote.update(state)

        phase = self.network.phase
        if phase == "countdown" and self.state not in {"countdown", "race"}:
            self.build_race()
        elif phase == "results" and self.state != "results":
            self.state = "results"
            self.race_running = False
            self.pressed_keys.clear()
        elif phase == "lobby" and self.state == "results":
            self.state = "lobby"

    def toggle_ready(self):
        if not self.network:
            return
        self.ready = not self.ready
        self.network.set_ready(self.ready)
        self.message = "READY." if self.ready else "NOT READY."

    def start_race_request(self):
        if not self.network:
            return
        if self.ready:
            self.network.request_start()
        else:
            self.message = "Press SPACE to become READY first."

    def update_race(self, dt):
        if not self.local_car or not self.network:
            return

        start_ms = self.network.get_race_start_ms()
        if start_ms is not None and self.network.get_server_time_ms() >= start_ms:
            self.race_running = True
            self.state = "race"

        race_time = self.network.get_race_time_seconds()
        self.local_car.update(dt, self.pressed_keys, self.race_running)

        if self.local_car.finished and not self.local_finish_sent:
            self.local_finish_sent = True
            self.local_car.finish_time_ms = race_time * 1000.0
            self.network.send_finish(self.local_car.finish_time_ms)

        now = time.monotonic()
        if now - self.last_state_send >= 1.0 / 20.0:
            self.last_state_send = now
            self.network.send_state(self.local_car)

    def draw_connect(self):
        canvas.fill((18, 22, 28))
        cx = MAP_WIDTH // 2
        draw_text(canvas, "NITRO CLASH", (cx, 180), 120, bold=True)
        draw_text(canvas, "MULTIPLAYER", (cx, 275), 60, (90, 190, 255), bold=True)

        draw_text(canvas, "Server IP", (510, 410), 38, (140, 210, 255) if self.host_cursor else (200, 200, 200))
        pygame.draw.rect(canvas, (35, 40, 50), (720, 365, 720, 72), border_radius=10)
        draw_text(canvas, self.server_host or "127.0.0.1", (745, 402), 34, center=False)

        draw_text(canvas, "Player name", (510, 520), 38, (140, 210, 255) if self.name_cursor else (200, 200, 200))
        pygame.draw.rect(canvas, (35, 40, 50), (720, 475, 720, 72), border_radius=10)
        draw_text(canvas, self.name or "Player", (745, 512), 34, center=False)

        draw_text(canvas, "Click a field or TAB to switch | ENTER: connect | ESC: quit", (cx, 680), 30, (160, 170, 185))
        draw_text(canvas, self.message, (cx, 770), 30, (255, 150, 120) if self.message else (180, 220, 180))

    def draw_lobby(self):
        canvas.fill((22, 27, 34))
        cx = MAP_WIDTH // 2
        draw_text(canvas, "MULTIPLAYER LOBBY", (cx, 125), 88, bold=True)
        draw_text(canvas, f"Server: {self.server_host}:{self.server_port}", (cx, 180), 30, (150, 165, 180))

        players = self.network.get_players()
        draw_text(canvas, f"Players {len(players)}/6", (cx, 235), 42, bold=True)

        y = 330
        for _, player in sorted(players.items(), key=lambda item: item[1].get("slot", 99)):
            col = COLOUR_RGB.get(player.get("colour", "red"), (255, 255, 255))
            pygame.draw.rect(canvas, (38, 45, 56), (325, y - 38, 1270, 82), border_radius=11)
            draw_text(canvas, f"P{player.get('slot', '?')}", (370, y + 5), 34, col, center=False, bold=True)
            draw_text(canvas, player.get("name", "Player"), (500, y + 5), 32, center=False)
            draw_text(canvas, player.get("vehicle", "Sports Car"), (930, y + 5), 30, (175, 185, 195), center=False)
            status = "READY" if player.get("ready") else "NOT READY"
            status_col = (100, 230, 130) if player.get("ready") else (255, 160, 100)
            draw_text(canvas, status, (1280, y + 5), 28, status_col, center=False, bold=True)
            if int(player.get("id", -1)) == self.network.player_id:
                draw_text(canvas, "YOU", (1450, y + 5), 24, (120, 190, 255), center=False, bold=True)
            y += 95

        draw_text(canvas, "TAB Rename | SPACE Ready | ENTER Start | 1-5 Vehicle | R/G/B/Y/K Colour", (cx, 965), 27, (195, 205, 215))
        draw_text(canvas, self.message, (cx, 1025), 26, (170, 190, 200))

    def draw_countdown(self):
        canvas.blit(self.map_surface, (0, 0))
        if self.local_car:
            self.local_car.draw(canvas)
        for remote in self.remote_cars.values():
            remote.draw(canvas)

        start = self.network.get_race_start_ms()
        remaining = max(0.0, (start - self.network.get_server_time_ms()) / 1000.0) if start is not None else 0.0
        if remaining > 0.05:
            draw_text(canvas, str(math.ceil(remaining)), (MAP_WIDTH // 2, MAP_HEIGHT // 2), 220, bold=True)
            draw_text(canvas, "GET READY", (MAP_WIDTH // 2, 900), 44, (255, 220, 110), bold=True)
        else:
            draw_text(canvas, "GO!", (MAP_WIDTH // 2, MAP_HEIGHT // 2), 180, (100, 255, 140), bold=True)

    def draw_obstacles(self):
        now = time.monotonic()
        for item in self.obstacles:
            rect = item["rect"]
            kind = item["kind"]
            if kind == "barrier":
                pygame.draw.rect(canvas, (38, 42, 48), rect.inflate(8, 8), border_radius=6)
                pygame.draw.rect(canvas, (235, 120, 45), rect, border_radius=5)
                stripe_w = max(8, rect.width // 5)
                for x in range(rect.left, rect.right, stripe_w * 2):
                    pygame.draw.rect(canvas, (245, 235, 210), (x, rect.top, min(stripe_w, rect.right - x), rect.height))
            elif kind == "tire":
                cx, cy = rect.center
                pygame.draw.ellipse(canvas, (28, 30, 34), rect)
                pygame.draw.ellipse(canvas, (75, 80, 86), rect.inflate(-10, -10))
                pygame.draw.ellipse(canvas, (25, 27, 30), rect.inflate(-17, -17))
            else:
                pygame.draw.circle(canvas, (235, 150, 45), rect.center, min(rect.width, rect.height) // 2)
                pygame.draw.circle(canvas, (255, 225, 110), rect.center, max(3, min(rect.width, rect.height) // 6))

        if self.local_car and self.local_car.obstacle_hit_until > now:
            draw_text(canvas, "OBSTACLE!", (MAP_WIDTH // 2, 112), 30, (255, 175, 80), bold=True)

    def draw_race_hud(self):
        car = self.local_car
        if not car or not self.network:
            return

        # Top race strip
        pygame.draw.rect(canvas, (8, 12, 18), (0, 0, MAP_WIDTH, 104))
        pygame.draw.line(canvas, (65, 75, 88), (0, 103), (MAP_WIDTH, 103), 2)
        lap_display = min(car.lap + 1, self.total_laps)
        race_time = self.network.get_race_time_seconds()
        speed_kmh = int(abs(car.speed) * 0.42)
        draw_text(canvas, f"LAP {lap_display}/{self.total_laps}", (55, 52), 38, center=False, bold=True)
        draw_text(canvas, f"{race_time:05.1f}", (390, 51), 38, (215, 225, 235), center=False, bold=True)
        draw_text(canvas, "TIME", (390, 25), 18, (120, 135, 150), center=False)

        # Position is based on completed laps and checkpoint progress.
        racers = []
        for _, player in self.network.get_players().items():
            pid = int(player.get("id", -1))
            if pid == self.network.player_id:
                progress = car.lap * len(self.checkpoints) + max(0, car.next_checkpoint - 1)
                finished = car.finished
            else:
                remote = self.remote_cars.get(pid)
                progress = (remote.lap * len(self.checkpoints) + max(0, remote.lap)) if remote else 0
                finished = remote.finished if remote else False
            racers.append((finished, progress, pid))
        racers.sort(key=lambda v: (not v[0], -v[1]))
        position = next((i + 1 for i, entry in enumerate(racers) if entry[2] == self.network.player_id), 1)
        draw_text(canvas, f"P{position}/{max(1, len(racers))}", (760, 52), 38, (255, 220, 110), center=False, bold=True)

        # Speed + nitro card
        pygame.draw.rect(canvas, (20, 27, 35), (1040, 16, 390, 72), border_radius=12)
        draw_text(canvas, f"{speed_kmh:03d} KM/H", (1065, 43), 34, center=False, bold=True)
        draw_text(canvas, "NITRO", (1270, 28), 17, (130, 145, 160), center=False)
        pygame.draw.rect(canvas, (48, 55, 64), (1270, 52, 130, 16), border_radius=8)
        fill_w = int(126 * max(0.0, min(1.0, car.nitro_energy / 100.0)))
        if fill_w:
            pygame.draw.rect(canvas, (70, 185, 255), (1272, 54, fill_w, 12), border_radius=6)

        # Compact racer list
        y = 126
        for _, player in sorted(self.network.get_players().items(), key=lambda item: item[1].get("slot", 99)):
            pid = int(player.get("id", -1))
            if pid == self.network.player_id:
                lap = car.lap
                finished = car.finished
            else:
                remote = self.remote_cars.get(pid)
                lap = remote.lap if remote else 0
                finished = remote.finished if remote else False
            colour = COLOUR_RGB.get(player.get("colour", "red"), (255, 255, 255))
            bg = (12, 17, 23, 225)
            panel = pygame.Surface((365, 38), pygame.SRCALPHA)
            panel.fill(bg)
            canvas.blit(panel, (24, y - 7))
            label = f"P{player.get('slot', '?')}  {player.get('name', 'Player')[:12]}"
            draw_text(canvas, label, (38, y + 12), 22, colour if not finished else (145, 150, 158), center=False)
            draw_text(canvas, f"{min(lap + 1, self.total_laps)}/{self.total_laps}", (350, y + 12), 20, (205, 215, 225), center=False)
            y += 43

        draw_text(canvas, "WASD / ARROWS  DRIVE     SHIFT  NITRO     ESC  EXIT", (MAP_WIDTH // 2, MAP_HEIGHT - 34), 22, (205, 215, 225), bold=True)

    def draw_race(self):
        canvas.blit(self.map_surface, (0, 0))
        self.draw_obstacles()
        for remote in self.remote_cars.values():
            remote.draw(canvas)
        if self.local_car:
            self.local_car.draw(canvas)
        self.draw_race_hud()

        if self.local_car and self.local_car.finished:
            pygame.draw.rect(canvas, (8, 13, 18), (575, 515, 770, 175), border_radius=24)
            pygame.draw.rect(canvas, (90, 230, 140), (575, 515, 770, 175), 2, border_radius=24)
            draw_text(canvas, "FINISH!", (960, 570), 82, (100, 255, 140), bold=True)
            draw_text(canvas, "Waiting for the other racers...", (960, 640), 32, (220, 225, 230))

    def draw_results(self):
        canvas.fill((17, 21, 27))
        cx = MAP_WIDTH // 2
        draw_text(canvas, "RACE RESULTS", (cx, 125), 96, bold=True)
        y = 260
        for result in self.network.get_results():
            pos = result.get("position", "-")
            name = result.get("name", "Player")
            ms = result.get("time_ms")
            time_str = "DNF" if ms is None else f"{float(ms) / 1000.0:.1f}s"
            mine = result.get("player_id") == self.network.player_id
            bg = (40, 56, 70) if mine else (32, 38, 46)
            pygame.draw.rect(canvas, bg, (390, y - 36, 1140, 82), border_radius=12)
            draw_text(canvas, f"#{pos}", (450, y + 5), 36, (255, 220, 100), center=False, bold=True)
            draw_text(canvas, name, (565, y + 5), 34, center=False, bold=mine)
            draw_text(canvas, time_str, (1365, y + 5), 32, (190, 205, 220), center=False)
            y += 100
        draw_text(canvas, "R = Rematch     ESC = Quit", (cx, 930), 36, (190, 200, 210))

    def draw(self):
        if self.state == "connect":
            self.draw_connect()
        elif self.state == "lobby":
            self.draw_lobby()
        elif self.state == "countdown":
            self.draw_countdown()
        elif self.state == "race":
            self.draw_race()
        elif self.state == "results":
            self.draw_results()
        present()

    def handle_event(self, event):
        if event.type == pygame.VIDEORESIZE:
            global window
            window = pygame.display.set_mode(event.size, pygame.RESIZABLE)
            return None

        if event.type == pygame.QUIT:
            return "quit"

        focus_lost = getattr(pygame, "WINDOWFOCUSLOST", None)
        if focus_lost is not None and event.type == focus_lost:
            self.pressed_keys.clear()
            return None

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()
                return None

            if self.state in {"countdown", "race"}:
                self.pressed_keys.add(event.key)
                if event.key == pygame.K_ESCAPE:
                    self.disconnect()
                    self.state = "connect"
                    self.message = "Disconnected from the race."
                return None

            if self.state == "connect":
                if event.key == pygame.K_ESCAPE:
                    return "quit"
                if event.key == pygame.K_TAB:
                    self.name_cursor, self.host_cursor = self.host_cursor, self.name_cursor
                elif event.key == pygame.K_BACKSPACE:
                    if self.name_cursor:
                        self.name = self.name[:-1]
                    elif self.host_cursor:
                        self.server_host = self.server_host[:-1]
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.connect()
                elif event.unicode and event.unicode.isprintable():
                    if self.name_cursor and len(self.name) < 16:
                        self.name = ("" if self.name == "Player" else self.name) + event.unicode
                    elif self.host_cursor and len(self.server_host) < 64:
                        self.server_host = ("" if self.server_host == "127.0.0.1" else self.server_host) + event.unicode
                return None

            if self.state == "lobby":
                if event.key == pygame.K_ESCAPE:
                    self.disconnect()
                    self.state = "connect"
                    return None
                if self.editing_name:
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self.editing_name = False
                        self.name = self.name.strip() or "Player"
                        self.network.set_profile(self.name, self.vehicle, self.colour)
                    elif event.key == pygame.K_BACKSPACE:
                        self.name = self.name[:-1]
                        self.network.set_profile(self.name or "Player", self.vehicle, self.colour)
                    elif event.unicode and event.unicode.isprintable() and len(self.name) < 16:
                        self.name += event.unicode
                        self.network.set_profile(self.name, self.vehicle, self.colour)
                else:
                    if event.key == pygame.K_TAB:
                        self.editing_name = True
                        self.message = "Type your name, ENTER to finish."
                    elif event.key == pygame.K_SPACE:
                        self.toggle_ready()
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self.start_race_request()
                    elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                        self.vehicle_index = event.key - pygame.K_1
                        self.network.set_profile(self.name or "Player", self.vehicle, self.colour)
                    elif event.key in (pygame.K_r, pygame.K_g, pygame.K_b, pygame.K_y, pygame.K_k):
                        self.colour_index = {
                            pygame.K_r: 0,
                            pygame.K_y: 1,
                            pygame.K_g: 2,
                            pygame.K_b: 3,
                            pygame.K_k: 4,
                        }[event.key]
                        self.network.set_profile(self.name or "Player", self.vehicle, self.colour)
                return None

            if self.state == "results":
                if event.key == pygame.K_r:
                    self.network.request_reset()
                    self.state = "lobby"
                    self.ready = False
                    self.message = "Rematch lobby. SPACE = Ready."
                elif event.key == pygame.K_ESCAPE:
                    self.disconnect()
                    self.state = "connect"
                return None

        elif event.type == pygame.KEYUP:
            self.pressed_keys.discard(event.key)

        return None


def main():
    game = MultiplayerGame()
    running = True

    while running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)

        for event in pygame.event.get():
            if game.handle_event(event) == "quit":
                running = False

        if not running:
            break

        if game.network:
            game.process_network()

        if game.state == "countdown":
            start_ms = game.network.get_race_start_ms() if game.network else None
            if start_ms is not None and game.network.get_server_time_ms() >= start_ms:
                game.race_running = True
                game.state = "race"
        elif game.state == "race":
            game.update_race(dt)

        game.draw()

    game.disconnect()
    pygame.quit()


if __name__ == "__main__":
    main()
