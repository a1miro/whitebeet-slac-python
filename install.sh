#!/bin/bash
# Installation script for WhiteBeet SLAC Python module

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}WhiteBeet SLAC Python Module - Installation${NC}"
echo "=============================================="
echo ""

# Check Python3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python3 not found${NC}"
    echo "Install with: sudo apt-get install python3 python3-pip"
    exit 1
fi

echo -e "${GREEN}✓ Python3 found:$(python3 --version)${NC}"

# Check FreeV2G
if [ ! -f "/opt/FreeV2G/Whitebeet.py" ]; then
    echo -e "${YELLOW}Warning: FreeV2G not found at /opt/FreeV2G${NC}"
    echo "Installing FreeV2G..."
    sudo git clone https://github.com/Sevenstax/FreeV2G.git /opt/FreeV2G
    echo -e "${GREEN}✓ FreeV2G installed${NC}"
else
    echo -e "${GREEN}✓ FreeV2G found${NC}"
fi

# Test FreeV2G import
echo ""
echo "Testing FreeV2G import..."
python3 << 'EOF'
import sys
sys.path.insert(0, '/opt/FreeV2G')
from Whitebeet import Whitebeet
print("✓ FreeV2G import successful")
EOF

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Cannot import FreeV2G${NC}"
    exit 1
fi

# Install Python dependencies
echo ""
echo "Checking Python dependencies..."
pip3 list | grep -q scapy || {
    echo "Installing scapy..."
    sudo pip3 install scapy
}
pip3 list | grep -q pylibpcap || {
    echo "Installing pylibpcap..."
    sudo pip3 install pylibpcap
}

echo -e "${GREEN}✓ Python dependencies OK${NC}"

# Ask for installation method
echo ""
echo "How would you like to install the module?"
echo "  1) Copy to EVerest modules directory"
echo "  2) Use module search path (EV_MODULE_DIR)"
echo -n "Choice [1/2]: "
read choice

if [ "$choice" = "1" ]; then
    echo -n "Enter EVerest modules directory [/usr/share/everest/modules]: "
    read modules_dir
    modules_dir=${modules_dir:-/usr/share/everest/modules}
    
    echo "Copying module to $modules_dir..."
    sudo cp -r modules/WhiteBeetSlac "$modules_dir/"
    echo -e "${GREEN}✓ Module installed to $modules_dir${NC}"
    
else
    echo ""
    echo "Add this to your ~/.bashrc or run before starting EVerest:"
    echo ""
    echo "export EV_MODULE_DIR=/home/amironenko/projects/imx93evk-rolec/workspace/whitebeet-slac-python/modules"
    echo ""
fi

echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Configure your WhiteBeet MAC in config/config-basic.yaml"
echo "  2. Run: sudo manager --conf config/config-basic.yaml"
echo ""
