"""
Host peer implementation.
Handles accepting connections, handshakes, and spectator support.
"""

import socket
import threading
import queue

from peers.base_peer import BasePeer
from protocol.messages import encode_message, decode_message
from protocol.battle_state import BattlePhase


class Host(BasePeer):
    """
    Host peer that accepts connections and manages the battle session.
    Inherits common functionality from BasePeer.
    """

    def __init__(self, pokemon, db, comm_mode):
        """
        Initialize host peer.

        Args:
            pokemon: This peer's Pokemon
            db: Pokemon database
            comm_mode: Communication mode ("P2P" or "BROADCAST")
        """
        super().__init__(pokemon, db, comm_mode, is_host=True)

        # Host-specific attributes
        self.addr = ""
        self.seed = 0
        self.request_queue = queue.Queue()
        self.battle_setup_done = False

        # Spectator support
        self.spect = False
        self.saddr = None

    def accept(self):
        """Main accept loop for the host."""
        self.name = input("Name this Peer\n")

        if self.comm_mode == "P2P":
            self.addr = str(input("Set host address:"))
        else:
            self.addr = "0.0.0.0"

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

        self.sock.bind((self.addr, port))
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
                    "Enter Y to accept Peer, enter anything else to ignore\n"
                ).upper()
                if choice != "Y":
                    print("Peer rejected.")
                    continue

                if self.comm_mode == "P2P":
                    self.remote_addr = addr
                else:
                    self.remote_addr = ("255.255.255.255", port)

                self.running = False

                seed = -1
                while seed < 0:
                    try:
                        seed = int(input("Enter seed: "))
                    except:
                        print("Invalid seed.")

                # Send handshake response
                self.seed = seed
                handshake = encode_message(
                    {"message_type": "HANDSHAKE_RESPONSE", "seed": seed}
                )
                self.sock.sendto(handshake.encode("utf-8"), self.remote_addr)
                print("Handshake sent.\n")

                listener = threading.Thread(target=self.listen_loop, daemon=True)
                listener.start()

                while True:
                    self.chat()

        self.sock.close()
        peers.join()

    def _accept_loop(self):
        """Loop for accepting peers, ends when the game begins."""
        while self.running:
            try:
                msg, addr = self.sock.recvfrom(1024)
            except OSError:
                break

            decoded = msg.decode()
            kv = decode_message(decoded)

            # Only process handshake requests in accept loop
            if kv.get("message_type") == "HANDSHAKE_REQUEST":
                self.request_queue.put((decoded, addr))

        # Reset socket timeout when exiting
        try:
            self.sock.settimeout(None)
        except OSError:
            pass

    def process_message(self, kv, addr):
        """
        Process messages with host-specific handling.

        Args:
            kv: Decoded message dictionary
            addr: Address message came from
        """
        # Forward to spectator if connected (P2P mode)
        if self.spect and self.comm_mode == "P2P":
            # Re-encode and forward the message
            raw_msg = encode_message(kv)
            self.reliability.send_with_ack(kv, self.saddr)

        # Handle SPECTATOR_REQUEST
        if kv.get("message_type") == "SPECTATOR_REQUEST":
            if not self.spect:
                self.saddr = addr
                response = encode_message({"message_type": "HANDSHAKE_RESPONSE"})
                self.sock.sendto(response.encode("utf-8"), addr)
                self.spect = True
                print("Spectator connected.")
            return

        # Use parent class for common message handling
        super().process_message(kv, addr)

    def _on_battle_setup(self, kv):
        """Send BATTLE_SETUP response to joiner after receiving their setup."""
        if not self.battle_setup_done and self.remote_addr is not None:
            reply = {
                "message_type": "BATTLE_SETUP",
                "communication_mode": self.comm_mode,
                "pokemon_name": self.pokemon.name,
                "stat_boosts": {"special_attack_uses": 5, "special_defense_uses": 5},
            }
            print(f"[Host] Sending BATTLE_SETUP: {reply}")
            self.battle_setup_done = True

            # Send in a separate thread to avoid blocking
            threading.Thread(
                target=lambda: self.reliability.send_with_ack(reply, self.remote_addr),
                daemon=True,
            ).start()

    def send_message(self, msg):
        """
        Send a message to the joiner and optionally to spectator.

        Args:
            msg: Message dictionary to send
        """
        self.reliability.send_with_ack(msg, self.remote_addr)

        # Forward to spectator in P2P mode
        if self.spect and self.comm_mode == "P2P":
            self.reliability.send_with_ack(msg, self.saddr)

    def chat(self):
        """Host-specific chat with additional commands."""
        msg = input(
            "Commands:\n!attack to attack\n!chat for text message\n!sticker for sticker message\n!defend to defend\n!resolve for resolution request\n"
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

        if msg.strip() == "!defend":
            print("defender logic here")

        if msg.strip() == "!resolve":
            print("Resolve logic here")


# Alias for backwards compatibility
host = Host
