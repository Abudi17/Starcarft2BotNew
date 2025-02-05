import asyncio
import logging
import socket
import json
import threading
import aiohttp
import random
import sys
import os
import aiohttp.client_exceptions

from sc2.bot_ai import BotAI
from sc2.data import Difficulty, Race
from sc2.main import run_game
from sc2.player import Bot, Computer
from sc2.protocol import ProtocolError
from sc2 import maps
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2

# === Logging-Konfiguration ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# === PersistentClient für die Verbindung zum Java-Agenten ===
class PersistentClient:
    """Stellt eine Verbindung zum Java-Agenten her, sendet den Spielstatus und empfängt Antworten."""
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = None
 
    def start_client(self):
        """Stellt eine Verbindung zum Java-Agenten her."""
        try:
            self.socket = socket.create_connection((self.host, self.port))
            logging.info("Verbindung zum Java-Agenten hergestellt.")
        except Exception as e:
            logging.error(f"Fehler beim Herstellen der Verbindung: {e}")
            self.terminate_game()

    def send_game_state(self, game_state):
        """Sendet den Spielstatus als JSON an den Java-Agenten."""
        if self.socket:
            try:
                message = json.dumps(game_state)
                self.socket.sendall((message + "\n").encode("utf-8"))
                logging.debug("Spielstatus erfolgreich gesendet.")
            except Exception as e:
                logging.error(f"Fehler beim Senden des Spielstatus: {e}")
                self.handle_disconnection()  # Behandlung bei Verbindungsfehler
        else:
            logging.warning("Socket nicht verbunden. Keine Daten gesendet.")
            self.terminate_game()

    def receive_response(self):
        if self.socket:
            try:
                response = self.socket.recv(4096).decode("utf-8").strip()
                parsed_response = json.loads(response)                
                similar_cases = parsed_response.get("similar_cases", {})
                if similar_cases:
                    first_case = next(iter(similar_cases.items()))
                    case_name, details = first_case
                    return case_name, details.get("category"), details.get("similarity")
                else:
                    logging.warning("Keine ähnlichen Fälle in der Antwort.")
                    return None
            except Exception as e:
                logging.error(f"Fehler beim Empfangen der Antwort: {e}")
                return None
        return None

    def handle_disconnection(self):
        """Behandelt die Trennung vom Java-Agenten."""
        logging.error("Verbindung zum Java-Agenten verloren. Spiel wird beendet.")
        self.close_connection()
        self.terminate_game()

    def close_connection(self):
        """Schließt die Verbindung zum Java-Agenten."""
        if self.socket:
            try:
                self.socket.close()
                logging.info("Verbindung zum Java-Agenten geschlossen.")
            except Exception as e:
                logging.error(f"Fehler beim Schließen der Verbindung: {e}")

    def terminate_game(self):
        """Beendet das Spiel."""
        logging.info("Das Spiel wird beendet.")
        # Hier sollte der Code zum Beenden des Spiels eingefügt werden.
        sys.exit(0)
        os._exit(1)

# === Server-Einstellungen und Thread-Start ===
HOST = "127.0.0.1"
PORT = 65432
client = PersistentClient(HOST, PORT)

server_thread = threading.Thread(target=client.start_client, daemon=True)
server_thread.start()

