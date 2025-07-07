# Horus Turntable Controller

Professional control software for MakerBot Digitizer turntable running Horus 0.2 firmware (GRBL-based). This project provides both command-line and GUI interfaces for precise turntable control, multi-rotation support, and safety features.

## Features

- **Precise positioning** - Control turntable to single degree accuracy
- **Multi-rotation support** - Execute multiple full rotations in both directions
- **Auto motor shutoff** - Configurable timer to prevent motor overheating
- **Real-time monitoring** - Live communication logs and status updates
- **Cross-platform support** - Linux command-line and Windows GUI versions
- **Professional installer** - Complete Windows setup with automatic port detection
- **Safety features** - Emergency stop and position synchronization

## What's Included

### Linux Version
- **horus_turntable_gcode_linux_sender.py** - Command-line interface with interactive mode
  - Full G-code command support
  - Command history with readline
  - Motor control and positioning
  - Status monitoring and diagnostics

### Linux GUI Version  
- **horus_turntable_linux_gui.py** - Graphical interface for Linux
  - Modern tkinter-based interface
  - Visual position control
  - Real-time communication monitor
  - Configuration management

### Windows Complete Package
- **horus_turntable_windows_complete_package.py** - All-in-one Windows solution
  - Complete application source code
  - PyInstaller build configuration
  - Professional Inno Setup installer
  - Icon generation and Windows integration
  - Automatic COM port detection

## Quick Start
### Linux GUI
```
python3 horus_turntable_linux_gui.py
```
### Linux Command Line
```
python3 horus_turntable_gcode_linux_sender.py --interactive
```
### Windows Command Line
```
python horus_turntable_windows_complete_package.py
```

