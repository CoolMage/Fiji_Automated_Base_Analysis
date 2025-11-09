"""
Setup script for Fiji Automated Analysis Tool
"""

from setuptools import setup, find_packages
import os

# Read the README file
def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()

# Read requirements
def read_requirements():
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="fiji-automated-analysis",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Universal Fiji Automated Analysis Tool for cross-platform image processing",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/fiji-automated-analysis",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Image Processing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires=">=3.7",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "flake8>=3.8",
            "mypy>=0.800",
        ],
        "docs": [
            "sphinx>=4.0",
            "sphinx-rtd-theme>=0.5",
        ],
    },
    entry_points={
        "console_scripts": [
            "fiji-document-processor=main:main",
        ],
        "gui_scripts": [
            "fiji-gui=gui:main",
        ],
    },
    keywords="fiji imagej image processing automation cross-platform bioimaging",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/fiji-automated-analysis/issues",
        "Source": "https://github.com/yourusername/fiji-automated-analysis",
        "Documentation": "https://fiji-automated-analysis.readthedocs.io/",
    },
)
