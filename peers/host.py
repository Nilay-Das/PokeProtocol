import socket
import threading
import queue
import time

from protocol import pokemon_db
from protocol.messages import *
from protocol.reliability import ReliableChannel
from protocol.battle_state import Move, BattleState, calculate_damage, apply_damage


class host:

    def __init__(self, pokemon):
        self.pokemon = pokemon
        self.opp_mon = None
        self.saddr = None
        self.spect = False
        self.jaddr = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.seed = 0
        self.request_queue = queue.Queue()
        self.ack_queue = queue.Queue()
        self.kv_messages = []
        self.lock = threading.Lock()
        self.listening = True
        self.running = False
        self.name = ""
        self.seq = 1
        self.ack = None
        self.reliability = ReliableChannel(self.sock, self.ack_queue)
        # Adding a local db for looking up Pokemons
        self.db = pokemon_db.load_pokemon_db()
        self.battle_setup_done = False

    def accept(self):
        self.name = input("Name this Peer\n")

        print("Enter a port (>5000):")
        port = 5000
        while port <= 5000:
            try:
                port = int(input())
            except:
                print("Invalid number.")
                continue
            if port <= 5000:
                print("Port must be above 5000.")

        self.sock.bind(("", port))
        print(f"{self.name} listening on port {port}")

        self.running = True
        peers = threading.Thread(target=self._accept_loop, daemon=True)
        peers.start()

        while True:
            if not self.request_queue.empty():
                msg, addr = self.request_queue.get()

                print(f"\nPeer at {addr} sent:")
                print(msg)

                choice = input(
                    "Enter Y to accept Peer, enter anything else to ignore"
                ).upper()
                if choice != "Y":
                    print("Peer rejected.")
                    continue

                self.jaddr = addr
                self.running = False  # Stop accepting new peers

                seed = -1
                while seed < 0:
                    try:
                        seed = int(input("Enter seed: "))
                    except:
                        print("Invalid seed.")

                # Send handshake response using KV pairs
                self.seed = seed
                handshake = encode_message(
                    {"message_type": "HANDSHAKE_RESPONSE", "seed": seed}
                )
                self.sock.sendto(handshake.encode("utf-8"), addr)
                print("Handshake sent.\n")

                listener = threading.Thread(target=self.listen_loop, daemon=True)
                listener.start()

                # Chat loop continues while listening
                while self.listening:
                    self.chat()

                self.sock.close()
                peers.join()

    # loop for accepting peers, ends when the game begins
    def _accept_loop(self):
        while self.running:
            try:
                # Set timeout so we can check self.running periodically
                self.sock.settimeout(0.5)
                msg, addr = self.sock.recvfrom(1024)
                self.sock.settimeout(None)  # Remove timeout
            except socket.timeout:
                # Timeout occurred, check if we should continue
                continue
            except OSError:
                break

            decoded = msg.decode()
            kv = decode_message(decoded)

            # Only process handshake requests in accept loop
            # Let other messages be handled by listen_loop
            if kv.get("message_type") == "HANDSHAKE_REQUEST":
                self.request_queue.put((decoded, addr))

    # main listener loop to handle differenet messages
    # pushes message to reliability layer via a queue
    # to get rid of multiple recvfroms populating socket
    def listen_loop(self):
        while self.listening:
            try:
                msg, addr = self.sock.recvfrom(1024)
            except OSError:
                break

            decoded = msg.decode()

            # if there is a spectator, sends message to it
            if self.spect is True:
                self.reliability.send_with_ack(msg, self.saddr)
            kv = decode_message(decoded)

            if kv.get("message_type") != "ACK":
                print(f"\n{decoded}")

            self.ack_queue.put(kv)
            # Store message
            with self.lock:
                self.kv_messages.append(kv)

            # Handle BATTLE_SETUP from joiner
            if kv.get("message_type") == "BATTLE_SETUP":
                pname = kv.get("pokemon_name")
                if pname:
                    self.opp_mon = self.db.get(pname.lower())
                    if self.opp_mon:
                        print(
                            f"[Host] Opponent chose {self.opp_mon.name} (HP {self.opp_mon.current_hp})"
                        )
                    else:
                        print(
                            f"[Host] Received BATTLE_SETUP with unknown Pokémon: {pname}"
                        )

                # Send BATTLE_SETUP to joiner
                if not self.battle_setup_done and self.jaddr is not None:
                    reply = {
                        "message_type": "BATTLE_SETUP",
                        "pokemon_name": self.pokemon.name,
                    }
                    print(f"[Host] Sending BATTLE_SETUP: {reply}")
                    self.reliability.send_with_ack(reply, self.jaddr)
                    self.battle_setup_done = True

            # Joiner's calculation report for the attack
            if kv.get("message_type") == "CALCULATION_REPORT":
                attacker_name = kv.get("attacker_name", "")
                defender_name = kv.get("defender_name", "")
                move_name = kv.get("move_name", "")
                damage_str = kv.get("damage_dealt", "0")
                hp_str = kv.get("defender_hp_remaining", "0")

                print(f"[HOST] Received CALCULATION_REPORT: {kv}")

                # Our view:
                attacker = self.pokemon
                defender = self.opp_mon

                if attacker is None or defender is None:
                    print(
                        "[HOST] Battle not set up correctly (missing attacker/defender)."
                    )
                else:
                    move = Move(  # Just for test purpose now. Category should come from CSV
                        name=move_name,
                        base_power=1,
                        category="special",
                        move_type=attacker.type1.lower(),
                    )

                    # Recalculate damage locally for double checking
                    state = BattleState(attacker=attacker, defender=defender)
                    local_damage = calculate_damage(state, move)

                    reported_damage = int(damage_str)
                    reported_hp = int(hp_str)

                    print(
                        f"[HOST] Local damage = {local_damage}, reported damage = {reported_damage}"
                    )

                    if local_damage == reported_damage:
                        # Accept and apply damage
                        apply_damage(state, local_damage)
                        print(
                            f"[HOST] Attack confirmed. {defender.name} HP is now {state.defender.current_hp}"
                        )
                        # Keeping the copy in sync
                        defender.current_hp = state.defender.current_hp

                        # Check for game over using reported HP (joiner's Pokemon fainted)
                        if reported_hp <= 0 or defender.current_hp <= 0:
                            print(f"[HOST] {defender.name} fainted!")

                            game_over_msg = {
                                "message_type": "GAME_OVER",
                                "winner": attacker.name,
                                "loser": defender.name,
                            }

                            # Use the host.send() helper so spectators get it too
                            print(f"[HOST] Sending GAME_OVER: {game_over_msg}")
                            self.send(game_over_msg)

                            # Stop battle loops
                            self.running = False
                            self.listening = False

            # Handling incoming GAME_OVER message
            if kv.get("message_type") == "GAME_OVER":
                winner = kv.get("winner", "Unknown")
                loser = kv.get("loser", "Unknown")
                print(f"[HOST] GAME_OVER: {winner} defeated {loser}")

                self.running = False
                self.listening = False
                self.sock.close()
                break

            # Detect and handle multiple message types
            if kv.get("message_type") == "SPECTATOR_REQUEST":
                if self.spect is False:
                    self.saddr = addr
                    response = encode_message({"message_type": "HANDSHAKE_RESPONSE"})
                    self.sock.sendto(response.encode("utf-8"), addr)
                    self.spect = True
                    print("Spectator connected.")
                continue
            if "sequence_number" in kv:
                incoming_seq = int(kv["sequence_number"])

                if incoming_seq == self.seq + 1:
                    self.seq += 1

                # ACK should acknowledge the received sequence number
                # Always send ACK back to the sender (addr)
                ackmsg = encode_message(
                    {"message_type": "ACK", "ack_number": incoming_seq}
                )
                print(f"[HOST] Sending ACK {incoming_seq} to {addr}")
                self.sock.sendto(ackmsg.encode("utf-8"), addr)

            if "ack_number" in kv:
                self.ack = int(kv["ack_number"])

    # Helper function to build a move from a name
    def _build_move_from_name(self, move_name: str) -> Move:
        return Move(  # Just for test purpose now. Category should come from CSV
            name=move_name,
            base_power=1,
            category="special",
            move_type=self.pokemon.type1.lower(),
        )

    # Chat function for CHAT_MESSAGE
    def chat(self):
        msg = input("Type a message (or !attack to attack):\n")

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
            self.reliability.send_with_ack(attack_msg, self.jaddr)
            return

        # Normal chat message
        chat_msg = {
            "message_type": "CHAT_MESSAGE",
            "sender_name": self.name,
            "content_type": "TEXT",
            "message_text": msg,
        }
        self.send(chat_msg)

    # host specific function to send data, just checks if there is a spectator
    # and sends the message to it as well
    def send(self, msg):
        self.reliability.send_with_ack(msg, self.jaddr)

        if self.spect is True:
            self.reliability.send_with_ack(msg, self.saddr)