# === Bot: Hauptlogik des Spiels ===
class HauptBot(BotAI):
    def __init__(self, host, port):
        # Hier wird der PersistentClient initialisiert
        self.persistent_client = PersistentClient(host, port)

        # Flags für die einmalige Ausführung und Verzögerung
        self.initial_structure_built = False  # Ob die Grundstruktur gebaut wurde
        self.initial_structure_completed = False  # Ob die Verzögerung abgeschlossen ist
            
    #Ist für die Position der Suche des Gegeners der Angriffstruppen (aktuell Voidrays)
    def random_location_variance(self, location: Point2, variance: float = 30):
        """Generiert eine zufällige Variation für eine gegebene Position."""
        x = location.x + random.uniform(-variance, variance)  # Verwende random.uniform()
        y = location.y + random.uniform(-variance, variance)  # Verwende random.uniform()
        return Point2((x, y))

    # Aktuell funktioniert es, brauche nur mehr Fälle und dann müssen die einzelnen Methoden angepasst werden
    async def on_step(self, iteration: int):
        # Grundstruktur bauen
        if not self.initial_structure_built:
            await self.build_initial_structure()
            asyncio.create_task(self.delay_rest_of_on_step())

        if self.initial_structure_completed:
            # Es wird eine Höhere Iteration gebraucht, damit er nicht 20 Fälle gleichzeitig ausführt und den gebäuden erstmal zeit gibt bis die fertig sind
            if iteration % 125 == 0:
                # Spielstatus sammeln und senden
                game_state = collect_game_state(self, iteration)
                logging.info(f"{json.dumps(game_state, ensure_ascii=False)}")
                client.send_game_state(game_state)

                # Antwort vom Java-Agenten empfangen
                response = client.receive_response()

                if response:
                    case_name, category, similarity = response
                    logging.info(f"Empfangene Kategorien: Name={case_name}, Kategorie={category}, Ähnlichkeit={similarity}")

                    # Aktionen basierend auf der Antwort
                    if category == "build_Nexus":
                        logging.info("Nexus wird gebaut!")
                        await self.build_Nexus()
                    elif (self.supply_cap - self.supply_used) < 5:
                        logging.info("Baue Pylon, da sonst kein weiteres Vorgehen möglich!")
                        await self.build_Pylon()
                    elif category == "build_Pylon":
                        logging.info("Pylon wird gebaut!")
                        await self.build_Pylon()
                    elif category == "build_Gateway":
                        logging.info("Gateway wird gebaut!")
                        await self.build_Gateway()
                    elif category == "build_Assimilator":
                        logging.info("Assimilator wird gebaut!")
                        await self.build_Assimilator()
                    elif category == "build_CyberneticsCore":
                        logging.info("CyberneticsCore wird gebaut!")
                        await self.build_CyberneticsCore()
                    elif category == "build_Stargate":
                        logging.info("Stargate wird gebaut!")
                        await self.build_Stargate()
                    elif category == "build_Forge":
                        logging.info("Forge wird gebaut!")
                        await self.build_Forge()
                    elif category == "deff_PhotonCannon":
                        logging.info("Photonengeschütz wird gebaut!")
                        await self.deff_PhotonCannon()
                    elif category == "troup_Worker":
                        logging.info("Arbeiter werden ausgebildet!")
                        await self.troup_Worker()
                    elif category == "troup_Voidray":
                        logging.info("Voidray wird ausgebildet!")
                        await self.troup_Voidray()
                    elif category == "troup_Sentry":
                        logging.info("Sentry wird ausgebildet!")
                        await self.troup_Sentry()
                    elif category == "deff_Sentry":
                        logging.info("Sentry wird zur Verteidigung eingesetzt!")
                        await self.deff_Sentry()
                    elif category == "attack_Voidray":
                        logging.info("Voidray greift an!")
                        await self.attack_Voidray()
                    elif category == "attack_Sentry":
                        logging.info("Sentry greift an!")
                        await self.attack_Sentry()
                    elif category == "attack_Sentry_Voidray":
                        logging.info("Kombinierter Angriff: Sentry und Voidray!")
                        await self.attack_Sentry_Voidray()
                    else:
                        logging.info(f"Unbekannte Kategorie: {category}")
                else:
                    logging.warning("Keine Kategorien empfangen oder Antwort ist leer.")
    
    async def delay_rest_of_on_step(self):
        try:
            # Überprüfen, ob die Nachricht schon geloggt wurde
            if not hasattr(self, 'log_message_shown'):
                self.log_message_shown = False

            # Log-Nachricht einmalig ausgeben
            if not self.log_message_shown:
                logging.info("Verzögerung gestartet: Warte 40 Sekunden, um die Grundstrucktur zu bauen.")
                self.log_message_shown = True  # Flag setzen, damit die Nachricht nicht erneut ausgegeben wird

            await asyncio.sleep(40)

            # Nach der Verzögerung
            self.initial_structure_built = True
            self.initial_structure_completed = True  # Verzögerung abgeschlossen
        except Exception as e:
            logging.error(f"Fehler während der Verzögerung: {e}")

    # Das hier ist für die Grundstruktur, also damit etwas deff und Gebäude am Spielbeginn vorhanden sind, um Entscheidungen trffen zu können
    ### So wie ich hier verstanden habe geht es darum, mit if statements die Grundstruktur aufzubauen. Dies erfolgt noch nicht über CBR!
    async def build_initial_structure(self):
        """Baut die Grundstruktur für Protoss und sorgt für Ressourcenmanagement."""
        # Überprüfen, ob ein Nexus vorhanden ist. Falls nicht, baue einen neuen Nexus.
        if self.townhalls:  # Sicherstellen, dass wir eine Nexus-Basis haben
            
            nexus = self.townhalls.random  # Wähle einen zufälligen Nexus für die Aktionen

            # 1. Arbeiter trainieren, falls benötigt (Es werden bei der Gundstruktur extra 2 Weniger als Möglich angegeben, da es somit im Verlauf optimal ist)
            optimal_workers = len(self.townhalls) * 19

            if self.workers.amount < optimal_workers and nexus.is_idle and self.can_afford(UnitTypeId.PROBE):
                nexus.train(UnitTypeId.PROBE)

            # 2. Pylon bauen
            if self.structures(UnitTypeId.PYLON).amount < 2 and self.can_afford(UnitTypeId.PYLON):
                pylon_position = nexus.position.towards(self.game_info.map_center, distance=10)
                await self.build(UnitTypeId.PYLON, near=pylon_position)

            # 3. Gateway bauen
            if self.structures(UnitTypeId.PYLON).ready and not self.structures(UnitTypeId.GATEWAY) and self.can_afford(UnitTypeId.GATEWAY):
                gateway_position = nexus.position.towards(self.game_info.map_center, distance=12)
                await self.build(UnitTypeId.GATEWAY, near=gateway_position)

            # 4. Assimilator bauen
            if self.structures(UnitTypeId.PYLON).ready and self.structures(UnitTypeId.GATEWAY).ready:
                assimilators_built = self.structures(UnitTypeId.ASSIMILATOR).amount + self.already_pending(UnitTypeId.ASSIMILATOR)
    
                # Baue genau zwei Assimilatoren
                if assimilators_built < 2:
                    for vespene in self.vespene_geyser.closer_than(15, nexus):
                        if not self.structures(UnitTypeId.ASSIMILATOR).closer_than(1, vespene) and not self.already_pending(UnitTypeId.ASSIMILATOR):
                            if self.can_afford(UnitTypeId.ASSIMILATOR):
                                await self.build(UnitTypeId.ASSIMILATOR, near=vespene)

            # 4.1 Gas abbauen (Arbeiter zu fertigen Assimilatoren schicken)
            if self.structures(UnitTypeId.ASSIMILATOR).ready.amount == 2:  # Sicherstellen, dass zwei Assimilatoren bereit sind
                for assimilator in self.structures(UnitTypeId.ASSIMILATOR).ready:
                    # Berechne, wie viele Arbeiter noch benötigt werden
                    needed_harvesters = 3
                    if needed_harvesters > 0:
                    # Hole so viele Arbeiter wie benötigt, entweder von idle oder anderen Quellen
                        idle_workers = self.workers.idle
                        if idle_workers:
                            for _ in range(needed_harvesters):
                                if idle_workers.exists:  # Sicherstellen, dass noch freie Arbeiter verfügbar sind
                                    idle_workers.random.gather(assimilator)

            # 5. Cybernetics Core bauen
            if self.structures(UnitTypeId.GATEWAY).ready and not self.structures(UnitTypeId.CYBERNETICSCORE) and self.can_afford(UnitTypeId.CYBERNETICSCORE):
                core_position = nexus.position.towards(self.game_info.map_center, distance=10)
                await self.build(UnitTypeId.CYBERNETICSCORE, near=core_position)

            # 6. Stargate bauen
            if self.structures(UnitTypeId.CYBERNETICSCORE).ready and not self.structures(UnitTypeId.STARGATE) and self.can_afford(UnitTypeId.STARGATE):
                stargate_position = nexus.position.towards(self.game_info.map_center, distance=15)
                await self.build(UnitTypeId.STARGATE, near=stargate_position)

            # 7. Photon Cannons bauen
            if self.structures(UnitTypeId.FORGE).ready:
                cannon_count = self.structures(UnitTypeId.PHOTONCANNON).amount
                while cannon_count < 4 and self.can_afford(UnitTypeId.PHOTONCANNON):
                    cannon_position = await self.find_placement(
                        UnitTypeId.PHOTONCANNON,
                        near=nexus.position,
                        max_distance=15,
                        random_alternative=True
                    )
                    if cannon_position:
                        await self.build(UnitTypeId.PHOTONCANNON, near=cannon_position)
                        cannon_count += 1
                    else:
                        break

            # 8. Forge bauen, falls noch nicht vorhanden
            if not self.structures(UnitTypeId.FORGE) and self.can_afford(UnitTypeId.FORGE):
                forge_position = nexus.position.towards(self.game_info.map_center, distance=8)
                await self.build(UnitTypeId.FORGE, near=forge_position) 
        
