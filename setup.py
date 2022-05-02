import os
import codecs
from distutils.core import setup
from setuptools import find_packages

HERE = os.path.dirname(os.path.abspath(__file__))

# get version without crashing from not having dependencies installed
def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), 'r') as fp:
        return fp.read()

def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith('__version__'):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")


with open(os.path.join(HERE, 'README.md'), encoding='utf-8') as f:
    LONG_DESCRIPTION = f.read()

setup(
    name="castnet",
    install_requires=['neo4j', 'shortuuid'],
    packages=find_packages('.'),
    version=get_version("castnet/__init__.py"),
    license='MIT',
    description='CastNet is a schema based low level Neo4j connection interaction library your Python back end,'
                ' enabling easy type conversions and generalized CRUD endpoints (including GraphQL).',
    author='Daniel S. Hitchcock',
    author_email="daniel.s.hitchcock@gmail.com",
    long_description_content_type="text/markdown",
    long_description=LONG_DESCRIPTION,
    keywords=['Neo4j', 'REST', 'graphdb', 'CRUD', 'graphql'],
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
    url="https://github.com/broadinstitute/castnet"
)