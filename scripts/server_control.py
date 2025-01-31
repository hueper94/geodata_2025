import os
import signal
import subprocess

def stop_server():
    try:
        # Finde alle Python-Prozesse, die app.py ausführen
        result = subprocess.run(['pgrep', '-f', 'python app.py'], 
                              capture_output=True, 
                              text=True)
        
        # Hole die PIDs
        pids = result.stdout.strip().split('\n')
        
        # Beende jeden gefundenen Prozess
        for pid in pids:
            if pid:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    print(f"Server-Prozess (PID: {pid}) wurde beendet.")
                except ProcessLookupError:
                    print(f"Prozess {pid} wurde nicht gefunden.")
                except Exception as e:
                    print(f"Fehler beim Beenden von Prozess {pid}: {str(e)}")
        
        print("Alle Server-Prozesse wurden beendet.")
    except Exception as e:
        print(f"Fehler beim Beenden des Servers: {str(e)}")

if __name__ == "__main__":
    stop_server() 