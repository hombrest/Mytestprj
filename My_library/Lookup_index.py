import os
import hashlib
import re
import time

# Function to calculate the SHA-1 checksum of a file
def sha1_checksum(file_path):
    sha1 = hashlib.sha1()
    with open(file_path, "rb") as f:
        while True:
            data = f.read(64 * 1024)  # Read file in chunks of 64KB
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()

index_file_path = "/storage/self/primary/Download/PC_books.txt"
# Main folder path containing the files
folder_path = "/storage/self/primary/Books"
exclude_pattern = r'Moonreader'
exclude_regex = re.compile(exclude_pattern, re.IGNORECASE)

start_time = time.time()
with open(index_file_path, encoding="utf-8") as index_file:
    library_index = tuple(line[:40] for line in index_file.readlines()[1:-1])
    # for item in library_index:
    #     print(item)
    no_of_processed_files = 0
    print("New Files:")
    # Iterate over the root folder and its subfolders
    for root, dirs, files in os.walk(folder_path):
        if not exclude_regex.search(root):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                checksum = sha1_checksum(file_path)
                if checksum not in library_index:
                    print(f'"{file_path}"')
                # print(f"{checksum}\t\"{file_name}\"\n")
                no_of_processed_files += 1
    end_time = time.time()
    # Calculate processing time
    processing_time = end_time - start_time
    print(f"Processing {no_of_processed_files} files in {processing_time} seconds.")