# setup.py
# Created: 2025-01-29 12:43:20
# Author: drphon

from setuptools import setup, find_packages
import os

# Read requirements
with open('requirements.txt') as f:
    required = f.read().splitlines()

# Read README
with open('README.md', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="windows-web-scraper",
    version="1.0.0",
    author="drphon",
    author_email="drphon@example.com",
    description="A Windows-optimized web scraping tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/drphon/windows-web-scraper",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=required,
    entry_points={
        'console_scripts': [
            'webscraper=web_scraper:main',
        ],
    },
    include_package_data=True,
    package_data={
        '': ['*.json', '*.yaml', '*.yml'],
    },
)