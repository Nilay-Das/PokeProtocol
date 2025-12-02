"""
PokeProtocol - Main entry point for the Pokemon battle protocol application.
"""

from protocol.pokemon_db import load_pokemon_db
from peers.host import Host
from peers.joiner import Joiner
from peers.spectator import spectator


def get_comm_mode() -> str:
    """
    Get communication mode from user input.

    Returns:
        "P2P" or "BROADCAST"
    """
    while True:
        try:
            choice = int(
                input(
                    "Choose your mode of communication: \n(1 for P2P)(2 for Broadcast)\n"
                )
            )
            if choice == 1:
                return "P2P"
            elif choice == 2:
                return "BROADCAST"
            else:
                print("Please choose a valid mode of communication (1 or 2)")
        except ValueError:
            print("Please enter a valid number")


def get_pokemon_id() -> int:
    """
    Get Pokemon ID from user input.

    Returns:
        Valid Pokedex ID (1-801)
    """
    while True:
        try:
            pk = int(input("Enter the pokedex ID of your chosen pokemon (1-801)\n"))
            if 1 <= pk <= 801:
                return pk
            else:
                print("Invalid pokedex ID. Please enter a number between 1 and 801.")
        except ValueError:
            print("Please enter a valid number")


def get_host_connection_info(comm_mode: str) -> tuple:
    """
    Get host connection info from user.

    Args:
        comm_mode: "P2P" or "BROADCAST"

    Returns:
        Tuple of (host_ip, host_port)
    """
    if comm_mode == "P2P":
        host_ip = input("Enter host IP: ")
    else:
        host_ip = "255.255.255.255"

    while True:
        try:
            host_port = int(input("Enter host port: "))
            return host_ip, host_port
        except ValueError:
            print("Please enter a valid port number")


def run_host(db: dict):
    """
    Run the host peer.

    Args:
        db: Pokemon database
    """
    comm_mode = get_comm_mode()
    pk_id = get_pokemon_id()

    host = Host(db[pk_id], db, comm_mode)
    host.accept()


def run_joiner(db: dict):
    """
    Run the joiner peer.

    Args:
        db: Pokemon database
    """
    comm_mode = get_comm_mode()
    pk_id = get_pokemon_id()
    host_ip, host_port = get_host_connection_info(comm_mode)

    joiner = Joiner(db[pk_id], db, comm_mode)
    try:
        joiner.start(host_ip, host_port)
    except Exception as e:
        print(f"Error connecting: {e}")


def run_spectator(db: dict):
    """
    Run the spectator peer.

    Args:
        db: Pokemon database
    """
    host_ip, host_port = get_host_connection_info("P2P")
    spec = spectator()
    try:
        spec.start(host_ip, host_port)
    except Exception as e:
        print(f"Error connecting spectator: {e}")


def main():
    """Main entry point."""
    print("--- PokeProtocol ---")

    # Load the database
    db = load_pokemon_db()

    print("h for host\nj for joiner\ns for spectator")
    choice = input().lower()

    if choice == "h":
        run_host(db)
    elif choice == "j":
        run_joiner(db)
    elif choice == "s":
        run_spectator(db)
    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()
