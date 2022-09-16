#!/usr/bin/env python

import re
from os.path import exists

from setuptools import find_packages, setup


def parse_requirements(file_name):
    requirements = []
    for line in open(file_name, "r").read().split("\n"):
        if re.match(r"(\s*#)|(\s*$)", line):
            continue
        if re.match(r"\s*-e\s+", line):
            requirements.append(re.sub(r"\s*-e\s+.*#egg=(.*)$", r"\1", line))
        elif re.match(r"(\s*git)|(\s*hg)", line):
            pass
        else:
            requirements.append(line)
    return requirements


setup(
    name="django-hordak",
    version=open("VERSION").read().strip(),
    author="Adam Charnock",
    author_email="adam@adamcharnock.com",
    packages=find_packages(),
    scripts=[],
    url="https://github.com/adamcharnock/django-hordak",
    license="MIT",
    description="Double entry book keeping in Django",
    long_description=open("README.rst").read() if exists("README.rst") else "",
    include_package_data=True,
    install_requires=parse_requirements("requirements.txt"),
    extras_require={"subqueries": ["django-sql-utils"]},
)
