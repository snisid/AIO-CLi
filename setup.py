"""
MA-CLI - Multi-Agent Autonomous CLI

An independent agent orchestration platform capable of planning,
task decomposition, agent selection, model selection, tool selection,
execution, observation, supervision, and more.
"""

from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ma-cli",
    version="0.1.0-dev",
    author="MA-CLI Core Team",
    description="Multi-Agent Autonomous CLI - An independent agent orchestration platform",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
    ],
    python_requires=">=3.11",
    install_requires=[
        "click>=8.0",
        "pydantic>=2.0",
        "pyyaml>=6.0",
        "httpx>=0.25",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-asyncio>=0.21",
            "pytest-cov>=4.0",
            "ruff>=0.1",
            "mypy>=1.0",
        ],
        "tui": [
            "rich>=13.0",
            "textual>=0.40",
        ],
        "sandbox": [
            "docker>=6.0",
        ],
        "git": [
            "gitpython>=3.1",
        ],
    },
    entry_points={
        "console_scripts": [
            "ma-cli=ma_cli.cli.main:main",
        ],
    },
)
