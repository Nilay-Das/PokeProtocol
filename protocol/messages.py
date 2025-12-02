"""
Functions for encoding and decoding messages.
We turn dictionaries into strings to send over the network, and vice versa.
"""


def encode_message(message_dict: dict) -> str:
    """Turns a dictionary into a string we can send over the network."""
    
    # every message needs a message_type
    if "message_type" not in message_dict:
        print("Error: Cannot encode message - no 'message_type' found!")
        print(f"The message was: {message_dict}")
        return None

    # build the message line by line
    lines = []
    
    for key in message_dict:
        value = message_dict[key]
        line = key + ": " + str(value)
        lines.append(line)

    # join with newlines
    full_message = "\n".join(lines)
    
    return full_message


def decode_message(raw_text: str) -> dict:
    """Turns a string back into a dictionary we can use."""
    
    result = {}
    
    # split into lines
    lines = raw_text.split("\n")
    
    for line in lines:
        line = line.strip()
        
        # skip empty lines
        if line == "":
            continue
        
        # split at colon
        parts = line.split(":")
        
        if len(parts) < 2:
            continue
        
        key = parts[0].strip()
        # join back in case value had colons in it
        value = ":".join(parts[1:]).strip()
        
        result[key] = value
    
    if "message_type" not in result:
        print("Warning: Decoded message has no 'message_type' field")
        print(f"Raw text was: {raw_text}")
    
    return result
