"""
Base peer class with shared functionality for host and joiner.
"""

import socket
import threading
import queue

from protocol.messages import encode_message, decode_message
from protocol.reliability import ReliableChannel
from protocol.battle_manager import BattleManager
from protocol.battle_state import BattlePhase
from protocol import message_handlers


class BasePeer:
    """
    Base class for peer implementations (host and joiner).
    Contains common socket setup, listener loop, and chat functionality.
    """

    def __init__(self, pokemon, db, comm_mode, is_host=True):
        """
        Initialize base peer.

        Args:
            pokemon: This peer's Pokemon
            db: Pokemon database
            comm_mode: Communication mode ("P2P" or "BROADCAST")
            is_host: Whether this peer is the host
        """
        self.pokemon = pokemon
        self.opp_mon = None
        self.db = db
        self.comm_mode = comm_mode
        self.is_host = is_host
        self.name = ""

        # Socket setup
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Message handling
        self.ack_queue = queue.Queue()
        self.kv_messages = []
        self.lock = threading.Lock()
        self.seq = 0  # Start at 0 so first message (seq=1) isn't flagged as duplicate
        self.ack = None

        # State flags
        self.running = False
        self.listening = True

        # Reliability layer
        self.reliability = ReliableChannel(self.sock, self.ack_queue)

        # Battle manager
        self.battle_manager = BattleManager(is_host=is_host)

        # Remote peer address
        self.remote_addr = None

    def get_role(self) -> str:
        """Get the role string for logging."""
        return "HOST" if self.is_host else "JOINER"

    def handle_sequence_and_ack(self, kv, addr) -> bool:
        """
        Handle sequence numbers and send ACKs.

        Args:
            kv: Decoded message dictionary
            addr: Address message came from

        Returns:
            True if this is a duplicate message that should be skipped
        """
        if "sequence_number" not in kv:
            return False

        incoming_seq = int(kv["sequence_number"])

        # Always send ACK for the received sequence number
        ackmsg = encode_message({"message_type": "ACK", "ack_number": incoming_seq})
        self.sock.sendto(ackmsg.encode("utf-8"), addr)

        if self.is_host:
            print(f"[HOST] Sending ACK {incoming_seq} to {addr}")

        # Only process if it's a new message (not a duplicate)
        if incoming_seq <= self.seq:
            print(
                f"[{self.get_role()}] Ignoring duplicate message seq={incoming_seq} (current seq={self.seq})"
            )
            return True

        # New message, update our sequence counter
        self.seq = incoming_seq
        return False

    def store_message(self, kv):
        """Store a message in the message history."""
        with self.lock:
            self.kv_messages.append(kv)

    def process_message(self, kv, addr):
        """
        Process a received message using the appropriate handler.
        Override in subclasses for peer-specific message handling.

        Args:
            kv: Decoded message dictionary
            addr: Address message came from
        """
        msg_type = kv.get("message_type")

        # Handle BATTLE_SETUP
        if msg_type == "BATTLE_SETUP":
            message_handlers.handle_battle_setup(kv, self, is_host=self.is_host)
            self._on_battle_setup(kv)

        # Handle ATTACK_ANNOUNCE
        elif msg_type == "ATTACK_ANNOUNCE":
            defense_msg, report_msg = message_handlers.handle_attack_announce(
                kv, self, is_host=self.is_host
            )
            if defense_msg and report_msg:

                def send_defense_and_report():
                    self.reliability.send_with_ack(defense_msg, self.remote_addr)
                    self.reliability.send_with_ack(report_msg, self.remote_addr)

                threading.Thread(target=send_defense_and_report, daemon=True).start()

        # Handle DEFENSE_ANNOUNCE
        elif msg_type == "DEFENSE_ANNOUNCE":
            report = message_handlers.handle_defense_announce(
                kv, self, is_host=self.is_host
            )
            if report:
                threading.Thread(
                    target=lambda: self.reliability.send_with_ack(
                        report, self.remote_addr
                    ),
                    daemon=True,
                ).start()

        # Handle CALCULATION_REPORT
        elif msg_type == "CALCULATION_REPORT":
            response, game_over_msg, should_stop = (
                message_handlers.handle_calculation_report(
                    kv, self, is_host=self.is_host
                )
            )
            if response:
                if game_over_msg:

                    def send_confirm_and_game_over():
                        self.reliability.send_with_ack(response, self.remote_addr)
                        self.send_message(game_over_msg)
                        self.running = False
                        self.listening = False

                    threading.Thread(
                        target=send_confirm_and_game_over, daemon=True
                    ).start()
                else:
                    threading.Thread(
                        target=lambda: self.reliability.send_with_ack(
                            response, self.remote_addr
                        ),
                        daemon=True,
                    ).start()

        # Handle CALCULATION_CONFIRM
        elif msg_type == "CALCULATION_CONFIRM":
            message_handlers.handle_calculation_confirm(kv, self, is_host=self.is_host)

        # Handle RESOLUTION_REQUEST
        elif msg_type == "RESOLUTION_REQUEST":
            game_over_msg, should_stop, is_fatal = (
                message_handlers.handle_resolution_request(
                    kv, self, is_host=self.is_host
                )
            )
            if game_over_msg:

                def send_game_over_resolution():
                    self.send_message(game_over_msg)
                    self.running = False
                    self.listening = False

                threading.Thread(target=send_game_over_resolution, daemon=True).start()
            elif is_fatal:
                self.running = False
                self.listening = False

        # Handle GAME_OVER
        elif msg_type == "GAME_OVER":
            message_handlers.handle_game_over(kv, self, is_host=self.is_host)
            self.running = False
            self.listening = False
            self.sock.close()

        # Handle ACK numbers
        if "ack_number" in kv:
            self.ack = int(kv["ack_number"])

    def _on_battle_setup(self, kv):
        """
        Hook for subclasses to handle battle setup completion.
        Override in host to send battle setup response.
        """
        pass

    def listen_loop(self):
        """Main listener loop to handle incoming messages."""
        try:
            self.sock.settimeout(None)
        except OSError:
            return

        while self.listening:
            try:
                msg, addr = self.sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break

            decoded = msg.decode()
            kv = decode_message(decoded)

            if kv.get("message_type") != "ACK":
                print(f"\n{decoded}")

            self.ack_queue.put(kv)

            # Handle sequence numbers and ACKs
            is_duplicate = self.handle_sequence_and_ack(kv, addr)
            if is_duplicate:
                continue

            # Store message
            self.store_message(kv)

            # Process message
            self.process_message(kv, addr)

    def send_message(self, msg):
        """
        Send a message to the remote peer.

        Args:
            msg: Message dictionary to send
        """
        self.reliability.send_with_ack(msg, self.remote_addr)

    def perform_attack(self):
        """
        Perform an attack if conditions are met.

        Returns:
            bool: True if attack was initiated
        """
        role = self.get_role()
        bm = self.battle_manager

        # Check if it's our turn and we're in the right state
        if not bm.is_my_turn:
            print(f"[{role}] It's not your turn! Wait for the opponent's move.")
            return False

        if bm.battle_phase != BattlePhase.WAITING_FOR_MOVE:
            print(f"[{role}] Cannot attack right now. Current state: {bm.battle_phase}")
            return False

        if not self.opp_mon:
            print(f"[{role}] Cannot attack - opponent's Pokemon not set up yet.")
            return False

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

        # Prepare and send attack
        attack_msg = bm.prepare_attack(self.pokemon, self.opp_mon, move_name)
        print(f"[{role}] Sending ATTACK_ANNOUNCE: {attack_msg}")
        self.reliability.send_with_ack(attack_msg, self.remote_addr)
        print(f"[{role}] Waiting for DEFENSE_ANNOUNCE...")
        return True

    def send_chat_message(self, text):
        """
        Send a chat text message.

        Args:
            text: Message text
        """
        chat_msg = {
            "message_type": "CHAT_MESSAGE",
            "sender_name": self.name,
            "content_type": "TEXT",
            "message_text": text,
        }
        self.send_message(chat_msg)

    def send_sticker_message(self, sticker_data):
        """
        Send a sticker message.

        Args:
            sticker_data: Sticker data
        """
        chat_msg = {
            "message_type": "CHAT_MESSAGE",
            "sender_name": self.name,
            "content_type": "STICKER",
            "sticker_data": sticker_data,
        }
        self.send_message(chat_msg)

    def chat(self):
        """Interactive chat function. Override for peer-specific behavior."""
        msg = input(
            "Commands:\n!attack to attack\n!chat for text message\n!sticker for sticker message\n"
        )

        if msg.strip() == "!attack":
            self.perform_attack()
            return

        if msg.strip() == "!chat":
            text = input("Type a message: \n")
            self.send_chat_message(text)

        if msg.strip() == "!sticker":
            stick = input("Input sticker data: \n")
            self.send_sticker_message(stick)
