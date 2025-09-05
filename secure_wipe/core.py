#!/usr/bin/env python3
"""
Secure Wipe Core - Business Logic

This module contains the core device classification logic.
It's UI-agnostic and can be used by GUI, CLI, or any other interface.
"""

import subprocess
import json
import os
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class DeviceType(Enum):
    """Storage device types we can classify."""
    HDD = "HDD"
    SATA_SSD = "SATA SSD" 
    NVME = "NVME"
    USB = "USB"
    UNKNOWN = "UNKNOWN"


@dataclass
class Device:
    """Represents a storage device with all its properties."""
    name: str
    path: str
    model: str
    size: str
    transport: str
    is_rotational: bool
    classification: DeviceType
    evidence: List[str]
    wipe_commands: List[str]


class SecureWipeCore:
    """
    Core business logic for device classification and wipe command generation.
    This class contains no UI code - it's pure logic.
    """

    def __init__(self):
        self.ignore_prefixes = ("loop", "zram", "dm-")
        self._devices_cache: List[Device] = []

    def scan_devices(self) -> Tuple[bool, str, List[Device]]:
        """
        Scan system for storage devices and classify them.
        
        Returns:
            (success, message, devices_list)
        """
        # Get device list from lsblk
        command = ["lsblk", "-d", "-o", "NAME,ROTA,TYPE,MODEL,TRAN,SIZE", "--json"]
        output = self._run_command(command)

        if output.startswith("Error"):
            return False, f"Failed to get device list: {output}", []

        try:
            data = json.loads(output)
            raw_devices = data["blockdevices"]
            
            # Filter out virtual devices
            physical_devices = [
                dev for dev in raw_devices 
                if not dev.get("name", "").startswith(self.ignore_prefixes)
            ]

            # Classify each device
            classified_devices = []
            for raw_dev in physical_devices:
                device = self._classify_device(raw_dev)
                classified_devices.append(device)

            self._devices_cache = classified_devices
            return True, f"Found {len(classified_devices)} devices", classified_devices

        except (json.JSONDecodeError, KeyError) as e:
            return False, f"Failed to parse device data: {e}", []

    def _classify_device(self, raw_device: Dict) -> Device:
        """Classify a single device and return Device object."""
        name = raw_device.get("name", "")
        transport = raw_device.get("tran", "").lower()
        is_rotational = raw_device.get("rota", False)
        device_path = f"/dev/{name}"

        # Build evidence trail
        evidence = [
            f"Transport: {transport or 'N/A'}",
            f"Rotational: {'Yes' if is_rotational else 'No'}",
            f"Type: {raw_device.get('type', 'N/A')}"
        ]

        # Classify the device
        classification = self._determine_type(raw_device, evidence, device_path)
        
        # Get appropriate wipe commands
        wipe_commands = self._get_wipe_commands(classification, device_path)

        return Device(
            name=name,
            path=device_path,
            model=raw_device.get("model", "Unknown"),
            size=raw_device.get("size", "Unknown"),
            transport=transport or "Unknown",
            is_rotational=is_rotational,
            classification=classification,
            evidence=evidence,
            wipe_commands=wipe_commands
        )

    def _determine_type(self, device: Dict, evidence: List[str], device_path: str) -> DeviceType:
        """Determine device type using multiple detection methods."""
        name = device.get("name", "")
        transport = device.get("tran", "").lower()
        is_rotational = device.get("rota", False)

        # 1. USB devices (highest priority)
        if transport == "usb":
            evidence.append("Detected: USB transport")
            return DeviceType.USB

        # 2. NVMe devices  
        if name.startswith("nvme"):
            evidence.append("Detected: NVMe device name")
            return DeviceType.NVME

        # 3. SATA/IDE disks - need SMART data
        if device.get("type") == "disk":
            smartctl_output = self._run_command(["smartctl", "-i", device_path])
            
            if smartctl_output.startswith("Error"):
                evidence.append("SMART: Data unavailable")
                return DeviceType.UNKNOWN

            if "Solid State Device" in smartctl_output:
                evidence.append("SMART: Confirmed SSD")
                return DeviceType.SATA_SSD
            
            if is_rotational:
                evidence.append("SMART: Confirmed rotational disk")
                return DeviceType.HDD
            else:
                evidence.append("SMART: Non-rotational but not confirmed SSD")
                return DeviceType.UNKNOWN

        evidence.append("Classification: Unable to determine type")
        return DeviceType.UNKNOWN

    def _get_wipe_commands(self, device_type: DeviceType, device_path: str) -> List[str]:
        """Get appropriate secure wipe commands for device type."""
        commands = {
            DeviceType.HDD: [
                f"sudo nwipe --method dodshort {device_path}"
            ],
            DeviceType.SATA_SSD: [
                f"sudo hdparm --user-master u --security-set-pass p {device_path}",
                f"sudo hdparm --user-master u --security-erase p {device_path}"
            ],
            DeviceType.NVME: [
                f"sudo nvme format {device_path} --ses=1"
            ],
            DeviceType.USB: [
                f"sudo dd if=/dev/zero of={device_path} bs=1M status=progress",
                f"# Alternative: sudo shred -vfz -n 1 {device_path}"
            ],
            DeviceType.UNKNOWN: [
                "# STOP: Cannot recommend commands for unknown device type",
                "# Manual verification required before any wipe operation"
            ]
        }
        return commands.get(device_type, commands[DeviceType.UNKNOWN])

    def _run_command(self, command: List[str]) -> str:
        """Execute system command and return output."""
        try:
            result = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                check=False
            )
            if result.returncode != 0:
                return f"Error: {result.stderr.strip()}"
            return result.stdout
        except FileNotFoundError:
            return f"Error: Command '{command[0]}' not found"

    def get_system_status(self) -> Dict:
        """Get system status and tool availability."""
        required_tools = ["lsblk", "smartctl", "hdparm", "nvme", "nwipe", "dd", "shred"]
        tool_status = {}
        
        for tool in required_tools:
            result = self._run_command(["which", tool])
            tool_status[tool] = not result.startswith("Error")

        return {
            "is_root": os.geteuid() == 0,
            "cached_devices": len(self._devices_cache),
            "tools": tool_status
        }

    def get_device_by_path(self, device_path: str) -> Optional[Device]:
        """Get specific device from cache by path."""
        for device in self._devices_cache:
            if device.path == device_path:
                return device
        return None


