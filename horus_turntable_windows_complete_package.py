#!/usr/bin/env python3
"""
KOMPLETNY PAKIET HORUS 0.2 CONTROLLER
====================================

Ten plik zawiera wszystkie potrzebne pliki do stworzenia
aplikacji Windows dla kontrolera talerza obrotowego.

Zawartość pakietu:
- horus_gui_windows.py - główna aplikacja
- requirements.txt - wymagane pakiety
- build.spec - konfiguracja PyInstaller  
- setup.iss - skrypt Inno Setup
- build.bat - skrypt budowania
- create_icon.py - generator ikony
- version_info.txt - informacje o wersji
- README.txt - instrukcja użytkownika
- LICENSE.txt - licencja MIT
- INSTALL.md - instrukcja instalacji

INSTRUKCJA SZYBKIEGO STARTU:
1. Rozpakuj wszystkie pliki do jednego folderu
2. Zainstaluj Python 3.8+ z python.org
3. Uruchom: build.bat
4. Gotowe! Aplikacja w folderze dist/
"""

# =============================================================================
# PLIK 1: horus_gui_windows.py
# =============================================================================

HORUS_GUI_WINDOWS = '''#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import serial
import serial.tools.list_ports
import time
import threading
import sys
import os
from datetime import datetime
import json

class HorusGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Horus 0.2 - Kontroler talerza obrotowego MakerBot Digitizer v1.0")
        self.root.geometry("850x750")
        
        # Ustaw ikonę (jeśli istnieje)
        try:
            if hasattr(sys, '_MEIPASS'):
                # Jesteśmy w PyInstaller bundle
                icon_path = os.path.join(sys._MEIPASS, 'icon.ico')
            else:
                icon_path = 'icon.ico'
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except:
            pass
        
        # Kontroler urządzenia
        self.controller = None
        self.ser = None
        self.is_connected = False
        self.monitoring = False
        self.monitor_thread = None
        
        # Zmienne GUI
        self.port_var = tk.StringVar(value="COM3")
        self.baudrate_var = tk.StringVar(value="115200")
        self.speed_var = tk.StringVar(value="200")
        self.position_var = tk.StringVar(value="0")
        self.command_var = tk.StringVar()
        self.auto_disable_var = tk.StringVar(value="0")
        self.rotations_var = tk.StringVar(value="1")
        
        # Timer dla automatycznego wyłączania silnika
        self.disable_timer = None
        
        # Śledź aktualną pozycję dla obrotów wielokrotnych
        self.current_position = 0.0
        
        # Konfiguracja
        self.config_file = os.path.join(os.path.expanduser("~"), "horus_config.json")
        self.load_config()
        
        self.setup_gui()
        self.refresh_ports()
        
    def load_config(self):
        """Ładuje konfigurację z pliku"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.port_var.set(config.get('port', 'COM3'))
                    self.baudrate_var.set(config.get('baudrate', '115200'))
                    self.speed_var.set(config.get('speed', '200'))
                    self.auto_disable_var.set(config.get('auto_disable', '0'))
        except Exception as e:
            print(f"Nie można załadować konfiguracji: {e}")
    
    def save_config(self):
        """Zapisuje konfigurację do pliku"""
        try:
            config = {
                'port': self.port_var.get(),
                'baudrate': self.baudrate_var.get(),
                'speed': self.speed_var.get(),
                'auto_disable': self.auto_disable_var.get()
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Nie można zapisać konfiguracji: {e}")
        
    def setup_gui(self):
        """Tworzy interfejs graficzny"""
        # Główny kontener
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Konfiguracja siatki
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Menu bar
        self.create_menu()
        
        # Sekcja połączenia
        conn_frame = ttk.LabelFrame(main_frame, text="Połączenie", padding="5")
        conn_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=0, sticky=tk.W)
        self.port_combo = ttk.Combobox(conn_frame, textvariable=self.port_var, width=12)
        self.port_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        
        ttk.Button(conn_frame, text="🔄", command=self.refresh_ports, width=3).grid(row=0, column=2, padx=(0, 10))
        
        ttk.Label(conn_frame, text="Baudrate:").grid(row=0, column=3, sticky=tk.W)
        baudrate_combo = ttk.Combobox(conn_frame, textvariable=self.baudrate_var, width=8,
                                     values=["9600", "19200", "38400", "57600", "115200"])
        baudrate_combo.grid(row=0, column=4, sticky=(tk.W, tk.E), padx=(5, 10))
        
        self.connect_btn = ttk.Button(conn_frame, text="Połącz", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=5, padx=(5, 0))
        
        # Sekcja kontroli silnika
        motor_frame = ttk.LabelFrame(main_frame, text="Kontrola silnika", padding="5")
        motor_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Pierwsza linia przycisków
        ttk.Button(motor_frame, text="Włącz silnik (M17)", command=self.enable_motor).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(motor_frame, text="Wyłącz silnik (M18)", command=self.disable_motor).grid(row=0, column=1, padx=5)
        ttk.Button(motor_frame, text="Reset pozycji (G50)", command=self.reset_position).grid(row=0, column=2, padx=5)
        ttk.Button(motor_frame, text="Pozycja domowa", command=self.home_turntable).grid(row=0, column=3, padx=(5, 0))
        
        # Druga linia - automatyczne wyłączanie
        auto_frame = ttk.Frame(motor_frame)
        auto_frame.grid(row=1, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(10, 0))
        
        ttk.Label(auto_frame, text="Auto-wyłączenie silnika po:").grid(row=0, column=0, sticky=tk.W)
        auto_disable_entry = ttk.Entry(auto_frame, textvariable=self.auto_disable_var, width=8)
        auto_disable_entry.grid(row=0, column=1, padx=(5, 5))
        ttk.Label(auto_frame, text="sek (0 = wyłączone)").grid(row=0, column=2, sticky=tk.W)
        
        # Sekcja pozycjonowania
        pos_frame = ttk.LabelFrame(main_frame, text="Pozycjonowanie", padding="5")
        pos_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Pierwsza linia - prędkość
        ttk.Label(pos_frame, text="Prędkość (°/s):").grid(row=0, column=0, sticky=tk.W)
        speed_entry = ttk.Entry(pos_frame, textvariable=self.speed_var, width=8)
        speed_entry.grid(row=0, column=1, padx=(5, 10))
        ttk.Button(pos_frame, text="Ustaw prędkość", command=self.set_speed).grid(row=0, column=2, padx=(0, 10))
        
        # Druga linia - pozycja podstawowa
        ttk.Label(pos_frame, text="Pozycja (°):").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        position_entry = ttk.Entry(pos_frame, textvariable=self.position_var, width=8)
        position_entry.grid(row=1, column=1, padx=(5, 10), pady=(5, 0))
        ttk.Button(pos_frame, text="Idź do pozycji", command=self.go_to_position).grid(row=1, column=2, padx=(0, 10), pady=(5, 0))
        
        # Trzecia linia - obroty wielokrotne
        ttk.Label(pos_frame, text="Ilość obrotów:").grid(row=2, column=0, sticky=tk.W, pady=(5, 0))
        rotations_entry = ttk.Entry(pos_frame, textvariable=self.rotations_var, width=8)
        rotations_entry.grid(row=2, column=1, padx=(5, 10), pady=(5, 0))
        ttk.Button(pos_frame, text="Wykonaj obroty", command=self.perform_rotations).grid(row=2, column=2, padx=(0, 10), pady=(5, 0))
        
        # Czwarta linia - kierunek obrotów i info o pozycji
        direction_frame = ttk.Frame(pos_frame)
        direction_frame.grid(row=3, column=0, columnspan=3, pady=(5, 0))
        ttk.Button(direction_frame, text="🔄 W prawo", command=lambda: self.rotate_direction(1)).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(direction_frame, text="🔄 W lewo", command=lambda: self.rotate_direction(-1)).grid(row=0, column=1, padx=5)
        ttk.Button(direction_frame, text="⏹️ Stop", command=self.emergency_stop).grid(row=0, column=2, padx=5)
        ttk.Button(direction_frame, text="🏠 Sync pozycji", command=self.sync_position).grid(row=0, column=3, padx=(5, 0))
        
        # Przyciski szybkiego pozycjonowania
        quick_frame = ttk.Frame(pos_frame)
        quick_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        positions = [0, 45, 90, 135, 180, -45, -90, -135, -180]
        for i, pos in enumerate(positions):
            ttk.Button(quick_frame, text=f"{pos}°", width=6,
                      command=lambda p=pos: self.quick_position(p)).grid(row=i//5, column=i%5, padx=2, pady=2)
        
        # Sekcja komend bezpośrednich
        cmd_frame = ttk.LabelFrame(main_frame, text="Komendy bezpośrednie", padding="5")
        cmd_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        cmd_frame.columnconfigure(0, weight=1)
        
        command_entry = ttk.Entry(cmd_frame, textvariable=self.command_var)
        command_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        command_entry.bind('<Return>', lambda e: self.send_command())
        
        ttk.Button(cmd_frame, text="Wyślij", command=self.send_command).grid(row=0, column=1)
        
        # Przyciski systemowe
        sys_frame = ttk.Frame(cmd_frame)
        sys_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        
        ttk.Button(sys_frame, text="Status (?)", command=self.get_status).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(sys_frame, text="Ustawienia ($$)", command=self.get_settings).grid(row=0, column=1, padx=5)
        ttk.Button(sys_frame, text="Info ($I)", command=self.get_info).grid(row=0, column=2, padx=5)
        ttk.Button(sys_frame, text="Odblokuj ($X)", command=self.unlock_alarm).grid(row=0, column=3, padx=5)
        ttk.Button(sys_frame, text="Soft Reset", command=self.soft_reset).grid(row=0, column=4, padx=(5, 0))
        
        # Sekcja monitorowania
        monitor_frame = ttk.LabelFrame(main_frame, text="Monitor komunikacji", padding="5")
        monitor_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        monitor_frame.columnconfigure(0, weight=1)
        monitor_frame.rowconfigure(1, weight=1)
        
        # Przyciski monitorowania
        monitor_btn_frame = ttk.Frame(monitor_frame)
        monitor_btn_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        self.monitor_btn = ttk.Button(monitor_btn_frame, text="Start Monitor", command=self.toggle_monitoring)
        self.monitor_btn.grid(row=0, column=0, padx=(0, 5))
        ttk.Button(monitor_btn_frame, text="Wyczyść", command=self.clear_log).grid(row=0, column=1, padx=5)
        ttk.Button(monitor_btn_frame, text="Zapisz log", command=self.save_log).grid(row=0, column=2, padx=(5, 0))
        
        # Obszar tekstowy dla logów
        self.log_text = scrolledtext.ScrolledText(monitor_frame, height=12, width=70)
        self.log_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Pasek statusu
        self.status_var = tk.StringVar(value="Gotowy")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Konfiguracja rozszerzania
        main_frame.rowconfigure(4, weight=1)
        
        # Dodaj tekst powitalny
        self.log_message("🚀 Horus 0.2 GUI Controller - Windows Edition v1.0")
        self.log_message("💡 Wybierz port COM i naciśnij 'Połącz' aby rozpocząć")
        
    def create_menu(self):
        """Tworzy menu aplikacji"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Menu Plik
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Plik", menu=file_menu)
        file_menu.add_command(label="Zapisz konfigurację", command=self.save_config)
        file_menu.add_command(label="Wczytaj konfigurację", command=self.load_config)
        file_menu.add_separator()
        file_menu.add_command(label="Zapisz log...", command=self.save_log)
        file_menu.add_separator()
        file_menu.add_command(label="Wyjście", command=self.on_closing)
        
        # Menu Narzędzia
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Narzędzia", menu=tools_menu)
        tools_menu.add_command(label="Odśwież porty COM", command=self.refresh_ports)
        tools_menu.add_command(label="Test połączenia", command=self.test_connection)
        
        # Menu Pomoc
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Pomoc", menu=help_menu)
        help_menu.add_command(label="Instrukcja obsługi", command=self.show_help)
        help_menu.add_command(label="O programie", command=self.show_about)
    
    def refresh_ports(self):
        """Odświeża listę dostępnych portów COM"""
        ports = []
        try:
            available_ports = serial.tools.list_ports.comports()
            for port in available_ports:
                ports.append(f"{port.device} - {port.description}")
            
            if not ports:
                ports = ["Brak dostępnych portów"]
                
            self.port_combo['values'] = ports
            
            # Jeśli obecny port nie jest na liście, wybierz pierwszy dostępny
            current_port = self.port_var.get()
            if not any(current_port in port for port in ports) and ports[0] != "Brak dostępnych portów":
                self.port_var.set(ports[0].split(' - ')[0])
                
            self.log_message(f"🔄 Odświeżono porty COM: {len(ports)} znaleziono")
            
        except Exception as e:
            self.log_message(f"❌ Błąd odświeżania portów: {e}")
    
    def test_connection(self):
        """Testuje połączenie z urządzeniem"""
        if not self.is_connected:
            messagebox.showwarning("Test", "Najpierw nawiąż połączenie z urządzeniem!")
            return
            
        self.log_message("🔍 Test połączenia...")
        response = self.send_gcode("?")
        if response:
            messagebox.showinfo("Test", "Połączenie działa poprawnie!")
        else:
            messagebox.showerror("Test", "Brak odpowiedzi z urządzenia!")
    
    def show_help(self):
        """Wyświetla instrukcję obsługi"""
        help_text = """
INSTRUKCJA OBSŁUGI - Horus 0.2 Controller

1. POŁĄCZENIE:
   • Wybierz port COM z listy (np. COM3)
   • Sprawdź baudrate (domyślnie 115200)
   • Kliknij "Połącz"

2. PODSTAWOWE OPERACJE:
   • Włącz silnik przed użyciem (M17)
   • Ustaw prędkość w °/s
   • Przejdź do pozycji lub wykonaj obroty
   • ZAWSZE wyłącz silnik po zakończeniu (M18)

3. OBROTY WIELOKROTNE:
   • Wpisz liczbę obrotów (np. 2.5)
   • Użyj przycisków kierunkowych
   • "W prawo" = zgodnie ze wskazówkami zegara
   • "W lewo" = przeciwnie do wskazówek zegara

4. BEZPIECZEŃSTWO:
   • Ustaw auto-wyłączenie silnika (np. 30 sek)
   • Użyj "Stop" w nagłych wypadkach
   • Monitor pokazuje wszystkie operacje

5. WSKAZÓWKI:
   • Zapisz konfigurację przed wyjściem
   • Używaj "Sync pozycji" po resetach
   • Sprawdzaj logi w przypadku problemów

Więcej informacji: github.com/twój-projekt
        """
        
        help_window = tk.Toplevel(self.root)
        help_window.title("Instrukcja obsługi")
        help_window.geometry("600x500")
        
        text_widget = scrolledtext.ScrolledText(help_window, wrap=tk.WORD, padx=10, pady=10)
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert(tk.END, help_text)
        text_widget.config(state=tk.DISABLED)
    
    def show_about(self):
        """Wyświetla informacje o programie"""
        about_text = """
Horus 0.2 GUI Controller
Windows Edition v1.0

Kontroler talerza obrotowego MakerBot Digitizer
Kompatybilny z firmware Horus 0.2 (GRBL)

Autor: [Twoje imię]
Licencja: Open Source
GitHub: [link do repozytorium]

Wykorzystane biblioteki:
• Python 3.x
• tkinter (GUI)
• pyserial (komunikacja)
• PyInstaller (kompilacja)

© 2025 - Wszystkie prawa zastrzeżone
        """
        messagebox.showinfo("O programie", about_text)
        
    def log_message(self, message):
        """Dodaje wiadomość do logu z timestampem"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}\\n"
        self.log_text.insert(tk.END, full_message)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def update_status(self, message):
        """Aktualizuje pasek statusu"""
        self.status_var.set(message)
        self.root.update_idletasks()
        
    def toggle_connection(self):
        """Przełącza połączenie z urządzeniem"""
        if not self.is_connected:
            self.connect_device()
        else:
            self.disconnect_device()
            
    def connect_device(self):
        """Nawiązuje połączenie z urządzeniem"""
        try:
            # Wyciągnij sam numer portu COM z opisu
            port_description = self.port_var.get()
            if " - " in port_description:
                port = port_description.split(" - ")[0]
            else:
                port = port_description
                
            self.ser = serial.Serial(
                port=port,
                baudrate=int(self.baudrate_var.get()),
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            time.sleep(2)  # Czas na inicjalizację
            
            self.is_connected = True
            self.connect_btn.config(text="Rozłącz")
            self.log_message(f"✅ Połączono z {port} na {self.baudrate_var.get()} baud")
            self.update_status("Połączono")
            
        except serial.SerialException as e:
            messagebox.showerror("Błąd połączenia", f"Nie można połączyć z urządzeniem:\\n{e}")
            self.log_message(f"❌ Błąd połączenia: {e}")
            self.update_status("Błąd połączenia")
            
    def disconnect_device(self):
        """Rozłącza urządzenie"""
        if self.monitoring:
            self.stop_monitoring()
            
        if self.ser and self.ser.is_open:
            self.ser.close()
            
        self.is_connected = False
        self.connect_btn.config(text="Połącz")
        self.log_message("🔌 Rozłączono")
        self.update_status("Rozłączono")
        
    def send_gcode(self, command):
        """Wysyła komendę G-code do urządzenia"""
        if not self.is_connected or not self.ser:
            messagebox.showwarning("Błąd", "Brak połączenia z urządzeniem!")
            return False
            
        try:
            # Opróżnij bufor wejściowy
            self.ser.flushInput()
            
            # Dodaj znak końca linii jeśli nie ma
            if not command.endswith('\\n'):
                command += '\\n'
                
            # Wyślij komendę
            self.ser.write(command.encode('utf-8'))
            self.log_message(f"📡 Wysłano: {command.strip()}")
            
            # Czekaj na odpowiedź
            time.sleep(0.2)
            responses = []
            
            start_time = time.time()
            while time.time() - start_time < 1.0:
                if self.ser.in_waiting > 0:
                    try:
                        line = self.ser.readline().decode('utf-8').strip()
                        if line:
                            responses.append(line)
                            self.log_message(f"📨 Odpowiedź: {line}")
                    except UnicodeDecodeError:
                        continue
                else:
                    time.sleep(0.05)
                    if self.ser.in_waiting == 0:
                        break
                        
            return responses if responses else True
            
        except Exception as e:
            self.log_message(f"❌ Błąd wysyłania: {e}")
            messagebox.showerror("Błąd", f"Błąd wysyłania komendy:\\n{e}")
            return False
            
    def enable_motor(self):
        """Włącza silnik"""
        self.log_message("⚡ Włączam silnik...")
        result = self.send_gcode("M17")
        
        # Sprawdź czy ma być automatyczne wyłączenie
        try:
            auto_disable_time = float(self.auto_disable_var.get())
            if auto_disable_time > 0:
                self.log_message(f"⏰ Silnik zostanie automatycznie wyłączony po {auto_disable_time} sekundach")
                # Anuluj poprzedni timer jeśli istnieje
                if self.disable_timer:
                    self.root.after_cancel(self.disable_timer)
                # Ustaw nowy timer
                self.disable_timer = self.root.after(int(auto_disable_time * 1000), self.auto_disable_motor)
        except ValueError:
            pass  # Nieprawidłowa wartość, ignoruj
        
        return result
    
    def auto_disable_motor(self):
        """Automatycznie wyłącza silnik"""
        self.log_message("⏰ Automatyczne wyłączenie silnika")
        self.disable_motor()
        self.disable_timer = None
        
    def disable_motor(self):
        """Wyłącza silnik"""
        # Anuluj timer automatycznego wyłączania jeśli istnieje
        if self.disable_timer:
            self.root.after_cancel(self.disable_timer)
            self.disable_timer = None
            
        self.log_message("🔌 Wyłączam silnik...")
        self.send_gcode("M18")
        
    def reset_position(self):
        """Resetuje pozycję do zera"""
        self.log_message("🏠 Resetuję pozycję do zera...")
        result = self.send_gcode("G50")
        # Aktualizuj śledzoną pozycję
        self.current_position = 0.0
        self.position_var.set("0")
        return result
        
    def home_turntable(self):
        """Przechodzi do pozycji domowej"""
        self.log_message("🏠 Przechodzę do pozycji domowej...")
        self.enable_motor()
        time.sleep(0.1)
        self.reset_position()
        
    def set_speed(self):
        """Ustawia prędkość"""
        try:
            speed = float(self.speed_var.get())
            self.log_message(f"🏃 Ustawiam prędkość na {speed}°/s")
            self.send_gcode(f"G1 F{speed}")
        except ValueError:
            messagebox.showerror("Błąd", "Nieprawidłowa wartość prędkości!")
            
    def go_to_position(self):
        """Idzie do określonej pozycji"""
        try:
            position = float(self.position_var.get())
            speed = float(self.speed_var.get())
            
            self.log_message(f"🔄 Ustawiam prędkość {speed}°/s i przechodzę do pozycji {position}°")
            self.send_gcode(f"G1 F{speed}")
            time.sleep(0.1)
            result = self.send_gcode(f"G1 X{position}")
            
            # Aktualizuj śledzoną pozycję
            self.current_position = position
            
            return result
        except ValueError:
            messagebox.showerror("Błąd", "Nieprawidłowa wartość pozycji lub prędkości!")
            
    def quick_position(self, position):
        """Szybko przechodzi do predefiniowanej pozycji"""
        self.position_var.set(str(position))
        self.go_to_position()
    
    def perform_rotations(self):
        """Wykonuje określoną liczbę pełnych obrotów"""
        try:
            rotations = float(self.rotations_var.get())
            speed = float(self.speed_var.get())
            
            if rotations == 0:
                messagebox.showwarning("Błąd", "Liczba obrotów nie może być równa 0!")
                return
            
            # Oblicz nową pozycję absolutną (aktualna pozycja + obroty * 360°)
            rotation_degrees = rotations * 360
            new_position = self.current_position + rotation_degrees
            
            self.log_message(f"🌀 Wykonuję {rotations} obrotów ({rotation_degrees}°) z prędkością {speed}°/s")
            self.log_message(f"📍 Pozycja: {self.current_position}° → {new_position}°")
            
            # Ustaw prędkość i przejdź do nowej pozycji absolutnej
            self.send_gcode(f"G1 F{speed}")
            time.sleep(0.1)
            result = self.send_gcode(f"G1 X{new_position}")
            
            # Aktualizuj śledzoną pozycję
            self.current_position = new_position
            self.position_var.set(str(new_position))
            
            return result
            
        except ValueError:
            messagebox.showerror("Błąd", "Nieprawidłowa wartość liczby obrotów!")
    
    def rotate_direction(self, direction):
        """Obraca w określonym kierunku (1 = prawo, -1 = lewo)"""
        try:
            rotations = float(self.rotations_var.get())
            speed = float(self.speed_var.get())
            
            # Ustaw kierunek (prawo = dodatnie, lewo = ujemne)
            actual_rotations = rotations * direction
            rotation_degrees = actual_rotations * 360
            new_position = self.current_position + rotation_degrees
            
            direction_text = "w prawo" if direction > 0 else "w lewo"
            self.log_message(f"🔄 Obracam {abs(rotations)} obrotów {direction_text} ({rotation_degrees}°)")
            self.log_message(f"📍 Pozycja: {self.current_position}° → {new_position}°")
            
            # Ustaw prędkość i wykonaj obrót do nowej pozycji absolutnej
            self.send_gcode(f"G1 F{speed}")
            time.sleep(0.1)
            result = self.send_gcode(f"G1 X{new_position}")
            
            # Aktualizuj śledzoną pozycję
            self.current_position = new_position
            self.position_var.set(str(new_position))
            
            return result
            
        except ValueError:
            messagebox.showerror("Błąd", "Nieprawidłowa wartość liczby obrotów!")
    
    def emergency_stop(self):
        """Natychmiastowe zatrzymanie"""
        self.log_message("🚨 EMERGENCY STOP!")
        self.send_gcode("!")  # Feed hold - natychmiastowe zatrzymanie
        time.sleep(0.1)
        self.disable_motor()  # Wyłącz silnik dla bezpieczeństwa
    
    def sync_position(self):
        """Synchronizuje śledzoną pozycję z wartością w polu pozycji"""
        try:
            position = float(self.position_var.get())
            self.current_position = position
            self.log_message(f"🔄 Zsynchronizowano pozycję na {position}°")
        except ValueError:
            messagebox.showerror("Błąd", "Nieprawidłowa wartość pozycji!")
    
    def send_command(self):
        """Wysyła bezpośrednią komendę"""
        command = self.command_var.get().strip()
        if command:
            self.send_gcode(command)
            self.command_var.set("")
            
    def get_status(self):
        """Pobiera status urządzenia"""
        self.log_message("📊 Sprawdzam status...")
        self.log_message(f"📍 Śledzona pozycja: {self.current_position}°")
        return self.send_gcode("?")
        
    def get_settings(self):
        """Pobiera ustawienia"""
        self.log_message("⚙️ Pobieranie ustawień...")
        self.send_gcode("$")
        
    def get_info(self):
        """Pobiera informacje o firmware"""
        self.log_message("ℹ️ Pobieranie informacji o firmware...")
        self.send_gcode("$I")
        
    def unlock_alarm(self):
        """Odblokowuje alarm"""
        self.log_message("🔓 Odblokowuję alarm...")
        self.send_gcode("$X")
        
    def soft_reset(self):
        """Wykonuje soft reset"""
        self.log_message("🔄 Wykonuję soft reset...")
        self.send_gcode("\\x18")  # Ctrl-X
        
    def toggle_monitoring(self):
        """Przełącza monitorowanie"""
        if not self.monitoring:
            self.start_monitoring()
        else:
            self.stop_monitoring()
            
    def start_monitoring(self):
        """Rozpoczyna monitorowanie"""
        if not self.is_connected:
            messagebox.showwarning("Błąd", "Brak połączenia z urządzeniem!")
            return
            
        self.monitoring = True
        self.monitor_btn.config(text="Stop Monitor")
        self.log_message("👁️ Rozpoczynam monitorowanie...")
        
        # Uruchom wątek monitorowania
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        
    def stop_monitoring(self):
        """Zatrzymuje monitorowanie"""
        self.monitoring = False
        self.monitor_btn.config(text="Start Monitor")
        self.log_message("⏹️ Zatrzymano monitorowanie")
        
    def monitor_loop(self):
        """Pętla monitorowania (uruchamiana w osobnym wątku)"""
        while self.monitoring and self.is_connected:
            try:
                if self.ser and self.ser.in_waiting > 0:
                    line = self.ser.readline().decode('utf-8').strip()
                    if line:
                        self.log_message(f"[Monitor] {line}")
                time.sleep(0.01)
            except Exception as e:
                self.log_message(f"❌ Błąd monitorowania: {e}")
                break
                
    def clear_log(self):
        """Czyści log"""
        self.log_text.delete(1.0, tk.END)
        self.log_message("🧹 Log wyczyszczony")
        
    def save_log(self):
        """Zapisuje log do pliku"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"horus_log_{timestamp}.txt"
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Pliki tekstowe", "*.txt"), ("Wszystkie pliki", "*.*")],
                initialvalue=default_filename
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.get(1.0, tk.END))
                    
                self.log_message(f"💾 Log zapisany jako: {os.path.basename(filename)}")
                messagebox.showinfo("Sukces", f"Log zapisany jako:\\n{filename}")
                
        except Exception as e:
            self.log_message(f"❌ Błąd zapisu: {e}")
            messagebox.showerror("Błąd", f"Nie można zapisać logu:\\n{e}")
            
    def on_closing(self):
        """Obsługuje zamknięcie aplikacji"""
        # Zapisz konfigurację
        self.save_config()
        
        # Anuluj timer automatycznego wyłączania
        if self.disable_timer:
            self.root.after_cancel(self.disable_timer)
        
        if self.monitoring:
            self.stop_monitoring()
        if self.is_connected:
            self.disconnect_device()
        self.root.destroy()


def main():
    """Funkcja główna"""
    root = tk.Tk()
    app = HorusGUI(root)
    
    # Obsługa zamknięcia okna
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Uruchom aplikację
    root.mainloop()


if __name__ == "__main__":
    main()
'''

