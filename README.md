# WhiteBeet SLAC - Python Module

Direct integration between EVerest and WHITE-beet-EI hardware for ISO15118-3 SLAC functionality using Python.

## Overview

This is a **pure Python** implementation of the WhiteBeet SLAC module. Unlike the C++ version, this module directly uses the FreeV2G Python library without any language bridging, making it simpler, cleaner, and easier to maintain.

## Why Python?

✅ **Much Simpler** - ~200 lines vs ~800 lines in C++  
✅ **Direct FreeV2G Integration** - No embedding, no wrappers  
✅ **Easier to Debug** - All in one language  
✅ **No Compilation** - Just copy and run  
✅ **Faster Development** - Modify and test immediately  
✅ **More Maintainable** - Clean, readable code  

## Quick Start

### Prerequisites

```bash
# Install Python and dependencies
sudo apt-get install python3 python3-pip
sudo pip3 install scapy pylibpcap

# Install EVerest (if not already done)
# Follow EVerest installation guide
```

**Note:** FreeV2G is now included as a git submodule and will be installed automatically with the module.

### Installation

#### Option 1: Using CMake (Recommended)

```bash
# Clone with submodules
git clone --recurse-submodules https://github.com/a1miro/whitebeet-slac-python.git
# Or if already cloned:
git submodule update --init --recursive

# Build and install
cmake -B build -S .
sudo cmake --build build --target install
```

This installs:
- Module to `/usr/local/libexec/everest/modules/WhiteBeetSlac/`
- Configs to `/usr/local/etc/everest/`
- FreeV2G to `/usr/local/share/FreeV2G/`

The module will automatically detect FreeV2G in standard locations.

See [BUILD.md](BUILD.md) for detailed build instructions.

#### Option 2: Manual Installation

```bash
# Copy module to EVerest modules directory
cd /home/amironenko/projects/imx93evk-rolec/workspace/whitebeet-slac-python
cp -r modules/WhiteBeetSlac /path/to/everest/modules/

# Or set module search path
export EV_MODULE_DIR=/home/amironenko/projects/imx93evk-rolec/workspace/whitebeet-slac-python/modules
```

### Configuration

The module provides several configuration files for different use cases:

#### 1. Debug Auto-Enable (Easiest for Testing)
`config/config-debug-auto.yaml` - Automatically enables SLAC on startup without needing EvseManager:

```yaml
whitebeet_slac:
  module: WhiteBeetSlac
  config_implementation:
    main:
      device: eth0
      whitebeet_mac: "c4:93:00:34:a4:e2"
      debug_auto_enable: true  # Auto-enable for testing
```

**Use this for:** Quick hardware testing without full EVerest setup.

#### 2. With EvseManager Simulation (Production-like)
`config/config-with-evse-sim.yaml` - Full EVSE simulation with YetiSimulator:

```yaml
evse_manager:
  module: EvseManager
  connections:
    slac:
      - implementation_id: main
        module_id: whitebeet_slac
    # ... other connections
```

**Use this for:** Testing the full charging workflow with simulated CP states.

#### 3. Standalone Testing (Manual Control)
`config/config-standalone-test.yaml` - Minimal config for manual command testing:

```bash
# Enable SLAC manually:
everest-cli call whitebeet_slac main reset '{"enable": true}'
everest-cli call whitebeet_slac main enter_bcd '{}'
```

**Use this for:** Development and debugging with manual control.

### Run

```bash
# Quick test (auto-enable):
sudo manager --conf config/config-debug-auto.yaml

# Full simulation with EvseManager:
sudo manager --conf config/config-with-evse-sim.yaml

# Manual control:
sudo manager --conf config/config-standalone-test.yaml
```

## Module Structure

```
modules/WhiteBeetSlac/
├── manifest.yaml           # Module configuration
└── whitebeet_slac.py      # Main module (200 lines)
```

That's it! No build system, no compilation, just Python.

## How It Works

The module is incredibly straightforward:

1. **Initialize**: Connect to WhiteBeet via FreeV2G
2. **Setup CP**: Configure Control Pilot in EVSE mode
3. **Start SLAC**: Enable SLAC module on QCA7005
4. **Wait for Vehicle**: When BCD state entered, start matching
5. **Match**: Call `slacStartMatching()` and wait for `slacMatched()`
6. **Done**: Publish MATCHED state and enable high-level communication

## Key Features

- ✅ Direct Whitebeet API calls (no language bridging)
- ✅ Simple thread-based operation
- ✅ Clean error handling
- ✅ Standard EVerest SLAC interface
- ✅ Logging integration
- ✅ No build dependencies

