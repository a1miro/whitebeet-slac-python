#!/usr/bin/env python3
"""
WhiteBeet Combined SLAC and ISO15118 Charger Module for EVerest
Provides both SLAC and ISO15118_charger interfaces using a single WhiteBeet instance

This module manages both SLAC (ISO15118-3) and V2G (ISO15118-2) communication
using WhiteBeet hardware's built-in implementations.
"""

import sys
import os
import time
import signal
from threading import Thread, Event

# Add FreeV2G to Python path
FREEV2G_PATHS = [
    os.environ.get('FREEV2G_PATH'),
    '/usr/local/share/FreeV2G',
    '/usr/share/FreeV2G',
    '/opt/FreeV2G'
]
FREEV2G_PATHS.append(os.path.join(os.path.dirname(__file__), '../../FreeV2G'))

FREEV2G_PATH = None
for path in FREEV2G_PATHS:
    if path and os.path.isdir(path):
        FREEV2G_PATH = path
        break

if not FREEV2G_PATH:
    raise ImportError(f"FreeV2G library not found. Searched paths: {[p for p in FREEV2G_PATHS if p]}")

sys.path.insert(0, FREEV2G_PATH)

from Whitebeet import Whitebeet

# EVerest module base
from everest.framework import Module, RuntimeSession, log

log.info(f"Using FreeV2G from: {FREEV2G_PATH}")


