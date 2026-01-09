from setuptools import setup

setup(
    name="lum-cli",
    version="1.0.0",
    py_modules=["lum"],
    install_requires=[
        "httpx",
        "pathlib",
    ],
    entry_points={
        "console_scripts": [
            "lum=lum:main",
        ],
    },
)