"""
Base class for Host and Joiner peers.
Has all the common stuff like socket setup, message handling, etc.
"""

import socket
import threading
import queue

from protocol.messages import encode_message, decode_message
from protocol.reliability import ReliableChannel
from protocol.battle_manager import BattleManager
from protocol.battle_state import BattlePhase, initialize_battle_rng
from protocol import message_handlers
from protocol.message_factory import MessageFactory
from protocol.constants import MessageType


class BasePeer:
    """Base class that Host and Joiner both inherit from."""

    def __init__(self, pokemon, db, comm_mode: str, is_host: bool = True):
        """Sets up the peer with socket and battle stuff."""

        # pokemon and battle info
        self.pokemon = pokemon
        self.opp_mon = None
        self.db = db
        self.is_host = is_host
        self.name = ""
        self.comm_mode = comm_mode

        # socket setup - using UDP
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # message handling stuff
        self.ack_queue = queue.Queue()
        self.kv_messages = []
        self.lock = threading.Lock()
        self.last_processed_sequence = 0
        self.ack = None

        # state flags
        self.running = False
        self.listening = True

        # reliability layer
        self.reliability = ReliableChannel(self.sock, self.ack_queue)

        # battle manager
        self.battle_manager = BattleManager(is_host=is_host)

        # remote peer address
        self.remote_addr = None
        self.seed = None

    def get_role(self) -> str:
        """Returns 'HOST' or 'JOINER'."""
        if self.is_host:
            return "HOST"
        else:
            return "JOINER"

    def initialize_rng(self, seed: int):
        """Sets up the RNG with a seed."""
        self.seed = seed
        initialize_battle_rng(seed)
        role = self.get_role()
        print(f"[{role}] Battle RNG initialized with seed: {seed}")

    def handle_sequence_and_ack(self, message: dict, sender_address: tuple) -> bool:
        """Handles sequence numbers and sends ACK. Returns True if duplicate."""

        if "sequence_number" not in message:
            return False

        incoming_sequence = int(message["sequence_number"])

        # always send ACK
        ack_message = MessageFactory.ack(incoming_sequence)
        ack_encoded = encode_message(ack_message)
        self.sock.sendto(ack_encoded.encode("utf-8"), sender_address)

        if self.is_host:
            print(f"[HOST] Sending ACK {incoming_sequence} to {sender_address}")

        # check if duplicate
        if incoming_sequence <= self.last_processed_sequence:
            role = self.get_role()
            print(
                f"[{role}] Ignoring duplicate message (seq={incoming_sequence}, already processed up to {self.last_processed_sequence})"
            )
            return True

        self.last_processed_sequence = incoming_sequence
        return False

    def store_message(self, message: dict):
        """Stores a message in history."""
        with self.lock:
            self.kv_messages.append(message)

    def process_message(self, message: dict, sender_address: tuple):
        """Processes a message by calling the right handler."""

        message_type = message.get("message_type")

        # BATTLE_SETUP
        if message_type == MessageType.BATTLE_SETUP:
            message_handlers.handle_battle_setup(message, self, is_host=self.is_host)
            self._on_battle_setup(message)

        # ATTACK_ANNOUNCE
        elif message_type == MessageType.ATTACK_ANNOUNCE:
            defense_msg, calculation_report_msg = (
                message_handlers.handle_attack_announce(
                    message, self, is_host=self.is_host
                )
            )

            if defense_msg and calculation_report_msg:

                def send_responses():
                    self.reliability.send_with_ack(defense_msg, self.remote_addr)
                    self.reliability.send_with_ack(
                        calculation_report_msg, self.remote_addr
                    )

                background_thread = threading.Thread(target=send_responses, daemon=True)
                background_thread.start()

        # DEFENSE_ANNOUNCE
        elif message_type == MessageType.DEFENSE_ANNOUNCE:
            calculation_report = message_handlers.handle_defense_announce(
                message, self, is_host=self.is_host
            )

            if calculation_report:

                def send_report():
                    self.reliability.send_with_ack(calculation_report, self.remote_addr)

                background_thread = threading.Thread(target=send_report, daemon=True)
                background_thread.start()

        # CALCULATION_REPORT
        elif message_type == MessageType.CALCULATION_REPORT:
            response, game_over_msg, should_stop = (
                message_handlers.handle_calculation_report(
                    message, self, is_host=self.is_host
                )
            )

            if response:
                if game_over_msg:

                    def send_confirm_and_game_over():
                        self.reliability.send_with_ack(response, self.remote_addr)
                        self.send_message(game_over_msg)
                        self.running = False
                        self.listening = False

                    background_thread = threading.Thread(
                        target=send_confirm_and_game_over, daemon=True
                    )
                    background_thread.start()
                else:

                    def send_response():
                        self.reliability.send_with_ack(response, self.remote_addr)

                    background_thread = threading.Thread(
                        target=send_response, daemon=True
                    )
                    background_thread.start()

        # CALCULATION_CONFIRM
        elif message_type == MessageType.CALCULATION_CONFIRM:
            message_handlers.handle_calculation_confirm(
                message, self, is_host=self.is_host
            )

        # RESOLUTION_REQUEST
        elif message_type == MessageType.RESOLUTION_REQUEST:
            game_over_msg, should_stop, is_fatal = (
                message_handlers.handle_resolution_request(
                    message, self, is_host=self.is_host
                )
            )

            if game_over_msg:

                def send_game_over():
                    self.send_message(game_over_msg)
                    self.running = False
                    self.listening = False

                background_thread = threading.Thread(target=send_game_over, daemon=True)
                background_thread.start()
            elif is_fatal:
                self.running = False
                self.listening = False

        # GAME_OVER
        elif message_type == MessageType.GAME_OVER:
            message_handlers.handle_game_over(message, self, is_host=self.is_host)
            self.running = False
            self.listening = False
            self.sock.close()

        # track ack numbers
        if "ack_number" in message:
            self.ack = int(message["ack_number"])

    def _on_battle_setup(self, message: dict):
        """Hook for subclasses after battle setup."""
        pass

    def listen_loop(self):
        """Listens for incoming messages."""

        try:
            self.sock.settimeout(None)
        except OSError:
            return

        while self.listening:
            try:
                raw_message, sender_address = self.sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break

            message_string = raw_message.decode("utf-8")
            message_dict = decode_message(message_string)

            # print non-ACK messages
            if message_dict.get("message_type") != MessageType.ACK:
                print(f"\n{message_string}")

            self.ack_queue.put(message_dict)

            # handle sequence and ACK
            is_duplicate = self.handle_sequence_and_ack(message_dict, sender_address)
            if is_duplicate:
                continue

            self.store_message(message_dict)
            self.process_message(message_dict, sender_address)

    def send_message(self, message: dict):
        """Sends a message with reliability."""
        self.reliability.send_with_ack(message, self.remote_addr)

    def send_chat_message(self, text: str):
        """Sends a chat message."""
        chat_message = MessageFactory.chat_text(self.name, text)
        self.send_message(chat_message)

    def send_sticker_message(self, sticker_data: str):
        """Sends a sticker."""
        sticker_message = MessageFactory.chat_sticker(self.name, sticker_data)
        self.send_message(sticker_message)

    def perform_attack(self) -> bool:
        """Performs an attack on the opponent."""

        role = self.get_role()
        bm = self.battle_manager

        # check if its our turn
        if not bm.is_my_turn:
            print(f"[{role}] It's not your turn! Wait for the opponent's move.")
            return False

        # check phase
        if bm.battle_phase != BattlePhase.WAITING_FOR_MOVE:
            print(f"[{role}] Cannot attack right now. Current phase: {bm.battle_phase}")
            return False

        # check opponent pokemon
        if not self.opp_mon:
            print(f"[{role}] Cannot attack - opponent's Pokemon not set up yet.")
            return False

        print(f"\nYour Pokemon: {self.pokemon.name}")

        # choose a move
        if not self.pokemon.moves:
            print("No moves available, using BasicMove.")
            move_name = "BasicMove"
        else:
            print("Available moves:")
            for index, move in enumerate(self.pokemon.moves, start=1):
                print(f"  {index}. {move}")

            choice = input("Choose a move number: ")
            try:
                index = int(choice) - 1
                if 0 <= index < len(self.pokemon.moves):
                    move_name = self.pokemon.moves[index]
                else:
                    print("Invalid choice, using first move.")
                    move_name = self.pokemon.moves[0]
            except ValueError:
                print("Invalid input, using first move.")
                move_name = self.pokemon.moves[0]

        # ask about boost
        if bm.special_attack_uses > 0:
            print(f"\nSpecial Attack boosts remaining: {bm.special_attack_uses}")
            use_boost_input = input("Use Special Attack boost? (y/n): ")
            if use_boost_input.lower().strip() == "y":
                bm.use_special_attack()

        # send attack
        attack_message = bm.prepare_attack(self.pokemon, self.opp_mon, move_name)
        print(f"[{role}] Sending ATTACK_ANNOUNCE: {move_name}")
        self.reliability.send_with_ack(attack_message, self.remote_addr)
        print(f"[{role}] Waiting for opponent's response...")

        return True

    def chat(self):
        """Chat interface for the player."""

        bm = self.battle_manager

        # show status
        print(f"\n--- Status ---")
        print(f"  Special Attack boosts: {bm.special_attack_uses}")
        print(f"  Special Defense boosts: {bm.special_defense_uses}")

        if bm.defense_boost_armed:
            print("  [Defense boost ARMED for next incoming attack]")

        # show commands
        print("\nCommands:")
        print("  !attack  - Attack the opponent")
        # print("  !defend  - Arm defense boost for next attack")
        print("  !chat    - Send a text message")
        print("  !sticker - Send a sticker")

        user_input = input("\nEnter command: ")
        command = user_input.strip().lower()

        if command == "!attack":
            self.perform_attack()

        # elif command == "!defend":
        #     if bm.is_my_turn:
        #         print(
        #             "You can only arm defense boost when waiting for opponent's attack."
        #         )
        #     else:
        #         bm.arm_defense_boost()

        elif command == "!chat":
            text = input("Type your message: ")
            self.send_chat_message(text)
            print("Message sent!")

        elif command == "!sticker":
            sticker = input("Enter sticker data (Base64): ")
            self.send_sticker_message(sticker)
            print("Sticker sent!")

        else:
            print(f"Unknown command: {command}")
