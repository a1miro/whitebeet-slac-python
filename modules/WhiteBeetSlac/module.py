#!/usr/bin/env python3
"""
WhiteBeet SLAC Module for EVerest
Python implementation using FreeV2G library

This module provides ISO15118-3 SLAC functionality by directly interfacing
with WhiteBeet hardware through the FreeV2G Python library.
"""

import sys
import os
import time
import signal
from threading import Thread, Event

# Add FreeV2G to Python path
# Try multiple possible locations for FreeV2G
FREEV2G_PATHS = [
    os.environ.get('FREEV2G_PATH'),  # Environment variable override
    '/usr/local/share/FreeV2G',       # Default install location
    '/usr/share/FreeV2G',             # System install location
    '/opt/FreeV2G'                    # Legacy location
]
# Add local directory to search paths
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

log.info(f"[SLAC] Using FreeV2G from: {FREEV2G_PATH}")

class WhiteBeetSlacModule(Module):
    """
    EVerest module for WhiteBeet SLAC integration.
    
    This module manages SLAC (Signal Level Attenuation Characterization) 
    for ISO15118-3 using the WhiteBeet hardware's QCA7005 PLC chip.
    """
    
    def __init__(self, session: RuntimeSession):
        super().__init__(session)
        
        self.whitebeet = None
        self.slac_enabled = False
        self.in_bcd_state = False
        self.terminate = Event()
        self.slac_thread = None
        
        # Configuration will be set in main()
        self.device = None
        self.whitebeet_mac = None
        self.slac_timeout_ms = None
        self.publish_mac_on_match_cnf = None
        self.debug_auto_enable = None
        self.module_ref = None  # Will be set to Module instance for publishing
    
    def initialize(self):
        """Initialize the WhiteBeet hardware and start SLAC worker."""
        log.info(f"WhiteBeet SLAC module initialized (device: {self.device}, mac: {self.whitebeet_mac})")
        
        # Start SLAC worker thread
        self.slac_thread = Thread(target=self._slac_worker, daemon=True)
        self.slac_thread.start()
    
    def cleanup(self):
        """Cleanup resources."""
        self.terminate.set()
        if self.slac_thread:
            self.slac_thread.join(timeout=2.0)
        if self.whitebeet:
            try:
                self.whitebeet.controlPilotStop()
                self.whitebeet.slacStop()
            except:
                pass
    
    def _slac_worker(self):
        """Background thread that manages SLAC operations."""
        try:
            # Initialize WhiteBeet connection
            log.info(f"Connecting to WhiteBeet on {self.device} (MAC: {self.whitebeet_mac})")
            self.whitebeet = Whitebeet("ETH", self.device, self.whitebeet_mac)
            log.info(f"WhiteBeet firmware version: {self.whitebeet.version}")
            
            # Initialize Control Pilot for EVSE mode
            log.info("Initializing Control Pilot in EVSE mode...")
            self.whitebeet.controlPilotSetMode(1)  # EVSE mode
            self.whitebeet.controlPilotSetDutyCycle(100)  # 100% duty cycle
            self.whitebeet.controlPilotStart()
            log.info("Control Pilot initialized (mode: EVSE, duty cycle: 100%)")
            
            # Start SLAC module in EVSE mode
            log.info("Starting SLAC module in EVSE mode...")
            self.whitebeet.slacStart(1)  # EVSE mode
            time.sleep(2)  # Wait for SLAC to be ready
            log.info("SLAC module ready")
            
            # Publish initial state
            self.module_ref.publish_variable("main", "state", "UNMATCHED")
            
            # Debug auto-enable for testing without EvseManager
            if self.debug_auto_enable:
                log.info("[DEBUG] Auto-enabling SLAC and simulating BCD state for testing")
                self.slac_enabled = True
                self.in_bcd_state = True
            
            # Main SLAC loop
            while not self.terminate.is_set():
                if not self.slac_enabled or not self.in_bcd_state:
                    # Not enabled or not in charging state - wait
                    time.sleep(1)
                    continue
                
                # Vehicle connected and SLAC enabled - start matching
                log.info("Entering BCD state - starting SLAC matching")
                self.module_ref.publish_variable("main", "state", "MATCHING")
                
                # Set duty cycle to 5% to signal EV to start SLAC
                self.whitebeet.controlPilotSetDutyCycle(5)
                
                # Start SLAC matching
                log.info("Starting SLAC matching...")
                self.whitebeet.slacStartMatching()
                
                # Wait for SLAC to complete (blocking call with timeout)
                try:
                    matched = self.whitebeet.slacMatched()
                    
                    if matched:
                        log.info("✓ SLAC matching successful!")
                        self.module_ref.publish_variable("main", "state", "MATCHED")
                        self.module_ref.publish_variable("main", "dlink_ready", True)
                        
                        # TODO: Extract and publish EV MAC if configured
                        # if self.publish_mac:
                        #     ev_mac = self._get_ev_mac()
                        #     self.module_ref.publish_variable("main", "ev_mac_address", ev_mac)
                        
                        # Stay matched until we leave BCD state
                        while self.in_bcd_state and not self.terminate.is_set():
                            time.sleep(0.1)
                        
                        # Left BCD state - terminate link
                        log.info("Left BCD state - terminating SLAC link")
                        self.module_ref.publish_variable("main", "state", "UNMATCHED")
                        self.module_ref.publish_variable("main", "dlink_ready", False)
                        
                        # Reset duty cycle to 100%
                        self.whitebeet.controlPilotSetDutyCycle(100)
                    else:
                        log.info("✗ SLAC matching failed or timed out")
                        self.module_ref.publish_variable("main", "state", "UNMATCHED")
                        self.publish.request_error_routine()
                        
                        # Wait before retry
                        time.sleep(2)
                        
                except TimeoutError as e:
                    log.info(f"SLAC matching timeout: {e}")
                    self.module_ref.publish_variable("main", "state", "UNMATCHED")
                    self.publish.request_error_routine()
                    time.sleep(2)
                except Exception as e:
                    log.info(f"SLAC matching error: {e}")
                    self.module_ref.publish_variable("main", "state", "UNMATCHED")
                    self.publish.request_error_routine()
                    time.sleep(2)
            
        except Exception as e:
            log.info(f"SLAC worker thread error: {e}", exc_info=True)
        finally:
            # Cleanup
            if self.whitebeet:
                try:
                    log.info("Stopping SLAC module...")
                    self.whitebeet.slacStop()
                    self.whitebeet.controlPilotStop()
                    log.info("SLAC module stopped")
                except Exception as e:
                    log.info(f"Error during cleanup: {e}")
    
    # Command handlers (called by EVerest framework)
    
    def handle_reset(self, enable):
        """Reset SLAC module."""
        log.info(f"SLAC reset requested (enable: {enable})")
        self.slac_enabled = enable
        
        if enable:
            self.module_ref.publish_variable("main", "state", "MATCHING")
        else:
            self.module_ref.publish_variable("main", "state", "UNMATCHED")
            self.module_ref.publish_variable("main", "dlink_ready", False)
    
    def handle_enter_bcd(self):
        """Signal that Control Pilot entered state B/C/D (vehicle connected)."""
        log.info("Entering BCD state (vehicle connected)")
        self.in_bcd_state = True
    
    def handle_leave_bcd(self):
        """Signal that Control Pilot left state B/C/D (vehicle disconnected)."""
        log.info("Leaving BCD state (vehicle disconnected)")
        self.in_bcd_state = False
    
    def handle_dlink_terminate(self):
        """Terminate the data link."""
        log.info("Data link terminate requested")
        self.in_bcd_state = False
        self.module_ref.publish_variable("main", "state", "UNMATCHED")
        self.module_ref.publish_variable("main", "dlink_ready", False)
    
    def handle_dlink_error(self):
        """Handle data link error."""
        log.info("Data link error - restarting matching process")
        self.module_ref.publish_variable("main", "state", "UNMATCHED")
        self.module_ref.publish_variable("main", "dlink_ready", False)
        # Worker thread will restart matching if still in BCD state
    
    def handle_dlink_pause(self):
        """Request power saving mode while staying matched."""
        log.info("Data link pause requested (power saving mode)")
        # WhiteBeet doesn't have a specific pause mode
        # Just log it for now


