#!/usr/bin/env python3
"""
Secure Wipe GUI - Desktop Interface

Provides a user-friendly graphical interface for the secure wipe tool.
Uses the core module for all business logic.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import sys
import os
from datetime import datetime

from core import SecureWipeAPI


class SecureWipeGUI:
    """Main GUI application class."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Secure Wipe Tool v2.0")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # Initialize API
        self.api = SecureWipeAPI()
        
        # Setup UI
        self._setup_styles()
        self._create_widgets()
        self._check_system_status()

    def _setup_styles(self):
        """Configure UI styles."""
        style = ttk.Style()
        style.configure('Title.TLabel', font=('Arial', 18, 'bold'))
        style.configure('Header.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Success.TLabel', foreground='#2e7d3a')
        style.configure('Warning.TLabel', foreground='#f57c00')
        style.configure('Error.TLabel', foreground='#d32f2f')

    def _create_widgets(self):
        """Create and layout all UI widgets."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="🔒 Secure Wipe Tool", style='Title.TLabel')
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Status section
        self._create_status_section(main_frame, row=1)
        
        # Control buttons
        self._create_controls_section(main_frame, row=2)
        
        # Results area
        self._create_results_section(main_frame, row=3)
        
        # Progress bar (initially hidden)
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate', length=400)
        self.progress.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        self.progress.grid_remove()  # Hide initially
        
        # Progress label (initially hidden)
        self.progress_label = ttk.Label(main_frame, text="", font=('Arial', 9))
        self.progress_label.grid(row=4, column=0, columnspan=3, pady=(35, 0))
        self.progress_label.grid_remove()  # Hide initially
        
        # Warning message
        self._create_warning_section(main_frame, row=6)
        
        # Configure grid weights for responsive layout
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)

    def _create_status_section(self, parent, row):
        """Create system status display section."""
        status_frame = ttk.LabelFrame(parent, text="System Status", padding="10")
        status_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        
        self.status_label = ttk.Label(status_frame, text="Checking system...")
        self.status_label.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.tools_label = ttk.Label(status_frame, text="Checking tools...")
        self.tools_label.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        status_frame.columnconfigure(0, weight=1)

    def _create_controls_section(self, parent, row):
        """Create control buttons section."""
        controls_frame = ttk.Frame(parent)
        controls_frame.grid(row=row, column=0, columnspan=3, pady=(0, 15))
        
        self.scan_btn = ttk.Button(controls_frame, text="🔍 Scan Devices", command=self._scan_devices)
        self.scan_btn.grid(row=0, column=0, padx=(0, 10))
        
        self.refresh_btn = ttk.Button(controls_frame, text="🔄 Refresh", command=self._refresh_scan)
        self.refresh_btn.grid(row=0, column=1, padx=(0, 10))
        
        self.clear_btn = ttk.Button(controls_frame, text="🗑️ Clear", command=self._clear_results)
        self.clear_btn.grid(row=0, column=2, padx=(0, 10))
        
        self.export_btn = ttk.Button(controls_frame, text="💾 Export", command=self._export_results)
        self.export_btn.grid(row=0, column=3)

    def _create_results_section(self, parent, row):
        """Create results display section."""
        results_frame = ttk.LabelFrame(parent, text="Device Analysis Results", padding="10")
        results_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15))
        
        self.results_text = scrolledtext.ScrolledText(
            results_frame, 
            width=100, 
            height=25, 
            wrap=tk.WORD,
            font=('Consolas', 10)
        )
        self.results_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

    def _create_warning_section(self, parent, row):
        """Create warning message section."""
        warning_frame = ttk.Frame(parent)
        warning_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        warning_text = ("⚠️  DANGER: These commands will PERMANENTLY DESTROY ALL DATA! "
                       "Always verify device paths before execution. No recovery possible!")
        
        warning_label = ttk.Label(
            warning_frame, 
            text=warning_text, 
            style='Error.TLabel',
            wraplength=950
        )
        warning_label.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        warning_frame.columnconfigure(0, weight=1)

    def _check_system_status(self):
        """Check and display system status."""
        status = self.api.status()
        
        # Root privilege status
        if status["is_root"]:
            self.status_label.config(text="✅ Running with root privileges", style='Success.TLabel')
        else:
            self.status_label.config(text="⚠️  Limited functionality - not running as root", style='Warning.TLabel')
        
        # Tool availability
        tools = status["tools"]
        available = sum(tools.values())
        total = len(tools)
        
        if available == total:
            self.tools_label.config(text=f"✅ All required tools available ({available}/{total})", style='Success.TLabel')
        else:
            missing = [tool for tool, avail in tools.items() if not avail]
            self.tools_label.config(text=f"⚠️  Some tools missing: {', '.join(missing)}", style='Warning.TLabel')

    def _scan_devices(self):
        """Start device scanning in background thread."""
        self.scan_btn.config(state='disabled')
        self.refresh_btn.config(state='disabled')
        
        # Show and start progress bar
        self.progress.grid()  # Make progress bar visible
        self.progress_label.grid()  # Make progress label visible
        
        self.progress.config(mode='indeterminate')
        self.progress.start(10)  # Update every 10ms for smoother animation
        self.progress_label.config(text="Scanning storage devices...")
        
        self.status_label.config(text="🔍 Scanning storage devices...", style='')
        
        thread = threading.Thread(target=self._scan_thread)
        thread.daemon = True
        thread.start()

    def _scan_thread(self):
        """Background thread for device scanning."""
        try:
            # Update progress message during scan
            self.root.after(0, lambda: self.progress_label.config(text="Discovering storage devices..."))
            
            result = self.api.scan()
            
            # Update progress message for classification phase
            if result["success"] and result["devices"]:
                self.root.after(0, lambda: self.progress_label.config(text="Classifying devices..."))
                # Small delay to show the classification phase
                import time
                time.sleep(0.5)
            
            self.root.after(0, lambda: self._display_results(result))
        except Exception as e:
            self.root.after(0, lambda: self._show_error(f"Scan failed: {str(e)}"))

    def _display_results(self, result):
        """Display scan results in the text area."""
        self.results_text.delete(1.0, tk.END)
        
        # Stop and hide progress bar
        self.progress.stop()
        self.progress.config(value=0)
        self.progress.grid_remove()  # Hide progress bar
        self.progress_label.grid_remove()  # Hide progress label
        
        # Re-enable buttons
        self.scan_btn.config(state='normal')
        self.refresh_btn.config(state='normal')
        
        if not result["success"]:
            self._show_error(result["message"])
            return
        
        devices = result["devices"]
        if not devices:
            self.results_text.insert(tk.END, "No storage devices found.\n")
            self.status_label.config(text="✅ Scan complete - No devices", style='Warning.TLabel')
        else:
            self._format_device_results(devices)
            self.status_label.config(text=f"✅ Scan complete - {len(devices)} devices found", style='Success.TLabel')

    def _format_device_results(self, devices):
        """Format and display device information."""
        # Header
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.results_text.insert(tk.END, f"SECURE WIPE ANALYSIS REPORT\n")
        self.results_text.insert(tk.END, f"Generated: {timestamp}\n")
        self.results_text.insert(tk.END, f"Devices Found: {len(devices)}\n")
        self.results_text.insert(tk.END, "=" * 100 + "\n\n")
        
        # Device details
        for i, device in enumerate(devices, 1):
            self._format_single_device(i, device)
        
        # Summary
        self._format_summary(devices)

    def _format_single_device(self, index, device):
        """Format information for a single device."""
        classification = device["classification"]
        
        # Device header with emoji
        emoji_map = {"HDD": "💾", "SATA SSD": "💿", "NVME": "⚡", "USB": "🔌", "UNKNOWN": "❓"}
        emoji = emoji_map.get(classification, "❓")
        
        self.results_text.insert(tk.END, f"{emoji} DEVICE {index}: {device['path']}\n")
        self.results_text.insert(tk.END, f"    Model: {device['model']}\n")
        self.results_text.insert(tk.END, f"    Size: {device['size']}\n")
        self.results_text.insert(tk.END, f"    Transport: {device['transport']}\n")
        self.results_text.insert(tk.END, f"    Classification: {classification}\n\n")
        
        # Evidence
        self.results_text.insert(tk.END, "    Evidence Trail:\n")
        for evidence in device["evidence"]:
            self.results_text.insert(tk.END, f"      • {evidence}\n")
        
        # Commands
        self.results_text.insert(tk.END, f"\n    Recommended Secure Wipe Commands:\n")
        for cmd in device["wipe_commands"]:
            if cmd.startswith("#"):
                self.results_text.insert(tk.END, f"      💬 {cmd}\n")
            else:
                self.results_text.insert(tk.END, f"      ⚡ {cmd}\n")
        
        self.results_text.insert(tk.END, "\n" + "-" * 100 + "\n\n")

    def _format_summary(self, devices):
        """Format summary statistics."""
        self.results_text.insert(tk.END, "SUMMARY STATISTICS\n")
        self.results_text.insert(tk.END, "=" * 50 + "\n")
        
        # Count by type
        type_counts = {}
        for device in devices:
            device_type = device["classification"]
            type_counts[device_type] = type_counts.get(device_type, 0) + 1
        
        for device_type, count in sorted(type_counts.items()):
            emoji_map = {"HDD": "💾", "SATA SSD": "💿", "NVME": "⚡", "USB": "🔌", "UNKNOWN": "❓"}
            emoji = emoji_map.get(device_type, "❓")
            self.results_text.insert(tk.END, f"{emoji} {device_type}: {count} device(s)\n")
        
        self.results_text.insert(tk.END, f"\n📊 Total Devices Analyzed: {len(devices)}\n")

    def _show_error(self, error_msg):
        """Display error message."""
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, f"❌ ERROR: {error_msg}\n")
        
        # Stop and hide progress bar
        self.progress.stop()
        self.progress.config(value=0)
        self.progress.grid_remove()  # Hide progress bar
        self.progress_label.grid_remove()  # Hide progress label
        
        # Re-enable buttons
        self.scan_btn.config(state='normal')
        self.refresh_btn.config(state='normal')
        
        self.status_label.config(text="❌ Scan failed", style='Error.TLabel')
        messagebox.showerror("Error", error_msg)

    def _refresh_scan(self):
        """Refresh scan by clearing and rescanning."""
        self._clear_results()
        self._scan_devices()

    def _clear_results(self):
        """Clear results display."""
        self.results_text.delete(1.0, tk.END)
        
        # Hide progress bar completely
        self.progress.stop()
        self.progress.config(value=0)
        self.progress.grid_remove()  # Hide progress bar
        self.progress_label.grid_remove()  # Hide progress label
        
        # Re-enable buttons
        self.scan_btn.config(state='normal')
        self.refresh_btn.config(state='normal')
        
        self.status_label.config(text="Ready to scan devices", style='')

    def _export_results(self):
        """Export results to text file."""
        content = self.results_text.get(1.0, tk.END).strip()
        if not content:
            messagebox.showwarning("Export", "No results to export. Please run a scan first.")
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"secure_wipe_report_{timestamp}.txt"
            
            with open(filename, 'w') as f:
                f.write(content)
            
            messagebox.showinfo("Export Complete", f"Results exported to:\n{filename}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Could not save file:\n{str(e)}")


def main():
    """Main entry point with proper error handling."""
    # Handle X11 display issues with sudo
    if os.geteuid() == 0:
        if 'DISPLAY' not in os.environ:
            print("❌ No DISPLAY environment variable found.")
            print("When running with sudo, X11 display access is required.")
            print("\n🔧 Solutions:")
            print("1. Use: ./run_gui.sh")
            print("2. Use: sudo -E python3 gui.py") 
            print("3. Use: xhost +local:root && sudo python3 gui.py")
            sys.exit(1)
        
        # Try to preserve X11 authentication
        try:
            original_user = os.environ.get('SUDO_USER')
            if original_user and 'XAUTHORITY' not in os.environ:
                xauth_path = f"/home/{original_user}/.Xauthority"
                if os.path.exists(xauth_path):
                    os.environ['XAUTHORITY'] = xauth_path
        except Exception:
            pass
    
    try:
        root = tk.Tk()
        app = SecureWipeGUI(root)
        root.mainloop()
    except tk.TclError as e:
        if "couldn't connect to display" in str(e):
            print("❌ Cannot connect to X11 display.")
            print("This usually happens when running GUI apps with sudo.")
            print("\n🔧 Try:")
            print("1. ./run_gui.sh")
            print("2. xhost +local:root")
            print("3. Run without sudo (limited functionality)")
            sys.exit(1)
        else:
            raise


if __name__ == "__main__":
    main()