# =============================================================================
# POZOSTAŁE PLIKI
# =============================================================================

FILES = {
    'requirements.txt': '''pyserial>=3.5
pyinstaller>=5.0
''',

    'build.spec': '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['horus_gui_windows.py'],
    pathex=[],
    binaries=[],
    datas=[('icon.ico', '.'), ('README.txt', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='HorusController',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
    version='version_info.txt'
)
''',

    'version_info.txt': '''VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'OpenSource Developer'),
        StringStruct(u'FileDescription', u'Horus 0.2 Turntable Controller'),
        StringStruct(u'FileVersion', u'1.0.0.0'),
        StringStruct(u'InternalName', u'HorusController'),
        StringStruct(u'LegalCopyright', u'Copyright (C) 2025'),
        StringStruct(u'OriginalFilename', u'HorusController.exe'),
        StringStruct(u'ProductName', u'Horus 0.2 GUI Controller'),
        StringStruct(u'ProductVersion', u'1.0.0.0')])
      ]), 
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
''',

    'setup.iss': '''[Setup]
AppName=Horus 0.2 Controller
AppVersion=1.0
AppPublisher=OpenSource Developer
AppPublisherURL=https://github.com/your-repo
AppSupportURL=https://github.com/your-repo/issues
AppUpdatesURL=https://github.com/your-repo/releases
DefaultDirName={autopf}\\Horus Controller
DefaultGroupName=Horus Controller
AllowNoIcons=yes
LicenseFile=LICENSE.txt
InfoBeforeFile=README.txt
OutputDir=installer
OutputBaseFilename=HorusController_Setup_v1.0
SetupIconFile=icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "polish"; MessagesFile: "compiler:Languages\\Polish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1
Name: "associate"; Description: "Associate .gcode files with Horus Controller"; GroupDescription: "File associations:"; Flags: unchecked

