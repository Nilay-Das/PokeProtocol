import socket
import threading
import queue
import time
from protocol.messages import *
from protocol.reliability import ReliableChannel

class host:

    saddr = None
    spect = False
    jaddr = None
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    request_queue = queue.Queue()
    kv_messages = []
    lock = threading.Lock()
    listening = True
    running = False
    name = ""
    seq = 1
    ack = None
    reliability = ReliableChannel(sock)

    #loop for accepting peers, ends when the game begins
    def _accept_loop(self):
        while self.running:
            try:
                msg, addr = self.sock.recvfrom(1024)
            except OSError:
                break

            self.request_queue.put((msg.decode(), addr))

    def send_kv(self, addr, **kwargs):

        lines = [f"{k}: {v}" for k, v in kwargs.items()]
        message = "\n".join(lines)
        self.sock.sendto(message.encode(), addr)

        # mirror to spectator if active
        if self.spect and self.saddr != addr:
            self.sock.sendto(message.encode(), self.saddr)

    def parse_kv(self, raw):
        kv = {}
        for line in raw.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
            else:
                continue
            kv[key.strip()] = val.strip()
        return kv

    def listen_loop(self):
        while self.listening:
            try:
                msg, addr = self.sock.recvfrom(1024)
            except OSError:
                break

            decoded = msg.decode()
            print(f"Host Received:\n{decoded}")

            kv = decode_message(decoded)

            # Store message
            with self.lock:
                self.kv_messages.append(kv)

            # Detect and handle multiple message types
            if kv.get("message_type") == "HANDSHAKE_RESPONSE":
                if "seed" in kv:
                    self.seed = int(kv["seed"])
                    print(f"Set seed to {self.seed}")

            if "sequence_number" in kv:
                incoming_seq = int(kv["sequence_number"])

                if incoming_seq == self.seq + 1:
                    self.seq += 1

                self.send_kv(self.jaddr,message_type= "ACK", ack_number=self.seq)

            if "ack_number" in kv:
                self.ack = int(kv["ack_number"])


            if "message_type: SPECTATOR_REQUEST" in kv:
                self.saddr = addr
                self.send_kv(addr, message_type="HANDSHAKE_RESPONSE")
                self.spect = True
                print("Spectator connected.")
    def chat(self, **kwargs):
        tries = 0
        cur_ack = self.ack
        while tries < 4:
            self.send_kv(self.jaddr, **kwargs)
            time.sleep(0.5)
            if cur_ack != self.ack:
                return
            else:
                tries += 1
        print("Connection lost, ending game")
        self.running = False

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
        print(f"{self.name} Listening on port {port}")

        self.running = True
        listener = threading.Thread(target=self._accept_loop, daemon=True)
        listener.start()

        while True:
            if not self.request_queue.empty():
                msg, addr = self.request_queue.get()

                print(f"\nPeer at {addr} sent:")
                print(msg)

                choice = input("Accept (Y/N)? ").strip().upper()
                if choice != "Y":
                    print("Peer rejected.")
                    continue

                self.jaddr = addr
                self.running = False

                seed = -1
                while seed < 0:
                    try:
                        seed = int(input("Enter seed: "))
                    except:
                        print("Invalid seed.")

                # Send handshake response using KV pairs
                self.send_kv(addr, message_type="HANDSHAKE_RESPONSE", seed=seed)
                print("Handshake sent.\n")

                while True:
                    l = threading.Thread(target=self.listen_loop, daemon=True)
                    l.start()
                    chatmsg = input("Type a message:\n")
                    send = {
                        "message_type": "CHAT_MESSAGE",
                        "sender_name": self.name,
                        "content_type": "TEXT",
                        "message_text": chatmsg
                    }
                    self.reliability.send_with_ack(send, self.jaddr)

        self.running = False
        self.sock.close()
        listener.join()
