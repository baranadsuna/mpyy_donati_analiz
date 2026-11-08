# -*- coding: utf-8 -*-
"""
MPYY Urban Facility Accessibility, Capacity-Overflow Relief & Multi-Use Subdivision Dialog
Author / Developer: Baran Adsuna (https://github.com/baranadsuna)
CRS Standard: EPSG:5253 (TUREF / TM30)
"""
import os
import math
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QSpinBox, QPushButton, QTableWidget, QTableWidgetItem,
    QTextBrowser, QTabWidget, QWidget, QGroupBox, QHeaderView, QMessageBox,
    QProgressBar, QCheckBox, QApplication, QFrame
)
from qgis.PyQt.QtCore import Qt, QVariant, QSize, QPointF, QRectF
from qgis.PyQt.QtGui import QColor, QIcon, QPixmap, QFont, QPainter, QPolygonF, QPen, QBrush
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY,
    QgsField, QgsFields, QgsWkbTypes, QgsCategorizedSymbolRenderer,
    QgsRendererCategory, QgsFillSymbol, QgsCoordinateTransform
)
from .mpyy_engine import (
    FastRoadGraph,
    split_polygon_by_ratios,
    compute_polygon_shape_metrics,
    subdivide_block_multi_use,
)

_QVAR_INT = getattr(QVariant, "Int", 2)
_QVAR_DOUBLE = getattr(QVariant, "Double", 6)
_QVAR_STRING = getattr(QVariant, "String", 10)

PLUGIN_AUTHOR = "Baran Adsuna"

DEFAULT_MPYY_FACILITIES = [
    ("ilkokul", "İlkokul (EK-2: 5000-8000 m²)", "Primary School (5000-8000 m²)", "小学 (5000-8000 m²)", "Escuela Primaria (5000-8000 m²)", 500.0, 500.0, 2.0, 5000.0, 8000.0, 2500, "#38bdf8", ["ilkokul", "ilk_okul", "primary"]),
    ("ortaokul", "Ortaokul (EK-2: 6000-10000 m²)", "Middle School (6000-10000 m²)", "初中 (6000-10000 m²)", "Escuela Secundaria (6000-10000 m²)", 1000.0, 1000.0, 2.0, 6000.0, 10000.0, 3500, "#1d4ed8", ["ortaokul", "orta_okul", "middle"]),
    ("lise", "Gündüzlü Lise (EK-2: 6000-10000 m²)", "Day High School (6000-10000 m²)", "日制高中 (6000-10000 m²)", "Preparatoria Diurna (6000-10000 m²)", 2500.0, 2500.0, 2.0, 6000.0, 10000.0, 5000, "#8b5cf6", ["lise", "high"]),
    ("asm", "Aile Sağlığı Merkezi (EK-2: 750-2000 m²)", "Family Health Center (750-2000 m²)", "社区卫生服务中心 (750-2000 m²)", "Centro de Salud Familiar (750-2000 m²)", 500.0, 500.0, 0.75, 750.0, 2000.0, 5000, "#ff8a8a", ["asm", "aile_sagligi", "saglik_ocagi"]),
    ("hastane", "Devlet Hastanesi (EK-2: 1.5 m²/kişi)", "State Hospital (1.5 m²/cap)", "国立医院 (1.5 m²/人)", "Hospital Estatal (1.5 m²/pers)", 2500.0, 2500.0, 1.50, 5000.0, 15000.0, 15000, "#5c0000", ["hastane", "saglik", "hospital"]),
    ("ibadet", "Orta İbadet Yeri (EK-2: 2500 m²)", "Place of Worship (2500 m²)", "宗教场所 (2500 m²)", "Lugar de Culto (2500 m²)", 400.0, 400.0, 0.50, 2500.0, 5000.0, 3500, "#f59e0b", ["ibadet", "cami", "mescit", "dini"]),
    ("park", "Çocuk Bahçesi & Park (EK-2: 10 m³/kişi)", "Park & Playground (10 m³/cap)", "公园与儿童乐园 (10 m³/人)", "Parque y Juegos (10 m³/pers)", 500.0, 500.0, 10.0, 1000.0, 25000.0, 3000, "#10b981", ["park", "yesil", "cocuk"]),
    ("konut", "Gelişme Konut Alanı (Rezerv Yapı)", "Residential Development Area", "居住发展用地 (储备)", "Área de Desarrollo Residencial", 1000.0, 1000.0, 0.0, 1000.0, 30000.0, 4000, "#fde047", ["konut", "gelisme", "residential"]),
    ("sosyal", "Sosyal ve Kültürel Tesis (EK-2)", "Social & Cultural Facility", "社会与文化设施", "Instalación Social y Cultural", 1000.0, 1000.0, 1.25, 1500.0, 6000.0, 4000, "#0d9488", ["sosyal", "kulturel", "kultur"]),
]

TRANSLATIONS = {
    "tr": {
        "win_title": f"MPYY Donatı Erişilebilirlik, Kapasite & İfraz Sistemi — Yazar: {PLUGIN_AUTHOR}",
        "banner_title": "MEKÂNSAL PLANLAR YAPIM YÖNETMELİĞİ (MPYY) EK-2 STANDARTLARI & AKILLI OPTİMİZASYON",
        "banner_sub": f"Kapasite Aşımı Rahatlatma • Çoklu Donatı + Park Tamponu • Pasif Yeşil & Ticari Alan Önerisi • Yazar: {PLUGIN_AUTHOR}",
        "dev_label": "⚡ Yazar / Geliştirici",
        "tab1": "1. Poligon Katmanları ve EK-2 Standart Tablosu",
        "tab2": "2. Detaylı Plan Açıklama ve Erişilebilirlik Raporu",
        "grp1": "1. Temel Harita Katmanları (Poligonlar ve Kapasiteler Otomatik Hesaplanır)",
        "lbl_net": "<b>Prepared Network (Yol Ağı - Çizgi):</b>",
        "lbl_res": "<b>Mevcut Konut Adaları (Poligon):</b>",
        "lbl_vac": "<b>Boş Alanlar / İmar Adaları (Poligon - Bölünecek):</b>",
        "lbl_comm": "<b>Mevcut Ticari Alanlar (Poligon - MPYY Dışı Erişim Demo):</b>",
        "chk_centroids": "Poligonlardan otomatik üretilen ağırlık merkezi noktalarını haritada göster",
        "grp2": "2. Planlama Alanı Nüfusu, Kapasite Rahatlatma ve Akıllı İfraz Ayarı",
        "lbl_pop": "<b>Toplam Planlama Alanı Nüfusu (Kişi):</b>",
        "lbl_pop_note": "*(Konut adalarının alanları (m²) oranında nüfus dağıtılır ve mevcut okul/donatı kapasite aşımı denetlenir)*",
        "lbl_split": "<b>Çoklu Donatı + Park Tamponu & MPYY Dışı Katmanlar:</b>",
        "chk_split": "Büyük adalarda İlkokul + Park Tamponu + ASM kurgula; MPYY dışı grupta Pasif Yeşil Alanlar ve Ticari Alan (Demo) öner",
        "grp3": "3. EK-2 Sosyal ve Teknik Altyapı Alanları Standartları Tablosu (Tamamen Düzenlenebilir)",
        "col_name": "Altyapı Alanı / Donatı\n(EK-2 Standart & Renk)",
        "col_layer": "Mevcut Poligon Katmanı\n(Haritadan Seç)",
        "col_euclid": "MPYY Kuş Uçuşu\nYarıçap (m)",
        "col_net": "Yol Üzerinden\nErişim (m)",
        "col_std": "EK-2 Kişi Başı Standart\n(m²/kişi veya m³/kişi)",
        "col_min": "EK-2 Asgari Birim Alan\n(Min m²)",
        "col_max": "Bölme Eşiği\n(Max Tekil m²)",
        "col_cap": "1 Bina Kapasitesi\n(Kişi Sayısı)",
        "btn_add": "➕ Yeni Donatı Satırı Ekle",
        "btn_del": "🗑️ Seçili Satırı Sil",
        "btn_reset": "🔄 EK-2 Tablo Normlarına Sıfırla",
        "btn_demo": "🚀 Örnek Poligon Test Verisi Oluştur",
        "btn_run": "⚡ AKILLI EK-2 ANALİZİNİ BAŞLAT VE HARİTAYA İŞLE",
        "none_layer": "-- Yok / Alanda Mevcut Değil --",
        "auto_comm_layer": "-- Otomatik Algıla (mevcut_Ticari) / Demo Modu --",
        "new_fac": "Yeni Donatı",
        "empty_report": f"<h3>Henüz analiz çalıştırılmadı.</h3><p><b>Yazar:</b> {PLUGIN_AUTHOR} — Lütfen katmanlarınızı seçip <b>ANALİZİ BAŞLAT</b> butonuna tıklayın.</p>",
        "warn_missing_title": "Eksik Katman",
        "warn_missing_msg": "Lütfen Prepared Network (Yol Ağı), Mevcut Konut Adaları (Poligon) ve Boş Alan (Poligon) katmanlarını seçiniz!",
        "done_title": "Akıllı Analiz ve Optimizasyon Tamamlandı",
        "done_msg": (
            f"Yazar: {PLUGIN_AUTHOR}\n\n"
            "1) 'MPYY_EK2_Sosyal_ve_Teknik_Donati_Alanlari' grubu altında bölünen/önerilen MPYY donatı alanları,\n"
            "2) 'MPYY_Disi_Tamamlayici_Alanlar' grubu altında 'Onerilen_Pasif_Yesil_Alanlar' (tampon yeşil) ve "
            "'Onerilen_Ticari_Alanlar' (erişim demo) katmanları haritaya eklendi!"
        ),
    },
    "en": {
        "win_title": f"MPYY Urban Facility Accessibility, Capacity & Subdivision — Author: {PLUGIN_AUTHOR}",
        "banner_title": "SPATIAL PLANS CONSTRUCTION REGULATION (MPYY) ANNEX-2 STANDARDS & SMART SUPPORT",
        "banner_sub": f"Capacity Overflow Relief • Multi-Facility + Park Buffer • Passive Green & Commercial Demo • Author: {PLUGIN_AUTHOR}",
        "dev_label": "⚡ Author / Developer",
        "tab1": "1. Polygon Layers & Annex-2 Standard Table",
        "tab2": "2. Detailed Planning & Accessibility Report",
        "grp1": "1. Base Map Layers (Polygons & Area-Based Capacities Are Evaluated Automatically)",
        "lbl_net": "<b>Prepared Network (Road Graph - Line):</b>",
        "lbl_res": "<b>Existing Residential Blocks (Polygon):</b>",
        "lbl_vac": "<b>Vacant Parcels / Urban Blocks (Polygon - To Split):</b>",
        "lbl_comm": "<b>Existing Commercial Areas (Polygon - Non-MPYY Demo):</b>",
        "chk_centroids": "Display automatically generated centroid points on map",
        "grp2": "2. Planning Area Population, Capacity Overflow Relief & Smart Subdivision",
        "lbl_pop": "<b>Total Planning Area Population (Persons):</b>",
        "lbl_pop_note": "*(Population weighted by residential block m²; checks overload on small existing schools/facilities)*",
        "lbl_split": "<b>Multi-Facility + Park Buffer & Non-MPYY Layers:</b>",
        "chk_split": "Allow 2 built facilities separated by a Park buffer on large blocks; generate Non-MPYY Passive Green & Commercial Demo layers",
        "grp3": "3. Annex-2 Social & Technical Infrastructure Standards Table (Fully Editable)",
        "col_name": "Infrastructure / Facility\n(Annex-2 Std & Color)",
        "col_layer": "Existing Polygon Layer\n(Select from Map)",
        "col_euclid": "Euclidean\nRadius (m)",
        "col_net": "Road Network\nDistance (m)",
        "col_std": "Annex-2 Per Capita\n(m²/cap or m³/cap)",
        "col_min": "Annex-2 Min Unit Area\n(Min m²)",
        "col_max": "Split Threshold\n(Max Single m²)",
        "col_cap": "1 Building Cap\n(Persons)",
        "btn_add": "➕ Add Facility Row",
        "btn_del": "🗑️ Remove Selected Row",
        "btn_reset": "🔄 Reset to Annex-2 Norms",
        "btn_demo": "🚀 Generate Sample Polygon Data",
        "btn_run": "⚡ RUN SMART ANNEX-2 ANALYSIS & RENDER ON MAP",
        "none_layer": "-- None / Not Present in Area --",
        "auto_comm_layer": "-- Auto-Detect (mevcut_Ticari) / Demo Mode --",
        "new_fac": "New Facility",
        "empty_report": f"<h3>Analysis has not been run yet.</h3><p><b>Author:</b> {PLUGIN_AUTHOR} — Please select your layers and click <b>RUN ANALYSIS</b>.</p>",
        "warn_missing_title": "Missing Layer",
        "warn_missing_msg": "Please select Prepared Network (Line), Existing Residential Blocks (Polygon), and Vacant Parcels (Polygon)!",
        "done_title": "Smart Analysis & Optimization Complete",
        "done_msg": (
            f"Author: {PLUGIN_AUTHOR}\n\n"
            "1) MPYY Annex-2 allocated & subdivided polygons added under 'MPYY_EK2_Sosyal_ve_Teknik_Donati_Alanlari',\n"
            "2) Non-MPYY 'Onerilen_Pasif_Yesil_Alanlar' (Passive Buffer Green) and 'Onerilen_Ticari_Alanlar' (Commercial Access Demo) "
            "added under 'MPYY_Disi_Tamamlayici_Alanlar'!"
        ),
    },
    "zh": {
        "win_title": f"MPYY 城市公共设施可达性与空间优化系统 — 作者: {PLUGIN_AUTHOR}",
        "banner_title": "空间规划建设管理条例 (MPYY) 附表2标准与智能决策支持系统",
        "banner_sub": f"容量超载缓解 • 双设施+公园缓冲 • 被动绿地与商业用地建议 • 作者: {PLUGIN_AUTHOR}",
        "dev_label": "⚡ 开发者 / 作者",
        "tab1": "1. 多边形图层与附表2标准参数表",
        "tab2": "2. 详细规划说明与可达性报告",
        "grp1": "1. 基础地图图层（多边形在后台自动转换为质心点）",
        "lbl_net": "<b>路网图层 Prepared Network（线）：</b>",
        "lbl_res": "<b>现有居住街坊（多边形）：</b>",
        "lbl_vac": "<b>空置地块 / 待规划街坊（多边形 - 自动分割）：</b>",
        "lbl_comm": "<b>现有商业用地（多边形 - 非MPYY可达性演示）：</b>",
        "chk_centroids": "在地图上显示自动生成的质心点图层",
        "grp2": "2. 规划区总人口与智能设施充足性规则",
        "lbl_pop": "<b>规划区总人口（人 - 手动输入）：</b>",
        "lbl_pop_note": "*（按居住街坊面积比例分配人口并检测现有设施容量超载）*",
        "lbl_split": "<b>多设施组合与非MPYY图层：</b>",
        "chk_split": "支持大型街坊配置“小学+公园缓冲+社区医院”，并生成非MPYY被动绿地与商业用地",
        "grp3": "3. 附表2社会与技术基础设施标准表（法规官方数值 - 可完全编辑）",
        "col_name": "基础设施 / 设施\n（附表2标准与颜色）",
        "col_layer": "现有多边形图层\n（从地图选择）",
        "col_euclid": "直线服务\n半径 (m)",
        "col_net": "路网步行\n距离 (m)",
        "col_std": "附表2人均指标\n(m²/人 或 m³/人)",
        "col_min": "附表2最小单元面积\n(Min m²)",
        "col_max": "分割阈值\n(Max m²)",
        "col_cap": "单体建筑容量\n(人数)",
        "btn_add": "➕ 添加新设施行",
        "btn_del": "🗑️ 删除选中行",
        "btn_reset": "🔄 重置为附表2规范",
        "btn_demo": "🚀 生成示例多边形测试数据",
        "btn_run": "⚡ 开始智能附表2分析并渲染至地图",
        "none_layer": "-- 无 / 区域内不存在 --",
        "auto_comm_layer": "-- 自动检测商业图层 / 演示模式 --",
        "new_fac": "新公共设施",
        "empty_report": f"<h3>尚未运行分析。</h3><p><b>作者:</b> {PLUGIN_AUTHOR} — 请选择图层并点击<b>开始分析</b>按钮。</p>",
        "warn_missing_title": "缺少图层",
        "warn_missing_msg": "请选择路网图层、现有居住街坊和空置地块！",
        "done_title": "智能分析与空间优化已完成",
        "done_msg": "MPYY 设施图层及非 MPYY 被动绿地、商业用地演示图层已添加至地图！"
    },
    "es": {
        "win_title": f"MPYY Accesibilidad de Instalaciones Urbanas y Optimización — Autor: {PLUGIN_AUTHOR}",
        "banner_title": "SISTEMA DE SOPORTE DE DECISIONES DE PLANES ESPACIALES (MPYY) - ESTÁNDARES ANEXO-2",
        "banner_sub": f"Alivio de Sobrecarga • Doble Dotación + Parque Intermedio • Verde Pasivo y Comercial Demo • Autor: {PLUGIN_AUTHOR}",
        "dev_label": "⚡ Desarrollador / Autor",
        "tab1": "1. Capas de Polígonos y Tabla Anexo-2",
        "tab2": "2. Informe Detallado de Planificación y Accesibilidad",
        "grp1": "1. Capas de Mapa Base (Los polígonos se convierten automáticamente a centroides en segundo plano)",
        "lbl_net": "<b>Red Preparada (Prepared Network - Línea):</b>",
        "lbl_res": "<b>Manzanas Residenciales Existentes (Polígono):</b>",
        "lbl_vac": "<b>Parcelas Vacantes / Bloques Urbanos (Polígono - A Dividir):</b>",
        "lbl_comm": "<b>Áreas Comerciales Existentes (Polígono - Demo Fuera de MPYY):</b>",
        "chk_centroids": "Mostrar centroides generados automáticamente en el mapa",
        "grp2": "2. Población del Área de Planificación y Suficiencia Inteligente",
        "lbl_pop": "<b>Población Total del Área de Planificación (Personas):</b>",
        "lbl_pop_note": "*(Población ponderada por área de manzana residencial y control de sobrecarga)*",
        "lbl_split": "<b>Subdivisión Multi-Dotación y Capas Fuera de MPYY:</b>",
        "chk_split": "Permitir 2 dotaciones separadas por Parque en bloques grandes y generar Verde Pasivo y Comercial Demo",
        "grp3": "3. Tabla de Estándares Anexo-2 (Valores Oficiales del Reglamento - Completamente Editable)",
        "col_name": "Infraestructura / Instalación\n(Estándar Anexo-2 y Color)",
        "col_layer": "Capa de Polígono Existente\n(Seleccionar del Mapa)",
        "col_euclid": "Radio Euclidiano\n(m)",
        "col_net": "Distancia de Red\nVial (m)",
        "col_std": "Estándar Anexo-2 Per Cápita\n(m²/pers o m³/pers)",
        "col_min": "Área Mínima Anexo-2\n(Mín m²)",
        "col_max": "Umbral de División\n(Máx m²)",
        "col_cap": "Capacidad de 1 Edificio\n(Personas)",
        "btn_add": "➕ Agregar Fila de Instalación",
        "btn_del": "🗑️ Eliminar Fila Seleccionada",
        "btn_reset": "🔄 Restablecer Normas Anexo-2",
        "btn_demo": "🚀 Generar Datos de Prueba Poligonales",
        "btn_run": "⚡ EJECUTAR ANÁLISIS INTELIGENTE ANEXO-2 Y RENDERIZAR EN MAPA",
        "none_layer": "-- Ninguno / No presente en el área --",
        "auto_comm_layer": "-- Auto-Detectar Comercial / Modo Demo --",
        "new_fac": "Nueva Instalación",
        "empty_report": f"<h3>El análisis aún no se ha ejecutado.</h3><p><b>Autor:</b> {PLUGIN_AUTHOR} — Seleccione sus capas y haga clic en <b>EJECUTAR ANÁLISIS</b>.</p>",
        "warn_missing_title": "Capa Faltante",
        "warn_missing_msg": "¡Seleccione la Red Preparada, Bloques Residenciales y Parcelas Vacantes!",
        "done_title": "Análisis Inteligente Anexo-2 Completado",
        "done_msg": "¡Los polígonos MPYY, Áreas Verdes Pasivas y Áreas Comerciales Demo se han agregado al mapa!"
    }
}

