import socket
from protocol.messages import decode_message, encode_message

class Spectator:

    def __init__(self, host_ip, host_port):
        self.host_addr = (host_ip, host_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("", 0))

        print(f"[SPECTATOR] Local socket: {self.sock.getsockname()}")


    def connect(self):
        print("[SPECTATOR] Sending SPECTATOR_REQUEST...")

        msg = encode_message({"message_type": "SPECTATOR_REQUEST"})
        self.sock.sendto(msg.encode("utf-8"), self.host_addr)

        data, _ = self.sock.recvfrom(1024)
        kv = decode_message(data.decode())

        if kv.get("message_type") == "HANDSHAKE_RESPONSE":
            print("[SPECTATOR] Connected successfully.")
        else:
            print("[SPECTATOR] Unexpected response:", kv)


    def listen(self):
        print("\n[SPECTATOR] Watching the match...\n")

        while True:
            data, _ = self.sock.recvfrom(1024)
            kv = decode_message(data.decode())

            # Send ACK for reliable packets
            if "sequence_number" in kv:
                ackmsg = encode_message({
                    "message_type": "ACK",
                    "ack_number": kv["sequence_number"]
                })
                self.sock.sendto(ackmsg.encode("utf-8"), self.host_addr)

            mtype = kv.get("message_type")



            if mtype == "CHAT_MESSAGE":
                if kv.get("content_type") == "TEXT":
                    print(f"[{kv['sender_name']}]: {kv['message_text']}")
                elif kv.get("content_type") == "STICKER":
                    print(f"[{kv['sender_name']}] sent sticker: {kv['message_text']}")

            elif mtype == "BATTLE_SETUP":
                print("[SETUP] Pokemon:", kv.get("pokemon_name"))

            elif mtype == "ATTACK_ANNOUNCE":
                print(
                    f"[ATTACK] {kv.get('attacker_name')} used "
                    f"{kv.get('move_name')} on "
                    f"{kv.get('defender_name')}"
                )

            elif mtype == "CALCULATION_REPORT":
                print(
                    f"[DAMAGE] {kv.get('defender_name')} "
                    f"took {kv.get('damage_dealt')} damage "
                    f"(HP: {kv.get('defender_hp_remaining')})"
                )

            elif mtype == "GAME_OVER":
                print(
                    f"\n🏆 GAME OVER\n"
                    f"{kv.get('winner')} defeated "
                    f"{kv.get('loser')}"
                )
                break

            elif mtype != "ACK":
                print("[EVENT]", kv)

        self.sock.close()

if __name__ == "__main__":

    ip = input("Enter host IP: ")
    port = int(input("Enter host PORT: "))

    spec = Spectator(ip, port)
    spec.connect()
    spec.listen()
