#!/usr/bin/env python3
"""
Secure Wipe CLI - Command Line Interface

Provides terminal-based access to the secure wipe tool.
Perfect for automation, scripting, and remote usage.
"""

import sys
import os
import argparse
from core import SecureWipeAPI


class SecureWipeCLI:
    """Command-line interface for the secure wipe tool."""
    
    def __init__(self):
        self.api = SecureWipeAPI()
    
    def run(self, args):
        """Main CLI dispatcher."""
        if args.command == "scan":
            self._cmd_scan(args)
        elif args.command == "status":
            self._cmd_status()
        elif args.command == "device":
            self._cmd_device(args)
    
    def _cmd_scan(self, args):
        """Handle scan command."""
        print("🔍 Scanning storage devices...")
        result = self.api.scan()
        
        if not result["success"]:
            print(f"❌ Error: {result['message']}")
            sys.exit(1)
        
        devices = result["devices"]
        if not devices:
            print("ℹ️  No storage devices found.")
            return
        
        print(f"✅ Found {len(devices)} storage device(s):")
        print()
        
        for i, device in enumerate(devices, 1):
            if args.verbose:
                self._print_device_detailed(i, device)
            else:
                self._print_device_summary(device)
        
        if not args.verbose:
            print(f"\n💡 Use --verbose for detailed information")
    
    def _cmd_status(self):
        """Handle status command."""
        status = self.api.status()
        
        print("🔧 System Status")
        print("=" * 40)
        
        # Root privileges
        if status["is_root"]:
            print("✅ Root privileges: Available")
        else:
            print("❌ Root privileges: Missing")
        
        print(f"📊 Cached devices: {status['cached_devices']}")
        
        # Tool availability
        print("\n🛠️  System Tools:")
        tools = status["tools"]
        for tool, available in tools.items():
            status_icon = "✅" if available else "❌"
            print(f"   {status_icon} {tool}")
        
        # Summary
        available_count = sum(tools.values())
        total_count = len(tools)
        print(f"\n📈 Tools available: {available_count}/{total_count}")
        
        if available_count < total_count:
            missing = [tool for tool, avail in tools.items() if not avail]
            print(f"⚠️  Missing tools: {', '.join(missing)}")
    
    def _cmd_device(self, args):
        """Handle device-specific command."""
        device = self.api.get_device(args.path)
        
        if not device:
            print(f"❌ Device {args.path} not found.")
            print("💡 Run 'scan' command first to discover devices.")
            sys.exit(1)
        
        self._print_device_detailed(1, device)
    
    def _print_device_summary(self, device):
        """Print brief device summary."""
        emoji_map = {"HDD": "💾", "SATA SSD": "💿", "NVME": "⚡", "USB": "🔌", "UNKNOWN": "❓"}
        emoji = emoji_map.get(device["classification"], "❓")
        
        print(f"{emoji} {device['path']} - {device['classification']}")
        print(f"    Model: {device['model']} | Size: {device['size']}")
    
    def _print_device_detailed(self, index, device):
        """Print detailed device information."""
        classification = device["classification"]
        emoji_map = {"HDD": "💾", "SATA SSD": "💿", "NVME": "⚡", "USB": "🔌", "UNKNOWN": "❓"}
        emoji = emoji_map.get(classification, "❓")
        
        print(f"{emoji} Device {index}: {device['path']}")
        print(f"   Model: {device['model']}")
        print(f"   Size: {device['size']}")
        print(f"   Transport: {device['transport']}")
        print(f"   Classification: {classification}")
        
        print("   Evidence:")
        for evidence in device["evidence"]:
            print(f"     • {evidence}")
        
        print("   Recommended Commands:")
        for cmd in device["wipe_commands"]:
            if cmd.startswith("#"):
                print(f"     💬 {cmd}")
            else:
                print(f"     ⚡ {cmd}")
        print()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Secure Wipe Tool - Command Line Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s scan              # Quick scan of all devices
  %(prog)s scan --verbose    # Detailed scan with full info
  %(prog)s status            # Show system status
  %(prog)s device /dev/sda   # Show specific device info

Security Warning:
  The generated commands will PERMANENTLY DESTROY ALL DATA!
  Always verify device paths before execution.
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Scan for storage devices")
    scan_parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Show detailed device information"
    )
    
    # Status command
    subparsers.add_parser("status", help="Show system status and tool availability")
    
    # Device command
    device_parser = subparsers.add_parser("device", help="Show specific device information")
    device_parser.add_argument("path", help="Device path (e.g., /dev/sda)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Root privilege check
    if os.geteuid() != 0:
        print("⚠️  Warning: Not running as root.")
        print("   Some device information may be limited.")
        print("   For full functionality: sudo python3 cli.py")
        print()
    
    try:
        cli = SecureWipeCLI()
        cli.run(args)
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
