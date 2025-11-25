import socket
from warnings import catch_warnings

# i think we might need to thread? especially since we need the host to handle at least 2 other peers (spectator and joiner)
# but I'm not sure how we would send data from one thread to another
import threading

# creating a udp socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print("Welcome to PokeProtocol!\nWill you host a game or do you wish to join one? H/J")

choice = ""
# quick try catch
while choice != "J" and choice != "H":
    choice = input().upper()
    (
        print("Invalid input. Please try again.")
        if choice != "J" and choice != "H"
        else None
    )

# host peer logic
if choice == "H":
    # the choice to make the port number above 5000 is completely arbitrary, we can change this if any of you want
    print(
        "Hosting a game now, enter a port you wish to listen on. Make sure it is higher than 5000"
    )
    port = 5000
    while port <= 5000:
        try:
            port = int(input())
        except:
            None
        print("Please enter a valid port number") if port <= 5000 else None

    print(f"Listening on port {port}")
    sock.bind(("", port))

    accept = ""
    # while loop to allow host to accept or reject peers, will need to change this when trying to implement spectating
    while accept != "Y":
        # storing the ip address and port from the incoming socket for later use in communication
        msg, paddr = sock.recvfrom(1024)
        print(f"Received a message from peer from {paddr}")
        print(msg.decode("utf-8"))
        print(
            "Enter 'Y' to proceed to battle with peer, enter anything else to ignore peer "
        )
        accept = input().upper()
    print("Enter a seed value")
    seed = -1
    while seed <= -1:
        try:
            seed = int(input())
        except:
            None
        print("Please enter a valid port number") if seed <= -1 else None

    print("Sending response")
    sock.sendto(str.encode("message type: HANDSHAKE_RESPONSE"), paddr)
    sock.sendto(str.encode(f"seed: {seed}"), paddr)

# 127.0.0.1 (putting this here for copy pasting to test peer logic)

# joiner peer logic
if choice == "J":
    print("Input the destination IP")
    ip = input()
    print("Input the destination port, make sure it is higher than 5000")
    port = 5000
    while port <= 5000:
        try:
            port = int(input())
        except:
            None
        print("Please enter a valid port number") if port <= 5000 else None

    print(f"Sending handshake request to {ip} on port {port}")
    haddr = (ip, port)
    sock.sendto(str.encode("message type: HANDSHAKE_REQUEST"), haddr)
    response = sock.recv(1024)
    seed = sock.recv(1024)
    print(f"Received response from host at {haddr}")
    print(response.decode("utf-8"))
    print(seed.decode("utf-8"))