# Module entry point
def main():
    # Create session from command line arguments provided by manager
    if len(sys.argv) != 3:
        session = RuntimeSession()
    else:
        session = RuntimeSession(sys.argv[1], sys.argv[2])
    
    module = WhiteBeetSlacModule(session)
    
    # Initialize and connect to the framework
    setup = module.say_hello()
    
    # Access configuration parameters
    device = setup.configs.implementations["main"].get("device", "eth0")
    whitebeet_mac = setup.configs.implementations["main"].get("whitebeet_mac", "c4:93:00:34:a4:e4")
    slac_timeout_ms = setup.configs.implementations["main"].get("slac_timeout_ms", 50000)
    publish_mac = setup.configs.implementations["main"].get("publish_mac_on_match_cnf", True)
    debug_auto_enable = setup.configs.implementations["main"].get("debug_auto_enable", False)
    
    # Store config in module
    module.device = device
    module.whitebeet_mac = whitebeet_mac
    module.slac_timeout_ms = slac_timeout_ms
    module.publish_mac_on_match_cnf = publish_mac
    module.debug_auto_enable = debug_auto_enable
    module.module_ref = module  # Store reference for publishing
    
    # Register command handlers
    def handle_reset(args):
        return module.handle_reset(args["enable"])
    
    def handle_enter_bcd(args):
        return module.handle_enter_bcd()
    
    def handle_leave_bcd(args):
        return module.handle_leave_bcd()
    
    def handle_dlink_terminate(args):
        return module.handle_dlink_terminate()
    
    def handle_dlink_error(args):
        return module.handle_dlink_error()
    
    def handle_dlink_pause(args):
        return module.handle_dlink_pause()
    
    module.implement_command("main", "reset", handle_reset)
    module.implement_command("main", "enter_bcd", handle_enter_bcd)
    module.implement_command("main", "leave_bcd", handle_leave_bcd)
    module.implement_command("main", "dlink_terminate", handle_dlink_terminate)
    module.implement_command("main", "dlink_error", handle_dlink_error)
    module.implement_command("main", "dlink_pause", handle_dlink_pause)
    
    # Signal that we're ready
    module.init_done()
    
    # Initialize module
    module.initialize()
    
    # Keep the module running
    running = [True]
    
    def signal_handler(signum, frame):
        log.info("[SLAC] Received shutdown signal, exiting...")
        running[0] = False
        module.terminate.set()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        while running[0]:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("[SLAC] Keyboard interrupt received, exiting...")
    finally:
        module.cleanup()


if __name__ == "__main__":
    main()
