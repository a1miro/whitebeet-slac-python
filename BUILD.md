# Building and Installing WhiteBeet SLAC Python Module

## Prerequisites

```bash
# Install build tools
sudo apt-get install cmake build-essential

# Install Python dependencies
sudo apt-get install python3 python3-pip python3-scapy
```

## Build with CMake

### Standard Build

```bash
# Configure
cmake -B build -S .

# Install to system (requires root)
sudo cmake --build build --target install
```

### Custom Installation Prefix

```bash
# Install to custom location
cmake -B build -S . -DCMAKE_INSTALL_PREFIX=/opt/everest
sudo cmake --build build --target install
```

### Installation Paths

By default, files are installed to:
- **Module**: `${CMAKE_INSTALL_LIBEXECDIR}/everest/modules/WhiteBeetSlac/`
  - `/usr/local/libexec/everest/modules/WhiteBeetSlac/manifest.yaml`
  - `/usr/local/libexec/everest/modules/WhiteBeetSlac/whitebeet_slac.py` (executable)

- **Configs**: `${CMAKE_INSTALL_SYSCONFDIR}/everest/`
  - `/usr/local/etc/everest/config-basic.yaml`
  - `/usr/local/etc/everest/config-full.yaml`

## Manual Installation (Alternative)

If you prefer not to use CMake:

```bash
./install.sh
```

## Verify Installation

```bash
# Check module is installed
ls -la /usr/local/libexec/everest/modules/WhiteBeetSlac/

# Check configs
ls -la /usr/local/etc/everest/config-*.yaml

# Verify executable permissions
ls -la /usr/local/libexec/everest/modules/WhiteBeetSlac/whitebeet_slac.py
```

## Building Debian Package

```bash
# Build DEB package
cmake -B build -S .
cd build
cpack -G DEB

# Install package
sudo dpkg -i whitebeet-slac-python-0.1.0-Linux.deb
```

## Uninstalling

```bash
# If installed via CMake
sudo cmake --build build --target uninstall

# If installed via package
sudo dpkg -r whitebeet-slac-python
```

## Troubleshooting

### Permission Denied

If `whitebeet_slac.py` is not executable:
```bash
sudo chmod +x /usr/local/libexec/everest/modules/WhiteBeetSlac/whitebeet_slac.py
```

### Missing FreeV2G Library

```bash
# Install FreeV2G from source
git clone https://github.com/SwitchEV/FreeV2G.git /opt/FreeV2G
export PYTHONPATH="/opt/FreeV2G:$PYTHONPATH"
```

### Module Not Found

Ensure EVerest can find the module:
```bash
export EVEREST_MODULE_DIR=/usr/local/libexec/everest/modules
```
