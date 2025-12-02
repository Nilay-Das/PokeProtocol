"""
The Host peer - starts the battle and waits for joiners.
Host picks the seed and goes first.
"""

import socket
import threading
import queue

from peers.base_peer import BasePeer
from protocol.messages import encode_message, decode_message
from protocol.battle_state import BattlePhase
from protocol.message_factory import MessageFactory
from protocol.constants import MessageType


class Host(BasePeer):
    """The host that accepts connections and runs the battle."""

    def __init__(self, pokemon, db, comm_mode: str):
        """Sets up the host."""
        super().__init__(pokemon, db, comm_mode, is_host=True)

        self.host_address = ""
        self.seed = 0
        self.request_queue = queue.Queue()
        self.battle_setup_done = False

        # spectator stuff
        self.spectator_connected = False
        self.spectator_address = None

    def accept(self):
        """Starts hosting and waits for connections."""

        # get name
        self.name = input("Enter your name: ")

        # get IP
        if self.comm_mode == "P2P":
            self.host_address = input("Enter your IP address: ")
        else:
            self.host_address = "0.0.0.0"

        # get port
        print("Enter a port number (must be above 5000):")
        port = 5000
        while port <= 5000:
            try:
                port = int(input())
                if port <= 5000:
                    print("Port must be above 5000. Try again:")
            except ValueError:
                print("Please enter a valid number:")

        # bind socket
        self.sock.bind((self.host_address, port))
        print(f"\n{self.name} is now listening on port {port}")
        print("Waiting for a Joiner to connect...")

        # start accept loop
        self.running = True
        accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        accept_thread.start()

        # main loop
        while True:
            if not self.request_queue.empty():
                request_message, joiner_address = self.request_queue.get()

                print(f"\n--- Connection Request ---")
                print(f"Address: {joiner_address}")
                print(f"Message: {request_message}")

                choice = input("\nAccept this connection? (Y/N): ").upper()

                if choice != "Y":
                    print("Connection rejected.")
                    continue

                # store joiner address
                if self.comm_mode == "P2P":
                    self.remote_addr = joiner_address
                else:
                    self.remote_addr = ("255.255.255.255", port)

                self.running = False

                # get seed
                seed = -1
                while seed < 0:
                    try:
                        seed = int(input("Enter a random seed (any positive number): "))
                        if seed < 0:
                            print("Seed must be positive.")
                    except ValueError:
                        print("Please enter a valid number.")

                # send handshake response
                self.seed = seed
                handshake_response = MessageFactory.handshake_response(seed)
                encoded_response = encode_message(handshake_response)
                self.sock.sendto(encoded_response.encode("utf-8"), self.remote_addr)
                print(f"Handshake sent with seed: {seed}")

                self.initialize_rng(seed)

                # start listener
                listener_thread = threading.Thread(target=self.listen_loop, daemon=True)
                listener_thread.start()

                # start chat loop
                print("\n--- Battle Ready! ---")
                print("You go first! Type !attack to make a move.")
                while True:
                    self.chat()

        self.sock.close()
        accept_thread.join()

    def _accept_loop(self):
        """Listens for handshake requests."""

        while self.running:
            try:
                raw_message, sender_address = self.sock.recvfrom(1024)
            except OSError:
                break

            message_string = raw_message.decode("utf-8")
            message_dict = decode_message(message_string)

            if message_dict.get("message_type") == "HANDSHAKE_REQUEST":
                self.request_queue.put((message_string, sender_address))

        try:
            self.sock.settimeout(None)
        except OSError:
            pass

    def process_message(self, message: dict, sender_address: tuple):
        """Processes messages with host-specific handling."""

        # forward to spectator if connected
        if self.spectator_connected and self.comm_mode == "P2P":
            self.reliability.send_with_ack(message, self.spectator_address)

        # handle spectator request
        message_type = message.get("message_type")
        if message_type == MessageType.SPECTATOR_REQUEST:
            self._handle_spectator_request(sender_address)
            return

        # use parent handler
        super().process_message(message, sender_address)

    def _handle_spectator_request(self, spectator_address: tuple):
        """Handles a spectator wanting to join."""

        if self.spectator_connected:
            print("A spectator is already connected.")
            return

        self.spectator_address = spectator_address

        response_message = {"message_type": MessageType.HANDSHAKE_RESPONSE}
        encoded_response = encode_message(response_message)
        self.sock.sendto(encoded_response.encode("utf-8"), spectator_address)

        self.spectator_connected = True
        print(f"Spectator connected from {spectator_address}")

    def _on_battle_setup(self, message: dict):
        """Sends our battle setup after receiving joiners."""

        if self.battle_setup_done:
            return

        if self.remote_addr is None:
            return

        our_battle_setup = MessageFactory.battle_setup(
            communication_mode=self.comm_mode,
            pokemon_name=self.pokemon.name,
        )

        print(f"[HOST] Sending BATTLE_SETUP: {our_battle_setup}")
        self.battle_setup_done = True

        def send_battle_setup():
            self.reliability.send_with_ack(our_battle_setup, self.remote_addr)

        sender_thread = threading.Thread(target=send_battle_setup, daemon=True)
        sender_thread.start()

    def send_message(self, message: dict):
        """Sends a message to joiner and spectator."""
        self.reliability.send_with_ack(message, self.remote_addr)

        if self.spectator_connected and self.comm_mode == "P2P":
            self.reliability.send_with_ack(message, self.spectator_address)


# for backwards compatibility
host = Host
