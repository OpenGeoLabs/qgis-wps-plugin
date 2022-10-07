import os
from zipfile import ZipFile

from qgis.core import QgsRasterLayer, QgsProject

class wps_postprocessing:
    def postprocess(self, inputs, response):
        process_identifier = os.path.splitext(os.path.basename(__file__))[0]
        try:
            target_dir = os.path.splitext(response.output['output'].filepath)[0]
            with ZipFile(response.output['output'].filepath, 'r') as zf:
                zf.extractall(target_dir)
            for name in inputs["layers"].checkedItems():
                uri = os.path.join(target_dir, name + '.tif')
                raster = QgsRasterLayer(uri, "{} {}".format(process_identifier, name))
                raster.loadNamedStyle(os.path.join(target_dir, name + '.qml'))
                QgsProject.instance().addMapLayer(raster)
        except Exception as e:
            print(e)
            return None

        return 0
