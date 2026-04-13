from .base import *
import os
import sys

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*']

if os.name == 'nt':
    OSGEO4W_BIN = r'C:\OSGeo4W\bin'
    
    if sys.version_info >= (3, 8):
        os.add_dll_directory(OSGEO4W_BIN)
        
    os.environ['PATH'] = f"{OSGEO4W_BIN};{os.environ.get('PATH', '')}"
    
    GDAL_LIBRARY_PATH = os.path.join(OSGEO4W_BIN, 'gdal312.dll') 
    GEOS_LIBRARY_PATH = os.path.join(OSGEO4W_BIN, 'geos_c.dll')