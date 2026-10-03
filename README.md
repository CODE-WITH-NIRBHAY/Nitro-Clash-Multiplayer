# Nitro Clash Multiplayer

> A lightweight LAN multiplayer racing game built with Python and
> Pygame.

Nitro Clash Multiplayer is a real-time multiplayer racing game designed
around a simple client-server architecture. Players connect to a host
over a local network, enter a shared lobby, select a vehicle and colour,
ready up, and compete on a racetrack with obstacles, checkpoints, nitro,
race timing, and multiplayer position tracking.

The project is intentionally compact and source-focused, making it
suitable for learning, classroom demonstrations, experimentation, and
further development.

------------------------------------------------------------------------

## Features

-   **LAN multiplayer** with a dedicated TCP server
-   Support for **up to 6 players**
-   Multiplayer lobby with:
    -   Player names
    -   Ready status
    -   Vehicle selection
    -   Colour selection
-   Synchronized race start and race timing
-   Multiple vehicle choices:
    -   Family Car
    -   Sports Car
    -   Luxury Car
    -   Truck
    -   Race Car
-   Multiple vehicle colours:
    -   Red
    -   Yellow
    -   Green
    -   Blue
    -   Black
-   Race checkpoints and lap tracking
-   Race obstacles including barriers and tires
-   Collision slowdown and recovery behaviour
-   Nitro boost with a rechargeable meter
-   Live race HUD displaying:
    -   Lap
    -   Race time
    -   Position
    -   Speed
    -   Nitro
    -   Racer information
-   Results screen and rematch flow
-   Resizable game window
-   Fullscreen toggle
-   Configuration through `settings.json`
-   Clean asset set containing only resources required by the current
    game

------------------------------------------------------------------------

## Technology Stack

  Component        Technology
  ---------------- ---------------------------
  Language         Python 3
  Game framework   Pygame 2.6.1
  Networking       Python TCP sockets
  Data format      JSON messages
  Concurrency      Threaded network receiver
  Rendering        Pygame
  Configuration    JSON

------------------------------------------------------------------------

## Project Architecture

Nitro Clash Multiplayer uses a client-server architecture.

``` text
                 Local Area Network
                        │
              ┌─────────┴─────────┐
              │                   │
        ┌─────▼─────┐       ┌─────▼─────┐
        │  Server   │       │  Server   │
        │ server.py │       │   Host    │
        └─────┬─────┘       └───────────┘
              │
       ┌──────┼───────────────┐
       │      │               │
   ┌───▼───┐ ┌▼──────┐ ┌─────▼───┐
   │Client │ │Client │ │ Client  │
   │  #1   │ │  #2   │ │   #N    │
   └───────┘ └────────┘ └─────────┘
```

### Main components

``` text
Nitro-Clash-Multiplayer/
│
├── main.py
├── settings.json
├── requirements.txt
├── .gitignore
│
├── assets/
│   ├── __init__.py
│   ├── image_loader.py
│   ├── map_loader.py
│   ├── images/
│   │   └── cars/
│   └── maps/
│       └── racetrack/
│
├── client/
│   ├── __init__.py
│   └── network.py
│
└── server/
    ├── __init__.py
    └── server.py
```

### Runtime responsibilities

-   `main.py` --- game loop, rendering, input, car movement, HUD, race
    state, and client-side gameplay.
-   `client/network.py` --- client networking and communication with the
    server.
-   `server/server.py` --- multiplayer session management, player state,
    race phases, and result synchronization.
-   `assets/image_loader.py` --- centralized car asset lookup.
-   `assets/map_loader.py` --- racetrack layers, checkpoints, starting
    positions, and obstacle definitions.
-   `settings.json` --- local game configuration.
-   `requirements.txt` --- Python dependency specification.

------------------------------------------------------------------------

## Requirements

### Software

-   Python **3.10 or newer**
-   Pygame **2.6.1**
-   Windows, Linux, or another platform supported by the installed
    Python/Pygame environment
-   For multiplayer: devices connected to the same local network

### Recommended

Python 3.10/3.11 is recommended for a predictable development
environment.

------------------------------------------------------------------------

## Installation

Clone the repository:

``` bash
git clone https://github.com/<your-username>/Nitro-Clash-Multiplayer.git
cd Nitro-Clash-Multiplayer
```

Create a virtual environment:

### Windows

``` powershell
python -m venv .venv
```

Activate it:

``` powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

``` powershell
python -m pip install -r requirements.txt
```

### Linux / macOS

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

``` bash
python3 -m pip install -r requirements.txt
```

------------------------------------------------------------------------

## Running the Game

Nitro Clash Multiplayer requires the server to be running before clients
connect.

### 1. Start the server

From the project root:

``` bash
python server/server.py
```

The default server port is:

``` text
5000
```

Keep the server terminal open while the race is running.

### 2. Start a client

Open another terminal:

``` bash
python main.py
```

Enter the server IP address and player name, then press **Enter** to
connect.

------------------------------------------------------------------------

## LAN Multiplayer Setup

For a LAN race:

1.  Connect all computers to the same local network.
2.  Start `server/server.py` on one computer.
3.  Find the host computer's local IPv4 address.
4.  Start `main.py` on each client computer.
5.  Enter the host computer's IPv4 address in the **Server IP** field.
6.  Keep port `5000` unless the project configuration is changed.
7.  Players join the lobby.
8.  Each player selects their vehicle/colour and presses **Space** to
    ready up.
9.  Once the required players are ready, the race begins.

### Example

If the host computer has:

``` text
192.168.1.20
```

clients should connect using:

``` text
Server IP: 192.168.1.20
Port: 5000
```

The host firewall may need to allow Python or TCP traffic on port
`5000`.

------------------------------------------------------------------------

## Controls

### Connection Screen

  Key / Input   Action
  ------------- -----------------------
  Mouse         Select input field
  Tab           Switch between fields
  Enter         Connect
  Backspace     Delete text
  Escape        Quit

### Lobby

  Key      Action
  -------- --------------------------------
  Space    Ready / Not Ready
  Tab      Rename player
  `1`      Family Car
  `2`      Sports Car
  `3`      Luxury Car
  `4`      Truck
  `5`      Race Car
  `R`      Red
  `G`      Green
  `B`      Blue
  `Y`      Yellow
  `K`      Black
  Enter    Start/connect where applicable
  Escape   Disconnect

### Race

  Key                   Action
  --------------------- -------------
  `W` / `Arrow Up`      Accelerate
  `S` / `Arrow Down`    Reverse
  `A` / `Arrow Left`    Steer left
  `D` / `Arrow Right`   Steer right
  `Shift`               Nitro
  `Escape`              Disconnect

### Results

  Key        Action
  ---------- -----------------
  `R`        Rematch
  `Escape`   Quit/disconnect

### Display

  Key     Action
  ------- -------------------
  `F11`   Toggle fullscreen

------------------------------------------------------------------------

## Game Flow

The multiplayer session follows a controlled state flow:

``` text
Connect
   │
   ▼
Lobby
   │
   ▼
Ready
   │
   ▼
Countdown
   │
   ▼
Race
   │
   ▼
Results
   │
   └──────────────► Rematch
                         │
                         ▼
                       Lobby
