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
                self.handle_disconnection() 
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
            
    #Ist für die Position der Suche des Gegeners der Angriffstruppen
    def random_location_variance(self, location: Point2, variance: float = 30):
        """Generiert eine zufällige Variation für eine gegebene Position."""
        x = location.x + random.uniform(-variance, variance)  
        y = location.y + random.uniform(-variance, variance)  
        return Point2((x, y))

    # Aktuell funktioniert es, brauche nur mehr Fälle und dann müssen die einzelnen Methoden angepasst werden
    async def on_step(self, iteration: int):
        # Grundstruktur bauen
        if not self.initial_structure_built:
            await self.build_initial_structure()
            asyncio.create_task(self.delay_rest_of_on_step())

        if self.initial_structure_completed:
            # Es wird eine Höhere Iteration gebraucht, damit er nicht 20 Fälle gleichzeitig ausführt und den gebäuden erstmal zeit gibt bis die fertig sind
            if iteration % 25 == 0:
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
                    elif category == "troup_Worker":
                        logging.info("Arbeiter werden ausgebildet!")
                        await self.troup_Worker()
                    elif category == "troup_Zealot":
                        logging.info("Zealot wird ausgebildet!")
                        await self.troup_Zealot()
                    elif category == "troup_Stalker":
                        logging.info("Stalker wird ausgebildet!")
                        await self.troup_Stalker()
                    elif category == "attack_Zealot":
                        logging.info("Zealot greift an!")
                        await self.attack_Zealot()
                    elif category == "attack_Stalker":
                        logging.info("Stalker greift an!")
                        await self.attack_Stalker()
                    elif category == "attack_Zealot_Stalker":
                        logging.info("Kombinierter Angriff: Zealot und Stalker!")
                        await self.attack_Zealots_Stalker()
                    elif category == "troup_Worker_Assimilator":
                        logging.info("Weise Arbeitern den Assimilatoren zu!")
                        await self.troup_Worker_Assimilator()
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
                logging.info("Verzögerung gestartet: Warte 10 Sekunden, um die Grundstrucktur zu bauen.")
                self.log_message_shown = True  # Flag setzen, damit die Nachricht nicht erneut ausgegeben wird

            # Nach der Verzögerung
            self.initial_structure_built = True
            self.initial_structure_completed = True  # Verzögerung abgeschlossen
        except Exception as e:
            logging.error(f"Fehler während der Verzögerung: {e}")

    # WIRD AKTUELL NICHT VERWENDET: WAR INITIAL DA FÜR DIE GRUNDSTRUKTUR: WURDE IM FINALEN STATUS RAUSGENOMMEN! CODE BLEIBT DENNOCH FÜR ZUKUNFT
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
        print("Baue Nexus.")
        if not self.townhalls:
            # Wähle den besten Startort für einen neuen Nexus
            expansion_location = await self.get_next_expansion()
            if expansion_location and self.can_afford(UnitTypeId.NEXUS):
                await self.build(UnitTypeId.NEXUS, near=expansion_location)
    
    async def build_Pylon(self):
        print("Baue Pylon.")
        if self.townhalls and self.can_afford(UnitTypeId.PYLON):
            nexus = self.townhalls.random
            pylon_position = nexus.position.towards(self.game_info.map_center, distance=8)
            builder = self.workers.idle.random_or(None)
            if builder is None:
                builder = self.workers.gathering.closest_to(nexus) if self.workers.gathering else None

            if builder:
                builder.move(pylon_position)  # Schicke den Arbeiter zur Bauposition
                await self.build(UnitTypeId.PYLON, near=pylon_position)  # Baue Pylon

    async def build_Gateway(self):
        print("Baue Gateway.")
        if self.townhalls and self.structures(UnitTypeId.PYLON).ready and self.can_afford(UnitTypeId.GATEWAY):
            nexus = self.townhalls.random
            gateway_position = nexus.position.towards(self.game_info.map_center, distance=12)

            builder = self.workers.idle.random_or(None)

            if builder is None:
                builder = self.workers.gathering.closest_to(nexus) if self.workers.gathering else None

            if builder:
                builder.move(gateway_position)  # Schicke den Arbeiter zur Bauposition
                await self.build(UnitTypeId.GATEWAY, near=gateway_position)  # Baue Gateway


    async def build_Assimilator(self):
        print("Bause Assimilator.")
        if self.townhalls:  # Sicherstellen, dass wir eine Nexus-Basis haben
            nexus = self.townhalls.random
        
            if self.structures(UnitTypeId.PYLON).ready:
                    for vespene in self.vespene_geyser.closer_than(15, nexus):
                        # Überprüfen, ob der Geysir bereits genutzt wird
                        if not self.structures(UnitTypeId.ASSIMILATOR).closer_than(1, vespene) and not self.already_pending(UnitTypeId.ASSIMILATOR):
                            if self.can_afford(UnitTypeId.ASSIMILATOR):
                                await self.build(UnitTypeId.ASSIMILATOR, near=vespene)

    async def build_CyberneticsCore(self):
        print("Baue CyberneticsCore.")
        if self.townhalls:  # Sicherstellen, dass wir eine Nexus-Basis haben
            nexus = self.townhalls.random

            if self.structures(UnitTypeId.GATEWAY).ready and not self.structures(UnitTypeId.CYBERNETICSCORE) and self.can_afford(UnitTypeId.CYBERNETICSCORE):
                core_position = nexus.position.towards(self.game_info.map_center, distance=10)
                await self.build(UnitTypeId.CYBERNETICSCORE, near=core_position)

