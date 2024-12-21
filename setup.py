from setuptools import setup, find_packages

setup(
    name="riceautomata",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "jinja2",
        "pyyaml",
        "toml",
        "colorama",
    ],
    entry_points={
        'console_scripts': [
            'riceautomata=src.cli:main',
        ],
    },
    author="Your Name",
    author_email="your.email@example.com",
    description="A powerful command-line tool for managing dotfiles and system configurations",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/riceautomata",
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
