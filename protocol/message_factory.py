"""
=============================================================================
MESSAGE FACTORY - Creating Protocol Messages the Right Way
=============================================================================

WHAT IS THIS FILE?
------------------
This file provides functions to create all the different message types
in our protocol. Instead of creating message dictionaries by hand
(and risking typos or missing fields), use these functions!

WHAT IS A "FACTORY"?
--------------------
In programming, a "factory" is something that creates objects for you.
It's like ordering food at a restaurant - you don't go into the kitchen
and cook it yourself, you just tell the waiter what you want.

Instead of:
    message = {
        "message_type": "ATTACK_ANNOUNCE",
        "move_name": "Thunderbolt"
    }

Use:
    message = MessageFactory.attack_announce("Thunderbolt")

WHY USE A FACTORY?
------------------
1. Consistency: Messages always have the correct format
2. No typos: Can't misspell "message_type" if you don't type it
3. Documentation: Each function shows exactly what parameters are needed
4. RFC Compliance: We know these messages match the specification


HOW TO USE THIS FILE
--------------------
    from protocol.message_factory import MessageFactory

    # Create an attack announcement
    attack = MessageFactory.attack_announce("Thunderbolt")
    # Returns: {"message_type": "ATTACK_ANNOUNCE", "move_name": "Thunderbolt"}

    # Create a chat message
    chat = MessageFactory.chat_text("Player1", "Good game!")
    # Returns: {"message_type": "CHAT_MESSAGE", "sender_name": "Player1", ...}

=============================================================================
"""

from protocol.constants import (
    MessageType,
    ContentType,
    DEFAULT_SPECIAL_ATTACK_USES,
    DEFAULT_SPECIAL_DEFENSE_USES,
)


