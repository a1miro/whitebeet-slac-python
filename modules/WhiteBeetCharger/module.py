#!/usr/bin/env python3
"""
WhiteBeet ISO15118 Charger Module for EVerest
Uses WhiteBeet's internal V2G implementation

This module bridges EVerest's ISO15118_charger interface with
WhiteBeet hardware's built-in ISO15118-2 stack.
"""

import sys
import time
import signal
from threading import Thread, Event

# Add FreeV2G to Python path
sys.path.insert(0, '/opt/FreeV2G')

from Whitebeet import Whitebeet

# EVerest module base
from everest.framework import Module, RuntimeSession, log


class WhiteBeetChargerModule(Module):
    """
    EVerest module for WhiteBeet ISO15118 Charger.
    
    Provides the ISO15118_charger interface using WhiteBeet's
    internal V2G implementation instead of external V2G software.
    """
    
    def __init__(self, session: RuntimeSession):
        super().__init__(session)
        
        self.whitebeet = None
        self.terminate = Event()
        self.v2g_thread = None
        
        # Configuration will be set in main()
        self.device = None
        self.whitebeet_mac = None
        self.payment_enable_eim = None
        self.payment_enable_contract = None
        self.ac_nominal_voltage = None
        self.free_service = None
        self.module_ref = None
        
        # Session state
        self.session_active = False
        self.authorization_received = False
        self.charging_started = False
        
    def initialize(self):
        """Initialize the WhiteBeet hardware and V2G service."""
        log.info(f"WhiteBeet Charger module initializing (device: {self.device}, mac: {self.whitebeet_mac})")
        
        # Connect to WhiteBeet
        self.whitebeet = Whitebeet("ETH", self.device, self.whitebeet_mac)
        log.info(f"WhiteBeet firmware version: {self.whitebeet.version}")
        
        # Set V2G mode to EVSE
        log.info("Setting V2G mode to EVSE")
        self.whitebeet.v2gSetMode(1)  # 1 = EVSE mode
        
        # Configure EVSE parameters
        evse_config = {
            "evseid": bytes.fromhex(self.whitebeet_mac.replace(":", "")),
            "protocol_count": 1,
            "protocols": [1],  # ISO15118-2
            "payment_method_count": 2 if self.payment_enable_contract else 1,
            "payment_method": [0, 1] if self.payment_enable_contract else [0],  # 0=EIM, 1=Contract
            "energy_transfer_mode_count": 1,
            "energy_transfer_mode": [0],  # AC single phase
            "free_service": 1 if self.free_service else 0,
        }
        
        log.info("Setting EVSE V2G configuration")
        self.whitebeet.v2gEvseSetConfiguration(evse_config)
        
        # Set AC charging parameters
        ac_params = {
            "nominal_voltage": self.ac_nominal_voltage,
            "max_current": 32,  # Will be updated from EVerest
        }
        log.info(f"Setting AC charging parameters: {ac_params}")
        self.whitebeet.v2gSetACChargingParameters(ac_params)
        
        # Configure SDP (Service Discovery Protocol)
        sdp_config = {
            "port": 15118,
            "security": 0,  # 0=TLS optional, 1=TLS required, 2=No TLS
        }
        log.info("Setting SDP configuration")
        self.whitebeet.v2gEvseSetSdpConfig(sdp_config)
        
        # Start V2G listener thread
        self.v2g_thread = Thread(target=self._v2g_worker, daemon=True)
        self.v2g_thread.start()
        
        log.info("WhiteBeet Charger ready")
    
    def cleanup(self):
        """Cleanup resources."""
        log.info("WhiteBeet Charger shutting down")
        self.terminate.set()
        if self.v2g_thread:
            self.v2g_thread.join(timeout=2.0)
        if self.whitebeet:
            try:
                self.whitebeet.v2gEvseStopListen()
                self.whitebeet.v2gStop()
            except:
                pass
    
    def _v2g_worker(self):
        """Background thread that manages V2G session."""
        log.info("V2G worker thread started")
        
        try:
            # Start listening for V2G sessions
            log.info("Starting V2G listener")
            self.whitebeet.v2gEvseStartListen()
            
            while not self.terminate.is_set():
                # Poll for V2G events/messages from WhiteBeet
                # The WhiteBeet firmware handles the ISO15118 protocol
                # We just need to bridge events to EVerest
                
                # In a full implementation, you would:
                # 1. Poll WhiteBeet for session events
                # 2. Publish events to EVerest via module_ref.publish_variable()
                # 3. Handle authorization requests
                # 4. Start/stop charging based on protocol state
                
                time.sleep(0.1)
                
        except Exception as e:
            log.error(f"V2G worker error: {e}")
    
    # ISO15118_charger interface command handlers
    
    def handle_authorization_response(self, args):
        """Handle authorization response from Auth module."""
        authorization_status = args.get("authorization_status", "Accepted")
        certificate_status = args.get("certificate_status", "Accepted")
        
        log.info(f"Authorization response: {authorization_status}")
        
        # Send authorization status to WhiteBeet
        status_code = 0 if authorization_status == "Accepted" else 1
        self.whitebeet.v2gEvseSetAuthorizationStatus(status_code)
        self.authorization_received = True
    
    def handle_ac_contactor_closed(self, args):
        """Called when AC contactor is closed."""
        allow_power_on = args.get("allow_power_on", True)
        log.info(f"AC contactor closed: allow_power_on={allow_power_on}")
        
        if allow_power_on and self.authorization_received:
            log.info("Starting charging")
            self.whitebeet.v2gEvseStartCharging()
            self.charging_started = True
    
    def handle_stop_charging(self, args):
        """Stop charging session."""
        log.info("Stopping charging")
        self.whitebeet.v2gEvseStopCharging()
        self.charging_started = False
    
    def handle_update_ac_max_current(self, args):
        """Update maximum AC current limit."""
        max_current = args.get("max_current", 32)
        log.info(f"Updating AC max current to {max_current}A")
        
        # Update AC charging parameters
        ac_params = {
            "nominal_voltage": self.ac_nominal_voltage,
            "max_current": max_current,
        }
        self.whitebeet.v2gEvseUpdateACChargingParameters(ac_params)
    
    def handle_session_setup(self, args):
        """Handle session setup request."""
        log.info("Session setup")
        # WhiteBeet handles this internally
        return {}
    
    def handle_certificate_response(self, args):
        """Handle certificate response (for PnC)."""
        log.info("Certificate response")
        # WhiteBeet handles this internally
        return {}