[Files]
Source: "dist\\HorusController.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\\Horus Controller"; Filename: "{app}\\HorusController.exe"
Name: "{group}\\{cm:ProgramOnTheWeb,Horus Controller}"; Filename: "https://github.com/your-repo"
Name: "{group}\\{cm:UninstallProgram,Horus Controller}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\\Horus Controller"; Filename: "{app}\\HorusController.exe"; Tasks: desktopicon
Name: "{userappdata}\\Microsoft\\Internet Explorer\\Quick Launch\\Horus Controller"; Filename: "{app}\\HorusController.exe"; Tasks: quicklaunchicon

[Registry]
Root: HKCR; Subkey: ".gcode"; ValueType: string; ValueName: ""; ValueData: "HorusGCode"; Flags: uninsdeletevalue; Tasks: associate
Root: HKCR; Subkey: "HorusGCode"; ValueType: string; ValueName: ""; ValueData: "G-Code File"; Flags: uninsdeletekey; Tasks: associate
Root: HKCR; Subkey: "HorusGCode\\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\\HorusController.exe,0"; Tasks: associate
Root: HKCR; Subkey: "HorusGCode\\shell\\open\\command"; ValueType: string; ValueName: ""; ValueData: """"{app}\\HorusController.exe"""" """"%1"""""; Tasks: associate

