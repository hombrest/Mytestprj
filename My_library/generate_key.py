# generate_key.py
from cryptography.fernet import Fernet
import os

def generate_key(key_filename="secret.key"):
    """
    Generates a key and saves it into a file.
    """
    # Check if key file already exists to avoid overwriting
    if os.path.exists(key_filename):
        print(f"Warning: Key file '{key_filename}' already exists. Skipping generation to prevent overwriting.")
        print("If you need a new key, delete the existing file first or specify a different filename.")
        return

    # Generate the key
    key = Fernet.generate_key()

    # Save the key to a file
    try:
        with open(key_filename, 'wb') as key_file:
            key_file.write(key)
        print(f"Secret key generated and saved to '{key_filename}'")
        print("Keep this file secure and secret!")
        # Optionally print the key (not recommended for production environments)
        # print(f"Key (base64): {key.decode()}") 
    except IOError as e:
        print(f"Error: Could not write key to file '{key_filename}': {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    # You can change the filename if needed
    KEY_FILE = "secret.key" 
    generate_key(KEY_FILE)