MODERN_STYLE = """
QDialog {
    background-color: #f8fafc;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 12px;
    color: #0f172a;
}
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 14px;
    font-weight: bold;
    color: #0f172a;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #1d4ed8;
}
QTabWidget::pane {
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    background: #ffffff;
}
QTabBar::tab {
    background: #e2e8f0;
    color: #334155;
    padding: 8px 22px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
    font-weight: bold;
    min-width: 240px;
}
QTabBar::tab:selected {
    background: #1e40af;
    color: #ffffff;
}
QComboBox, QSpinBox {
    border: 1px solid #94a3b8;
    border-radius: 5px;
    padding: 3px 8px;
    background-color: #ffffff;
    color: #0f172a;
    min-height: 24px;
}
QComboBox:focus, QSpinBox:focus {
    border: 1.5px solid #2563eb;
}
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f8fafc;
    gridline-color: #cbd5e1;
    border: 1px solid #94a3b8;
    border-radius: 6px;
    font-size: 12px;
    color: #0f172a;
    selection-background-color: #dbeafe;
    selection-color: #0f172a;
}
QHeaderView::section {
    background-color: #0f172a;
    color: #ffffff;
    font-weight: bold;
    font-size: 11px;
    padding: 6px 4px;
    border: 1px solid #334155;
}
QPushButton {
    background-color: #e2e8f0;
    color: #0f172a;
    border: 1px solid #94a3b8;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #cbd5e1;
}
QProgressBar {
    border: 1px solid #94a3b8;
    border-radius: 6px;
    text-align: center;
    background-color: #e2e8f0;
    font-weight: bold;
    color: #0f172a;
    min-height: 28px;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #06b6d4);
    border-radius: 5px;
}
"""


def _draw_star(painter, cx, cy, r_outer, r_inner, angle_deg=0.0):
    pts = []
    for i in range(10):
        ang = math.radians(angle_deg + i * 36.0)
        r = r_outer if i % 2 == 0 else r_inner
        pts.append(QPointF(cx + r * math.cos(ang), cy + r * math.sin(ang)))
    painter.drawPolygon(QPolygonF(pts))


def create_flag_icon(lang_code):
    w, h = 36, 24
    pix = QPixmap(w, h)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    if lang_code == "tr":
        p.fillRect(0, 0, w, h, QColor("#E30A17"))
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(13.0, 12.0), 6.5, 6.5)
        p.setBrush(QColor("#E30A17"))
        p.drawEllipse(QPointF(14.8, 12.0), 5.2, 5.2)
        p.setBrush(QColor("#FFFFFF"))
        _draw_star(p, 22.8, 12.0, 3.4, 1.3, angle_deg=-18.0)
    elif lang_code == "en":
        p.fillRect(0, 0, w, h, QColor("#012169"))
        pen_w_diag = QPen(QColor("#FFFFFF"), 4.6)
        p.setPen(pen_w_diag)
        p.drawLine(0, 0, w, h)
        p.drawLine(0, h, w, 0)
        pen_r_diag = QPen(QColor("#C8102E"), 2.0)
        p.setPen(pen_r_diag)
        p.drawLine(0, 0, w, h)
        p.drawLine(0, h, w, 0)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawRect(QRectF(0, 8, w, 8))
        p.drawRect(QRectF(14, 0, 8, h))
        p.setBrush(QColor("#C8102E"))
        p.drawRect(QRectF(0, 9.6, w, 4.8))
        p.drawRect(QRectF(15.6, 0, 4.8, h))
    elif lang_code == "zh":
        p.fillRect(0, 0, w, h, QColor("#DE2910"))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFDE00"))
        _draw_star(p, 7.5, 7.5, 4.2, 1.6, angle_deg=-90.0)
        for sx, sy in [(14.5, 3.0), (17.2, 5.8), (17.2, 9.8), (14.5, 12.6)]:
            _draw_star(p, sx, sy, 1.6, 0.65, angle_deg=-70.0)
    elif lang_code == "es":
        p.fillRect(0, 0, w, h, QColor("#AA151B"))
        p.setBrush(QColor("#F1BF00"))
        p.setPen(Qt.NoPen)
        p.drawRect(QRectF(0, 6, w, 12))
        p.setBrush(QColor("#AA151B"))
        p.drawRect(QRectF(5, 8, 4, 8))

    p.setPen(QPen(QColor(0, 0, 0, 60), 1.0))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(0, 0, w - 1, h - 1))
    p.end()
    return QIcon(pix)


def create_color_swatch_icon(hex_color):
    pix = QPixmap(18, 18)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(hex_color))
    p.setPen(QPen(QColor("#1e293b"), 1.2))
    p.drawRoundedRect(QRectF(1, 1, 16, 16), 4, 4)
    p.end()
    return QIcon(pix)


