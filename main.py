from protocol.battle_state import Move, BattleState, calculate_damage, apply_damage
from protocol.pokemon_db import load_pokemon_db

from peers.host import host
from peers.joiner import joiner

# .from peers.spectator import spectator

print("--- PokeProtocol ---")

# Load the database
db = load_pokemon_db()
pk = 0
# spectator = spectator()
print("h for host\nj for joiner\ns for spectator(not yet implemented)")
choice = input().lower()

if choice == "h":
    while pk <= 0 or pk > 801:
        pk = int(input("Enter the pokedex ID of your chosen pokemon (1-801)"))
        if pk > 0 and pk <= 801:
            break
        else:
            print("Invalid pokedex ID")

    host = host(db[pk])
    host.accept()
elif choice == "j":
    hIP = str(input("Enter host IP: "))
    hPort = int(input("Enter host port: "))

    while pk <= 0 or pk > 801:
        pk = int(input("Enter the pokedex ID of your chosen pokemon (1-801)"))
        if pk > 0 and pk <= 801:
            break
        else:
            print("Invalid pokedex ID")

    joiner = joiner(db[pk])

    try:
        joiner.start(hIP, hPort)
    except:
        print("Invalid IP or port")
elif choice == "s":
    hIP = input("Enter host IP: ")
    hPort = input("Enter host port: ")
    # spectator.start(hIP, hPort)
