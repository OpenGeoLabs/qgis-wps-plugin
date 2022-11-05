# -*- coding: utf-8 -*-
"""
/***************************************************************************
                                 A QGIS WFS plugin

 This plugin connect to WPS via OWSLib.

 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2020-08-04
        git sha              : $Format:%H$
        copyright            : (C) 2020 by OpenGeoLabs
        email                : info@opengeolabs.cz
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

import os

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt import QtGui
from qgis.utils import iface
from qgis.core import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import *
from qgis.gui import *

import importlib

from .connect import *
from owslib.wps import ComplexDataInput

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'wps_dialog_base.ui'))

DATE_TIME_KEYWORDS = ['date', 'datum']

class WpsDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, iface, parent=None):
        """Constructor."""
        super(WpsDialog, self).__init__(parent)
        self.iface = iface
        self.setupUi(self)

        self.verticalLayoutInputs = QVBoxLayout(self.tabInputs)
        self.verticalLayoutOutputs = QVBoxLayout(self.tabOutputs)
        self.pushButtonExecute.clicked.connect(self.executeProcess)
        self.handleOutputComboBox = None
        self.input_items = {}
        self.input_items_all = []
        self.output_items_all = []
        self.processes = []
        self.only_selected = {}

    def showProcessDescription(self, index):
        self.textEditProcessDescription.setText(
            "[" + self.processes[index].identifier + "]: " +
            self.processes[index].abstract
        )

    def processSelected(self):
        current_index = self.comboBoxProcesses.currentIndex()
        self.show_process_description(current_index)
        self.loadProcess()

    def getAllLayersInput(self):
        return QgsMapLayerComboBox(self.tabInputs)

    def getLayerFields(self):
        return QgsFieldComboBox(self.tabInputs)

    def setMapLayerCmbBoxConnect(self):
        for param, widget in self.input_items.items():
            if isinstance(widget, QgsMapLayerComboBox):
                widget.currentIndexChanged.connect(self.setLayerToQgsFieldComboBox)

    def setLayerToQgsFieldComboBox(self):
        # TODO not generic - only last items will be connected
        layer = None
        field_cmb_box = None
        for param, widget in self.input_items.items():
            if isinstance(widget, QgsFieldComboBox):
                field_cmb_box = widget
            if isinstance(widget, QgsMapLayerComboBox):
                layer = widget.currentLayer()
            if layer is not None:
                layer.selectionChanged.connect(self.onLayerSelection)
        if layer is not None and field_cmb_box is not None:
            field_cmb_box.setLayer(layer)

    def isDateInput(self, identifier, title):
        for item in DATE_TIME_KEYWORDS:
            if item in identifier or "date" in title:
                return True
        return False

    def onLayerSelection(self, selected_features):
        for param, widget in self.input_items.items():
            if isinstance(widget, QgsMapLayerComboBox):
                layer = widget.currentLayer()
                selection_widget = self.only_selected[param]
                if layer == self.sender():
                    selection_widget.setChecked(len(selected_features) > 0)
                    selection_widget.setEnabled(len(selected_features) > 0)

    def getOnlySelectedInput(self, identifier):
        input_item = QCheckBox(self.tabInputs)
        input_item.setText(self.tr("Only selected features"))
        for param, widget in self.input_items.items():
            if isinstance(widget, QgsMapLayerComboBox):
                if param == identifier:
                    layer = widget.currentLayer()
                    selected = layer is not None and layer.selectedFeatureCount() > 0
                    input_item.setChecked(selected)
                    input_item.setEnabled(selected)
                    break
        self.only_selected[str(identifier)] = input_item
        self.input_items_all.append(input_item)
        hbox_layout = QHBoxLayout(self.tabInputs)
        hbox_layout.addWidget(input_item)
        return hbox_layout

    def _getAllowedValuesInput(self, values, min_occurs, max_occurs, default_value):
        """Create select dialogue maybe with checkboxes for multiple values
        """
        input_item = QgsCheckableComboBox()
        input_item.insertItems(0, values)
        if default_value:
            try:
                input_item.setCheckedItems(default_value.split(','))
            except Exception as e:
                self.appendLogMessage(
                    self.tr("ERROR: Unable to set default value {}".format(default_value)
                ))

        def items_checked(checked):
            """Make sure, there is only max_occurs checked items
            """

            if max_occurs and len(checked) > max_occurs:
                input_item.deselectAllOptions()
                input_item.setCheckedItems(checked[:-1])

        input_item.checkedItemsChanged.connect(items_checked)
        return input_item

    def getInput(self, identifier, title, data_type, default_value,
            min_occurs, max_occurs, allowed_values):
        # TODO check types
        input_item = None
        if data_type == 'ComplexData':
            input_item = self.getAllLayersInput()
        else:
            input_item = QLineEdit(self.tabInputs)
            if "column" in identifier:
                input_item = self.getLayerFields()
            elif self.isDateInput(identifier, title):
                input_item = QgsDateTimeEdit(self.tabInputs)
            elif allowed_values:
                input_item = self._getAllowedValuesInput(allowed_values,
                                                         min_occurs, max_occurs, default_value)
            else:
                if str(default_value) == 'None':
                    input_item.setText('')
                else:
                    input_item.setText(str(default_value))
        hbox_layout, label, label_id = self.getInputItemContainer(
            identifier, input_item, min_occurs, title
        )
        # TODO check if there is not a better way
        self.input_items[str(identifier)] = input_item
        self.input_items_all.append(input_item)
        self.input_items_all.append(label)
        self.input_items_all.append(label_id)
        return hbox_layout

    def getInputItemContainer(self, identifier, input_item, min_occurs, title):
        hbox_layout = QHBoxLayout(self.tabInputs)
        vbox_layout = QVBoxLayout(self.tabInputs)
        label_id = QLabel(self.tabInputs)
        label_id.setFixedWidth(200)
        label_id.setWordWrap(True)
        label_id.setText("[" + str(identifier) + "]")
        if min_occurs > 0:
            label_id.setStyleSheet("QLabel { color : red; }");
        vbox_layout.addWidget(label_id)
        label = QLabel(self.tabInputs)
        label.setFixedWidth(200)
        label.setText(str(title))
        label.setWordWrap(True)
        vbox_layout.addWidget(label)
        hbox_layout.addLayout(vbox_layout)
        hbox_layout.addWidget(input_item)
        return hbox_layout, label, label_id

    def setServiceUrl(self, url):
        self.service_url = url

    def setProcessIdentifier(self, id):
        self.process_identifier = id

    def loadProcess(self):
        if self.process_identifier is not None and self.service_url is not None:
            self.setCursor(Qt.WaitCursor)
            self.itemRemove(self.input_items_all)
            self.progressBar.setValue(0)
            self.textEditLog.setText(self.tr("Loading process {}...".format(self.process_identifier)))
            self.__load_process = GetProcess()
            self.__load_process.setUrl(self.service_url)
            self.__load_process.setIdentifier(self.process_identifier)
            self.__load_process.statusChanged.connect(self.onLoadProcessResponse)
            self.__load_process.start()

    def itemRemove(self, array):
        for item_to_remove in array:
            item_to_remove.setParent(None)

    def setInputItems(self, data):
        self.input_items = {}
        self.pushButtonExecute.setEnabled(True)
        for x in data.dataInputs:

            input_item = self.getInput(
                x.identifier, x.title, x.dataType, x.defaultValue,
                x.minOccurs, x.maxOccurs, x.allowedValues
            )

            self.verticalLayoutInputs.addLayout(input_item)
            if x.dataType == 'ComplexData':
                only_selected_item = self.getOnlySelectedInput(x.identifier)
                self.verticalLayoutInputs.addLayout(only_selected_item)
        self.tabInputs.setLayout(self.verticalLayoutInputs)
        self.setLayerToQgsFieldComboBox()
        self.setMapLayerCmbBoxConnect()

    def getOutput(self, identifier, title, mime_type):
        hbox_layout = QHBoxLayout(self.tabOutputs)
        label = QLabel(self.tabOutputs)
        label.setFixedWidth(200)
        label.setText(str(title))
        label.setWordWrap(True)
        hbox_layout.addWidget(label)
        label_mime_type = QLabel(self.tabOutputs)
        label_mime_type.setWordWrap(True)
        label_mime_type.setText("[" + str(mime_type) + "]")
        hbox_layout.addWidget(label_mime_type)
        self.output_items_all.append(label)
        self.output_items_all.append(label_mime_type)
        return hbox_layout

    def getOutputOptionsPostprocessing(self):
        hbox_layout = QHBoxLayout(self.tabOutputs)
        label = QLabel(self.tabOutputs)
        label.setFixedWidth(200)
        label.setText(self.tr('Handle output'))
        hbox_layout.addWidget(label)
        self.handleOutputComboBox = QComboBox()
        self.handleOutputComboBox.addItem(self.tr("Load into map"))
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'postprocessing', self.getStrippedUrl(), self.process_identifier + ".py")
        if os.path.exists(path):
            self.handleOutputComboBox.addItem(self.tr("Postprocess"))
            self.handleOutputComboBox.setCurrentIndex(1)
        hbox_layout.addWidget(self.handleOutputComboBox)
        self.output_items_all.append(label)
        self.output_items_all.append(self.handleOutputComboBox)
        return hbox_layout

    def setOutputItems(self, data):
        self.itemRemove(self.output_items_all)
        for x in data.processOutputs:
            output_item = self.getOutput(x.identifier, x.title, x.mimeType)
            self.verticalLayoutOutputs.addLayout(output_item)
            output_item_handle = self.getOutputOptionsPostprocessing()
            self.verticalLayoutOutputs.addLayout(output_item_handle)
        self.tabOutputs.setLayout(self.verticalLayoutOutputs)

    def onLoadProcessResponse(self, response):
        if response.status == 200:
            if response.data.abstract is not None:
                self.setInputItems(response.data)
                self.setOutputItems(response.data)
                self.appendLogMessage(self.tr("Process {} loaded".format(self.process_identifier)))
            else:
                self.appendLogMessage(self.tr("Error loading process {}".format(self.process_identifier)))
        else:
            QMessageBox.information(None, self.tr("ERROR:"),
                                    self.tr("Error loading process {}".format(self.process_identifier)))
            self.appendLogMessage(self.tr("Error loading process {}".format(self.process_identifier)))
        self.setCursor(Qt.ArrowCursor)

    def executeProcess(self):
        self.setCursor(Qt.WaitCursor)
        # Async call: https://ouranosinc.github.io/pavics-sdi/tutorials/wps_with_python.html
        myinputs = []
        for param, widget in self.input_items.items():
            if isinstance(widget, QgsMapLayerComboBox):
                # TODO check input type and export into it (GML, GeoPackage, etc.)
                layer = widget.currentLayer()
                if layer is None:
                    iface.messageBar().pushMessage(
                        self.tr("Error"), self.tr("There is not any layer"), level=Qgis.Critical
                    )
                    self.resetOnError()
                    return
                if layer.type() == QgsMapLayer.VectorLayer:
                    tmp_ext = '.gml'
                    tmp_frmt = 'GML'
                else:
                    iface.messageBar().pushMessage("Error", "Unsupported map layer type", level=Qgis.Critical)
                    self.resetOnError()
                    return

                tmp_file = QgsProcessingUtils.generateTempFilename(
                    self.process_identifier + '_' + param) + tmp_ext
                only_selected = False
                if param in self.only_selected:
                    only_selected = self.only_selected[param].isChecked()
                    # check number of selected features
                    if only_selected and layer.selectedFeatureCount() < 1:
                        iface.messageBar().pushMessage(
                            self.tr("Warning"),
                            self.tr("No features selected"), level=Qgis.Warning
                        )
                        self.resetOnError()
                        return

                options = QgsVectorFileWriter.SaveVectorOptions()
                options.driverName = tmp_frmt
                options.onlySelectedFeatures = only_selected
                options.layerName = layer.name().replace('-', '_')
                QgsVectorFileWriter.writeAsVectorFormatV3(
                    layer,
                    tmp_file,
                    QgsProject.instance().transformContext(),
                    options
                )
                with open(tmp_file) as fd:
                    cdi = ComplexDataInput(fd.read())
                myinputs.append((param, cdi))
            elif isinstance(widget, QgsFieldComboBox):
                myinputs.append((param, widget.currentField()))
            elif isinstance(widget, QgsDateTimeEdit):
                myinputs.append((param, widget.date().toString('yyyy-MM-dd')))
            elif isinstance(widget, QgsCheckableComboBox):
                for val in widget.checkedItems():
                    myinputs.append((param, val))
            else:
                # TODO check also other types than just QLineEdit
                if widget.text() != 'None':
                    myinputs.append((param, widget.text()))
        self.appendLogMessage(self.tr("Executing {} process ...".format(self.process_identifier)))
        self.__execute_process = ExecuteProcess()
        self.__execute_process.setUrl(self.service_url)
        self.__execute_process.setIdentifier(self.process_identifier)
        self.__execute_process.setInputs(myinputs)
        self.__execute_process.statusChanged.connect(self.onExecuteProcessResponse)
        self.__execute_process.start()

    # Only for testing purposes
    def postprocess(self, inputs, response):
        csv_uri = 'file:///' + response.filepath + '?delimiter=,'
        csv = QgsVectorLayer(csv_uri, "process {} output".format('d-rain-csv'), 'delimitedtext')
        QgsProject.instance().addMapLayer(csv)
        layer = None
        layerField = None
        csvField = None
        for param, widget in inputs.items():
            if isinstance(widget, QgsMapLayerComboBox):
                # TODO check input type and export into it (GML, GeoPackage, etc.)
                layer = widget.currentLayer()
            elif isinstance(widget, QgsFieldComboBox):
                layerField = widget.currentField()
        csvField = csv.fields()[0].name()

        if layer is not None and layerField is not None and csv is not None and csvField is not None:
            import processing
            parameters = { 'DISCARD_NONMATCHING' : False, 'FIELD' : layerField, 'FIELDS_TO_COPY' : [], 'FIELD_2' : csvField, 'INPUT' : layer.source(), 'INPUT_2' : csv.source(), 'METHOD' : 1, 'OUTPUT' : 'TEMPORARY_OUTPUT', 'PREFIX' : '' }
            result = processing.runAndLoadResults('qgis:joinattributestable', parameters)

    def getStrippedUrl(self):
        return self.service_url.split('//')[1].replace('.', '_').replace('/', '_')

    def postprocessOutput(self, process_identifier, inputs, response):
        current_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
        current_module_name = os.path.splitext(os.path.basename(current_dir))[0]
        module = importlib.import_module(".postprocessing." + self.getStrippedUrl() + "." + process_identifier, package=current_module_name)
        for member in dir(module):
            if member == 'WPSPostprocessing':
                handler_class = getattr(module, member)
                current_source = handler_class()
                return current_source.run(inputs, response)
                # only for testig purposes
                # self.postprocess(inputs, response)

    def processNotKnownOutput(self, item):
        QMessageBox.information(
            None, self.tr("INFO:"),
            self.tr("Process sucesfully finished. The output can not be loaded into map. "
                    "Printing output into log."))
        self.appendLogMessage(self.tr("Showing content of the output"))
        self.appendFileContentIntoLog(item)

    def getCsvLayer(self, file_path, layer_name):
        return QgsVectorLayer(
            'file:///' + file_path + '?delimiter=,',
            layer_name, 'delimitedtext'
        )

    def getZippedVectorLayer(self, file_path, layer_name):
        return QgsVectorLayer(
            '/vsizip/' + file_path,
            layer_name,
            "ogr")

    def getVectorLayer(self, file_path, layer_name):
        return QgsVectorLayer(
            file_path,
            layer_name,
            "ogr")

    def getRasterLayer(self, file_path, layer_name):
        return QgsRasterLayer(
            file_path,
            layer_name
        )

    def processOutput(self, response):
        process_identifier = self.process_identifier
        if self.handleOutputComboBox is not None and self.handleOutputComboBox.currentIndex() == 1:
            result = self.postprocessOutput(process_identifier, self.input_items, response)
            if result is not None:
                self.appendLogMessage(self.tr("Postprocessing successfully finished"))
            else:
                QMessageBox.information(None, self.tr("INFO:"), self.tr("Postprocessing ended with error."))
                self.appendLogMessage(self.tr("ERROR: Postprocessing ended with error."))
        else:
            for identifier, item in response.output.items():
                layer = None
                layer_name = "{} {}".format(process_identifier, identifier)
                if layer is None or not layer.isValid():
                    layer = self.getZippedVectorLayer(item.filepath, layer_name)
                if layer is None or not layer.isValid():
                    layer = self.getVectorLayer(item.filepath, layer_name)
                if layer is None or not layer.isValid():
                    layer = self.getRasterLayer(item.filepath, layer_name)
                if (layer is None or not layer.isValid()) and item.mimetype == 'application/csv':
                    layer = self.getCsvLayer(item.filepath, layer_name)
                if layer is not None and layer.isValid():
                    QgsProject.instance().addMapLayer(layer)
                    self.appendLogMessage(self.tr("Output data loaded into the map"))
                else:
                    self.processNotKnownOutput(item)

    def resetOnError(self):
        self.setCursor(Qt.ArrowCursor)
        self.progressBar.setValue(0)

    def onExecuteProcessResponse(self, response):
        process_identifier = self.process_identifier
        if response.status == 200:
            self.appendLogMessage(self.tr("Process {} successfully finished".format(process_identifier)))
            self.processOutput(response)
            self.setCursor(Qt.ArrowCursor)
        if response.status == 201:
            self.appendLogMessage(self.tr("Process '{}': {}% {}".format(
                process_identifier, response.data['percent'], response.data['message'], 
            )))
            self.progressBar.setValue(int(response.data['percent']))
        if response.status == 500:
            self.appendLogMessage(self.tr("Process {} failed".format(process_identifier)))
            self.setCursor(Qt.ArrowCursor)
            # QMessageBox.information(None, self.tr("ERROR:"),
            #                         self.tr("Error executing process {}".format(process_identifier)))
            self.appendLogMessage(self.tr("Error executing process {}".format(process_identifier)))
            self.appendLogMessage(response.data)
            self.iface.messageBar().pushMessage(
                self.tr("Error in {}").format(process_identifier), response.data, level=Qgis.Critical
            )

    def appendFileContentIntoLog(self, item):
        # with (open(item.filepath, "r")) as f:
        #     self.appendLogMessage(str(f.read()))
        self.appendLogMessage("File: {} (mimetype: {})".format(item.filepath, item.mimetype))

    def appendLogMessage(self, msg):
        self.textEditLog.append(msg)
        self.textEditLog.moveCursor(QtGui.QTextCursor.End)