[Run]
Filename: "{app}\\HorusController.exe"; Description: "{cm:LaunchProgram,Horus Controller}"; Flags: nowait postinstall skipifsilent
''',

    'build.bat': '''@echo off
echo ================================================
echo    Horus 0.2 Controller - Windows Build Script
echo ================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo BŁĄD: Python nie jest zainstalowany!
    echo Pobierz Python z: https://python.org
    pause
    exit /b 1
)

echo ✅ Python wykryty
echo.

pip --version >nul 2>&1
if errorlevel 1 (
    echo BŁĄD: pip nie jest dostępny!
    pause
    exit /b 1
)

echo ✅ pip wykryty
echo.

echo 📦 Instalowanie wymaganych pakietów...
pip install -r requirements.txt
if errorlevel 1 (
    echo BŁĄD: Nie można zainstalować pakietów!
    pause
    exit /b 1
)

echo ✅ Pakiety zainstalowane
echo.

echo 🧹 Czyszczenie poprzednich buildów...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo 🔨 Tworzenie pliku .exe...
pyinstaller build.spec
if errorlevel 1 (
    echo BŁĄD: PyInstaller zakończył się błędem!
    pause
    exit /b 1
)

echo ✅ Plik .exe utworzony w folderze dist\\
echo.

echo 📦 Sprawdzanie Inno Setup...
if exist "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe" (
    set INNO_PATH="C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe"
) else if exist "C:\\Program Files\\Inno Setup 6\\ISCC.exe" (
    set INNO_PATH="C:\\Program Files\\Inno Setup 6\\ISCC.exe"
) else (
    echo ⚠️  Inno Setup nie znaleziony!
    echo    Pobierz z: https://jrsoftware.org/isinfo.php
    echo    Lub skopiuj plik HorusController.exe z folderu dist\\
    echo.
    goto :end
)

