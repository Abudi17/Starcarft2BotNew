import socket
import json

# Server Einstellungen
HOST = '127.0.0.1'  # localhost
PORT = 65432        # Port zum Lauschen

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f'Server läuft auf {HOST}:{PORT}')
        conn, addr = s.accept()
        with conn:
            print('Verbunden mit', addr)
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                print('Empfangen:', data)
                json_data = json.loads(data.decode())
                print('JSON:', json_data)
                
                # Beispiel-Antwort
                response = json.dumps({"status": "ok"})
                conn.sendall(response.encode())

if __name__ == "__main__":
    start_server()