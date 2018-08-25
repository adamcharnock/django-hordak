#!/usr/bin/env python

from os.path import exists
from setuptools import setup, find_packages

setup(
    name='django-hordak',
    version=open('VERSION').read().strip(),
    author='Adam Charnock',
    author_email='adam@adamcharnock.com',
    packages=find_packages(),
    scripts=[],
    url='https://github.com/adamcharnock/django-hordak',
    license='MIT',
    description='Double entry book keeping in Django',
    long_description=open('README.rst').read() if exists("README.rst") else "",
    include_package_data=True,
    install_requires=[
        'django>=1.10, <2.1',
        'django-mptt>=0.8',
        'django-model-utils>=2.5.0',
        'dj-database-url>=0.4.1',
        'psycopg2-binary>=2.6.2',
        'django-extensions>=1.7.3',
        'django-smalluuid>=1.1.1',
        'requests>=2',
        'py-moneyed>=0.6.0',
        'django-money>=0.9.1',
        'django-import-export>=0.5.0',
        'babel==2.5.1',
    ],
)
