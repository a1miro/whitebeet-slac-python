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
            "allow_unsecure": True,   # Allow connections without TLS
            "unsecure_port": 49153,   # Dynamic port for internal communication (49152-65535 range)
            "allow_secure": True,    # No TLS for testing 
            "secure_port": 49154,
            "security": 0  # 0=TLS optional, 1=TLS required, 2=No TLS
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
                # Poll for V2G notification messages from WhiteBeet firmware
                try:
                    sub_id, payload = self.whitebeet.v2gEvseReceiveRequestSilent()
                    
                    if sub_id is not None:
                        log.info(f"Received V2G notification: sub_id=0x{sub_id:02X}, payload_len={len(payload) if payload else 0}")
                        
                        # TODO: Parse notification and bridge to EVerest
                        # For now, just log that we're receiving messages
                        
                except Exception as e:
                    log.error(f"Error receiving V2G message: {e}")
                    time.sleep(0.1)
                
        except Exception as e:
            log.error(f"V2G worker error: {e}")
    
    # ISO15118_charger interface command handlers
    
    def handle_authorization_response(self, args):
        """Handle authorization response from Auth module."""
        authorization_status = args.get("authorization_status", "Accepted")
        certificate_status = args.get("certificate_status", "Accepted")
        
        log.info(f"Authorization response: {authorization_status}")
        
        if self.whitebeet is None:
            log.warning("WhiteBeet not initialized yet, skipping authorization response")
            return
        
        # Send authorization status to WhiteBeet
        status_code = 0 if authorization_status == "Accepted" else 1
        self.whitebeet.v2gEvseSetAuthorizationStatus(status_code)
        self.authorization_received = True
    
    def handle_ac_contactor_closed(self, args):
        """Called when AC contactor is closed."""
        allow_power_on = args.get("allow_power_on", True)
        log.info(f"AC contactor closed: allow_power_on={allow_power_on}")
        
        if self.whitebeet is None:
            log.warning("WhiteBeet not initialized yet, skipping contactor closed")
            return
        
        if allow_power_on and self.authorization_received:
            log.info("Starting charging")
            self.whitebeet.v2gEvseStartCharging()
            self.charging_started = True
    
    def handle_stop_charging(self, args):
        """Stop charging session."""
        log.info("Stopping charging")
        
        if self.whitebeet is None:
            log.warning("WhiteBeet not initialized yet, skipping stop charging")
            return
        
        self.whitebeet.v2gEvseStopCharging()
        self.charging_started = False
    
    def handle_update_ac_max_current(self, args):
        """Update maximum AC current limit."""
        max_current = args.get("max_current", 32)
        log.info(f"Updating AC max current to {max_current}A")
        
        if self.whitebeet is None:
            log.warning("WhiteBeet not initialized yet, will use default current")
            return
        
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
    
    def handle_setup(self, args):
        """Initial setup of the charger."""
        log.info("Setup called")
        return {}
    
    def handle_set_charging_parameters(self, args):
        """Set charging parameters."""
        log.info("Set charging parameters")
        return {}
    
    def handle_bpt_setup(self, args):
        """Bidirectional power transfer setup."""
        log.info("BPT setup")
        return {}
    
    def handle_set_powersupply_capabilities(self, args):
        """Set power supply capabilities."""
        log.info("Set powersupply capabilities")
        return {}
    
    def handle_dlink_ready(self, args):
        """Data link ready signal from SLAC."""
        log.info(f"Data link ready: {args.get('value', False)}")
        return {}
    
    def handle_cable_check_finished(self, args):
        """Cable check finished."""
        log.info(f"Cable check finished: {args.get('status', False)}")
        return {}
    
    def handle_receipt_is_required(self, args):
        """Receipt is required."""
        log.info(f"Receipt required: {args.get('receipt_required', False)}")
        return {}
    
    def handle_pause_charging(self, args):
        """Pause charging."""
        log.info(f"Pause charging: {args.get('pause', False)}")
        return {}
    
    def handle_no_energy_pause_charging(self, args):
        """No energy pause charging."""
        log.info(f"No energy pause: {args.get('mode', 'unknown')}")
        return {}
    
    def handle_update_energy_transfer_modes(self, args):
        """Update energy transfer modes."""
        log.info("Update energy transfer modes")
        return {}
    
    def handle_update_ac_parameters(self, args):
        """Update AC parameters."""
        log.info("Update AC parameters")
        return {}
    
    def handle_update_ac_maximum_limits(self, args):
        """Update AC maximum limits."""
        log.info("Update AC maximum limits")
        return {}
    
    def handle_update_ac_minimum_limits(self, args):
        """Update AC minimum limits."""
        log.info("Update AC minimum limits")
        return {}
    
    def handle_update_ac_target_values(self, args):
        """Update AC target values."""
        log.info("Update AC target values")
        return {}
    
    def handle_update_ac_present_power(self, args):
        """Update AC present power."""
        log.info("Update AC present power")
        return {}
    
    def handle_update_dc_maximum_limits(self, args):
        """Update DC maximum limits."""
        log.info("Update DC maximum limits")
        return {}
    
    def handle_update_dc_minimum_limits(self, args):
        """Update DC minimum limits."""
        log.info("Update DC minimum limits")
        return {}
    
    def handle_update_dc_present_values(self, args):
        """Update DC present values."""
        log.info("Update DC present values")
        return {}
    
    def handle_update_isolation_status(self, args):
        """Update isolation status."""
        log.info("Update isolation status")
        return {}
    
    def handle_update_meter_info(self, args):
        """Update meter info."""
        log.info("Update meter info")
        return {}
    
    def handle_send_error(self, args):
        """Send error to EV."""
        log.info(f"Send error: {args}")
        return {}
    
    def handle_reset_error(self, args):
        """Reset error."""
        log.info("Reset error")
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
    
    def handle_setup(args):
        return module.handle_setup(args)
    
    def handle_set_charging_parameters(args):
        return module.handle_set_charging_parameters(args)
    
    def handle_bpt_setup(args):
        return module.handle_bpt_setup(args)
    
    def handle_set_powersupply_capabilities(args):
        return module.handle_set_powersupply_capabilities(args)
    
    def handle_dlink_ready(args):
        return module.handle_dlink_ready(args)
    
    def handle_cable_check_finished(args):
        return module.handle_cable_check_finished(args)
    
    def handle_receipt_is_required(args):
        return module.handle_receipt_is_required(args)
    
    def handle_pause_charging(args):
        return module.handle_pause_charging(args)
    
    def handle_no_energy_pause_charging(args):
        return module.handle_no_energy_pause_charging(args)
    
    def handle_update_energy_transfer_modes(args):
        return module.handle_update_energy_transfer_modes(args)
    
    def handle_update_ac_parameters(args):
        return module.handle_update_ac_parameters(args)
    
    def handle_update_ac_maximum_limits(args):
        return module.handle_update_ac_maximum_limits(args)
    
    def handle_update_ac_minimum_limits(args):
        return module.handle_update_ac_minimum_limits(args)
    
    def handle_update_ac_target_values(args):
        return module.handle_update_ac_target_values(args)
    
    def handle_update_ac_present_power(args):
        return module.handle_update_ac_present_power(args)
    
    def handle_update_dc_maximum_limits(args):
        return module.handle_update_dc_maximum_limits(args)
    
    def handle_update_dc_minimum_limits(args):
        return module.handle_update_dc_minimum_limits(args)
    
    def handle_update_dc_present_values(args):
        return module.handle_update_dc_present_values(args)
    
    def handle_update_isolation_status(args):
        return module.handle_update_isolation_status(args)
    
    def handle_update_meter_info(args):
        return module.handle_update_meter_info(args)
    
    def handle_send_error(args):
        return module.handle_send_error(args)
    
    def handle_reset_error(args):
        return module.handle_reset_error(args)
    
    module.implement_command("charger", "setup", handle_setup)
    module.implement_command("charger", "set_charging_parameters", handle_set_charging_parameters)
    module.implement_command("charger", "session_setup", handle_session_setup)
    module.implement_command("charger", "bpt_setup", handle_bpt_setup)
    module.implement_command("charger", "set_powersupply_capabilities", handle_set_powersupply_capabilities)
    module.implement_command("charger", "authorization_response", handle_authorization_response)
    module.implement_command("charger", "ac_contactor_closed", handle_ac_contactor_closed)
    module.implement_command("charger", "dlink_ready", handle_dlink_ready)
    module.implement_command("charger", "cable_check_finished", handle_cable_check_finished)
    module.implement_command("charger", "receipt_is_required", handle_receipt_is_required)
    module.implement_command("charger", "stop_charging", handle_stop_charging)
    module.implement_command("charger", "pause_charging", handle_pause_charging)
    module.implement_command("charger", "no_energy_pause_charging", handle_no_energy_pause_charging)
    module.implement_command("charger", "update_energy_transfer_modes", handle_update_energy_transfer_modes)
    module.implement_command("charger", "update_ac_max_current", handle_update_ac_max_current)
    module.implement_command("charger", "update_ac_parameters", handle_update_ac_parameters)
    module.implement_command("charger", "update_ac_maximum_limits", handle_update_ac_maximum_limits)
    module.implement_command("charger", "update_ac_minimum_limits", handle_update_ac_minimum_limits)
    module.implement_command("charger", "update_ac_target_values", handle_update_ac_target_values)
    module.implement_command("charger", "update_ac_present_power", handle_update_ac_present_power)
    module.implement_command("charger", "update_dc_maximum_limits", handle_update_dc_maximum_limits)
    module.implement_command("charger", "update_dc_minimum_limits", handle_update_dc_minimum_limits)
    module.implement_command("charger", "update_dc_present_values", handle_update_dc_present_values)
    module.implement_command("charger", "update_isolation_status", handle_update_isolation_status)
    module.implement_command("charger", "update_meter_info", handle_update_meter_info)
    module.implement_command("charger", "send_error", handle_send_error)
    module.implement_command("charger", "reset_error", handle_reset_error)
    
    # Initialize module first (before signaling ready)
    module.initialize()
    
    # Signal that we're ready
    module.init_done()
    
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