##### Build Methoden:
    async def build_Nexus(self):
        print("Wenn das Fall Baue Nexus, dann soll er hier rein.")
        if not self.townhalls:
            # Wähle den besten Startort für einen neuen Nexus
            expansion_location = await self.get_next_expansion()
            if expansion_location and self.can_afford(UnitTypeId.NEXUS):
                await self.build(UnitTypeId.NEXUS, near=expansion_location)
    
    async def build_Pylon(self):
        print("Wenn das Fall Baue Pylon, dann soll er hier rein.")
        if self.townhalls:  # Sicherstellen, dass wir eine Nexus-Basis haben
            nexus = self.townhalls.random
            
            if self.can_afford(UnitTypeId.PYLON):
                pylon_position = nexus.position.towards(self.game_info.map_center, distance=8)
                await self.build(UnitTypeId.PYLON, near=pylon_position)

    async def build_Gateway(self):
        print("Wenn das Fall Baue Gateway, dann soll er hier rein.")
        if self.townhalls:  # Sicherstellen, dass wir eine Nexus-Basis haben
            nexus = self.townhalls.random

            if self.structures(UnitTypeId.PYLON).ready and not self.structures(UnitTypeId.GATEWAY) and self.can_afford(UnitTypeId.GATEWAY):
                gateway_position = nexus.position.towards(self.game_info.map_center, distance=12)
                await self.build(UnitTypeId.GATEWAY, near=gateway_position)

    async def build_Assimilator(self):
        print("Wenn das Fall Baue Assimilator für Gas, dann soll er hier rein.")
        if self.townhalls:  # Sicherstellen, dass wir eine Nexus-Basis haben
            nexus = self.townhalls.random
        
            if self.structures(UnitTypeId.PYLON).ready and self.structures(UnitTypeId.GATEWAY).ready:
                    for vespene in self.vespene_geyser.closer_than(15, nexus):
                        # Überprüfen, ob der Geysir bereits genutzt wird
                        if not self.structures(UnitTypeId.ASSIMILATOR).closer_than(1, vespene) and not self.already_pending(UnitTypeId.ASSIMILATOR):
                            if self.can_afford(UnitTypeId.ASSIMILATOR):
                                await self.build(UnitTypeId.ASSIMILATOR, near=vespene)

    async def build_CyberneticsCore(self):
        print("Wenn das Fall Baue CyberneticsCore, dann soll er hier rein.")
        if self.townhalls:  # Sicherstellen, dass wir eine Nexus-Basis haben
            nexus = self.townhalls.random

            if self.structures(UnitTypeId.GATEWAY).ready and not self.structures(UnitTypeId.CYBERNETICSCORE) and self.can_afford(UnitTypeId.CYBERNETICSCORE):
                core_position = nexus.position.towards(self.game_info.map_center, distance=10)
                await self.build(UnitTypeId.CYBERNETICSCORE, near=core_position)

    async def build_Stargate(self):
        print("Wenn das Fall Baue Stargate, dann soll er hier rein.")
        if self.townhalls:  # Sicherstellen, dass wir eine Nexus-Basis haben
            nexus = self.townhalls.random

            if self.structures(UnitTypeId.CYBERNETICSCORE).ready and not self.structures(UnitTypeId.STARGATE) and self.can_afford(UnitTypeId.STARGATE):
                stargate_position = nexus.position.towards(self.game_info.map_center, distance=15)
                await self.build(UnitTypeId.STARGATE, near=stargate_position)

    async def build_Forge(self):
        print("Wenn das Fall Baue Forge, dann soll er hier rein.")
        if self.townhalls:  # Sicherstellen, dass wir eine Nexus-Basis haben
            nexus = self.townhalls.random

            if self.structures(UnitTypeId.FORGE).amount < 4 and self.can_afford(UnitTypeId.FORGE):
                forge_position = nexus.position.towards(self.game_info.map_center, distance=8)
                await self.build(UnitTypeId.FORGE, near=forge_position)

