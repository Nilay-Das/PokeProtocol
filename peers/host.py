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

    #thread to receive messages
    def _accept_loop(self):
        while self.running:
            try:
                msg, addr = self.sock.recvfrom(1024)
            except OSError:
                break

            self.request_queue.put((msg.decode(), addr))

    
    #general message function to send messages to joiner and spectator if it exists
    def send_kv(self, addr, **kwargs):

        lines = [f"{k}={v}" for k, v in kwargs.items()]
        message = "\n".join(lines)
        self.sock.sendto(message.encode(), addr)

        # mirror to spectator if active
        if self.spect and self.saddr != addr:
            self.sock.sendto(message.encode(), self.saddr)

    # need to change this, main loop for accepting peers
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

                #auto accepts spectators, for now only has 1 max
                if "message_type=SPECTATOR_REQUEST" in msg:
                    if self.spect != True:
                        self.saddr = addr
                        self.send_kv(addr, message_type="HANDSHAKE_RESPONSE")
                        self.spect = True
                        print("Spectator connected.")
                        continue

               #joiner request
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

                # send message, follow this format for send the key value pairs
                self.send_kv(addr, message_type="HANDSHAKE_RESPONSE", seed=seed)

                print("Handshake sent.\n")

        # unreachable unless main loop exits
        self.running = False
        self.sock.close()
        listener.join()
