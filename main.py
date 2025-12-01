from protocol.battle_state import Move, BattleState, calculate_damage, apply_damage
from protocol.pokemon_db import load_pokemon_db

from peers.host import host
from peers.joiner import joiner
#.from peers.spectator import spectator

print("--- PokeProtocol ---")

# Load the database
db = load_pokemon_db()
comm_mode = 0
pk = 0
#spectator = spectator()
print("h for host\nj for joiner\ns for spectator(not yet implemented)")
choice = input().lower()

if choice == "h":
    while comm_mode != 1 and comm_mode != 2:
        comm_mode = int(input("Choose your mode of communication: \n(1 for P2P)(2 for Broadcast)\n"))
        if comm_mode != 1 and comm_mode != 2:
            print("Please choose a mode of communication")

    while pk <= 0 or pk > 801:
        pk = int(input("Enter the pokedex ID of your chosen pokemon (1-801)\n"))
        if pk > 0 and pk <= 801:
            break
        else:
            print("Invalid pokedex ID")

    if comm_mode == 1:
        # initialize host as P2P
        host = host(db[pk],db,"P2P")
        host.accept()
    else:
        # initialize host as BROADCAST
        host = host(db[pk],db,"BROADCAST")
        host.accept()

if choice == "j":
    while comm_mode != 1 and comm_mode != 2:
        comm_mode = int(input("Choose your mode of communication: \n(1 for P2P)(2 for Broadcast)\n"))
        if comm_mode != 1 and comm_mode != 2:
            print("Please choose a mode of communication")

    while pk <= 0 or pk > 801:
        pk = int(input("Enter the pokedex ID of your chosen pokemon (1-801)\n"))
        if pk > 0 and pk <= 801:
            break
        else:
            print("Invalid pokedex ID")

    if comm_mode == 1:
        hIP = str(input("Enter host IP: "))
        hPort = int(input("Enter host port: "))
        joiner = joiner(db[pk], db, "P2P")
        try:
            joiner.start(hIP, hPort)
        except:
            print("Invalid IP or port")
    else:
        hPort = int(input("Enter host port: "))
        joiner = joiner(db[pk], db, "BROADCAST")
        try:
            joiner.start("255.255.255.255", hPort)
        except:
            print("Invalid IP or port")
if choice == "s":
    hIP = input("Enter host IP: ")
    hPort = input("Enter host port: ")
    #spectator.start(hIP, hPort)
