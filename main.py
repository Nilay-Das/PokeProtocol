from protocol.battle_state import Move, BattleState, calculate_damage, apply_damage
from protocol.pokemon_db import load_pokemon_db

print("--- Pokemon Battle Simulator ---")

# Load the database
db = load_pokemon_db()

# Get two Pokemon
p1 = db["charmander"]
p2 = db["bulbasaur"]

print("Player 1: " + p1.name)
print("Player 2: " + p2.name)

# Show moves
print("Charmander's moves: " + str(p1.moves))

# Make a move
# We will use the first move for now
move_name = "Basic Attack"
if len(p1.moves) > 0:
    move_name = p1.moves[0]
    
print("Charmander chooses: " + move_name)

# Create the move object
# Let's assume it is a special move and type is fire
move = Move(move_name, 70, "special", "fire")

# Create battle state
state = BattleState(p1, p2)

print("\n--- Battle Start ---")
print(p2.name + " has " + str(p2.current_hp) + " HP.")

# Calculate damage
dmg = calculate_damage(state, move)
print("Calculated damage: " + str(dmg))

# Apply it
apply_damage(state, dmg)

print(p2.name + " now has " + str(p2.current_hp) + " HP.")
print("--- Battle End ---")
