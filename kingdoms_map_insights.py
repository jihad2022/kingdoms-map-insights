"""Read-only Travian Kingdoms map snapshot exploration."""
import argparse
import csv
from datetime import date, datetime, timezone
import json
from math import dist, isfinite
import os
from pathlib import Path
import re
import sys
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, build_opener

CROPPERS = {"3339": 9, "11115": 15}
OASES = {"10", "11", "20", "21", "30", "31", "40", "41"}
WORLD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


class NoRedirect(HTTPRedirectHandler):
    """Keep credentials on the selected origin."""

    def redirect_request(self, *args, **kwargs):
        return None


def coordinates(row):
    return int(row["x"]), int(row["y"])


def parse(document):
    if not isinstance(document, dict) or not isinstance(document.get("response"), dict):
        raise ValueError("Missing snapshot response")
    snapshot = document["response"]
    world = snapshot["gameworld"]
    datetime.fromtimestamp(int(world["date"]), timezone.utc)
    int(world["startTime"])
    grid = snapshot["map"]
    if int(grid["radius"]) < 0 or not grid["cells"]:
        raise ValueError("Invalid or empty map")
    points = [coordinates(cell) for cell in grid["cells"]]
    if len(points) != len(set(points)):
        raise ValueError("Duplicate map coordinates")
    if not isinstance(snapshot["players"], list) or not isinstance(snapshot["kingdoms"], list):
        raise ValueError("Invalid player or kingdom records")
    return snapshot


def snapshot_date(snapshot):
    return datetime.fromtimestamp(int(snapshot["gameworld"]["date"]), timezone.utc).date()


def fetch(world, day, cache):
    if not WORLD.fullmatch(world):
        raise ValueError("Use a bare Kingdoms world name, such as com1nx3")
    path = cache / world / (day.isoformat() + ".json") if day else None
    if path is not None and path.exists():
        document = json.loads(path.read_text())
    else:
        key = os.getenv("KINGDOMS_API_KEY")
        if not key:
            raise ValueError("Set KINGDOMS_API_KEY or provide a local snapshot")
        params = {"action": "getMapData", "privateApiKey": key}
        if day:
            params["date"] = day.strftime("%d.%m.%Y")
        url = "https://" + world + ".kingdoms.com/api/external.php?" + urlencode(params)
        try:
            with build_opener(NoRedirect()).open(url, timeout=30) as response:
                document = json.load(response)
        except (URLError, TimeoutError, OSError) as error:
            code = getattr(error, "code", None)
            raise ValueError("Snapshot request failed" + (f" (HTTP {code})" if code else "")) from None
    snapshot = parse(document)
    if snapshot["gameworld"]["name"].lower() != world or (day and snapshot_date(snapshot) != day):
        raise ValueError("Returned world or snapshot date differs from the request")
    if path is not None and not path.exists():
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Retain map data while omitting external authentication tokens.
        for player in snapshot["players"]:
            player.pop("externalLoginToken", None)
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            try:
                json.dump(document, output)
                output.flush()
                temporary.replace(path)
            finally:
                if temporary.exists():
                    temporary.unlink()
    return snapshot


def villages(snapshot):
    return [village for player in snapshot["players"] for village in player["villages"]]


def tiles(snapshot):
    occupied = {coordinates(village) for village in villages(snapshot)}
    for cell in snapshot["map"]["cells"]:
        x, y = coordinates(cell)
        resource = str(cell.get("resType", ""))
        oasis = str(cell.get("oasis", ""))
        yield {
            "x": x, "y": y, "resource": resource, "cropper": CROPPERS.get(resource),
            "oasis": oasis if oasis in OASES else None,
            "listed_village": (x, y) in occupied,
        }


def query(snapshot, mode, crop, center, radius, unoccupied):
    rows = []
    for tile in tiles(snapshot):
        if mode == "croppers" and (tile["cropper"] is None or crop and tile["cropper"] != crop):
            continue
        if mode == "oases" and tile["oasis"] is None:
            continue
        if unoccupied and tile["listed_village"]:
            continue
        if center:
            tile["distance"] = dist(center, (tile["x"], tile["y"]))
            if radius is not None and tile["distance"] > radius:
                continue
        rows.append(tile)
    if center:
        rows.sort(key=lambda tile: (tile["distance"], tile["x"], tile["y"]))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--snapshot", type=Path)
    source.add_argument("--world")
    parser.add_argument("--date", type=date.fromisoformat)
    parser.add_argument("--cache", type=Path, default=Path.home() / ".cache/kingdoms-map-insights")
    parser.add_argument("mode", choices=["croppers", "oases", "tiles", "villages", "statistics"])
    parser.add_argument("--crop", type=int, choices=[9, 15])
    parser.add_argument("--center", type=int, nargs=2, metavar=("X", "Y"))
    parser.add_argument("--radius", type=float)
    parser.add_argument("--unoccupied", action="store_true")
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    args = parser.parse_args()
    if args.date and args.snapshot:
        parser.error("--date requires --world")
    if args.radius is not None and (not args.center or not isfinite(args.radius) or args.radius < 0):
        parser.error("--radius requires --center and a finite nonnegative value")
    if args.crop and args.mode != "croppers":
        parser.error("--crop requires croppers")
    if args.mode in {"statistics", "villages"} and (args.center or args.unoccupied):
        parser.error("Tile filters require croppers, oases, or tiles")
    try:
        snapshot = parse(json.loads(args.snapshot.read_text())) if args.snapshot else fetch(args.world, args.date, args.cache)
        if args.mode == "statistics":
            rows = [{
                "world": snapshot["gameworld"]["name"], "date": snapshot_date(snapshot).isoformat(),
                "radius": int(snapshot["map"]["radius"]), "cells": len(snapshot["map"]["cells"]),
                "players": len(snapshot["players"]), "villages": len(villages(snapshot)),
                "kingdoms": len(snapshot["kingdoms"]),
            }]
        elif args.mode == "villages":
            rows = villages(snapshot)
        else:
            rows = query(snapshot, args.mode, args.crop, args.center, args.radius, args.unoccupied)
    except (ValueError, KeyError, TypeError, OverflowError, OSError) as error:
        message = str(error) if type(error) is ValueError else "Unable to read a valid snapshot"
        parser.exit(1, f"Error: {message}\n")
    if args.format == "csv":
        fields = list(dict.fromkeys(key for row in rows for key in row))
        if fields:
            writer = csv.DictWriter(sys.stdout, fields)
            writer.writeheader()
            writer.writerows(rows)
    else:
        print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
