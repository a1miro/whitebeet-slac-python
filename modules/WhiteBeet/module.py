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
        # V2G interface command handlers (FreeV2G EVSE structure)
        def v2g_handle_session_started(self, args):
            log.info("V2G: Session started")
            # Parse and handle session started, e.g. protocol, session_id, evcc_id
            return {}

        def v2g_handle_payment_selected(self, args):
            log.info("V2G: Payment selected")
            # Parse and handle payment selection
            return {}

        def v2g_handle_request_authorization(self, args):
            log.info("V2G: Request authorization")
            # Handle authorization request, set status
            return {}

        def v2g_handle_energy_transfer_mode_selected(self, args):
            log.info("V2G: Energy transfer mode selected")
            # Handle energy transfer mode selection
            return {}

        def v2g_handle_request_schedules(self, args):
            log.info("V2G: Request schedules")
            # Handle schedule request
            return {}

        def v2g_handle_dc_charge_parameters_changed(self, args):
            log.info("V2G: DC charge parameters changed")
            # Handle DC charge parameters
            return {}

        def v2g_handle_ac_charge_parameters_changed(self, args):
            log.info("V2G: AC charge parameters changed")
            # Handle AC charge parameters
            return {}

        def v2g_handle_request_cable_check(self, args):
            log.info("V2G: Request cable check")
            # Handle cable check request
            return {}

        def v2g_handle_pre_charge_started(self, args):
            log.info("V2G: Pre charge started")
            # Handle pre charge started
            return {}

        def v2g_handle_request_start_charging(self, args):
            log.info("V2G: Start charging requested")
            # Handle start charging request
            return {}

        def v2g_handle_request_stop_charging(self, args):
            log.info("V2G: Stop charging requested")
            # Handle stop charging request
            return {}

        def v2g_handle_welding_detection_started(self, args):
            log.info("V2G: Welding detection started")
            # Handle welding detection
            return {}

        def v2g_handle_session_stopped(self, args):
            log.info("V2G: Session stopped")
            # Handle session stopped
            return {}

        def v2g_handle_session_error(self, args):
            log.info("V2G: Session error")
            # Handle session error
            return {}

        def v2g_handle_certificate_installation_requested(self, args):
            log.info("V2G: Certificate installation requested")
            # Handle certificate installation request
            return {}

        def v2g_handle_certificate_update_requested(self, args):
            log.info("V2G: Certificate update requested")
            # Handle certificate update request
            return {}

        def v2g_handle_metering_receipt_status(self, args):
            log.info("V2G: Metering receipt status")
            # Handle metering receipt status
            return {}
        # ...existing code...
        # Register V2G interface commands after module instantiation
        module.implement_command("v2g", "session_started", lambda args: module.v2g_handle_session_started(args))
        module.implement_command("v2g", "payment_selected", lambda args: module.v2g_handle_payment_selected(args))
        module.implement_command("v2g", "request_authorization", lambda args: module.v2g_handle_request_authorization(args))
        module.implement_command("v2g", "energy_transfer_mode_selected", lambda args: module.v2g_handle_energy_transfer_mode_selected(args))
        module.implement_command("v2g", "request_schedules", lambda args: module.v2g_handle_request_schedules(args))
        module.implement_command("v2g", "dc_charge_parameters_changed", lambda args: module.v2g_handle_dc_charge_parameters_changed(args))
        module.implement_command("v2g", "ac_charge_parameters_changed", lambda args: module.v2g_handle_ac_charge_parameters_changed(args))
        module.implement_command("v2g", "request_cable_check", lambda args: module.v2g_handle_request_cable_check(args))
        module.implement_command("v2g", "pre_charge_started", lambda args: module.v2g_handle_pre_charge_started(args))
        module.implement_command("v2g", "request_start_charging", lambda args: module.v2g_handle_request_start_charging(args))
        module.implement_command("v2g", "request_stop_charging", lambda args: module.v2g_handle_request_stop_charging(args))
        module.implement_command("v2g", "welding_detection_started", lambda args: module.v2g_handle_welding_detection_started(args))
        module.implement_command("v2g", "session_stopped", lambda args: module.v2g_handle_session_stopped(args))
        module.implement_command("v2g", "session_error", lambda args: module.v2g_handle_session_error(args))
        module.implement_command("v2g", "certificate_installation_requested", lambda args: module.v2g_handle_certificate_installation_requested(args))
        module.implement_command("v2g", "certificate_update_requested", lambda args: module.v2g_handle_certificate_update_requested(args))
        module.implement_command("v2g", "metering_receipt_status", lambda args: module.v2g_handle_metering_receipt_status(args))
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
        
        try:
            # Connect to WhiteBeet (single instance for both SLAC and V2G)
            log.info("Creating WhiteBeet instance...")
            self.whitebeet = Whitebeet("ETH", self.device, self.whitebeet_mac)
            log.info(f"WhiteBeet firmware version: {self.whitebeet.version}")
        except Exception as e:
            log.error(f"Failed to create WhiteBeet instance: {e}")
            log.error("This may indicate another WhiteBeet instance is already running")
            log.error("Try stopping all manager processes and retry")
            raise
        
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
            "evse_id_DIN": "49A80737A45678",  # DIN SPEC 91286 EVSE ID
            "evse_id_ISO": "DE*PNX*E1234567*1",  # ISO 15118 EVSE ID
            "protocol": [1],  # ISO15118-2
            "payment_method": [0, 1] if self.payment_enable_contract else [0],  # 0=EIM, 1=PnC
            "certificate_installation_support": self.payment_enable_contract,
            "certificate_update_support": self.payment_enable_contract,
            "energy_transfer_mode": [0],  # AC single phase (0=AC_single_phase_core)
        }
        log.info("Setting EVSE V2G configuration")
        self.whitebeet.v2gEvseSetConfiguration(evse_config)
        
        # Set AC charging parameters for EVSE
        ac_params = {
            "rcd_status": False,  # RCD (Residual Current Device) status
            "nominal_voltage": int(self.ac_nominal_voltage),
            "max_current": 32,
        }
        log.info(f"Setting AC charging parameters: {ac_params}")
        self.whitebeet.v2gEvseSetAcChargingParameters(ac_params)
        
        # Configure SDP (Service Discovery Protocol)
        sdp_config = {
            "allow_unsecure": True,   # Allow connections without TLS
            "unsecure_port": 49152,   # Dynamic port for internal communication (49152-65535 range)
            #"allow_secure": False,    # Disable TLS
            #"secure_port": 49152      # Must be present and in valid range
        }
        #log.info("Setting SDP configuration")
        #self.whitebeet.v2gEvseSetSdpConfig(sdp_config)
        
        # Publish initial SLAC state
        self.publish_variable("slac", "state", "UNMATCHED")
        
        # Start worker threads
        self.slac_thread = Thread(target=self._slac_worker, daemon=True)
        self.slac_thread.start()
        
        # ...existing code...
    
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
    
    # ...existing code...
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
            "rcd_status": False,
            "max_current": max_current,
        }
        self.whitebeet.v2gEvseUpdateAcChargingParameters(ac_params)
    
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
