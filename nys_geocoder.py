# -*- coding: utf-8 -*-
"""
/***************************************************************************
 NYSGeocoder
                                 A QGIS plugin
 Geocode street addresses in New York State
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2019-04-03
        git sha              : $Format:%H$
        copyright            : (C) 2019 by Keith Jenkins
        email                : kgj2@cornell.edu
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QProgressDialog
from qgis.core import (
        QgsProject,
        QgsCoordinateReferenceSystem,
        QgsVectorLayer,
        QgsPointXY,
        QgsFeature,
        QgsGeometry,
        QgsMarkerSymbol,
        QgsExpression,
        QgsExpressionContext,
        QgsMessageLog,
        QgsMapLayerProxyModel,
        QgsFieldProxyModel )
from qgis.gui import QgsMapLayerComboBox, QgsFieldComboBox

import requests
import time


# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .nys_geocoder_dialog import NYSGeocoderDialog
import os.path


class NYSGeocoder:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        self.project = QgsProject.instance()
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'NYSGeocoder_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&NYS Geocoder')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('NYSGeocoder', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToWebMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/nys_geocoder/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'NYS Geocoder'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginWebMenu(
                self.tr(u'&NYS Geocoder'),
                action)
            self.iface.removeToolBarIcon(action)


    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = NYSGeocoderDialog()

        # Set up the form for Table (single field)
        self.dlg.inputLayer.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.dlg.inputLayer.layerChanged.connect(self.dlg.expression.setLayer)
        self.dlg.inputLayer.layerChanged.connect(self.dlg.idField.setLayer)
        self.dlg.inputLayer.setCurrentIndex(-1)

        self.dlg.inputLayer_2.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.dlg.inputLayer_2.layerChanged.connect(self.dlg.street.setLayer)
        self.dlg.inputLayer_2.layerChanged.connect(self.dlg.city.setLayer)
        self.dlg.inputLayer_2.layerChanged.connect(self.dlg.zip.setLayer)
        self.dlg.inputLayer_2.layerChanged.connect(self.dlg.idField_2.setLayer)
        self.dlg.inputLayer_2.setCurrentIndex(-1)


        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:

            addresses = []

            # check which tab is active
            tab = self.dlg.tabWidget.currentIndex()
            if tab == 0:
                # single address
                singleAddress = self.dlg.singleAddress.text()
                addresses.append( (1, singleAddress) )

            elif tab == 1:
                # addresses from single field (or expression) of layer
                inputLayerName = self.dlg.inputLayer.currentText()
                inputLayer = QgsProject.instance().mapLayersByName(inputLayerName)[0]

                # get features, depending on "selected" checkbox
                if self.dlg.selectedOnly.isChecked():
                    features = inputLayer.getSelectedFeatures()
                else:
                    features = inputLayer.getFeatures()

                expression = self.dlg.expression.currentText()
                e = QgsExpression(expression)
                if e.hasParserError():
                    self.iface.messageBar().pushMessage('Error parsing expression')
                    return
                context = QgsExpressionContext()
                context.setFields(inputLayer.fields())
                e.prepare(context)

                idField = self.dlg.idField.currentField()

                for f in features:
                    context.setFeature(f)
                    address = e.evaluate(context)
                    if e.hasEvalError():
                        raise ValueError(e.evalErrorString())
                    addresses.append( (f[idField], address) )

            elif tab == 2:
                # addresses from multiple fields of layer
                inputLayerName = self.dlg.inputLayer_2.currentText()
                inputLayer = QgsProject.instance().mapLayersByName(inputLayerName)[0]

                # get features, depending on "selected" checkbox
                if self.dlg.selectedOnly_2.isChecked():
                    features = inputLayer.getSelectedFeatures()
                else:
                    features = inputLayer.getFeatures()

                expression = self.dlg.street.currentText()
                e = QgsExpression(expression)
                if e.hasParserError():
                    self.iface.messageBar().pushMessage('Error parsing expression')
                    return
                context = QgsExpressionContext()
                context.setFields(inputLayer.fields())
                e.prepare(context)

                cityField = self.dlg.city.currentField()
                zipField = self.dlg.zip.currentField()
                idField = self.dlg.idField_2.currentField()

                for f in features:
                    context.setFeature(f)
                    street = e.evaluate(context)
                    if e.hasEvalError():
                        raise ValueError(e.evalErrorString())
                    address = "{}, {}, {}".format(street, f[cityField], f[zipField])
                    addresses.append( (f[idField], address) )

            # Create a new memory Point layer
            layer_out = QgsVectorLayer("Point?crs=EPSG:4326&field=geocode_id:integer&field=geocode_address:string&field=geocode_score:integer&field=geocode_x:real&field=geocode_y:real",
                                       "NYS Geocoder results",
                                       "memory")

            # Set up the progress bar
            count = len(addresses)
            progress = QProgressDialog("Geocoding {} addresses...".format(count), 'Cancel', 0, count)
            progress.setWindowModality(2) # Qt.WindowModal

            for i, addrtuple in enumerate(addresses):
                # Show progress
                progress.setValue(i)
                if progress.wasCanceled():
                    break

                (id, addr) = addrtuple

                # Create request
                base_url = 'https://gisservices.its.ny.gov/arcgis/rest/services/Locators/Street_and_Address_Composite/GeocodeServer/findAddressCandidates'
                #base_url = 'http://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates'
                params = {'SingleLine':addr, 'maxLocations':1, 'outSR':'4326', 'f':'json'}

                time.process_time()
                response = requests.get(url=base_url, params=params)
                #QgsMessageLog.logMessage("{}ms to fetch {}".format(round(time.process_time()),response.url))
                response_json = response.json()

                # Handle the response. Only process if HTTP status code is 200. All other status codes imply an error.
                if response.status_code == 200:
                    # Check for candidates in the result
                    candidates = response_json['candidates']
                    if len(candidates) == 0:
                        QgsMessageLog.logMessage("No results found {}".format(response.json()))
                        # Try the fallback locator
                        base_url = 'https://gisservices.its.ny.gov/arcgis/rest/services/Locators/Street_NoNum_and_ZipCode_Composite/GeocodeServer/findAddressCandidates'
                        time.process_time()
                        response = requests.get(url=base_url, params=params)
                        QgsMessageLog.logMessage("{}ms to fetch {}".format(round(time.process_time()),response.url))
                        response_json = response.json()

                        if response.status_code == 200:
                            candidates = response_json['candidates']
                            if len(candidates) == 0:
                                QgsMessageLog.logMessage("No results found {}".format(response.json()))
                                continue
                        else:
                            # Notify user if smth went wrong during the request
                            self.iface.messageBar().pushMessage("NYS Geocoder2 error",
                                     "The request was not processed succesfully!\n\n"
                                     "HTTP status code: {}\nMessage: {}".format(response.status_code, response.json()),
                                     1)

                    # Get location
                    location = candidates[0]['location']
                    x = float(location['x'])
                    y = float(location['y'])
                    address = candidates[0]['address']
                    score = candidates[0]['score']

                    # Build the output feature
                    point_out = QgsPointXY(x, y)
                    feature = QgsFeature()
                    feature.setGeometry(QgsGeometry.fromPointXY(point_out))
                    feature.setAttributes([id, address, score, x, y])  # Expects an ordered list as per attribute creation of layer

                    # Add feature to layer
                    layer_out.dataProvider().addFeature(feature)

                else:
                    # Notify user if smth went wrong during the request
                    self.iface.messageBar().pushMessage("NYS Geocoder error",
                                     "The request was not processed succesfully!\n\n"
                                     "HTTP status code: {}\nMessage: {}".format(response.status_code, response.json()),
                                     1)


            # Update Extents, set the style, add the layer to the canvas and zoom to layer
            layer_out.updateExtents()
            symbol = QgsMarkerSymbol.createSimple({'name':'circle', 'color':'#ffcc00', 'size':'3'})
            layer_out.renderer().setSymbol(symbol)
            self.project.addMapLayer(layer_out)
            self.iface.zoomToActiveLayer()
            self.iface.messageBar().clearWidgets()


