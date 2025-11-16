#!/usr/bin/env python3
"""
WhiteBeet SLAC Module for EVerest
Python implementation using FreeV2G library

This module provides ISO15118-3 SLAC functionality by directly interfacing
with WhiteBeet hardware through the FreeV2G Python library.
"""

import sys
import time
import logging
from threading import Thread, Event

# Add FreeV2G to Python path
sys.path.insert(0, '/opt/FreeV2G')

from Whitebeet import Whitebeet

# EVerest module base
from everest.framework import Module, log


class WhiteBeetSlacModule(Module):
    """
    EVerest module for WhiteBeet SLAC integration.
    
    This module manages SLAC (Signal Level Attenuation Characterization) 
    for ISO15118-3 using the WhiteBeet hardware's QCA7005 PLC chip.
    """
    
    def __init__(self):
        super().__init__()
        
        self.whitebeet = None
        self.slac_enabled = False
        self.in_bcd_state = False
        self.terminate = Event()
        self.slac_thread = None
        
        # Get configuration
        self.device = self.config.device
        self.whitebeet_mac = self.config.whitebeet_mac
        self.slac_timeout_ms = self.config.slac_timeout_ms
        self.publish_mac = self.config.publish_mac_on_match_cnf
        
        log.info(f"WhiteBeet SLAC module initialized (device: {self.device}, mac: {self.whitebeet_mac})")
    
    def ready(self):
        """Called when module is ready to start."""
        log.info("WhiteBeet SLAC module ready")
        
        # Start SLAC worker thread
        self.slac_thread = Thread(target=self._slac_worker, daemon=True)
        self.slac_thread.start()
    
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
            self.publish.state("UNMATCHED")
            
            # Main SLAC loop
            while not self.terminate.is_set():
                if not self.slac_enabled or not self.in_bcd_state:
                    # Not enabled or not in charging state - wait
                    time.sleep(0.1)
                    continue
                
                # Vehicle connected and SLAC enabled - start matching
                log.info("Entering BCD state - starting SLAC matching")
                self.publish.state("MATCHING")
                
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
                        self.publish.state("MATCHED")
                        self.publish.dlink_ready(True)
                        
                        # TODO: Extract and publish EV MAC if configured
                        # if self.publish_mac:
                        #     ev_mac = self._get_ev_mac()
                        #     self.publish.ev_mac_address(ev_mac)
                        
                        # Stay matched until we leave BCD state
                        while self.in_bcd_state and not self.terminate.is_set():
                            time.sleep(0.1)
                        
                        # Left BCD state - terminate link
                        log.info("Left BCD state - terminating SLAC link")
                        self.publish.state("UNMATCHED")
                        self.publish.dlink_ready(False)
                        
                        # Reset duty cycle to 100%
                        self.whitebeet.controlPilotSetDutyCycle(100)
                    else:
                        log.warning("✗ SLAC matching failed or timed out")
                        self.publish.state("UNMATCHED")
                        self.publish.request_error_routine()
                        
                        # Wait before retry
                        time.sleep(2)
                        
                except TimeoutError as e:
                    log.error(f"SLAC matching timeout: {e}")
                    self.publish.state("UNMATCHED")
                    self.publish.request_error_routine()
                    time.sleep(2)
                except Exception as e:
                    log.error(f"SLAC matching error: {e}")
                    self.publish.state("UNMATCHED")
                    self.publish.request_error_routine()
                    time.sleep(2)
            
        except Exception as e:
            log.error(f"SLAC worker thread error: {e}", exc_info=True)
        finally:
            # Cleanup
            if self.whitebeet:
                try:
                    log.info("Stopping SLAC module...")
                    self.whitebeet.slacStop()
                    self.whitebeet.controlPilotStop()
                    log.info("SLAC module stopped")
                except Exception as e:
                    log.error(f"Error during cleanup: {e}")
    
    # Command handlers (called by EVerest framework)
    
    def handle_reset(self, enable):
        """Reset SLAC module."""
        log.info(f"SLAC reset requested (enable: {enable})")
        self.slac_enabled = enable
        
        if enable:
            self.publish.state("MATCHING")
        else:
            self.publish.state("UNMATCHED")
            self.publish.dlink_ready(False)
    
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
        self.publish.state("UNMATCHED")
        self.publish.dlink_ready(False)
    
    def handle_dlink_error(self):
        """Handle data link error."""
        log.info("Data link error - restarting matching process")
        self.publish.state("UNMATCHED")
        self.publish.dlink_ready(False)
        # Worker thread will restart matching if still in BCD state
    
    def handle_dlink_pause(self):
        """Request power saving mode while staying matched."""
        log.info("Data link pause requested (power saving mode)")
        # WhiteBeet doesn't have a specific pause mode
        # Just log it for now


# Module entry point
def main():
    module = WhiteBeetSlacModule()
    module.run()


if __name__ == "__main__":
    main()
