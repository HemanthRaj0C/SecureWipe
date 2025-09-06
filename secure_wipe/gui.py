#!/usr/bin/env python3
"""
Secure Wipe GUI - Simple Interface with Wipe Buttons

Provides a user-friendly graphical interface for the secure wipe tool.
Uses the core module for all business logic.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import subprocess
import time
import sys
import os
import re
import signal
import collections
from datetime import datetime

from core import SecureWipeAPI


class SecureWipeGUI:
    """Main GUI application class."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Secure Wipe Tool v2.0")
        self.root.geometry("900x600")
        self.root.minsize(800, 500)
        
        # Initialize API
        self.api = SecureWipeAPI()
        
        # Wipe process tracking
        self.wipe_process = None
        self.wipe_thread = None
        self.monitor_thread = None
        self.is_wiping = False
        self.current_device = None
        self.last_dd_speed = 0
        
        # Utilization history for sparkline (last 60 samples ~ 1 min)
        self.util_history = collections.deque(maxlen=60)
        
        # Setup UI
        self._setup_styles()
        self._create_widgets()
        self._check_system_status()

    def _setup_styles(self):
        """Configure UI styles."""
        style = ttk.Style()
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'))
        style.configure('Header.TLabel', font=('Arial', 11, 'bold'))
        style.configure('Success.TLabel', foreground='#2e7d3a')
        style.configure('Warning.TLabel', foreground='#f57c00')
        style.configure('Error.TLabel', foreground='#d32f2f')
        style.configure('USB.TLabel', foreground='#1976d2', font=('Arial', 10, 'bold'))
        style.configure('Danger.TButton', foreground='#ffffff', background='#d32f2f')

    def _create_widgets(self):
        """Create and layout all UI widgets."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="🔒 Secure Wipe Tool", style='Title.TLabel')
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Status section
        self._create_status_section(main_frame, row=1)
        
        # Control buttons
        self._create_controls_section(main_frame, row=2)
        
        # Devices section
        self._create_devices_section(main_frame, row=3)
        
        # Progress section
        self._create_progress_section(main_frame, row=4)
        
        # Warning message
        self._create_warning_section(main_frame, row=5)
        
        # Configure grid weights for responsive layout
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)

    def _create_status_section(self, parent, row):
        """Create system status display section."""
        status_frame = ttk.LabelFrame(parent, text="System Status", padding="10")
        status_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        self.status_label = ttk.Label(status_frame, text="Checking system...")
        self.status_label.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        status_frame.columnconfigure(0, weight=1)

    def _create_controls_section(self, parent, row):
        """Create control buttons section."""
        controls_frame = ttk.Frame(parent)
        controls_frame.grid(row=row, column=0, columnspan=2, pady=(0, 15))
        
        self.scan_btn = ttk.Button(controls_frame, text="🔍 Scan Devices", command=self._scan_devices)
        self.scan_btn.grid(row=0, column=0, padx=(0, 10))
        
        self.refresh_btn = ttk.Button(controls_frame, text="🔄 Refresh", command=self._refresh_scan)
        self.refresh_btn.grid(row=0, column=1, padx=(0, 10))

    def _create_devices_section(self, parent, row):
        """Create devices display section."""
        devices_frame = ttk.LabelFrame(parent, text="Storage Devices", padding="10")
        devices_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15))
        
        # Create canvas and scrollbar for scrollable device list
        canvas = tk.Canvas(devices_frame, height=200)
        scrollbar = ttk.Scrollbar(devices_frame, orient="vertical", command=canvas.yview)
        self.devices_inner_frame = ttk.Frame(canvas)
        
        # Configure scrolling
        self.devices_inner_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.devices_inner_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Grid the canvas and scrollbar
        canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        devices_frame.columnconfigure(0, weight=1)
        devices_frame.rowconfigure(0, weight=1)
        
        # Initially show placeholder
        self.no_devices_label = ttk.Label(self.devices_inner_frame, text="Click 'Scan Devices' to start")
        self.no_devices_label.grid(row=0, column=0, pady=20)

    def _create_progress_section(self, parent, row):
        """Create progress monitoring section."""
        self.progress_frame = ttk.LabelFrame(parent, text="Wipe Progress & Disk Monitor", padding="10")
        self.progress_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        self.progress_frame.grid_remove()  # Hide initially
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='determinate', length=400)
        self.progress_bar.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Status labels
        self.progress_status = ttk.Label(self.progress_frame, text="")
        self.progress_status.grid(row=1, column=0, columnspan=2, sticky=tk.W)
        
        self.progress_details = ttk.Label(self.progress_frame, text="")
        self.progress_details.grid(row=2, column=0, columnspan=2, sticky=tk.W)
        
        # Disk Activity Monitor Section
        monitor_frame = ttk.LabelFrame(self.progress_frame, text="Disk Activity Monitor", padding="5")
        monitor_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # Disk usage percentage bar
        ttk.Label(monitor_frame, text="Disk Usage:").grid(row=0, column=0, sticky=tk.W)
        self.disk_usage_bar = ttk.Progressbar(monitor_frame, mode='determinate', length=200)
        self.disk_usage_bar.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
        self.disk_usage_label = ttk.Label(monitor_frame, text="0%")
        self.disk_usage_label.grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
        
        # Disk utilization sparkline (full width)
        ttk.Label(monitor_frame, text="Disk Utilization:").grid(row=1, column=0, sticky=tk.W)
        # Theme-aware background color
        theme_bg = self._get_theme_bg()
        self.util_history_canvas = tk.Canvas(
            monitor_frame,
            width=400,
            height=80,
            bg=theme_bg,
            highlightthickness=1,
            highlightbackground='#ddd'
        )
        self.util_history_canvas.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), padx=(10, 0), pady=(5, 0))
        # Redraw on resize so it consistently fills available width
        self.util_history_canvas.bind('<Configure>', lambda e: self._draw_util_history())
        # Initial draw after widget is realized
        self.root.after(50, self._draw_util_history)
            
        self.util_percentage_label = ttk.Label(monitor_frame, text="0%", font=('Arial', 12, 'bold'))
        self.util_percentage_label.grid(row=1, column=3, sticky=tk.W, padx=(10, 0), pady=(5, 0))
        
        # I/O Stats
        ttk.Label(monitor_frame, text="Total Written:").grid(row=2, column=0, sticky=tk.W)
        self.total_written_label = ttk.Label(monitor_frame, text="0 GB")
        self.total_written_label.grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=(5, 0))
        
        ttk.Label(monitor_frame, text="Estimated Time:").grid(row=2, column=2, sticky=tk.W, padx=(20, 0))
        self.eta_label = ttk.Label(monitor_frame, text="Calculating...")
        self.eta_label.grid(row=2, column=3, sticky=tk.W, padx=(10, 0), pady=(5, 0))
        
        # Cancel button
        self.cancel_btn = ttk.Button(self.progress_frame, text="❌ Cancel Wipe", command=self._cancel_wipe)
        self.cancel_btn.grid(row=4, column=0, columnspan=2, pady=(10, 0))

        self.progress_frame.columnconfigure(0, weight=1)
        # Let the canvas stretch to take full width between labels
        monitor_frame.columnconfigure(1, weight=1)
        monitor_frame.columnconfigure(2, weight=1)
        monitor_frame.columnconfigure(3, weight=0)

    def _get_theme_bg(self):
        """Return a background color that matches the current ttk theme."""
        try:
            style = ttk.Style()
            bg = style.lookup('TFrame', 'background')
            if not bg:
                bg = self.root.cget('bg')
            # Fallback default
            return bg or '#f0f0f0'
        except Exception:
            return '#f0f0f0'

    def _create_warning_section(self, parent, row):
        """Create warning message section."""
        warning_frame = ttk.Frame(parent)
        warning_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        warning_text = ("⚠️  DANGER: Wiping will PERMANENTLY DESTROY ALL DATA! Always verify the correct device!")
        
        warning_label = ttk.Label(
            warning_frame, 
            text=warning_text, 
            style='Error.TLabel',
            wraplength=800
        )
        warning_label.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        warning_frame.columnconfigure(0, weight=1)

    def _check_system_status(self):
        """Check and display system status."""
        status = self.api.status()
        
        # Root privilege status
        if status["is_root"]:
            self.status_label.config(text="✅ Running with root privileges - Ready for secure wipe", style='Success.TLabel')
        else:
            self.status_label.config(text="⚠️  Limited functionality - not running as root", style='Warning.TLabel')

    def _draw_donut_chart(self, percentage):
        """Draw an enhanced donut chart showing disk utilization percentage."""
        self.util_canvas.delete("all")
        
        # Canvas dimensions (updated for larger size)
        width = 120
        height = 120
        center_x = width // 2
        center_y = height // 2
        outer_radius = 50
        inner_radius = 32
        
        # Background ring with gradient effect
        self.util_canvas.create_oval(
            center_x - outer_radius, center_y - outer_radius,
            center_x + outer_radius, center_y + outer_radius,
            fill='#f8f9fa', outline='#e9ecef', width=3
        )
        
        # Inner circle with subtle shadow
        self.util_canvas.create_oval(
            center_x - inner_radius, center_y - inner_radius,
            center_x + inner_radius, center_y + inner_radius,
            fill='white', outline='#dee2e6', width=2
        )
        
        # Utilization arc with enhanced colors
        if percentage > 0:
            # Enhanced color scheme
            if percentage < 30:
                color = '#28a745'  # Success green
                shadow_color = '#20c997'
            elif percentage < 60:
                color = '#ffc107'  # Warning yellow
                shadow_color = '#ffca2c'
            elif percentage < 85:
                color = '#fd7e14'  # Orange
                shadow_color = '#ff851b'
            else:
                color = '#dc3545'  # Danger red
                shadow_color = '#e74c3c'
            
            # Calculate arc extent (360 degrees = 100%)
            extent = (percentage / 100) * 360
            
            # Draw shadow arc (slightly offset)
            self.util_canvas.create_arc(
                center_x - outer_radius + 2, center_y - outer_radius + 2,
                center_x + outer_radius + 2, center_y + outer_radius + 2,
                start=90, extent=-extent,
                fill='#00000015', outline='#00000015', width=0,
                style='pieslice'
            )
            
            # Draw main utilization arc
            self.util_canvas.create_arc(
                center_x - outer_radius, center_y - outer_radius,
                center_x + outer_radius, center_y + outer_radius,
                start=90, extent=-extent,
                fill=color, outline=shadow_color, width=2,
                style='pieslice'
            )
            
            # Redraw inner circle to maintain donut shape
            self.util_canvas.create_oval(
                center_x - inner_radius, center_y - inner_radius,
                center_x + inner_radius, center_y + inner_radius,
                fill='white', outline='#dee2e6', width=2
            )
        
        # Add percentage text in center with better formatting
        self.util_canvas.create_text(
            center_x, center_y - 5,
            text=f"{percentage:.0f}%",
            font=('Arial', 14, 'bold'),
            fill='#495057'
        )
        
        # Add "UTIL" label below percentage
        self.util_canvas.create_text(
            center_x, center_y + 12,
            text="UTIL",
            font=('Arial', 8),
            fill='#6c757d'
        )

    def _draw_util_history(self):
        """Draw utilization history sparkline without alpha colors."""
        c = self.util_history_canvas
        if not c:
            return
        c.delete('all')
        # Use actual rendered size for responsive drawing
        w = max(c.winfo_width(), int(c['width']))
        h = max(c.winfo_height(), int(c['height']))

        # No background - blend with existing theme
        c.delete('all')

        # Grid lines with subtle theme colors
        grid_levels = [100, 75, 50, 25, 0]
        left_margin = 36
        right_margin = 10
        top_margin = 8
        bottom_margin = 12
        for level in grid_levels:
            y = top_margin + int((100 - level) / 100.0 * (h - top_margin - bottom_margin))
            # Very subtle grid lines that blend with gray background
            color = '#d0d0d0' if level != 50 else '#c0c0c0'
            width_px = 1
            c.create_line(left_margin, y, w - right_margin, y, fill=color, width=width_px)
            # Black text to match theme
            c.create_text(left_margin - 6, y, text=f"{level}%", anchor='e', fill='#000000', font=('Arial', 8))

        if len(self.util_history) < 2:
            c.create_text(w//2, h//2, text='Waiting for utilization...', fill='#000000', font=('Arial', 10))
            return

        # Build sparkline points
        values = list(self.util_history)
        chart_w = w - left_margin - right_margin
        chart_h = h - top_margin - bottom_margin
        step = chart_w / max(1, len(values) - 1)
        points = []
        for idx, val in enumerate(values):
            x = left_margin + int(idx * step)
            y = top_margin + int((100 - val) / 100.0 * chart_h)
            points.extend([x, y])

        # Filled area under curve - subtle blue that works with gray theme
        if len(points) >= 4:
            area_points = [left_margin, top_margin + chart_h] + points + [points[-2], top_margin + chart_h]
            c.create_polygon(*area_points, fill='#a8c8ec', outline='')
            # Main line - darker blue for contrast
            c.create_line(*points, fill='#4472c4', width=2, smooth=True)

            # Current value indicator
            x_cur, y_cur = points[-2], points[-1]
            c.create_oval(x_cur-3, y_cur-3, x_cur+3, y_cur+3, fill='#4472c4', outline='white', width=1)

        # Time labels in black to match theme
        c.create_text(w - right_margin, h - 2, text='Now', anchor='se', fill='#000000', font=('Arial', 8))
        c.create_text(left_margin, h - 2, text=f"{min(60, len(values))}s ago", anchor='sw', fill='#000000', font=('Arial', 8))

    def _get_disk_usage(self, device_path):
        """Get disk usage information for a device."""
        try:
            # First get actual device size from lsblk
            result = subprocess.run(['lsblk', '-b', '-n', '-o', 'SIZE', device_path], capture_output=True, text=True)
            if result.returncode == 0:
                size_bytes = int(result.stdout.strip())
                size_gb = size_bytes / (1024**3)
                total_size = f"{size_gb:.1f}G"
            else:
                total_size = 'Unknown'
            
            # Try to get filesystem usage if mounted
            result = subprocess.run(['df', '-h', device_path], capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 4:
                        return {
                            'size': total_size,  # Use actual device size
                            'used': parts[2], 
                            'available': parts[3],
                            'use_percent': parts[4]
                        }
            
            # Device not mounted or no filesystem
            return {
                'size': total_size,
                'used': 'Not mounted',
                'available': 'Not mounted', 
                'use_percent': 'N/A'
            }
        except Exception as e:
            # Fallback to device size from the device info itself
            return {
                'size': 'Unknown',
                'used': 'Unknown',
                'available': 'Unknown',
                'use_percent': 'Unknown'
            }

    def _scan_devices(self):
        """Start device scanning in background thread."""
        if self.is_wiping:
            messagebox.showwarning("Busy", "Cannot scan while wipe operation is in progress")
            return
            
        self.scan_btn.config(state='disabled')
        self.refresh_btn.config(state='disabled')
        self.status_label.config(text="🔍 Scanning storage devices...", style='')
        
        thread = threading.Thread(target=self._scan_thread)
        thread.daemon = True
        thread.start()

    def _scan_thread(self):
        """Background thread for device scanning."""
        try:
            result = self.api.scan()
            self.root.after(0, lambda: self._display_devices(result))
        except Exception as e:
            self.root.after(0, lambda: self._show_error(f"Scan failed: {str(e)}"))

    def _display_devices(self, result):
        """Display scanned devices with wipe buttons."""
        # Clear existing device widgets
        for widget in self.devices_inner_frame.winfo_children():
            widget.destroy()
        
        # Re-enable buttons
        self.scan_btn.config(state='normal')
        self.refresh_btn.config(state='normal')
        
        if not result["success"]:
            self._show_error(result["message"])
            return
        
        devices = result["devices"]
        if not devices:
            no_devices = ttk.Label(self.devices_inner_frame, text="No storage devices found")
            no_devices.grid(row=0, column=0, pady=20)
            self.status_label.config(text="✅ Scan complete - No devices", style='Warning.TLabel')
            return
        
        # Display each device
        row = 0
        for device in devices:
            self._create_device_widget(device, row)
            row += 1
        
        self.status_label.config(text=f"✅ Scan complete - {len(devices)} devices found", style='Success.TLabel')

    def _create_device_widget(self, device, row):
        """Create widget for a single device."""
        # Device frame
        device_frame = ttk.LabelFrame(self.devices_inner_frame, padding="10")
        device_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        # Device icon and basic info
        emoji_map = {"HDD": "💾", "SATA SSD": "💿", "NVME": "⚡", "USB": "🔌", "UNKNOWN": "❓"}
        emoji = emoji_map.get(device["classification"], "❓")
        
        # Main device info
        device_info = f"{emoji} {device['path']} - {device['model']} ({device['size']})"
        device_label = ttk.Label(device_frame, text=device_info, font=('Arial', 10, 'bold'))
        device_label.grid(row=0, column=0, columnspan=3, sticky=tk.W)
        
        # Device type
        type_text = f"Type: {device['classification']} | Transport: {device['transport']}"
        type_label = ttk.Label(device_frame, text=type_text)
        type_label.grid(row=1, column=0, columnspan=3, sticky=tk.W)
        
        # Disk usage info
        usage = self._get_disk_usage(device['path'])
        usage_text = f"Size: {device['size']} | Used: {usage['used']} | Available: {usage['available']}"
        usage_label = ttk.Label(device_frame, text=usage_text)
        usage_label.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
        
        # Wipe button (only for USB devices for safety)
        if device["classification"] == "USB":
            wipe_btn = ttk.Button(
                device_frame, 
                text=f"🗑️ WIPE {device['path']}", 
                command=lambda d=device: self._confirm_wipe(d)
            )
            wipe_btn.grid(row=3, column=0, pady=(10, 0), sticky=tk.W)
            
            # Safety warning for USB
            safety_text = "⚠️ USB Drive - Safe to wipe"
            safety_label = ttk.Label(device_frame, text=safety_text, style='USB.TLabel')
            safety_label.grid(row=3, column=1, pady=(10, 0), sticky=tk.W, padx=(20, 0))
        else:
            # For non-USB devices, show why it's disabled
            disabled_text = f"⚠️ {device['classification']} - Wipe disabled for safety"
            disabled_label = ttk.Label(device_frame, text=disabled_text, style='Warning.TLabel')
            disabled_label.grid(row=3, column=0, columnspan=3, pady=(10, 0), sticky=tk.W)
        
        # Configure frame
        device_frame.columnconfigure(0, weight=1)
        self.devices_inner_frame.columnconfigure(0, weight=1)

    def _confirm_wipe(self, device):
        """Show confirmation dialog before wiping."""
        if self.is_wiping:
            messagebox.showwarning("Busy", "Another wipe operation is already in progress")
            return
        
        usage = self._get_disk_usage(device['path'])
        
        message = (
            f"⚠️ PERMANENT DATA DESTRUCTION WARNING ⚠️\n\n"
            f"Device: {device['path']}\n"
            f"Model: {device['model']}\n" 
            f"Size: {device['size']}\n"
            f"Used Space: {usage['used']}\n\n"
            f"This will PERMANENTLY ERASE ALL DATA on this device!\n"
            f"There is NO WAY to recover the data after this operation.\n\n"
            f"Are you absolutely sure you want to continue?"
        )
        
        result = messagebox.askyesno(
            "Confirm Secure Wipe",
            message,
            icon='warning'
        )
        
        if result:
            self._start_wipe(device)

    def _start_wipe(self, device):
        """Start the wipe operation."""
        self.is_wiping = True
        self.current_device = device  # Store device being wiped
        
        # Disable scan buttons
        self.scan_btn.config(state='disabled')
        self.refresh_btn.config(state='disabled')
        
        # Show progress section
        self.progress_frame.grid()
        self.progress_bar.config(value=0)
        self.progress_status.config(text=f"Starting wipe of {device['path']}...")
        self.progress_details.config(text="")
        
        # Reset monitor displays
        self.util_history.clear()  # Clear utilization history
        self.disk_usage_bar.config(value=0)
        self.disk_usage_label.config(text="0%")
        self._draw_util_history()
        self.util_percentage_label.config(text="0%")
        self.total_written_label.config(text="0 GB")
        self.eta_label.config(text="Calculating...")
        
        # Start wipe in background thread
        self.wipe_thread = threading.Thread(target=self._wipe_thread, args=(device,))
        self.wipe_thread.daemon = True
        self.wipe_thread.start()
        
        # Start disk monitoring
        self.monitor_thread = threading.Thread(target=self._monitor_disk_activity)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def _wipe_thread(self, device):
        """Background thread for wipe operation."""
        try:
            # Get device size for progress calculation
            device_size = self._get_device_size_bytes(device['path'])
            
            # Use the tested optimal command
            command = f"sudo dd if=/dev/zero of={device['path']} bs=1M status=progress"
            
            self.root.after(0, lambda: self.progress_status.config(text=f"Wiping {device['path']}..."))
            
            # Start dd process with process group for proper termination
            self.wipe_process = subprocess.Popen(
                command.split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                preexec_fn=os.setsid  # Create new process group
            )
            
            # Monitor progress
            self._monitor_wipe_progress(device_size)
            
        except Exception as e:
            self.root.after(0, lambda: self._wipe_error(f"Wipe failed: {str(e)}"))

    def _get_device_size_bytes(self, device_path):
        """Get device size in bytes."""
        try:
            result = subprocess.run(['lsblk', '-b', '-n', '-o', 'SIZE', device_path], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return int(result.stdout.strip())
        except:
            pass
        return 0

    def _monitor_disk_activity(self):
        """Monitor disk utilization using iostat -x."""
        device_name = self.current_device['path'].split('/')[-1]
        print(f"DEBUG[iostat]: monitor started for device='{device_name}'")
        
        while self.is_wiping:
            try:
                # Wait until dd process is started to avoid exiting early
                if not self.wipe_process:
                    print("DEBUG[iostat]: waiting for wipe process to start...")
                    time.sleep(0.5)
                    continue

                # Stop if process ended
                if self.wipe_process.poll() is not None:
                    print("DEBUG[iostat]: wipe process ended; stopping monitor")
                    break

                # Use iostat with -y to skip the since-boot report and -x for extended stats
                env = os.environ.copy()
                env.setdefault('LC_ALL', 'C')
                env.setdefault('LANG', 'C')
                print(f"DEBUG[iostat]: invoking iostat -xy 1 1 {device_name}")
                result = subprocess.run(
                    ['iostat', '-xy', '1', '1', device_name],
                    capture_output=True,
                    text=True,
                    timeout=6,
                    env=env,
                )

                print(f"DEBUG[iostat]: returncode={result.returncode} stdout_len={len(result.stdout) if result.stdout else 0} stderr_len={len(result.stderr) if result.stderr else 0}")
                if result.returncode == 0 and result.stdout:
                    lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
                    print(f"DEBUG[iostat]: lines_count={len(lines)} tail=\n" + "\n".join(lines[-6:]))
                    util_percent = None
                    # Parse from the bottom to get the most recent sample
                    for line in reversed(lines):
                        parts = line.split()
                        # Match exact device name in first column to avoid header/wrap lines
                        if parts and parts[0] == device_name:
                            print(f"DEBUG[iostat]: matched_line='{line}'")
                            last_token = parts[-1].replace(',', '.')  # handle locales
                            try:
                                util_percent = float(last_token)
                                print(f"DEBUG[iostat]: parsed_util={util_percent}")
                                break
                            except ValueError:
                                print(f"DEBUG[iostat]: parse_error token='{last_token}' line='{line}'")
                                continue

                    if util_percent is not None:
                        self.root.after(0, lambda u=util_percent: self._update_utilization(u))
                    else:
                        print("DEBUG[iostat]: device line not found or util not parsed; will retry")

                time.sleep(1)

            except FileNotFoundError:
                # iostat not available; stop monitoring silently
                print("DEBUG[iostat]: iostat command not found; stopping disk monitor")
                break
            except Exception:
                # On transient errors, back off briefly
                print("DEBUG[iostat]: unexpected exception; backing off 2s", file=sys.stderr)
                time.sleep(2)
    
    def _update_utilization(self, util_percent):
        """Update utilization sparkline safely."""
        try:
            print(f"DEBUG[util]: updating utilization={util_percent}")
            
            # Add to history and update sparkline
            self.util_history.append(util_percent)
            self._draw_util_history()
            
            # Update percentage label
            self.util_percentage_label.config(text=f"{util_percent:.0f}%")
        except Exception as e:
            print(f"DEBUG: Utilization update error: {e}")

    def _monitor_wipe_progress(self, total_size):
        """Monitor dd progress output."""
        start_time = time.time()
        last_bytes = 0
        
        while self.wipe_process and self.wipe_process.poll() is None:
            try:
                # Read output from dd
                output = self.wipe_process.stdout.readline()
                if output:
                    # Parse dd progress output
                    match = re.search(r'(\d+) bytes.*copied.*?(\d+\.?\d*) s.*?(\d+\.?\d*) [KMGT]?B/s', output)
                    if match:
                        bytes_copied = int(match.group(1))
                        time_elapsed = float(match.group(2))
                        speed_text = output.split()[-1]
                        
                        # Extract numeric speed for monitoring
                        try:
                            speed_match = re.search(r'(\d+\.?\d*)', speed_text)
                            if speed_match:
                                speed_value = float(speed_match.group(1))
                                if 'GB/s' in speed_text:
                                    speed_mb = speed_value * 1024
                                elif 'MB/s' in speed_text:
                                    speed_mb = speed_value
                                elif 'KB/s' in speed_text:
                                    speed_mb = speed_value / 1024
                                else:
                                    speed_mb = speed_value
                                
                                # Store for activity monitor fallback
                                self.last_dd_speed = speed_mb
                        except:
                            self.last_dd_speed = 0
                        
                        # Calculate progress percentage
                        if total_size > 0:
                            progress_percent = (bytes_copied / total_size) * 100
                            self.root.after(0, lambda p=progress_percent: self.progress_bar.config(value=p))
                            
                            # Update disk usage based on how much we've wiped
                            wiped_percent = progress_percent
                            self.root.after(0, lambda p=wiped_percent: self.disk_usage_bar.config(value=p))
                            self.root.after(0, lambda p=wiped_percent: self.disk_usage_label.config(text=f"Wiped: {p:.1f}%"))
                        
                        # Update status
                        gb_copied = bytes_copied / (1024**3)
                        gb_total = total_size / (1024**3)
                        
                        status_text = f"Wiped: {gb_copied:.1f} GB / {gb_total:.1f} GB"
                        elapsed_str = f"Elapsed: {int(time_elapsed//60)}m {int(time_elapsed%60)}s"
                        
                        # Calculate ETA
                        if bytes_copied > last_bytes and time_elapsed > 0:
                            bytes_per_sec = bytes_copied / time_elapsed
                            remaining_bytes = total_size - bytes_copied
                            eta_seconds = remaining_bytes / bytes_per_sec if bytes_per_sec > 0 else 0
                            eta_str = f"ETA: {int(eta_seconds//60)}m {int(eta_seconds%60)}s"
                        else:
                            eta_str = "ETA: Calculating..."
                        
                        self.root.after(0, lambda: self.progress_status.config(text=status_text))
                        self.root.after(0, lambda: self.progress_details.config(text=elapsed_str))
                        self.root.after(0, lambda g=gb_copied: self.total_written_label.config(text=f"{g:.1f} GB"))
                        self.root.after(0, lambda e=eta_str: self.eta_label.config(text=e))
                        
                        last_bytes = bytes_copied
                
                time.sleep(0.5)
                
            except Exception as e:
                break
        
        # Wipe completed or cancelled
        if self.wipe_process:
            return_code = self.wipe_process.returncode
            if return_code == 0:
                self.root.after(0, lambda: self._wipe_completed())
            elif return_code is None:
                # Process still running, was cancelled
                self.root.after(0, lambda: self._wipe_cancelled())
            else:
                self.root.after(0, lambda: self._wipe_error(f"Wipe failed with exit code {return_code}"))

    def _wipe_completed(self):
        """Handle successful wipe completion."""
        self.progress_bar.config(value=100)
        self.disk_usage_bar.config(value=100)
        self.disk_usage_label.config(text="100% Wiped")
        self._draw_util_history()  # Refresh sparkline
        self.util_percentage_label.config(text="0%")
        
        self.progress_status.config(text="✅ Wipe completed successfully!")
        self.progress_details.config(text="All data has been securely erased.")
        self.eta_label.config(text="Complete!")
        
        # Re-enable controls
        self.is_wiping = False
        self.scan_btn.config(state='normal')
        self.refresh_btn.config(state='normal')
        
        # Hide cancel button, show close button
        self.cancel_btn.config(text="✅ Close", command=self._close_progress)
        
        messagebox.showinfo("Wipe Complete", "Device has been successfully wiped!\nAll data has been permanently erased.")

    def _wipe_cancelled(self):
        """Handle wipe cancellation."""
        self.progress_status.config(text="❌ Wipe operation cancelled")
        self.progress_details.config(text="Operation was interrupted - device may be partially wiped")
        self._draw_util_history()
        self.util_percentage_label.config(text="0%")
        self.eta_label.config(text="Cancelled")
        
        # Re-enable controls
        self.is_wiping = False
        self.scan_btn.config(state='normal')
        self.refresh_btn.config(state='normal')
        
        self.cancel_btn.config(text="✅ Close", command=self._close_progress)
        
        messagebox.showwarning("Wipe Cancelled", "Wipe operation was cancelled.\nDevice may be partially wiped.")

    def _wipe_error(self, error_msg):
        """Handle wipe error."""
        self.progress_status.config(text=f"❌ Error: {error_msg}")
        self.progress_details.config(text="")
        self._draw_util_history()
        self.util_percentage_label.config(text="0%")
        self.eta_label.config(text="Error")
        
        # Re-enable controls
        self.is_wiping = False
        self.scan_btn.config(state='normal')
        self.refresh_btn.config(state='normal')
        
        self.cancel_btn.config(text="✅ Close", command=self._close_progress)
        
        messagebox.showerror("Wipe Error", f"Wipe operation failed:\n{error_msg}")

    def _cancel_wipe(self):
        """Cancel ongoing wipe operation immediately."""
        if self.wipe_process and self.wipe_process.poll() is None:
            # Confirm cancellation
            result = messagebox.askyesno(
                "Cancel Wipe",
                "Are you sure you want to cancel the wipe operation?\nThe device will be partially wiped.",
                icon='warning'
            )
            
            if result:
                try:
                    # Kill entire process group for immediate termination
                    if hasattr(self.wipe_process, 'pid'):
                        os.killpg(os.getpgid(self.wipe_process.pid), signal.SIGTERM)
                        time.sleep(0.5)
                        # Force kill if still running
                        if self.wipe_process.poll() is None:
                            os.killpg(os.getpgid(self.wipe_process.pid), signal.SIGKILL)
                except Exception as e:
                    print(f"DEBUG: Cancel error: {e}")
                    # Fallback to direct process termination
                    try:
                        self.wipe_process.terminate()
                        time.sleep(0.5)
                        if self.wipe_process.poll() is None:
                            self.wipe_process.kill()
                    except:
                        pass

    def _close_progress(self):
        """Close progress section."""
        self.progress_frame.grid_remove()
        self.cancel_btn.config(text="❌ Cancel Wipe", command=self._cancel_wipe)

    def _refresh_scan(self):
        """Refresh scan by rescanning devices."""
        if self.is_wiping:
            messagebox.showwarning("Busy", "Cannot scan while wipe operation is in progress")
            return
        self._scan_devices()

    def _show_error(self, error_msg):
        """Display error message."""
        for widget in self.devices_inner_frame.winfo_children():
            widget.destroy()
        
        error_label = ttk.Label(self.devices_inner_frame, text=f"❌ ERROR: {error_msg}", style='Error.TLabel')
        error_label.grid(row=0, column=0, pady=20)
        
        self.scan_btn.config(state='normal')
        self.refresh_btn.config(state='normal')
        self.status_label.config(text="❌ Scan failed", style='Error.TLabel')
        messagebox.showerror("Error", error_msg)


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
