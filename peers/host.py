import socket
import threading
import queue

class Host:

    saddr = None
    spect = False

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.request_queue = queue.Queue()
        self.running = False
        self.name = ""

    # ---------------------------------------------------------
    #  THREAD: background listener
    # ---------------------------------------------------------
    def _accept_loop(self):
        while self.running:
            try:
                msg, addr = self.sock.recvfrom(1024)
            except OSError:
                break

            self.request_queue.put((msg.decode(), addr))

    # ---------------------------------------------------------
    #  Send newline-separated key-value pairs to a peer
    # ---------------------------------------------------------
    def send_kv(self, addr, **kwargs):

        lines = [f"{k}={v}" for k, v in kwargs.items()]
        message = "\n".join(lines)
        self.sock.sendto(message.encode(), addr)

        # mirror to spectator if active
        if self.spect and self.saddr != addr:
            self.sock.sendto(message.encode(), self.saddr)

    # ---------------------------------------------------------
    #  Main accept loop
    # ---------------------------------------------------------
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

        # ---------------------------------------------------------
        #  MAIN LOOP
        # ---------------------------------------------------------
        while True:
            if not self.request_queue.empty():
                msg, addr = self.request_queue.get()

                print(f"\nPeer at {addr} sent:")
                print(msg)

                # ---------------------------
                # Spectator handshake
                # ---------------------------
                if "message_type=SPECTATOR_REQUEST" in msg:
                    self.saddr = addr
                    self.send_kv(addr, message_type="HANDSHAKE_RESPONSE")
                    self.spect = True
                    print("Spectator connected.")
                    continue

                # ---------------------------
                # Normal peer request
                # ---------------------------
                choice = input("Accept (Y/N)? ").strip().upper()
                if choice != "Y":
                    print("Peer rejected.")
                    continue

                seed = -1
                while seed < 0:
                    try:
                        seed = int(input("Enter seed: "))
                    except:
                        print("Invalid seed.")

                # Send handshake response using KV pairs
                self.send_kv(addr, message_type="HANDSHAKE_RESPONSE", seed=seed)

                print("Handshake sent.\n")

        # unreachable unless main loop exits
        self.running = False
        self.sock.close()
        listener.join()