class WhiteBeetModule(Module):
    """
    Combined EVerest module for WhiteBeet SLAC and ISO15118 Charger.
    
    This module provides both:
    - slac interface (ISO15118-3)
    - ISO15118_charger interface (ISO15118-2 V2G)
    
    Using a single WhiteBeet hardware instance to avoid multiprocessing conflicts.
    """
    
    def __init__(self, session: RuntimeSession):
        super().__init__(session)
        
        # Single WhiteBeet instance for both SLAC and V2G
        self.whitebeet = None
        self.terminate = Event()
        
        # Worker threads
        self.slac_thread = None
        self.v2g_thread = None
        
        # Configuration (set in main())
        self.device = None
        self.whitebeet_mac = None
        self.slac_timeout_ms = None
        self.publish_mac_on_match_cnf = None
        self.payment_enable_eim = None
        self.payment_enable_contract = None
        self.ac_nominal_voltage = None
        self.free_service = None
        
        # SLAC state
        self.slac_enabled = False
        self.in_bcd_state = False
        self.slac_matched = False
        
        # V2G/Charging state
        self.session_active = False
        self.authorization_received = False
        self.charging_started = False
        
    def initialize(self):
        """Initialize the WhiteBeet hardware."""
        log.info(f"WhiteBeet module initializing (device: {self.device}, mac: {self.whitebeet_mac})")
        
        # Connect to WhiteBeet (single instance for both SLAC and V2G)
        self.whitebeet = Whitebeet("ETH", self.device, self.whitebeet_mac)
        log.info(f"WhiteBeet firmware version: {self.whitebeet.version}")
        
        # Initialize Control Pilot for EVSE mode
        log.info("Initializing Control Pilot in EVSE mode")
        self.whitebeet.controlPilotSetMode(1)  # EVSE mode
        self.whitebeet.controlPilotSetDutyCycle(100)  # 100% duty cycle
        self.whitebeet.controlPilotStart()
        
        # Start SLAC module in EVSE mode
        log.info("Starting SLAC module in EVSE mode")
        self.whitebeet.slacStart(1)  # EVSE mode
        time.sleep(2)  # Wait for SLAC to be ready
        
        # Set V2G mode to EVSE
        log.info("Setting V2G mode to EVSE")
        self.whitebeet.v2gSetMode(1)  # 1 = EVSE mode
        
        # Configure EVSE V2G parameters
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
            "max_current": 32,
        }
        log.info(f"Setting AC charging parameters: {ac_params}")
        self.whitebeet.v2gSetACChargingParameters(ac_params)
        
        # Configure SDP (Service Discovery Protocol)
        sdp_config = {
            "port": 15118,
            "security": 0,  # 0=TLS optional
        }
        log.info("Setting SDP configuration")
        self.whitebeet.v2gEvseSetSdpConfig(sdp_config)
        
        # Publish initial SLAC state
        self.publish_variable("slac", "state", "UNMATCHED")
        
        # Start worker threads
        self.slac_thread = Thread(target=self._slac_worker, daemon=True)
        self.slac_thread.start()
        
        self.v2g_thread = Thread(target=self._v2g_worker, daemon=True)
        self.v2g_thread.start()
        
        log.info("WhiteBeet module ready (SLAC + V2G)")
    
    def cleanup(self):
        """Cleanup resources."""
        self.terminate.set()
        
        if self.slac_thread:
            self.slac_thread.join(timeout=2.0)
        if self.v2g_thread:
            self.v2g_thread.join(timeout=2.0)
            
        if self.whitebeet:
            try:
                self.whitebeet.controlPilotStop()
                self.whitebeet.slacStop()
                log.info("WhiteBeet module stopped")
            except Exception as e:
                log.error(f"Error during cleanup: {e}")
    
    # =========================================================================
    # SLAC Worker Thread
    # =========================================================================
    
    def _slac_worker(self):
        """Background thread that manages SLAC operations."""
        try:
            log.info("SLAC worker thread started")
            
            # Main SLAC loop
            while not self.terminate.is_set():
                if not self.slac_enabled or not self.in_bcd_state:
                    # Not enabled or not in charging state - wait
                    time.sleep(0.5)
                    continue
                
                # Vehicle connected and SLAC enabled - start matching
                log.info("Starting SLAC matching")
                self.publish_variable("slac", "state", "MATCHING")
                
                # Set duty cycle to 5% to signal EV to start SLAC
                self.whitebeet.controlPilotSetDutyCycle(5)
                
                # Start SLAC matching
                self.whitebeet.slacStartMatching()
                
                # Wait for SLAC to complete (blocking call with timeout)
                try:
                    matched = self.whitebeet.slacMatched()
                    
                    if matched:
                        log.info("✓ SLAC matching successful!")
                        self.slac_matched = True
                        self.publish_variable("slac", "state", "MATCHED")
                        self.publish_variable("slac", "dlink_ready", True)
                        
                        # TODO: Extract and publish EV MAC if configured
                        
                        # Stay matched until we leave BCD state
                        while self.in_bcd_state and not self.terminate.is_set():
                            time.sleep(0.1)
                        
                        # Left BCD state - terminate link
                        log.info("Left BCD state - terminating SLAC link")
                        self.slac_matched = False
                        self.publish_variable("slac", "state", "UNMATCHED")
                        self.publish_variable("slac", "dlink_ready", False)
                        
                        # Reset duty cycle to 100%
                        self.whitebeet.controlPilotSetDutyCycle(100)
                    else:
                        log.warning("SLAC matching failed or timed out")
                        self.publish_variable("slac", "state", "UNMATCHED")
                        time.sleep(2)
                        
                except Exception as e:
                    log.error(f"SLAC matching error: {e}")
                    self.publish_variable("slac", "state", "UNMATCHED")
                    time.sleep(2)
            
        except Exception as e:
            log.error(f"SLAC worker thread error: {e}", exc_info=True)
    
    # =========================================================================
    # V2G Worker Thread
    # =========================================================================
    
    def _v2g_worker(self):
        """Background thread that handles V2G communication."""
        try:
            log.info("V2G worker thread started")
            
            # Main V2G loop
            while not self.terminate.is_set():
                # Only start V2G after SLAC is matched
                if not self.slac_matched:
                    time.sleep(0.5)
                    continue
                
                # SLAC matched - start V2G listener
                if not self.session_active:
                    log.info("SLAC matched, starting V2G listener")
                    self.whitebeet.v2gEvseStartListen()
                    self.session_active = True
                
                # Poll for V2G notifications
                # TODO: Implement notification handling
                # notification = self.whitebeet.v2gEvseReceiveRequestSilent()
                # if notification:
                #     self._handle_v2g_notification(notification)
                
                time.sleep(0.1)
            
        except Exception as e:
            log.error(f"V2G worker error: {e}", exc_info=True)
    
    # =========================================================================
    # SLAC Interface Command Handlers
    # =========================================================================
    
    def handle_slac_reset(self, enable):
        """Reset SLAC module."""
        log.info(f"SLAC reset requested (enable: {enable})")
        self.slac_enabled = enable
        
        if enable:
            self.publish_variable("slac", "state", "MATCHING")
        else:
            self.publish_variable("slac", "state", "UNMATCHED")
            self.publish_variable("slac", "dlink_ready", False)
    
    def handle_slac_enter_bcd(self):
        """Signal that Control Pilot entered state B/C/D (vehicle connected)."""
        log.info("Entering BCD state (vehicle connected)")
        self.in_bcd_state = True
    
    def handle_slac_leave_bcd(self):
        """Signal that Control Pilot left state B/C/D (vehicle disconnected)."""
        log.info("Leaving BCD state (vehicle disconnected)")
        self.in_bcd_state = False
        self.session_active = False
    
    def handle_slac_dlink_terminate(self):
        """Terminate the data link."""
        log.info("Data link terminate requested")
        self.in_bcd_state = False
        self.slac_matched = False
        self.publish_variable("slac", "state", "UNMATCHED")
        self.publish_variable("slac", "dlink_ready", False)
    
    def handle_slac_dlink_error(self):
        """Handle data link error."""
        log.info("Data link error - restarting matching process")
        self.slac_matched = False
        self.publish_variable("slac", "state", "UNMATCHED")
        self.publish_variable("slac", "dlink_ready", False)
    
    def handle_slac_dlink_pause(self):
        """Request power saving mode while staying matched."""
        log.info("Data link pause requested (power saving mode)")
        # WhiteBeet doesn't have a specific pause mode
    
    # =========================================================================
    # ISO15118_charger Interface Command Handlers
    # =========================================================================
    
    def handle_setup(self, args):
        """Initial setup of the charger."""
        log.info("Charger setup called")
        return {}
    
    def handle_set_charging_parameters(self, args):
        """Set charging parameters."""
        log.info("Set charging parameters")
        return {}
    
    def handle_session_setup(self, args):
        """Handle session setup request."""
        log.info("Session setup")
        return {}
    
    def handle_bpt_setup(self, args):
        """Bidirectional power transfer setup."""
        log.info("BPT setup")
        return {}
    
    def handle_set_powersupply_capabilities(self, args):
        """Set power supply capabilities."""
        log.info("Set powersupply capabilities")
        return {}
    
    def handle_authorization_response(self, args):
        """Handle authorization response from Auth module."""
        authorization_status = args.get("authorization_status", "Accepted")
        log.info(f"Authorization response: {authorization_status}")
        
        if self.whitebeet is None:
            log.warning("WhiteBeet not initialized yet")
            return
        
        status_code = 0 if authorization_status == "Accepted" else 1
        self.whitebeet.v2gEvseSetAuthorizationStatus(status_code)
        self.authorization_received = True
    
    def handle_ac_contactor_closed(self, args):
        """Called when AC contactor is closed."""
        allow_power_on = args.get("allow_power_on", True)
        log.info(f"AC contactor closed: allow_power_on={allow_power_on}")
        
        if self.whitebeet is None:
            log.warning("WhiteBeet not initialized yet")
            return
        
        if allow_power_on and self.authorization_received:
            log.info("Starting charging")
            self.whitebeet.v2gEvseStartCharging()
            self.charging_started = True
    
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
    
    def handle_stop_charging(self, args):
        """Stop charging session."""
        log.info("Stopping charging")
        
        if self.whitebeet is None:
            log.warning("WhiteBeet not initialized yet")
            return
        
        self.whitebeet.v2gEvseStopCharging()
        self.charging_started = False
    
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
    
    def handle_update_ac_max_current(self, args):
        """Update maximum AC current limit."""
        max_current = args.get("max_current", 32)
        log.info(f"Updating AC max current to {max_current}A")
        
        if self.whitebeet is None:
            log.warning("WhiteBeet not initialized yet")
            return
        
        ac_params = {
            "nominal_voltage": self.ac_nominal_voltage,
            "max_current": max_current,
        }
        self.whitebeet.v2gEvseUpdateACChargingParameters(ac_params)
    
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


