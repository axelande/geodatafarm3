from distutils.core import setup
from distutils.extension import Extension
from Cython.Build import cythonize
import os

this_folder = os.path.dirname(os.path.abspath(__file__))
extensions = [
    Extension("cython_agri", [f"{this_folder}/cython_agri.pyx"])
]
setup(ext_modules=cythonize(extensions, language_level="3"))
