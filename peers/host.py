import socket
import threading
import queue
import time

from protocol import pokemon_db
from protocol.messages import *
from protocol.reliability import ReliableChannel
from protocol.battle_state import (
    Move, BattleState, BattlePhase, 
    calculate_damage, apply_damage, get_damage_category
)


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
        self.seq = 0  # Start at 0 so first message (seq=1) isn't flagged as duplicate
        self.ack = None
        self.reliability = ReliableChannel(self.sock, self.ack_queue)
        # Adding a local db for looking up Pokemons
        self.db = pokemon_db.load_pokemon_db()
        self.battle_setup_done = False
        
        # Turn-based battle state tracking
        self.battle_phase = None  # BattlePhase enum
        self.is_my_turn = True  # Host goes first
        self.pending_move = None  # Current move being processed
        self.my_calculation = None  # Local damage calculation for comparison
        self.pending_attacker = None  # Attacker for current turn
        self.pending_defender = None  # Defender for current turn

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
        
        # IMPORTANT: Reset socket timeout when exiting so listen_loop doesn't inherit it
        try:
            self.sock.settimeout(None)
        except OSError:
            pass  # Socket might already be closed

    # main listener loop to handle differenet messages
    # pushes message to reliability layer via a queue
    # to get rid of multiple recvfroms populating socket
    def listen_loop(self):
        # Ensure no timeout is set (in case _accept_loop left one)
        try:
            self.sock.settimeout(None)
        except OSError:
            return
            
        while self.listening:
            try:
                msg, addr = self.sock.recvfrom(1024)
            except socket.timeout:
                # Timeout shouldn't happen with None timeout, but handle it gracefully
                continue
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
            
            # Handle sequence numbers and ACKs first
            is_duplicate = False
            if "sequence_number" in kv:
                incoming_seq = int(kv["sequence_number"])
                # Always send ACK for the received sequence number
                ackmsg = encode_message(
                    {"message_type": "ACK", "ack_number": incoming_seq}
                )
                self.sock.sendto(ackmsg.encode("utf-8"), addr)
                print(f"[HOST] Sending ACK {incoming_seq} to {addr}")
                
                # Only process if it's a new message (not a duplicate)
                if incoming_seq <= self.seq:
                    # This is a duplicate message, skip processing
                    is_duplicate = True
                    print(f"[HOST] Ignoring duplicate message seq={incoming_seq} (current seq={self.seq})")
                else:
                    # New message, update our sequence counter
                    self.seq = incoming_seq
            
            if is_duplicate:
                continue
            
            # Store message (only non-duplicates)
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
                    self.battle_setup_done = True
                    
                    # Transition to WAITING_FOR_MOVE state
                    self.battle_phase = BattlePhase.WAITING_FOR_MOVE
                    print(f"[HOST] Battle setup complete! Entering {self.battle_phase.value} state.")
                    print("[HOST] It's your turn! Type !attack to make a move.")
                    
                    # Send in a separate thread to avoid blocking listen_loop
                    threading.Thread(target=lambda: self.reliability.send_with_ack(reply, self.jaddr), daemon=True).start()

            # Handle ATTACK_ANNOUNCE - joiner is attacking us
            if kv.get("message_type") == "ATTACK_ANNOUNCE":
                attacker_name = kv.get("attacker_name", "")
                defender_name = kv.get("defender_name", "")
                move_name = kv.get("move_name", "")

                print(f"[HOST] Received ATTACK_ANNOUNCE: {attacker_name} uses {move_name} on {defender_name}")

                # Mapping names to the local Pokémon objects:
                attacker = self.opp_mon  # Joiner's Pokemon is attacking
                defender = self.pokemon  # Host's Pokemon is defending

                if attacker is None or defender is None:
                    print("[HOST] Battle not set up correctly (missing attacker/defender).")
                else:
                    # Store pending move info
                    self.pending_attacker = attacker
                    self.pending_defender = defender
                    
                    # Create the move with damage category based on type
                    move_type = attacker.type1.lower()
                    damage_category = get_damage_category(move_type)
                    self.pending_move = Move(
                        name=move_name,
                        base_power=1,
                        category=damage_category,
                        move_type=move_type,
                    )
                    
                    # Send DEFENSE_ANNOUNCE to confirm receipt
                    defense_msg = {
                        "message_type": "DEFENSE_ANNOUNCE",
                        "defender_name": defender.name,
                        "acknowledged_move": move_name,
                    }
                    print(f"[HOST] Sending DEFENSE_ANNOUNCE: {defense_msg}")
                    
                    # Transition to PROCESSING_TURN
                    self.battle_phase = BattlePhase.PROCESSING_TURN
                    print(f"[HOST] Entering {self.battle_phase.value} state.")
                    
                    # Calculate damage locally (don't apply yet)
                    state = BattleState(attacker=attacker, defender=defender)
                    print(f"[HOST] Before attack: {defender.name} HP = {defender.current_hp}")
                    damage = calculate_damage(state, self.pending_move)
                    
                    # Store calculation for comparison
                    self.my_calculation = {
                        "damage": damage,
                        "remaining_hp": defender.current_hp - damage if defender.current_hp - damage > 0 else 0
                    }
                    print(f"[HOST] Calculated damage: {damage}")
                    
                    # Send CALCULATION_REPORT
                    report = {
                        "message_type": "CALCULATION_REPORT",
                        "attacker_name": attacker.name,
                        "defender_name": defender.name,
                        "move_name": self.pending_move.name,
                        "damage_dealt": str(damage),
                        "defender_hp_remaining": str(self.my_calculation["remaining_hp"]),
                    }
                    print(f"[HOST] Sending CALCULATION_REPORT: {report}")
                    
                    # Send in a separate thread to avoid blocking listen_loop
                    def send_defense_and_report():
                        self.reliability.send_with_ack(defense_msg, self.jaddr)
                        self.reliability.send_with_ack(report, self.jaddr)
                    threading.Thread(target=send_defense_and_report, daemon=True).start()

            # Handle DEFENSE_ANNOUNCE - defender acknowledged the attack
            if kv.get("message_type") == "DEFENSE_ANNOUNCE":
                defender_name = kv.get("defender_name", "")
                acknowledged_move = kv.get("acknowledged_move", "")
                print(f"[HOST] Received DEFENSE_ANNOUNCE: {defender_name} acknowledged {acknowledged_move}")
                
                # Transition to PROCESSING_TURN
                self.battle_phase = BattlePhase.PROCESSING_TURN
                print(f"[HOST] Entering {self.battle_phase.value} state.")
                
                # Calculate damage locally
                if self.pending_attacker and self.pending_defender and self.pending_move:
                    state = BattleState(attacker=self.pending_attacker, defender=self.pending_defender)
                    damage = calculate_damage(state, self.pending_move)
                    remaining_hp = self.pending_defender.current_hp - damage
                    if remaining_hp < 0:
                        remaining_hp = 0
                    
                    # Store calculation for comparison
                    self.my_calculation = {
                        "damage": damage,
                        "remaining_hp": remaining_hp
                    }
                    print(f"[HOST] Calculated damage: {damage}, remaining HP: {remaining_hp}")
                    
                    # Send CALCULATION_REPORT
                    report = {
                        "message_type": "CALCULATION_REPORT",
                        "attacker_name": self.pending_attacker.name,
                        "defender_name": self.pending_defender.name,
                        "move_name": self.pending_move.name,
                        "damage_dealt": str(damage),
                        "defender_hp_remaining": str(remaining_hp),
                    }
                    print(f"[HOST] Sending CALCULATION_REPORT: {report}")
                    # Send in a separate thread to avoid blocking listen_loop
                    threading.Thread(target=lambda: self.reliability.send_with_ack(report, self.jaddr), daemon=True).start()
                else:
                    print("[HOST] Error: No pending move info for calculation")

            # Handle incoming CALCULATION_REPORT
            if kv.get("message_type") == "CALCULATION_REPORT":
                attacker_name = kv.get("attacker_name", "")
                defender_name = kv.get("defender_name", "")
                move_name = kv.get("move_name", "")
                damage_str = kv.get("damage_dealt", "0")
                hp_str = kv.get("defender_hp_remaining", "0")

                print(f"[HOST] Received CALCULATION_REPORT: {kv}")

                reported_damage = int(damage_str)
                reported_hp = int(hp_str)

                # Compare with our local calculation
                if self.my_calculation:
                    local_damage = self.my_calculation["damage"]
                    local_remaining_hp = self.my_calculation["remaining_hp"]

                    print(f"[HOST] Local damage = {local_damage}, reported damage = {reported_damage}")
                    print(f"[HOST] Local remaining HP = {local_remaining_hp}, reported HP = {reported_hp}")

                    if local_damage == reported_damage and local_remaining_hp == reported_hp:
                        # Calculations match - send CALCULATION_CONFIRM
                        confirm_msg = {
                            "message_type": "CALCULATION_CONFIRM",
                            "damage_confirmed": str(local_damage),
                            "remaining_health": str(local_remaining_hp),
                        }
                        print(f"[HOST] Calculations match! Sending CALCULATION_CONFIRM: {confirm_msg}")

                        # Apply damage to the defender
                        if self.pending_defender:
                            self.pending_defender.current_hp = local_remaining_hp
                            print(f"[HOST] Applied damage. {self.pending_defender.name} HP is now {self.pending_defender.current_hp}")

                        # Check for game over
                        if local_remaining_hp <= 0 and self.pending_defender:
                            print(f"[HOST] {self.pending_defender.name} fainted!")

                            game_over_msg = {
                                "message_type": "GAME_OVER",
                                "winner": self.pending_attacker.name if self.pending_attacker else "Unknown",
                                "loser": self.pending_defender.name,
                            }

                            print(f"[HOST] Sending GAME_OVER: {game_over_msg}")
                            # Send in a separate thread to avoid blocking listen_loop
                            def send_confirm_and_game_over():
                                self.reliability.send_with_ack(confirm_msg, self.jaddr)
                                self.send(game_over_msg)
                                self.running = False
                                self.listening = False
                            threading.Thread(target=send_confirm_and_game_over, daemon=True).start()
                        else:
                            # Don't switch turns here - wait for CALCULATION_CONFIRM to be received
                            # Just send the confirm message
                            # Send in a separate thread to avoid blocking listen_loop
                            threading.Thread(target=lambda: self.reliability.send_with_ack(confirm_msg, self.jaddr), daemon=True).start()
                    else:
                        # Calculations don't match - send RESOLUTION_REQUEST
                        resolution_msg = {
                            "message_type": "RESOLUTION_REQUEST",
                            "calculated_damage": str(local_damage),
                            "calculated_remaining_hp": str(local_remaining_hp),
                            "attacker_stat": str(self.pending_attacker.attack if self.pending_move and self.pending_move.category == "physical" else self.pending_attacker.special_attack) if self.pending_attacker else "0",
                            "defender_stat": str(self.pending_defender.physical_defense if self.pending_move and self.pending_move.category == "physical" else self.pending_defender.special_defense) if self.pending_defender else "0",
                            "type_multiplier": str(self.pending_defender.type_multipliers.get(self.pending_move.move_type, 1.0)) if self.pending_defender and self.pending_move else "1.0",
                        }
                        print(f"[HOST] Calculations DON'T match! Sending RESOLUTION_REQUEST: {resolution_msg}")
                        # Send in a separate thread to avoid blocking listen_loop
                        threading.Thread(target=lambda: self.reliability.send_with_ack(resolution_msg, self.jaddr), daemon=True).start()
                else:
                    print("[HOST] Warning: No local calculation to compare against")

            # Handle CALCULATION_CONFIRM
            if kv.get("message_type") == "CALCULATION_CONFIRM":
                damage_confirmed = kv.get("damage_confirmed", "0")
                remaining_health = kv.get("remaining_health", "0")
                
                print(f"[HOST] Received CALCULATION_CONFIRM: damage={damage_confirmed}, remaining_hp={remaining_health}")
                
                # Apply damage
                if self.pending_defender:
                    self.pending_defender.current_hp = int(remaining_health)
                    print(f"[HOST] Applied confirmed damage. {self.pending_defender.name} HP is now {self.pending_defender.current_hp}")
                
                # Check for game over
                if int(remaining_health) <= 0 and self.pending_defender:
                    print(f"[HOST] {self.pending_defender.name} fainted!")
                    # Game over will be handled by GAME_OVER message or already sent
                else:
                    # Switch turns and return to WAITING_FOR_MOVE
                    self.is_my_turn = not self.is_my_turn
                    self.battle_phase = BattlePhase.WAITING_FOR_MOVE
                    self.pending_move = None
                    self.my_calculation = None
                    
                    if self.is_my_turn:
                        print("[HOST] Turn switched! It's your turn. Type !attack to make a move.")
                    else:
                        print("[HOST] Turn switched! Waiting for opponent's move...")

            # Handle RESOLUTION_REQUEST - other peer's calculation didn't match
            if kv.get("message_type") == "RESOLUTION_REQUEST":
                their_damage = kv.get("calculated_damage", "0")
                their_remaining_hp = kv.get("calculated_remaining_hp", "0")
                their_atk_stat = kv.get("attacker_stat", "0")
                their_def_stat = kv.get("defender_stat", "0")
                their_multiplier = kv.get("type_multiplier", "1.0")
                
                print(f"[HOST] Received RESOLUTION_REQUEST: {kv}")
                print(f"[HOST] Their values - damage: {their_damage}, remaining_hp: {their_remaining_hp}")
                print(f"[HOST] Their stats - atk: {their_atk_stat}, def: {their_def_stat}, multiplier: {their_multiplier}")
                
                if self.my_calculation:
                    print(f"[HOST] Our values - damage: {self.my_calculation['damage']}, remaining_hp: {self.my_calculation['remaining_hp']}")
                    
                    # Check if we can accept their values (re-evaluate)
                    # For now, if there's a discrepancy, we'll accept their values if reasonable
                    their_damage_int = int(their_damage)
                    their_hp_int = int(their_remaining_hp)
                    
                    # Accept their calculation and update state
                    print(f"[HOST] Accepting resolution values. Applying damage: {their_damage_int}")
                    
                    if self.pending_defender:
                        self.pending_defender.current_hp = their_hp_int
                        print(f"[HOST] {self.pending_defender.name} HP is now {their_hp_int}")
                    
                    # Check for game over
                    if their_hp_int <= 0 and self.pending_defender:
                        print(f"[HOST] {self.pending_defender.name} fainted!")
                        game_over_msg = {
                            "message_type": "GAME_OVER",
                            "winner": self.pending_attacker.name if self.pending_attacker else "Unknown",
                            "loser": self.pending_defender.name,
                        }
                        print(f"[HOST] Sending GAME_OVER: {game_over_msg}")
                        # Send in a separate thread to avoid blocking listen_loop
                        def send_game_over_resolution():
                            self.send(game_over_msg)
                            self.running = False
                            self.listening = False
                        threading.Thread(target=send_game_over_resolution, daemon=True).start()
                    else:
                        # Switch turns
                        self.is_my_turn = not self.is_my_turn
                        self.battle_phase = BattlePhase.WAITING_FOR_MOVE
                        self.pending_move = None
                        self.my_calculation = None
                        
                        if self.is_my_turn:
                            print("[HOST] Resolution accepted. It's your turn. Type !attack to make a move.")
                        else:
                            print("[HOST] Resolution accepted. Waiting for opponent's move...")
                else:
                    print("[HOST] Error: Received RESOLUTION_REQUEST but no local calculation exists")
                    # Terminate battle due to fundamental error
                    print("[HOST] FATAL: Battle state inconsistent. Terminating.")
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

            if "ack_number" in kv:
                self.ack = int(kv["ack_number"])

    # Helper function to build a move from a name
    def _build_move_from_name(self, move_name: str, attacker) -> Move:
        move_type = attacker.type1.lower()
        damage_category = get_damage_category(move_type)
        return Move(
            name=move_name,
            base_power=1,
            category=damage_category,
            move_type=move_type,
        )

    # Chat function for CHAT_MESSAGE
    def chat(self):
        msg = input("Type a message (or !attack to attack):\n")

        if msg.strip() == "!attack":
            # Check if it's our turn and we're in the right state
            if not self.is_my_turn:
                print("[HOST] It's not your turn! Wait for the opponent's move.")
                return
            if self.battle_phase != BattlePhase.WAITING_FOR_MOVE:
                print(f"[HOST] Cannot attack right now. Current state: {self.battle_phase}")
                return
            if not self.opp_mon:
                print("[HOST] Cannot attack - opponent's Pokemon not set up yet.")
                return
                
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

            # Store pending move info for this turn
            self.pending_attacker = self.pokemon
            self.pending_defender = self.opp_mon
            self.pending_move = self._build_move_from_name(move_name, self.pokemon)
            
            attack_msg = {
                "message_type": "ATTACK_ANNOUNCE",
                "attacker_name": self.pokemon.name,
                "defender_name": self.opp_mon.name if self.opp_mon else "",
                "move_name": move_name,
            }
            print(f"[HOST] Sending ATTACK_ANNOUNCE: {attack_msg}")
            # Sending ATTACK_ANNOUNCE to the joiner
            self.reliability.send_with_ack(attack_msg, self.jaddr)
            print("[HOST] Waiting for DEFENSE_ANNOUNCE...")
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
