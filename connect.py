from qgis.PyQt.QtCore import QThread, pyqtSignal
import tempfile, os
from .check_ows_lib import CheckOwsLib

import sys
sys.path.insert(0, "/home/jachym/src/opengeolabs/OWSLib/")
import owslib.wps
print(owslib.wps.__file__)
from owslib.wps import WebProcessingService
from owslib.wps import ComplexDataInput

class ResponseOutput:
    def __init__(self, filepath, minetype):
        self.filepath = filepath
        self.minetype = minetype

class Response():
    status = 200
    data = []
    output = {}

# TODO create superclass for these classes
class GetProcesses(QThread):
    statusChanged = pyqtSignal(object)
    url = None
    timeout = 5

    def setUrl(self, url):
        self.url = url

    def setTimeout(self, timeout):
        self.timeout = timeout

    def run(self):
        responseToReturn = Response()
        try:
            wps = WebProcessingService(self.url)
            wps.getcapabilities()
            # processes = [x.identifier for x in wps.processes]
            responseToReturn.status = 200
            responseToReturn.data = wps.processes
        except Exception as e:
#             print(e)
            responseToReturn.status = 500
        self.statusChanged.emit(responseToReturn)

class GetProcess(QThread):
    statusChanged = pyqtSignal(object)
    url = None
    timeout = 5
    identifier = ''

    def setUrl(self, url):
        self.url = url

    def setTimeout(self, timeout):
        self.timeout = timeout

    def setIdentifier(self, identifier):
        self.identifier = identifier

    def run(self):
        responseToReturn = Response()
        if self.identifier != "":
            try:
                wps = WebProcessingService(self.url)
                process = wps.describeprocess(self.identifier)
                responseToReturn.status = 200
                responseToReturn.data = process
            except:
                responseToReturn.status = 500
        else:
            responseToReturn.status = 500
        self.statusChanged.emit(responseToReturn)

class ExecuteProcess(QThread):
    statusChanged = pyqtSignal(object)
    url = None
    timeout = 60
    identifier = ''
    inputs = []

    def setUrl(self, url):
        self.url = url

    def setTimeout(self, timeout):
        self.timeout = timeout

    def setIdentifier(self, identifier):
        self.identifier = identifier

    def setInputs(self, inputs):
        self.inputs = inputs

    def getFilePath(self, mimeType):
        temp_name = next(tempfile._get_candidate_names())
        defult_tmp_dir = tempfile._get_default_tempdir()
        suffix = 'zip'
        if mimeType == 'application/csv':
            suffix = 'csv'
        elif mimeType == 'image/tiff; subtype=geotiff':
            suffix = 'tif'
        return os.path.join(defult_tmp_dir, temp_name + "." + suffix)

    def run(self):
        """
        * Call the `Execute` request on WPS service with all intpus
        * Wait for result
        * After executed, download all outputs and show the progress
        * Handle Execeptions
        """

        responseToReturn = Response()
        if self.identifier != "" and len(self.inputs) > 0:
            try:
                wps = WebProcessingService(self.url)
                execution = wps.execute(self.identifier, self.inputs, output=[])
                self.monitorExecution(execution)
                for output in execution.processOutputs:
                    filePath = self.getFilePath(output.mimeType)
                    responseToReturn.output[output.identifier] = ResponseOutput(
                        filePath, output.mimeType
                    )
                    data_output = execution.getOutput(filePath, output.identifier)
                    for i in data_output:
                        #print("download progress: ", i)
                        responseToReturn = Response()
                        responseToReturn.status = 201
                        responseToReturn.data = {
                            "message": "Downloading ouput {}".format(output.identifier),
                            "status":  "Download",
                            "percent": int(i*100)
                        }
                        self.statusChanged.emit(responseToReturn)
                responseToReturn.status = 200
            except Exception as e:
                responseToReturn.status = 500
                responseToReturn.data = str(e)
        else:
            responseToReturn.status = 500
        self.statusChanged.emit(responseToReturn)


    def monitorExecution(self, execution, sleepSecs=3, download=False, filepath=None):
        '''
        Custom implementation of monitorExecution from om owslib/owslib/wps.py
        '''
        responseToReturn = Response()
        while execution.isComplete() is False:
            execution.checkStatus(sleepSecs=sleepSecs)

            responseToReturn.status = 201
            responseToReturn.data = {
                "status": execution.status,
                "message": execution.statusMessage,
                "percent": execution.percentCompleted
            }
            self.statusChanged.emit(responseToReturn)

        # if execution.isSucceded():
        #     if download:
        #         execution.getOutput(filepath=filepath)
        #     else:
        #         for output in execution.processOutputs:
        #             if output.reference is not None:
        #                 print('Output URL=%s' % output.reference)
        # else:
        #     for ex in execution.errors:
        #         print('Error: code=%s, locator=%s, text=%s' %
        #                 (ex.code, ex.locator, ex.text))
