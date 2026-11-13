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
    QProgressBar, QCheckBox, QApplication, QFrame, QScrollArea
)
from qgis.PyQt.QtCore import Qt, QVariant, QSize, QPointF, QRectF
try:
    from qgis.PyQt.QtCore import QMetaType
except ImportError:
    QMetaType = None
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
    PlanActualDiffEngine,
    ResidentialGrowthNetworkEvaluator,
    AdaptiveAmenityWeightingEngine,
)

# Qt5 & Qt6 dual compatibility field types and scoped enum helpers
if QMetaType is not None and hasattr(QMetaType, "Type"):
    _QVAR_INT = QMetaType.Type.Int
    _QVAR_DOUBLE = QMetaType.Type.Double
    _QVAR_STRING = QMetaType.Type.QString
else:
    _QVAR_INT = getattr(QVariant, "Int", 2)
    _QVAR_DOUBLE = getattr(QVariant, "Double", 6)
    _QVAR_STRING = getattr(QVariant, "String", 10)

_KEEP_ASPECT = getattr(getattr(Qt, "AspectRatioMode", Qt), "KeepAspectRatio", Qt.KeepAspectRatio if hasattr(Qt, "KeepAspectRatio") else 1)
_SMOOTH_XFORM = getattr(getattr(Qt, "TransformationMode", Qt), "SmoothTransformation", Qt.SmoothTransformation if hasattr(Qt, "SmoothTransformation") else 1)
_ALIGN_CENTER = getattr(getattr(Qt, "AlignmentFlag", Qt), "AlignCenter", getattr(Qt, "AlignCenter", 0x0084))
_ALIGN_RIGHT_VCENTER = (
    getattr(getattr(Qt, "AlignmentFlag", Qt), "AlignRight", getattr(Qt, "AlignRight", 0x0002))
    | getattr(getattr(Qt, "AlignmentFlag", Qt), "AlignVCenter", getattr(Qt, "AlignVCenter", 0x0080))
)
_USER_ROLE = getattr(getattr(Qt, "ItemDataRole", Qt), "UserRole", getattr(Qt, "UserRole", 0x0100))
_RESIZE_INTERACTIVE = getattr(getattr(QHeaderView, "ResizeMode", QHeaderView), "Interactive", 0)
_RESIZE_STRETCH = getattr(getattr(QHeaderView, "ResizeMode", QHeaderView), "Stretch", 1)
_FRAME_NO_FRAME = getattr(getattr(QFrame, "Shape", QFrame), "NoFrame", 0)
_POLY_GEOM = getattr(getattr(QgsWkbTypes, "GeometryType", QgsWkbTypes), "PolygonGeometry", 2)
_LINE_GEOM = getattr(getattr(QgsWkbTypes, "GeometryType", QgsWkbTypes), "LineGeometry", 1)
_POINT_GEOM = getattr(getattr(QgsWkbTypes, "GeometryType", QgsWkbTypes), "PointGeometry", 0)
_BOLD_WEIGHT = getattr(getattr(QFont, "Weight", QFont), "Bold", 75)
_DEMI_WEIGHT = getattr(getattr(QFont, "Weight", QFont), "DemiBold", 63)

PLUGIN_AUTHOR = "Baran Adsuna"

DEFAULT_MPYY_FACILITIES = [
    ("ilkokul", "İlkokul (EK-2: 5000-8000 m²)", "Primary School (5000-8000 m²)", "小学 (5000-8000 m²)", "Escuela Primaria (5000-8000 m²)", 500.0, 500.0, 2.0, 5000.0, 8000.0, 2500, "#38bdf8", ["ilkokul", "ilk_okul", "primary"]),
    ("ortaokul", "Ortaokul (EK-2: 6000-10000 m²)", "Middle School (6000-10000 m²)", "初中 (6000-10000 m²)", "Escuela Secundaria (6000-10000 m²)", 1000.0, 1000.0, 2.0, 6000.0, 10000.0, 3500, "#1d4ed8", ["ortaokul", "orta_okul", "middle"]),
    ("lise", "Gündüzlü Lise (EK-2: 6000-10000 m²)", "Day High School (6000-10000 m²)", "日制高中 (6000-10000 m²)", "Preparatoria Diurna (6000-10000 m²)", 2500.0, 2500.0, 2.0, 6000.0, 10000.0, 5000, "#8b5cf6", ["lise", "high"]),
    ("anaokulu", "Anaokulu / Kreş (EK-2: 1500-2000 m²)", "Kindergarten / Nursery (1500-2000 m²)", "幼儿园 / 托儿所 (1500-2000 m²)", "Jardín de Infantes (1500-2000 m²)", 500.0, 500.0, 0.50, 1500.0, 2500.0, 1500, "#ec4899", ["anaokulu", "kres", "kinder", "nursery"]),
    ("asm", "Aile Sağlığı Merkezi (EK-2: 750-2000 m²)", "Family Health Center (750-2000 m²)", "社区卫生服务中心 (750-2000 m²)", "Centro de Salud Familiar (750-2000 m²)", 500.0, 500.0, 0.75, 750.0, 2000.0, 5000, "#ff8a8a", ["asm", "aile_sagligi", "saglik_ocagi"]),
    ("hastane", "Devlet Hastanesi (EK-2: 1.5 m²/kişi)", "State Hospital (1.5 m²/cap)", "国立医院 (1.5 m²/人)", "Hospital Estatal (1.5 m²/pers)", 2500.0, 2500.0, 1.50, 5000.0, 15000.0, 15000, "#5c0000", ["hastane", "saglik", "hospital"]),
    ("ibadet", "Orta İbadet Yeri (EK-2: 2500 m²)", "Place of Worship (2500 m²)", "宗教场所 (2500 m²)", "Lugar de Culto (2500 m²)", 400.0, 400.0, 0.50, 2500.0, 5000.0, 3500, "#f59e0b", ["ibadet", "cami", "mescit", "dini"]),
    ("park", "Çocuk Bahçesi & Park (EK-2: 10 m²/kişi)", "Park & Playground (10 m²/cap)", "公园与儿童乐园 (10 m²/人)", "Parque y Juegos (10 m²/pers)", 500.0, 500.0, 10.0, 1000.0, 25000.0, 3000, "#10b981", ["park", "yesil", "cocuk"]),
    ("sosyal", "Sosyal ve Kültürel Tesis (EK-2)", "Social & Cultural Facility", "社会与文化设施", "Instalación Social y Cultural", 1000.0, 1000.0, 1.25, 1500.0, 6000.0, 4000, "#0d9488", ["sosyal", "kulturel", "kultur"]),
]

