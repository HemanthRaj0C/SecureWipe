#!/usr/bin/env python3
#
# Secure Wipe Identifier (v5 - Evidentiary Output)
#
# This version explicitly shows the evidence from multiple commands (lsblk, smartctl)
# used to classify each storage device.
#
# Run with 'sudo': sudo python3 secure_wipe_identifier.py
#

import subprocess
import json
import sys
import os

class DeviceClassifier:
    """A class to handle device identification and classification."""

    def __init__(self):
        self.ignore_prefixes = ("loop", "zram", "dm-")
        self.devices = self._discover_devices()

    def _run_command(self, command):
        """A helper function to run a shell command."""
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                return f"Error: {result.stderr.strip()}"
            return result.stdout
        except FileNotFoundError:
            return f"Error: Command '{command[0]}' not found."

    def _discover_devices(self):
        """Gets all physical storage devices using a single lsblk call."""
        command = ["lsblk", "-d", "-o", "NAME,ROTA,TYPE,MODEL,TRAN", "--json"]
        lsblk_output = self._run_command(command)

        if "Error" in lsblk_output:
            print(f"Critical Error: Could not get device list from lsblk. {lsblk_output}")
            return []

        try:
            all_devices = json.loads(lsblk_output)["blockdevices"]
            return [dev for dev in all_devices if not dev.get("name", "").startswith(self.ignore_prefixes)]
        except (json.JSONDecodeError, KeyError):
            print("Critical Error: Could not parse lsblk output.")
            return []

    def classify(self, device):
        """
        Classifies a single device and returns the classification and an evidence log.
        """
        name = device.get("name")
        transport = device.get("tran", "").lower()
        is_rotational = device.get("rota", False)
        device_path = f"/dev/{name}"
        evidence = [
            f"[lsblk] Transport Type: '{transport or 'N/A'}'",
            f"[lsblk] Is Rotational: {is_rotational}"
        ]
        
        # 1. Highest priority: Check transport type for USB
        if transport == "usb":
            return "USB", evidence

        # 2. Check name for NVMe (most reliable check)
        if name.startswith("nvme"):
            return "NVME", evidence

        # 3. Handle standard block devices (disks) by cross-checking with smartctl
        if device.get("type") == "disk":
            smartctl_output = self._run_command(["smartctl", "-i", device_path])
            
            if "Error" in smartctl_output or "Unavailable" in smartctl_output:
                evidence.append("[smartctl] Result: Could not get reliable SMART data.")
                return "UNKNOWN", evidence

            if "Solid State Device" in smartctl_output:
                evidence.append("[smartctl] Result: Confirmed as Solid State Device.")
                return "SATA SSD", evidence
            
            if is_rotational:
                evidence.append("[smartctl] Result: Confirmed as a Rotational Device.")
                return "HDD", evidence
            else:
                evidence.append("[smartctl] Result: CONFLICT! Non-rotational but not confirmed as SSD.")
                return "UNKNOWN", evidence

        return "UNKNOWN", evidence

    @staticmethod
    def get_wipe_command(classification, device_path):
        """Returns the recommended wipe command(s) for a given classification."""
        commands = {
            "HDD": [f"sudo nwipe --method dodshort {device_path}"],
            "SATA SSD": [
                f"sudo hdparm --user-master u --security-set-pass p {device_path}",
                f"sudo hdparm --user-master u --security-erase p {device_path}"
            ],
            "NVME": [f"sudo nvme format {device_path} --ses=1"],
            "USB": [
                f"sudo dd if=/dev/zero of={device_path} bs=1M status=progress",
                f"(Alternative: sudo shred -vfz -n 1 {device_path})"
            ],
            "UNKNOWN": ["HALT: Cannot recommend a safe command for an unknown device."]
        }
        return commands.get(classification, commands["UNKNOWN"])

def main():
    """Main function to discover, classify, and report on storage devices."""
    print("--- Secure Wipe Identifier ---")
    
    if os.geteuid() != 0:
        print("This script needs root privileges. Please run it using 'sudo'.")
        sys.exit(1)

    classifier = DeviceClassifier()
    if not classifier.devices:
        print("No physical storage devices found to classify.")
        return

    print("Found the following physical storage devices:\n")
    for dev in classifier.devices:
        model = dev.get("model", "N/A")
        device_path = f"/dev/{dev.get('name')}"
        
        classification, evidence = classifier.classify(dev)
        recommended_commands = classifier.get_wipe_command(classification, device_path)

        print(f"Device: {device_path} ({model})")
        print("  -> Evidence Trail:")
        for item in evidence:
            print(f"     {item}")
        print(f"  -> Final Classification: {classification}")
        for cmd in recommended_commands:
            print(f"  -> Recommended Command: {cmd}")
        print("-" * 40)

if __name__ == "__main__":
    main()