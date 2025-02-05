import socket
import json
import time
import threading

HOST = '127.0.0.1'
PORT = 65432

class PersistentClient:
    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self.sock = None

    def start_client(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        print(f'Verbunden mit Server auf {self.host}:{self.port}')
        
        threading.Thread(target=self.receive_messages, daemon=True).start()

    def send_message(self, message):
        if self.sock:
            request = {
                "message": message,
                "timestamp": int(time.time())
            }
            json_request = json.dumps(request)
            self.sock.sendall((json_request + "\n").encode())

    def send_game_state(self, iteration, workers, idle_workers, minerals, gas, cannons, pylons, nexus, gateways, cybernetics_cores, stargates, voidrays, supply_used, supply_cap):
        if self.sock:
            game_state = {
                "iteration": iteration,
                "workers": workers,
                "idle_workers": idle_workers,
                "minerals": minerals,
                "gas": gas,
                "cannons": cannons,
                "pylons": pylons,
                "nexus": nexus,
                "gateways": gateways,
                "cybernetics_cores": cybernetics_cores,
                "stargates": stargates,
                "voidrays": voidrays,
                "supply": {
                    "used": supply_used,
                    "cap": supply_cap
                }
            }
            json_request = json.dumps(game_state)
            self.sock.sendall((json_request + "\n").encode())        
    
    def receive_messages(self):
        while True:
            data = self.sock.recv(1024)
            if data:
                print('Empfangen:', data.decode())
                json_response = json.loads(data.decode())
                print('JSON Antwort:', json_response)
            else:
                break