echo 🎁 Tworzenie instalatora...
%INNO_PATH% setup.iss
if errorlevel 1 (
    echo BŁĄD: Inno Setup zakończył się błędem!
    pause
    exit /b 1
)

echo ✅ Installer utworzony w folderze installer\\

:end
echo.
echo ================================================
echo              BUILD ZAKOŃCZONY POMYŚLNIE!
echo ================================================
echo.
echo 📁 Pliki zostały utworzone:
echo    • dist\\HorusController.exe - Aplikacja
if exist installer\\HorusController_Setup_v1.0.exe (
    echo    • installer\\HorusController_Setup_v1.0.exe - Installer
)
echo.
echo 🚀 Możesz teraz dystrybuować aplikację!
echo.
pause
''',

    'create_icon.py': '''#!/usr/bin/env python3
"""
Tworzy prostą ikonę dla aplikacji Horus Controller
"""

try:
    from PIL import Image, ImageDraw, ImageFont
    
    def create_icon():
        # Utwórz obraz 256x256 z przezroczystym tłem
        size = 256
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Narysuj koło (talerz obrotowy)
        margin = 20
        circle_bbox = [margin, margin, size-margin, size-margin]
        draw.ellipse(circle_bbox, fill=(64, 128, 255, 255), outline=(32, 64, 128, 255), width=8)
        
        # Narysuj strzałkę rotacji
        center = size // 2
        radius = 60
        
        # Strzałka zakrzywiona
        arrow_points = []
        import math
        for angle in range(45, 315, 5):
            x = center + radius * math.cos(math.radians(angle))
            y = center + radius * math.sin(math.radians(angle))
            arrow_points.append((x, y))
        
        # Narysuj ścieżkę strzałki
        if len(arrow_points) > 1:
            for i in range(len(arrow_points)-1):
                draw.line([arrow_points[i], arrow_points[i+1]], fill=(255, 255, 255, 255), width=6)
        
        # Narysuj grot strzałki
        if arrow_points:
            end_point = arrow_points[-1]
            arrow_head = [
                (end_point[0], end_point[1]),
                (end_point[0]-15, end_point[1]-10),
                (end_point[0]-10, end_point[1]),
                (end_point[0]-15, end_point[1]+10)
            ]
            draw.polygon(arrow_head, fill=(255, 255, 255, 255))
        
        # Dodaj tekst "H" w centrum
        try:
            font = ImageFont.truetype("arial.ttf", 80)
        except:
            font = ImageFont.load_default()
        
        text = "H"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = (size - text_width) // 2
        text_y = (size - text_height) // 2
        
        draw.text((text_x, text_y), text, fill=(255, 255, 255, 255), font=font)
        
        # Zapisz jako ICO (różne rozmiary)
        icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        images = []
        
        for icon_size in icon_sizes:
            resized = image.resize(icon_size, Image.Resampling.LANCZOS)
            images.append(resized)
        
        # Zapisz jako .ico
        images[0].save('icon.ico', format='ICO', sizes=[(img.width, img.height) for img in images])
        print("✅ Ikona została utworzona: icon.ico")
        
        # Zapisz też jako PNG dla podglądu
        image.save('icon.png', format='PNG')
        print("✅ Podgląd ikony: icon.png")

    if __name__ == "__main__":
        create_icon()
        
