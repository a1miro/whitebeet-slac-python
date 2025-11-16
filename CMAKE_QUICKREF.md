# CMake Quick Reference

## Build & Install

```bash
# Standard installation
cmake -B build -S .
sudo cmake --build build --target install

# Custom prefix
cmake -B build -S . -DCMAKE_INSTALL_PREFIX=/opt/everest
sudo cmake --build build --target install

# Test installation (dry-run)
cmake -B build -S .
cmake --install build --prefix ~/tmp/test --verbose
```

## Installed Locations

Default prefix: `/usr/local`

```
/usr/local/
├── libexec/everest/modules/WhiteBeetSlac/
│   ├── manifest.yaml
│   └── whitebeet_slac.py (executable)
│
└── etc/everest/
    ├── config-basic.yaml
    └── config-full.yaml
```

## Packaging

```bash
# Build DEB package
cmake -B build -S .
cd build
cpack -G DEB

# Install package
sudo dpkg -i whitebeet-slac-python-0.1.0-Linux.deb

# Remove package
sudo dpkg -r whitebeet-slac-python
```

## Clean Build

```bash
# Remove build directory
rm -rf build

# Reconfigure from scratch
cmake -B build -S .
```

## Verify Installation

```bash
# Check module files
ls -la /usr/local/libexec/everest/modules/WhiteBeetSlac/

# Check executable permissions
ls -la /usr/local/libexec/everest/modules/WhiteBeetSlac/whitebeet_slac.py

# Check configs
ls -la /usr/local/etc/everest/config-*.yaml

# Run module
cd /usr/local/libexec/everest/modules/WhiteBeetSlac/
./whitebeet_slac.py --help
```

## Common Issues

### Permission Denied
```bash
# Make module executable
sudo chmod +x /usr/local/libexec/everest/modules/WhiteBeetSlac/whitebeet_slac.py
```

### Module Not Found
```bash
# Set module directory
export EVEREST_MODULE_DIR=/usr/local/libexec/everest/modules
```

### FreeV2G Not Found
```bash
# Install FreeV2G
sudo git clone https://github.com/Sevenstax/FreeV2G.git /opt/FreeV2G
export PYTHONPATH="/opt/FreeV2G:$PYTHONPATH"
```