##### Troup Methoden:
    # Arbeiter
    async def troup_Worker(self):
        print("Wenn das hier kommt, dann werden Arbeiter ausgebildet.")
        # Arbeiter trainieren, wenn genug Ressourcen vorhanden sind
        if self.can_afford(UnitTypeId.PROBE) and self.units(UnitTypeId.PROBE).amount < 100:
            logging.debug("Arbeiter wird trainiert.")
            for sg in self.structures(UnitTypeId.NEXUS).ready.idle:
                sg.train(UnitTypeId.PROBE)

    # Lufttuppen
    async def troup_Voidray(self):
        print("Wenn das Fall Baue Voidray (Phasengleiter), dann soll er hier rein.")
        # **Voidrays trainieren, wenn genug Ressourcen vorhanden sind**
        if self.can_afford(UnitTypeId.VOIDRAY) and self.units(UnitTypeId.VOIDRAY).amount < 10:
            logging.debug("Voidray wird trainiert.")
            for sg in self.structures(UnitTypeId.STARGATE).ready.idle:
                sg.train(UnitTypeId.VOIDRAY)

    # Bodentruppen 
    async def troup_Sentry(self):
        print("Wenn das Fall Baue Protector, dann soll er hier rein.")
        # **Protektor trainieren, wenn genug Ressourcen vorhanden sind**
        if self.can_afford(UnitTypeId.SENTRY) and self.units(UnitTypeId.SENTRY).amount < 10:
            logging.debug("ProteKtor wird trainiert.")
            for sg in self.structures(UnitTypeId.GATEWAY).ready.idle:
                sg.train(UnitTypeId.SENTRY)