# ============================================================================
# Module Entry Point
# ============================================================================

def main():
    # Create session from command line arguments
    if len(sys.argv) != 3:
        session = RuntimeSession()
    else:
        session = RuntimeSession(sys.argv[1], sys.argv[2])
    
    module = WhiteBeetModule(session)
    
    # Initialize and connect to the framework
    setup = module.say_hello()
    
    # Access configuration parameters from both interfaces
    slac_config = setup.configs.implementations.get("slac", {})
    charger_config = setup.configs.implementations.get("charger", {})
    
    # SLAC configuration
    module.device = slac_config.get("device", "eth0")
    module.whitebeet_mac = slac_config.get("whitebeet_mac", "c4:93:00:34:a4:e4")
    module.slac_timeout_ms = slac_config.get("slac_timeout_ms", 50000)
    module.publish_mac_on_match_cnf = slac_config.get("publish_mac_on_match_cnf", True)
    
    # Charger configuration
    module.payment_enable_eim = charger_config.get("payment_enable_eim", True)
    module.payment_enable_contract = charger_config.get("payment_enable_contract", False)
    module.ac_nominal_voltage = charger_config.get("ac_nominal_voltage", 230)
    module.free_service = charger_config.get("free_service", True)
    
    # ========================================================================
    # Register SLAC Interface Commands
    # ========================================================================
    
    module.implement_command("slac", "reset", 
                            lambda args: module.handle_slac_reset(args["enable"]))
    module.implement_command("slac", "enter_bcd", 
                            lambda args: module.handle_slac_enter_bcd())
    module.implement_command("slac", "leave_bcd", 
                            lambda args: module.handle_slac_leave_bcd())
    module.implement_command("slac", "dlink_terminate", 
                            lambda args: module.handle_slac_dlink_terminate())
    module.implement_command("slac", "dlink_error", 
                            lambda args: module.handle_slac_dlink_error())
    module.implement_command("slac", "dlink_pause", 
                            lambda args: module.handle_slac_dlink_pause())
    
    # ========================================================================
    # Register ISO15118_charger Interface Commands
    # ========================================================================
    
    module.implement_command("charger", "setup", 
                            lambda args: module.handle_setup(args))
    module.implement_command("charger", "set_charging_parameters", 
                            lambda args: module.handle_set_charging_parameters(args))
    module.implement_command("charger", "session_setup", 
                            lambda args: module.handle_session_setup(args))
    module.implement_command("charger", "bpt_setup", 
                            lambda args: module.handle_bpt_setup(args))
    module.implement_command("charger", "set_powersupply_capabilities", 
                            lambda args: module.handle_set_powersupply_capabilities(args))
    module.implement_command("charger", "authorization_response", 
                            lambda args: module.handle_authorization_response(args))
    module.implement_command("charger", "ac_contactor_closed", 
                            lambda args: module.handle_ac_contactor_closed(args))
    module.implement_command("charger", "dlink_ready", 
                            lambda args: module.handle_dlink_ready(args))
    module.implement_command("charger", "cable_check_finished", 
                            lambda args: module.handle_cable_check_finished(args))
    module.implement_command("charger", "receipt_is_required", 
                            lambda args: module.handle_receipt_is_required(args))
    module.implement_command("charger", "stop_charging", 
                            lambda args: module.handle_stop_charging(args))
    module.implement_command("charger", "pause_charging", 
                            lambda args: module.handle_pause_charging(args))
    module.implement_command("charger", "no_energy_pause_charging", 
                            lambda args: module.handle_no_energy_pause_charging(args))
    module.implement_command("charger", "update_energy_transfer_modes", 
                            lambda args: module.handle_update_energy_transfer_modes(args))
    module.implement_command("charger", "update_ac_max_current", 
                            lambda args: module.handle_update_ac_max_current(args))
    module.implement_command("charger", "update_ac_parameters", 
                            lambda args: module.handle_update_ac_parameters(args))
    module.implement_command("charger", "update_ac_maximum_limits", 
                            lambda args: module.handle_update_ac_maximum_limits(args))
    module.implement_command("charger", "update_ac_minimum_limits", 
                            lambda args: module.handle_update_ac_minimum_limits(args))
    module.implement_command("charger", "update_ac_target_values", 
                            lambda args: module.handle_update_ac_target_values(args))
    module.implement_command("charger", "update_ac_present_power", 
                            lambda args: module.handle_update_ac_present_power(args))
    module.implement_command("charger", "update_dc_maximum_limits", 
                            lambda args: module.handle_update_dc_maximum_limits(args))
    module.implement_command("charger", "update_dc_minimum_limits", 
                            lambda args: module.handle_dc_minimum_limits(args))
    module.implement_command("charger", "update_dc_present_values", 
                            lambda args: module.handle_update_dc_present_values(args))
    module.implement_command("charger", "update_isolation_status", 
                            lambda args: module.handle_update_isolation_status(args))
    module.implement_command("charger", "update_meter_info", 
                            lambda args: module.handle_update_meter_info(args))
    module.implement_command("charger", "send_error", 
                            lambda args: module.handle_send_error(args))
    module.implement_command("charger", "reset_error", 
                            lambda args: module.handle_reset_error(args))
    
    # ========================================================================
    # Initialize and Run
    # ========================================================================
    
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
