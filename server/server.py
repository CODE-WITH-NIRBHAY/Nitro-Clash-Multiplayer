import asyncio
import json
import time


HOST = "0.0.0.0"
PORT = 5000
MAX_PLAYERS = 6
MIN_PLAYERS_TO_START = 1
TOTAL_LAPS = 3
MAP_NAME = "racetrack"
COUNTDOWN_SECONDS = 3.5
RACE_TIMEOUT_SECONDS = 180

clients = {}
next_player_id = 1
race_id = 0
race_active = False
race_start_at_ms = None
race_timeout_task = None


VEHICLES = {"Family Car", "Sports Car", "Luxury Car", "Truck", "Race Car"}
COLOURS = {"red", "yellow", "green", "blue", "black"}


def now_ms():
    return time.time() * 1000.0


async def send_message(writer, message):
    writer.write((json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8"))
    await writer.drain()


async def safe_send(player, message):
    try:
        await send_message(player["writer"], message)
        return True
    except (ConnectionResetError, BrokenPipeError, OSError):
        return False


async def broadcast(message, exclude=None):
    dead = []
    for pid, player in list(clients.items()):
        if pid == exclude:
            continue
        if not await safe_send(player, message):
            dead.append(pid)
    for pid in dead:
        clients.pop(pid, None)


def player_payload(player):
    return {
        "id": player["id"],
        "slot": player["slot"],
        "name": player["name"],
        "vehicle": player["vehicle"],
        "colour": player["colour"],
        "ready": player["ready"],
        "connected": True,
    }


async def broadcast_room():
    await broadcast({
        "type": "room",
        "phase": "race" if race_active else "lobby",
        "players": [player_payload(p) for p in sorted(clients.values(), key=lambda x: x["slot"])],
        "max_players": MAX_PLAYERS,
        "min_players": MIN_PLAYERS_TO_START,
    })


async def start_race():
    global race_id, race_active, race_start_at_ms, race_timeout_task

    if race_active:
        return False
    if len(clients) < MIN_PLAYERS_TO_START:
        return False
    if not clients or not all(p["ready"] for p in clients.values()):
        return False

    race_id += 1
    race_active = True
    race_start_at_ms = now_ms() + COUNTDOWN_SECONDS * 1000.0

    for player in clients.values():
        player["finished"] = False
        player["finish_time_ms"] = None
        player["state"] = None

    await broadcast_room()
    await broadcast({
        "type": "race_start",
        "race_id": race_id,
        "map": MAP_NAME,
        "total_laps": TOTAL_LAPS,
        "start_at_ms": race_start_at_ms,
    })

    print(f"[SERVER] Race {race_id} started countdown for {len(clients)} player(s).")

    if race_timeout_task and not race_timeout_task.done():
        race_timeout_task.cancel()
    race_timeout_task = asyncio.create_task(race_timeout_watch(race_id))
    return True


async def race_timeout_watch(expected_race_id):
    global race_active, race_start_at_ms
    try:
        await asyncio.sleep(RACE_TIMEOUT_SECONDS)
    except asyncio.CancelledError:
        return

    if race_active and race_id == expected_race_id:
        race_active = False
        race_start_at_ms = None
        print(f"[SERVER] Race {expected_race_id} timed out.")
        await send_results()
        await broadcast_room()


def reseat_players():
    for slot, player in enumerate(sorted(clients.values(), key=lambda p: p["id"]), 1):
        player["slot"] = slot


def result_payload():
    ordered = sorted(
        clients.values(),
        key=lambda p: (
            0 if p["finished"] else 1,
            p["finish_time_ms"] if p["finish_time_ms"] is not None else float("inf"),
            p["slot"],
        ),
    )
    return [
        {
            "position": position,
            "player_id": p["id"],
            "slot": p["slot"],
            "name": p["name"],
            "time_ms": p["finish_time_ms"],
            "finished": p["finished"],
        }
        for position, p in enumerate(ordered, 1)
    ]


async def send_results():
    await broadcast({"type": "results", "results": result_payload()})


async def finish_player(player_id, finish_time_ms):
    global race_active, race_start_at_ms

    player = clients.get(player_id)
    if not player or not race_active or player["finished"]:
        return

    player["finished"] = True
    player["finish_time_ms"] = max(0.0, float(finish_time_ms))

    await broadcast({
        "type": "finish",
        "player_id": player_id,
        "finish_time_ms": player["finish_time_ms"],
    })

    if clients and all(p["finished"] for p in clients.values()):
        race_active = False
        race_start_at_ms = None
        await send_results()
        await broadcast_room()


async def reset_race():
    global race_active, race_start_at_ms, race_timeout_task

    race_active = False
    race_start_at_ms = None

    if race_timeout_task and not race_timeout_task.done():
        race_timeout_task.cancel()
    race_timeout_task = None

    for p in clients.values():
        p["ready"] = False
        p["finished"] = False
        p["finish_time_ms"] = None
        p["state"] = None

    await broadcast({"type": "race_reset"})
    await broadcast_room()


async def handle_client(reader, writer):
    global next_player_id

    if race_active:
        await send_message(writer, {
            "type": "error",
            "message": "A race is already in progress. Try again after it ends.",
        })
        writer.close()
        await writer.wait_closed()
        return

    if len(clients) >= MAX_PLAYERS:
        await send_message(writer, {
            "type": "error",
            "message": "Server is full (6 players maximum).",
        })
        writer.close()
        await writer.wait_closed()
        return

    player_id = next_player_id
    next_player_id += 1
    slot = len(clients) + 1

    player = {
        "id": player_id,
        "slot": slot,
        "writer": writer,
        "name": f"Player {slot}",
        "vehicle": "Sports Car",
        "colour": ["red", "yellow", "green", "blue", "black", "red"][slot - 1],
        "ready": False,
        "finished": False,
        "finish_time_ms": None,
        "state": None,
    }
    clients[player_id] = player

    address = writer.get_extra_info("peername")
    print(f"[SERVER] Player {player_id} connected from {address}")

    await send_message(writer, {
        "type": "welcome",
        "player_id": player_id,
        "slot": slot,
        "server_time_ms": now_ms(),
        "phase": "lobby",
    })
    await broadcast_room()

    buffer = b""

    try:
        while True:
            data = await reader.read(65536)
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

                current = clients.get(player_id)
                if current is None:
                    break

                message_type = message.get("type")

                if message_type == "hello":
                    if int(message.get("protocol", -1)) != 3:
                        await safe_send(current, {
                            "type": "error",
                            "message": "Protocol version mismatch.",
                        })
                        return

                elif message_type == "profile" and not race_active:
                    name = " ".join(str(message.get("name", current["name"])).split())[:16]
                    current["name"] = name or current["name"]

                    vehicle = str(message.get("vehicle", current["vehicle"]))
                    colour = str(message.get("colour", current["colour"]))
                    if vehicle in VEHICLES:
                        current["vehicle"] = vehicle
                    if colour in COLOURS:
                        current["colour"] = colour

                    await broadcast_room()

                elif message_type == "ready" and not race_active:
                    current["ready"] = bool(message.get("ready"))
                    await broadcast_room()

                elif message_type == "start" and not race_active:
                    if len(clients) < MIN_PLAYERS_TO_START:
                        await safe_send(current, {"type": "error", "message": "Not enough players."})
                    elif not all(p["ready"] for p in clients.values()):
                        await safe_send(current, {"type": "error", "message": "Every connected player must be READY first."})
                    else:
                        await start_race()

                elif message_type == "state" and race_active:
                    try:
                        x = float(message.get("x", 0.0))
                        y = float(message.get("y", 0.0))
                        rotation = float(message.get("rotation", 0.0))
                        speed = float(message.get("speed", 0.0))
                        lap = int(message.get("lap", 0))
                    except (TypeError, ValueError):
                        continue

                    state = {
                        "type": "state",
                        "player_id": player_id,
                        "x": max(0.0, min(1920.0, x)),
                        "y": max(0.0, min(1280.0, y)),
                        "rotation": rotation % 360.0,
                        "speed": max(-500.0, min(500.0, speed)),
                        "lap": max(0, min(TOTAL_LAPS, lap)),
                        "finished": bool(message.get("finished", False)),
                        "finish_time_ms": message.get("finish_time_ms"),
                    }
                    current["state"] = state
                    await broadcast(state, exclude=player_id)

                elif message_type == "finish" and race_active:
                    try:
                        finish_time_ms = float(message["finish_time_ms"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    await finish_player(player_id, finish_time_ms)

                elif message_type == "reset" and not race_active:
                    await reset_race()

    except (ConnectionResetError, asyncio.IncompleteReadError, OSError):
        pass
    finally:
        clients.pop(player_id, None)
        reseat_players()
        print(f"[SERVER] Player {player_id} disconnected")

        if race_active:
            if not clients:
                await reset_race()
            elif all(p["finished"] for p in clients.values()):
                await send_results()
                await broadcast_room()

        await broadcast_room()

        try:
            writer.close()
            await writer.wait_closed()
        except OSError:
            pass


async def main():
    server = await asyncio.start_server(handle_client, HOST, PORT)
    print("=" * 60)
    print("             NITRO CLASH MULTIPLAYER SERVER")
    print("=" * 60)
    print(f"Listening on {HOST}:{PORT}")
    print(f"Players: {MIN_PLAYERS_TO_START}-{MAX_PLAYERS}")
    print(f"Map: {MAP_NAME} | Laps: {TOTAL_LAPS}")
    print("Lobby: all players READY, then any player presses START.")
    print("Press CTRL+C to stop.")
    print("=" * 60)

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[SERVER] Stopped.")