# Module entry point
def main():
    # Create session from command line arguments provided by manager
    if len(sys.argv) != 3:
        session = RuntimeSession()
    else:
        session = RuntimeSession(sys.argv[1], sys.argv[2])
    
    module = WhiteBeetChargerModule(session)
    
    # Initialize and connect to the framework
    setup = module.say_hello()
    
    # Access configuration parameters
    device = setup.configs.implementations["charger"].get("device", "eth0")
    whitebeet_mac = setup.configs.implementations["charger"].get("whitebeet_mac", "c4:93:00:34:a4:e4")
    payment_enable_eim = setup.configs.implementations["charger"].get("payment_enable_eim", True)
    payment_enable_contract = setup.configs.implementations["charger"].get("payment_enable_contract", False)
    ac_nominal_voltage = setup.configs.implementations["charger"].get("ac_nominal_voltage", 230)
    free_service = setup.configs.implementations["charger"].get("free_service", True)
    
    # Store config in module
    module.device = device
    module.whitebeet_mac = whitebeet_mac
    module.payment_enable_eim = payment_enable_eim
    module.payment_enable_contract = payment_enable_contract
    module.ac_nominal_voltage = ac_nominal_voltage
    module.free_service = free_service
    module.module_ref = module
    
    # Register command handlers
    def handle_authorization_response(args):
        return module.handle_authorization_response(args)
    
    def handle_ac_contactor_closed(args):
        return module.handle_ac_contactor_closed(args)
    
    def handle_stop_charging(args):
        return module.handle_stop_charging(args)
    
    def handle_update_ac_max_current(args):
        return module.handle_update_ac_max_current(args)
    
    def handle_session_setup(args):
        return module.handle_session_setup(args)
    
    def handle_certificate_response(args):
        return module.handle_certificate_response(args)
    
    module.implement_command("charger", "authorization_response", handle_authorization_response)
    module.implement_command("charger", "ac_contactor_closed", handle_ac_contactor_closed)
    module.implement_command("charger", "stop_charging", handle_stop_charging)
    module.implement_command("charger", "update_ac_max_current", handle_update_ac_max_current)
    module.implement_command("charger", "session_setup", handle_session_setup)
    module.implement_command("charger", "certificate_response", handle_certificate_response)
    
    # Signal that we're ready
    module.init_done()
    
    # Initialize module
    module.initialize()
    
    # Keep the module running
    running = [True]
    
    def signal_handler(signum, frame):
        log.info("Received shutdown signal, exiting...")
        running[0] = False
        module.terminate.set()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        while running[0]:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Keyboard interrupt received, exiting...")
    finally:
        module.cleanup()


if __name__ == "__main__":
    main()
