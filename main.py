from protocol.battle_state import Move, BattleState, calculate_damage, apply_damage
from protocol.pokemon_db import load_pokemon_db

from peers.host import host
from peers.joiner import joiner
from peers.spectator import spectator

print("--- Pokemon Battle Simulator ---")

# Load the database
db = load_pokemon_db()

host = host()
joiner = joiner()
spectator = spectator()
print("h for host, j for joiner, s for spectator(not yet implemented)")
print("For host, please just use port 5001 this is a test for now")
choice = input()

if choice == "h":
    host.accept()
if choice == "j":
    joiner.start("127.0.0.1", 5001)
if choice == "s":
    spectator.start("127.0.0.1", 5001)

print(p2.name + " now has " + str(p2.current_hp) + " HP.")
print("--- Battle End ---")
