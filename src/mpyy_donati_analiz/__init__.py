# -*- coding: utf-8 -*-
def classFactory(iface):
    from .mpyy_plugin import MPYYDonatiPlugin
    return MPYYDonatiPlugin(iface)