except ImportError:
    print("⚠️  Moduł PIL (Pillow) nie jest zainstalowany")
    print("   Zainstaluj: pip install Pillow")
    print("   Lub użyj gotowej ikony icon.ico")
''',

    'README.txt': '''Horus 0.2 GUI Controller - Windows Edition
==========================================

WYMAGANIA SYSTEMOWE:
- Windows 7/8/10/11 (32-bit lub 64-bit)
- Microsoft .NET Framework 4.5 lub nowszy
- Port USB (dla połączenia z urządzeniem)

INSTALACJA:
1. Uruchom HorusController_Setup_v1.0.exe
2. Podążaj za instrukcjami instalatora
3. Podłącz urządzenie MakerBot Digitizer przez USB
4. Uruchom "Horus Controller" z menu Start

PIERWSZE URUCHOMIENIE:
1. Uruchom program
2. Kliknij przycisk "🔄" aby odświeżyć porty COM
3. Wybierz odpowiedni port COM z listy
4. Kliknij "Połącz"
5. Gdy połączenie zostanie nawiązane, możesz kontrolować talerz

PODSTAWOWE FUNKCJE:
- Kontrola silnika (włącz/wyłącz)
- Pozycjonowanie precyzyjne
- Obroty wielokrotne w obu kierunkach
- Automatyczne wyłączanie silnika
- Monitorowanie komunikacji w czasie rzeczywistym
- Zapisywanie logów

