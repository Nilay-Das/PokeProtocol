"""
Main file for PokeProtocol - a Pokemon battle game over the network.
Run this and pick host, joiner, or spectator.
"""

from protocol.pokemon_db import load_pokemon_db
from peers.host import Host
from peers.joiner import Joiner
from peers.spectator import spectator


def get_communication_mode() -> str:
    """Asks user for P2P or broadcast mode."""
    
    print("\nChoose communication mode:")
    print("  1 = P2P (direct connection - works over internet)")
    print("  2 = Broadcast (local network only)")
    
    while True:
        try:
            choice = int(input("Enter 1 or 2: "))
            if choice == 1:
                return "P2P"
            elif choice == 2:
                return "BROADCAST"
            else:
                print("Please enter 1 or 2")
        except ValueError:
            print("Please enter a number")


def get_pokemon_id() -> int:
    """Asks user to pick a pokemon by pokedex number."""
    
    print("\nChoose your Pokemon!")
    print("Enter a Pokedex ID from 1 to 801")
    print("(Examples: 1=Bulbasaur, 4=Charmander, 7=Squirtle, 25=Pikachu)")
    
    while True:
        try:
            pokemon_id = int(input("Pokedex ID: "))
            if 1 <= pokemon_id <= 801:
                return pokemon_id
            else:
                print("ID must be between 1 and 801")
        except ValueError:
            print("Please enter a number")


def get_host_connection_info(comm_mode: str) -> tuple:
    """Gets the host IP and port from user."""
    
    # get IP
    if comm_mode == "P2P":
        print("\nEnter the Host's IP address:")
        host_ip = input("IP: ")
    else:
        host_ip = "255.255.255.255"
        print(f"\nUsing broadcast address: {host_ip}")
    
    # get port
    print("Enter the Host's port number:")
    while True:
        try:
            host_port = int(input("Port: "))
            return host_ip, host_port
        except ValueError:
            print("Please enter a valid number")


def run_host(pokemon_database: dict):
    """Runs the host peer."""
    
    print("\n=== Starting as HOST ===")
    
    comm_mode = get_communication_mode()
    pokemon_id = get_pokemon_id()
    
    my_pokemon = pokemon_database[pokemon_id]
    print(f"\nYou chose: {my_pokemon.name}!")
    
    host = Host(my_pokemon, pokemon_database, comm_mode)
    host.accept()


def run_joiner(pokemon_database: dict):
    """Runs the joiner peer."""
    
    print("\n=== Starting as JOINER ===")
    
    comm_mode = get_communication_mode()
    pokemon_id = get_pokemon_id()
    host_ip, host_port = get_host_connection_info(comm_mode)
    
    my_pokemon = pokemon_database[pokemon_id]
    print(f"\nYou chose: {my_pokemon.name}!")
    
    joiner = Joiner(my_pokemon, pokemon_database, comm_mode)
    
    try:
        joiner.start(host_ip, host_port)
    except Exception as error:
        print(f"Error connecting to Host: {error}")


def run_spectator(pokemon_database: dict):
    """Runs the spectator peer."""
    
    print("\n=== Starting as SPECTATOR ===")
    
    host_ip, host_port = get_host_connection_info("P2P")
    
    spec = spectator()
    
    try:
        spec.start(host_ip, host_port)
    except Exception as error:
        print(f"Error connecting as spectator: {error}")


def main():
    """Main function - shows menu and starts the game."""
    
    print("=" * 50)
    print("       POKEPROTOCOL - Pokemon Battle!")
    print("=" * 50)
    
    # load pokemon
    print("\nLoading Pokemon database...")
    pokemon_database = load_pokemon_db()
    print(f"Loaded {len(pokemon_database)} Pokemon!")
    
    # show menu
    print("\nChoose your role:")
    print("  h = Host (start a new game)")
    print("  j = Joiner (join an existing game)")
    print("  s = Spectator (watch a game)")
    
    choice = input("\nEnter h, j, or s: ").lower().strip()
    
    if choice == "h":
        run_host(pokemon_database)
    elif choice == "j":
        run_joiner(pokemon_database)
    elif choice == "s":
        run_spectator(pokemon_database)
    else:
        print(f"Unknown choice: '{choice}'")
        print("Please run the program again and enter h, j, or s")


if __name__ == "__main__":
    main()
