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

    def _accept_loop(self):
        """Background thread: NO input() here."""
        while self.running:
            try:
                msg, addr = self.sock.recvfrom(1024)
            except OSError:
                break

            # Push request to queue
            self.request_queue.put((msg.decode(), addr))

    def response(self, message, addr):
        self.sock.sendto(message.encode(), addr)
        if self.spect:
            self.sock.sendto(message.encode(), self.saddr)

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
        thread = threading.Thread(target=self._accept_loop)
        thread.start()

        # Main loop handles input
        while True:
            if not self.request_queue.empty():
                msg, addr = self.request_queue.get()

                print(f"\nPeer at {addr} wants to join")
                print(msg)

                if msg == "message type: SPECTATOR_REQUEST":
                    self.saddr = addr
                    self.sock.sendto(b"message type: HANDSHAKE_RESPONSE", self.saddr)
                    self.spect = True
                    continue

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

                self.response("message type: HANDSHAKE_RESPONSE", addr)
                self.response(f"seed: {seed}", addr)

                print("Handshake sent.\n")

        self.running = False
        self.sock.close()
        thread.join()