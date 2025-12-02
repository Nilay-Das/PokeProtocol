"""
=============================================================================
POKEPROTOCOL - Pokemon Battle Protocol Application
=============================================================================

WHAT IS THIS APPLICATION?
-------------------------
PokeProtocol is a peer-to-peer Pokemon battle game that runs over a network.
Two players can connect and battle their Pokemon against each other!

HOW IT WORKS
------------
1. One player starts as the HOST (the server)
2. Another player starts as the JOINER (the client)
3. Optionally, others can join as SPECTATORS to watch

The HOST waits for connections, the JOINER connects to the HOST,
and they battle! The HOST always goes first.

RUNNING THE GAME
----------------
1. Run this file: python main.py
2. Choose your role:
   - 'h' for Host (start a new game)
   - 'j' for Joiner (join an existing game)
   - 's' for Spectator (watch a game)
3. Follow the prompts!

Example:
   Player 1 (Host):
       > python main.py
       > h
       > MyName
       > 192.168.1.100  (their IP address)
       > 5001           (port to listen on)
       > Y              (accept joiner)
       > 12345          (random seed)
   
   Player 2 (Joiner):
       > python main.py
       > j
       > TheirName
       > 192.168.1.100  (host's IP address)
       > 5001           (host's port)

COMMUNICATION MODES
-------------------
P2P (Peer-to-Peer):
    Direct connection between two computers.
    You need to know the other player's IP address.
    Works over the internet!

BROADCAST:
    Send messages to everyone on the local network.
    Uses the special address 255.255.255.255.
    Only works on the same WiFi/network!

=============================================================================
"""

from protocol.pokemon_db import load_pokemon_db
from peers.host import Host
from peers.joiner import Joiner
from peers.spectator import spectator


def get_communication_mode() -> str:
    """
    Ask the user which communication mode to use.
    
    Returns:
        "P2P" for peer-to-peer (direct connection)
        "BROADCAST" for local network broadcast
    """
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
    """
    Ask the user to choose a Pokemon by Pokedex ID.
    
    The Pokemon database contains Pokemon with IDs from 1 to 801.
    
    Returns:
        A valid Pokedex ID (1-801)
    """
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
    """
    Ask for the Host's IP address and port.
    
    This is used by Joiners and Spectators to know where to connect.
    
    Args:
        comm_mode: "P2P" or "BROADCAST"
    
    Returns:
        Tuple of (ip_address, port_number)
    """
    # Get IP address
    if comm_mode == "P2P":
        # In P2P mode, we need the actual IP address
        print("\nEnter the Host's IP address:")
        host_ip = input("IP: ")
    else:
        # In broadcast mode, we use the broadcast address
        host_ip = "255.255.255.255"
        print(f"\nUsing broadcast address: {host_ip}")
    
    # Get port number
    print("Enter the Host's port number:")
    while True:
        try:
            host_port = int(input("Port: "))
            return host_ip, host_port
        except ValueError:
            print("Please enter a valid number")


def run_host(pokemon_database: dict):
    """
    Run the Host peer.
    
    The Host:
    - Waits for connections
    - Sets the random seed
    - Goes first in battle
    
    Args:
        pokemon_database: Dictionary of all Pokemon
    """
    print("\n=== Starting as HOST ===")
    
    # Get settings
    comm_mode = get_communication_mode()
    pokemon_id = get_pokemon_id()
    
    # Get the Pokemon from the database
    my_pokemon = pokemon_database[pokemon_id]
    print(f"\nYou chose: {my_pokemon.name}!")
    
    # Create and start the Host
    host = Host(my_pokemon, pokemon_database, comm_mode)
    host.accept()


def run_joiner(pokemon_database: dict):
    """
    Run the Joiner peer.
    
    The Joiner:
    - Connects to an existing Host
    - Receives the random seed
    - Goes second in battle
    
    Args:
        pokemon_database: Dictionary of all Pokemon
    """
    print("\n=== Starting as JOINER ===")
    
    # Get settings
    comm_mode = get_communication_mode()
    pokemon_id = get_pokemon_id()
    host_ip, host_port = get_host_connection_info(comm_mode)
    
    # Get the Pokemon from the database
    my_pokemon = pokemon_database[pokemon_id]
    print(f"\nYou chose: {my_pokemon.name}!")
    
    # Create and start the Joiner
    joiner = Joiner(my_pokemon, pokemon_database, comm_mode)
    
    try:
        joiner.start(host_ip, host_port)
    except Exception as error:
        print(f"Error connecting to Host: {error}")


def run_spectator(pokemon_database: dict):
    """
    Run the Spectator peer.
    
    The Spectator:
    - Connects to an existing Host
    - Watches the battle without participating
    - Can send chat messages
    
    Args:
        pokemon_database: Dictionary of all Pokemon (not really used)
    """
    print("\n=== Starting as SPECTATOR ===")
    
    # Get connection info (spectators always use P2P)
    host_ip, host_port = get_host_connection_info("P2P")
    
    # Create and start the Spectator
    spec = spectator()
    
    try:
        spec.start(host_ip, host_port)
    except Exception as error:
        print(f"Error connecting as spectator: {error}")


def main():
    """
    Main entry point for the PokeProtocol application.
    
    Shows a menu and lets the user choose their role:
    - Host: Start a new game
    - Joiner: Join an existing game
    - Spectator: Watch a game
    """
    print("=" * 50)
    print("       POKEPROTOCOL - Pokemon Battle!")
    print("=" * 50)
    
    # Load the Pokemon database
    print("\nLoading Pokemon database...")
    pokemon_database = load_pokemon_db()
    print(f"Loaded {len(pokemon_database)} Pokemon!")
    
    # Show the menu
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


# This is the standard Python way to run code only when this file
# is executed directly (not imported as a module)
if __name__ == "__main__":
    main()
