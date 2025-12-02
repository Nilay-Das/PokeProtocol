"""
=============================================================================
MESSAGE ENCODING AND DECODING
=============================================================================

WHAT IS THIS FILE?
------------------
This file converts Python dictionaries into text strings and back again.
We need this because networks send text/bytes, not Python objects!


THE MESSAGE FORMAT
------------------
Our protocol uses a simple text format where each line has a key and value
separated by a colon. This is easy to read and debug.

Example message as a Python dictionary:
    {
        "message_type": "ATTACK_ANNOUNCE",
        "move_name": "Thunderbolt",
        "sequence_number": "5"
    }

Same message as a text string (what gets sent over the network):
    message_type: ATTACK_ANNOUNCE
    move_name: Thunderbolt
    sequence_number: 5


WHY THIS FORMAT?
----------------
1. Human-readable: You can print messages and understand them
2. Simple to parse: Just split by newlines and colons
3. No special libraries needed: Works with basic Python string operations


HOW TO USE THIS FILE
--------------------
    from protocol.messages import encode_message, decode_message

    # Creating a message to send:
    my_message = {"message_type": "CHAT_MESSAGE", "text": "Hello!"}
    text_to_send = encode_message(my_message)
    # text_to_send is now "message_type: CHAT_MESSAGE\ntext: Hello!"

    # Receiving a message:
    received_text = "message_type: GAME_OVER\nwinner: Pikachu"
    parsed_message = decode_message(received_text)
    # parsed_message is now {"message_type": "GAME_OVER", "winner": "Pikachu"}

=============================================================================
"""


def encode_message(message_dict: dict) -> str:
    """
    Convert a Python dictionary into a text string for sending over the network.
    
    This function takes a dictionary and turns it into our protocol's text format,
    where each key-value pair becomes a line like "key: value".
    
    Args:
        message_dict: A dictionary containing the message data.
                      MUST include "message_type" key.
    
    Returns:
        A string in the format:
            key1: value1
            key2: value2
            ...
        
        Returns None if message_type is missing.
    
    Example:
        >>> message = {"message_type": "ATTACK_ANNOUNCE", "move_name": "Tackle"}
        >>> result = encode_message(message)
        >>> print(result)
        message_type: ATTACK_ANNOUNCE
        move_name: Tackle
    
    Note:
        The order of keys in the output may vary since Python dicts
        don't guarantee order (though in Python 3.7+ they do).
    """
    # Every message MUST have a message_type
    # This tells the receiver what kind of message it is
    if "message_type" not in message_dict:
        print("Error: Cannot encode message - no 'message_type' found!")
        print(f"The message was: {message_dict}")
        return None

    # Build the message line by line
    lines = []
    
    # Go through each key-value pair in the dictionary
    for key in message_dict:
        value = message_dict[key]
        
        # Create a line in the format "key: value"
        # We use str(value) to handle numbers and other types
        line = key + ": " + str(value)
        lines.append(line)

    # Join all lines together with newline characters
    # This creates the final message string
    full_message = "\n".join(lines)
    
    return full_message


def decode_message(raw_text: str) -> dict:
    """
    Convert a text string back into a Python dictionary.
    
    This is the opposite of encode_message(). It takes text received
    from the network and parses it back into a dictionary we can use.
    
    Args:
        raw_text: A string in the format:
                  key1: value1
                  key2: value2
                  ...
    
    Returns:
        A dictionary with the parsed key-value pairs.
        If the text is invalid or empty, returns an empty dict.
    
    Example:
        >>> text = "message_type: GAME_OVER\\nwinner: Pikachu\\nloser: Charmander"
        >>> result = decode_message(text)
        >>> print(result)
        {"message_type": "GAME_OVER", "winner": "Pikachu", "loser": "Charmander"}
    
    Note:
        All values are returned as strings. If you need a number,
        you'll need to convert it yourself:
            damage = int(result["damage_dealt"])
    """
    # This dictionary will hold our parsed result
    result = {}
    
    # Split the big string into individual lines
    lines = raw_text.split("\n")
    
    # Process each line
    for line in lines:
        # Remove any extra whitespace from the beginning and end
        line = line.strip()
        
        # Skip empty lines
        if line == "":
            continue
        
        # Split the line at the colon to separate key and value
        # Example: "move_name: Thunderbolt" -> ["move_name", " Thunderbolt"]
        parts = line.split(":")
        
        # We need at least two parts (key and value)
        if len(parts) < 2:
            # This line doesn't have a colon, skip it
            continue
        
        # The key is the first part (before the colon)
        key = parts[0].strip()
        
        # The value is everything after the first colon
        # We use ":".join(parts[1:]) in case the value itself contains colons
        # Example: "time: 10:30:00" -> value is "10:30:00"
        value = ":".join(parts[1:]).strip()
        
        # Add to our result dictionary
        result[key] = value
    
    # Warn if there's no message_type (useful for debugging)
    if "message_type" not in result:
        print("Warning: Decoded message has no 'message_type' field")
        print(f"Raw text was: {raw_text}")
    
    return result
