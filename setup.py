from setuptools import find_packages, setup

setup(
    name="instahunt",
    version="1.0.0",
    description="Automated Instagram Skincare Creator Discovery Engine for Tier 2/3 Indian Cities",
    author="Wydia & Zoro",
    packages=find_packages(),
    install_requires=[
        "click>=8.0.0",
        "rich>=13.0.0",
        "requests>=2.28.0",
        "openpyxl>=3.1.0",
        "pydantic>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "instahunt = instahunt.cli:main",
        ],
    },
    python_requires=">=3.9",
)
