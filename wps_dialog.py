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
import webbrowser

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt import QtGui
from qgis.utils import iface
from qgis.core import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import *
from qgis.gui import *

import importlib, inspect

from .connect import *

owslib_exists = True
try:
    from owslib.wps import WebProcessingService
    from owslib.wps import ComplexDataInput
    from owslib.util import getTypedValue
except:
    owslib_exists = False

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'wps_dialog_base.ui'))


class WpsDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, iface, parent=None):
        """Constructor."""
        super(WpsDialog, self).__init__(parent)
        self.iface = iface
        self.setupUi(self)
        if owslib_exists and self.check_owslib_fix():
            self.pushButtonLoadProcesses.clicked.connect(self.load_processes)
            self.verticalLayoutInputs = QVBoxLayout(self.tabInputs)
            self.verticalLayoutOutputs = QVBoxLayout(self.tabOutputs)
            self.pushButtonExecute.clicked.connect(self.execute_process)
            self.comboBoxProcesses.currentIndexChanged.connect(self.process_selected)
            self.handleOutputComboBox = None
            self.input_items = {}
            self.input_items_all = []
            self.output_items_all = []
            self.processes = []
        else:
            QMessageBox.information(None, self.tr("ERROR:"), self.tr("You have to install OWSlib with fix."))

    def check_owslib_fix(self):
        try:
            val = getTypedValue('integer', None)
            return True
        except:
            return False

    def load_processes(self):
        self.setCursor(Qt.WaitCursor)
        self.textEditLog.append(self.tr("Loading processes ..."))
        self.loadProcesses = GetProcesses()
        self.loadProcesses.setUrl(self.lineEditWpsUrl.text())
        self.loadProcesses.statusChanged.connect(self.on_load_processes_response)
        self.loadProcesses.start()

    def on_load_processes_response(self, response):
        if response.status == 200:
            self.comboBoxProcesses.clear()
            self.processes = response.data
            for proc in self.processes:
                self.comboBoxProcesses.addItem('[{}] {}'.format(proc.identifier, proc.title))
            self.show_process_description(0)
            self.textEditLog.append(self.tr("Processes loaded"))
        else:
            QMessageBox.information(None, self.tr("ERROR:"), self.tr("Error loading processes"))
            self.textEditLog.append(self.tr("Error loading processes"))
        self.setCursor(Qt.ArrowCursor)

    def show_process_description(self, index):
        self.textEditProcessDescription.setText("[" + self.processes[index].identifier + "]: " + self.processes[index].abstract)

    def process_selected(self):
        current_index = self.comboBoxProcesses.currentIndex()
        self.show_process_description(current_index)
        self.load_process()

    def get_all_layers_input(self):
        return QgsMapLayerComboBox(self.tabInputs)

    def get_layer_fields(self):
        return QgsFieldComboBox(self.tabInputs)

    def set_map_layer_cmb_box_connect(self):
        for param, widget in self.input_items.items():
            if isinstance(widget, QgsMapLayerComboBox):
                widget.currentIndexChanged.connect(self.set_layer_to_qgs_field_combo_box)

    def set_layer_to_qgs_field_combo_box(self):
        # TODO not generic - only last items will be connected
        layer = None
        field_cmb_box = None
        for param, widget in self.input_items.items():
            if isinstance(widget, QgsFieldComboBox):
                field_cmb_box = widget
            if isinstance(widget, QgsMapLayerComboBox):
                layer = widget.currentLayer()
        if layer is not None and field_cmb_box is not None:
            field_cmb_box.setLayer(layer)

    def get_input(self, identifier, title, data_type, default_value, min_occurs):
        # TODO check types
        input_item = None
        if data_type == 'ComplexData':
            input_item = self.get_all_layers_input()
        else:
            input_item = QLineEdit(self.tabInputs)
            if "column" in identifier:
                input_item = self.get_layer_fields()
            else:
                if str(default_value) == 'None':
                    input_item.setText('')
                else:
                    input_item.setText(str(default_value))
        hbox_layout, label, label_id = self.get_input_item_container(identifier, input_item, min_occurs, title)
        # TODO check if there is not a better way
        self.input_items[str(identifier)] = input_item
        self.input_items_all.append(input_item)
        self.input_items_all.append(label)
        self.input_items_all.append(label_id)
        return hbox_layout

    def get_input_item_container(self, identifier, input_item, min_occurs, title):
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

    def get_process_identifier(self):
        return self.processes[self.comboBoxProcesses.currentIndex()].identifier

    def load_process(self):
        self.setCursor(Qt.WaitCursor)
        process_identifier = self.get_process_identifier()
        self.textEditLog.append(self.tr("Loading process {}...".format(process_identifier)))
        self.loadProcess = GetProcess()
        self.loadProcess.setUrl(self.lineEditWpsUrl.text())
        self.loadProcess.setIdentifier(process_identifier)
        self.loadProcess.statusChanged.connect(self.on_load_process_response)
        self.loadProcess.start()

    def item_remove(self, array):
        for item_to_remove in array:
            item_to_remove.setParent(None)

    def set_input_items(self, data):
        self.item_remove(self.input_items_all)
        self.textEditProcessDescription.setText(data.abstract)
        self.input_items = {}
        self.pushButtonExecute.setEnabled(True)
        for x in data.dataInputs:
            input_item = self.get_input(x.identifier, x.title, x.dataType, x.defaultValue, x.minOccurs)
            self.verticalLayoutInputs.addLayout(input_item)
        self.tabInputs.setLayout(self.verticalLayoutInputs)
        self.set_layer_to_qgs_field_combo_box()
        self.set_map_layer_cmb_box_connect()

    def get_output(self, identifier, title, mime_type):
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

    def get_output_options_postprocessing(self):
        hbox_layout = QHBoxLayout(self.tabOutputs)
        label = QLabel(self.tabOutputs)
        label.setFixedWidth(200)
        label.setText(self.tr('Handle output'))
        hbox_layout.addWidget(label)
        self.handleOutputComboBox = QComboBox()
        self.handleOutputComboBox.addItem(self.tr("Load into map"))
        process_identifier = self.get_process_identifier()
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'postprocessing', process_identifier + ".py")
        if os.path.exists(path):
            self.handleOutputComboBox.addItem(self.tr("Postprocess"))
            self.handleOutputComboBox.setCurrentIndex(1)
        hbox_layout.addWidget(self.handleOutputComboBox)
        self.output_items_all.append(label)
        self.output_items_all.append(self.handleOutputComboBox)
        return hbox_layout

    def set_output_items(self, data):
        self.item_remove(self.output_items_all)
        for x in data.processOutputs:
            output_item = self.get_output(x.identifier, x.title, x.mimeType)
            self.verticalLayoutOutputs.addLayout(output_item)
            output_item_handle = self.get_output_options_postprocessing()
            self.verticalLayoutOutputs.addLayout(output_item_handle)
        self.tabOutputs.setLayout(self.verticalLayoutOutputs)

    def on_load_process_response(self, response):
        process_identifier = self.get_process_identifier()
        if response.status == 200:
            if response.data.abstract is not None:
                self.set_input_items(response.data)
                self.set_output_items(response.data)
                self.textEditLog.append(self.tr("Process {} loaded".format(process_identifier)))
            else:
                self.textEditLog.append(self.tr("Error loading process {}".format(process_identifier)))
        else:
            QMessageBox.information(None, self.tr("ERROR:"),
                                    self.tr("Error loading process {}".format(process_identifier)))
            self.textEditLog.append(self.tr("Error loading process {}".format(process_identifier)))
        self.setCursor(Qt.ArrowCursor)

    def execute_process(self):
        self.setCursor(Qt.WaitCursor)
        # Async call: https://ouranosinc.github.io/pavics-sdi/tutorials/wps_with_python.html
        process_identifier = self.get_process_identifier()
        myinputs = []
        for param, widget in self.input_items.items():
            if isinstance(widget, QgsMapLayerComboBox):
                # TODO check input type and export into it (GML, GeoPackage, etc.)
                layer = widget.currentLayer()
                if layer is None:
                    iface.messageBar().pushMessage(self.tr("Error"), self.tr("There is not any layer"), level=Qgis.Critical)
                    return
                if layer.type() == QgsMapLayer.VectorLayer:
                    tmp_ext = '.gml'
                    tmp_frmt = 'GML'
                else:
                    iface.messageBar().pushMessage("Error", "Unsupported map layer type", level=Qgis.Critical)
                    return

                tmp_file = QgsProcessingUtils.generateTempFilename(
                    process_identifier + '_' + param) + tmp_ext
                QgsVectorFileWriter.writeAsVectorFormat(
                    layer,
                    tmp_file,
                    fileEncoding="UTF-8",
                    driverName=tmp_frmt
                )
                with open(tmp_file) as fd:
                    cdi = ComplexDataInput(fd.read())
                myinputs.append((param, cdi))
            elif isinstance(widget, QgsFieldComboBox):
                myinputs.append((param, widget.currentField()))
            else:
                # TODO check also other types than just QLineEdit
                if widget.text() != 'None':
                    myinputs.append((param, widget.text()))
        self.textEditLog.append(self.tr("Executing {} process ...".format(process_identifier)))
        self.executeProcess = ExecuteProcess()
        self.executeProcess.setUrl(self.lineEditWpsUrl.text())
        self.executeProcess.setIdentifier(process_identifier)
        self.executeProcess.setInputs(myinputs)
        self.executeProcess.statusChanged.connect(self.on_execute_process_response)
        self.executeProcess.start()

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

    def postprocess_output(self, process_identifier, inputs, response):
        current_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
        current_module_name = os.path.splitext(os.path.basename(current_dir))[0]
        module = importlib.import_module(".postprocessing." + process_identifier, package=current_module_name)
        for member in dir(module):
            if member == 'wps_postprocessing':
                handler_class = getattr(module, member)
                current_source = handler_class()
                return current_source.postprocess(inputs, response)
                # only for testig purposes
                # self.postprocess(inputs, response)

    def process_not_known_output(self, item):
        QMessageBox.information(
            None, self.tr("INFO:"),
            self.tr("Process sucesfully finished. The output can not be loaded into map. Printing output into log."))
        self.textEditLog.append(self.tr("Showing content of the output"))
        self.appendFileContentIntoLog(item)

    def process_output(self, response):
        process_identifier = self.get_process_identifier()
        if self.handleOutputComboBox is not None and self.handleOutputComboBox.currentIndex() == 1:
            result = self.postprocess_output(process_identifier, self.input_items, response)
            if result is not None:
                self.textEditLog.append(self.tr("Postprocessing successfully finished"))
            else:
                QMessageBox.information(None, self.tr("INFO:"), self.tr("Postprocessing ended with error."))
                self.textEditLog.append(self.tr("ERROR: Postprocessing ended with error."))
        else:
            for identifier, item in response.output.items():
                # dir(item)
                vector = None
                if item.minetype == 'application/csv':
                    csv_uri = 'file:///' + item.filepath + '?delimiter=,'
                    vector = QgsVectorLayer(csv_uri, "{} {}".format(process_identifier, identifier), 'delimitedtext')
                elif item.minetype == 'application/x-zipped-shp':
                    vector = QgsVectorLayer('/vsizip/' + item.filepath, "{} {}".format(process_identifier, identifier), "ogr")
                if vector is not None and vector.isValid():
                    QgsProject.instance().addMapLayer(vector)
                    self.textEditLog.append(self.tr("Output data loaded into the map"))
                else:
                    self.process_not_known_output(item)

    def on_execute_process_response(self, response):
        process_identifier = self.get_process_identifier()
        if response.status == 200:
            self.textEditLog.append(self.tr("Process {} successfully finished".format(process_identifier)))
            self.process_output(response)
            self.setCursor(Qt.ArrowCursor)
        if response.status == 201:
            self.textEditLog.append(self.tr("Process '{}': {}% {}".format(
                process_identifier, response.data['percent'], response.data['message'], 
            )))
        if response.status == 500:
            self.textEditLog.append(self.tr("Process {} failed".format(process_identifier)))
            self.process_output(response)
            self.setCursor(Qt.ArrowCursor)
            QMessageBox.information(None, self.tr("ERROR:"),
                                    self.tr("Error executing process {}".format(process_identifier)))
            self.textEditLog.append(self.tr("Error executing process {}".format(process_identifier)))
            self.textEditLog.append(response.data)

    def appendFileContentIntoLog(self, item):
        with (open(item.filepath, "r")) as f:
            self.textEditLog.append(str(f.read()))