## Code Comparison

### Python Version (Clean!)
```python
# Initialize WhiteBeet
self.whitebeet = Whitebeet("ETH", self.device, self.whitebeet_mac)

# Setup Control Pilot
self.whitebeet.controlPilotSetMode(1)
self.whitebeet.controlPilotSetDutyCycle(100)
self.whitebeet.controlPilotStart()

# Start SLAC
self.whitebeet.slacStart(1)

# Wait for matching
matched = self.whitebeet.slacMatched()
if matched:
    self.publish.state("MATCHED")
```

### C++ Version (Complex)
```cpp
// Initialize Python interpreter
Py_Initialize();
PyRun_SimpleString("import sys");
PyRun_SimpleString("sys.path.insert(0, '/opt/FreeV2G')");

// Import Python module
PyObject* pName = PyUnicode_DecodeFSDefault("Whitebeet");
PyObject* pModule = PyImport_Import(pName);
Py_DECREF(pName);

// Get class and create instance
PyObject* pClass = PyObject_GetAttrString(pModule, "Whitebeet");
PyObject* pArgs = PyTuple_New(3);
// ... 50 more lines of Python C API calls
```

The difference is clear!

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device` | string | `eth0` | Ethernet interface for WhiteBeet |
| `whitebeet_mac` | string | `c4:93:00:34:a4:e4` | WhiteBeet MAC address |
| `slac_timeout_ms` | integer | `50000` | SLAC timeout (ms) |
| `publish_mac_on_match_cnf` | boolean | `true` | Publish EV MAC |

## Debugging

Enable debug logging:
```bash
export EVEREST_LOG_LEVEL=debug
sudo manager --conf config/config-basic.yaml
```

Monitor SLAC traffic:
```bash
sudo tcpdump -i eth0 -XX ether proto 0x88e1
```

## Troubleshooting

### Module not found
```bash
# Check module search path
echo $EV_MODULE_DIR

# Or copy to EVerest modules directory
cp -r modules/WhiteBeetSlac /usr/share/everest/modules/
```

### FreeV2G import error
```bash
# Verify FreeV2G installation
python3 -c "import sys; sys.path.insert(0, '/opt/FreeV2G'); from Whitebeet import Whitebeet"

# If fails, clone FreeV2G
sudo git clone https://github.com/Sevenstax/FreeV2G.git /opt/FreeV2G
```

### Connection error
```bash
# Check network interface
ip link show eth0

# Verify WhiteBeet is reachable
ping <whitebeet_ip>

# Check MAC address (lowercase with colons)
# Correct: c4:93:00:34:a4:e4
```

## Comparison: Python vs C++

| Aspect | C++ Module | Python Module ✅ |
|--------|-----------|-----------------|
| **Code Size** | ~800 lines | ~200 lines |
| **Complexity** | High (Python embedding) | Low (direct calls) |
| **Build Time** | Minutes (compilation) | None (interpreted) |
| **Debugging** | Complex (2 languages) | Simple (Python) |
| **Dependencies** | Python dev headers, CMake | Just Python3 |
| **Maintenance** | Hard (cross-language) | Easy (pure Python) |
| **Development** | Edit → Build → Test | Edit → Test |
| **Errors** | Compile + runtime | Runtime only |

## Development

### Modifying the Module

```bash
# Edit the module
vim modules/WhiteBeetSlac/whitebeet_slac.py

# No build needed - just restart EVerest
sudo manager --conf config/config-basic.yaml
```

### Adding Features

The code is straightforward to extend:

```python
# Add EV MAC extraction
def _get_ev_mac(self):
    # Extract MAC from WhiteBeet
    # ... implementation ...
    return mac_address

# Use it
if self.publish_mac:
    ev_mac = self._get_ev_mac()
    self.publish.ev_mac_address(ev_mac)
```

## Performance

SLAC is not performance-critical (happens once per charging session), so Python's slightly lower performance vs C++ is completely negligible. The network and hardware operations dominate the timing.

## License

Apache 2.0 - See LICENSE file for details.

## Authors

- Andrei Mironenko, Parallel Dynamic Ltd.

## See Also

- [EVerest Documentation](https://everest.github.io/)
- [FreeV2G Project](https://github.com/Sevenstax/FreeV2G)
- [WhiteBeet Hardware](https://www.sevenstax.com/)
- C++ version (for comparison): `../whitebeet-slac/`
