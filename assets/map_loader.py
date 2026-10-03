"""Racetrack definition used by Nitro Clash Multiplayer.

The current build intentionally ships one polished, tested track.
"""

from pathlib import Path

MAP_DIR = Path(__file__).resolve().parent / "maps" / "racetrack"


class Racetrack:
    """Single supported Nitro Clash circuit."""

    name = "racetrack"
    _start = (1312, 233)

    def layer(self, layer: int):
        """Return a map layer or checkpoint data.

        0 = background image
        1 = decorative/object image
        2 = drivable-track mask image
        3 = checkpoint rectangles
        """
        if layer == 0:
            return str(MAP_DIR / "bg.png")
        if layer == 1:
            return str(MAP_DIR / "obj.png")
        if layer == 2:
            return str(MAP_DIR / "trk.png")
        if layer == 3:
            return (
                (1312, 233, 32, 183),
                (1428, 513, 215, 27),
                (1376, 665, 32, 183),
                (928, 665, 32, 183),
                (512, 665, 32, 183),
                (276, 513, 215, 27),
                (512, 233, 32, 183),
                (928, 233, 32, 183),
            )
        if layer == 4:
            # Small deterministic track hazards. They sit on the racing surface,
            # leave the apexes open, and are identical for every multiplayer client.
            return (
                (1450, 315, 62, 28, "barrier"),
                (1535, 430, 34, 34, "tire"),
                (1510, 705, 62, 28, "barrier"),
                (1325, 860, 34, 34, "tire"),
                (1040, 900, 62, 28, "barrier"),
                (730, 845, 34, 34, "tire"),
                (340, 700, 62, 28, "barrier"),
                (345, 520, 34, 34, "tire"),
                (555, 320, 62, 28, "barrier"),
                (850, 350, 34, 34, "tire"),
                (1110, 350, 62, 28, "barrier"),
            )
        raise ValueError(f"Racetrack.layer(layer) must be between 0 and 4, got {layer}")

    def start_pos(self, pos: int):
        """Return the starting position and rotation for slots 1-6."""
        if pos not in range(1, 7):
            raise ValueError(f"Racetrack.start_pos(pos) must be between 1 and 6, got {pos}")

        row = 0 if pos % 2 == 1 else 1
        column = (pos - 1) // 2
        return self._start[0] - (77 + column * 115), self._start[1] + 52 + row * 70, 270


index = ("racetrack",)
objs = (Racetrack,)