##### Troup Methoden:
    # Arbeiter
    async def troup_Worker(self):
        print("Bilde Arbeiter aus.")
        # Arbeiter trainieren, wenn genug Ressourcen vorhanden sind
        if self.can_afford(UnitTypeId.PROBE):
            logging.debug("Arbeiter wird trainiert.")
            for sg in self.structures(UnitTypeId.NEXUS).ready.idle:
                sg.train(UnitTypeId.PROBE)
            

    async def troup_Worker_Assimilator(self):
        print("Weise Arbeiter Assimilator zu.")#
        for assimilator in self.structures(UnitTypeId.ASSIMILATOR).ready:
                needed_harvesters = 3
                current_harvesters = assimilator.assigned_harvesters
                missing_harvesters = needed_harvesters - current_harvesters

                if missing_harvesters > 0:
                            # Zuerst versuchen, freie Arbeiter zuzuweisen
                    idle_workers = self.workers.idle
                    for _ in range(missing_harvesters):
                        if idle_workers.exists:
                            idle_workers.random.gather(assimilator)
                        else:
                            # Wenn keine untätigen Arbeiter verfügbar sind, Arbeiter von Mineralien abziehen
                            mineral_workers = self.workers.gathering
                            if mineral_workers.exists:
                                mineral_workers.random.gather(assimilator)


    # Bodentruppen:

    async def troup_Zealot(self):
        print("bilde Zealots aus.")
        if self.can_afford(UnitTypeId.ZEALOT):
            logging.debug("Zealot wird trainiert.")
            for sg in self.structures(UnitTypeId.GATEWAY).ready.idle:
                sg.train(UnitTypeId.ZEALOT)

        # Alle neuen Zealots zur Rampe schicken
        for zealot in self.units(UnitTypeId.ZEALOT).idle:
            zealot.move(self.main_base_ramp.top_center)

    async def troup_Stalker(self):
        print("bilde Stalker aus.")
        if self.can_afford(UnitTypeId.STALKER):
            logging.debug("Stalker wird trainiert.")
            for sg in self.structures(UnitTypeId.GATEWAY).ready.idle:
                sg.train(UnitTypeId.STALKER)


        # Alle neuen Stalker zur Rampe schicken
        for stalker in self.units(UnitTypeId.STALKER).idle:
            stalker.move(self.main_base_ramp.top_center)
                    
    

##### Attack Methoden:      
    async def attack_Zealot(self):
        print("Zealots zum Angriff.")
        zealots = self.units(UnitTypeId.ZEALOT).idle
        if zealots.amount > 10:
            logging.debug("Zealots Angreifen!")
            for z in zealots:
                enemy_units = self.enemy_units | self.enemy_structures
                if enemy_units:
                    target = enemy_units.closest_to(z)
                    z.attack(target)
                else:
                    explore_point = self.random_location_variance(self.enemy_start_locations[0])
                    z.attack(explore_point)
    
    async def attack_Stalker(self):
        print("Stalker zum Angriff.")
        stalker = self.units(UnitTypeId.STALKER).idle
        if stalker.amount > 10:
            logging.debug("Zealots Angreifen!")
            for s in stalker:
                enemy_units = self.enemy_units | self.enemy_structures
                if enemy_units:
                    target = enemy_units.closest_to(s)
                    s.attack(target)
                else:
                    explore_point = self.random_location_variance(self.enemy_start_locations[0])
                    s.attack(explore_point)
    
    async def attack_Zealots_Stalker(self):
        print("Zealots und Stalker zum Angriff.")
        
        # ALLE Zealots und Stalker in die Angriffswelle aufnehmen
        zealots = self.units(UnitTypeId.ZEALOT)
        stalkers = self.units(UnitTypeId.STALKER)

        logging.debug("Zealots und Stalker greifen an!")

        enemy_units = self.enemy_units | self.enemy_structures

        if enemy_units:
            # Angriff auf den nächsten Gegner
            target = enemy_units.closest_to(zealots.center) if zealots else enemy_units.closest_to(stalkers.center)
            for unit in zealots + stalkers:
                unit.attack(target)
        else:
            # Falls keine Gegner gefunden werden, erkunden
            explore_point = self.random_location_variance(self.enemy_start_locations[0])
            for unit in zealots + stalkers:
                unit.attack(explore_point)

#####################################################################

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
        "supplyUsed": bot.supply_used,
        "supplyCap": bot.supply_cap,
        "assimilator": bot.structures(UnitTypeId.ASSIMILATOR).amount,
        "totalAssimilatorHarvesters": sum(a.assigned_harvesters for a in bot.structures(UnitTypeId.ASSIMILATOR).ready),
        "zealot" : bot.units(UnitTypeId.ZEALOT).amount,
        "stalker" : bot.units(UnitTypeId.STALKER).amount,
        "supplyDifferenceUsedCap" : bot.supply_cap - bot.supply_used,
        "nexusWorker" : sum(nexus.assigned_harvesters for nexus in bot.structures(UnitTypeId.NEXUS).ready),
        "nexusTrainingStatus": int(any(nexus.orders for nexus in bot.structures(UnitTypeId.NEXUS).ready))
    }


# === Spiel starten ===
try: 
    run_game(
    maps.get("AcropolisLE"),
    [Bot(Race.Protoss, HauptBot(HOST, PORT)), 
    Computer(Race.Terran, Difficulty.Easy)],
    realtime=False
)
except aiohttp.client_exceptions.ClientConnectionError:
    print("Verbindung wurde geschlossen, vermutlich Spielabbruch.")
except ProtocolError as e:
    print(f"Protokollfehler: {e}")
except Exception as e:
    print(f"Unerwarteter Fehler: {e}")