# Simple API wrapper for easy usage
class SecureWipeAPI:
    """High-level API for different interfaces to use."""
    
    def __init__(self):
        self.core = SecureWipeCore()
    
    def scan(self) -> Dict:
        """Scan devices and return standardized result."""
        success, message, devices = self.core.scan_devices()
        
        return {
            "success": success,
            "message": message,
            "count": len(devices),
            "devices": [self._device_to_dict(dev) for dev in devices]
        }
    
    def status(self) -> Dict:
        """Get system status."""
        return self.core.get_system_status()
    
    def get_device(self, device_path: str) -> Optional[Dict]:
        """Get specific device info."""
        device = self.core.get_device_by_path(device_path)
        return self._device_to_dict(device) if device else None
    
    def _device_to_dict(self, device: Device) -> Dict:
        """Convert Device object to dictionary."""
        return {
            "name": device.name,
            "path": device.path,
            "model": device.model,
            "size": device.size,
            "transport": device.transport,
            "is_rotational": device.is_rotational,
            "classification": device.classification.value,
            "evidence": device.evidence,
            "wipe_commands": device.wipe_commands
        }


if __name__ == "__main__":
    # Quick test when run directly
    api = SecureWipeAPI()
    print("🔍 Quick device scan:")
    result = api.scan()
    
    if result["success"]:
        print(f"✅ Found {result['count']} devices")
        for device in result["devices"]:
            print(f"  📀 {device['path']} - {device['classification']}")
    else:
        print(f"❌ Error: {result['message']}")
