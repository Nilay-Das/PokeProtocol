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

    def start(self, host_ip, host_port):
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
            self.chat()

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
                ackmsg = encode_message({
                    "message_type": "ACK",
                    "ack_number": self.seq
                })
                self.sock.sendto(ackmsg.encode("utf-8"), self.host_addr)
            if "ack_number" in kv:
                self.ack = int(kv["ack_number"])

    def handshake(self, host_ip, host_port):
        self.host_addr = (host_ip, host_port)
        handshake = encode_message({"message_type":"HANDSHAKE_REQUEST"})
        self.sock.sendto(handshake.encode("utf-8"), self.host_addr)

    def chat(self):
        chatmsg = input("Type a message:\n")
        send = {
            "message_type": "CHAT_MESSAGE",
            "sender_name": self.name,
            "content_type": "TEXT",
            "message_text": chatmsg
        }

        self.reliability.send_with_ack(send, self.host_addr)


