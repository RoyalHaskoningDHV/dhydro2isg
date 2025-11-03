# D-HYDRO2iMOD

[![PyPI version](https://badge.fury.io/py/dhydro2imod.svg)](https://badge.fury.io/py/dhydro2imod)
[![Python versions](https://img.shields.io/pypi/pyversions/dhydro2imod.svg)](https://pypi.org/project/dhydro2imod/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

Python tool to convert D-HYDRO output to iMOD input.

## Installation

Install from PyPI:

```bash
pip install dhydro2imod
```

Install from source:

```bash
git clone https://github.com/RoyalHaskoningDHV/D-HYDRO2iMOD.git
cd D-HYDRO2iMOD
pip install -e .
```

## Usage

### Command Line

```bash
dhydro2imod
```

### Python API

```python
import dhydro2imod

# Use the conversion functionality
dhydro2imod.main()
```

## Development

### Setup Development Environment

```bash
git clone https://github.com/RoyalHaskoningDHV/D-HYDRO2iMOD.git
cd D-HYDRO2iMOD
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
