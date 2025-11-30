import csv
import os
from protocol.battle_state import Pokemon

# Get the path to the CSV file
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
data_dir = os.path.join(parent_dir, "data")
DEFAULT_CSV_PATH = os.path.join(data_dir, "pokemon.csv")

def load_pokemon_db(csv_path=DEFAULT_CSV_PATH):
    print("Loading Pokemon from: " + csv_path)
    
    db = {}
    
    # Open the file
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            name = row["name"]

            dex_id = int(row["pokedex_number"])
            # Get stats
            hp = int(float(row["hp"]))
            attack = int(float(row["attack"]))
            defense = int(float(row["defense"]))
            sp_attack = int(float(row["sp_attack"]))
            sp_defense = int(float(row["sp_defense"]))
            
            type1 = row["type1"]
            type2 = row.get("type2", "")
            if type2 == "":
                type2 = None
                
            # Get multipliers
            type_multipliers = {}
            for key in row:
                if key.startswith("against_"):
                    # key is like "against_fire but we want just "fire"
                    move_type = key.replace("against_", "")
                    
                    value_str = row[key]
                    try:
                        value = float(value_str)
                        type_multipliers[move_type] = value
                    except:
                        type_multipliers[move_type] = 1.0
                        
            # Get moves
            # The CSV has them like "['Move1', 'Move2']"
            abilities_str = row.get("abilities", "[]")
            
            # Remove brackets and quotes manually
            clean_str = abilities_str.replace("[", "").replace("]", "").replace("'", "")
            
            moves_list = []
            parts = clean_str.split(",")
            for part in parts:
                move_name = part.strip()
                if move_name != "":
                    moves_list.append(move_name)
                    
            # Create the Pokemon object
            p = Pokemon(name, hp, hp, attack, sp_attack, defense, sp_defense, type1, type2, type_multipliers, moves_list)
            
            # Save it (lowercase name)
            db[name.lower()] = p
            db[dex_id] = p

    print("Loaded " + str(len(db)/2) + " Pokemon.")
    return db

