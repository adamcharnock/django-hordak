#!/usr/bin/env python

from os.path import exists
from setuptools import setup, find_packages

setup(
    name='django-hordak',
    version=open('VERSION').read().strip(),
    # Your name & email here
    author='',
    author_email='',
    # If you had hordak.tests, you would also include that in this list
    packages=find_packages(),
    # Any executable scripts, typically in 'bin'. E.g 'bin/do-something.py'
    scripts=[],
    # REQUIRED: Your project's URL
    url='',
    # Put your license here. See LICENSE.txt for more information
    license='',
    # Put a nice one-liner description here
    description='',
    long_description=open('README.rst').read() if exists("README.rst") else "",
    install_requires=[
        'django>=1.10'
        'django-mptt>=0.8',
        'django-model-utils>=2.5.0',
        'dj-database-url>=0.4.1',
        'psycopg2>=2.6.2',
        'django-extensions>=1.7.3',
    ],
)
