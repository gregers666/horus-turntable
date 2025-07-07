#!/usr/bin/env python3

import serial
import time
import sys
import argparse
import atexit
import os

# Próbuj załadować readline, ale kontynuuj bez niego jeśli nie ma
try:
    import readline
    READLINE_AVAILABLE = True
    print("✅ Moduł readline załadowany - historia komend dostępna")
except ImportError:
    READLINE_AVAILABLE = False
    print("⚠️ Moduł readline niedostępny - brak historii komend")

class MakerBotDigitizerController:
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200):
        """
        Inicjalizuje kontroler talerza obrotowego MakerBot Digitizer (Horus 0.2/GRBL)
        
        Args:
            port: Port szeregowy (zwykle /dev/ttyUSB0 lub /dev/ttyACM0)
            baudrate: Prędkość transmisji (domyślnie 115200)
        """
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.is_grbl = True  # Firmware Horus 0.2 jest oparty na GRBL
        self.setup_readline()  # Konfiguruj historię komend
        
    def setup_readline(self):
        """Konfiguruje readline dla historii komend"""
        if not READLINE_AVAILABLE:
            print("📝 Historia komend niedostępna (brak modułu readline)")
            self.history_file = None
            return
            
        try:
            # Plik z historią komend
            self.history_file = os.path.expanduser('~/.horus_history')
            
            # Wczytaj historię jeśli istnieje
            if os.path.exists(self.history_file):
                readline.read_history_file(self.history_file)
                print(f"📚 Wczytano historię z {self.history_file}")
            
            # Ustaw maksymalną długość historii
            readline.set_history_length(1000)
            
            # Zapisuj historię przy wyjściu
            atexit.register(self.save_history)
            
            # Ustawienia edycji - poprawione escape sequences
            readline.parse_and_bind('tab: complete')
            readline.parse_and_bind('"\\e[A": history-search-backward')  # Strzałka góra
            readline.parse_and_bind('"\\e[B": history-search-forward')   # Strzałka dół
            readline.parse_and_bind('"\\e[C": forward-char')             # Strzałka prawo
            readline.parse_and_bind('"\\e[D": backward-char')            # Strzałka lewo
            
            print("⌨️ Skróty klawiszowe skonfigurowane (↑↓ dla historii)")
            
        except Exception as e:
            print(f"⚠️ Nie można skonfigurować historii: {e}")
            self.history_file = None
    
    def save_history(self):
        """Zapisuje historię komend do pliku"""
        if not READLINE_AVAILABLE or not self.history_file:
            return
        try:
            readline.write_history_file(self.history_file)
            print(f"💾 Historia zapisana w {self.history_file}")
        except Exception as e:
            print(f"⚠️ Nie można zapisać historii: {e}")
    
    def add_to_history(self, command):
        """Dodaje komendę do historii (jeśli nie jest pusta lub duplikatem)"""
        if not READLINE_AVAILABLE:
            return
        if command.strip() and (
            readline.get_current_history_length() == 0 or 
            command != readline.get_history_item(readline.get_current_history_length())
        ):
            readline.add_history(command)
        
    def connect(self):
        """Nawiązuje połączenie z talerzem obrotowym"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            time.sleep(2)  # Czas na inicjalizację
            print(f"✅ Połączono z {self.port} na {self.baudrate} baud")
            return True
        except serial.SerialException as e:
            print(f"❌ Błąd połączenia: {e}")
            return False
    
    def disconnect(self):
        """Zamyka połączenie"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("🔌 Rozłączono")
    
    def flush_input(self):
        """Opróżnia bufor wejściowy"""
        if self.ser and self.ser.is_open:
            self.ser.flushInput()
    
    def send_gcode(self, command):
        """
        Wysyła komendę G-code do talerza
        
        Args:
            command: Komenda G-code jako string
        """
        if not self.ser or not self.ser.is_open:
            print("❌ Brak połączenia!")
            return False
        
        try:
            # Opróżnij bufor wejściowy przed wysłaniem nowej komendy
            self.flush_input()
            
            # Dodaj znak końca linii jeśli nie ma
            if not command.endswith('\n'):
                command += '\n'
            
            # Wyślij komendę
            self.ser.write(command.encode('utf-8'))
            print(f"📡 Wysłano: {command.strip()}")
            
            # Czekaj na odpowiedź i odczytaj wszystkie dostępne linie
            time.sleep(0.2)  # Dłuższe oczekiwanie na odpowiedź
            responses = []
            
            # Odczytaj wszystkie dostępne dane
            start_time = time.time()
            while time.time() - start_time < 1.0:  # Maksymalnie 1 sekunda oczekiwania
                if self.ser.in_waiting > 0:
                    try:
                        line = self.ser.readline().decode('utf-8').strip()
                        if line:
                            responses.append(line)
                            print(f"📨 Odpowiedź: {line}")
                    except UnicodeDecodeError:
                        continue
                else:
                    # Jeśli nie ma więcej danych, czekaj krótko i sprawdź ponownie
                    time.sleep(0.05)
                    if self.ser.in_waiting == 0:
                        break
            
            return responses if responses else True
        except Exception as e:
            print(f"❌ Błąd wysyłania: {e}")
            return False

    # GRBL/System commands
    def get_status(self):
        """Pobiera aktualny status urządzenia (GRBL)"""
        print("📊 Sprawdzam status...")
        return self.send_gcode("?")
    
    def get_settings(self):
        """Wyświetla wszystkie ustawienia GRBL"""
        print("⚙️ Pobieranie ustawień...")
        print("(To może zająć chwilę, GRBL wysyła wiele linii...)")
        return self.send_gcode("$$")
    
    def get_parser_state(self):
        """Sprawdza stan parsera G-code"""
        print("🔍 Sprawdzam stan parsera...")
        return self.send_gcode("$G")
    
    def get_build_info(self):
        """Pobiera informacje o firmware"""
        print("ℹ️ Pobieranie informacji o firmware...")
        return self.send_gcode("$I")
    
    def unlock_alarm(self):
        """Odblokowuje alarm (GRBL)"""
        print("🔓 Odblokowuję alarm...")
        return self.send_gcode("$X")
    
    def cycle_start(self):
        """Rozpoczyna cykl (GRBL)"""
        print("▶️ Rozpoczynam cykl...")
        return self.send_gcode("~")
    
    def feed_hold(self):
        """Wstrzymuje ruch (GRBL)"""
        print("⏸️ Wstrzymuję ruch...")
        return self.send_gcode("!")
    
    def soft_reset(self):
        """Wykonuje soft reset (GRBL)"""
        print("🔄 Wykonuję soft reset...")
        return self.send_gcode("\x18")  # Ctrl-X

    # Horus 0.2 specific motor commands
    def enable_motor(self):
        """Włącza silnik (M17)"""
        print("⚡ Włączam silnik...")
        return self.send_gcode("M17")
    
    def disable_motor(self):
        """Wyłącza silnik (M18)"""
        print("🔌 Wyłączam silnik...")
        return self.send_gcode("M18")
    
    def reset_position(self):
        """Resetuje pozycję do zera (G50) - zalecane po M18"""
        print("🏠 Resetuję pozycję do zera...")
        return self.send_gcode("G50")
    
    def set_speed(self, speed):
        """
        Ustawia prędkość kątową w stopniach na sekundę (G1 F)
        
        Args:
            speed: Prędkość w stopniach/sekundę
        """
        print(f"🏃 Ustawiam prędkość na {speed}°/s")
        return self.send_gcode(f"G1 F{speed}")
    
    def rotate_to_absolute_position(self, position):
        """
        Obraca do absolutnej pozycji w stopniach (G1 X)
        
        Args:
            position: Pozycja w stopniach (może być ujemna)
        """
        print(f"🎯 Przechodzę do absolutnej pozycji {position}°")
        return self.send_gcode(f"G1 X{position}")
    
    def home_turntable(self):
        """Przechodzi do pozycji domowej - resetuje i włącza silnik"""
        print("🏠 Przechodzę do pozycji domowej...")
        self.enable_motor()
        time.sleep(0.1)
        return self.reset_position()
    
    def rotate_to_position(self, position, speed=200):
        """
        Obraca talerz do konkretnej pozycji absolutnej
        
        Args:
            position: Pozycja docelowa w stopniach
            speed: Prędkość obrotu w stopniach/sekundę (domyślnie 200)
        """
        print(f"🔄 Ustawiam prędkość {speed}°/s i przechodzę do pozycji {position}°")
        self.set_speed(speed)
        time.sleep(0.1)
        return self.rotate_to_absolute_position(position)
    
    def stop_turntable(self):
        """Zatrzymuje talerz - wyłącza silnik"""
        print("⏹️ Zatrzymuję talerz (wyłączam silnik)...")
        return self.disable_motor()

    def monitor_continuous(self, duration=10):
        """
        Monitoruje odpowiedzi przez określony czas
        
        Args:
            duration: Czas monitorowania w sekundach
        """
        print(f"👁️ Monitorowanie przez {duration} sekund... (Ctrl+C aby przerwać)")
        start_time = time.time()
        
        try:
            while time.time() - start_time < duration:
                if self.ser.in_waiting > 0:
                    try:
                        line = self.ser.readline().decode('utf-8').strip()
                        if line:
                            print(f"[{time.strftime('%H:%M:%S')}] {line}")
                    except UnicodeDecodeError:
                        continue
                time.sleep(0.01)
        except KeyboardInterrupt:
            print("\n⏹️ Monitorowanie przerwane")

    def show_help(self):
        """Wyświetla pomoc z dostępnymi komendami"""
        print("\n" + "="*60)
        print("POMOC - Dostępne komendy Horus 0.2")
        print("="*60)
        print("\n🔧 KONTROLA SILNIKA:")
        print("  enable           - włącz silnik (M17)")
        print("  disable          - wyłącz silnik (M18)")
        print("  reset            - resetuj pozycję do 0° (G50)")
        print("  home             - pozycja domowa (enable + reset)")
        print("  stop             - zatrzymaj silnik (disable)")
        
        print("\n🔄 RUCH I POZYCJONOWANIE:")
        print("  speed X          - ustaw prędkość X°/s (G1 F)")
        print("  abs_pos X        - przejdź do pozycji X° (G1 X)")
        print("  position X       - ustaw prędkość 200°/s i idź do X°")
        
        print("\n📊 INFORMACJE I STATUS:")
        print("  status           - sprawdź status urządzenia (?)")
        print("  settings         - wyświetl wszystkie ustawienia ($$)")
        print("  info             - informacje o firmware ($I)")
        print("  parser           - stan parsera G-code ($G)")
        
        print("\n🛠️ KONTROLA SYSTEMU:")
        print("  unlock           - odblokuj alarmy ($X)")
        print("  reset_ctrl       - soft reset systemu (Ctrl-X)")
        print("  start            - rozpocznij cykl (~)")
        print("  flush            - opróżnij bufor komunikacji")
        
        print("\n🔍 DIAGNOSTYKA:")
        print("  monitor X        - monitoruj odpowiedzi przez X sekund")
        print("  history          - pokaż historię komend")
        print("  clear_history    - wyczyść historię komend")
        print("  help             - wyświetl tę pomoc")
        
        print("\n📝 BEZPOŚREDNIE KOMENDY:")
        print("  [komenda]        - wyślij dowolną komendę G-code/GRBL")
        
        print("\n⌨️ SKRÓTY KLAWISZOWE:")
        print("  ↑ / ↓            - nawigacja po historii komend")
        print("  ← / →            - edycja bieżącej linii")
        print("  Tab              - auto-uzupełnianie (jeśli dostępne)")
        print("  Ctrl+C           - przerwij / wyjdź")
        
        print("\n💡 PRZYKŁADOWA SEKWENCJA:")
        print("  1. enable        # Włącz silnik")
        print("  2. speed 200     # Ustaw prędkość")
        print("  3. abs_pos 90    # Obróć do 90°")
        print("  4. abs_pos -90   # Obróć do -90°")
        print("  5. abs_pos 0     # Wróć do 0°")
        print("  6. disable       # Wyłącz silnik")
        
        print("\n⚠️ WAŻNE UWAGI:")
        print("  • Dodatnie kąty = obrót przeciwny do wskazówek zegara")
        print("  • Prędkość w stopniach/sekundę (nie mm/min)")
        print("  • Pozycje są zawsze absolutne, mogą być ujemne")
        print("  • Zawsze wyłącz silnik po użyciu (disable/stop)")
        print("  • Jeśli silnik długo włączony - może się przegrzać!")
        
        print("\n📁 HISTORIA KOMEND:")
        if READLINE_AVAILABLE and self.history_file:
            print(f"  • Historia zapisywana w: {self.history_file}")
            print("  • Użyj strzałek ↑↓ aby przeglądać poprzednie komendy")
            print("  • Historia zachowywana między sesjami")
        else:
            print("  • Historia komend niedostępna (brak modułu readline)")
            print("  • Zainstaluj readline: pip install readline")
        
        print("\n" + "="*60)
        print("Wpisz 'exit' aby zakończyć")
        print("="*60 + "\n")
    
    def show_command_history(self):
        """Wyświetla historię komend"""
        if not READLINE_AVAILABLE:
            print("❌ Historia komend niedostępna (brak modułu readline)")
            return
            
        print("\n📜 HISTORIA KOMEND:")
        print("-" * 40)
        history_length = readline.get_current_history_length()
        if history_length == 0:
            print("Brak komend w historii")
        else:
            # Pokaż ostatnie 20 komend
            start = max(1, history_length - 19)
            for i in range(start, history_length + 1):
                cmd = readline.get_history_item(i)
                print(f"{i:3d}: {cmd}")
        print("-" * 40 + "\n")
    
    def clear_command_history(self):
        """Czyści historię komend"""
        if not READLINE_AVAILABLE:
            print("❌ Historia komend niedostępna (brak modułu readline)")
            return
            
        readline.clear_history()
        # Usuń także plik historii
        try:
            if self.history_file and os.path.exists(self.history_file):
                os.remove(self.history_file)
            print("✅ Historia komend wyczyszczona")
        except Exception as e:
            print(f"⚠️ Nie można usunąć pliku historii: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Kontroler talerza obrotowego MakerBot Digitizer (Horus 0.2)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady użycia:
  %(prog)s --interactive                    # Tryb interaktywny
  %(prog)s --command "M17"                 # Włącz silnik
  %(prog)s --command "G1 F200"             # Ustaw prędkość 200°/s
  %(prog)s --position 90                   # Przejdź do pozycji 90°
  %(prog)s --command "M18"                 # Wyłącz silnik

Horus 0.2 G-codes:
  M17        - Włącz silnik
  M18        - Wyłącz silnik  
  G50        - Resetuj pozycję do 0°
  G1 F[X]    - Ustaw prędkość X stopni/sekundę
  G1 X[pos]  - Przejdź do pozycji [pos] stopni (może być ujemna)

UWAGA: Zawsze wyłącz silnik po użyciu (M18) aby uniknąć przegrzania!
        """
    )
    parser.add_argument('--port', default='/dev/ttyUSB0', help='Port szeregowy')
    parser.add_argument('--baudrate', type=int, default=115200, help='Prędkość transmisji')
    parser.add_argument('--command', help='Pojedyncza komenda G-code do wysłania')
    parser.add_argument('--position', type=float, help='Przejście do podanej pozycji (stopnie)')
    parser.add_argument('--speed', type=int, default=200, help='Prędkość obrotu (stopnie/s)')
    parser.add_argument('--interactive', action='store_true', help='Tryb interaktywny')
    
    args = parser.parse_args()
    
    # Inicjalizuj kontroler
    controller = MakerBotDigitizerController(args.port, args.baudrate)
    
    if not controller.connect():
        sys.exit(1)
    
    try:
        if args.position is not None:
            controller.rotate_to_position(args.position, args.speed)
        elif args.command:
            controller.send_gcode(args.command)
        elif args.interactive:
            print("🚀 Tryb interaktywny - MakerBot Digitizer (Horus 0.2)")
            print("="*50)
            if READLINE_AVAILABLE:
                print("✅ Historia komend: Użyj strzałek ↑↓ do nawigacji")
            else:
                print("⚠️ Brak historii komend (moduł readline niedostępny)")
            print("💡 Wpisz 'help' aby zobaczyć wszystkie dostępne komendy")
            print("🚪 Wpisz 'exit' aby zakończyć")
            print("="*50 + "\n")
            
            while True:
                try:
                    cmd = input("Horus> ").strip()
                    
                    # Dodaj komendę do historii (jeśli nie jest pusta)
                    if cmd:
                        controller.add_to_history(cmd)
                    
                    if cmd.lower() == 'exit':
                        print("👋 Do widzenia!")
                        break
                    elif cmd.lower() in ['help', 'h', '?']:
                        controller.show_help()
                    elif cmd.lower() == 'test':
                        print("✅ Test działa! Komenda została rozpoznana.")
                    elif cmd.lower() == 'history':
                        controller.show_command_history()
                    elif cmd.lower() == 'clear_history':
                        controller.clear_command_history()
                    elif cmd.lower() == 'enable':
                        controller.enable_motor()
                    elif cmd.lower() == 'disable':
                        controller.disable_motor()
                    elif cmd.lower() == 'reset':
                        controller.reset_position()
                    elif cmd.lower() == 'home':
                        controller.home_turntable()
                    elif cmd.lower().startswith('speed '):
                        try:
                            speed = float(cmd.split()[1])
                            controller.set_speed(speed)
                        except (ValueError, IndexError):
                            print("❌ Błąd: Użycie -> speed <stopnie_na_sekundę>")
                            print("   Przykład: speed 200")
                    elif cmd.lower().startswith('abs_pos '):
                        try:
                            pos = float(cmd.split()[1])
                            controller.rotate_to_absolute_position(pos)
                        except (ValueError, IndexError):
                            print("❌ Błąd: Użycie -> abs_pos <pozycja_w_stopniach>")
                            print("   Przykład: abs_pos 90")
                    elif cmd.lower().startswith('position '):
                        try:
                            pos = float(cmd.split()[1])
                            controller.rotate_to_position(pos)
                        except (ValueError, IndexError):
                            print("❌ Błąd: Użycie -> position <pozycja_w_stopniach>")
                            print("   Przykład: position 90")
                    elif cmd.lower() == 'stop':
                        controller.stop_turntable()
                    elif cmd.lower() == 'status':
                        controller.get_status()
                    elif cmd.lower() == 'settings':
                        controller.get_settings()
                    elif cmd.lower() == 'unlock':
                        controller.unlock_alarm()
                    elif cmd.lower() == 'reset_ctrl':
                        controller.soft_reset()
                    elif cmd.lower() == 'info':
                        controller.get_build_info()
                    elif cmd.lower() == 'parser':
                        controller.get_parser_state()
                    elif cmd.lower() == 'start':
                        controller.cycle_start()
                    elif cmd.lower().startswith('monitor '):
                        try:
                            duration = int(cmd.split()[1])
                            controller.monitor_continuous(duration)
                        except (ValueError, IndexError):
                            print("❌ Błąd: Użycie -> monitor <sekundy>")
                            print("   Przykład: monitor 5")
                    elif cmd.lower() == 'flush':
                        controller.flush_input()
                        print("✅ Bufor opróżniony")
                    elif cmd.strip() == '':
                        continue  # Pusta linia - nic nie rób
                    elif cmd:
                        print(f"📡 Wysyłam raw komendę: '{cmd}'")
                        controller.send_gcode(cmd)
                    else:
                        print("❓ Nieznana komenda. Wpisz 'help' aby zobaczyć dostępne komendy.")
                except KeyboardInterrupt:
                    print("\n👋 Przerwano przez użytkownika (Ctrl+C)")
                    break
                except EOFError:
                    print("\n👋 Koniec wejścia (Ctrl+D) - zakończenie")
                    break
                except Exception as e:
                    print(f"❌ Błąd: {e}")
                    print("💡 Wpisz 'help' aby zobaczyć poprawne komendy")
        else:
            print("❓ Brak komendy. Użyj --help aby zobaczyć opcje.")
    
    finally:
        print("🔌 Zamykam połączenie...")
        controller.disconnect()


if __name__ == "__main__":
    main()