BEZPIECZEŃSTWO:
- ZAWSZE wyłącz silnik po zakończeniu pracy
- Używaj funkcji auto-wyłączania (np. 30 sekund)
- W nagłych wypadkach użyj przycisku "Stop"

WSPARCIE:
- Dokumentacja: README.txt w folderze instalacji
- Kod źródłowy: GitHub (link w menu Pomoc)
- Zgłaszanie błędów: GitHub Issues

LICENCJA:
Program jest dostępny na licencji open source.
Zobacz plik LICENSE.txt dla szczegółów.

© 2025 - Wszystkie prawa zastrzeżone
''',

    'LICENSE.txt': '''MIT License

Copyright (c) 2025 Horus Controller Developer

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
''',

    'INSTALL.md': '''# 🚀 Horus 0.2 Controller - Instrukcja budowania Windows

## 📋 Wymagania

### 1. Python 3.8+
- Pobierz z https://python.org
- Zaznacz "Add Python to PATH" podczas instalacji

### 2. Pakiety Python
```bash
pip install pyserial pyinstaller pillow
```

### 3. Inno Setup (opcjonalne)
- Pobierz z: https://jrsoftware.org/isinfo.php
- Dla tworzenia profesjonalnego instalatora

## 🔧 Instrukcja krok po kroku

