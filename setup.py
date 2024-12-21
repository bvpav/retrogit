from setuptools import setup, find_packages

setup(
    name="retrogit",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        'toml>=0.10.2',
        'python-dateutil>=2.8.2',
        'gitpython>=3.1.31',
    ],
    entry_points={
        'console_scripts': [
            'retrogit=retrogit:main',
        ],
    },
) 