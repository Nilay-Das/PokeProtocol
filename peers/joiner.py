import socket
import threading
import time
import queue

from protocol import reliability, pokemon_db
from protocol.messages import *
from protocol.reliability import ReliableChannel
from protocol.battle_state import Move, BattleState, calculate_damage, apply_damage



class joiner:
    #attributes
    def __init__(self, pokemon, db, comm_mode):
        self.pokemon = pokemon
        self.opp_mon = None
        self.db = db
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # adding broadcast capabilities to udp socket
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.comm_mode = comm_mode
        self.name = ""
        self.ack_queue = queue.Queue()
        self.running = False
        self.host_addr = None
        self.kv_messages = []
        self.lock = threading.Lock()
        self.seed = None
        self.seq = 1
        self.ack = None
        self.reliability = ReliableChannel(self.sock, self.ack_queue)

    def start(self, host_ip, host_port):
        # bind local ephemeral port
        if self.comm_mode == 1:
            self.sock.bind(("", 0))
        else:
            self.sock.bind(("0.0.0.0",host_port))

        self.name = input("Name this Peer\n")

        self.running = True
        t = threading.Thread(target=self.listen_loop, daemon=True)
        t.start()

        # Send handshake request
        self.handshake(host_ip, host_port)

        print("[Joiner] Handshake sent. Waiting for Host...")
        print("If host has not sent seed please Ctrl+C to end program")

        while self.seed is None:
            time.sleep(0.5)
        
        # Send battle setup message
        self.send_battle_setup()

        while True:
            self.chat()

    # main listener loop to handle differenet messages
    # pushes message to reliability layer via a queue
    # to get rid of multiple recvfroms populating socket
    def listen_loop(self):
        while self.running:
            try:
                msg, addr = self.sock.recvfrom(1024)
            except OSError:
                break

            decoded = msg.decode()

            kv = decode_message(decoded)

            if kv.get("message_type") != "ACK":
                print(f"\n{decoded}")

            self.ack_queue.put(kv)
            # Store message
            with self.lock:
                self.kv_messages.append(kv)

            # Handle BATTLE_SETUP from host
            if kv.get("message_type") == "BATTLE_SETUP":
                pname = kv.get("pokemon_name")
                if pname:
                    self.opp_mon = self.db.get(pname.lower())
                    if self.opp_mon:
                        print(f"[Joiner] Opponent chose {self.opp_mon.name} (HP {self.opp_mon.current_hp})")
                    else:
                        print(f"[Joiner] Received BATTLE_SETUP with unknown Pokémon: {pname}")
        
            # 1) Host attack announce
            if kv.get("message_type") == "ATTACK_ANNOUNCE":
                attacker_name = kv.get("attacker_name", "")
                defender_name = kv.get("defender_name", "")
                move_name = kv.get("move_name", "")

                print(f"[JOINER] Received ATTACK_ANNOUNCE: {attacker_name} uses {move_name} on {defender_name}")

                # Mapping names to the local Pokémon objects:
                attacker = self.opp_mon
                defender = self.pokemon

                if attacker is None or defender is None:
                    print("[JOINER] Battle not set up correctly (missing attacker/defender).")
                else:
                    move = Move( #Just for test purpose now. Category should come from CSV
                        name=move_name,
                        base_power=1,
                        category="special",
                        move_type=attacker.type1.lower(),
                    )

                    state = BattleState(attacker=attacker, defender=defender)
                    print(f"[JOINER] Before attack: {defender.name} HP = {defender.current_hp}")
                    damage = calculate_damage(state, move)
                    apply_damage(state, damage)
                    print(f"[JOINER] Calculated damage: {damage}")
                    print(f"[JOINER] After attack: {defender.name} HP = {defender.current_hp}")

                    report = {
                        "message_type": "CALCULATION_REPORT",
                        "attacker_name": attacker.name,
                        "defender_name": defender.name,
                        "move_name": move.name,
                        "damage_dealt": str(damage),
                        "defender_hp_remaining": str(defender.current_hp),
                    }
                    # Sending CALCULATION_REPORT to the host
                    encoded_report = encode_message(report).encode("utf-8")
                    self.sock.sendto(encoded_report, self.host_addr)
                    print("[JOINER] Sent CALCULATION_REPORT")



            # Detect and handle multiple message types
            if "seed" in kv:
                self.seed = int(kv["seed"])
            if "sequence_number" in kv:
                incoming_seq = int(kv["sequence_number"])

                if incoming_seq == self.seq + 1:
                    self.seq += 1
                ackmsg = encode_message({
                    "message_type": "ACK",
                    "ack_number": self.seq
                })
                self.sock.sendto(ackmsg.encode("utf-8"), self.host_addr)
            if "ack_number" in kv:
                self.ack = int(kv["ack_number"])

    # chat function for CHAT_MESSAGE
    def handshake(self, host_ip, host_port):
        self.host_addr = (host_ip, host_port)
        handshake = encode_message({"message_type":"HANDSHAKE_REQUEST"})
        self.sock.sendto(handshake.encode("utf-8"), self.host_addr)
    
    # send battle setup message to host
    def send_battle_setup(self):
        msg = {
            "message_type": "BATTLE_SETUP",
            "communication_mode": self.comm_mode,
            "pokemon_name": self.pokemon.name,
            "stat_boosts": { "special_attack_uses": 5, "special_defense_uses": 5 }
        }
        print(f"[Joiner] Sending BATTLE_SETUP: {msg}")
        self.reliability.send_with_ack(msg, self.host_addr)


    def chat(self):
        msg = input("Commands:\n!attack to attack\n!chat for text message\n!sticker for sticker message\n!defend to defend\n!resolve for resolution request\n")

        if msg.strip() == "!attack":
            # Show available moves
            print(f"Your Pokémon: {self.pokemon.name}")
            if not self.pokemon.moves:
                print("No moves available, sending a basic attack.")
                move_name = "BasicMove"
            else:
                print("Available moves:")
                for i, m in enumerate(self.pokemon.moves, start=1):
                    print(f"{i}. {m}")
                choice = input("Choose a move number: ")
                try:
                    idx = int(choice) - 1
                    move_name = self.pokemon.moves[idx]
                except Exception:
                    print("Invalid choice, using first move.")
                    move_name = self.pokemon.moves[0]

            attack_msg = {
                "message_type": "ATTACK_ANNOUNCE",
                "attacker_name": self.pokemon.name,
                "defender_name": self.opp_mon.name if self.opp_mon else "",
                "move_name": move_name,
            }
            print(f"[HOST] Sending ATTACK_ANNOUNCE: {attack_msg}")
            # Sending ATTACK_ANNOUNCE to the joiner
            self.reliability.send_with_ack(attack_msg, self.host_addr)
            return

        if msg.strip() == "!chat":
            text = input("Type a message: \n")
            # Normal chat message
            chat_msg = {
                "message_type": "CHAT_MESSAGE",
                "sender_name": self.name,
                "content_type": "TEXT",
                "message_text": text,
            }
            self.reliability.send_with_ack(chat_msg, self.host_addr)

        if msg.strip() == "!sticker":
            stick = input("Input sticker data: \n")
            # Normal chat message
            chat_msg = {
                "message_type": "CHAT_MESSAGE",
                "sender_name": self.name,
                "content_type": "STICKER",
                "sticker_data": stick,
            }
            self.reliability.send_with_ack(chat_msg, self.host_addr)

        if msg.strip() == "!defend":
            print("defender logic here")

        if msg.strip() == "!resolve":
            print("Resolve logic here")


