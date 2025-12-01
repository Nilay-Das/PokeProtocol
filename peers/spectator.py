import socket
import threading
import time
import queue

from protocol.messages import *
from protocol.reliability import ReliableChannel

class spectator:
    def __init__(self):
        # Spectator doesn't need a Pokemon object
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.name = ""
        self.ack_queue = queue.Queue()
        self.running = False
        self.host_addr = None
        self.seq = 1
        self.connected = False
        # Initialize reliability layer
        self.reliability = ReliableChannel(self.sock, self.ack_queue)

    def start(self, host_ip, host_port):
        # Bind to ephemeral port
        self.sock.bind(("", 0))

        self.name = input("Name this Spectator\n")

        self.running = True
        # Start listener thread
        t = threading.Thread(target=self.listen_loop, daemon=True)
        t.start()

        # Send handshake
        self.handshake(host_ip, host_port)
        print("[Spectator] Request sent. Waiting for Host...")

        # Wait for connection confirmation
        while not self.connected:
            time.sleep(0.1)

        print("--- Connected to Lobby as Spectator ---")
        print("You will see battle updates below. Type to chat.")

        while True:
            self.chat()

    def listen_loop(self):
        while self.running:
            try:
                msg, addr = self.sock.recvfrom(1024)
            except OSError:
                break

            decoded = msg.decode()
            kv = decode_message(decoded)

            # 1. Feed the reliability layer (for outgoing messages waiting for ACKs)
            self.ack_queue.put(kv)

            # 2. Handle Sequence Numbers & Send ACKs (for incoming messages)
            if "sequence_number" in kv:
                incoming_seq = int(kv["sequence_number"])
                
                # Simple sequence tracking
                if incoming_seq >= self.seq:
                    self.seq = incoming_seq + 1

                # Send ACK back to Host so Host doesn't retransmit
                ackmsg = encode_message({
                    "message_type": "ACK",
                    "ack_number": incoming_seq
                })
                self.sock.sendto(ackmsg.encode("utf-8"), self.host_addr)

            # 3. Process Messages for Display
            msg_type = kv.get("message_type")

            if msg_type == "HANDSHAKE_RESPONSE":
                self.connected = True
            
            elif msg_type == "CHAT_MESSAGE":
                sender = kv.get("sender_name", "Unknown")
                text = kv.get("message_text", "")
                print(f"\n[Chat] {sender}: {text}")

            elif msg_type == "BATTLE_SETUP":
                pname = kv.get("pokemon_name", "Unknown")
                print(f"\n[Battle] A player has selected {pname}!")

            elif msg_type == "ATTACK_ANNOUNCE":
                attacker = kv.get("attacker_name", "?")
                move = kv.get("move_name", "?")
                print(f"\n[Battle] {attacker} uses {move}!")

            elif msg_type == "CALCULATION_REPORT":
                # Spectator just trusts the Host's report
                attacker = kv.get("attacker_name", "?")
                damage = kv.get("damage_dealt", "0")
                hp_rem = kv.get("defender_hp_remaining", "?")
                print(f"[Battle] {attacker} dealt {damage} damage. Opponent HP: {hp_rem}")

            elif msg_type == "GAME_OVER":
                winner = kv.get("winner", "?")
                print(f"\n[Battle] GAME OVER! The winner is {winner}!")

    def handshake(self, host_ip, host_port):
        self.host_addr = (host_ip, int(host_port))
        # Send raw request first
        req = encode_message({"message_type": "SPECTATOR_REQUEST"})
        self.sock.sendto(req.encode("utf-8"), self.host_addr)

    def chat(self):
        chatmsg = input()
        # Don't send empty messages
        if not chatmsg.strip():
            return

        send = {
            "message_type": "CHAT_MESSAGE",
            "sender_name": self.name,
            "content_type": "TEXT",
            "message_text": chatmsg
        }
        # Use reliability to ensure chat reaches host
        self.reliability.send_with_ack(send, self.host_addr)