##### Defense Methoden:
    async def deff_PhotonCannon(self):
        print("Wenn das Fall Baue Photonenkanone, dann soll er hier rein.")
        if self.townhalls:  # Sicherstellen, dass wir eine Nexus-Basis haben
            nexus = self.townhalls.random   
            # Photon Cannons bauen
            if self.structures(UnitTypeId.FORGE).ready:
                cannon_count = self.structures(UnitTypeId.PHOTONCANNON).amount
                while cannon_count < 1 and self.can_afford(UnitTypeId.PHOTONCANNON):
                    cannon_position = await self.find_placement(UnitTypeId.PHOTONCANNON,
                        near=nexus.position, max_distance=15,
                        random_alternative=True)
                    if cannon_position:
                        await self.build(UnitTypeId.PHOTONCANNON, near=cannon_position)
                        cannon_count += 1
                    else:
                        break

    #Hier muss ich dann nochmal schauen, ob ich welche ausbilden muss oder ob ich dann die wenn von oeben nehmen kann
    async def deff_Sentry(self):
        print("wenn das der Fall ist werden Sentry zur Verteidigung in der Basis abgestellt")      
        # Sentry ausbilden und in der Basis abstellen
        if self.can_afford(UnitTypeId.SENTRY) and self.units(UnitTypeId.SENTRY).amount <= 3:
            logging.debug("ProteKtor wird trainiert.")
            for sg in self.structures(UnitTypeId.GATEWAY).ready.idle:
                sg.train(UnitTypeId.SENTRY)
                sg.position.towards(self.game_info.map_center, distance=15)

