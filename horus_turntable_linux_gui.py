#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import serial
import time
import threading
import sys
import os
from datetime import datetime

class HorusGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Horus 0.2 - Kontroler talerza obrotowego MakerBot Digitizer")
        self.root.geometry("800x700")
        
        # Kontroler urządzenia
        self.controller = None
        self.ser = None
        self.is_connected = False
        self.monitoring = False
        self.monitor_thread = None
        
        # Zmienne GUI
        self.port_var = tk.StringVar(value="/dev/ttyUSB0")
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
        
        self.setup_gui()
        
    def setup_gui(self):
        """Tworzy interfejs graficzny"""
        # Główny kontener
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Konfiguracja siatki
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Sekcja połączenia
        conn_frame = ttk.LabelFrame(main_frame, text="Połączenie", padding="5")
        conn_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=0, sticky=tk.W)
        port_combo = ttk.Combobox(conn_frame, textvariable=self.port_var, 
                                 values=["/dev/ttyUSB0", "/dev/ttyACM0", "/dev/ttyUSB1", "COM1", "COM2", "COM3"])
        port_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 10))
        
        ttk.Label(conn_frame, text="Baudrate:").grid(row=0, column=2, sticky=tk.W)
        baudrate_combo = ttk.Combobox(conn_frame, textvariable=self.baudrate_var,
                                     values=["9600", "19200", "38400", "57600", "115200"])
        baudrate_combo.grid(row=0, column=3, sticky=(tk.W, tk.E), padx=(5, 10))
        
        self.connect_btn = ttk.Button(conn_frame, text="Połącz", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=4, padx=(5, 0))
        
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
        self.log_text = scrolledtext.ScrolledText(monitor_frame, height=15, width=70)
        self.log_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Pasek statusu
        self.status_var = tk.StringVar(value="Gotowy")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Konfiguracja rozszerzania
        main_frame.rowconfigure(4, weight=1)
        
        # Dodaj tekst powitalny
        self.log_message("🚀 Horus 0.2 GUI Controller - Gotowy do pracy")
        self.log_message("💡 Wybierz port i naciśnij 'Połącz' aby rozpocząć")
        
    def log_message(self, message):
        """Dodaje wiadomość do logu z timestampem"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}\n"
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
            self.ser = serial.Serial(
                port=self.port_var.get(),
                baudrate=int(self.baudrate_var.get()),
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            time.sleep(2)  # Czas na inicjalizację
            
            self.is_connected = True
            self.connect_btn.config(text="Rozłącz")
            self.log_message(f"✅ Połączono z {self.port_var.get()} na {self.baudrate_var.get()} baud")
            self.update_status("Połączono")
            
        except serial.SerialException as e:
            messagebox.showerror("Błąd połączenia", f"Nie można połączyć z urządzeniem:\n{e}")
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
            if not command.endswith('\n'):
                command += '\n'
                
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
            messagebox.showerror("Błąd", f"Błąd wysyłania komendy:\n{e}")
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
    
    def get_status(self):
        """Pobiera status urządzenia"""
        self.log_message("📊 Sprawdzam status...")
        self.log_message(f"📍 Śledzona pozycja: {self.current_position}°")
        return self.send_gcode("?")
        
    def send_command(self):
        """Wysyła bezpośrednią komendę"""
        command = self.command_var.get().strip()
        if command:
            self.send_gcode(command)
            self.command_var.set("")
            

        
    def get_settings(self):
        """Pobiera ustawienia"""
        self.log_message("⚙️ Pobieranie ustawień...")
        self.send_gcode("$$")
        
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
        self.send_gcode("\x18")  # Ctrl-X
        
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
            filename = f"horus_log_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.log_text.get(1.0, tk.END))
                
            self.log_message(f"💾 Log zapisany jako: {filename}")
            messagebox.showinfo("Sukces", f"Log zapisany jako:\n{filename}")
            
        except Exception as e:
            self.log_message(f"❌ Błąd zapisu: {e}")
            messagebox.showerror("Błąd", f"Nie można zapisać logu:\n{e}")
            
    def on_closing(self):
        """Obsługuje zamknięcie aplikacji"""
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