TRANSLATIONS = {
    "tr": {
        "win_title": f"MPYY Donatı Erişilebilirlik, Kapasite & İfraz Sistemi — Yazar: {PLUGIN_AUTHOR}",
        "banner_title": "MEKÂNSAL PLANLAR YAPIM YÖNETMELİĞİ (MPYY) EK-2 STANDARTLARI & AKILLI OPTİMİZASYON",
        "banner_sub": f"Yol Ağı P-Lokasyon • İhtiyaç Ağırlığı & Stokastik Denge • Çoklu İfraz + Park Tamponu • Yazar: {PLUGIN_AUTHOR}",
        "dev_label": "⚡ Yazar / Geliştirici",
        "tab1": "1. Poligon Katmanları ve EK-2 Tablosu",
        "tab2": "2. Eski Plan ve Fiili Kullanım",
        "tab3": "3. Plan Açıklama ve Erişim Raporu",
        "grp1": "1. Temel Harita Katmanları (Poligonlar ve Kapasiteler Otomatik Hesaplanır)",
        "lbl_net": "<b>Yol Ağı (Çizgi):</b>",
        "lbl_res": "<b>Mevcut Konut Adaları:</b>",
        "lbl_vac": "<b>Boş İmar Adaları (Bölünecek):</b>",
        "lbl_comm": "<b>Mevcut Ticari Alanlar (Demo):</b>",
        "chk_centroids": "Poligonlardan otomatik üretilen ağırlık merkezi noktalarını haritada göster",
        "grp2": "2. Planlama Alanı Nüfusu ve Çekirdek Model Altyapısı",
        "lbl_pop": "<b>Toplam Planlama Alanı Nüfusu (Kişi):</b>",
        "lbl_pop_note": "Nüfus konut adalarının m² alanına oranla dağıtılır; yol ağı p-lokasyon talep yükü, kişi başı ihtiyaç ağırlığı (stokastik tarama), çoklu donatı ve park tamponu ifrazı otomatik çalışır.",
        "grp3": "3. EK-2 Sosyal ve Teknik Altyapı Alanları Standartları Tablosu (Düzenlenebilir)",
        "col_name": "Donatı / Altyapı\n(EK-2 ve Renk)",
        "col_layer": "Mevcut Poligon\nKatmanı",
        "col_euclid": "Kuş Uçuşu\nYarıçap (m)",
        "col_net": "Yol Üzeri\nErişim (m)",
        "col_std": "EK-2 Kişi Başı\n(m² / kişi)",
        "col_min": "EK-2 Asgari\nAlan (Min m²)",
        "col_max": "Bölme Eşiği\n(Max Tekil m²)",
        "col_cap": "1 Bina Kapasite\n(Kişi Sayısı)",
        "btn_add": "➕ Yeni Donatı Satırı Ekle",
        "btn_del": "🗑️ Seçili Satırı Sil",
        "btn_reset": "🔄 EK-2 Normlarına Sıfırla",
        "btn_demo": "🚀 Örnek Poligon Test Verisi Oluştur",
        "btn_run": "⚡ AKILLI EK-2 ANALİZİNİ BAŞLAT VE HARİTAYA İŞLE",
        "none_layer": "-- Yok (Alanda Mevcut Değil) --",
        "auto_comm_layer": "-- Otomatik Algıla (mevcut_Ticari) / Demo --",
        "new_fac": "Yeni Donatı",
        "empty_report": f"<h3>Henüz analiz çalıştırılmadı.</h3><p><b>Yazar:</b> {PLUGIN_AUTHOR} — Lütfen katmanlarınızı seçip <b>ANALİZİ BAŞLAT</b> butonuna tıklayın.</p>",
        "warn_missing_title": "Eksik Katman",
        "warn_missing_msg": "Lütfen Yol Ağı (Çizgi), Mevcut Konut Adaları (Poligon) ve Boş İmar Adaları (Poligon) katmanlarını seçiniz!",
        "done_title": "Akıllı Analiz ve Optimizasyon Tamamlandı",
        "done_msg": (
            f"Yazar: {PLUGIN_AUTHOR}\n\n"
            "1) Seçili katman tercihlerinize göre 'MPYY_EK2_Sosyal_ve_Teknik_Donati_Alanlari' altında donatı/park önerileri,\n"
            "2) 'MPYY_Onerilen_Konut_Alanlari' altında yol erişimi ve kapasite geri-beslemesi onaylı 'Onerilen_Konut_Adalari',\n"
            "3) 'MPYY_Disi_Tamamlayici_Alanlar' altında Pasif Yeşil ve Ticari (Demo) katmanları haritaya eklendi!"
        ),
        "grp_diff": "Eski / Onaylı Plan Kararları ve Mevcut Fiili Kullanım Katmanları",
        "lbl_old_plan": "<b>Eski / Onaylı Plan Poligon Katmanı:</b>",
        "lbl_old_field": "<b>Eski Plan Fonksiyon / Karar Sütunu:</b>",
        "lbl_actual_use": "<b>Mevcut Fiili Kullanım / Saha Durumu Katmanı:</b>",
        "lbl_actual_field": "<b>Fiili Kullanım / Saha Durumu Sütunu:</b>",
        "chk_detect_vacant_commercial": "Planda Ticaret / Donatı olup Fiiliyatta Boş Olan Adaları Belirle",
        "chk_detect_amenity_loss": "Planda Donatı/Park olup Fiiliyatta Yapılaşmış Alanları Belirle (Md. 26 Eşdeğer Alan)",
        "btn_run_diff": "🔍 Eski Plan ve Fiili Kullanım Uyuşmazlık Analizini Başlat",
        "diff_summary_title": "Eski Plan Kararları ile Fiili Durum Uyuşmazlık Özeti",
        "col_diff_plan": "Eski Plan Kararı",
        "col_diff_actual": "Fiili Kullanım",
        "col_diff_status": "Uyuşmazlık Durumu",
        "col_diff_area": "Alan (m²)",
        "col_diff_note": "Planlama Değerlendirmesi",
        "diff_done_title": "Plan ve Fiili Kullanım Analizi Tamamlandı",
        "diff_done_msg": "'Plan_ve_Fiili_Kullanim_Karsilastirma' katmanı başarıyla üretildi ve haritaya eklendi!",
        "warn_diff_missing_title": "Eksik Karşılaştırma Katmanı",
        "warn_diff_missing_msg": "Lütfen Eski / Onaylı Plan ve Mevcut Fiili Kullanım poligon katmanlarını seçiniz!",
        "grp_out": "4. Çıktı Katmanları ve Öneri Tercihleri (Haritada Üretilip Gösterilecekleri Seçin)",
        "chk_out_donati": "Önerilen MPYY Ek-2 Donatı Alanları (Okul, Sağlık, İbadet, Park)",
        "chk_out_konut": "Gelişme Konut Adaları Öner ve Haritada Göster (Onerilen_Konut_Adalari)",
        "chk_out_passive": "Pasif Yeşil Alanlar (Yol / Kavşak Tampon Yeşili)",
        "chk_out_comm": "Önerilen Ticari Alanlar (Erişim Demo)",
    },
    "en": {
        "win_title": f"MPYY Urban Facility Accessibility, Capacity & Subdivision — Author: {PLUGIN_AUTHOR}",
        "banner_title": "SPATIAL PLANS CONSTRUCTION REGULATION (MPYY) ANNEX-2 STANDARDS & OPTIMIZATION",
        "banner_sub": f"Network P-Location • Deficit Weighting & Equilibrium • Multi-Use Subdivision + Park Buffer • Author: {PLUGIN_AUTHOR}",
        "dev_label": "⚡ Author / Developer",
        "tab1": "1. Layers and Annex-2 Standards",
        "tab2": "2. Plan vs. Actual Land Use Diff",
        "tab3": "3. Planning and Access Report",
        "grp1": "1. Base Map Layers (Polygons and Capacities Are Evaluated Automatically)",
        "lbl_net": "<b>Road Network (Line):</b>",
        "lbl_res": "<b>Residential Blocks (Polygon):</b>",
        "lbl_vac": "<b>Vacant Parcels (To Split):</b>",
        "lbl_comm": "<b>Commercial Areas (Demo):</b>",
        "chk_centroids": "Display automatically generated centroid points on map",
        "grp2": "2. Planning Area Population and Core Optimization Engine",
        "lbl_pop": "<b>Total Planning Area Population (Persons):</b>",
        "lbl_pop_note": "Demand distributes proportionally by residential m²; road p-location loads, stochastic deficit weights, multi-facility + park-buffered subdivision and capacity feedback run automatically.",
        "grp3": "3. Annex-2 Social and Technical Infrastructure Standards Table (Editable)",
        "col_name": "Facility Category\n(Annex-2 Norm)",
        "col_layer": "Existing Polygon\nLayer",
        "col_euclid": "Euclidean\nRadius (m)",
        "col_net": "Road Network\nAccess (m)",
        "col_std": "Per-Capita Std\n(m² / person)",
        "col_min": "Min Unit Area\n(Min m²)",
        "col_max": "Split Threshold\n(Max Single m²)",
        "col_cap": "Building Cap\n(Persons)",
        "btn_add": "➕ Add Facility Row",
        "btn_del": "🗑️ Remove Selected Row",
        "btn_reset": "🔄 Reset Annex-2 Norms",
        "btn_demo": "🚀 Generate Sample Polygon Data",
        "btn_run": "⚡ RUN SMART ANNEX-2 ANALYSIS AND RENDER ON MAP",
        "none_layer": "-- None in Study Area --",
        "auto_comm_layer": "-- Auto-Detect (mevcut_Ticari) / Demo --",
        "new_fac": "New Facility",
        "empty_report": f"<h3>Analysis has not been run yet.</h3><p><b>Author:</b> {PLUGIN_AUTHOR} — Please select your layers and click <b>RUN ANALYSIS</b>.</p>",
        "warn_missing_title": "Missing Layer",
        "warn_missing_msg": "Please select Road Network (Line), Existing Residential Blocks (Polygon), and Vacant Parcels (Polygon)!",
        "done_title": "Smart Analysis & Optimization Complete",
        "done_msg": (
            f"Author: {PLUGIN_AUTHOR}\n\n"
            "1) Proposed MPYY Annex-2 facility & park subdivisions added under 'MPYY_EK2_Sosyal_ve_Teknik_Donati_Alanlari',\n"
            "2) Access- and capacity-verified 'Onerilen_Konut_Adalari' added when enabled under 'MPYY_Onerilen_Konut_Alanlari',\n"
            "3) Passive Green Buffers and Commercial Demo added under 'MPYY_Disi_Tamamlayici_Alanlar'."
        ),
        "grp_diff": "Old / Approved Plan Decisions & Current Actual Land Use Layers",
        "lbl_old_plan": "<b>Old / Approved Master Plan (Polygon):</b>",
        "lbl_old_field": "<b>Plan Function / Zoning Column:</b>",
        "lbl_actual_use": "<b>Current Actual Land Use / Survey Layer:</b>",
        "lbl_actual_field": "<b>Actual Land Use / Status Column:</b>",
        "chk_detect_vacant_commercial": "Identify Planned Commercial & Public Facilities that are Actually Vacant Blocks",
        "chk_detect_amenity_loss": "Identify Planned Parks & Amenities that were Built Over (MPYY Art. 26 Equivalent Area)",
        "btn_run_diff": "🔍 Run Plan vs. Actual Land Use Discrepancy Analysis",
        "diff_summary_title": "Plan Decisions vs. Field Reality Transition Summary",
        "col_diff_plan": "Old Plan Decision",
        "col_diff_actual": "Actual Use",
        "col_diff_status": "Discrepancy Status",
        "col_diff_area": "Area (m²)",
        "col_diff_note": "Planning Assessment",
        "diff_done_title": "Plan vs. Actual Analysis Completed",
        "diff_done_msg": "'Plan_ve_Fiili_Kullanim_Karsilastirma' layer successfully generated and styled on map!",
        "warn_diff_missing_title": "Missing Comparison Layers",
        "warn_diff_missing_msg": "Please select both Old / Approved Master Plan and Current Actual Use polygon layers!",
        "grp_out": "4. Output Layers and Proposal Preferences (Select Layers to Generate and Show on Map)",
        "chk_out_donati": "Proposed MPYY Annex-2 Amenities (Schools, Health, Worship, Park)",
        "chk_out_konut": "Propose and Display Residential Development Blocks (Onerilen_Konut_Adalari)",
        "chk_out_passive": "Passive Green Buffers (Roadside / Median Green)",
        "chk_out_comm": "Proposed Commercial Areas (Access Demo)",
    },
    "zh": {
        "win_title": f"MPYY 城市公共设施可达性与空间优化系统 — 作者: {PLUGIN_AUTHOR}",
        "banner_title": "空间规划建设管理条例 (MPYY) 附表2标准与智能决策支持系统",
        "banner_sub": f"路网P-中位 • 人均缺口权重与随机均衡 • 多设施组合分割与公园缓冲 • 作者: {PLUGIN_AUTHOR}",
        "dev_label": "⚡ 开发者 / 作者",
        "tab1": "1. 多边形图层与附表2标准参数表",
        "tab2": "2. 原法定规划与实际现状用地对比分析",
        "tab3": "3. 详细规划说明与可达性报告",
        "grp1": "1. 基础地图图层（多边形与服务容量自动评估）",
        "lbl_net": "<b>路网图层（线）：</b>",
        "lbl_res": "<b>现有居住街坊（多边形）：</b>",
        "lbl_vac": "<b>空置地块（自动分割）：</b>",
        "lbl_comm": "<b>现有商业用地（演示）：</b>",
        "chk_centroids": "在地图上显示自动生成的质心点图层",
        "grp2": "2. 规划区总人口与核心计算引擎",
        "lbl_pop": "<b>规划区总人口（人）：</b>",
        "lbl_pop_note": "按居住街坊面积比例分配人口；路网p-中位负荷、人均缺口权重（随机扫描均衡）、多设施+公园缓冲分割及容量反馈均自动核心执行。",
        "grp3": "3. 附表2社会与技术基础设施标准表（可编辑）",
        "col_name": "基础设施 / 设施\n（附表2与颜色）",
        "col_layer": "现有多边形\n图层",
        "col_euclid": "直线服务\n半径 (m)",
        "col_net": "路网步行\n距离 (m)",
        "col_std": "人均标准\n(m² / 人)",
        "col_min": "最小单元面积\n(Min m²)",
        "col_max": "分割阈值\n(Max m²)",
        "col_cap": "单体容量\n(人数)",
        "btn_add": "➕ 添加新设施行",
        "btn_del": "🗑️ 删除选中行",
        "btn_reset": "🔄 重置附表2规范",
        "btn_demo": "🚀 生成示例多边形测试数据",
        "btn_run": "⚡ 开始智能附表2分析并渲染至地图",
        "none_layer": "-- 无 / 区域内不存在 --",
        "auto_comm_layer": "-- 自动检测商业图层 / 演示 --",
        "new_fac": "新公共设施",
        "empty_report": f"<h3>尚未运行分析。</h3><p><b>作者:</b> {PLUGIN_AUTHOR} — 请选择图层并点击<b>开始分析</b>按钮。</p>",
        "warn_missing_title": "缺少图层",
        "warn_missing_msg": "请选择路网图层、现有居住街坊和空置地块！",
        "done_title": "智能分析与空间优化已完成",
        "done_msg": "MPYY 设施图层、经路网与容量核验的建议居住街坊、被动绿地与商业演示图层已按您的选择添加至地图！",
        "grp_diff": "原法定规划决策与现状实际利用图层",
        "lbl_old_plan": "<b>原法定规划多边形图层：</b>",
        "lbl_old_field": "<b>原规划功能 / 用地字段：</b>",
        "lbl_actual_use": "<b>现状实际利用 / 调研图层：</b>",
        "lbl_actual_field": "<b>现状利用 / 状态字段：</b>",
        "chk_detect_vacant_commercial": "识别原规划为商业/设施但现状仍为空置街坊的地块",
        "chk_detect_amenity_loss": "识别原规划为公园/设施但被实际占用的地块（第26条等效面积核查）",
        "btn_run_diff": "🔍 启动原规划与实际利用冲突分析",
        "diff_summary_title": "原规划决策与现状实际情况转换汇总",
        "col_diff_plan": "原规划决策",
        "col_diff_actual": "现状利用",
        "col_diff_status": "冲突状态",
        "col_diff_area": "面积 (m²)",
        "col_diff_note": "规划评估意见",
        "diff_done_title": "规划与现状对比分析完成",
        "diff_done_msg": "'Plan_ve_Fiili_Kullanim_Karsilastirma' 图层已生成并渲染至地图！",
        "warn_diff_missing_title": "缺少对比图层",
        "warn_diff_missing_msg": "请同时选择原规划图层与现状实际利用多边形图层！",
        "grp_out": "4. 输出图层与建议选项（勾选需要生成并在地图显示的图层）",
        "chk_out_donati": "建议公共设施用地（MPYY附表2：学校、医疗、宗教、公园）",
        "chk_out_konut": "建议并显示居住发展街坊 (Onerilen_Konut_Adalari)",
        "chk_out_passive": "被动绿地缓冲区（道路缓冲/隔离绿化）",
        "chk_out_comm": "建议商业用地（可达性演示）",
    },
    "es": {
        "win_title": f"MPYY Accesibilidad de Instalaciones Urbanas y Optimización — Autor: {PLUGIN_AUTHOR}",
        "banner_title": "SISTEMA DE SOPORTE DE DECISIONES DE PLANES ESPACIALES (MPYY) - ESTÁNDARES ANEXO-2",
        "banner_sub": f"P-Mediana en Red • Pesos de Déficit y Equilibrio • Subdivisión Multi-Uso + Parque • Autor: {PLUGIN_AUTHOR}",
        "dev_label": "⚡ Desarrollador / Autor",
        "tab1": "1. Capas de Polígonos y Tabla Anexo-2",
        "tab2": "2. Comparación de Plan Aprobado vs. Uso Real del Suelo",
        "tab3": "3. Informe Detallado de Planificación y Accesibilidad",
        "grp1": "1. Capas de Mapa Base (Polígonos y Capacidades Evaluados Automáticamente)",
        "lbl_net": "<b>Red Vial (Línea):</b>",
        "lbl_res": "<b>Manzanas Residenciales:</b>",
        "lbl_vac": "<b>Parcelas Vacantes (Dividir):</b>",
        "lbl_comm": "<b>Áreas Comerciales (Demo):</b>",
        "chk_centroids": "Mostrar centroides generados automáticamente en el mapa",
        "grp2": "2. Población del Área y Motor Central de Optimización",
        "lbl_pop": "<b>Población Total del Área de Planificación (Personas):</b>",
        "lbl_pop_note": "Demanda proporcional al área residencial m²; carga p-mediana vial, pesos de déficit estocásticos, subdivisión multi-dotación con parque intermedio y retroalimentación de capacidad se ejecutan automáticamente.",
        "grp3": "3. Tabla de Estándares Anexo-2 (Editable)",
        "col_name": "Infraestructura / Instalación\n(Estándar y Color)",
        "col_layer": "Capa de Polígono\nExistente",
        "col_euclid": "Radio\nEuclidiano (m)",
        "col_net": "Acceso Red\nVial (m)",
        "col_std": "Norma Per Cápita\n(m² / persona)",
        "col_min": "Área Mínima\n(Mín m²)",
        "col_max": "Umbral División\n(Máx m²)",
        "col_cap": "Capacidad\n(Personas)",
        "btn_add": "➕ Agregar Fila de Instalación",
        "btn_del": "🗑️ Eliminar Fila",
        "btn_reset": "🔄 Restablecer Anexo-2",
        "btn_demo": "🚀 Generar Datos de Prueba Poligonales",
        "btn_run": "⚡ EJECUTAR ANÁLISIS INTELIGENTE ANEXO-2 Y RENDERIZAR EN MAPA",
        "none_layer": "-- Ninguno / No presente --",
        "auto_comm_layer": "-- Auto-Detectar Comercial / Demo --",
        "new_fac": "Nueva Instalación",
        "empty_report": f"<h3>El análisis aún no se ha ejecutado.</h3><p><b>Autor:</b> {PLUGIN_AUTHOR} — Seleccione sus capas y haga clic en <b>EJECUTAR ANÁLISIS</b>.</p>",
        "warn_missing_title": "Capa Faltante",
        "warn_missing_msg": "¡Seleccione la Red Vial, Bloques Residenciales y Parcelas Vacantes!",
        "done_title": "Análisis Inteligente Anexo-2 Completado",
        "done_msg": "¡Las dotaciones MPYY, manzanas residenciales validadas (Onerilen_Konut_Adalari), verde pasivo y comercial demo se han agregado al mapa!",
        "grp_diff": "Capas de Decisiones del Plan Anterior y Uso Real del Suelo",
        "lbl_old_plan": "<b>Capa de Plan Maestro Anterior (Polígono):</b>",
        "lbl_old_field": "<b>Columna de Función / Zonificación:</b>",
        "lbl_actual_use": "<b>Capa de Uso Actual del Suelo (Polígono):</b>",
        "lbl_actual_field": "<b>Columna de Uso Actual / Estado:</b>",
        "chk_detect_vacant_commercial": "Identificar Comercio y Dotaciones Planificadas que Siguen Siendo Manzanas Vacías",
        "chk_detect_amenity_loss": "Identificar Parques y Dotaciones Edificados (Verificación de Área Equivalente Art. 26)",
        "btn_run_diff": "🔍 Iniciar Análisis de Discrepancias Plan vs. Uso Real",
        "diff_summary_title": "Resumen de Transición de Decisiones del Plan vs. Realidad",
        "col_diff_plan": "Decisión del Plan Anterior",
        "col_diff_actual": "Uso Actual Real",
        "col_diff_status": "Estado de Discrepancia",
        "col_diff_area": "Área (m²)",
        "col_diff_note": "Evaluación de Planificación",
        "diff_done_title": "Análisis Plan vs. Realidad Completado",
        "diff_done_msg": "¡La capa 'Plan_ve_Fiili_Kullanim_Karsilastirma' se ha generado y renderizado con éxito en el mapa!",
        "warn_diff_missing_title": "Capas Faltantes para Comparación",
        "warn_diff_missing_msg": "¡Por favor seleccione tanto el Plan Anterior como la Capa de Uso Actual del Suelo!",
        "grp_out": "4. Capas de Salida y Preferencias de Propuesta (Seleccione para Generar y Mostrar)",
        "chk_out_donati": "Áreas de Dotación MPYY Anexo-2 (Escuela, Salud, Culto, Parque)",
        "chk_out_konut": "Proponer y Mostrar Manzanas Residenciales (Onerilen_Konut_Adalari)",
        "chk_out_passive": "Zonas Verdes Pasivas (Amortiguador Vial / Mediana)",
        "chk_out_comm": "Áreas Comerciales Propuestas (Demo de Acceso)",
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
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 12px;
    font-weight: bold;
    padding: 8px 20px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
    min-width: 260px;
}
QTabBar::tab:selected {
    background: #1e40af;
    color: #ffffff;
}
QScrollArea {
    background: transparent;
    border: none;
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
        self.resize(1200, 840)
        self.setMinimumSize(940, 620)
        self.setStyleSheet(MODERN_STYLE)
        self.setup_ui()
        self.table = self.tbl_params
        self.apply_language("en")

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(8, 8, 8, 8)

        banner = QFrame()
        banner.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f172a, stop:0.6 #1e3a8a, stop:1 #1d4ed8);"
            "border-radius: 8px; padding: 4px;"
        )
        banner_layout = QHBoxLayout(banner)

        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        logo_lbl = QLabel()
        if os.path.exists(icon_path):
            logo_lbl.setPixmap(QPixmap(icon_path).scaled(44, 44, _KEEP_ASPECT, _SMOOTH_XFORM))
        logo_lbl.setFixedSize(48, 48)
        logo_lbl.setStyleSheet("background: transparent;")
        banner_layout.addWidget(logo_lbl)

        self.title_lbl = QLabel()
        self.title_lbl.setStyleSheet("background: transparent;")
        banner_layout.addWidget(self.title_lbl, stretch=1)

        lang_box = QVBoxLayout()
        self.cmb_lang = QComboBox()
        self.cmb_lang.setIconSize(QSize(28, 18))
        self.cmb_lang.setFixedWidth(180)
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
        self.tabs.setElideMode(getattr(getattr(Qt, "TextElideMode", Qt), "ElideNone", 3))
        if self.tabs.tabBar() is not None:
            self.tabs.tabBar().setExpanding(False)
            self.tabs.tabBar().setUsesScrollButtons(False)
        main_layout.addWidget(self.tabs, stretch=1)

        # Scrollable container for Tab 1 so Section 3 Table is NEVER crushed on any monitor
        scroll_inputs = QScrollArea()
        scroll_inputs.setWidgetResizable(True)
        scroll_inputs.setFrameShape(_FRAME_NO_FRAME)

        tab_inputs = QWidget()
        layout_inputs = QVBoxLayout(tab_inputs)
        layout_inputs.setSpacing(6)
        layout_inputs.setContentsMargins(6, 6, 6, 6)

        # 1. Base Map Layers (Compact 2x2 grid saves vertical room cleanly)
        self.grp_layers = QGroupBox()
        grid = QGridLayout(self.grp_layers)
        grid.setSpacing(5)
        grid.setContentsMargins(8, 8, 8, 6)

        self.lbl_net = QLabel()
        self.cmb_network = QComboBox()
        self.lbl_res = QLabel()
        self.cmb_residential_poly = QComboBox()
        self.lbl_vac = QLabel()
        self.cmb_vacant_polys = QComboBox()
        self.lbl_comm = QLabel()
        self.cmb_commercial_poly = QComboBox()

        grid.addWidget(self.lbl_net, 0, 0)
        grid.addWidget(self.cmb_network, 0, 1)
        grid.addWidget(self.lbl_res, 0, 2)
        grid.addWidget(self.cmb_residential_poly, 0, 3)
        grid.addWidget(self.lbl_vac, 1, 0)
        grid.addWidget(self.cmb_vacant_polys, 1, 1)
        grid.addWidget(self.lbl_comm, 1, 2)
        grid.addWidget(self.cmb_commercial_poly, 1, 3)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        self.chk_show_centroids = QCheckBox()
        self.chk_show_centroids.setChecked(False)
        self.chk_show_centroids.setStyleSheet("color: #1e40af; font-weight: bold;")
        grid.addWidget(self.chk_show_centroids, 2, 0, 1, 4)

        layout_inputs.addWidget(self.grp_layers)

        # 2. Planning Area Population & Core Optimization Engine (clean, zero removable toggles)
        self.grp_pop = QGroupBox()
        pop_grid = QGridLayout(self.grp_pop)
        pop_grid.setSpacing(6)

        self.lbl_pop = QLabel()
        pop_grid.addWidget(self.lbl_pop, 0, 0)
        self.spn_population = QSpinBox()
        self.spn_population.setRange(100, 10000000)
        self.spn_population.setValue(65000)
        self.spn_population.setSingleStep(1000)
        self.spn_population.setFixedWidth(150)
        self.spn_population.setStyleSheet("font-weight: bold; font-size: 13px; color: #1e3a8a;")
        pop_grid.addWidget(self.spn_population, 0, 1)

        self.lbl_pop_note = QLabel()
        self.lbl_pop_note.setWordWrap(True)
        self.lbl_pop_note.setStyleSheet("color: #475569; font-weight: normal; font-size: 11px;")
        pop_grid.addWidget(self.lbl_pop_note, 0, 2)
        pop_grid.setColumnStretch(2, 1)

        layout_inputs.addWidget(self.grp_pop)

        # 3. EK-2 Social & Technical Infrastructure Standards Table (Spacious & Unclipped!)
        self.grp_table = QGroupBox()
        tbl_layout = QVBoxLayout(self.grp_table)
        tbl_layout.setSpacing(5)
        tbl_layout.setContentsMargins(8, 8, 8, 6)

        self.tbl_params = QTableWidget()
        self.tbl_params.setAlternatingRowColors(True)
        self.tbl_params.setIconSize(QSize(18, 18))
        self.tbl_params.setColumnCount(8)
        self.tbl_params.setWordWrap(True)
        self.tbl_params.setMinimumHeight(250)

        horiz_hdr = self.tbl_params.horizontalHeader()
        horiz_hdr.setDefaultAlignment(_ALIGN_CENTER)
        horiz_hdr.setMinimumHeight(44)
        horiz_hdr.setMaximumHeight(56)
        horiz_hdr.setMinimumSectionSize(84)
        horiz_hdr.setSectionResizeMode(_RESIZE_INTERACTIVE)
        horiz_hdr.setStretchLastSection(True)

        col_widths = [286, 194, 86, 92, 96, 94, 98, 92]
        for ci, cw in enumerate(col_widths):
            self.tbl_params.setColumnWidth(ci, cw)

        vert_hdr = self.tbl_params.verticalHeader()
        vert_hdr.setDefaultSectionSize(30)

        self.populate_default_params()
        tbl_layout.addWidget(self.tbl_params, stretch=1)

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

        # 4. Output Layers & Visibility Preferences Group (Clean 2x2 grid)
        self.grp_outputs = QGroupBox()
        out_grid = QGridLayout(self.grp_outputs)
        out_grid.setSpacing(6)

        self.chk_out_donati = QCheckBox()
        self.chk_out_donati.setChecked(True)
        out_grid.addWidget(self.chk_out_donati, 0, 0)

        self.chk_out_konut = QCheckBox()
        self.chk_out_konut.setChecked(True)
        out_grid.addWidget(self.chk_out_konut, 0, 1)

        self.chk_out_passive = QCheckBox()
        self.chk_out_passive.setChecked(True)
        out_grid.addWidget(self.chk_out_passive, 1, 0)

        self.chk_out_comm = QCheckBox()
        self.chk_out_comm.setChecked(True)
        out_grid.addWidget(self.chk_out_comm, 1, 1)

        layout_inputs.addWidget(self.grp_outputs)

        scroll_inputs.setWidget(tab_inputs)
        self.tabs.addTab(scroll_inputs, "")

        # ----------------------------------------------------
        # TAB 2: Old Master Plan vs. Actual Land Use Discrepancy
        # ----------------------------------------------------
        self.tab_diff = QWidget()
        layout_diff = QVBoxLayout(self.tab_diff)
        layout_diff.setSpacing(10)

        self.grp_diff = QGroupBox()
        diff_grid = QGridLayout(self.grp_diff)
        diff_grid.setSpacing(8)

        self.lbl_old_plan = QLabel()
        diff_grid.addWidget(self.lbl_old_plan, 0, 0)
        self.cmb_old_plan = QComboBox()
        self.cmb_old_plan.currentIndexChanged.connect(self.on_old_plan_layer_changed)
        diff_grid.addWidget(self.cmb_old_plan, 0, 1)

        self.lbl_old_field = QLabel()
        diff_grid.addWidget(self.lbl_old_field, 0, 2)
        self.cmb_old_field = QComboBox()
        diff_grid.addWidget(self.cmb_old_field, 0, 3)

        self.lbl_actual_use = QLabel()
        diff_grid.addWidget(self.lbl_actual_use, 1, 0)
        self.cmb_actual_use = QComboBox()
        self.cmb_actual_use.currentIndexChanged.connect(self.on_actual_use_layer_changed)
        diff_grid.addWidget(self.cmb_actual_use, 1, 1)

        self.lbl_actual_field = QLabel()
        diff_grid.addWidget(self.lbl_actual_field, 1, 2)
        self.cmb_actual_field = QComboBox()
        diff_grid.addWidget(self.cmb_actual_field, 1, 3)

        self.chk_detect_vacant_commercial = QCheckBox()
        self.chk_detect_vacant_commercial.setChecked(True)
        diff_grid.addWidget(self.chk_detect_vacant_commercial, 2, 0, 1, 2)

        self.chk_detect_amenity_loss = QCheckBox()
        self.chk_detect_amenity_loss.setChecked(True)
        diff_grid.addWidget(self.chk_detect_amenity_loss, 2, 2, 1, 2)

        self.btn_run_diff = QPushButton()
        self.btn_run_diff.setMinimumHeight(38)
        self.btn_run_diff.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);"
            "color: white; font-weight: bold; font-size: 13px; padding: 6px 16px; border-radius: 6px;"
        )
        self.btn_run_diff.clicked.connect(lambda: self.run_plan_actual_diff(show_msg=True))
        diff_grid.addWidget(self.btn_run_diff, 3, 0, 1, 4)

        layout_diff.addWidget(self.grp_diff)

        self.grp_diff_tbl = QGroupBox()
        diff_tbl_layout = QVBoxLayout(self.grp_diff_tbl)

        self.tbl_diff_preview = QTableWidget()
        self.tbl_diff_preview.setAlternatingRowColors(True)
        self.tbl_diff_preview.setColumnCount(5)
        self.tbl_diff_preview.setMinimumHeight(240)
        diff_horiz = self.tbl_diff_preview.horizontalHeader()
        diff_horiz.setDefaultAlignment(_ALIGN_CENTER)
        diff_horiz.setMinimumHeight(40)
        diff_horiz.setSectionResizeMode(_RESIZE_STRETCH)
        diff_horiz.setSectionResizeMode(4, _RESIZE_INTERACTIVE)
        self.tbl_diff_preview.setColumnWidth(4, 380)
        diff_tbl_layout.addWidget(self.tbl_diff_preview)

        layout_diff.addWidget(self.grp_diff_tbl, stretch=1)
        self.tabs.addTab(self.tab_diff, "")

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
        self.tabs.setTabText(2, t["tab3"])

        self.grp_layers.setTitle(t["grp1"])
        self.lbl_net.setText(t["lbl_net"])
        self.lbl_res.setText(t["lbl_res"])
        self.lbl_vac.setText(t["lbl_vac"])
        self.lbl_comm.setText(t["lbl_comm"])
        self.chk_show_centroids.setText(t["chk_centroids"])

        self.grp_pop.setTitle(t["grp2"])
        self.lbl_pop.setText(t["lbl_pop"])
        self.lbl_pop_note.setText(t["lbl_pop_note"])

        # Tab 2 Diff Controls
        self.grp_diff.setTitle(t["grp_diff"])
        self.lbl_old_plan.setText(t["lbl_old_plan"])
        self.lbl_old_field.setText(t["lbl_old_field"])
        self.lbl_actual_use.setText(t["lbl_actual_use"])
        self.lbl_actual_field.setText(t["lbl_actual_field"])
        self.chk_detect_vacant_commercial.setText(t["chk_detect_vacant_commercial"])
        self.chk_detect_amenity_loss.setText(t["chk_detect_amenity_loss"])
        self.btn_run_diff.setText(t["btn_run_diff"])
        self.grp_diff_tbl.setTitle(t["diff_summary_title"])
        self.tbl_diff_preview.setHorizontalHeaderLabels([
            t["col_diff_plan"], t["col_diff_actual"], t["col_diff_status"], t["col_diff_area"], t["col_diff_note"]
        ])

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

        self.grp_outputs.setTitle(t["grp_out"])
        self.chk_out_donati.setText(t["chk_out_donati"])
        self.chk_out_konut.setText(t["chk_out_konut"])
        self.chk_out_passive.setText(t["chk_out_passive"])
        self.chk_out_comm.setText(t["chk_out_comm"])

        if self.cmb_commercial_poly.count() > 0:
            self.cmb_commercial_poly.setItemText(0, t["auto_comm_layer"])

        lang_idx_map = {"tr": 1, "en": 2, "zh": 3, "es": 4}
        lang_idx = lang_idx_map.get(lang, 2)

        for r in range(self.tbl_params.rowCount()):
            name_item = self.tbl_params.item(r, 0)
            if name_item:
                key_id = name_item.data(_USER_ROLE)
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
            if isinstance(lyr, QgsVectorLayer) and lyr.geometryType() in (_POLY_GEOM, _POINT_GEOM):
                if lyr.name().startswith("MPYY_"):
                    continue
                cmb.addItem(lyr.name(), lyr)
        if auto_keywords:
            self._auto_select_combo(cmb, auto_keywords, start_idx=1)
        return cmb

    def populate_default_params(self):
        lang_idx_map = {"tr": 1, "en": 2, "zh": 3, "es": 4}
        lang_idx = lang_idx_map.get(self.current_lang, 2)
        bold_font = QFont("Segoe UI", 10, _BOLD_WEIGHT)
        num_font = QFont("Segoe UI", 10, _DEMI_WEIGHT)

        self.tbl_params.setRowCount(0)
        for row_idx, item in enumerate(DEFAULT_MPYY_FACILITIES):
            self.tbl_params.insertRow(row_idx)
            self.tbl_params.setRowHeight(row_idx, 29)

            name_cell = QTableWidgetItem(create_color_swatch_icon(item[11]), str(item[lang_idx]))
            name_cell.setData(_USER_ROLE, item[0])
            name_cell.setFont(bold_font)
            name_cell.setForeground(QColor("#0f172a"))
            self.tbl_params.setItem(row_idx, 0, name_cell)

            cmb = self._create_poly_layer_combo(auto_keywords=item[12])
            self.tbl_params.setCellWidget(row_idx, 1, cmb)

            for col_idx, val_idx in enumerate(range(5, 11), start=2):
                cell = QTableWidgetItem(str(item[val_idx]))
                cell.setFont(num_font)
                cell.setForeground(QColor("#0f172a"))
                cell.setTextAlignment(_ALIGN_CENTER)
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
        self.tbl_params.setRowHeight(r, 34)
        name_cell = QTableWidgetItem(create_color_swatch_icon("#475569"), t["new_fac"])
        name_cell.setData(_USER_ROLE, f"custom_{r}")
        name_cell.setFont(QFont("Segoe UI", 10, _BOLD_WEIGHT))
        self.tbl_params.setItem(r, 0, name_cell)
        cmb = self._create_poly_layer_combo()
        self.tbl_params.setCellWidget(r, 1, cmb)
        defaults = ["500.0", "500.0", "1.0", "1000.0", "5000.0", "2500"]
        for c_offset, val in enumerate(defaults, start=2):
            item = QTableWidgetItem(val)
            item.setTextAlignment(_ALIGN_CENTER)
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

        self.cmb_old_plan.blockSignals(True)
        self.cmb_actual_use.blockSignals(True)
        self.cmb_old_plan.clear()
        self.cmb_actual_use.clear()
        self.cmb_old_plan.addItem(t["none_layer"], None)
        self.cmb_actual_use.addItem(t["none_layer"], None)

        layers = list(QgsProject.instance().mapLayers().values())
        for lyr in layers:
            if not isinstance(lyr, QgsVectorLayer):
                continue
            if lyr.name().startswith("MPYY_"):
                continue
            geom_type = lyr.geometryType()
            if geom_type == _LINE_GEOM:
                self.cmb_network.addItem(lyr.name(), lyr)
            elif geom_type == _POLY_GEOM:
                self.cmb_residential_poly.addItem(lyr.name(), lyr)
                self.cmb_vacant_polys.addItem(lyr.name(), lyr)
                self.cmb_commercial_poly.addItem(lyr.name(), lyr)
                self.cmb_old_plan.addItem(lyr.name(), lyr)
                self.cmb_actual_use.addItem(lyr.name(), lyr)

        self._auto_select_combo(self.cmb_network, ["prepared", "yol", "network", "ag", "road"])
        self._auto_select_combo(self.cmb_residential_poly, ["konut_adalari", "mevcut_konut", "konut", "yerlesim"])
        self._auto_select_combo(self.cmb_vacant_polys, ["mevcut_bos", "bos_alan", "bos_imar", "bos_ada", "bos", "vacant"])
        self._auto_select_combo(self.cmb_commercial_poly, ["mevcut_ticari", "ticari", "ticaret", "commercial"], start_idx=1)

        self._auto_select_combo(self.cmb_old_plan, ["eski_onayli_plan", "eski_plan", "onayli_plan", "meri_plan", "plan_kararlari", "plan"], start_idx=1)
        self._auto_select_combo(self.cmb_actual_use, ["mevcut_fiili_kullanim", "fiili_kullanim", "mevcut_kullanim", "arazi_kullanimi", "saha", "actual"], start_idx=1)

        self.cmb_old_plan.blockSignals(False)
        self.cmb_actual_use.blockSignals(False)
        self.on_old_plan_layer_changed()
        self.on_actual_use_layer_changed()

        for r in range(self.tbl_params.rowCount()):
            name_item = self.tbl_params.item(r, 0)
            key_id = name_item.data(_USER_ROLE) if name_item else ""
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

    def on_old_plan_layer_changed(self):
        lyr = self.cmb_old_plan.currentData()
        self.cmb_old_field.clear()
        if not lyr or not isinstance(lyr, QgsVectorLayer):
            return
        for f in lyr.fields():
            self.cmb_old_field.addItem(f.name(), f.name())
        self._auto_select_combo(self.cmb_old_field, ["plan_fonk", "fonksiyon", "kullanim", "lejant", "tur", "use", "zoning", "ad", "name"])

    def on_actual_use_layer_changed(self):
        lyr = self.cmb_actual_use.currentData()
        self.cmb_actual_field.clear()
        if not lyr or not isinstance(lyr, QgsVectorLayer):
            return
        for f in lyr.fields():
            self.cmb_actual_field.addItem(f.name(), f.name())
        self._auto_select_combo(self.cmb_actual_field, ["fiili_kullanim", "fiili_kul", "fiili", "kullanim", "durum", "actual", "use", "status", "ad"])

    def run_plan_actual_diff(self, show_msg=True):
        t = TRANSLATIONS[self.current_lang]
        old_lyr = self.cmb_old_plan.currentData()
        act_lyr = self.cmb_actual_use.currentData()
        old_field = self.cmb_old_field.currentText()
        act_field = self.cmb_actual_field.currentText()

        if not old_lyr or not act_lyr:
            if show_msg:
                QMessageBox.warning(self, t["warn_diff_missing_title"], t["warn_diff_missing_msg"])
            return None

        diff_feats, summary, matrix = PlanActualDiffEngine.run_comparison(
            old_lyr, old_field, act_lyr, act_field,
            target_crs=old_lyr.crs(), min_area_m2=1.0
        )

        self.last_diff_summary = summary
        self.last_diff_matrix = matrix

        # Populate tbl_diff_preview in Tab 2
        self.tbl_diff_preview.setRowCount(0)
        sorted_feats = sorted(diff_feats, key=lambda x: x["alan_m2"], reverse=True)
        for df in sorted_feats[:120]:
            r = self.tbl_diff_preview.rowCount()
            self.tbl_diff_preview.insertRow(r)
            self.tbl_diff_preview.setItem(r, 0, QTableWidgetItem(str(df["eski_plan"])))
            self.tbl_diff_preview.setItem(r, 1, QTableWidgetItem(str(df["mevcut_fiili"])))
            status_item = QTableWidgetItem(df["durum"])
            if df["kod"] == "UYUMLU":
                status_item.setForeground(QColor("#059669"))
            elif df["kod"] == "BOS_ADA":
                status_item.setForeground(QColor("#d97706"))
            elif df["kod"] == "DONATI_KAYBI":
                status_item.setForeground(QColor("#dc2626"))
            elif df["kod"] == "ACIK_ALAN":
                status_item.setForeground(QColor("#0d9488"))
            else:
                status_item.setForeground(QColor("#2563eb"))
            status_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.tbl_diff_preview.setItem(r, 2, status_item)
            area_item = QTableWidgetItem(f"{df['alan_m2']:,.1f}")
            area_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tbl_diff_preview.setItem(r, 3, area_item)
            self.tbl_diff_preview.setItem(r, 4, QTableWidgetItem(df["yorum"]))

        # Build QGIS Vector Memory Layer
        crs_auth = old_lyr.crs().authid()
        out_lyr = QgsVectorLayer(f"Polygon?crs={crs_auth}", "Plan_Fiili_Kullanim_Uyusmazlik_Analizi", "memory")
        pr = out_lyr.dataProvider()
        pr.addAttributes([
            QgsField("eski_plan", _QVAR_STRING),
            QgsField("mevcut_fiili", _QVAR_STRING),
            QgsField("durum", _QVAR_STRING),
            QgsField("kod", _QVAR_STRING),
            QgsField("alan_m2", _QVAR_DOUBLE),
            QgsField("planlama_yorumu", _QVAR_STRING),
            QgsField("yazar", _QVAR_STRING),
        ])
        out_lyr.updateFields()

        qfeats = []
        for df in diff_feats:
            f = QgsFeature(out_lyr.fields())
            f.setGeometry(df["geom"])
            f["eski_plan"] = df["eski_plan"]
            f["mevcut_fiili"] = df["mevcut_fiili"]
            f["durum"] = df["durum"]
            f["kod"] = df["kod"]
            f["alan_m2"] = df["alan_m2"]
            f["planlama_yorumu"] = df["yorum"]
            f["yazar"] = PLUGIN_AUTHOR
            qfeats.append(f)
        pr.addFeatures(qfeats)
        out_lyr.updateExtents()

        # Categorized Symbology
        cats = [
            ("UYUMLU", "Uyumlu / Gerçekleşmiş", "#10b981"),
            ("BOS_ADA", "Gerçekleşmemiş (Boş Ada)", "#f59e0b"),
            ("ACIK_ALAN", "Gerçekleşmemiş (Park / Açık Alan)", "#059669"),
            ("DONATI_KAYBI", "Aykırı Dönüşüm / Donatı Kaybı", "#ef4444"),
            ("FONKSIYON_DEGISIMI", "Fonksiyon Değişimi", "#3b82f6"),
        ]
        renderer_cats = []
        for val, label, hex_col in cats:
            sym = QgsFillSymbol.createSimple({
                "color": hex_col,
                "color_border": "#0f172a",
                "width_border": "0.6",
                "style": "solid",
            })
            sym.setOpacity(0.72)
            renderer_cats.append(QgsRendererCategory(val, sym, label))
        renderer = QgsCategorizedSymbolRenderer("kod", renderer_cats)
        out_lyr.setRenderer(renderer)
        out_lyr.triggerRepaint()

        # Add to Group in Layer Tree
        root = QgsProject.instance().layerTreeRoot()
        grp_name = "Plan_ve_Fiili_Kullanim_Karsilastirma"
        grp = root.findGroup(grp_name)
        if grp is None:
            grp = root.addGroup(grp_name)
        existing = QgsProject.instance().mapLayersByName(out_lyr.name())
        for el in existing:
            QgsProject.instance().removeMapLayer(el.id())
        QgsProject.instance().addMapLayer(out_lyr, False)
        grp.addLayer(out_lyr)

        if show_msg:
            QMessageBox.information(self, t["diff_done_title"], t["diff_done_msg"])
            self.tabs.setCurrentIndex(1)

        return out_lyr

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
                key_id = name_item.data(_USER_ROLE) or name
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
            if isinstance(lyr, QgsVectorLayer) and lyr.geometryType() in (_POLY_GEOM, _POINT_GEOM):
                lname = lyr.name().lower()
                if not lname.startswith("mpyy_") and any(k in lname for k in ("ticari", "ticaret", "commercial")):
                    return lyr
        return None

    def run_full_analysis(self, show_msg=True):
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

            # 6. Pass 2: Evaluate Every Residential Block (Distance Reachability + Capacity Overflow + Deficit Weights)
            stochastic_profiles, stochastic_ordered_list = AdaptiveAmenityWeightingEngine.compute_block_amenity_profiles(
                res_feats=res_feats,
                graph=graph,
                fac_by_type=fac_by_type,
                specs=specs,
                total_pop=total_pop,
                net_dist_maps=net_dist_maps,
                randomize_order=True,
                seed=42,
            )

            res_out_lyr = QgsVectorLayer(f"Point?crs={crs_auth}", "MPYY_Konut_Agirlik_Merkezleri_Erisim", "memory")
            res_pr = res_out_lyr.dataProvider()
            res_fields = QgsFields()
            res_fields.append(QgsField("ada_id", _QVAR_INT))
            res_fields.append(QgsField("ada_alan_m2", _QVAR_DOUBLE))
            res_fields.append(QgsField("tahmini_nufus", _QVAR_DOUBLE))
            res_fields.append(QgsField("ticari_yol_m", _QVAR_DOUBLE))

            if stochastic_profiles:
                res_fields.append(QgsField("stokastik_sira", _QVAR_INT))
                res_fields.append(QgsField("oncelikli_ihtiyac", _QVAR_STRING))
                res_fields.append(QgsField("donati_yeterlilik", _QVAR_DOUBLE))
                for cat in specs.keys():
                    if specs[cat]["key_id"] == "konut":
                        continue
                    short_c = cat[:10].replace(" ", "_")
                    res_fields.append(QgsField(f"{short_c}_m2_kisi", _QVAR_DOUBLE))
                    res_fields.append(QgsField(f"{short_c}_ihtiyac_agirlik", _QVAR_DOUBLE))

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

                if r_id in stochastic_profiles:
                    sprof = stochastic_profiles[r_id]
                    new_f["stokastik_sira"] = sprof["stokastik_sira"]
                    new_f["oncelikli_ihtiyac"] = f"{sprof['en_oncelikli_ihtiyac']} (%{int(sprof['oncelikli_agirlik']*100)})"
                    new_f["donati_yeterlilik"] = sprof["donati_yeterlilik_yuzdesi"]
                    for cat in specs.keys():
                        if specs[cat]["key_id"] == "konut":
                            continue
                        short_c = cat[:10].replace(" ", "_")
                        new_f[f"{short_c}_m2_kisi"] = sprof["mevcut_m2_kisi"].get(cat, 0.0)
                        new_f[f"{short_c}_ihtiyac_agirlik"] = sprof["ihtiyac_agirligi"].get(cat, 0.0)

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

            # Dedicated Unified Proposed Residential Blocks Layer (Walkability + Carrying-Capacity Feedback)
            konut_out_lyr = QgsVectorLayer(f"Polygon?crs={crs_auth}", "Onerilen_Konut_Adalari", "memory")
            konut_out_pr = konut_out_lyr.dataProvider()
            konut_fields = QgsFields()
            konut_fields.append(QgsField("kaynak_ada_id", _QVAR_INT))
            konut_fields.append(QgsField("parca_no", _QVAR_INT))
            konut_fields.append(QgsField("kod", _QVAR_STRING))
            konut_fields.append(QgsField("kullanim_turu", _QVAR_STRING))
            konut_fields.append(QgsField("alan_m2", _QVAR_DOUBLE))
            konut_fields.append(QgsField("ongorulen_nufus", _QVAR_INT))
            konut_fields.append(QgsField("yol_erisim_skoru", _QVAR_DOUBLE))
            konut_fields.append(QgsField("ilkokul_yol_m", _QVAR_DOUBLE))
            konut_fields.append(QgsField("ortaokul_yol_m", _QVAR_DOUBLE))
            konut_fields.append(QgsField("asm_yol_m", _QVAR_DOUBLE))
            konut_fields.append(QgsField("park_yol_m", _QVAR_DOUBLE))
            konut_fields.append(QgsField("ticari_yol_m", _QVAR_DOUBLE))
            konut_fields.append(QgsField("kapasite_geri_besleme", _QVAR_STRING))
            konut_fields.append(QgsField("komsu_donatilar", _QVAR_STRING))
            konut_fields.append(QgsField("planlama_gerekcesi", _QVAR_STRING))
            konut_fields.append(QgsField("yazar", _QVAR_STRING))
            konut_out_pr.addAttributes(konut_fields)
            konut_out_lyr.updateFields()

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
            out_konut_features = []
            out_passive_features = []
            out_comm_features = []
            res_growth_results = []

            dyn_fac_view = {c: [list(it) for it in fac_by_type.get(c, [])] for c in specs.keys()}
            dyn_stoch_profiles = {k: dict(v) for k, v in stochastic_profiles.items()}
            for _k, _v in dyn_stoch_profiles.items():
                _v["ihtiyac_agirligi"] = dict(_v["ihtiyac_agirligi"])
                _v["mevcut_m2_kisi"] = dict(_v["mevcut_m2_kisi"])

            # Sector-level minimum spacing (m), max new facility quotas, and urban priority weights
            SECTOR_RULES = {
                "hastane": {"exist_r": 3500.0, "new_r": 5000.0, "max_new": 0 if any(len(fac_by_type[c]) > 0 for c, s in specs.items() if s["key_id"] == "hastane") else 1, "prio": 0.70, "ideal_max_lot": 12000.0},
                "ilkokul": {"exist_r": 490.0,  "new_r": 580.0,  "max_new": 4, "prio": 1.85, "ideal_max_lot": 7200.0},
                "ortaokul": {"exist_r": 920.0, "new_r": 1150.0, "max_new": 3, "prio": 1.35, "ideal_max_lot": 8200.0},
                "lise":    {"exist_r": 1800.0, "new_r": 2500.0, "max_new": 1, "prio": 1.00, "ideal_max_lot": 9000.0},
                "anaokulu": {"exist_r": 490.0, "new_r": 580.0,  "max_new": 3, "prio": 1.15, "ideal_max_lot": 2200.0},
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

                agg_w, n_blocks, tot_n_pop, avg_sat, max_def_cat, max_def_val = (
                    AdaptiveAmenityWeightingEngine.compute_neighborhood_deficit_weights(
                        eval_pt, dyn_stoch_profiles, dyn_fac_view, specs
                    )
                )

                # Proximity to existing and newly placed parks (to prevent creating redundant giant parks)
                d_exist_park = min(
                    (math.hypot(eval_pt.x() - it[1].x(), eval_pt.y() - it[1].y()) for it in fac_by_type.get(park_cat, [])),
                    default=float('inf')
                )
                d_new_park = min(
                    (math.hypot(eval_pt.x() - np_pt.x(), eval_pt.y() - np_pt.y()) for np_pt, _, _ in newly_placed_points.get(park_cat, [])),
                    default=float('inf')
                )
                nearby_park_adequate = (min(d_exist_park, d_new_park) <= 450.0)

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
                        if key_id in ("ilkokul", "ortaokul", "anaokulu", "asm", "ibadet", "sosyal"):
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
                        local_w = agg_w.get(cat, 0.0)
                        if newly_covered_pop <= 20.0 and deficit_weight <= 100.0 and local_w < 0.25:
                            continue

                        scale_factor = srule["prio"]
                        if poly_area >= 7000.0:
                            if key_id in ("ilkokul", "ortaokul", "lise"):
                                scale_factor *= 1.45
                            elif key_id in ("asm", "anaokulu"):
                                scale_factor *= 1.10
                            elif key_id == "ibadet":
                                scale_factor *= 0.50
                        elif poly_area <= 4500.0:
                            if key_id in ("ibadet", "asm", "sosyal", "anaokulu"):
                                scale_factor *= 1.25

                        if relief_target is not None:
                            scale_factor *= 1.35

                        diversity_factor = 1.0 / (1.0 + allocated_summary[cat]["count"] * 0.70)
                        score = (
                            (newly_covered_pop * 2.4 + deficit_weight * 0.45)
                            * (1.0 + 1.15 * local_w)
                            * diversity_factor
                            * scale_factor
                        )

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
                    non_mpyy_summary["ticari_demo"]["count"] < 2
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
                    can_house_block = nearby_park_adequate or (
                        block_rect_fill >= 0.70 and poly_area >= 2500.0 and not is_triangular_medium_block
                    )
                    if self.chk_out_konut.isChecked() and can_house_block:
                        gerekce_intro = (
                            f"Ada #{pf.id()} ({int(poly_area)} m²): Çevre sektörde donatılar yeterli olup ({iyi_str}), "
                            f"yürüme mesafesinde ({int(min(d_exist_park, d_new_park)) if min(d_exist_park, d_new_park) < 1e8 else 0} m) park mevcuttur. "
                            f"Alan gereksiz yere büyük bir parka dönüştürülmeyip gelişme konutu olarak ayrılmıştır"
                        )
                        self._evaluate_and_append_housing_parcel(
                            pf.id(), 1, pgeom, konut_out_lyr, out_konut_features, res_growth_results,
                            parcel_narrative_list, graph, specs, fac_by_type, newly_placed_points,
                            net_dist_maps, comm_pts, newly_placed_comm_pts, comm_dist_map,
                            tot_n_pop, iyi_str, gerekce_intro,
                        )
                        v_pt_f = QgsFeature(vac_pts_lyr.fields())
                        v_pt_f.setGeometry(QgsGeometry.fromPointXY(eval_pt))
                        v_pt_f["kaynak_ada_id"] = pf.id()
                        v_pt_f["alan_m2"] = round(poly_area, 1)
                        v_pt_f["atanan_donatilar"] = "Önerilen Konut Alanı"
                        vac_pt_features.append(v_pt_f)
                        continue
                    elif not nearby_park_adequate:
                        fallback_cat = park_cat
                        etki_val = int(round(poly_area / max(specs[fallback_cat]["std_m2"], 1.0)))
                        aciklama = (
                            f"Ada #{pf.id()} ({int(poly_area)} m²): Sektör donatı kotaları karşılandığından ve yakın çevrede park "
                            f"bulunmadığından (en yakın {int(min(d_exist_park, d_new_park)) if min(d_exist_park, d_new_park) < 1e8 else 999} m) '{fallback_cat}' olarak ayrıldı."
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
                        self._register_placed_facility(
                            fallback_cat, eval_pt, v_nid, v_snap, vac_dist_map, specs[fallback_cat]["net_r"],
                            etki_val, poly_area, newly_placed_points, existing_cap_by_type,
                            remaining_deficit_pop, unserved_res_nodes, allocated_summary,
                            dyn_fac_view=dyn_fac_view, dyn_stoch_profiles=dyn_stoch_profiles,
                            neighborhood_blocks=n_blocks, tot_n_pop=tot_n_pop, fid=pf.id(),
                        )
                        parcel_narrative_list.append(aciklama)

                        v_pt_f = QgsFeature(vac_pts_lyr.fields())
                        v_pt_f.setGeometry(QgsGeometry.fromPointXY(eval_pt))
                        v_pt_f["kaynak_ada_id"] = pf.id()
                        v_pt_f["alan_m2"] = round(poly_area, 1)
                        v_pt_f["atanan_donatilar"] = fallback_cat
                        vac_pt_features.append(v_pt_f)
                        continue
                    else:
                        parcel_narrative_list.append(
                            f"Ada #{pf.id()} ({int(poly_area)} m²): Yakın çevrede park ve donatılar yeterli olup konut önerisi "
                            f"seçeneği kapalı olduğundan gereksiz yeşil dönüşümü yapılmayıp rezerv parsel olarak korundu."
                        )
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
                if poly_area >= 9500.0 and len(aday_donatilar) >= 2:
                    for cand2 in aday_donatilar[1:]:
                        c2_key = cand2["sp"]["key_id"]
                        if c2_key == p_sp["key_id"]:
                            continue
                        if c2_key in ("asm", "sosyal", "ibadet", "anaokulu"):
                            ideal_lot_2 = min(cand2["sp"]["max_single"], cand2["srule"].get("ideal_max_lot", 2200.0))
                            cand2_area = max(cand2["sp"]["min_area"], min(poly_area * 0.18, ideal_lot_2))
                            if (target_primary_area + cand2_area + 2000.0) <= poly_area * 0.78:
                                secondary = cand2
                                target_second_area = cand2_area
                                break

                # Carve outer Passive Green Buffer strip on large tapered highway-edge blocks
                carve_passive = (
                    poly_area >= 26000.0
                    and block_rect_fill < 0.72
                )

                rem_area = poly_area - target_primary_area - target_second_area
                park_min = max(specs[park_cat]["min_area"] if park_cat in specs else 1000.0, 1200.0)

                should_split = (
                    p_cat != park_cat
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

                    # Check if the park remainder is large and nearby park is adequate:
                    # Carve a modest park buffer around the facility and allocate the large remainder to Housing (when housing is enabled)
                    park_part_geom = multi_res["park"]
                    housing_part_geom = None
                    park_buf_m2 = 0.0
                    if self.chk_out_konut.isChecked() and park_part_geom is not None and not park_part_geom.isEmpty():
                        p_rem_area = park_part_geom.area()
                        if (nearby_park_adequate and p_rem_area >= 3200.0) or p_rem_area >= 5000.0:
                            park_buf_m2 = min(2200.0, max(1200.0, p_rem_area * 0.18))
                            house_rem_m2 = p_rem_area - park_buf_m2
                            spl_park = split_polygon_by_ratios(park_part_geom, [park_buf_m2, house_rem_m2], is_built_flags=[False, True])
                            if len(spl_park) >= 2:
                                park_part_geom = spl_park[0]
                                housing_part_geom = spl_park[1]

                    alloc_parts = []
                    if multi_res["built1"] is not None and not multi_res["built1"].isEmpty():
                        alloc_parts.append((p_cat, multi_res["built1"], primary.get("relief_target")))
                    if park_part_geom is not None and not park_part_geom.isEmpty():
                        alloc_parts.append((park_cat, park_part_geom, None))
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
                            relief_target=s_relief, dyn_fac_view=dyn_fac_view,
                            dyn_stoch_profiles=dyn_stoch_profiles, neighborhood_blocks=n_blocks,
                            tot_n_pop=tot_n_pop, fid=pf.id(),
                        )
                        if s_cat != park_cat:
                            all_newly_placed_built_pts.append(s_pt)

                    if self.chk_out_konut.isChecked() and housing_part_geom is not None and not housing_part_geom.isEmpty():
                        gerekce_intro = (
                            f"Ada #{pf.id()}: '{p_cat}' ve {int(park_buf_m2)} m² yeşil tampon "
                            f"ayrıldıktan sonra kalan {int(housing_part_geom.area())} m² alan; yakın çevrede park bulunduğu "
                            f"için gereksiz yeşil genişletmesi yerine gelişme konutuna ayrılmıştır"
                        )
                        self._evaluate_and_append_housing_parcel(
                            pf.id(), 9, housing_part_geom, konut_out_lyr, out_konut_features, res_growth_results,
                            parcel_narrative_list, graph, specs, fac_by_type, newly_placed_points,
                            net_dist_maps, comm_pts, newly_placed_comm_pts, comm_dist_map,
                            tot_n_pop, f"Bitişik Donatılar ({p_cat})", gerekce_intro,
                        )

                    parcel_narrative_list.append(ortak_aciklama)

                    v_pt_f = QgsFeature(vac_pts_lyr.fields())
                    v_pt_f.setGeometry(QgsGeometry.fromPointXY(eval_pt))
                    v_pt_f["kaynak_ada_id"] = pf.id()
                    v_pt_f["alan_m2"] = round(poly_area, 1)
                    atanan_str = " + ".join(c for c, _, _ in alloc_parts)
                    if self.chk_out_konut.isChecked() and housing_part_geom is not None:
                        atanan_str += " + Önerilen Konut Alanı"
                    v_pt_f["atanan_donatilar"] = atanan_str
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
                        self._register_placed_facility(
                            park_cat, eval_pt, v_nid, v_snap, vac_dist_map, specs[park_cat]["net_r"],
                            int(round(poly_area / 10.0)), poly_area, newly_placed_points, existing_cap_by_type,
                            remaining_deficit_pop, unserved_res_nodes, allocated_summary,
                            dyn_fac_view=dyn_fac_view, dyn_stoch_profiles=dyn_stoch_profiles,
                            neighborhood_blocks=n_blocks, tot_n_pop=tot_n_pop, fid=pf.id(),
                        )
                        continue

                    # Compact facility (ibadet / asm / anaokulu <= 2500 m²) on large block (>= 5500 m²):
                    # Allocate compact facility lot + park buffer + remaining Önerilen Konut Alanı when enabled
                    if (
                        self.chk_out_konut.isChecked()
                        and (p_sp["key_id"] in ("ibadet", "asm", "anaokulu") or p_sp.get("min_area", 2500.0) <= 2500.0)
                        and poly_area >= 5500.0
                    ):
                        facility_lot_m2 = min(p_sp.get("max_single", 3000.0), max(p_sp.get("min_area", 2500.0), 2500.0))
                        park_buf_m2 = min(2000.0, max(1200.0, poly_area * 0.12))
                        house_rem_m2 = poly_area - facility_lot_m2 - park_buf_m2
                        spl_parts = split_polygon_by_ratios(pgeom, [facility_lot_m2, park_buf_m2, house_rem_m2], is_built_flags=[True, False, True])
                        if len(spl_parts) >= 3:
                            fac_geom, pbuf_geom, h_geom = spl_parts[0], spl_parts[1], spl_parts[2]
                            # 1. Facility
                            f_fac = QgsFeature(alloc_lyr.fields())
                            f_fac.setGeometry(fac_geom)
                            f_fac["kaynak_ada_id"] = pf.id()
                            f_fac["parca_no"] = 1
                            f_fac["onerilen_donati"] = p_cat
                            f_fac["alan_m2"] = round(fac_geom.area(), 1)
                            f_fac["hedef_nufus_etki"] = int(p_sp["unit_cap"])
                            f_fac["yol_erisim_skoru"] = round(primary["score"], 1)
                            f_fac["mevcut_durum_ozeti"] = f"Mevcut: {iyi_str}"
                            f_fac["planlama_aciklama_raporu"] = (
                                f"Ada #{pf.id()}: '{p_cat}' ihtiyacı ({int(fac_geom.area())} m²) kompakt parselle karşılanmış; "
                                f"büyük adanın gereksiz yeşile dönüştürülmesi engellenerek kalan alan konuta ayrılmıştır."
                            )
                            f_fac["yazar"] = PLUGIN_AUTHOR
                            out_alloc_features.append(f_fac)

                            fac_pt = fac_geom.centroid().asPoint()
                            fac_nid, fac_snap = graph.snap_polygon_to_node(fac_geom)
                            self._register_placed_facility(
                                p_cat, fac_pt, fac_nid, fac_snap, vac_dist_map, p_sp["net_r"],
                                int(p_sp["unit_cap"]), fac_geom.area(), newly_placed_points, existing_cap_by_type,
                                remaining_deficit_pop, unserved_res_nodes, allocated_summary,
                                dyn_fac_view=dyn_fac_view, dyn_stoch_profiles=dyn_stoch_profiles,
                                neighborhood_blocks=n_blocks, tot_n_pop=tot_n_pop, fid=pf.id(),
                            )
                            all_newly_placed_built_pts.append(fac_pt)

                            # 2. Park buffer
                            f_pb = QgsFeature(alloc_lyr.fields())
                            f_pb.setGeometry(pbuf_geom)
                            f_pb["kaynak_ada_id"] = pf.id()
                            f_pb["parca_no"] = 2
                            f_pb["onerilen_donati"] = park_cat
                            f_pb["alan_m2"] = round(pbuf_geom.area(), 1)
                            f_pb["hedef_nufus_etki"] = int(round(pbuf_geom.area() / 10.0))
                            f_pb["yol_erisim_skoru"] = 100.0
                            f_pb["mevcut_durum_ozeti"] = "Donatı Tampon Yeşili"
                            f_pb["planlama_aciklama_raporu"] = (
                                f"Ada #{pf.id()}: '{p_cat}' çevresinde {int(pbuf_geom.area())} m² yeşil tampon ayrılmıştır."
                            )
                            f_pb["yazar"] = PLUGIN_AUTHOR
                            out_alloc_features.append(f_pb)
                            pb_pt = pbuf_geom.centroid().asPoint()
                            pb_nid, pb_snap = graph.snap_polygon_to_node(pbuf_geom)
                            self._register_placed_facility(
                                park_cat, pb_pt, pb_nid, pb_snap, vac_dist_map, specs[park_cat]["net_r"],
                                int(round(pbuf_geom.area() / 10.0)), pbuf_geom.area(), newly_placed_points,
                                existing_cap_by_type, remaining_deficit_pop, unserved_res_nodes, allocated_summary,
                                dyn_fac_view=dyn_fac_view, dyn_stoch_profiles=dyn_stoch_profiles,
                                neighborhood_blocks=n_blocks, tot_n_pop=tot_n_pop, fid=pf.id(),
                            )

                            # 3. Remaining Housing
                            gerekce_intro = (
                                f"Ada #{pf.id()} ({int(poly_area)} m²): '{p_cat}' ({int(fac_geom.area())} m²) ve "
                                f"{int(pbuf_geom.area())} m² tampon park ayrıldıktan sonra kalan {int(h_geom.area())} m² alan; "
                                f"kompakt donatı yerleşimi sayesinde gelişme konutu olarak planlanmıştır"
                            )
                            self._evaluate_and_append_housing_parcel(
                                pf.id(), 3, h_geom, konut_out_lyr, out_konut_features, res_growth_results,
                                parcel_narrative_list, graph, specs, fac_by_type, newly_placed_points,
                                net_dist_maps, comm_pts, newly_placed_comm_pts, comm_dist_map,
                                tot_n_pop, f"Bitişik Donatılar ({p_cat})", gerekce_intro,
                            )

                            v_pt_f = QgsFeature(vac_pts_lyr.fields())
                            v_pt_f.setGeometry(QgsGeometry.fromPointXY(eval_pt))
                            v_pt_f["kaynak_ada_id"] = pf.id()
                            v_pt_f["alan_m2"] = round(poly_area, 1)
                            v_pt_f["atanan_donatilar"] = f"{p_cat} + Tampon Park + Önerilen Konut Alanı"
                            vac_pt_features.append(v_pt_f)
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
                        relief_target=rt, dyn_fac_view=dyn_fac_view,
                        dyn_stoch_profiles=dyn_stoch_profiles, neighborhood_blocks=n_blocks,
                        tot_n_pop=tot_n_pop, fid=pf.id(),
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
            konut_out_pr.addFeatures(out_konut_features)
            konut_out_lyr.updateExtents()
            passive_pr.addFeatures(out_passive_features)
            passive_lyr.updateExtents()
            comm_out_pr.addFeatures(out_comm_features)
            comm_out_lyr.updateExtents()
            vac_pts_pr.addFeatures(vac_pt_features)
            vac_pts_lyr.updateExtents()

            # 8. Internal Stochastic Balancing Summary for Planning Report (Zero Duplicate Map Layers)
            stochastic_allocations = []
            if stochastic_profiles:
                stochastic_allocations = AdaptiveAmenityWeightingEngine.evaluate_and_allocate_vacant_blocks(
                    vac_feats=list(vac_poly_lyr.getFeatures()),
                    block_profiles=stochastic_profiles,
                    graph=graph,
                    specs=specs,
                    fac_by_type=fac_by_type,
                    gross_density_pop_per_ha=180.0,
                    satisfaction_threshold=0.35,
                    randomize_vacant=True,
                    seed=42,
                )

            # 9. Auto-run Plan vs Actual Use Discrepancy Analysis if layers are selected
            old_lyr = self.cmb_old_plan.currentData()
            act_lyr = self.cmb_actual_use.currentData()
            if old_lyr and act_lyr:
                try:
                    self.run_plan_actual_diff(show_msg=False)
                except Exception:
                    pass

            layers_to_tag = [alloc_lyr, konut_out_lyr, passive_lyr, comm_out_lyr, res_out_lyr, fac_pts_lyr, vac_pts_lyr]
            for lyr_obj in layers_to_tag:
                md = lyr_obj.metadata()
                md.setAbstract(f"Generated by MPYY Urban Facility Optimization Plugin — Author: {PLUGIN_AUTHOR}")
                lyr_obj.setMetadata(md)

            self.apply_polygon_symbology(alloc_lyr, specs)
            self.apply_konut_symbology(konut_out_lyr)
            self.apply_non_mpyy_symbology(passive_lyr, comm_out_lyr)

            self._add_layers_to_grouped_tree(
                alloc_lyr, konut_out_lyr, passive_lyr, comm_out_lyr,
                res_out_lyr, fac_pts_lyr, vac_pts_lyr,
            )

            html_report = self.build_html_report(
                total_pop, specs, fac_by_type, existing_cap_by_type,
                unserved_pop_by_cat, overflow_pop_by_cat, bird_ok_road_fail_count,
                allocated_summary, non_mpyy_summary, parcel_narrative_list,
                res_growth_results=res_growth_results,
                stochastic_profiles=stochastic_profiles,
                stochastic_allocations=stochastic_allocations,
            )
            self.txt_report.setHtml(html_report)
            self.tabs.setCurrentIndex(2)
            self.progress.setValue(100)

            if show_msg:
                QMessageBox.information(self, t["done_title"], t["done_msg"])
        finally:
            self.btn_run.setEnabled(True)

    def _evaluate_and_append_housing_parcel(
        self,
        ada_id,
        parca_no,
        parcel_geom,
        konut_out_lyr,
        out_konut_features,
        res_growth_results,
        parcel_narrative_list,
        graph,
        specs,
        fac_by_type,
        newly_placed_points,
        net_dist_maps,
        comm_pts,
        newly_placed_comm_pts,
        comm_dist_map,
        neighborhood_pop,
        komsu_donatilar,
        gerekce_intro,
    ):
        """Evaluates road-network accessibility and carrying capacity for a proposed housing block."""
        eq = AdaptiveAmenityWeightingEngine.evaluate_housing_parcel_equilibrium(
            parcel_geom=parcel_geom,
            graph=graph,
            specs=specs,
            fac_by_type=fac_by_type,
            newly_placed_points=newly_placed_points,
            net_dist_maps=net_dist_maps,
            comm_pts=comm_pts,
            newly_placed_comm_pts=newly_placed_comm_pts,
            comm_dist_map=comm_dist_map,
            neighborhood_pop=neighborhood_pop,
            gross_density_pop_per_ha=180.0,
        )
        area_m2 = round(parcel_geom.area(), 1)
        gerekce = (
            f"{gerekce_intro} | Yol Ağı Erişim Skoru: {eq['yol_erisim_skoru']}/100 "
            f"({eq['kullanim_turu']}); Geri-Besleme: {eq['kapasite_geri_besleme']}."
        )
        f_kh = QgsFeature(konut_out_lyr.fields())
        f_kh.setGeometry(parcel_geom)
        f_kh["kaynak_ada_id"] = ada_id
        f_kh["parca_no"] = parca_no
        f_kh["kod"] = eq["kod"]
        f_kh["kullanim_turu"] = eq["kullanim_turu"]
        f_kh["alan_m2"] = area_m2
        f_kh["ongorulen_nufus"] = eq["ongorulen_nufus"]
        f_kh["yol_erisim_skoru"] = eq["yol_erisim_skoru"]
        f_kh["ilkokul_yol_m"] = eq["ilkokul_yol_m"]
        f_kh["ortaokul_yol_m"] = eq["ortaokul_yol_m"]
        f_kh["asm_yol_m"] = eq["asm_yol_m"]
        f_kh["park_yol_m"] = eq["park_yol_m"]
        f_kh["ticari_yol_m"] = eq["ticari_yol_m"]
        f_kh["kapasite_geri_besleme"] = eq["kapasite_geri_besleme"]
        f_kh["komsu_donatilar"] = komsu_donatilar
        f_kh["planlama_gerekcesi"] = gerekce
        f_kh["yazar"] = PLUGIN_AUTHOR
        out_konut_features.append(f_kh)
        parcel_narrative_list.append(gerekce)

        color_map = {
            "ONCELIKLI_KONUT": "#eab308",
            "UYGUN_KONUT": "#d97706",
            "SARTLI_KONUT": "#f97316",
        }
        res_growth_results.append({
            "ada_id": ada_id,
            "alan_m2": area_m2,
            "ongorulen_nufus": eq["ongorulen_nufus"],
            "konut_skoru": eq["yol_erisim_skoru"],
            "erisim_sinifi": eq["kullanim_turu"],
            "renk": color_map.get(eq["kod"], "#eab308"),
            "ilkokul_yol_m": eq["ilkokul_yol_m"],
            "ortaokul_yol_m": eq["ortaokul_yol_m"],
            "asm_yol_m": eq["asm_yol_m"],
            "park_yol_m": eq["park_yol_m"],
            "ticari_yol_m": eq["ticari_yol_m"],
            "planlama_gerekcesi": gerekce,
        })

    def _register_placed_facility(
        self, cat, pt, nid, snap_d, vac_dist_map, net_limit,
        added_cap, added_area, newly_placed_points, existing_cap_by_type,
        remaining_deficit_pop, unserved_res_nodes, allocated_summary,
        relief_target=None, dyn_fac_view=None, dyn_stoch_profiles=None,
        neighborhood_blocks=None, tot_n_pop=1.0, fid=0,
    ):
        newly_placed_points[cat].append((pt, nid, snap_d))
        existing_cap_by_type[cat] += added_cap
        remaining_deficit_pop[cat] = max(0.0, remaining_deficit_pop[cat] - added_cap)
        allocated_summary[cat]["count"] += 1
        allocated_summary[cat]["area"] += added_area
        allocated_summary[cat]["served_pop"] += added_cap

        if dyn_fac_view is not None:
            dyn_fac_view.setdefault(cat, []).append([fid, pt, added_cap, added_area, 0.0])

        if dyn_stoch_profiles and neighborhood_blocks:
            denom = max(float(tot_n_pop), 1.0)
            for r_id, _, _ in neighborhood_blocks:
                prof = dyn_stoch_profiles.get(r_id)
                if not prof:
                    continue
                cur_w = prof["ihtiyac_agirligi"].get(cat, 0.0)
                prof["ihtiyac_agirligi"][cat] = max(0.0, round(cur_w - 0.40, 3))
                cur_s = prof["mevcut_m2_kisi"].get(cat, 0.0)
                prof["mevcut_m2_kisi"][cat] = round(cur_s + (added_area / denom), 2)

        if relief_target is not None:
            relief_target["overflow_rem"] = max(0.0, relief_target["overflow_rem"] - added_cap)

        for node_entry in unserved_res_nodes[cat]:
            if not node_entry[4]:
                r_nid, r_snap = node_entry[2], node_entry[3]
                if r_nid is not None and r_nid in vac_dist_map:
                    if (vac_dist_map[r_nid] + r_snap) <= net_limit * 1.15:
                        node_entry[4] = True

    def _add_layers_to_grouped_tree(
        self, alloc_lyr, konut_out_lyr, passive_lyr, comm_out_lyr, res_out_lyr, fac_pts_lyr, vac_pts_lyr
    ):
        proj = QgsProject.instance()
        root = proj.layerTreeRoot()

        grp_mpyy_name = "MPYY_EK2_Sosyal_ve_Teknik_Donati_Alanlari"
        grp_konut_name = "MPYY_Onerilen_Konut_Alanlari"
        grp_non_mpyy_name = "MPYY_Disi_Tamamlayici_Alanlar (Pasif Yesil & Ticari Demo)"

        # Clean up previous output groups and stale map layers before re-populating
        for gname in (grp_mpyy_name, grp_konut_name, grp_non_mpyy_name):
            old_grp = root.findGroup(gname)
            if old_grp is not None:
                old_ids = old_grp.findLayerIds()
                root.removeChildNode(old_grp)
                if old_ids:
                    proj.removeMapLayers(old_ids)

        grp_mpyy = root.insertGroup(0, grp_mpyy_name)
        grp_konut = root.insertGroup(1, grp_konut_name)
        grp_non_mpyy = root.insertGroup(2, grp_non_mpyy_name)

        # 1. MPYY Amenity Group (chk_out_donati + optional centroids)
        if self.chk_out_donati.isChecked() and alloc_lyr is not None and alloc_lyr.featureCount() > 0:
            proj.addMapLayer(alloc_lyr, False)
            grp_mpyy.addLayer(alloc_lyr)

        if self.chk_show_centroids.isChecked():
            for c_lyr in (res_out_lyr, fac_pts_lyr, vac_pts_lyr):
                proj.addMapLayer(c_lyr, False)
                grp_mpyy.addLayer(c_lyr)

        # 2. Dedicated Proposed Housing Group (chk_out_konut)
        if self.chk_out_konut.isChecked() and konut_out_lyr is not None and konut_out_lyr.featureCount() > 0:
            proj.addMapLayer(konut_out_lyr, False)
            grp_konut.addLayer(konut_out_lyr)

        # 3. Non-MPYY Complementary Group (chk_out_passive & chk_out_comm)
        if self.chk_out_passive.isChecked() and passive_lyr is not None and passive_lyr.featureCount() > 0:
            proj.addMapLayer(passive_lyr, False)
            grp_non_mpyy.addLayer(passive_lyr)

        if self.chk_out_comm.isChecked() and comm_out_lyr is not None and comm_out_lyr.featureCount() > 0:
            proj.addMapLayer(comm_out_lyr, False)
            grp_non_mpyy.addLayer(comm_out_lyr)

        # Remove empty groups if no layers were added
        for grp in (grp_non_mpyy, grp_konut, grp_mpyy):
            if len(grp.children()) == 0:
                root.removeChildNode(grp)

    def apply_konut_symbology(self, layer):
        cats = [
            ("ONCELIKLI_KONUT", "Öncelikli Gelişme Konut Alanı (Erişim & Kapasite Onaylı)", "#eab308", "#854d0e"),
            ("UYGUN_KONUT", "Uygun Gelişme Konut Alanı (İyi Donatı Erişimi)", "#f59e0b", "#b45309"),
            ("SARTLI_KONUT", "Şartlı Gelişme Konut Alanı (Kapasite / Donatı Uyarısı)", "#f97316", "#9a3412"),
        ]
        renderer_cats = []
        for val, label, hex_fill, hex_border in cats:
            sym = QgsFillSymbol.createSimple({
                "color": hex_fill,
                "outline_color": hex_border,
                "outline_width": "0.75",
                "style": "solid",
            })
            sym.setOpacity(0.84)
            renderer_cats.append(QgsRendererCategory(val, sym, label))
        renderer = QgsCategorizedSymbolRenderer("kod", renderer_cats)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    def apply_polygon_symbology(self, layer, specs):
        categories = []
        used_names = set()
        for feat in layer.getFeatures():
            val = feat["onerilen_donati"]
            if val and val not in used_names and "konut" not in val.lower():
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

    def build_html_report(
        self, total_pop, specs, fac_by_type, existing_cap_by_type,
        unserved_pop_by_cat, overflow_pop_by_cat, bird_ok_road_fail_count,
        allocated_summary, non_mpyy_summary, parcel_narrative_list,
        res_growth_results=None,
        stochastic_profiles=None,
        stochastic_allocations=None,
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

        diff_html = ""
        if hasattr(self, "last_diff_summary") and self.last_diff_summary:
            s = self.last_diff_summary
            tot_a = max(s.get("toplam_alan_m2", 1), 1)
            diff_html = f"""
            <h3 style='margin-top:22px; color:#1e3a8a; border-bottom:2px solid #1e3a8a; padding-bottom:5px;'>
                Eski / Onaylı Plan Kararları ile Fiili Arazi Kullanımı Uyuşmazlık Raporu (MPYY Md. 26 Denetimi)
            </h3>
            <p style='font-size:12px; color:#334155;'>
                Önceki onaylı imar planında ayrılan arazi kullanım kararları ile sahadaki fiili durum mekânsal çakıştırma
                (spatial intersection) ile taranmıştır. Planda Ticaret/Donatı olup sahada gerçekleşmemiş ('Boş Ada') veya
                kamusal donatı alanının yapılaşmaya kurban edildiği ('DONATI_KAYBI') durumlar tespit edilmiştir.
            </p>
            <table border='1' cellspacing='0' cellpadding='6' width='100%' style='border-collapse:collapse; font-size:12px;'>
                <tr style='background-color:#1e293b; color:white;'>
                    <th>Uyuşmazlık / Gerçekleşme Durumu</th>
                    <th>Parsel Sayısı</th>
                    <th>Toplam Alan (m²)</th>
                    <th>Oran (%)</th>
                    <th>İmar Mevzuatı & MPYY Planlama Yorumu</th>
                </tr>
                <tr>
                    <td><span style='color:#059669; font-weight:bold;'>✔ Uyumlu / Gerçekleşmiş</span></td>
                    <td align='center'><b>{s.get('uyumlu_adet', 0)}</b></td>
                    <td align='center'>{s.get('uyumlu_m2', 0):,.1f} m²</td>
                    <td align='center'>%{s.get('uyumlu_m2', 0) / tot_a * 100:.1f}</td>
                    <td>Plan kararı sahada aynen hayata geçmiştir.</td>
                </tr>
                <tr style='background-color:#fef3c7;'>
                    <td><span style='color:#d97706; font-weight:bold;'>⏳ Gerçekleşmemiş (Boş Ada / Arsa)</span></td>
                    <td align='center'><b>{s.get('bos_ada_adet', 0)}</b></td>
                    <td align='center'>{s.get('bos_ada_m2', 0):,.1f} m²</td>
                    <td align='center'>%{s.get('bos_ada_m2', 0) / tot_a * 100:.1f}</td>
                    <td>Planda Ticaret veya Donatı öngörülmüş ancak yapılaşmamış; öncelikli rezerv müdahale alanıdır.</td>
                </tr>
                <tr>
                    <td><span style='color:#0d9488; font-weight:bold;'>🌳 Gerçekleşmemiş (Açık Alan / Park)</span></td>
                    <td align='center'><b>{s.get('acik_alan_adet', 0)}</b></td>
                    <td align='center'>{s.get('acik_alan_m2', 0):,.1f} m²</td>
                    <td align='center'>%{s.get('acik_alan_m2', 0) / tot_a * 100:.1f}</td>
                    <td>Planda yapılaşma kararı varken fiiliyatta yeşil alan/park olarak değerlendirilmektedir.</td>
                </tr>
                <tr style='background-color:#fee2e2;'>
                    <td><span style='color:#dc2626; font-weight:bold;'>✖ Aykırı Dönüşüm / Donatı Kaybı</span></td>
                    <td align='center'><b>{s.get('donati_kaybi_adet', 0)}</b></td>
                    <td align='center'>{s.get('donati_kaybi_m2', 0):,.1f} m²</td>
                    <td align='center'>%{s.get('donati_kaybi_m2', 0) / tot_a * 100:.1f}</td>
                    <td><b>DİKKAT:</b> Plandaki kamusal donatı sahadaki yapılaşmayla yok olmuştur; MPYY Md. 26 gereği eşdeğer alan tahsisi zorunludur!</td>
                </tr>
                <tr>
                    <td><span style='color:#2563eb; font-weight:bold;'>🔄 Fonksiyon Değişimi</span></td>
                    <td align='center'><b>{s.get('fonksiyon_degisimi_adet', 0)}</b></td>
                    <td align='center'>{s.get('fonksiyon_degisimi_m2', 0):,.1f} m²</td>
                    <td align='center'>%{s.get('fonksiyon_degisimi_m2', 0) / tot_a * 100:.1f}</td>
                    <td>Farklı bir kentsel fonksiyon gelişmiştir.</td>
                </tr>
            </table>
            """

        res_growth_html = ""
        if res_growth_results:
            rg_rows = ""
            for rg in res_growth_results:
                badge_bg = rg["renk"]
                sch_str = f"{int(rg['ilkokul_yol_m'])} m" if rg['ilkokul_yol_m'] > 0 else "Uzak / Yok"
                asm_str = f"{int(rg['asm_yol_m'])} m" if rg['asm_yol_m'] > 0 else "Uzak / Yok"
                park_str = f"{int(rg['park_yol_m'])} m" if rg['park_yol_m'] > 0 else "Uzak / Yok"
                comm_str = f"{int(rg['ticari_yol_m'])} m" if rg['ticari_yol_m'] > 0 else "Uzak / Yok"
                rg_rows += f"""
                <tr>
                    <td align='center'><b>Ada #{rg['ada_id']}</b></td>
                    <td align='center'>{rg['alan_m2']:,.1f} m²</td>
                    <td align='center'><b>~{rg['ongorulen_nufus']:,} kişi</b></td>
                    <td align='center'>{sch_str}</td>
                    <td align='center'>{asm_str}</td>
                    <td align='center'>{park_str}</td>
                    <td align='center'>{comm_str}</td>
                    <td align='center'><span style='display:inline-block;padding:2px 8px;border-radius:3px;background:{badge_bg};color:#ffffff;font-weight:bold;'>{rg['konut_skoru']}/100</span></td>
                    <td><b>{rg['erisim_sinifi']}</b><br><small style='color:#475569;'>{rg['planlama_gerekcesi']}</small></td>
                </tr>
                """

            res_growth_html = f"""
            <h3 style='margin-top:22px; color:#b45309; border-bottom:2px solid #b45309; padding-bottom:5px;'>
                Donatı Erişilebilirlik Tabanlı Önerilen Konut Adaları ve Kapasite Denge Raporu
            </h3>
            <p style='font-size:12px; color:#334155;'>
                <b>Temel Planlama İlkesi:</b> Gelişme Konut Alanları dışarıya hizmet yarıçapı üreten bir donatı değil,
                temel kamusal donatılardan (İlkokul 500m, Sağlık Ocağı 500m, Park 500m, Ortaokul 1000m, Ticaret 800m)
                yaya yol ağı üzerinden hizmet <b>ALAN</b> talep birimleridir. Bu nedenle konut adası yer seçimi tahmini değil;
                yol ağı yürüme mesafeleri ve mevcut tesislerin kapasite aşım riski (<i>C<sub>safe</sub></i>) denetlenerek
                çok kriterli yer seçimi skoru (<i>S<sub>res</sub></i> &isin; [0, 100]) ile bilimsel olarak gerekçelendirilmiştir.
            </p>
            <table border='1' cellspacing='0' cellpadding='6' width='100%' style='border-collapse:collapse; font-size:12px;'>
                <tr style='background-color:#78350f; color:white;'>
                    <th>İmar Adası</th>
                    <th>Alan (m²)</th>
                    <th>Öngörülen Nüfus (180 k/ha)</th>
                    <th>İlkokul (Yol m)</th>
                    <th>Sağlık (ASM Yol m)</th>
                    <th>Park (Yol m)</th>
                    <th>Ticaret (Yol m)</th>
                    <th>Erişim Skoru</th>
                    <th>Planlama Kararı ve Gerekçesi</th>
                </tr>
                {rg_rows}
            </table>
            """

        stoch_html = ""
        if stochastic_profiles or stochastic_allocations:
            sp_rows = ""
            if stochastic_profiles:
                sorted_profiles = sorted(stochastic_profiles.values(), key=lambda x: x.get("stokastik_sira", 0))
                for prof in sorted_profiles:
                    ada_id = prof["ada_id"]
                    pop = prof["nufus"]
                    sat = prof["donati_yeterlilik_yuzdesi"]
                    top_need = prof["en_oncelikli_ihtiyac"]
                    top_w = prof["oncelikli_agirlik"]
                    sira = prof["stokastik_sira"]

                    m2_dict = prof["mevcut_m2_kisi"]
                    w_dict = prof["ihtiyac_agirligi"]
                    details_str = []
                    for c_name, m2_val in m2_dict.items():
                        w_val = w_dict.get(c_name, 0.0)
                        details_str.append(f"{c_name}: {m2_val:.1f} m²/k (Açık: %{int(w_val*100)})")
                    detail_text = " | ".join(details_str[:4])

                    sat_color = "#16a34a" if sat >= 70 else ("#d97706" if sat >= 40 else "#dc2626")

                    sp_rows += f"""
                    <tr>
                        <td align='center'><b>#{sira}</b></td>
                        <td align='center'><b>Ada #{ada_id}</b></td>
                        <td align='center'>{prof['area_m2']:,.1f} m²</td>
                        <td align='center'><b>{int(pop):,} kişi</b></td>
                        <td align='center' style='color:{sat_color}; font-weight:bold;'>%{sat:.1f}</td>
                        <td align='center'><span style='color:#b91c1c; font-weight:bold;'>{top_need} (%{int(top_w*100)})</span></td>
                        <td><small>{detail_text}</small></td>
                    </tr>
                    """

            sa_rows = ""
            if stochastic_allocations:
                sorted_alloc = sorted(stochastic_allocations, key=lambda x: x.get("stokastik_sira", 0))
                for sa in sorted_alloc:
                    s_id = sa["ada_id"]
                    s_area = sa["alan_m2"]
                    s_sira = sa["stokastik_sira"]
                    s_kullanim = sa["atanan_kullanim"]
                    s_pop = sa["ongorulen_nufus"]
                    s_kod = sa["kod"]
                    s_sat = sa["donati_yeterlilik_yuzdesi"]
                    s_fb = sa["feedback_durumu"]
                    s_just = sa["planlama_gerekcesi"]

                    badge_color = "#0284c7" if "DONATI" in s_kod else ("#eab308" if "OK" in s_kod else "#f97316")

                    sa_rows += f"""
                    <tr>
                        <td align='center'><b>#{s_sira}</b></td>
                        <td align='center'><b>Ada #{s_id}</b></td>
                        <td align='center'>{s_area:,.1f} m²</td>
                        <td align='center'><span style='display:inline-block;padding:2px 8px;border-radius:3px;background:{badge_color};color:white;font-weight:bold;'>{s_kullanim}</span></td>
                        <td align='center'><b>{s_pop:,} kişi</b></td>
                        <td align='center'>%{s_sat:.1f}</td>
                        <td align='center'><b>{s_fb}</b></td>
                        <td><small>{s_just}</small></td>
                    </tr>
                    """

            stoch_html = f"""
            <h3 style='margin-top:24px; color:#1e1b4b; border-bottom:2px solid #4338ca; padding-bottom:5px;'>
                Kentsel Donatı İhtiyaç Ağırlıkları, Stokastik Tarama ve Kapasite Dengeleme Raporu
            </h3>
            <p style='font-size:12px; color:#334155; line-height:1.6;'>
                <b>Bilimsel Yöntem ve Mekânsal Dengeleme İlkeleri:</b><br>
                <b>1. Konut Adası Başına Kişi Başı Donatı Açığı ve İhtiyaç Ağırlığı Formülü:</b>
                Her konut adası (<i>i</i>) için yürüme mesafesinde erişilebilen mevcut tesis alanı kişi başına (<i>s<sub>i,k</sub></i>) hesaplanır ve
                yönetmelik standardı (<i>T<sub>k</sub></i>, örn. Park 10 m², İlkokul 2 m², Ortaokul 2 m², Sağlık 0.75 m²)
                ile karşılaştırılarak ihtiyaç açığı ağırlığı belirlenir:
                <br><br>
                <code style='background:#f1f5f9; padding:4px 8px; border-radius:4px; font-weight:bold;'>
                W<sub>i,k</sub> = max(0, (T<sub>k</sub> &minus; s<sub>i,k</sub>) / T<sub>k</sub>) &isin; [0.0, 1.0]
                </code>
                <br><br>
                Örneğin bir adada 5 m² park (ihtiyaç 10 m²) ve 0.5 m² ilkokul (ihtiyaç 2 m²) varsa;
                ilkokul açığı %75 (<i>W</i> = 0.75) iken park açığı %50 (<i>W</i> = 0.50)'dir. Sistem en yüksek ağırlığa sahip fonksiyona öncelik verir.
                <br><br>
                <b>2. Rastlantısal / Stokastik Tarama (Unbiased Spatial Order):</b>
                Adalar coğrafi sıralama veya katman kimlik sırasına göre taranırsa kuzeydeki veya ilk adalar tüm donatıları tüketip güneydekileri mahrum bırakır (mekânsal yanlılık).
                Bu nedenle konut adaları ve boş parseller stokastik (rastlantısal permütasyon) dizilimle işlenir; her ada eşit şansla taranır, denetlenen ada sisteme işlenerek bir sonrakine geçilir.
                <br><br>
                <b>3. Boş İmar Adaları Çift Rolü (Donatı vs Gelişme Konut):</b>
                Çevre konut adalarının açık ağırlığı yüksekse boş ada doğrudan en çok ihtiyaç duyulan donatıya (örn. İlkokul) tahsis edilir ve çevre adaların açığı dinamik olarak düşürülür.
                Eğer çevre donatılar yeterli ise alan 'Gelişme Konut Alanı' adayı olarak değerlendirilir.
                <br><br>
                <b>4. Kapasite ve Eşit Dağılım Geri-Beslemesi (Feedback Simulation):</b>
                Boş adaya konut önerildiğinde alana eklenecek nüfus (<i>P<sub>new</sub></i>) simülasyona sokulur. İlave nüfus sonrasında çevredeki okul, sağlık ve parkların kişi başı standartların altına düşüp düşmediği (<i>s<sub>k</sub>' &lt; T<sub>k</sub></i>) ve bina kapasite sınırları denetlenir; aşım yoksa 'Kapasite ve Denge Onaylı', aşım riski varsa 'Şartlı Gelişme Konut' olarak etiketlenir.
            </p>

            <h4 style='color:#312e81; margin-top:14px;'>Tablo 1: Konut Adaları Donatı m²/Kişi ve İhtiyaç Ağırlıkları (Stokastik Tarama)</h4>
            <table border='1' cellspacing='0' cellpadding='6' width='100%' style='border-collapse:collapse; font-size:12px;'>
                <tr style='background-color:#312e81; color:white;'>
                    <th>Sıra</th>
                    <th>Konut Adası</th>
                    <th>Alan (m²)</th>
                    <th>Nüfus</th>
                    <th>Donatı Yeterliliği</th>
                    <th>En Öncelikli İhtiyaç (Açık %)</th>
                    <th>Mevcut m²/kişi ve Açık Ağırlıkları</th>
                </tr>
                {sp_rows}
            </table>

            <h4 style='color:#065f46; margin-top:18px;'>Tablo 2: Boş İmar Adaları Stokastik Tahsis ve Geri-Besleme (Feedback) Denetimi</h4>
            <table border='1' cellspacing='0' cellpadding='6' width='100%' style='border-collapse:collapse; font-size:12px;'>
                <tr style='background-color:#065f46; color:white;'>
                    <th>Sıra</th>
                    <th>Boş İmar Adası</th>
                    <th>Alan (m²)</th>
                    <th>Atanan Kullanım</th>
                    <th>Öngörülen Nüfus</th>
                    <th>Çevre Yeterlilik</th>
                    <th>Geri-Besleme (Feedback) Durumu</th>
                    <th>Planlama Gerekçesi</th>
                </tr>
                {sa_rows}
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
                (1) Her konut adasının yol ağı üzerinden erişimi ve mevcut donatıların gerçek parsel büyüklüğüne dayalı kapasite yükü (<i>D<sub>j</sub> / C<sub>j</sub></i>) denetlenmiştir;
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
            {res_growth_html}
            {stoch_html}
            {diff_html}
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

        # Demo Layers for Tab 2: Eski Onaylı Plan vs Fiili Arazi Kullanımı
        old_plan_lyr = QgsVectorLayer(f"Polygon?crs={crs}", "eski_onayli_plan", "memory")
        opr = old_plan_lyr.dataProvider()
        opr.addAttributes([QgsField("plan_fonksiyonu", _QVAR_STRING)])
        old_plan_lyr.updateFields()

        actual_use_lyr = QgsVectorLayer(f"Polygon?crs={crs}", "mevcut_fiili_kullanim", "memory")
        apr = actual_use_lyr.dataProvider()
        apr.addAttributes([QgsField("fiili_kullanim", _QVAR_STRING)])
        actual_use_lyr.updateFields()

        demo_diff_parcels = [
            (base_x + 1150, base_y + 100, 100, 90, "Ticaret Alanı", "Boş Ada / Arsa"),
            (base_x + 1150, base_y + 250, 90, 85, "Ticaret Alanı", "Park ve Yeşil Alan"),
            (base_x + 1150, base_y + 400, 110, 90, "İlkokul Alanı", "Konut Alanı"),
            (base_x + 1150, base_y + 550, 95, 80, "Konut Alanı", "Konut Alanı"),
            (base_x + 1150, base_y + 700, 80, 80, "Park Alanı", "Park Alanı"),
        ]
        old_feats = []
        act_feats = []
        for bx, by, bw, bh, p_fn, a_fn in demo_diff_parcels:
            g = make_rect_poly(bx, by, bw, bh)
            f_old = QgsFeature(old_plan_lyr.fields())
            f_old.setGeometry(g)
            f_old["plan_fonksiyonu"] = p_fn
            old_feats.append(f_old)

            f_act = QgsFeature(actual_use_lyr.fields())
            f_act.setGeometry(g)
            f_act["fiili_kullanim"] = a_fn
            act_feats.append(f_act)

        opr.addFeatures(old_feats)
        old_plan_lyr.updateExtents()
        apr.addFeatures(act_feats)
        actual_use_lyr.updateExtents()

        QgsProject.instance().addMapLayer(net_lyr)
        QgsProject.instance().addMapLayer(vac_poly_lyr)
        QgsProject.instance().addMapLayer(res_lyr)
        QgsProject.instance().addMapLayer(old_plan_lyr)
        QgsProject.instance().addMapLayer(actual_use_lyr)

        self.populate_layers()


MPYYDialog = MPYYDonatiDialog
