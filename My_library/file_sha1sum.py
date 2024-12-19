import os
import hashlib
import time
import re

# Function to calculate the SHA-1 checksum of a file
def sha1_checksum(file_path):
    sha1 = hashlib.sha1()
    with open(file_path, "rb") as f:
        while True:
            data = f.read(65536)  # Read file in chunks of 64KB
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()


# Folder path containing the files
folder_path = '/storage/self/primary/Books'
out_file = '/storage/self/primary/Download/book_list.txt'

no_of_file = 0
start_time = time.time()
with open(out_file, 'w') as __file__:
    # Iterate over files in the folder
    for root, dirs, files in os.walk(folder_path):
        if not re.search('moonreader', root, re.IGNORECASE):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                checksum = sha1_checksum(file_path)
                # print(f"{checksum}\t{file_path}")
                __file__.write(f"{checksum}\t{file_path}\n")
                no_of_file += 1

end_time = time.time()
processing_time = end_time - start_time
print(f"Total {no_of_file} files in {round(processing_time, 2)} seconds.")