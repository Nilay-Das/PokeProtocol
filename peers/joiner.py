import socket
import threading
import time
import queue
from protocol.messages import *
from protocol.reliability import ReliableChannel


class joiner:
    #attributes
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    name = "Joiner"
    request_queue = queue.Queue()
    running = False
    host_addr = None
    kv_messages = []
    lock = threading.Lock()
    seed = None
    seq = 1
    ack = None
    reliability = ReliableChannel(sock)

    def wait_for_seed(self, timeout=None):

        start = time.time()

        while self.seed is None:
            time.sleep(0.05)
            if timeout is not None and (time.time() - start) > timeout:
                return False

        return True

    def parse_kv(self, raw):
        kv = {}
        for line in raw.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
            else:
                continue
            kv[key.strip()] = val.strip()
        return kv

    def send_kv(self, addr, **kwargs):

        lines = [f"{k}: {v}" for k, v in kwargs.items()]
        message = "\n".join(lines)
        self.sock.sendto(message.encode(), addr)

    def listen_loop(self):
        while self.running:
            try:
                msg, addr = self.sock.recvfrom(1024)
            except OSError:
                break

            decoded = msg.decode()
            print(f"[Joiner] Received:\n{decoded}")

            kv = decode_message(decoded)

            # Store message
            with self.lock:
                self.kv_messages.append(kv)

            # Detect and handle multiple message types
            if "seed" in kv:
                self.seed = int(kv["seed"])
            if "sequence_number" in kv:
                incoming_seq = int(kv["sequence_number"])

                if incoming_seq == self.seq + 1:
                    self.seq += 1

                self.send_kv(self.host_addr,message_type="ACK", ack_number=self.seq)
            if "ack_number" in kv:
                self.ack = int(kv["ack_number"])

    def handshake(self, host_ip, host_port):
        self.host_addr = (host_ip, host_port)
        self.send_kv(self.host_addr, message_type="HANDSHAKE_REQUEST")

    def chat(self, **kwargs):
        tries = 0
        cur_ack = self.ack
        while tries < 4:
            self.send_kv(self.host_addr, **kwargs)
            time.sleep(0.5)
            if cur_ack != self.ack:
                return
            else:
                tries += 1
        print("Connection lost, ending game")
        self.running = False

    def start(self, host_ip, host_port):
        reliability = self.reliability
        # bind local ephemeral port
        self.sock.bind(("", 0))
        print(f"[Joiner] Using port {self.sock.getsockname()[1]}")

        self.running = True
        t = threading.Thread(target=self.listen_loop, daemon=True)
        t.start()

        # Send handshake request
        self.handshake(host_ip, host_port)

        print("[Joiner] Handshake sent. Waiting for Host...")
        print("If host has not sent seed please Ctrl+C to end program")

        while self.seed is None:
            time.sleep(0.5)

        while True:

            chatmsg = input("Type a message:\n")
            send = {
                "message_type": "CHAT_MESSAGE",
                "sender_name": self.name,
                "content_type": "TEXT",
                "message_text": chatmsg
            }

            self.reliability.send_with_ack(send, self.host_addr)


