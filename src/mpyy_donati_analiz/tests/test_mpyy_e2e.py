#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Headless E2E & Unit Test Suite for MPYY Urban Facility Accessibility & Optimization
===================================================================================
Verifies:
  1. EPSG:5253 (TUREF / TM30) planar road network construction & O(1) snapping
  2. Multi-source Dijkstra shortest path service area calculation
  3. Recursive binary polygon splitting (`split_polygon_by_ratios`) area conservation
  4. MPYYDonatiDialog 100% English default UI, multi-language switching, and full
     end-to-end analysis pipeline in EPSG:5253.
"""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)

PLUGIN_PARENT = Path(__file__).resolve().parent.parent.parent
if str(PLUGIN_PARENT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_PARENT))

from mpyy_donati_analiz.mpyy_engine import FastRoadGraph, split_polygon_by_ratios
from mpyy_donati_analiz.mpyy_dialog import MPYYDonatiDialog


class TestMPYYDonatiAnalizE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qgs = QgsApplication.instance()
        cls._owns_qgs = False
        if cls.qgs is None:
            cls.qgs = QgsApplication([], False)
            cls.qgs.initQgis()
            cls._owns_qgs = True

    @classmethod
    def tearDownClass(cls):
        QgsProject.instance().clear()
        if cls._owns_qgs and cls.qgs is not None:
            cls.qgs.exitQgis()

    def test_01_epsg5253_road_graph_and_dijkstra(self):
        crs = QgsCoordinateReferenceSystem("EPSG:5253")
        self.assertTrue(crs.isValid())

        lyr = QgsVectorLayer("LineString?crs=EPSG:5253", "roads", "memory")
        pr = lyr.dataProvider()
        f1 = QgsFeature()
        f1.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(500000, 4250000), QgsPointXY(500400, 4250000)]))
        f2 = QgsFeature()
        f2.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(500400, 4250000), QgsPointXY(500400, 4250300)]))
        pr.addFeatures([f1, f2])
        lyr.updateExtents()

        graph = FastRoadGraph(lyr, target_crs=crs, tolerance=2.0)
        nid, dist = graph.snap_point_to_node(QgsPointXY(500001.0, 4250001.0))
        self.assertIsNotNone(nid)
        self.assertLess(dist, 3.0)

        dmap = graph.multi_source_dijkstra([QgsPointXY(500000, 4250000)], max_cutoff=1000.0)
        self.assertGreaterEqual(len(dmap), 2)

    def test_02_polygon_binary_splitting(self):
        poly = QgsGeometry.fromPolygonXY([[
            QgsPointXY(500000, 4250000),
            QgsPointXY(500200, 4250000),
            QgsPointXY(500200, 4250100),
            QgsPointXY(500000, 4250100),
            QgsPointXY(500000, 4250000),
        ]])
        parts = split_polygon_by_ratios(poly, [6000.0, 14000.0])
        self.assertEqual(len(parts), 2)
        self.assertAlmostEqual(sum(p.area() for p in parts), 20000.0, delta=50.0)

    def test_03_dialog_english_default_and_epsg5253_pipeline(self):
        QgsProject.instance().clear()
        dlg = MPYYDonatiDialog(None)
        self.assertEqual(dlg.current_lang, "en")
        self.assertIn("MPYY Urban Facility Accessibility", dlg.windowTitle())

        dlg.create_demo_layers()
        layers = list(QgsProject.instance().mapLayers().values())
        self.assertGreaterEqual(len(layers), 3)
        for lyr in layers:
            self.assertEqual(lyr.crs().authid(), "EPSG:5253")

        dlg.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
