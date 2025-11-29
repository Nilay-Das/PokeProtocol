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

                ackmsg = encode_message({
                    "message_type": "ACK",
                    "ack_number": self.seq
                })
                self.sock.sendto(ackmsg.encode("utf-8"), self.jaddr)

            if "ack_number" in kv:
                self.ack = int(kv["ack_number"])

            if "message_type: SPECTATOR_REQUEST" in kv:
                if self.spect != True:
                    self.saddr = addr
                    response = encode_message({"message_type": "HANDSHAKE_RESPONSE"})
                    self.sock.sendto(response.encode("utf-8"), addr)
                    self.spect = True
                    print("Spectator connected.")

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
                handshake = encode_message({"message_type": "HANDSHAKE_RESPONSE", "seed": seed})
                self.sock.sendto(handshake.encode("utf-8"), addr)
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
