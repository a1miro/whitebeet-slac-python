# WhiteBeet SLAC Python Module - Quick Start

## What Is This?

A **pure Python** EVerest module for WhiteBeet SLAC integration. 

**200 lines of clean Python** vs 800 lines of complex C++ with Python embedding!

## Installation (2 minutes)

### Option 1: CMake Install (Recommended)
```bash
cd /home/amironenko/projects/imx93evk-rolec/workspace/whitebeet-slac-python
cmake -B build -S .
sudo cmake --build build --target install
```

This installs:
- ✅ Module to `/usr/local/libexec/everest/modules/WhiteBeetSlac/`
- ✅ Configs to `/usr/local/etc/everest/`
- ✅ Sets executable permissions automatically

### Option 2: Manual Install Script
```bash
cd /home/amironenko/projects/imx93evk-rolec/workspace/whitebeet-slac-python
./install.sh
```

The installer will:
- ✅ Check Python3
- ✅ Install FreeV2G if needed
- ✅ Install Python dependencies (scapy, pylibpcap)
- ✅ Copy module to EVerest or set up module path

### 2. Configure
```bash
# Edit /usr/local/etc/everest/config-basic.yaml
# Update your WhiteBeet MAC address
sudo vim /usr/local/etc/everest/config-basic.yaml
```

### 3. Run
```bash
sudo manager --conf /usr/local/etc/everest/config-basic.yaml
```

Done! 🎉

## Why Python is Better

| Feature | C++ Version | Python Version ✅ |
|---------|-------------|-------------------|
| **Lines of Code** | ~800 | ~200 |
| **Build Time** | 5-10 minutes | 0 seconds |
| **Dependencies** | Python-dev, CMake, GCC | Python3 only |
| **Modify & Test** | Edit → Build → Run | Edit → Run |
| **Debugging** | GDB + Python | Just Python |
| **Complexity** | Python C API | Direct calls |

## Module Structure

```
whitebeet-slac-python/
├── README.md                          📚 Full documentation
├── QUICKSTART.md                      🚀 This file
├── LICENSE                            📄 Apache 2.0
├── install.sh                         🛠️ Installation script
│
├── modules/WhiteBeetSlac/            🎯 The module
│   ├── manifest.yaml                  (Module config)
│   └── whitebeet_slac.py             (200 lines - that's it!)
│
└── config/                            ⚙️ Sample configs
    ├── config-basic.yaml
    └── config-full.yaml
```

## Code Sample

```python
# The entire SLAC initialization:
self.whitebeet = Whitebeet("ETH", self.device, self.whitebeet_mac)
self.whitebeet.controlPilotSetMode(1)
self.whitebeet.controlPilotSetDutyCycle(100)
self.whitebeet.controlPilotStart()
self.whitebeet.slacStart(1)

# SLAC matching:
matched = self.whitebeet.slacMatched()
if matched:
    self.publish.state("MATCHED")
    self.publish.dlink_ready(True)
```

Clean and simple!

## Troubleshooting

**Module not found?**
```bash
export EV_MODULE_DIR=/home/amironenko/projects/imx93evk-rolec/workspace/whitebeet-slac-python/modules
```

**FreeV2G not found?**
```bash
sudo git clone https://github.com/Sevenstax/FreeV2G.git /opt/FreeV2G
```

**Import error?**
```bash
python3 -c "import sys; sys.path.insert(0, '/opt/FreeV2G'); from Whitebeet import Whitebeet"
```

## Comparison with C++ Version

Both implementations do the same thing, but:

**Python:**
- 200 lines of code
- No build process
- Easy to modify
- Direct FreeV2G usage
- One language (Python)

**C++:**
- 800 lines of code
- Requires CMake build
- Complex to modify
- Python C API embedding
- Two languages (C++ + Python)

For this use case, **Python is clearly better**!

## Next Steps

1. ✅ Run `./install.sh`
2. ✅ Edit `config/config-basic.yaml` (set your MAC)
3. ✅ Run `sudo manager --conf config/config-basic.yaml`
4. ✅ Plug in a vehicle and test!

## Support

- **Full README**: `README.md`
- **EVerest Docs**: https://everest.github.io/
- **FreeV2G**: https://github.com/Sevenstax/FreeV2G

---

**Ready in 2 minutes!** Run `./install.sh` now! 🚀