```

The server coordinates the shared multiplayer state so that connected
clients remain in the same race phase.

------------------------------------------------------------------------

## Vehicle System

Players can choose from five vehicle types:

  Vehicle      General Characteristics
  ------------ -------------------------------------------------
  Family Car   Balanced and forgiving
  Sports Car   Faster with responsive handling
  Luxury Car   Balanced performance
  Truck        Lower speed with heavier handling
  Race Car     Highest performance and more demanding handling

Vehicle performance is defined in the client gameplay configuration and
can be adjusted for future balancing.

------------------------------------------------------------------------

## Nitro System

Nitro provides a temporary speed increase while accelerating.

The current implementation includes:

-   Nitro activation using **Shift**
-   Increased maximum speed while boosting
-   Nitro energy consumption while active
-   Automatic recharge when Nitro is not being consumed
-   HUD feedback through the Nitro meter

This system is intentionally simple so that it can be expanded later
with pickups, cooldowns, effects, or additional boost mechanics.

------------------------------------------------------------------------

## Track and Obstacles

The current game uses the `racetrack` map.

The track system contains:

-   Background/map layers
-   Track collision mask
-   Checkpoints
-   Starting positions
-   Race obstacles

Obstacles include barriers and tire objects positioned around the racing
surface. Collision reduces vehicle speed rather than immediately
resetting the player, allowing the race to continue smoothly.

Off-track movement also applies a speed penalty.

------------------------------------------------------------------------

## Multiplayer Networking

The game uses a lightweight TCP client-server model.

### Client

The client is responsible for:

-   Connecting to the server
-   Sending player/profile information
-   Sending local race state
-   Sending finish information
-   Receiving shared player state
-   Rendering remote racers
-   Displaying synchronized race information

### Server

The server is responsible for:

-   Accepting client connections
-   Assigning player slots
-   Maintaining player information
-   Managing lobby readiness
-   Coordinating race phases
-   Tracking race timing
-   Receiving player state
-   Broadcasting multiplayer state
-   Collecting finish results
-   Handling rematch/reset flow

Communication uses newline-delimited JSON messages over TCP.

------------------------------------------------------------------------

## Configuration

The main configuration file is:

``` text
settings.json
```

Default configuration:

``` json
{
  "Resolution": [960, 540],
  "Server": "127.0.0.1",
  "Port": 5000,
  "Name": "Player",
  "Vehicle": "Sports Car",
  "Colour": "red",
  "Laps": 3
}
```

### Configuration options

  Setting        Purpose
  -------------- --------------------------------
  `Resolution`   Initial game window resolution
  `Server`       Default server IP/host
  `Port`         TCP server port
  `Name`         Default player name
  `Vehicle`      Default vehicle
  `Colour`       Default vehicle colour
  `Laps`         Number of race laps

The client also allows the server IP and player name to be changed from
the connection screen.

------------------------------------------------------------------------

## Troubleshooting

### `ModuleNotFoundError: No module named 'pygame'`

Install the project dependencies:

``` bash
python -m pip install -r requirements.txt
```

Or install Pygame directly:

``` bash
python -m pip install pygame==2.6.1
```

### Client cannot connect

Check:

-   The server is running.
-   The client is using the correct host IP.
-   Port `5000` is available.
-   Both devices are on the same LAN.
-   The firewall is allowing Python/TCP traffic.
-   The server is listening on the expected network interface.

### `Connection refused`

Usually means the server is not running or the client is using the wrong
IP/port.

Start:

``` bash
python server/server.py
```

Then verify the client connection settings.

### Multiplayer works on the host but not on another computer

Check the host computer's local IPv4 address and use that address
instead of:

``` text
127.0.0.1
```

`127.0.0.1` refers to the local computer itself and should not be used
by another computer to reach the host.

------------------------------------------------------------------------

## Development

The project is structured so that gameplay, networking, map data, and
asset loading remain separated.

For gameplay changes, start with:

``` text
main.py
```

For networking changes:

``` text
client/network.py
server/server.py
```

For track/checkpoint/obstacle changes:

``` text
assets/map_loader.py
```

For car asset lookup:

``` text
assets/image_loader.py
```

For default configuration:

``` text
settings.json
```

------------------------------------------------------------------------

## Project Status

**Current status: Functional multiplayer prototype / academic project**

The current version provides a complete playable multiplayer loop:

-   Connection
-   Lobby
-   Player customization
-   Ready system
-   Countdown
-   Multiplayer race
-   Lap/checkpoint tracking
-   Obstacles
-   Nitro
-   HUD
-   Finish results
-   Rematch

The codebase is intentionally kept lightweight and can serve as a
foundation for additional gameplay and networking features.

------------------------------------------------------------------------

## Possible Future Improvements

Potential future development areas include:

-   More racetracks
-   Advanced vehicle physics
-   Drifting mechanics
-   Vehicle-specific handling
-   More obstacle types
-   Power-ups
-   Sound effects and music
-   Improved race-position interpolation
-   More detailed race statistics
-   Dedicated matchmaking
-   Internet/WAN multiplayer
-   Persistent player profiles
-   AI opponents
-   Improved visual effects
-   More customizable vehicles
-   Replay or spectator mode

These are not required for the current playable version.

------------------------------------------------------------------------

## Repository Structure

``` text
Nitro-Clash-Multiplayer/
├── assets/
│   ├── __init__.py
│   ├── image_loader.py
│   ├── map_loader.py
│   ├── images/
│   │   └── cars/
│   └── maps/
│       └── racetrack/
│           ├── bg.png
│           ├── obj.png
│           └── trk.png
│
├── client/
│   ├── __init__.py
│   └── network.py
│
├── server/
│   ├── __init__.py
│   └── server.py
│
├── main.py
├── settings.json
├── requirements.txt
└── .gitignore
```

------------------------------------------------------------------------

## License

This repository is distributed under the terms specified in
[`LICENSE`](LICENSE).

If the repository contains third-party assets or modified assets, their
original licensing and attribution requirements should be reviewed and
preserved separately from the project's source-code license.

------------------------------------------------------------------------

## Acknowledgements

Nitro Clash Multiplayer was developed as a Python/Pygame multiplayer
racing project with a focus on LAN networking, real-time game state
synchronization, and modular game development.

Third-party libraries and assets remain subject to their respective
licenses and terms.

------------------------------------------------------------------------

## Author

**Nitro Clash Multiplayer**

Developed as a multiplayer game development project using Python,
Pygame, TCP networking, and JSON-based communication.
