# Charging Session Flow with WhiteBeet SLAC

## Complete Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Charging Session                         │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┴─────────────────────┐
        │                                           │
        ▼                                           ▼
┌───────────────┐                          ┌──────────────┐
│ EvseManager   │◄────────────────────────►│ Auth Module  │
│ (Orchestrator)│                          │ (Token/PnC)  │
└───────┬───────┘                          └──────────────┘
        │
        │ Controls
        │
   ┌────┼────────────────────────────────┐
   │    │                                │
   ▼    ▼                                ▼
┌──────────┐  ┌──────────────────┐  ┌─────────────┐
│YetiSim/  │  │ WhiteBeet SLAC   │  │  EvseV2G    │
│BoardSup  │  │ (PLC Data Link)  │  │ (ISO15118)  │
└──────────┘  └──────────────────┘  └─────────────┘
   │                  │                     │
   │ CP/Relays        │ PLC (SLAC)         │ PLC (V2G)
   │                  │                     │
   └──────────────────┴─────────────────────┘
                      │
              ┌───────┴────────┐
              │   eth0 (PLC)   │
              │   WhiteBeet    │
              │   Hardware     │
              └────────────────┘
                      │
              ════════╪════════
                   Vehicle
```

## Step-by-Step: What Happens After Plugin

### Phase 1: Physical Connection (Board Support)
```
1. Vehicle plugs in
2. YetiSimulator/BoardSupport detects CP state change (A→B)
3. EvseManager receives "enter_bcd()" notification
```

### Phase 2: Data Link Establishment (SLAC)
```
4. EvseManager calls SLAC.reset(enable=true)
5. WhiteBeet SLAC:
   - Sets CP to 5% duty cycle
   - Starts SLAC matching (sends SLAC_PARM_REQ, etc.)
   - Waits for EV response
6. SLAC matching completes ✓
7. WhiteBeet SLAC publishes:
   - state = "MATCHED"
   - dlink_ready = true
8. CP returns to normal PWM duty cycle
```

### Phase 3: High-Level Communication (ISO15118) ← YOU ARE HERE
```
9. EvseManager detects dlink_ready = true
10. EvseManager triggers ISO15118 module (EvseV2G)
11. EvseV2G starts V2G protocol over PLC:
    - SupportedAppProtocol
    - SessionSetup
    - ServiceDiscovery
    - PaymentServiceSelection
    - Authorization
    - ChargeParameterDiscovery
    - PowerDelivery (START)
12. Power flows! ⚡
```

### Phase 4: Charging Loop
```
13. Ongoing V2G communication (CurrentDemand/ChargingStatus)
14. EvseManager monitors:
    - Power meter readings
    - Current limits
    - Safety conditions
15. Charging continues until:
    - EV requests stop (SoC reached, user stop)
    - EVSE stops (energy limit, error)
    - Cable disconnected
```

## Your Current Status

Based on "SLAC matching successful" message:

```
✅ Phase 1: DONE - Vehicle connected
✅ Phase 2: DONE - SLAC data link established
❌ Phase 3: MISSING - No ISO15118 module configured
❌ Phase 4: BLOCKED - Can't start without Phase 3
```

## Required Configuration

Minimal config to get charging working:

```yaml
evse_manager:
  module: EvseManager
  connections:
    slac:
      - module_id: whitebeet_slac  # ✅ You have this
    hlc:
      - module_id: iso15118_charger  # ❌ You need this!
    bsp:
      - module_id: yeti_simulator

iso15118_charger:  # ❌ Add this module
  module: EvseV2G
  config_module:
    device: eth0  # Same as SLAC
    tls_security: prohibit  # For testing

whitebeet_slac:  # ✅ You have this
  module: WhiteBeetSlac
  config_implementation:
    main:
      device: eth0
      whitebeet_mac: "c4:93:00:34:a4:e2"
```

## What Each Module Does

| Module | Layer | Purpose | Status |
|--------|-------|---------|--------|
| **WhiteBeet SLAC** | OSI Layer 2 | PLC link establishment (SLAC protocol) | ✅ Working |
| **EvseV2G** | OSI Layer 7 | V2G charging protocol (ISO15118-2) | ❌ Missing |
| **EvseManager** | Application | Session orchestration, power control | ⚠️ Needs HLC connection |
| **YetiSimulator** | Hardware | CP states, relays, power measurement | ✅ Working |

## Quick Fix

Use the complete configuration:
```bash
sudo manager --conf config/config-complete-charging.yaml
```

This includes all required modules and connections for a full charging session.

## Debug Tips

Monitor what's happening:
```bash
# Watch SLAC messages
tail -f /tmp/everest-logs/*.log | grep SLAC

# Watch ISO15118 messages
tail -f /tmp/everest-logs/*.log | grep -E "V2G|ISO15118"

# Check module status
everest-cli status

# Monitor state transitions
everest-cli subscribe evse_manager evse state
```

## Common Issues

### "SLAC matched but nothing happens"
→ Missing ISO15118 module or HLC connection

### "ISO15118 starts but fails immediately"  
→ Check `device: eth0` matches your PLC interface
→ Verify no firewall blocking PLC traffic

### "Authorization timeout"
→ Set `disable_authentication: true` for testing
→ Or configure token_provider/validator

### "Certificate errors"
→ Use `tls_security: prohibit` for testing
→ Or properly configure EvseSecurity module
