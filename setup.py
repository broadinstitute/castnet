from distutils.core import setup
from setuptools import find_packages
import os
from castnet import __version__

current_directory = os.path.dirname(os.path.abspath(__file__))
try:
    with open(os.path.join(current_directory, 'README.md'), encoding='utf-8') as f:
        long_description = f.read()
except Exception:
    long_description = ''

setup(
    name="castnet",
    packages=find_packages('.'),
    version=__version__,
    license='MIT',
    description='',
    long_description = long_description,
    long_description_context_type = 'text/markdown',
    author='Daniel S. Hitchcock',
    keywords=['Neo4j', 'REST', 'graphdb', 'CRUD', 'graph'],
    install_requires=[],
    classifiers=[]
)