from protocol.messages import encode_message, decode_message

print("--- Main Program ---")

# Let's make a message dictionary
original_message = {
    "message_type": "ATTACK_ANNOUNCE",
    "sequence_number": "5",
    "move_name": "Thunderbolt"
}

print("Original dictionary:")
print(original_message)

# Encode it
encoded_string = encode_message(original_message)
print("\nEncoded string:")
print(encoded_string)
print("---")

# Decode it back
decoded_message = decode_message(encoded_string)
print("Decoded dictionary:")
print(decoded_message)
