# This file helps with making messages into strings and back to dictionaries

def encode_message(fields):
    # We need a message type
    if "message_type" not in fields:
        print("Error: No message_type found!")
        return None

    # This will hold all our lines
    lines = []
    
    # Go through each key and value
    for key in fields:
        value = fields[key]
        # Make a string like "key: value"
        line = key + ": " + str(value)
        lines.append(line)

    # Join them with new lines
    full_message = "\n".join(lines)
    return full_message


def decode_message(raw):
    # This will hold our result
    result = {}
    
    # Split the big string into lines
    lines = raw.split("\n")
    
    for line in lines:
        # Remove spaces
        line = line.strip()
        
        # Skip empty lines
        if line == "":
            continue
            
        # Split by the colon
        parts = line.split(":")
        
        # We need at least a key and a value
        if len(parts) < 2:
            continue
            
        key = parts[0].strip()
        # Join the rest back together just in case
        value = ":".join(parts[1:]).strip()
        
        result[key] = value
        
    # Check if we have the message type
    if "message_type" not in result:
        print("Warning: No message_type in decoded message")
        
    return result
