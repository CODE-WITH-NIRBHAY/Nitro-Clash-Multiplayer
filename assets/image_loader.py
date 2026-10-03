"""Asset path helpers for Nitro Clash Multiplayer.

Only assets used by the current multiplayer build are exposed here.
"""

from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent
IMAGE_DIR = ASSETS_DIR / "images"
CAR_DIR = IMAGE_DIR / "cars"


_VEHICLE_IDS = {
    "Family Car": 1,
    "Sports Car": 2,
    "Luxury Car": 3,
    "Truck": 4,
    "Race Car": 5,
}

_COLOUR_NAMES = {
    (232, 106, 23): "red",
    (255, 0, 0): "red",
    (255, 204, 0): "yellow",
    (255, 255, 0): "yellow",
    (57, 194, 114): "green",
    (0, 255, 0): "green",
    (47, 149, 208): "blue",
    (0, 0, 255): "blue",
    (93, 91, 91): "black",
    (0, 0, 0): "black",
}


def car(colour: str | tuple[int, int, int], vehicle: str | int) -> str:
    """Return the path to a playable car sprite."""
    if isinstance(colour, tuple):
        try:
            colour = _COLOUR_NAMES[colour]
        except KeyError as exc:
            raise ValueError(f"Unknown car colour: {colour}") from exc

    if isinstance(vehicle, str):
        try:
            vehicle = _VEHICLE_IDS[vehicle]
        except KeyError as exc:
            raise ValueError(f"Unknown vehicle: {vehicle}") from exc

    if colour not in {"red", "yellow", "green", "blue", "black"}:
        raise ValueError(f"Unknown car colour: {colour}")
    if vehicle not in range(1, 6):
        raise ValueError(f"Unknown vehicle id: {vehicle}")

    return str(CAR_DIR / f"car_{colour}_{vehicle}.png")
