"""
Arrakis Common Library Setup
MSA 서비스 간 공통 기능 제공
"""
from setuptools import find_packages, setup

setup(
    name="arrakis-common",
    version="0.1.0",
    description="Common utilities for Arrakis MSA services",
    packages=find_packages(),
    install_requires=[
        "pydantic >= 2.0.0",
        "PyJWT >= 2.8.0",
        "cryptography >= 41.0.0",
        "httpx >= 0.25.0",
        "redis >= 5.0.0",
        "structlog >= 23.0.0",
        "python-multipart >= 0.0.6",
    ],
    python_requires=">=3.8",
)
