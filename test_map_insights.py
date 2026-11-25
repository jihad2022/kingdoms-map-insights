import unittest

from kingdoms_map_insights import parse, query, snapshot_date


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.document = {"response": {
            "gameworld": {"name": "example", "startTime": "1699920000", "date": "1700006400"},
            "map": {"radius": "60", "cells": [
                {"x": "0", "y": "0", "resType": "11115"},
                {"x": "3", "y": "4", "resType": "3339"},
                {"x": "1", "y": "1", "resType": "0", "oasis": "41"},
            ]},
            "players": [{"villages": [{"x": "0", "y": "0"}]}],
            "kingdoms": [],
        }}

    def test_croppers_and_distance(self):
        rows = query(parse(self.document), "croppers", None, (0, 0), 5, True)
        self.assertEqual([(row["cropper"], row["distance"]) for row in rows], [(9, 5)])

    def test_oasis_type(self):
        rows = query(parse(self.document), "oases", None, None, None, False)
        self.assertEqual([row["oasis"] for row in rows], ["41"])

    def test_reject_duplicate_coordinates(self):
        cells = self.document["response"]["map"]["cells"]
        cells.append(cells[0])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            parse(self.document)

    def test_date(self):
        self.assertEqual(snapshot_date(parse(self.document)).isoformat(), "2023-11-15")
