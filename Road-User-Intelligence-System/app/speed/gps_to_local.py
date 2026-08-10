"""
Converts GPS (latitude, longitude) ground control points into local
(X, Y) meter coordinates relative to the first point, for use with
app/speed/calibrate.py.

Uses an equirectangular flat-earth approximation — accurate to well
under 1% error for short distances (tens to a few hundred meters),
which is more than sufficient for a single camera's field of view.

Usage:
    python -m app.speed.gps_to_local
    (then paste your lat,lon pairs when prompted)
"""

import math

EARTH_RADIUS_M = 6371000.0


def gps_to_local(points_latlon):
    """
    points_latlon: list of (lat, lon) tuples.
    Returns: list of (x, y) in meters, relative to points_latlon[0].
    """
    lat0, lon0 = points_latlon[0]
    lat0_rad = math.radians(lat0)

    local_points = []
    for lat, lon in points_latlon:
        dlat = math.radians(lat - lat0)
        dlon = math.radians(lon - lon0)

        y = dlat * EARTH_RADIUS_M
        x = dlon * EARTH_RADIUS_M * math.cos(lat0_rad)

        local_points.append((round(x, 2), round(y, 2)))

    return local_points


def main():
    print("Enter GPS points as 'lat,lon' (one per line).")
    print("Type 'done' when finished (need at least 4 points).\n")

    points = []
    while True:
        raw = input(f"Point {len(points) + 1} (or 'done'): ").strip()
        if raw.lower() == "done":
            break
        try:
            lat, lon = [float(v) for v in raw.split(",")]
            points.append((lat, lon))
        except ValueError:
            print("  Invalid format. Example: 5.6037,-0.1870")

    if len(points) < 4:
        print("Need at least 4 points.")
        return

    local = gps_to_local(points)

    print("\nLocal (X, Y) meters, relative to Point 1:")
    for i, (x, y) in enumerate(local):
        print(f"  Point {i + 1}: {x}, {y}   <- use this in calibrate.py")


if __name__ == "__main__":
    main()