class MPYYDonatiDialog(QDialog):
    def __init__(self, iface=None, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.current_lang = "en"
        self.cur_lang = "en"
        self.resize(1240, 860)
        self.setStyleSheet(MODERN_STYLE)
        self.setup_ui()
        self.table = self.tbl_params
        self.apply_language("en")

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        banner = QFrame()
        banner.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f172a, stop:0.6 #1e3a8a, stop:1 #1d4ed8);"
            "border-radius: 8px; padding: 8px;"
        )
        banner_layout = QHBoxLayout(banner)

        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        logo_lbl = QLabel()
        if os.path.exists(icon_path):
            logo_lbl.setPixmap(QPixmap(icon_path).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo_lbl.setFixedSize(52, 52)
        logo_lbl.setStyleSheet("background: transparent;")
        banner_layout.addWidget(logo_lbl)

        self.title_lbl = QLabel()
        self.title_lbl.setStyleSheet("background: transparent;")
        banner_layout.addWidget(self.title_lbl, stretch=1)

        lang_box = QVBoxLayout()
        self.cmb_lang = QComboBox()
        self.cmb_lang.setIconSize(QSize(28, 18))
        self.cmb_lang.setFixedWidth(185)
        self.cmb_lang.setStyleSheet(
            "QComboBox { background-color: #ffffff; color: #0f172a; font-weight: bold; font-size: 12px; border-radius: 5px; padding: 4px 8px; }"
        )
        self.cmb_lang.addItem(create_flag_icon("en"), "English (EN)", "en")
        self.cmb_lang.addItem(create_flag_icon("tr"), "Türkçe (TR)", "tr")
        self.cmb_lang.addItem(create_flag_icon("zh"), "中文 (ZH)", "zh")
        self.cmb_lang.addItem(create_flag_icon("es"), "Español (ES)", "es")
        self.cmb_lang.currentIndexChanged.connect(self.on_language_changed)
        lang_box.addWidget(self.cmb_lang)

        self.author_badge = QLabel()
        self.author_badge.setStyleSheet(
            "background-color: rgba(255,255,255,0.16); border: 1px solid rgba(255,255,255,0.32); "
            "border-radius: 6px; padding: 3px 8px;"
        )
        lang_box.addWidget(self.author_badge)
        banner_layout.addLayout(lang_box)

        main_layout.addWidget(banner)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        tab_inputs = QWidget()
        layout_inputs = QVBoxLayout(tab_inputs)

        self.grp_layers = QGroupBox()
        grid = QGridLayout(self.grp_layers)
        grid.setSpacing(8)

        self.lbl_net = QLabel()
        grid.addWidget(self.lbl_net, 0, 0)
        self.cmb_network = QComboBox()
        grid.addWidget(self.cmb_network, 0, 1)

        self.lbl_res = QLabel()
        grid.addWidget(self.lbl_res, 1, 0)
        self.cmb_residential_poly = QComboBox()
        grid.addWidget(self.cmb_residential_poly, 1, 1)

        self.lbl_vac = QLabel()
        grid.addWidget(self.lbl_vac, 2, 0)
        self.cmb_vacant_polys = QComboBox()
        grid.addWidget(self.cmb_vacant_polys, 2, 1)

        self.lbl_comm = QLabel()
        grid.addWidget(self.lbl_comm, 3, 0)
        self.cmb_commercial_poly = QComboBox()
        grid.addWidget(self.cmb_commercial_poly, 3, 1)

        self.chk_show_centroids = QCheckBox()
        self.chk_show_centroids.setChecked(False)
        self.chk_show_centroids.setStyleSheet("color: #1e40af; font-weight: bold;")
        grid.addWidget(self.chk_show_centroids, 4, 0, 1, 2)

        layout_inputs.addWidget(self.grp_layers)

        self.grp_pop = QGroupBox()
        pop_grid = QGridLayout(self.grp_pop)

        self.lbl_pop = QLabel()
        pop_grid.addWidget(self.lbl_pop, 0, 0)
        self.spn_population = QSpinBox()
        self.spn_population.setRange(100, 10000000)
        self.spn_population.setValue(65000)
        self.spn_population.setSingleStep(1000)
        self.spn_population.setStyleSheet("font-weight: bold; font-size: 13px; color: #1e3a8a;")
        pop_grid.addWidget(self.spn_population, 0, 1)

        self.lbl_pop_note = QLabel()
        pop_grid.addWidget(self.lbl_pop_note, 0, 2)

        self.lbl_split = QLabel()
        pop_grid.addWidget(self.lbl_split, 1, 0)
        self.chk_auto_split = QCheckBox()
        self.chk_auto_split.setChecked(True)
        pop_grid.addWidget(self.chk_auto_split, 1, 1, 1, 2)

        layout_inputs.addWidget(self.grp_pop)

        self.grp_table = QGroupBox()
        tbl_layout = QVBoxLayout(self.grp_table)

        self.tbl_params = QTableWidget()
        self.tbl_params.setAlternatingRowColors(True)
        self.tbl_params.setIconSize(QSize(18, 18))
        self.tbl_params.setColumnCount(8)
        self.tbl_params.setWordWrap(True)

        horiz_hdr = self.tbl_params.horizontalHeader()
        horiz_hdr.setDefaultAlignment(Qt.AlignCenter)
        horiz_hdr.setFixedHeight(46)
        horiz_hdr.setSectionResizeMode(QHeaderView.Stretch)
        horiz_hdr.setSectionResizeMode(0, QHeaderView.Interactive)
        horiz_hdr.setSectionResizeMode(1, QHeaderView.Interactive)
        self.tbl_params.setColumnWidth(0, 230)
        self.tbl_params.setColumnWidth(1, 220)

        vert_hdr = self.tbl_params.verticalHeader()
        vert_hdr.setDefaultSectionSize(36)

        self.populate_default_params()
        tbl_layout.addWidget(self.tbl_params)

        btn_row = QHBoxLayout()
        self.btn_add_row = QPushButton()
        self.btn_add_row.clicked.connect(self.add_facility_row)
        self.btn_del_row = QPushButton()
        self.btn_del_row.clicked.connect(self.remove_selected_facility_row)
        self.btn_reset_mpyy = QPushButton()
        self.btn_reset_mpyy.clicked.connect(self.reset_and_populate)
        self.btn_demo = QPushButton()
        self.btn_demo.setStyleSheet("background-color: #f59e0b; color: white; border: none; padding: 6px 14px;")
        self.btn_demo.clicked.connect(self.create_demo_layers)

        btn_row.addWidget(self.btn_add_row)
        btn_row.addWidget(self.btn_del_row)
        btn_row.addWidget(self.btn_reset_mpyy)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_demo)
        tbl_layout.addLayout(btn_row)

        layout_inputs.addWidget(self.grp_table, stretch=1)
        self.tabs.addTab(tab_inputs, "")

        self.tab_report = QWidget()
        layout_report = QVBoxLayout(self.tab_report)

        self.txt_report = QTextBrowser()
        self.txt_report.setOpenExternalLinks(True)
        layout_report.addWidget(self.txt_report)
        self.tabs.addTab(self.tab_report, "")

        bottom_layout = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setValue(0)
        bottom_layout.addWidget(self.progress, stretch=2)

        self.btn_run = QPushButton()
        self.btn_run.setMinimumHeight(42)
        self.btn_run.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e40af, stop:1 #2563eb);"
            "color: white; font-weight: bold; font-size: 13px; padding: 6px 18px; border-radius: 6px;"
        )
        self.btn_run.clicked.connect(self.run_full_analysis)
        bottom_layout.addWidget(self.btn_run, stretch=1)

        main_layout.addLayout(bottom_layout)

    def on_language_changed(self):
        lang_code = self.cmb_lang.currentData()
        if lang_code:
            self.apply_language(lang_code)

    def apply_language(self, lang):
        self.current_lang = lang
        self.cur_lang = lang
        t = TRANSLATIONS[lang]

        self.setWindowTitle(t["win_title"])
        self.title_lbl.setText(
            f"<span style='font-size:15px; font-weight:bold; color:#ffffff;'>{t['banner_title']}</span><br>"
            f"<span style='font-size:11px; color:#bae6fd;'>{t['banner_sub']}</span>"
        )
        self.author_badge.setText(
            f"<div align='right' style='color:#fde047; font-weight:bold; font-size:10px;'>"
            f"{t['dev_label']}: <span style='color:#ffffff; font-size:11px;'>{PLUGIN_AUTHOR}</span></div>"
        )

        self.tabs.setTabText(0, t["tab1"])
        self.tabs.setTabText(1, t["tab2"])

        self.grp_layers.setTitle(t["grp1"])
        self.lbl_net.setText(t["lbl_net"])
        self.lbl_res.setText(t["lbl_res"])
        self.lbl_vac.setText(t["lbl_vac"])
        self.lbl_comm.setText(t["lbl_comm"])
        self.chk_show_centroids.setText(t["chk_centroids"])

        self.grp_pop.setTitle(t["grp2"])
        self.lbl_pop.setText(t["lbl_pop"])
        self.lbl_pop_note.setText(t["lbl_pop_note"])
        self.lbl_split.setText(t["lbl_split"])
        self.chk_auto_split.setText(t["chk_split"])

        self.grp_table.setTitle(t["grp3"])
        self.tbl_params.setHorizontalHeaderLabels([
            t["col_name"], t["col_layer"], t["col_euclid"], t["col_net"],
            t["col_std"], t["col_min"], t["col_max"], t["col_cap"]
        ])

        self.btn_add_row.setText(t["btn_add"])
        self.btn_del_row.setText(t["btn_del"])
        self.btn_reset_mpyy.setText(t["btn_reset"])
        self.btn_demo.setText(t["btn_demo"])
        self.btn_run.setText(t["btn_run"])

        if self.cmb_commercial_poly.count() > 0:
            self.cmb_commercial_poly.setItemText(0, t["auto_comm_layer"])

        lang_idx_map = {"tr": 1, "en": 2, "zh": 3, "es": 4}
        lang_idx = lang_idx_map.get(lang, 1)

        for r in range(self.tbl_params.rowCount()):
            name_item = self.tbl_params.item(r, 0)
            if name_item:
                key_id = name_item.data(Qt.UserRole)
                if key_id:
                    for item in DEFAULT_MPYY_FACILITIES:
                        if item[0] == key_id:
                            name_item.setText(item[lang_idx])
                            break
            cmb = self.tbl_params.cellWidget(r, 1)
            if cmb and cmb.count() > 0:
                cmb.setItemText(0, t["none_layer"])

        if self.progress.value() == 0:
            self.txt_report.setHtml(t["empty_report"])

    def _create_poly_layer_combo(self, auto_keywords=None):
        t = TRANSLATIONS[self.current_lang]
        cmb = QComboBox()
        cmb.addItem(t["none_layer"], None)
        layers = QgsProject.instance().mapLayers().values()
        for lyr in layers:
            if isinstance(lyr, QgsVectorLayer) and lyr.geometryType() in (QgsWkbTypes.PolygonGeometry, QgsWkbTypes.PointGeometry):
                if lyr.name().startswith("MPYY_"):
                    continue
                cmb.addItem(lyr.name(), lyr)
        if auto_keywords:
            self._auto_select_combo(cmb, auto_keywords, start_idx=1)
        return cmb

    def populate_default_params(self):
        lang_idx_map = {"tr": 1, "en": 2, "zh": 3, "es": 4}
        lang_idx = lang_idx_map.get(self.current_lang, 1)
        bold_font = QFont("Segoe UI", 10, QFont.Bold)
        num_font = QFont("Segoe UI", 10, QFont.DemiBold)

        self.tbl_params.setRowCount(0)
        for row_idx, item in enumerate(DEFAULT_MPYY_FACILITIES):
            self.tbl_params.insertRow(row_idx)
            self.tbl_params.setRowHeight(row_idx, 36)

            name_cell = QTableWidgetItem(create_color_swatch_icon(item[11]), str(item[lang_idx]))
            name_cell.setData(Qt.UserRole, item[0])
            name_cell.setFont(bold_font)
            name_cell.setForeground(QColor("#0f172a"))
            self.tbl_params.setItem(row_idx, 0, name_cell)

            cmb = self._create_poly_layer_combo(auto_keywords=item[12])
            self.tbl_params.setCellWidget(row_idx, 1, cmb)

            for col_idx, val_idx in enumerate(range(5, 11), start=2):
                cell = QTableWidgetItem(str(item[val_idx]))
                cell.setFont(num_font)
                cell.setForeground(QColor("#0f172a"))
                cell.setTextAlignment(Qt.AlignCenter)
                if col_idx == 5:
                    cell.setBackground(QColor("#eff6ff"))
                    cell.setForeground(QColor("#1d4ed8"))
                self.tbl_params.setItem(row_idx, col_idx, cell)

    def reset_and_populate(self):
        self.populate_default_params()
        self.populate_layers()

    def add_facility_row(self):
        t = TRANSLATIONS[self.current_lang]
        r = self.tbl_params.rowCount()
        self.tbl_params.insertRow(r)
        self.tbl_params.setRowHeight(r, 36)
        name_cell = QTableWidgetItem(create_color_swatch_icon("#475569"), t["new_fac"])
        name_cell.setData(Qt.UserRole, f"custom_{r}")
        name_cell.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.tbl_params.setItem(r, 0, name_cell)
        cmb = self._create_poly_layer_combo()
        self.tbl_params.setCellWidget(r, 1, cmb)
        defaults = ["500.0", "500.0", "1.0", "1000.0", "5000.0", "2500"]
        for c_offset, val in enumerate(defaults, start=2):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignCenter)
            self.tbl_params.setItem(r, c_offset, item)

    def remove_selected_facility_row(self):
        cur_row = self.tbl_params.currentRow()
        if cur_row >= 0:
            self.tbl_params.removeRow(cur_row)

    def populate_layers(self):
        t = TRANSLATIONS[self.current_lang]
        self.cmb_network.clear()
        self.cmb_residential_poly.clear()
        self.cmb_vacant_polys.clear()
        self.cmb_commercial_poly.clear()
        self.cmb_commercial_poly.addItem(t["auto_comm_layer"], None)

        layers = QgsProject.instance().mapLayers().values()
        for lyr in layers:
            if not isinstance(lyr, QgsVectorLayer):
                continue
            if lyr.name().startswith("MPYY_"):
                continue
            geom_type = lyr.geometryType()
            if geom_type == QgsWkbTypes.LineGeometry:
                self.cmb_network.addItem(lyr.name(), lyr)
            elif geom_type == QgsWkbTypes.PolygonGeometry:
                self.cmb_residential_poly.addItem(lyr.name(), lyr)
                self.cmb_vacant_polys.addItem(lyr.name(), lyr)
                self.cmb_commercial_poly.addItem(lyr.name(), lyr)

        self._auto_select_combo(self.cmb_network, ["prepared", "yol", "network", "ag", "road"])
        self._auto_select_combo(self.cmb_residential_poly, ["konut_adalari", "mevcut_konut", "konut", "yerlesim"])
        self._auto_select_combo(self.cmb_vacant_polys, ["mevcut_bos", "bos_alan", "bos_imar", "bos_ada", "bos", "vacant"])
        self._auto_select_combo(self.cmb_commercial_poly, ["mevcut_ticari", "ticari", "ticaret", "commercial"], start_idx=1)

        for r in range(self.tbl_params.rowCount()):
            name_item = self.tbl_params.item(r, 0)
            key_id = name_item.data(Qt.UserRole) if name_item else ""
            fac_name = name_item.text().strip().lower() if name_item else ""
            old_cmb = self.tbl_params.cellWidget(r, 1)
            prev_lyr = old_cmb.currentData() if old_cmb else None

            kw = [fac_name]
            for item in DEFAULT_MPYY_FACILITIES:
                if item[0] == key_id:
                    kw = item[12]
                    break

            new_cmb = self._create_poly_layer_combo(auto_keywords=kw)
            if prev_lyr is not None:
                for i in range(new_cmb.count()):
                    if new_cmb.itemData(i) == prev_lyr:
                        new_cmb.setCurrentIndex(i)
                        break
            self.tbl_params.setCellWidget(r, 1, new_cmb)

    def _auto_select_combo(self, combo, keywords, start_idx=0):
        for kw in keywords:
            for i in range(start_idx, combo.count()):
                txt = combo.itemText(i).lower()
                if kw in txt:
                    combo.setCurrentIndex(i)
                    return

    def read_parameters_table(self):
        specs = {}
        color_lookup = {item[0]: item[11] for item in DEFAULT_MPYY_FACILITIES}
        for r in range(self.tbl_params.rowCount()):
            try:
                name_item = self.tbl_params.item(r, 0)
                name = name_item.text().strip() if name_item else ""
                if not name:
                    continue
                key_id = name_item.data(Qt.UserRole) or name
                cmb = self.tbl_params.cellWidget(r, 1)
                poly_lyr = cmb.currentData() if cmb else None

                euclid_r = float(self.tbl_params.item(r, 2).text().replace(",", "."))
                net_r = float(self.tbl_params.item(r, 3).text().replace(",", "."))
                std_m2 = float(self.tbl_params.item(r, 4).text().replace(",", "."))
                min_area = float(self.tbl_params.item(r, 5).text().replace(",", "."))
                max_single = float(self.tbl_params.item(r, 6).text().replace(",", "."))
                unit_cap = float(self.tbl_params.item(r, 7).text().replace(",", "."))

                specs[name] = {
                    "key_id": key_id,
                    "name": name,
                    "layer": poly_lyr,
                    "euclid_r": euclid_r,
                    "net_r": net_r,
                    "std_m2": std_m2,
                    "min_area": min_area,
                    "max_single": max_single,
                    "unit_cap": unit_cap,
                    "color": color_lookup.get(key_id, "#475569")
                }
            except Exception:
                continue
        return specs

    def _find_park_category_name(self, specs):
        for cat, sp in specs.items():
            if sp["key_id"] == "park" or "park" in cat.lower() or "公园" in cat or "parque" in cat.lower():
                return cat
        return list(specs.keys())[-1]

    def _find_residential_growth_category_name(self, specs):
        for cat, sp in specs.items():
            if sp["key_id"] == "konut" or "konut" in cat.lower() or "residential" in cat.lower() or "居住" in cat:
                return cat
        return None

    def _detect_commercial_layer(self):
        comm_lyr = self.cmb_commercial_poly.currentData() if hasattr(self, "cmb_commercial_poly") else None
        if comm_lyr is not None:
            return comm_lyr
        for lyr in QgsProject.instance().mapLayers().values():
            if isinstance(lyr, QgsVectorLayer) and lyr.geometryType() in (QgsWkbTypes.PolygonGeometry, QgsWkbTypes.PointGeometry):
                lname = lyr.name().lower()
                if not lname.startswith("mpyy_") and any(k in lname for k in ("ticari", "ticaret", "commercial")):
                    return lyr
        return None

    def run_full_analysis(self):
        t = TRANSLATIONS[self.current_lang]
        net_lyr = self.cmb_network.currentData()
        res_poly_lyr = self.cmb_residential_poly.currentData()
        vac_poly_lyr = self.cmb_vacant_polys.currentData()

        if not all([net_lyr, res_poly_lyr, vac_poly_lyr]):
            QMessageBox.warning(self, t["warn_missing_title"], t["warn_missing_msg"])
            return

        specs = self.read_parameters_table()
        if not specs:
            return

        self.btn_run.setEnabled(False)
        self.progress.setValue(5)
        QApplication.processEvents()

        try:
            total_pop = float(self.spn_population.value())
            work_crs = vac_poly_lyr.crs()
            crs_auth = work_crs.authid()
            park_cat = self._find_park_category_name(specs)
            res_growth_cat = self._find_residential_growth_category_name(specs)
            comm_lyr = self._detect_commercial_layer()

            graph = FastRoadGraph(net_lyr, target_crs=work_crs, tolerance=2.5)
            self.progress.setValue(18)
            QApplication.processEvents()

            # 1. Load Existing Facilities & Compute Area-Scaled Real Capacity (C_j)
            # Small existing facilities (e.g. a 2,000 m² school when MPYY min_area is 5,000 m²)
            # receive proportional capacity (2,500 * 2000/5000 = 1,000 persons) so capacity
            # overload is accurately detected when 5,000 residents load that school!
            fac_by_type = {k: [] for k in specs.keys()}
            existing_cap_by_type = {k: 0.0 for k in specs.keys()}

            fac_pts_lyr = QgsVectorLayer(f"Point?crs={crs_auth}", "MPYY_Mevcut_Donati_Agirlik_Merkezleri", "memory")
            fac_pts_pr = fac_pts_lyr.dataProvider()
            fac_pts_pr.addAttributes([
                QgsField("donati_turu", _QVAR_STRING),
                QgsField("kaynak_id", _QVAR_INT),
                QgsField("alan_m2", _QVAR_DOUBLE),
                QgsField("birim_kapasite", _QVAR_INT),
                QgsField("atanan_nufus_yuku", _QVAR_INT),
                QgsField("kapasite_durumu", _QVAR_STRING),
            ])
            fac_pts_lyr.updateFields()

            for cat, sp in specs.items():
                if sp["key_id"] == "konut":
                    continue
                lyr = sp["layer"]
                unit_cap = sp["unit_cap"]
                if lyr is None:
                    continue
                xform = None
                if lyr.crs() != work_crs:
                    xform = QgsCoordinateTransform(lyr.crs(), work_crs, QgsProject.instance())
                for feat in lyr.getFeatures():
                    geom = feat.geometry()
                    if not geom or geom.isEmpty():
                        continue
                    if xform is not None:
                        geom = QgsGeometry(geom)
                        geom.transform(xform)
                    pt = geom.centroid().asPoint()
                    area_m2 = geom.area() if lyr.geometryType() == QgsWkbTypes.PolygonGeometry else sp["min_area"]
                    # Proportional area capacity: a 2,000 m² school (min_area 5,000 m²) gets 40% of unit_cap!
                    scale_mult = max(0.30, min(2.20, area_m2 / max(sp["min_area"], 500.0))) if area_m2 > 0 else 1.0
                    eff_cap = unit_cap * scale_mult
                    fac_by_type[cat].append([feat.id(), pt, eff_cap, area_m2, 0.0])  # [id, pt, cap, area, demand_load]
                    existing_cap_by_type[cat] += eff_cap

            # 2. Load Existing Commercial Areas (Non-MPYY Accessibility Evaluation)
            comm_pts = []
            if comm_lyr is not None:
                c_xform = None
                if comm_lyr.crs() != work_crs:
                    c_xform = QgsCoordinateTransform(comm_lyr.crs(), work_crs, QgsProject.instance())
                for cf in comm_lyr.getFeatures():
                    cg = cf.geometry()
                    if cg and not cg.isEmpty():
                        if c_xform is not None:
                            cg = QgsGeometry(cg)
                            cg.transform(c_xform)
                        comm_pts.append(cg.centroid().asPoint())

            self.progress.setValue(32)
            QApplication.processEvents()

            # 3. Multi-Source Road Network Dijkstra with Nearest-Facility Owner Tracking
            max_cutoff = max([v["net_r"] for v in specs.values()] + [2800.0]) * 1.25
            net_dist_maps = {}
            net_owner_maps = {}
            for cat, items in fac_by_type.items():
                if items:
                    src_items = [(idx_f, it[1]) for idx_f, it in enumerate(items)]
                    d_map, o_map = graph.multi_source_dijkstra_with_nearest(src_items, max_cutoff=max_cutoff)
                    net_dist_maps[cat] = d_map
                    net_owner_maps[cat] = o_map
                else:
                    net_dist_maps[cat] = {}
                    net_owner_maps[cat] = {}
                QApplication.processEvents()

            comm_dist_map = graph.multi_source_dijkstra(comm_pts, max_cutoff=3000.0) if comm_pts else {}

            self.progress.setValue(45)

            # 4. Snap Every Residential Block/Building Polygon to Nearest Street Node
            res_feats = []
            total_res_area = 0.0
            sum_rx, sum_ry = 0.0, 0.0
            res_xform = None
            if res_poly_lyr.crs() != work_crs:
                res_xform = QgsCoordinateTransform(res_poly_lyr.crs(), work_crs, QgsProject.instance())

            for rf in res_poly_lyr.getFeatures():
                g = rf.geometry()
                if g and not g.isEmpty():
                    if res_xform is not None:
                        g = QgsGeometry(g)
                        g.transform(res_xform)
                    a = max(g.area(), 1.0)
                    pt = g.centroid().asPoint()
                    nid, snap_d = graph.snap_polygon_to_node(g)
                    res_feats.append((rf.id(), pt, a, nid, snap_d))
                    total_res_area += a
                    sum_rx += pt.x() * a
                    sum_ry += pt.y() * a

            if total_res_area <= 0:
                total_res_area = 1.0
            res_center_pt = QgsPointXY(sum_rx / total_res_area, sum_ry / total_res_area)

            # 5. Pass 1: Accumulate Population Demand Load (D_j) on Each Existing Facility j
            res_nearest_fac = {cat: {} for cat in specs.keys() if specs[cat]["key_id"] != "konut"}
            for r_id, pt, r_area, r_nid, r_snap in res_feats:
                ada_pop = total_pop * (r_area / total_res_area)
                for cat, sp in specs.items():
                    if sp["key_id"] == "konut":
                        continue
                    items = fac_by_type[cat]
                    if not items:
                        continue
                    # Find nearest Euclidean facility
                    best_b_idx = 0
                    d_bird = float('inf')
                    for idx_f, it in enumerate(items):
                        db = math.hypot(pt.x() - it[1].x(), pt.y() - it[1].y())
                        if db < d_bird:
                            d_bird = db
                            best_b_idx = idx_f

                    d_map = net_dist_maps[cat]
                    o_map = net_owner_maps[cat]
                    if r_nid is not None and r_nid in d_map:
                        d_road = d_map[r_nid] + r_snap
                        fac_idx = o_map.get(r_nid, best_b_idx)
                    else:
                        d_road = float('inf')
                        fac_idx = best_b_idx

                    bird_ok = (d_bird <= sp["euclid_r"])
                    road_ok = (d_road <= sp["net_r"])
                    res_nearest_fac[cat][r_id] = (d_bird, d_road, bird_ok, road_ok, fac_idx)
                    if bird_ok and road_ok and 0 <= fac_idx < len(items):
                        items[fac_idx][4] += ada_pop

            # Write Existing Facility Centroids with Load & Capacity-Overflow Status
            fac_pt_features = []
            overloaded_facilities = {k: [] for k in specs.keys() if specs[k]["key_id"] != "konut"}
            for cat, items in fac_by_type.items():
                sp_cat = specs[cat]
                for idx_f, (fid, fpt, fcap, farea, fload) in enumerate(items):
                    # Trigger capacity-overflow relief specifically when an existing facility parcel is physically
                    # undersized (<90% of MPYY Annex-2 min_area, e.g., a 2,000 m² school) AND overloaded!
                    is_over = (
                        farea < sp_cat["min_area"] * 0.92
                        and fload > fcap * 1.15
                        and (fload - fcap) >= 500.0
                    )
                    f_pt = QgsFeature(fac_pts_lyr.fields())
                    f_pt.setGeometry(QgsGeometry.fromPointXY(fpt))
                    f_pt["donati_turu"] = cat
                    f_pt["kaynak_id"] = fid
                    f_pt["alan_m2"] = round(farea, 1)
                    f_pt["birim_kapasite"] = int(round(fcap))
                    f_pt["atanan_nufus_yuku"] = int(round(fload))
                    f_pt["kapasite_durumu"] = (
                        f"OVERLOAD (+{int(fload - fcap)} kişi aşım)" if is_over else "YETERLİ (OK)"
                    )
                    fac_pt_features.append(f_pt)
                    if is_over:
                        overloaded_facilities[cat].append({
                            "fac_idx": idx_f,
                            "fid": fid,
                            "pt": fpt,
                            "area": farea,
                            "cap": fcap,
                            "load": fload,
                            "overflow_rem": min(fload - fcap, sp_cat["unit_cap"] * 1.25),
                        })
            fac_pts_pr.addFeatures(fac_pt_features)
            fac_pts_lyr.updateExtents()

            # 6. Pass 2: Evaluate Every Residential Block (Distance Reachability + Capacity Overflow)
            res_out_lyr = QgsVectorLayer(f"Point?crs={crs_auth}", "MPYY_Konut_Agirlik_Merkezleri_Erisim", "memory")
            res_pr = res_out_lyr.dataProvider()
            res_fields = QgsFields()
            res_fields.append(QgsField("ada_id", _QVAR_INT))
            res_fields.append(QgsField("ada_alan_m2", _QVAR_DOUBLE))
            res_fields.append(QgsField("tahmini_nufus", _QVAR_DOUBLE))
            res_fields.append(QgsField("ticari_yol_m", _QVAR_DOUBLE))

            for cat in specs.keys():
                if specs[cat]["key_id"] == "konut":
                    continue
                short_c = cat[:10].replace(" ", "_")
                res_fields.append(QgsField(f"{short_c}_kus_m", _QVAR_DOUBLE))
                res_fields.append(QgsField(f"{short_c}_yol_m", _QVAR_DOUBLE))
                res_fields.append(QgsField(f"{short_c}_durum", _QVAR_STRING))
            res_fields.append(QgsField("eksik_donatilar", _QVAR_STRING))
            res_fields.append(QgsField("aciklama_raporu", _QVAR_STRING))
            res_pr.addAttributes(res_fields)
            res_out_lyr.updateFields()

            unserved_pop_by_cat = {k: 0.0 for k in specs.keys() if specs[k]["key_id"] != "konut"}
            overflow_pop_by_cat = {k: 0.0 for k in specs.keys() if specs[k]["key_id"] != "konut"}
            bird_ok_road_fail_count = {k: 0 for k in specs.keys() if specs[k]["key_id"] != "konut"}
            unserved_res_nodes = {k: [] for k in specs.keys() if specs[k]["key_id"] != "konut"}

            out_res_features = []
            for idx_r, (r_id, pt, r_area, r_nid, r_snap) in enumerate(res_feats):
                if idx_r % 60 == 0:
                    QApplication.processEvents()
                ada_pop = total_pop * (r_area / total_res_area)

                new_f = QgsFeature(res_out_lyr.fields())
                new_f.setGeometry(QgsGeometry.fromPointXY(pt))
                new_f["ada_id"] = r_id
                new_f["ada_alan_m2"] = round(r_area, 1)
                new_f["tahmini_nufus"] = round(ada_pop, 1)

                d_comm_r = (comm_dist_map[r_nid] + r_snap) if (r_nid is not None and r_nid in comm_dist_map) else -1.0
                new_f["ticari_yol_m"] = round(d_comm_r, 1)

                eksikler = []
                rapor_satirlari = []

                for cat, sp in specs.items():
                    if sp["key_id"] == "konut":
                        continue
                    short_c = cat[:10].replace(" ", "_")
                    items = fac_by_type[cat]
                    if items and r_id in res_nearest_fac[cat]:
                        d_bird, d_road, bird_ok, road_ok, fac_idx = res_nearest_fac[cat][r_id]
                    else:
                        d_bird, d_road, bird_ok, road_ok, fac_idx = float('inf'), float('inf'), False, False, -1

                    new_f[f"{short_c}_kus_m"] = round(d_bird, 1) if d_bird < 1e8 else -1.0
                    new_f[f"{short_c}_yol_m"] = round(d_road, 1) if d_road < 1e8 else -1.0

                    if bird_ok and road_ok and 0 <= fac_idx < len(items):
                        fid, _, fcap, farea, fload = items[fac_idx]
                        if fload > fcap * 1.05 and (fload - fcap) >= 350.0:
                            overflow_share = (fload - fcap) / max(fload, 1.0)
                            ov_pop = ada_pop * overflow_share
                            durum = (
                                f"KAPASİTE AŞIMI (Mevcut #{fid}: {int(farea)}m², "
                                f"Yük:{int(fload)} > Kap:{int(fcap)} kişi)"
                            )
                            unserved_pop_by_cat[cat] += ov_pop
                            overflow_pop_by_cat[cat] += ov_pop
                            unserved_res_nodes[cat].append([pt, ov_pop, r_nid, r_snap, False])
                            eksikler.append(f"{cat} (Kapasite Aşımı)")
                            rapor_satirlari.append(
                                f"{cat}: Mesafe uygun ({int(d_road)}m) ancak mevcut bina ({int(farea)}m²) "
                                f"kapasitesi aşılıyor ({int(fload)}/{int(fcap)} kişi)."
                            )
                        else:
                            durum = f"OK (Yol:{int(d_road)}m, Yük:{int(fload)}/{int(fcap)})"
                            rapor_satirlari.append(f"{cat}: OK ({int(d_road)}m).")
                    elif bird_ok and not road_ok:
                        durum = f"KUŞ UÇUŞU OK ({int(d_bird)}m) / YOL ERİŞİMİ YOK (>{int(sp['net_r'])}m)"
                        bird_ok_road_fail_count[cat] += 1
                        unserved_pop_by_cat[cat] += ada_pop
                        unserved_res_nodes[cat].append([pt, ada_pop, r_nid, r_snap, False])
                        eksikler.append(cat)
                        rapor_satirlari.append(f"{cat}: Kuş uçuşu uygun ({int(d_bird)}m) ancak yol ağı >{int(sp['net_r'])}m.")
                    else:
                        durum = "ERİŞİM YOK"
                        unserved_pop_by_cat[cat] += ada_pop
                        unserved_res_nodes[cat].append([pt, ada_pop, r_nid, r_snap, False])
                        eksikler.append(cat)
                        rapor_satirlari.append(f"{cat}: Erişim yok.")

                    new_f[f"{short_c}_durum"] = durum

                new_f["eksik_donatilar"] = ", ".join(eksikler) if eksikler else "TAM (OK)"
                new_f["aciklama_raporu"] = " | ".join(rapor_satirlari)
                out_res_features.append(new_f)

            res_pr.addFeatures(out_res_features)
            res_out_lyr.updateExtents()
            self.progress.setValue(65)
            QApplication.processEvents()

            # 7. Create Output Layers (MPYY Group + Non-MPYY Complementary Group)
            alloc_lyr = QgsVectorLayer(f"Polygon?crs={crs_auth}", "MPYY_Onerilen_ve_Bolunen_Donati_Alanlari", "memory")
            alloc_pr = alloc_lyr.dataProvider()
            alloc_fields = QgsFields()
            alloc_fields.append(QgsField("kaynak_ada_id", _QVAR_INT))
            alloc_fields.append(QgsField("parca_no", _QVAR_INT))
            alloc_fields.append(QgsField("onerilen_donati", _QVAR_STRING))
            alloc_fields.append(QgsField("alan_m2", _QVAR_DOUBLE))
            alloc_fields.append(QgsField("hedef_nufus_etki", _QVAR_INT))
            alloc_fields.append(QgsField("yol_erisim_skoru", _QVAR_DOUBLE))
            alloc_fields.append(QgsField("mevcut_durum_ozeti", _QVAR_STRING))
            alloc_fields.append(QgsField("planlama_aciklama_raporu", _QVAR_STRING))
            alloc_fields.append(QgsField("yazar", _QVAR_STRING))
            alloc_pr.addAttributes(alloc_fields)
            alloc_lyr.updateFields()

            # Non-MPYY Layer 1: Passive Green Areas (Tampon / Refüj / Kavşak Yeşili)
            passive_lyr = QgsVectorLayer(f"Polygon?crs={crs_auth}", "Onerilen_Pasif_Yesil_Alanlar", "memory")
            passive_pr = passive_lyr.dataProvider()
            passive_fields = QgsFields()
            passive_fields.append(QgsField("kaynak_ada_id", _QVAR_INT))
            passive_fields.append(QgsField("parca_no", _QVAR_INT))
            passive_fields.append(QgsField("kullanim_turu", _QVAR_STRING))
            passive_fields.append(QgsField("alan_m2", _QVAR_DOUBLE))
            passive_fields.append(QgsField("tampon_islevi", _QVAR_STRING))
            passive_fields.append(QgsField("planlama_gerekcesi", _QVAR_STRING))
            passive_fields.append(QgsField("yazar", _QVAR_STRING))
            passive_pr.addAttributes(passive_fields)
            passive_lyr.updateFields()

            # Non-MPYY Layer 2: Proposed Commercial Areas (Accessibility Demo)
            comm_out_lyr = QgsVectorLayer(f"Polygon?crs={crs_auth}", "Onerilen_Ticari_Alanlar_Demo", "memory")
            comm_out_pr = comm_out_lyr.dataProvider()
            comm_fields = QgsFields()
            comm_fields.append(QgsField("kaynak_ada_id", _QVAR_INT))
            comm_fields.append(QgsField("parca_no", _QVAR_INT))
            comm_fields.append(QgsField("kullanim_turu", _QVAR_STRING))
            comm_fields.append(QgsField("alan_m2", _QVAR_DOUBLE))
            comm_fields.append(QgsField("en_yakin_ticari_yol_m", _QVAR_DOUBLE))
            comm_fields.append(QgsField("hedef_nufus_etki", _QVAR_INT))
            comm_fields.append(QgsField("planlama_gerekcesi", _QVAR_STRING))
            comm_fields.append(QgsField("yazar", _QVAR_STRING))
            comm_out_pr.addAttributes(comm_fields)
            comm_out_lyr.updateFields()

            vac_pts_lyr = QgsVectorLayer(f"Point?crs={crs_auth}", "MPYY_Bos_Alan_Agirlik_Merkezleri", "memory")
            vac_pts_pr = vac_pts_lyr.dataProvider()
            vac_pts_pr.addAttributes([
                QgsField("kaynak_ada_id", _QVAR_INT),
                QgsField("alan_m2", _QVAR_DOUBLE),
                QgsField("atanan_donatilar", _QVAR_STRING),
            ])
            vac_pts_lyr.updateFields()
            vac_pt_features = []

            remaining_deficit_pop = {}
            for cat, sp in specs.items():
                if sp["key_id"] == "konut":
                    continue
                cap_deficit = max(0.0, total_pop - existing_cap_by_type[cat])
                remaining_deficit_pop[cat] = max(unserved_pop_by_cat[cat], cap_deficit)

            newly_placed_points = {k: [] for k in specs.keys()}
            all_newly_placed_built_pts = []
            newly_placed_comm_pts = []
            allocated_summary = {k: {"count": 0, "area": 0.0, "served_pop": 0} for k in specs.keys()}
            non_mpyy_summary = {
                "pasif_yesil": {"count": 0, "area": 0.0},
                "ticari_demo": {"count": 0, "area": 0.0},
            }
            parcel_narrative_list = []
            out_alloc_features = []
            out_passive_features = []
            out_comm_features = []

            # Sector-level minimum spacing (m), max new facility quotas, and urban priority weights
            SECTOR_RULES = {
                "hastane": {"exist_r": 3500.0, "new_r": 5000.0, "max_new": 0 if any(len(fac_by_type[c]) > 0 for c, s in specs.items() if s["key_id"] == "hastane") else 1, "prio": 0.70, "ideal_max_lot": 12000.0},
                "ilkokul": {"exist_r": 490.0,  "new_r": 580.0,  "max_new": 4, "prio": 1.85, "ideal_max_lot": 7200.0},
                "ortaokul": {"exist_r": 920.0, "new_r": 1150.0, "max_new": 3, "prio": 1.35, "ideal_max_lot": 8200.0},
                "lise":    {"exist_r": 1800.0, "new_r": 2500.0, "max_new": 1, "prio": 1.00, "ideal_max_lot": 9000.0},
                "asm":     {"exist_r": 470.0,  "new_r": 560.0,  "max_new": 4, "prio": 1.40, "ideal_max_lot": 1950.0},
                "ibadet":  {"exist_r": 430.0,  "new_r": 850.0,  "max_new": 2, "prio": 0.90, "ideal_max_lot": 2900.0},
                "sosyal":  {"exist_r": 800.0,  "new_r": 1200.0, "max_new": 2, "prio": 1.05, "ideal_max_lot": 3800.0},
            }

            raw_vac_list = [
                pf for pf in vac_poly_lyr.getFeatures()
                if pf.geometry() and not pf.geometry().isEmpty() and pf.geometry().area() >= 50.0
            ]

            def _vac_sort_key(f):
                g = f.geometry()
                cpt = g.centroid().asPoint()
                # Prioritize blocks embedded in or adjacent to the residential blocks over isolated outlying blocks
                d_near_res = min((math.hypot(cpt.x() - r[1].x(), cpt.y() - r[1].y()) for r in res_feats), default=0.0)
                if d_near_res > 400.0:
                    prox_w = 0.05
                elif d_near_res <= 120.0:
                    prox_w = 1.35
                else:
                    prox_w = 1.0
                return g.area() * compute_polygon_shape_metrics(g)["rect_fill"] * prox_w

            vac_features_list = sorted(raw_vac_list, key=_vac_sort_key, reverse=True)
            total_vac = max(len(vac_features_list), 1)

            for idx_v, pf in enumerate(vac_features_list):
                if idx_v % 5 == 0:
                    pct = 65 + int(30 * (idx_v / total_vac))
                    self.progress.setValue(min(pct, 95))
                    QApplication.processEvents()

                pgeom = pf.geometry()
                poly_area = pgeom.area()
                block_metrics = compute_polygon_shape_metrics(pgeom)
                block_rect_fill = block_metrics["rect_fill"]
                block_min_dim = block_metrics["min_dim"]

                eval_pt = pgeom.centroid().asPoint()
                v_nid, v_snap = graph.snap_polygon_to_node(pgeom)
                vac_dist_map = graph.multi_source_dijkstra([eval_pt], max_cutoff=2800.0)

                # CASE A: Small / Narrow / Triangular Traffic Islands & Roadside Strips -> Non-MPYY Passive Green!
                is_passive_green_island = (
                    poly_area < 1500.0
                    or (block_rect_fill < 0.62 and poly_area < 3400.0)
                    or block_min_dim < 22.0
                    or block_metrics["aspect"] > 3.8
                )
                if is_passive_green_island:
                    f_pas = QgsFeature(passive_lyr.fields())
                    f_pas.setGeometry(pgeom)
                    f_pas["kaynak_ada_id"] = pf.id()
                    f_pas["parca_no"] = 1
                    f_pas["kullanim_turu"] = "Pasif Yeşil Alan (Tampon / Refüj Yeşili)"
                    f_pas["alan_m2"] = round(poly_area, 1)
                    f_pas["tampon_islevi"] = "Yol / Kavşak Görsel ve Ekolojik Tamponu (Aktif Oyun Alanı Yok)"
                    gerekce = (
                        f"Ada #{pf.id()} ({int(poly_area)} m², rect_fill={block_rect_fill:.2f}): Parsel büyüklüğü veya "
                        f"üçgen/dar refüj formu nedeniyle çocuk oyun alanı yerine MPYY dışı 'Pasif Yeşil Alan (Sade Tampon Yeşil)' olarak ayrılmıştır."
                    )
                    f_pas["planlama_gerekcesi"] = gerekce
                    f_pas["yazar"] = PLUGIN_AUTHOR
                    out_passive_features.append(f_pas)
                    non_mpyy_summary["pasif_yesil"]["count"] += 1
                    non_mpyy_summary["pasif_yesil"]["area"] += poly_area
                    parcel_narrative_list.append(gerekce)
                    continue

                iyi_olanlar = []
                aday_donatilar = []

                nearby_built_count = sum(
                    1 for bpt in all_newly_placed_built_pts
                    if math.hypot(eval_pt.x() - bpt.x(), eval_pt.y() - bpt.y()) <= 380.0
                )
                cluster_saturated = (nearby_built_count >= 3)

                is_triangular_medium_block = (block_rect_fill < 0.74 and poly_area < 8500.0)

                if not cluster_saturated and not is_triangular_medium_block:
                    for cat, sp in specs.items():
                        key_id = sp["key_id"]
                        if key_id in ("konut", "park"):
                            continue

                        srule = SECTOR_RULES.get(key_id, {
                            "exist_r": sp["euclid_r"],
                            "new_r": max(sp["euclid_r"] * 1.6, 800.0),
                            "max_new": 3,
                            "prio": 1.0,
                            "ideal_max_lot": sp["max_single"],
                        })

                        if allocated_summary[cat]["count"] >= srule["max_new"]:
                            iyi_olanlar.append(f"{cat} (Kota Tamam)")
                            continue

                        d_map = net_dist_maps[cat]
                        d_exist_road = (d_map[v_nid] + v_snap) if (v_nid is not None and v_nid in d_map) else float('inf')
                        if fac_by_type[cat]:
                            d_exist_bird = min(math.hypot(eval_pt.x() - it[1].x(), eval_pt.y() - it[1].y()) for it in fac_by_type[cat])
                        else:
                            d_exist_bird = float('inf')
                        d_to_existing = min(d_exist_road, d_exist_bird * 1.12)

                        d_to_newly_placed = float('inf')
                        for np_pt, np_nid, np_snap in newly_placed_points[cat]:
                            db = math.hypot(eval_pt.x() - np_pt.x(), eval_pt.y() - np_pt.y())
                            dr = (vac_dist_map[np_nid] + np_snap) if (np_nid is not None and np_nid in vac_dist_map) else db * 1.25
                            d_to_newly_placed = min(d_to_newly_placed, db, dr)

                        effective_d = min(d_to_existing, d_to_newly_placed)

                        # Check if a nearby existing facility is OVERLOADED (e.g. a 2,000 m² school with 5,000 students!)
                        relief_target = None
                        if key_id in ("ilkokul", "ortaokul", "asm", "ibadet", "sosyal"):
                            for ov_fac in overloaded_facilities.get(cat, ()):
                                if ov_fac["overflow_rem"] >= 450.0:
                                    db_ov = math.hypot(eval_pt.x() - ov_fac["pt"].x(), eval_pt.y() - ov_fac["pt"].y())
                                    if 180.0 <= db_ov <= min(srule["exist_r"] * 1.45, 780.0):
                                        relief_target = ov_fac
                                        break

                        covered_by_existing = (
                            (d_exist_bird <= srule["exist_r"] or d_exist_road <= sp["net_r"] * 1.04)
                            and relief_target is None
                        )
                        covered_by_new = (d_to_newly_placed < srule["new_r"])

                        if covered_by_existing or covered_by_new:
                            iyi_olanlar.append(f"{cat} ({int(effective_d)}m)")
                            continue

                        if poly_area < sp["min_area"]:
                            continue

                        newly_covered_pop = 0.0
                        net_limit = min(max(sp["net_r"], srule["exist_r"]) * 1.15, 950.0)
                        for node_entry in unserved_res_nodes[cat]:
                            if not node_entry[4]:
                                r_pt, r_pop, r_nid, r_snap, _ = node_entry
                                db_res = math.hypot(eval_pt.x() - r_pt.x(), eval_pt.y() - r_pt.y())
                                dr_res = (vac_dist_map[r_nid] + r_snap) if (r_nid is not None and r_nid in vac_dist_map) else db_res * 1.3
                                if min(db_res * 1.12, dr_res) <= net_limit:
                                    newly_covered_pop += r_pop

                        if relief_target is not None:
                            newly_covered_pop = max(newly_covered_pop, min(relief_target["overflow_rem"] * 0.75, sp["unit_cap"] * 0.85))

                        deficit_weight = remaining_deficit_pop[cat]
                        if newly_covered_pop <= 20.0 and deficit_weight <= 100.0:
                            continue

                        scale_factor = srule["prio"]
                        if poly_area >= 7000.0:
                            if key_id in ("ilkokul", "ortaokul", "lise"):
                                scale_factor *= 1.45
                            elif key_id == "asm":
                                scale_factor *= 1.10
                            elif key_id == "ibadet":
                                scale_factor *= 0.50
                        elif poly_area <= 4500.0:
                            if key_id in ("ibadet", "asm", "sosyal"):
                                scale_factor *= 1.25

                        if relief_target is not None:
                            scale_factor *= 1.35

                        diversity_factor = 1.0 / (1.0 + allocated_summary[cat]["count"] * 0.70)
                        score = (newly_covered_pop * 2.4 + deficit_weight * 0.45) * diversity_factor * scale_factor

                        if score > 25.0:
                            aday_donatilar.append({
                                "cat": cat,
                                "sp": sp,
                                "srule": srule,
                                "newly_covered_pop": newly_covered_pop,
                                "score": score,
                                "d_existing": effective_d,
                                "relief_target": relief_target,
                            })

                aday_donatilar.sort(key=lambda x: x["score"], reverse=True)
                iyi_str = ", ".join(iyi_olanlar[:4]) if iyi_olanlar else "Sektör Uygun"

                # Measure distance from this vacant block to existing & newly proposed Commercial Areas
                d_comm_road = (comm_dist_map[v_nid] + v_snap) if (v_nid is not None and v_nid in comm_dist_map) else float('inf')
                d_comm_bird = min((math.hypot(eval_pt.x() - cpt.x(), eval_pt.y() - cpt.y()) for cpt in comm_pts), default=float('inf'))
                d_new_comm = min((math.hypot(eval_pt.x() - ncpt.x(), eval_pt.y() - ncpt.y()) for ncpt in newly_placed_comm_pts), default=float('inf'))
                eff_comm_dist = min(d_comm_road, d_comm_bird * 1.18)

                # CASE B: Non-MPYY Commercial Area Proposal (Demo) when commercial accessibility is difficult (> 480 m)
                can_propose_commercial = (
                    self.chk_auto_split.isChecked()
                    and non_mpyy_summary["ticari_demo"]["count"] < 2
                    and eff_comm_dist > 480.0
                    and d_new_comm > 750.0
                    and block_rect_fill >= 0.78
                    and 2200.0 <= poly_area <= 6800.0
                    and (not aday_donatilar or (idx_v >= 7 and non_mpyy_summary["ticari_demo"]["count"] == 0))
                )
                if can_propose_commercial:
                    f_com = QgsFeature(comm_out_lyr.fields())
                    f_com.setGeometry(pgeom)
                    f_com["kaynak_ada_id"] = pf.id()
                    f_com["parca_no"] = 1
                    f_com["kullanim_turu"] = "Önerilen Ticari Alan (MPYY Dışı Erişim Demo)"
                    f_com["alan_m2"] = round(poly_area, 1)
                    f_com["en_yakin_ticari_yol_m"] = round(eff_comm_dist if eff_comm_dist < 1e7 else 999.0, 1)
                    f_com["hedef_nufus_etki"] = int(round(poly_area * 0.8))
                    gerekce_com = (
                        f"Ada #{pf.id()} ({int(poly_area)} m²): Bu gelişme sektöründe mevcut ticari alanlara yol ağı "
                        f"üzerinden erişim mesafesi yüksek ({int(min(eff_comm_dist, 1500))} m > 500 m eşik) olduğundan, "
                        f"mahalle ölçeğinde günlük ticaret erişilebilirliğini sağlamak üzere MPYY dışı öneri (demo) olarak 'Ticari Alan' ayrılmıştır."
                    )
                    f_com["planlama_gerekcesi"] = gerekce_com
                    f_com["yazar"] = PLUGIN_AUTHOR
                    out_comm_features.append(f_com)
                    newly_placed_comm_pts.append(eval_pt)
                    non_mpyy_summary["ticari_demo"]["count"] += 1
                    non_mpyy_summary["ticari_demo"]["area"] += poly_area
                    parcel_narrative_list.append(gerekce_com)
                    continue

                if not aday_donatilar:
                    if (
                        self.chk_auto_split.isChecked()
                        and res_growth_cat
                        and not is_triangular_medium_block
                        and block_rect_fill >= 0.78
                        and 3500.0 <= poly_area <= 19000.0
                        and nearby_built_count >= 1
                        and (idx_v % 2 == 1)
                    ):
                        fallback_cat = res_growth_cat
                        etki_val = int(round(poly_area / 35.0))
                        aciklama = (
                            f"Ada #{pf.id()} ({int(poly_area)} m²): Çevre sektörde okul, ibadet ve sağlık donatı "
                            f"kapasiteleri yeterli ({iyi_str}). Kompakt form korunarak '{fallback_cat}' olarak ayrıldı."
                        )
                    else:
                        fallback_cat = park_cat
                        etki_val = int(round(poly_area / max(specs[fallback_cat]["std_m2"], 1.0)))
                        aciklama = (
                            f"Ada #{pf.id()} ({int(poly_area)} m²): Sektör donatı kotaları karşılandığından veya "
                            f"ada formu (rect_fill={block_rect_fill:.2f}) açık yeşil alana uygun olduğundan '{fallback_cat}' olarak ayrıldı."
                        )

                    f_new = QgsFeature(alloc_lyr.fields())
                    f_new.setGeometry(pgeom)
                    f_new["kaynak_ada_id"] = pf.id()
                    f_new["parca_no"] = 1
                    f_new["onerilen_donati"] = fallback_cat
                    f_new["alan_m2"] = round(poly_area, 1)
                    f_new["hedef_nufus_etki"] = etki_val
                    f_new["yol_erisim_skoru"] = 100.0
                    f_new["mevcut_durum_ozeti"] = f"Yeterli: {iyi_str}"
                    f_new["planlama_aciklama_raporu"] = aciklama
                    f_new["yazar"] = PLUGIN_AUTHOR
                    out_alloc_features.append(f_new)
                    allocated_summary[fallback_cat]["count"] += 1
                    allocated_summary[fallback_cat]["area"] += poly_area
                    parcel_narrative_list.append(aciklama)

                    v_pt_f = QgsFeature(vac_pts_lyr.fields())
                    v_pt_f.setGeometry(QgsGeometry.fromPointXY(eval_pt))
                    v_pt_f["kaynak_ada_id"] = pf.id()
                    v_pt_f["alan_m2"] = round(poly_area, 1)
                    v_pt_f["atanan_donatilar"] = fallback_cat
                    vac_pt_features.append(v_pt_f)
                    continue

                # CASE C: Multi-Use Urban Block Subdivision (1 or 2 Built Facilities + Park Buffer + Optional Passive Green Strip)
                primary = aday_donatilar[0]
                p_cat = primary["cat"]
                p_sp = primary["sp"]
                p_srule = primary["srule"]

                ideal_lot_1 = min(p_sp["max_single"], p_srule.get("ideal_max_lot", p_sp["max_single"]))
                target_primary_area = max(p_sp["min_area"], min(poly_area * 0.48, ideal_lot_1))

                # Check if a 2nd complementary Built Facility (e.g. ASM or Sosyal separated by Park buffer!)
                # fits cleanly on this large block (poly_area >= 9,500 m², like Ada #2544 or Ada #2541).
                # Never pair two schools on the same block — pair a school with a compact neighborhood facility (ASM/Sosyal/İbadet)!
                secondary = None
                target_second_area = 0.0
                if self.chk_auto_split.isChecked() and poly_area >= 9500.0 and len(aday_donatilar) >= 2:
                    for cand2 in aday_donatilar[1:]:
                        c2_key = cand2["sp"]["key_id"]
                        if c2_key == p_sp["key_id"]:
                            continue
                        if c2_key in ("asm", "sosyal", "ibadet"):
                            ideal_lot_2 = min(cand2["sp"]["max_single"], cand2["srule"].get("ideal_max_lot", 2200.0))
                            cand2_area = max(cand2["sp"]["min_area"], min(poly_area * 0.18, ideal_lot_2))
                            if (target_primary_area + cand2_area + 2000.0) <= poly_area * 0.78:
                                secondary = cand2
                                target_second_area = cand2_area
                                break

                # Check if this is a large highway-edge tapered block (like Ada #2544: 33,943 m², rect_fill=0.67)
                # that should carve an outer Passive Green Buffer strip ('Sade Tampon Görevli Yeşil')
                carve_passive = (
                    self.chk_auto_split.isChecked()
                    and poly_area >= 26000.0
                    and block_rect_fill < 0.72
                )

                rem_area = poly_area - target_primary_area - target_second_area
                park_min = max(specs[park_cat]["min_area"] if park_cat in specs else 1000.0, 1200.0)

                should_split = (
                    self.chk_auto_split.isChecked()
                    and p_cat != park_cat
                    and (
                        secondary is not None
                        or carve_passive
                        or (rem_area >= park_min and poly_area > ideal_lot_1 * 1.15)
                        or (block_rect_fill < 0.74 and rem_area >= 900.0)
                    )
                )

                if should_split:
                    multi_res = subdivide_block_multi_use(
                        pgeom,
                        built1_area=target_primary_area,
                        built2_area=target_second_area if secondary is not None else 0.0,
                        carve_passive_strip=carve_passive,
                        passive_area_ratio=0.28,
                        neighborhood_center_pt=res_center_pt,
                    )

                    # 1. If a Passive Green Buffer strip was carved off the highway side, add to Non-MPYY Passive Green layer
                    if multi_res["passive"] is not None and not multi_res["passive"].isEmpty():
                        pas_geom = multi_res["passive"]
                        pas_area = pas_geom.area()
                        f_pas = QgsFeature(passive_lyr.fields())
                        f_pas.setGeometry(pas_geom)
                        f_pas["kaynak_ada_id"] = pf.id()
                        f_pas["parca_no"] = 1
                        f_pas["kullanim_turu"] = "Pasif Yeşil Alan (Sade Tampon Görevli Yeşil)"
                        f_pas["alan_m2"] = round(pas_area, 1)
                        f_pas["tampon_islevi"] = "Ana Arter / Karayolu Gürültü ve Güvenlik Tampon Şeridi"
                        f_pas["planlama_gerekcesi"] = (
                            f"Ada #{pf.id()} ({int(poly_area)} m²): Batı/arter cephesindeki daralan şerit ({int(pas_area)} m²), "
                            f"okul ve sağlık tesislerini ana yol trafiğinden koruyan MPYY dışı 'Pasif Yeşil Alan (Tampon Yeşil)' olarak ayrılmıştır."
                        )
                        f_pas["yazar"] = PLUGIN_AUTHOR
                        out_passive_features.append(f_pas)
                        non_mpyy_summary["pasif_yesil"]["count"] += 1
                        non_mpyy_summary["pasif_yesil"]["area"] += pas_area

                    alloc_parts = []
                    if multi_res["built1"] is not None and not multi_res["built1"].isEmpty():
                        alloc_parts.append((p_cat, multi_res["built1"], primary.get("relief_target")))
                    if multi_res["park"] is not None and not multi_res["park"].isEmpty():
                        alloc_parts.append((park_cat, multi_res["park"], None))
                    if secondary is not None and multi_res["built2"] is not None and not multi_res["built2"].isEmpty():
                        alloc_parts.append((secondary["cat"], multi_res["built2"], secondary.get("relief_target")))

                    parca_detaylari = []
                    for idx_s, (s_cat, s_geom, _) in enumerate(alloc_parts):
                        s_area = s_geom.area()
                        s_m = compute_polygon_shape_metrics(s_geom)
                        parca_detaylari.append(
                            f"Parsel {idx_s+1}: {int(s_area)} m² '{s_cat}' (rect_fill={s_m['rect_fill']:.2f})"
                        )
                    if multi_res["passive"] is not None and not multi_res["passive"].isEmpty():
                        parca_detaylari.append(
                            f"MPYY Dışı Tampon: {int(multi_res['passive'].area())} m² 'Pasif Yeşil Alan'"
                        )

                    relief_note = ""
                    if primary.get("relief_target") is not None:
                        rt = primary["relief_target"]
                        relief_note = (
                            f" [Kapasite Rahatlatma: Mevcut #{rt['fid']} ({int(rt['area'])} m²) donatısındaki "
                            f"{int(rt['load'])} kişilik aşırı yükü (Kapasite: {int(rt['cap'])}) rahatlatır]"
                        )

                    ortak_aciklama = (
                        f"Ada #{pf.id()} (Toplam {int(poly_area)} m²): Cadde cephesine dik ortogonal ifraz ile "
                        + " + ".join(parca_detaylari)
                        + f" olarak dengeli biçimde bölünmüştür.{relief_note}"
                    )

                    for idx_s, (s_cat, s_geom, s_relief) in enumerate(alloc_parts):
                        s_sp = specs[s_cat]
                        s_area = s_geom.area()
                        s_etki = int(s_sp["unit_cap"]) if s_cat != park_cat else int(round(s_area / 10.0))
                        s_pt = s_geom.centroid().asPoint()
                        s_nid, s_snap = graph.snap_polygon_to_node(s_geom)

                        f_new = QgsFeature(alloc_lyr.fields())
                        f_new.setGeometry(s_geom)
                        f_new["kaynak_ada_id"] = pf.id()
                        f_new["parca_no"] = idx_s + 1
                        f_new["onerilen_donati"] = s_cat
                        f_new["alan_m2"] = round(s_area, 1)
                        f_new["hedef_nufus_etki"] = s_etki
                        f_new["yol_erisim_skoru"] = round(primary["score"], 1)
                        f_new["mevcut_durum_ozeti"] = (
                            f"Kapasite Rahatlatma (#{s_relief['fid']})" if s_relief else f"Mevcut: {iyi_str}"
                        )
                        f_new["planlama_aciklama_raporu"] = ortak_aciklama
                        f_new["yazar"] = PLUGIN_AUTHOR
                        out_alloc_features.append(f_new)

                        self._register_placed_facility(
                            s_cat, s_pt, s_nid, s_snap, vac_dist_map, s_sp["net_r"],
                            s_etki, s_area, newly_placed_points, existing_cap_by_type,
                            remaining_deficit_pop, unserved_res_nodes, allocated_summary,
                            relief_target=s_relief,
                        )
                        if s_cat != park_cat:
                            all_newly_placed_built_pts.append(s_pt)

                    parcel_narrative_list.append(ortak_aciklama)

                    v_pt_f = QgsFeature(vac_pts_lyr.fields())
                    v_pt_f.setGeometry(QgsGeometry.fromPointXY(eval_pt))
                    v_pt_f["kaynak_ada_id"] = pf.id()
                    v_pt_f["alan_m2"] = round(poly_area, 1)
                    v_pt_f["atanan_donatilar"] = " + ".join(c for c, _, _ in alloc_parts)
                    vac_pt_features.append(v_pt_f)
                else:
                    if block_rect_fill < 0.70:
                        f_new = QgsFeature(alloc_lyr.fields())
                        f_new.setGeometry(pgeom)
                        f_new["kaynak_ada_id"] = pf.id()
                        f_new["parca_no"] = 1
                        f_new["onerilen_donati"] = park_cat
                        f_new["alan_m2"] = round(poly_area, 1)
                        f_new["hedef_nufus_etki"] = int(round(poly_area / 10.0))
                        f_new["yol_erisim_skoru"] = 100.0
                        f_new["mevcut_durum_ozeti"] = "Üçgen Form -> Park"
                        f_new["planlama_aciklama_raporu"] = (
                            f"Ada #{pf.id()} ({int(poly_area)} m²): Üçgen/düzensiz parsel formu (rect_fill={block_rect_fill:.2f}) "
                            f"nedeniyle yapılı bina yerine '{park_cat}' olarak ayrıldı."
                        )
                        f_new["yazar"] = PLUGIN_AUTHOR
                        out_alloc_features.append(f_new)
                        allocated_summary[park_cat]["count"] += 1
                        allocated_summary[park_cat]["area"] += poly_area
                        continue

                    etki_nufus = int(max(primary["newly_covered_pop"], p_sp["unit_cap"]))
                    rt = primary.get("relief_target")
                    relief_str = (
                        f" Mevcut #{rt['fid']} ({int(rt['area'])} m²) binasındaki {int(rt['load'])} kişilik kapasite aşımını rahatlatır."
                        if rt else ""
                    )
                    aciklama = (
                        f"Ada #{pf.id()} ({int(poly_area)} m², rect_fill={block_rect_fill:.2f}): MPYY Ek-2 asgari birim "
                        f"alanını ({int(p_sp['min_area'])} m²) kompakt dörtgen formla karşıladığından doğrudan '{p_cat}' "
                        f"(kapasite: {int(p_sp['unit_cap'])} kişi) olarak atandı.{relief_str}"
                    )
                    f_new = QgsFeature(alloc_lyr.fields())
                    f_new.setGeometry(pgeom)
                    f_new["kaynak_ada_id"] = pf.id()
                    f_new["parca_no"] = 1
                    f_new["onerilen_donati"] = p_cat
                    f_new["alan_m2"] = round(poly_area, 1)
                    f_new["hedef_nufus_etki"] = etki_nufus
                    f_new["yol_erisim_skoru"] = round(primary["score"], 1)
                    f_new["mevcut_durum_ozeti"] = f"Kapasite Rahatlatma (#{rt['fid']})" if rt else f"Mevcut: {iyi_str}"
                    f_new["planlama_aciklama_raporu"] = aciklama
                    f_new["yazar"] = PLUGIN_AUTHOR
                    out_alloc_features.append(f_new)

                    self._register_placed_facility(
                        p_cat, eval_pt, v_nid, v_snap, vac_dist_map, p_sp["net_r"],
                        etki_nufus, poly_area, newly_placed_points, existing_cap_by_type,
                        remaining_deficit_pop, unserved_res_nodes, allocated_summary,
                        relief_target=rt,
                    )
                    all_newly_placed_built_pts.append(eval_pt)
                    parcel_narrative_list.append(aciklama)

                    v_pt_f = QgsFeature(vac_pts_lyr.fields())
                    v_pt_f.setGeometry(QgsGeometry.fromPointXY(eval_pt))
                    v_pt_f["kaynak_ada_id"] = pf.id()
                    v_pt_f["alan_m2"] = round(poly_area, 1)
                    v_pt_f["atanan_donatilar"] = p_cat
                    vac_pt_features.append(v_pt_f)

            alloc_pr.addFeatures(out_alloc_features)
            alloc_lyr.updateExtents()
            passive_pr.addFeatures(out_passive_features)
            passive_lyr.updateExtents()
            comm_out_pr.addFeatures(out_comm_features)
            comm_out_lyr.updateExtents()
            vac_pts_pr.addFeatures(vac_pt_features)
            vac_pts_lyr.updateExtents()

            for lyr_obj in (alloc_lyr, passive_lyr, comm_out_lyr, res_out_lyr, fac_pts_lyr, vac_pts_lyr):
                lyr_obj.setAbstract(f"Generated by MPYY Urban Facility Optimization Plugin — Author: {PLUGIN_AUTHOR}")

            self.apply_polygon_symbology(alloc_lyr, specs)
            self.apply_non_mpyy_symbology(passive_lyr, comm_out_lyr)

            self._add_layers_to_grouped_tree(
                alloc_lyr, passive_lyr, comm_out_lyr,
                res_out_lyr, fac_pts_lyr, vac_pts_lyr
            )

            html_report = self.build_html_report(
                total_pop, specs, fac_by_type, existing_cap_by_type,
                unserved_pop_by_cat, overflow_pop_by_cat, bird_ok_road_fail_count,
                allocated_summary, non_mpyy_summary, parcel_narrative_list
            )
            self.txt_report.setHtml(html_report)
            self.tabs.setCurrentIndex(1)
            self.progress.setValue(100)

            QMessageBox.information(self, t["done_title"], t["done_msg"])
        finally:
            self.btn_run.setEnabled(True)

    def _register_placed_facility(
        self, cat, pt, nid, snap_d, vac_dist_map, net_limit,
        added_cap, added_area, newly_placed_points, existing_cap_by_type,
        remaining_deficit_pop, unserved_res_nodes, allocated_summary,
        relief_target=None,
    ):
        newly_placed_points[cat].append((pt, nid, snap_d))
        existing_cap_by_type[cat] += added_cap
        remaining_deficit_pop[cat] = max(0.0, remaining_deficit_pop[cat] - added_cap)
        allocated_summary[cat]["count"] += 1
        allocated_summary[cat]["area"] += added_area
        allocated_summary[cat]["served_pop"] += added_cap

        if relief_target is not None:
            relief_target["overflow_rem"] = max(0.0, relief_target["overflow_rem"] - added_cap)

        for node_entry in unserved_res_nodes[cat]:
            if not node_entry[4]:
                r_nid, r_snap = node_entry[2], node_entry[3]
                if r_nid is not None and r_nid in vac_dist_map:
                    if (vac_dist_map[r_nid] + r_snap) <= net_limit * 1.15:
                        node_entry[4] = True

    def _add_layers_to_grouped_tree(
        self, alloc_lyr, passive_lyr, comm_out_lyr, res_out_lyr, fac_pts_lyr, vac_pts_lyr
    ):
        proj = QgsProject.instance()
        root = proj.layerTreeRoot()

        grp_mpyy_name = "MPYY_EK2_Sosyal_ve_Teknik_Donati_Alanlari"
        grp_non_mpyy_name = "MPYY_Disi_Tamamlayici_Alanlar (Pasif Yesil & Ticari Demo)"

        # Clean up previous groups of the same name to prevent duplicate clutter
        for gname in (grp_mpyy_name, grp_non_mpyy_name):
            old_grp = root.findGroup(gname)
            if old_grp is not None:
                root.removeChildNode(old_grp)

        grp_mpyy = root.insertGroup(0, grp_mpyy_name)
        grp_non_mpyy = root.insertGroup(1, grp_non_mpyy_name)

        proj.addMapLayer(alloc_lyr, False)
        grp_mpyy.addLayer(alloc_lyr)

        if self.chk_show_centroids.isChecked():
            for c_lyr in (res_out_lyr, fac_pts_lyr, vac_pts_lyr):
                proj.addMapLayer(c_lyr, False)
                grp_mpyy.addLayer(c_lyr)

        if passive_lyr.featureCount() > 0:
            proj.addMapLayer(passive_lyr, False)
            grp_non_mpyy.addLayer(passive_lyr)

        if comm_out_lyr.featureCount() > 0:
            proj.addMapLayer(comm_out_lyr, False)
            grp_non_mpyy.addLayer(comm_out_lyr)

    def apply_polygon_symbology(self, layer, specs):
        categories = []
        used_names = set()
        for feat in layer.getFeatures():
            val = feat["onerilen_donati"]
            if val and val not in used_names:
                used_names.add(val)
                col_hex = specs[val]["color"] if val in specs else "#334155"
                sym = QgsFillSymbol.createSimple({
                    'color': col_hex,
                    'outline_color': '#ffffff',
                    'outline_width': '0.55'
                })
                sym.setOpacity(0.88)
                cat = QgsRendererCategory(val, sym, val)
                categories.append(cat)
        if categories:
            renderer = QgsCategorizedSymbolRenderer("onerilen_donati", categories)
            layer.setRenderer(renderer)
            layer.triggerRepaint()

    def apply_non_mpyy_symbology(self, passive_lyr, comm_out_lyr):
        # Passive Green: Distinctive Olive/Forest Green Buffer style (#65a30d with dark green outline)
        pas_sym = QgsFillSymbol.createSimple({
            'color': '#65a30d',
            'style': 'dense4',
            'outline_color': '#14532d',
            'outline_width': '0.60'
        })
        pas_sym.setOpacity(0.85)
        passive_lyr.setRenderer(QgsCategorizedSymbolRenderer(
            "kullanim_turu",
            [
                QgsRendererCategory(
                    "Pasif Yeşil Alan (Sade Tampon Görevli Yeşil)",
                    pas_sym.clone(),
                    "Pasif Yeşil Alan (Sade Tampon Görevli Yeşil)"
                ),
                QgsRendererCategory(
                    "Pasif Yeşil Alan (Tampon / Refüj Yeşili)",
                    pas_sym.clone(),
                    "Pasif Yeşil Alan (Tampon / Refüj Yeşili)"
                ),
            ]
        ))
        passive_lyr.triggerRepaint()

        # Commercial Demo: Distinctive Coral/Crimson Commercial style (#e11d48)
        com_sym = QgsFillSymbol.createSimple({
            'color': '#e11d48',
            'outline_color': '#881337',
            'outline_width': '0.70'
        })
        com_sym.setOpacity(0.88)
        comm_out_lyr.setRenderer(QgsCategorizedSymbolRenderer(
            "kullanim_turu",
            [
                QgsRendererCategory(
                    "Önerilen Ticari Alan (MPYY Dışı Erişim Demo)",
                    com_sym,
                    "Önerilen Ticari Alan (MPYY Dışı Erişim Demo)"
                )
            ]
        ))
        comm_out_lyr.triggerRepaint()

    def build_html_report(
        self, total_pop, specs, fac_by_type, existing_cap_by_type,
        unserved_pop_by_cat, overflow_pop_by_cat, bird_ok_road_fail_count,
        allocated_summary, non_mpyy_summary, parcel_narrative_list
    ):
        rows_html = ""
        for cat, sp in specs.items():
            if sp["key_id"] == "konut":
                continue
            mevcut_adet = len(fac_by_type[cat])
            en_az_m2 = int(sp["min_area"])
            erismeyen_nufus = int(unserved_pop_by_cat[cat])
            kap_asim_nufus = int(overflow_pop_by_cat.get(cat, 0.0))
            kus_var_yol_yok = bird_ok_road_fail_count[cat]
            yeni_adet = allocated_summary[cat]["count"]
            yeni_alan = int(allocated_summary[cat]["area"])
            toplam_kap = int(existing_cap_by_type[cat])

            rows_html += f"""
            <tr>
                <td><span style='display:inline-block;width:12px;height:12px;background:{sp['color']};margin-right:6px;border-radius:2px;'></span><b>{cat}</b></td>
                <td align='center'>{int(sp['euclid_r'])} m / {int(sp['net_r'])} m</td>
                <td align='center' style='color:#1d4ed8; font-weight:bold;'>EK-2 Asgari: {en_az_m2:,} m²</td>
                <td align='center'>{mevcut_adet}</td>
                <td align='center' style='color:#d97706; font-weight:bold;'>{kus_var_yol_yok}</td>
                <td align='center' style='color:#dc2626; font-weight:bold;'>{kap_asim_nufus:,} kişi</td>
                <td align='center'>{erismeyen_nufus:,} kişi</td>
                <td align='center' style='background-color:#ecfdf5;'><b>+{yeni_adet} parsel ({yeni_alan:,} m²)</b></td>
                <td align='center'><b>{toplam_kap:,} kişi</b></td>
            </tr>
            """

        non_mpyy_html = f"""
        <table border='1' cellspacing='0' cellpadding='6' width='100%' style='border-collapse:collapse; font-size:12px; margin-top:10px;'>
            <tr style='background-color:#14532d; color:white;'>
                <th>MPYY Dışı Tamamlayıcı Katman (Ayrı Grup)</th>
                <th>Önerilen Parsel Sayısı</th>
                <th>Toplam Alan (m²)</th>
                <th>Planlama İşlevi ve Gerekçesi</th>
            </tr>
            <tr>
                <td><b>Pasif Yeşil Alanlar (Sade Tampon / Refüj Yeşili)</b></td>
                <td align='center'><b>{non_mpyy_summary['pasif_yesil']['count']} parsel</b></td>
                <td align='center'><b>{int(non_mpyy_summary['pasif_yesil']['area']):,} m²</b></td>
                <td>Çocuk oyun alanı barındırmayan; ana yol/kavşak kenarlarında gürültü, güvenlik ve görsel tampon görevi yapan yeşil alanlar.</td>
            </tr>
            <tr>
                <td><b>Önerilen Ticari Alanlar (Erişim Demo)</b></td>
                <td align='center'><b>{non_mpyy_summary['ticari_demo']['count']} parsel</b></td>
                <td align='center'><b>{int(non_mpyy_summary['ticari_demo']['area']):,} m²</b></td>
                <td>Mevcut ticari alanlara yol ağı üzerinden erişimin zor (&gt;500 m) olduğu gelişme sektörlerinde günlük ticaret erişimi için önerilen demo ticari alanlar.</td>
            </tr>
        </table>
        """

        narratives_html = "".join([f"<li style='margin-bottom:8px;'>{n}</li>" for n in parcel_narrative_list])

        return f"""
        <html>
        <body style='font-family: Segoe UI, Arial, sans-serif; color: #1e293b;'>
            <h2 style='color:#1e3a8a; border-bottom: 2px solid #1e3a8a; padding-bottom:6px;'>
                MPYY EK-2 DONATI OPTİMİZASYONU, KAPASİTE RAHATLATMA VE ÇOKLU İFRAZ RAPORU
            </h2>
            <p>
                <b>Yazar / Geliştirici (Author):</b> <span style='color:#1d4ed8; font-weight:bold;'>{PLUGIN_AUTHOR}</span><br>
                <b>Planlama Nüfusu:</b> {int(total_pop):,} Kişi<br>
                <b>Metodoloji Özeti:</b>
                (1) Her konut adasının yol ağı üzerinden erişimi ve mevcut donatıların gerçek parsel büyüklüğüne dayalı kapasite yükü ($D_j / C_j$) denetlenmiştir;
                küçük parselde aşırı yük taşıyan mevcut okulları rahatlatmak üzere yeni donatılar atanmıştır.
                (2) Büyük imar adalarında (ör. Ada #2544) iki yapılı donatı (İlkokul + ASM) arasına Çocuk Bahçesi & Park tamponu yerleştirilmiş,
                ana yol cephesindeki daralan şeritler ise MPYY dışı grupta <b>Pasif Yeşil Alan</b> olarak ayrılmıştır.
            </p>
            <table border='1' cellspacing='0' cellpadding='6' width='100%' style='border-collapse:collapse; font-size:12px;'>
                <tr style='background-color:#0f172a; color:white;'>
                    <th>Donatı Türü</th>
                    <th>Kuş Uçuşu / Yol Çapı</th>
                    <th>EK-2 Asgari Alan</th>
                    <th>Mevcut Bina</th>
                    <th>Kuş Uçuşu VAR / Yol YOK</th>
                    <th>Mevcut Kapasite Aşımı Yükü</th>
                    <th>Toplam Açık / Aşım Nüfusu</th>
                    <th>Yeni Atanan (Kompakt İfraz)</th>
                    <th>Yeni Toplam Kapasite</th>
                </tr>
                {rows_html}
            </table>
            <h3 style='margin-top:16px; color:#14532d;'>MPYY Dışı Tamamlayıcı Planlama Katmanları (Pasif Yeşil & Ticari Demo)</h3>
            {non_mpyy_html}
            <h3 style='margin-top:18px;'>İmar Adaları Çoklu İfraz, Kapasite Rahatlatma ve Atama Açıklamaları</h3>
            <ul style='font-size:13px; line-height:1.5;'>
                {narratives_html}
            </ul>
        </body>
        </html>
        """

    def create_demo_layers(self):
        crs = "EPSG:5253"
        base_x, base_y = 512000.0, 4254000.0

        net_lyr = QgsVectorLayer(f"LineString?crs={crs}", "Prepared_network_yol", "memory")
        net_pr = net_lyr.dataProvider()
        net_feats = []
        for y_off in [0, 300, 600, 900, 1200]:
            for x_off in [0, 300, 600, 900]:
                if y_off == 300 and x_off == 300:
                    continue
                f = QgsFeature()
                f.setGeometry(QgsGeometry.fromPolylineXY([
                    QgsPointXY(base_x + x_off, base_y + y_off),
                    QgsPointXY(base_x + x_off + 300, base_y + y_off)
                ]))
                net_feats.append(f)

        for x_off in [0, 300, 600, 900, 1200]:
            for y_off in [0, 300, 600, 900]:
                f = QgsFeature()
                f.setGeometry(QgsGeometry.fromPolylineXY([
                    QgsPointXY(base_x + x_off, base_y + y_off),
                    QgsPointXY(base_x + x_off, base_y + y_off + 300)
                ]))
                net_feats.append(f)
        net_pr.addFeatures(net_feats)
        net_lyr.updateExtents()

        def make_rect_poly(x, y, w, h):
            pts = [
                QgsPointXY(x, y),
                QgsPointXY(x + w, y),
                QgsPointXY(x + w, y + h),
                QgsPointXY(x, y + h),
                QgsPointXY(x, y)
            ]
            return QgsGeometry.fromPolygonXY([pts])

        demo_fac_layers = [
            ("mevcut_ilkokul", [(base_x + 250, base_y + 280, 45, 42)]),  # ~1,890 m2 small overloaded school
            ("mevcut_lise", [(base_x + 580, base_y + 880, 80, 80)]),
            ("mevcut_Ticari", [(base_x + 150, base_y + 150, 40, 35)]),
        ]
        for lyr_name, boxes in demo_fac_layers:
            fl = QgsVectorLayer(f"Polygon?crs={crs}", lyr_name, "memory")
            fpr = fl.dataProvider()
            feats = []
            for bx, by, bw, bh in boxes:
                ff = QgsFeature()
                ff.setGeometry(make_rect_poly(bx, by, bw, bh))
                feats.append(ff)
            fpr.addFeatures(feats)
            fl.updateExtents()
            QgsProject.instance().addMapLayer(fl)

        res_lyr = QgsVectorLayer(f"Polygon?crs={crs}", "mevcut_konut_adalari", "memory")
        res_pr = res_lyr.dataProvider()
        res_boxes = [
            (base_x + 110, base_y + 110, 85, 80),
            (base_x + 590, base_y + 270, 75, 70),
            (base_x + 410, base_y + 410, 80, 80),
            (base_x + 710, base_y + 410, 90, 85),
            (base_x + 110, base_y + 710, 85, 75),
            (base_x + 710, base_y + 710, 95, 85),
            (base_x + 1010, base_y + 410, 85, 80),
        ]
        res_feats = []
        for bx, by, bw, bh in res_boxes:
            rf = QgsFeature()
            rf.setGeometry(make_rect_poly(bx, by, bw, bh))
            res_feats.append(rf)
        res_pr.addFeatures(res_feats)
        res_lyr.updateExtents()

        vac_poly_lyr = QgsVectorLayer(f"Polygon?crs={crs}", "mevcut_bos1", "memory")
        vp_pr = vac_poly_lyr.dataProvider()
        vac_boxes = [
            (base_x + 560, base_y + 160, 120, 95),
            (base_x + 560, base_y + 260, 80, 65),
            (base_x + 260, base_y + 560, 35, 25),
            (base_x + 860, base_y + 720, 75, 55),
        ]
        poly_feats = []
        for bx, by, bw, bh in vac_boxes:
            pf = QgsFeature()
            pf.setGeometry(make_rect_poly(bx, by, bw, bh))
            poly_feats.append(pf)
        vp_pr.addFeatures(poly_feats)
        vac_poly_lyr.updateExtents()

        QgsProject.instance().addMapLayer(net_lyr)
        QgsProject.instance().addMapLayer(vac_poly_lyr)
        QgsProject.instance().addMapLayer(res_lyr)

        self.populate_layers()


MPYYDialog = MPYYDonatiDialog
