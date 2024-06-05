#!/usr/bin/env python

from setuptools import find_packages, setup

with open("README.md") as f:
    readme = f.read()

setup(
    name="cs_fmu_mapper",
    version="0.1.0",
    description="A tool to map FMUs to a common interface for simulation.",
    author="Marvin Schlageter, Cedric Ewen",
    author_email="marvin.schlageter@buildlinx.de",
    url="https://github.com/marvin-schl/cs-fmu-mapper",
    long_description=readme,
    install_requires=[
        "pyfmi",
        "asyncua",
        "FMPy",
        "inquirer",
        "matplotlib",
        "numpy",
        "pandas",
        "PyYAML",
        "tqdm",
    ],
    packages=find_packages(),
)
