from setuptools import setup, find_namespace_packages

setup(
    name="riceautomata",
    version="0.1.0",
    packages=find_namespace_packages(include=['src.*']),
    package_dir={'': '.'},
    install_requires=[
        "jsonschema>=4.17.3",
        "jinja2>=3.1.2",
        "colorama>=0.4.6",
        "pyyaml>=6.0.1",
        "toml>=0.10.2",
        "aiofiles>=23.2.1",
        "asyncio>=3.4.3",
        "typing-extensions>=4.7.1",
        "rich>=13.5.2",
        "distro"
    ],
    entry_points={
        'console_scripts': [
            'riceautomata=src.cli:main',
        ],
    },
    author="Gabriel",
    author_email="your.email@example.com",
    description="A powerful command-line tool for managing dotfiles and system configurations",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/zgabrielr1/riceautomata",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Environment :: Console",
        "Topic :: System :: Installation/Setup",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.6",
)