class MessageFactory:
    """
    Factory class for creating protocol-compliant messages.
    
    All methods are @staticmethod, meaning you don't need to create
    an instance of MessageFactory. Just call the methods directly:
        
        MessageFactory.attack_announce("Tackle")  # Correct!
        
    NOT:
        factory = MessageFactory()
        factory.attack_announce("Tackle")  # Works but unnecessary
    """

    # =========================================================================
    # CONNECTION MESSAGES
    # Used when peers first connect to each other
    # =========================================================================

    @staticmethod
    def handshake_request() -> dict:
        """
        Create a HANDSHAKE_REQUEST message.
        
        This is sent by the Joiner to the Host to request a connection.
        It's like knocking on someone's door to ask if you can come in.
        
        Returns:
            A message dictionary ready to be sent
        
        Example:
            # Joiner wants to connect to Host
            request = MessageFactory.handshake_request()
            channel.send_with_ack(request, host_address)
            
            # Result: {"message_type": "HANDSHAKE_REQUEST"}
        """
        return {"message_type": MessageType.HANDSHAKE_REQUEST}

    @staticmethod
    def handshake_response(seed: int) -> dict:
        """
        Create a HANDSHAKE_RESPONSE message.
        
        This is sent by the Host to accept the Joiner's connection request.
        It includes a random seed that both peers will use to ensure
        their random number generators produce the same results.
        
        Args:
            seed: A random number to synchronize both peers' RNG.
                  This ensures both peers calculate the same damage.
        
        Returns:
            A message dictionary ready to be sent
        
        Example:
            # Host accepts the connection with seed 12345
            response = MessageFactory.handshake_response(12345)
            channel.send_with_ack(response, joiner_address)
            
            # Result: {"message_type": "HANDSHAKE_RESPONSE", "seed": 12345}
        """
        return {"message_type": MessageType.HANDSHAKE_RESPONSE, "seed": seed}

    @staticmethod
    def spectator_request() -> dict:
        """
        Create a SPECTATOR_REQUEST message.
        
        This is sent by a spectator who wants to watch the battle
        without participating. Spectators receive battle updates
        but cannot attack or chat.
        
        Returns:
            A message dictionary ready to be sent
        
        Example:
            # Spectator wants to watch the battle
            request = MessageFactory.spectator_request()
            channel.send_with_ack(request, host_address)
            
            # Result: {"message_type": "SPECTATOR_REQUEST"}
        """
        return {"message_type": MessageType.SPECTATOR_REQUEST}

    # =========================================================================
    # BATTLE SETUP MESSAGES
    # Exchanged after connection, before battle starts
    # =========================================================================

    @staticmethod
    def battle_setup(
        communication_mode: str,
        pokemon_name: str,
        special_attack_uses: int = DEFAULT_SPECIAL_ATTACK_USES,
        special_defense_uses: int = DEFAULT_SPECIAL_DEFENSE_USES,
    ) -> dict:
        """
        Create a BATTLE_SETUP message.
        
        Both peers send this to share their chosen Pokemon and stat boost
        counts. After both peers exchange BATTLE_SETUP, the battle begins!
        
        Args:
            communication_mode: How peers communicate
                                "P2P" = direct connection
                                "BROADCAST" = local network broadcast
            
            pokemon_name: The name of the chosen Pokemon (e.g., "Pikachu")
            
            special_attack_uses: How many special attack boosts this player has.
                                Default is 5.
            
            special_defense_uses: How many special defense boosts this player has.
                                 Default is 5.
        
        Returns:
            A message dictionary ready to be sent
        
        Example:
            # Player chose Pikachu in P2P mode
            setup = MessageFactory.battle_setup(
                communication_mode="P2P",
                pokemon_name="Pikachu"
            )
            channel.send_with_ack(setup, opponent_address)
            
            # Result:
            # {
            #     "message_type": "BATTLE_SETUP",
            #     "communication_mode": "P2P",
            #     "pokemon_name": "Pikachu",
            #     "stat_boosts": {"special_attack_uses": 5, "special_defense_uses": 5}
            # }
        """
        message = {
            "message_type": MessageType.BATTLE_SETUP,
            "communication_mode": communication_mode,
            "pokemon_name": pokemon_name,
            "stat_boosts": {
                "special_attack_uses": special_attack_uses,
                "special_defense_uses": special_defense_uses,
            },
        }
        return message

    # =========================================================================
    # TURN-BASED BATTLE MESSAGES
    # These form the "4-step handshake" for each attack:
    #   1. ATTACK_ANNOUNCE (attacker sends)
    #   2. DEFENSE_ANNOUNCE (defender sends)
    #   3. CALCULATION_REPORT (both send)
    #   4. CALCULATION_CONFIRM (one sends to agree)
    # =========================================================================

    @staticmethod
    def attack_announce(move_name: str) -> dict:
        """
        Create an ATTACK_ANNOUNCE message.
        
        This is Step 1 of the 4-step attack handshake.
        The attacker tells the defender what move they're using.
        
        Args:
            move_name: The name of the move being used (e.g., "Thunderbolt")
        
        Returns:
            A message dictionary ready to be sent
        
        Example:
            # Pikachu uses Thunderbolt!
            attack = MessageFactory.attack_announce("Thunderbolt")
            channel.send_with_ack(attack, opponent_address)
            
            # Result: {"message_type": "ATTACK_ANNOUNCE", "move_name": "Thunderbolt"}
        """
        return {"message_type": MessageType.ATTACK_ANNOUNCE, "move_name": move_name}

    @staticmethod
    def defense_announce() -> dict:
        """
        Create a DEFENSE_ANNOUNCE message.
        
        This is Step 2 of the 4-step attack handshake.
        The defender confirms they received the attack announcement.
        
        Per the RFC specification, this message only contains the message_type.
        It's simply an acknowledgment that the attack was received.
        
        Returns:
            A message dictionary ready to be sent
        
        Example:
            # Defender acknowledges the incoming attack
            defense = MessageFactory.defense_announce()
            channel.send_with_ack(defense, opponent_address)
            
            # Result: {"message_type": "DEFENSE_ANNOUNCE"}
        """
        return {"message_type": MessageType.DEFENSE_ANNOUNCE}

    @staticmethod
    def calculation_report(
        attacker_name: str,
        move_used: str,
        attacker_remaining_health: int,
        damage_dealt: int,
        defender_hp_remaining: int,
        status_message: str,
    ) -> dict:
        """
        Create a CALCULATION_REPORT message.
        
        This is Step 3 of the 4-step attack handshake.
        Both peers calculate the damage and send their results.
        This allows them to verify they got the same answer.
        
        Args:
            attacker_name: Name of the attacking Pokemon (e.g., "Pikachu")
            
            move_used: Name of the move (e.g., "Thunderbolt")
            
            attacker_remaining_health: The attacker's current HP
            
            damage_dealt: How much damage was calculated
            
            defender_hp_remaining: Defender's HP after taking damage
            
            status_message: A description of what happened
                           (e.g., "Pikachu used Thunderbolt! It was super effective!")
        
        Returns:
            A message dictionary ready to be sent
        
        Example:
            # Report that Thunderbolt did 50 damage
            report = MessageFactory.calculation_report(
                attacker_name="Pikachu",
                move_used="Thunderbolt",
                attacker_remaining_health=100,
                damage_dealt=50,
                defender_hp_remaining=45,
                status_message="Pikachu used Thunderbolt! It was super effective!"
            )
            channel.send_with_ack(report, opponent_address)
        """
        message = {
            "message_type": MessageType.CALCULATION_REPORT,
            "attacker": attacker_name,
            "move_used": move_used,
            "remaining_health": str(attacker_remaining_health),
            "damage_dealt": str(damage_dealt),
            "defender_hp_remaining": str(defender_hp_remaining),
            "status_message": status_message,
        }
        return message

    @staticmethod
    def calculation_confirm() -> dict:
        """
        Create a CALCULATION_CONFIRM message.
        
        This is Step 4a of the 4-step attack handshake.
        Sent when both peers calculated the same damage.
        It means "I agree with your calculation, let's continue."
        
        Per the RFC specification, this message only contains message_type.
        
        Returns:
            A message dictionary ready to be sent
        
        Example:
            # Calculations match, confirm and move on
            confirm = MessageFactory.calculation_confirm()
            channel.send_with_ack(confirm, opponent_address)
            
            # Result: {"message_type": "CALCULATION_CONFIRM"}
        """
        return {"message_type": MessageType.CALCULATION_CONFIRM}

    @staticmethod
    def resolution_request(
        attacker_name: str,
        move_used: str,
        damage_dealt: int,
        defender_hp_remaining: int,
    ) -> dict:
        """
        Create a RESOLUTION_REQUEST message.
        
        This is Step 4b of the 4-step attack handshake.
        Sent when the two peers calculated DIFFERENT damage values.
        This should be rare if both peers use the same RNG seed!
        
        Args:
            attacker_name: Name of the attacking Pokemon
            move_used: Name of the move used
            damage_dealt: The damage value this peer calculated
            defender_hp_remaining: The HP value this peer calculated
        
        Returns:
            A message dictionary ready to be sent
        
        Example:
            # Calculations don't match, request resolution
            resolution = MessageFactory.resolution_request(
                attacker_name="Pikachu",
                move_used="Thunderbolt",
                damage_dealt=48,  # This peer calculated 48
                defender_hp_remaining=47
            )
            channel.send_with_ack(resolution, opponent_address)
        """
        message = {
            "message_type": MessageType.RESOLUTION_REQUEST,
            "attacker": attacker_name,
            "move_used": move_used,
            "damage_dealt": str(damage_dealt),
            "defender_hp_remaining": str(defender_hp_remaining),
        }
        return message

    # =========================================================================
    # GAME END MESSAGE
    # =========================================================================

    @staticmethod
    def game_over(winner_name: str, loser_name: str) -> dict:
        """
        Create a GAME_OVER message.
        
        Sent when one Pokemon's HP reaches 0. The battle is over!
        
        Args:
            winner_name: Name of the Pokemon that won
            loser_name: Name of the Pokemon that lost (fainted)
        
        Returns:
            A message dictionary ready to be sent
        
        Example:
            # Charmander fainted, Pikachu wins!
            game_over = MessageFactory.game_over(
                winner_name="Pikachu",
                loser_name="Charmander"
            )
            channel.send_with_ack(game_over, opponent_address)
            
            # Result:
            # {"message_type": "GAME_OVER", "winner": "Pikachu", "loser": "Charmander"}
        """
        return {
            "message_type": MessageType.GAME_OVER,
            "winner": winner_name,
            "loser": loser_name,
        }

    # =========================================================================
    # CHAT MESSAGES
    # For player communication during the battle
    # =========================================================================

    @staticmethod
    def chat_text(sender_name: str, message_text: str) -> dict:
        """
        Create a text CHAT_MESSAGE.
        
        Players can send text messages to each other during battle.
        This is for regular text messages (not stickers).
        
        Args:
            sender_name: Name of the player sending the message
            message_text: The text of the message
        
        Returns:
            A message dictionary ready to be sent
        
        Example:
            # Player1 says "Good luck!"
            chat = MessageFactory.chat_text("Player1", "Good luck!")
            channel.send_with_ack(chat, opponent_address)
            
            # Result:
            # {
            #     "message_type": "CHAT_MESSAGE",
            #     "sender_name": "Player1",
            #     "content_type": "TEXT",
            #     "message_text": "Good luck!"
            # }
        """
        message = {
            "message_type": MessageType.CHAT_MESSAGE,
            "sender_name": sender_name,
            "content_type": ContentType.TEXT,
            "message_text": message_text,
        }
        return message

    @staticmethod
    def chat_sticker(sender_name: str, sticker_data: str) -> dict:
        """
        Create a sticker CHAT_MESSAGE.
        
        Players can send stickers (small images) to each other.
        The sticker data is encoded as a Base64 string.
        
        What is Base64?
            It's a way to represent binary data (like an image)
            as a text string. This lets us send images through
            our text-based protocol.
        
        Args:
            sender_name: Name of the player sending the sticker
            sticker_data: The sticker image encoded as a Base64 string
        
        Returns:
            A message dictionary ready to be sent
        
        Example:
            # Player1 sends a sticker
            sticker = MessageFactory.chat_sticker("Player1", "SGVsbG8gV29ybGQh...")
            channel.send_with_ack(sticker, opponent_address)
            
            # Result:
            # {
            #     "message_type": "CHAT_MESSAGE",
            #     "sender_name": "Player1",
            #     "content_type": "STICKER",
            #     "sticker_data": "SGVsbG8gV29ybGQh..."
            # }
        """
        message = {
            "message_type": MessageType.CHAT_MESSAGE,
            "sender_name": sender_name,
            "content_type": ContentType.STICKER,
            "sticker_data": sticker_data,
        }
        return message

    # =========================================================================
    # RELIABILITY LAYER MESSAGE
    # =========================================================================

    @staticmethod
    def ack(ack_number: int) -> dict:
        """
        Create an ACK (acknowledgment) message.
        
        This is used by the reliability layer to confirm that a
        message was received. Each ACK includes the sequence number
        of the message it's acknowledging.
        
        Args:
            ack_number: The sequence number of the message being acknowledged.
                       This should match the sequence_number from the
                       message we received.
        
        Returns:
            A message dictionary ready to be sent
        
        Example:
            # We received a message with sequence_number 5
            # Send back an ACK to confirm
            ack = MessageFactory.ack(5)
            sock.sendto(encode_message(ack).encode(), sender_address)
            
            # Result: {"message_type": "ACK", "ack_number": 5}
        """
        return {"message_type": MessageType.ACK, "ack_number": ack_number}
