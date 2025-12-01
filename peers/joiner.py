import socket
import threading
import time
import queue

from protocol import reliability, pokemon_db
from protocol.messages import *
from protocol.reliability import ReliableChannel
from protocol.battle_state import Move, BattleState, calculate_damage, apply_damage


class joiner:
    # attributes
    def __init__(self, pokemon):
        self.pokemon = pokemon
        self.opp_mon = None
        self.db = (
            pokemon_db.load_pokemon_db()
        )  # Adding a local db for looking up Pokemons
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
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
        self.sock.bind(("", 0))

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

        while self.running:
            self.chat()

        self.sock.close()

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
                        print(
                            f"[Joiner] Opponent chose {self.opp_mon.name} (HP {self.opp_mon.current_hp})"
                        )
                    else:
                        print(
                            f"[Joiner] Received BATTLE_SETUP with unknown Pokémon: {pname}"
                        )

            # 1) Host attack announce
            if kv.get("message_type") == "ATTACK_ANNOUNCE":
                attacker_name = kv.get("attacker_name", "")
                defender_name = kv.get("defender_name", "")
                move_name = kv.get("move_name", "")

                print(
                    f"[JOINER] Received ATTACK_ANNOUNCE: {attacker_name} uses {move_name} on {defender_name}"
                )

                # Mapping names to the local Pokémon objects:
                attacker = self.opp_mon
                defender = self.pokemon

                if attacker is None or defender is None:
                    print(
                        "[JOINER] Battle not set up correctly (missing attacker/defender)."
                    )
                else:
                    move = Move(  # Just for test purpose now. Category should come from CSV
                        name=move_name,
                        base_power=1,
                        category="special",
                        move_type=attacker.type1.lower(),
                    )

                    state = BattleState(attacker=attacker, defender=defender)
                    print(
                        f"[JOINER] Before attack: {defender.name} HP = {defender.current_hp}"
                    )
                    damage = calculate_damage(state, move)
                    apply_damage(state, damage)
                    print(f"[JOINER] Calculated damage: {damage}")
                    print(
                        f"[JOINER] After attack: {defender.name} HP = {defender.current_hp}"
                    )

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

            # Handling incoming GAME_OVER message

            if kv.get("message_type") == "GAME_OVER":
                winner = kv.get("winner", "Unknown")
                loser = kv.get("loser", "Unknown")
                print(f"[JOINER] GAME_OVER: {winner} defeated {loser}")

                # Stop loops
                self.running = False
                # Optionally close socket here or let start() handle it
                self.sock.close()
                break

            # Detect and handle multiple message types
            if "seed" in kv:
                self.seed = int(kv["seed"])
            if "sequence_number" in kv:
                incoming_seq = int(kv["sequence_number"])

                if incoming_seq == self.seq + 1:
                    self.seq += 1
                ackmsg = encode_message({"message_type": "ACK", "ack_number": self.seq})
                self.sock.sendto(ackmsg.encode("utf-8"), self.host_addr)
            if "ack_number" in kv:
                self.ack = int(kv["ack_number"])

    # chat function for CHAT_MESSAGE
    def handshake(self, host_ip, host_port):
        self.host_addr = (host_ip, host_port)
        handshake = encode_message({"message_type": "HANDSHAKE_REQUEST"})
        self.sock.sendto(handshake.encode("utf-8"), self.host_addr)

    # send battle setup message to host
    def send_battle_setup(self):
        msg = {
            "message_type": "BATTLE_SETUP",
            "pokemon_name": self.pokemon.name,
        }
        print(f"[Joiner] Sending BATTLE_SETUP: {msg}")
        self.reliability.send_with_ack(msg, self.host_addr)

    def chat(self):
        chatmsg = input("Type a message:\n")
        send = {
            "message_type": "CHAT_MESSAGE",
            "sender_name": self.name,
            "content_type": "TEXT",
            "message_text": chatmsg,
        }

        self.reliability.send_with_ack(send, self.host_addr)
