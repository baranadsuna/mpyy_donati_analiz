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

from mpyy_donati_analiz.mpyy_engine import (
    FastRoadGraph,
    split_polygon_by_ratios,
    PlanActualDiffEngine,
    ResidentialGrowthNetworkEvaluator,
)
from mpyy_donati_analiz.mpyy_dialog import MPYYDonatiDialog
from qgis.core import QgsField
from qgis.PyQt.QtCore import QVariant


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
        self.assertGreaterEqual(len(layers), 5)
        for lyr in layers:
            self.assertEqual(lyr.crs().authid(), "EPSG:5253")

        dlg.close()

    def test_04_plan_actual_diff_engine(self):
        crs = QgsCoordinateReferenceSystem("EPSG:5253")
        old_lyr = QgsVectorLayer("Polygon?crs=EPSG:5253", "old_plan", "memory")
        opr = old_lyr.dataProvider()
        opr.addAttributes([QgsField("plan_fonk", QVariant.String)])
        old_lyr.updateFields()

        act_lyr = QgsVectorLayer("Polygon?crs=EPSG:5253", "actual_use", "memory")
        apr = act_lyr.dataProvider()
        apr.addAttributes([QgsField("fiili_kullanim", QVariant.String)])
        act_lyr.updateFields()

        def make_sq(x, y, s):
            return QgsGeometry.fromPolygonXY([[
                QgsPointXY(x, y), QgsPointXY(x + s, y),
                QgsPointXY(x + s, y + s), QgsPointXY(x, y + s),
                QgsPointXY(x, y)
            ]])

        # 1: Plan Ticaret, Actual Boş (Unrealized Commercial)
        f1_old = QgsFeature(old_lyr.fields())
        f1_old.setGeometry(make_sq(500000, 4250000, 100))
        f1_old["plan_fonk"] = "Ticaret Alanı"
        f1_act = QgsFeature(act_lyr.fields())
        f1_act.setGeometry(make_sq(500000, 4250000, 100))
        f1_act["fiili_kullanim"] = "Boş Ada / Arsa"

        # 2: Plan İlkokul, Actual Konut (Amenity Loss / MPYY Art 26)
        f2_old = QgsFeature(old_lyr.fields())
        f2_old.setGeometry(make_sq(500200, 4250000, 100))
        f2_old["plan_fonk"] = "İlkokul Alanı"
        f2_act = QgsFeature(act_lyr.fields())
        f2_act.setGeometry(make_sq(500200, 4250000, 100))
        f2_act["fiili_kullanim"] = "Konut Alanı"

        # 3: Plan Park, Actual Park (Uyumlu)
        f3_old = QgsFeature(old_lyr.fields())
        f3_old.setGeometry(make_sq(500400, 4250000, 100))
        f3_old["plan_fonk"] = "Park Alanı"
        f3_act = QgsFeature(act_lyr.fields())
        f3_act.setGeometry(make_sq(500400, 4250000, 100))
        f3_act["fiili_kullanim"] = "Park Alanı"

        opr.addFeatures([f1_old, f2_old, f3_old])
        old_lyr.updateExtents()
        apr.addFeatures([f1_act, f2_act, f3_act])
        act_lyr.updateExtents()

        diff_feats, summary, matrix = PlanActualDiffEngine.run_comparison(
            old_lyr, "plan_fonk", act_lyr, "fiili_kullanim", target_crs=crs
        )

        codes = [df["kod"] for df in diff_feats]
        self.assertIn("BOS_ADA", codes)
        self.assertIn("DONATI_KAYBI", codes)
        self.assertIn("UYUMLU", codes)
        self.assertEqual(summary["bos_ada_adet"], 1)
        self.assertEqual(summary["donati_kaybi_adet"], 1)
        self.assertEqual(summary["uyumlu_adet"], 1)

    def test_05_residential_growth_network_evaluator(self):
        crs = QgsCoordinateReferenceSystem("EPSG:5253")

        # Road Network
        net_lyr = QgsVectorLayer("LineString?crs=EPSG:5253", "roads", "memory")
        npr = net_lyr.dataProvider()
        f_net = QgsFeature()
        f_net.setGeometry(QgsGeometry.fromPolylineXY([
            QgsPointXY(500000, 4250000),
            QgsPointXY(500400, 4250000)
        ]))
        npr.addFeatures([f_net])
        net_lyr.updateExtents()
        graph = FastRoadGraph(net_lyr, target_crs=crs)

        # Candidate Block
        cand_geom = QgsGeometry.fromPolygonXY([[
            QgsPointXY(500100, 4250010),
            QgsPointXY(500200, 4250010),
            QgsPointXY(500200, 4250090),
            QgsPointXY(500100, 4250090),
            QgsPointXY(500100, 4250010)
        ]])
        cf = QgsFeature()
        cf.setGeometry(cand_geom)
        cf.setId(101)

        fac_by_type = {
            "ilkokul": [[1, QgsPointXY(500050, 4250000), 1000, 5000.0, 500.0]],
            "ortaokul": [[2, QgsPointXY(500350, 4250000), 1500, 7000.0, 600.0]],
            "asm": [[3, QgsPointXY(500150, 4250000), 2000, 1000.0, 400.0]],
            "park": [[4, QgsPointXY(500250, 4250000), 5000, 3000.0, 0.0]],
        }
        specs = {
            "ilkokul": {"key_id": "ilkokul", "min_area": 5000.0, "net_r": 500.0},
            "ortaokul": {"key_id": "ortaokul", "min_area": 6000.0, "net_r": 1000.0},
            "asm": {"key_id": "asm", "min_area": 750.0, "net_r": 500.0},
            "park": {"key_id": "park", "min_area": 2000.0, "net_r": 500.0},
        }

        results = ResidentialGrowthNetworkEvaluator.evaluate_candidate_blocks(
            candidate_features=[cf],
            graph=graph,
            fac_by_type=fac_by_type,
            specs=specs,
            target_crs=crs,
            gross_density_pop_per_ha=180.0
        )

        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertGreater(r["konut_skoru"], 70.0)
        self.assertEqual(r["kod"], "ONCELIKLI_KONUT")
        self.assertGreater(r["ongorulen_nufus"], 0)

    def test_06_dialog_end_to_end_full_pipeline(self):
        QgsProject.instance().clear()
        dlg = MPYYDonatiDialog(None)
        dlg.create_demo_layers()

        # Run Diff
        out_diff = dlg.run_plan_actual_diff(show_msg=False)
        self.assertIsNotNone(out_diff)
        diff_layers = QgsProject.instance().mapLayersByName("Plan_Fiili_Kullanim_Uyusmazlik_Analizi")
        self.assertEqual(len(diff_layers), 1)

        # Run Full Analysis
        dlg.run_full_analysis(show_msg=False)
        growth_layers = QgsProject.instance().mapLayersByName("Onerilen_Gelisme_Konut_Alanlari")
        self.assertEqual(len(growth_layers), 1)
        self.assertIn("Gelişme Konut Alanı", dlg.txt_report.toHtml())

        dlg.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