### Krok 1: Przygotowanie
1. Stwórz folder projektu: `mkdir HorusController`
2. Skopiuj wszystkie pliki do folderu
3. Zainstaluj zależności: `pip install -r requirements.txt`

### Krok 2: Budowanie
**Opcja A: Automatyczny build**
```cmd
build.bat
```

**Opcja B: Ręczny build**
```cmd
python create_icon.py  # Stwórz ikonę
pyinstaller build.spec  # Stwórz .exe
```

### Krok 3: Testowanie
```cmd
dist\\HorusController.exe
```

### Krok 4: Installer (opcjonalne)
```cmd
"C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe" setup.iss
```

## 📁 Wynikowe pliki
- `dist\\HorusController.exe` - Standalone aplikacja
- `installer\\HorusController_Setup_v1.0.exe` - Installer

## 🎯 Dystrybyucja
1. **Dla małej grupy**: Udostępnij `HorusController.exe`
2. **Szeroka dystrybucja**: Użyj instalatora `.exe`
3. **Enterprise**: MSI package (zaawansowane)

## 🐛 Rozwiązywanie problemów
- **Python nie znaleziony**: Dodaj do PATH
- **PyInstaller błędy**: `pip install pyinstaller==5.13.2`
- **Brak serial**: `pip install pyserial==3.5`
- **Błąd ikony**: `pip install Pillow`

## ✅ Checklist
- [ ] Aplikacja kompiluje się
- [ ] Wszystkie funkcje działają
- [ ] Ikona jest wyświetlana
- [ ] Dokumentacja kompletna
- [ ] Testowane na czystym Windows
'''
}

# =============================================================================
# SKRYPT EKSTRAKTORA
# =============================================================================

def extract_all_files():
    """Ekstraktuje wszystkie pliki z pakietu"""
    import os
    
    print("🚀 Horus 0.2 Controller - Ekstraktor pakietu")
    print("=" * 50)
    
    # Stwórz główny plik aplikacji
    print("📄 Tworzę horus_gui_windows.py...")
    with open('horus_gui_windows.py', 'w', encoding='utf-8') as f:
        f.write(HORUS_GUI_WINDOWS)
    
    # Stwórz pozostałe pliki
    for filename, content in FILES.items():
        print(f"📄 Tworzę {filename}...")
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
    
    print("\n✅ Wszystkie pliki zostały utworzone!")
    print("\n📋 Lista plików:")
    files = ['horus_gui_windows.py'] + list(FILES.keys())
    for i, filename in enumerate(files, 1):
        print(f"  {i:2d}. {filename}")
    
    print(f"\n🎯 Łącznie: {len(files)} plików")
    print("\n🚀 NASTĘPNE KROKI:")
    print("1. Zainstaluj Python 3.8+ z python.org")
    print("2. Uruchom: build.bat")
    print("3. Gotowe! Aplikacja w folderze dist/")
    print("\n📖 Więcej informacji w INSTALL.md")

if __name__ == "__main__":
    extract_all_files()
