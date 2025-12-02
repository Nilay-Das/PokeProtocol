import socket
import threading
import time
import queue

from protocol import reliability, pokemon_db
from protocol.messages import *
from protocol.reliability import ReliableChannel
from protocol.battle_state import (
    Move,
    BattleState,
    BattlePhase,
    calculate_damage,
    apply_damage,
    get_damage_category,
)


class joiner:
    # attributes
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
        self.seq = 0  # Start at 0 so first message (seq=1) isn't flagged as duplicate
        self.ack = None
        self.reliability = ReliableChannel(self.sock, self.ack_queue)

        # Turn-based battle state tracking
        self.battle_phase = None  # BattlePhase enum
        self.is_my_turn = False  # Joiner goes second
        self.pending_move = None  # Current move being processed
        self.my_calculation = None  # Local damage calculation for comparison
        self.pending_attacker = None  # Attacker for current turn
        self.pending_defender = None  # Defender for current turn

    def start(self, host_ip, host_port):
        # bind local ephemeral port
        if self.comm_mode == "P2P":
            self.sock.bind(("", 0))
        else:
            self.sock.bind(("0.0.0.0", host_port))

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

            # Handle sequence numbers and ACKs first
            is_duplicate = False
            if "sequence_number" in kv:
                incoming_seq = int(kv["sequence_number"])
                # Always send ACK for the received sequence number
                ackmsg = encode_message(
                    {"message_type": "ACK", "ack_number": incoming_seq}
                )
                self.sock.sendto(ackmsg.encode("utf-8"), self.host_addr)

                # Only process if it's a new message (not a duplicate)
                if incoming_seq <= self.seq:
                    # This is a duplicate message, skip processing
                    is_duplicate = True
                    print(
                        f"[JOINER] Ignoring duplicate message seq={incoming_seq} (current seq={self.seq})"
                    )
                else:
                    # New message, update our sequence counter
                    self.seq = incoming_seq

            if is_duplicate:
                continue

            # Store message (only non-duplicates)
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

                        # Transition to WAITING_FOR_MOVE state
                        self.battle_phase = BattlePhase.WAITING_FOR_MOVE
                        print(
                            f"[JOINER] Battle setup complete! Entering {self.battle_phase.value} state."
                        )
                        print("[JOINER] Waiting for Host's move...")
                    else:
                        print(
                            f"[Joiner] Received BATTLE_SETUP with unknown Pokémon: {pname}"
                        )

            # Handle ATTACK_ANNOUNCE - defender receives attack
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
                    print(f"[JOINER] Sending DEFENSE_ANNOUNCE: {defense_msg}")

                    # Transition to PROCESSING_TURN
                    self.battle_phase = BattlePhase.PROCESSING_TURN
                    print(f"[JOINER] Entering {self.battle_phase.value} state.")

                    # Calculate damage locally (don't apply yet)
                    state = BattleState(attacker=attacker, defender=defender)
                    print(
                        f"[JOINER] Before attack: {defender.name} HP = {defender.current_hp}"
                    )
                    damage = calculate_damage(state, self.pending_move)

                    # Store calculation for comparison
                    self.my_calculation = {
                        "damage": damage,
                        "remaining_hp": (
                            defender.current_hp - damage
                            if defender.current_hp - damage > 0
                            else 0
                        ),
                    }
                    print(f"[JOINER] Calculated damage: {damage}")

                    # Send CALCULATION_REPORT
                    report = {
                        "message_type": "CALCULATION_REPORT",
                        "attacker_name": attacker.name,
                        "defender_name": defender.name,
                        "move_name": self.pending_move.name,
                        "damage_dealt": str(damage),
                        "defender_hp_remaining": str(
                            self.my_calculation["remaining_hp"]
                        ),
                    }
                    print(f"[JOINER] Sending CALCULATION_REPORT: {report}")

                    # Send in a separate thread to avoid blocking listen_loop
                    def send_defense_and_report():
                        self.reliability.send_with_ack(defense_msg, self.host_addr)
                        self.reliability.send_with_ack(report, self.host_addr)

                    threading.Thread(
                        target=send_defense_and_report, daemon=True
                    ).start()

            # Handle DEFENSE_ANNOUNCE - host acknowledged our attack
            if kv.get("message_type") == "DEFENSE_ANNOUNCE":
                defender_name = kv.get("defender_name", "")
                acknowledged_move = kv.get("acknowledged_move", "")
                print(
                    f"[JOINER] Received DEFENSE_ANNOUNCE: {defender_name} acknowledged {acknowledged_move}"
                )

                # Transition to PROCESSING_TURN
                self.battle_phase = BattlePhase.PROCESSING_TURN
                print(f"[JOINER] Entering {self.battle_phase.value} state.")

                # Calculate damage locally (joiner attacking host)
                if (
                    self.pending_attacker
                    and self.pending_defender
                    and self.pending_move
                ):
                    state = BattleState(
                        attacker=self.pending_attacker, defender=self.pending_defender
                    )
                    damage = calculate_damage(state, self.pending_move)
                    remaining_hp = self.pending_defender.current_hp - damage
                    if remaining_hp < 0:
                        remaining_hp = 0

                    # Store calculation for comparison
                    self.my_calculation = {
                        "damage": damage,
                        "remaining_hp": remaining_hp,
                    }
                    print(
                        f"[JOINER] Calculated damage: {damage}, remaining HP: {remaining_hp}"
                    )

                    # Send CALCULATION_REPORT
                    report = {
                        "message_type": "CALCULATION_REPORT",
                        "attacker_name": self.pending_attacker.name,
                        "defender_name": self.pending_defender.name,
                        "move_name": self.pending_move.name,
                        "damage_dealt": str(damage),
                        "defender_hp_remaining": str(remaining_hp),
                    }
                    print(f"[JOINER] Sending CALCULATION_REPORT: {report}")
                    # Send in a separate thread to avoid blocking listen_loop
                    threading.Thread(
                        target=lambda: self.reliability.send_with_ack(
                            report, self.host_addr
                        ),
                        daemon=True,
                    ).start()
                else:
                    print("[JOINER] Error: No pending move info for calculation")

            # Handle incoming CALCULATION_REPORT from host
            if kv.get("message_type") == "CALCULATION_REPORT":
                attacker_name = kv.get("attacker_name", "")
                defender_name = kv.get("defender_name", "")
                move_name = kv.get("move_name", "")
                damage_str = kv.get("damage_dealt", "0")
                hp_str = kv.get("defender_hp_remaining", "0")

                print(f"[JOINER] Received CALCULATION_REPORT: {kv}")

                reported_damage = int(damage_str)
                reported_hp = int(hp_str)

                # Compare with our local calculation
                if self.my_calculation:
                    local_damage = self.my_calculation["damage"]
                    local_remaining_hp = self.my_calculation["remaining_hp"]

                    print(
                        f"[JOINER] Local damage = {local_damage}, reported damage = {reported_damage}"
                    )
                    print(
                        f"[JOINER] Local remaining HP = {local_remaining_hp}, reported HP = {reported_hp}"
                    )

                    if (
                        local_damage == reported_damage
                        and local_remaining_hp == reported_hp
                    ):
                        # Calculations match - send CALCULATION_CONFIRM
                        confirm_msg = {
                            "message_type": "CALCULATION_CONFIRM",
                            "damage_confirmed": str(local_damage),
                            "remaining_health": str(local_remaining_hp),
                        }
                        print(
                            f"[JOINER] Calculations match! Sending CALCULATION_CONFIRM: {confirm_msg}"
                        )
                        # Send in a separate thread to avoid blocking listen_loop
                        threading.Thread(
                            target=lambda: self.reliability.send_with_ack(
                                confirm_msg, self.host_addr
                            ),
                            daemon=True,
                        ).start()

                        # Apply damage to the defender (joiner's Pokemon when host attacks)
                        if self.pending_defender:
                            self.pending_defender.current_hp = local_remaining_hp
                            print(
                                f"[JOINER] Applied damage. {self.pending_defender.name} HP is now {self.pending_defender.current_hp}"
                            )

                        # Check for game over
                        if local_remaining_hp <= 0 and self.pending_defender:
                            print(f"[JOINER] {self.pending_defender.name} fainted!")

                            game_over_msg = {
                                "message_type": "GAME_OVER",
                                "winner": (
                                    self.pending_attacker.name
                                    if self.pending_attacker
                                    else "Unknown"
                                ),
                                "loser": self.pending_defender.name,
                            }

                            print(f"[JOINER] Sending GAME_OVER: {game_over_msg}")

                            # Send in a separate thread to avoid blocking listen_loop
                            def send_game_over():
                                self.reliability.send_with_ack(
                                    game_over_msg, self.host_addr
                                )
                                self.running = False
                                self.sock.close()

                            threading.Thread(target=send_game_over, daemon=True).start()
                            break
                        # Don't switch turns here - wait for CALCULATION_CONFIRM to be received
                    else:
                        # Calculations don't match - send RESOLUTION_REQUEST
                        resolution_msg = {
                            "message_type": "RESOLUTION_REQUEST",
                            "calculated_damage": str(local_damage),
                            "calculated_remaining_hp": str(local_remaining_hp),
                            "attacker_stat": (
                                str(
                                    self.pending_attacker.attack
                                    if self.pending_move
                                    and self.pending_move.category == "physical"
                                    else self.pending_attacker.special_attack
                                )
                                if self.pending_attacker
                                else "0"
                            ),
                            "defender_stat": (
                                str(
                                    self.pending_defender.physical_defense
                                    if self.pending_move
                                    and self.pending_move.category == "physical"
                                    else self.pending_defender.special_defense
                                )
                                if self.pending_defender
                                else "0"
                            ),
                            "type_multiplier": (
                                str(
                                    self.pending_defender.type_multipliers.get(
                                        self.pending_move.move_type, 1.0
                                    )
                                )
                                if self.pending_defender and self.pending_move
                                else "1.0"
                            ),
                        }
                        print(
                            f"[JOINER] Calculations DON'T match! Sending RESOLUTION_REQUEST: {resolution_msg}"
                        )
                        # Send in a separate thread to avoid blocking listen_loop
                        threading.Thread(
                            target=lambda: self.reliability.send_with_ack(
                                resolution_msg, self.host_addr
                            ),
                            daemon=True,
                        ).start()
                else:
                    print("[JOINER] Warning: No local calculation to compare against")

            # Handle CALCULATION_CONFIRM
            if kv.get("message_type") == "CALCULATION_CONFIRM":
                damage_confirmed = kv.get("damage_confirmed", "0")
                remaining_health = kv.get("remaining_health", "0")

                print(
                    f"[JOINER] Received CALCULATION_CONFIRM: damage={damage_confirmed}, remaining_hp={remaining_health}"
                )

                # Apply damage
                if self.pending_defender:
                    self.pending_defender.current_hp = int(remaining_health)
                    print(
                        f"[JOINER] Applied confirmed damage. {self.pending_defender.name} HP is now {self.pending_defender.current_hp}"
                    )

                # Check for game over
                if int(remaining_health) <= 0 and self.pending_defender:
                    print(f"[JOINER] {self.pending_defender.name} fainted!")
                    # Game over will be handled by GAME_OVER message
                else:
                    # Switch turns and return to WAITING_FOR_MOVE
                    self.is_my_turn = not self.is_my_turn
                    self.battle_phase = BattlePhase.WAITING_FOR_MOVE
                    self.pending_move = None
                    self.my_calculation = None

                    if self.is_my_turn:
                        print(
                            "[JOINER] Turn switched! It's your turn. Type !attack to make a move."
                        )
                    else:
                        print("[JOINER] Turn switched! Waiting for opponent's move...")

            # Handle RESOLUTION_REQUEST - other peer's calculation didn't match
            if kv.get("message_type") == "RESOLUTION_REQUEST":
                their_damage = kv.get("calculated_damage", "0")
                their_remaining_hp = kv.get("calculated_remaining_hp", "0")
                their_atk_stat = kv.get("attacker_stat", "0")
                their_def_stat = kv.get("defender_stat", "0")
                their_multiplier = kv.get("type_multiplier", "1.0")

                print(f"[JOINER] Received RESOLUTION_REQUEST: {kv}")
                print(
                    f"[JOINER] Their values - damage: {their_damage}, remaining_hp: {their_remaining_hp}"
                )
                print(
                    f"[JOINER] Their stats - atk: {their_atk_stat}, def: {their_def_stat}, multiplier: {their_multiplier}"
                )

                if self.my_calculation:
                    print(
                        f"[JOINER] Our values - damage: {self.my_calculation['damage']}, remaining_hp: {self.my_calculation['remaining_hp']}"
                    )

                    # Check if we can accept their values (re-evaluate)
                    their_damage_int = int(their_damage)
                    their_hp_int = int(their_remaining_hp)

                    # Accept their calculation and update state
                    print(
                        f"[JOINER] Accepting resolution values. Applying damage: {their_damage_int}"
                    )

                    if self.pending_defender:
                        self.pending_defender.current_hp = their_hp_int
                        print(
                            f"[JOINER] {self.pending_defender.name} HP is now {their_hp_int}"
                        )

                    # Check for game over
                    if their_hp_int <= 0 and self.pending_defender:
                        print(f"[JOINER] {self.pending_defender.name} fainted!")
                        game_over_msg = {
                            "message_type": "GAME_OVER",
                            "winner": (
                                self.pending_attacker.name
                                if self.pending_attacker
                                else "Unknown"
                            ),
                            "loser": self.pending_defender.name,
                        }
                        print(f"[JOINER] Sending GAME_OVER: {game_over_msg}")

                        # Send in a separate thread to avoid blocking listen_loop
                        def send_game_over_resolution():
                            self.reliability.send_with_ack(
                                game_over_msg, self.host_addr
                            )
                            self.running = False
                            self.sock.close()

                        threading.Thread(
                            target=send_game_over_resolution, daemon=True
                        ).start()
                        break
                    else:
                        # Switch turns
                        self.is_my_turn = not self.is_my_turn
                        self.battle_phase = BattlePhase.WAITING_FOR_MOVE
                        self.pending_move = None
                        self.my_calculation = None

                        if self.is_my_turn:
                            print(
                                "[JOINER] Resolution accepted. It's your turn. Type !attack to make a move."
                            )
                        else:
                            print(
                                "[JOINER] Resolution accepted. Waiting for opponent's move..."
                            )
                else:
                    print(
                        "[JOINER] Error: Received RESOLUTION_REQUEST but no local calculation exists"
                    )
                    # Terminate battle due to fundamental error
                    print("[JOINER] FATAL: Battle state inconsistent. Terminating.")
                    self.running = False
                    self.sock.close()
                    break

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
            "communication_mode": self.comm_mode,
            "pokemon_name": self.pokemon.name,
            "stat_boosts": {"special_attack_uses": 5, "special_defense_uses": 5},
        }
        print(f"[Joiner] Sending BATTLE_SETUP: {msg}")
        self.reliability.send_with_ack(msg, self.host_addr)

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

    def chat(self):
        chatmsg = input("Type a message (or !attack to attack):\n")

        if chatmsg.strip() == "!attack":
            # Check if it's our turn and we're in the right state
            if not self.is_my_turn:
                print("[JOINER] It's not your turn! Wait for the opponent's move.")
                return
            if self.battle_phase != BattlePhase.WAITING_FOR_MOVE:
                print(
                    f"[JOINER] Cannot attack right now. Current state: {self.battle_phase}"
                )
                return
            if not self.opp_mon:
                print("[JOINER] Cannot attack - opponent's Pokemon not set up yet.")
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
            print(f"[JOINER] Sending ATTACK_ANNOUNCE: {attack_msg}")
            self.reliability.send_with_ack(attack_msg, self.host_addr)
            print("[JOINER] Waiting for DEFENSE_ANNOUNCE...")
            return

        # Normal chat message
        send = {
            "message_type": "CHAT_MESSAGE",
            "sender_name": self.name,
            "content_type": "TEXT",
            "message_text": chatmsg,
        }
        self.reliability.send_with_ack(send, self.host_addr)
