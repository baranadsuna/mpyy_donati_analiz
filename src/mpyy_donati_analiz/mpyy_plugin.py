# -*- coding: utf-8 -*-
import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from .mpyy_dialog import MPYYDonatiDialog


class MPYYDonatiPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        self.dialog = None
        self.icon = QIcon()

    def initGui(self):
        svg_path = os.path.join(self.plugin_dir, "icon.svg")
        png_path = os.path.join(self.plugin_dir, "icon.png")
        icon_path = svg_path if os.path.exists(svg_path) else png_path
        self.icon = QIcon(icon_path)
        parent_win = self.iface.mainWindow() if self.iface else None
        self.action = QAction(
            self.icon,
            "MPYY Urban Facility Accessibility & Optimization",
            parent_win,
        )
        self.action.setToolTip(
            "MPYY Urban Facility Accessibility & Optimization (EPSG:5253) — by Baran Adsuna"
        )
        self.action.triggered.connect(self.run)
        if self.iface:
            self.iface.addToolBarIcon(self.action)
            self.iface.addPluginToVectorMenu(
                "&MPYY Urban Facility Accessibility", self.action
            )

    def unload(self):
        if self.action and self.iface:
            self.iface.removePluginVectorMenu(
                "&MPYY Urban Facility Accessibility", self.action
            )
            self.iface.removeToolBarIcon(self.action)

    def run(self):
        if self.dialog is None:
            self.dialog = MPYYDonatiDialog(self.iface)
            self.dialog.setWindowIcon(self.icon)
        self.dialog.populate_layers()
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
