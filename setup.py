from distutils.core import setup
from setuptools import find_packages
import os
from castnet import __version__

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, 'README.md'), encoding='utf-8') as f:
    LONG_DESCRIPTION = f.read()

setup(
    name="castnet",
    packages=find_packages('.'),
    version=__version__,
    license='MIT',
    description='CastNet is a schema based low level Neo4j connection interaction library your Python back end,'
                ' enabling easy type conversions and generalized CRUD endpoints (including GraphQL).',
    author='Daniel S. Hitchcock',
    author_email="daniel.s.hitchcock@gmail.com",
    long_description_content_type="text/markdown",
    long_description=LONG_DESCRIPTION,
    keywords=['Neo4j', 'REST', 'graphdb', 'CRUD', 'graphql'],
    install_requires=["neo4j", 'shortuuid'],
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
    url="https://github.com/broadinstitute/castnet"
)