##### Attack Methoden:
    async def attack_Voidray(self):
        print("Wenn das Fall greifen Voidrays den Gegner an, dann soll er hier rein.")
        """Steuert Voidrays für Angriffe oder Erkundung."""
        voidrays = self.units(UnitTypeId.VOIDRAY).idle
        if voidrays.amount > 3:
            logging.debug("Voidrays agieren!")
            for vr in voidrays:
                enemy_units = self.enemy_units | self.enemy_structures
                if enemy_units:
                    target = enemy_units.closest_to(vr)
                    vr.attack(target)
                else:
                    # Kein Gegner in Sicht - Karte erkunden
                    explore_point = self.random_location_variance(self.enemy_start_locations[0])
                    vr.attack(explore_point)

    async def attack_Sentry(self):
        print("Wenn das Fall greifen Protektor den Gegner an, dann soll er hier rein.")    
        """Steuert Protektor für Angriffe oder Erkundung."""
        sentry = self.units(UnitTypeId.SENTRY).idle
        if sentry.amount > 3:
            logging.debug("Protektor agieren!")
            for st in sentry:
                enemy_units = self.enemy_units | self.enemy_structures
                if enemy_units:
                    target = enemy_units.closest_to(st)
                    st.attack(target)
                else:
                    # Kein Gegner in Sicht - Karte erkunden
                    explore_point = self.random_location_variance(self.enemy_start_locations[0])
                    st.attack(explore_point)

    async def attack_Sentry_Voidray(self):
        sentry = self.units(UnitTypeId.SENTRY).idle
        voidray = self.units(UnitTypeId.VOIDRAY).idle
        if sentry.amount > 3 & voidray.amount > 3:
            logging.debug("Protektor und Voidray agieren gemeinsam!")
            
            for st, vr in sentry, voidray:
                enemy_units = self.enemy_units | self.enemy_structures
                if enemy_units:
                    target = enemy_units.closest_to(st)
                    st.attack(target)
                    vr.attack(target)
                else:
                    # Kein Gegner in Sicht - Karte erkunden
                    explore_point = self.random_location_variance(self.enemy_start_locations[0])
                    st.attack(explore_point)
                    vr.attack(explore_point)

#####################################################################
    # Das hier kann ich wenn lassen als Angriffslog
    async def manage_voidrays(self):
        """Steuert Voidrays für Angriffe oder Erkundung."""
        voidrays = self.units(UnitTypeId.VOIDRAY).idle
        if voidrays.amount > 3:
            logging.debug("Voidrays agieren!")
            for vr in voidrays:
                enemy_units = self.enemy_units | self.enemy_structures
                if enemy_units:
                    target = enemy_units.closest_to(vr)
                    vr.attack(target)
                else:
                    # Kein Gegner in Sicht - Karte erkunden
                    explore_point = self.random_location_variance(self.enemy_start_locations[0])
                    vr.attack(explore_point)

    # Muss ich gucken, ob ich das noch brauche bzw. wie ich das verwenden kann. Sucht einen geeigneten Platz zum bauen von Gebäuden
    # Wird aktuell nicht verwendet
    async def find_location(self, unit_type, near):
        """Findet einen geeigneten Bauort für das Gebäude und Truppen."""
        placement = await self.find_placement(unit_type, near=near)
        # Wenn Platz gefunden wurde, prüfen, ob er sinnvoll ist
        return placement if placement else None

# === Hilfsfunktionen ===
def collect_game_state(bot, iteration):
    return {
        "iteration": iteration,
        "workers": bot.workers.amount,
        "idleWorkers": bot.workers.idle.amount,
        "minerals": bot.minerals,
        "gas": bot.vespene,
        "pylons": bot.structures(UnitTypeId.PYLON).amount,
        "nexus": bot.structures(UnitTypeId.NEXUS).amount,
        "gateways": bot.structures(UnitTypeId.GATEWAY).amount,
        "cyberneticsCores": bot.structures(UnitTypeId.CYBERNETICSCORE).amount,
        "stargates": bot.structures(UnitTypeId.STARGATE).amount,
        "voidrays": bot.units(UnitTypeId.VOIDRAY).amount,
        "photonCannons": bot.structures(UnitTypeId.PHOTONCANNON).amount,
        "supplyUsed": bot.supply_used,
        "supplyCap": bot.supply_cap,
        "forge": bot.structures(UnitTypeId.FORGE).amount,
        "sentry": bot.structures(UnitTypeId.SENTRY).amount
    }

# === Spiel starten ===
try: 
    run_game(
    maps.get("AcropolisLE"),
    [Bot(Race.Protoss, HauptBot(HOST, PORT)), 
    Computer(Race.Terran, Difficulty.Easy)],
    realtime=True
)
except aiohttp.client_exceptions.ClientConnectionError:
    print("Verbindung wurde geschlossen, vermutlich Spielabbruch.")
except ProtocolError as e:
    print(f"Protokollfehler: {e}")
except Exception as e:
    print(f"Unerwarteter Fehler: {e}")
