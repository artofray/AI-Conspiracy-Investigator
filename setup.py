#!/usr/bin/env python3
"""
SHADOW - Open Source Intelligence Platform
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="shadow-osint",
    version="1.0.0",
    author="SHADOW Project Contributors",
    author_email="hello@shadow-project.org",
    description="Open Source Intelligence Platform for Truth Seekers",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/truth-seekers/shadow",
    project_urls={
        "Bug Tracker": "https://github.com/truth-seekers/shadow/issues",
        "Documentation": "https://github.com/truth-seekers/shadow/wiki",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
    ],
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "flask>=2.3.0",
        "flask-cors>=4.0.0",
        "requests>=2.31.0",
        "aiohttp>=3.9.0",
        "aiofiles>=23.0.0",
        "PyPDF2>=3.0.0",
        "pdf2image>=1.16.0",
        "pytesseract>=0.3.10",
        "Pillow>=10.0.0",
        "python-docx>=0.8.11",
        "beautifulsoup4>=4.12.0",
        "openpyxl>=3.1.0",
        "lxml>=4.9.0",
        "spacy>=3.6.0",
        "chromadb>=0.4.0",
        "sentence-transformers>=2.2.0",
        "numpy>=1.24.0",
        "python-dateutil>=2.8.0",
        "tqdm>=4.65.0",
        "websockets>=12.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "mypy>=1.5.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "shadow=shadow_backend:main",
            "shadow-scrape=foia_scraper:main",
            "shadow-monitor=social_monitor:main",
            "shadow-vector=vector_db:main",
        ],
    },
)
