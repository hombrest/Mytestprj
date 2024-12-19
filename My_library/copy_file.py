import shutil
import os

def copy_file(src_file, dest_dir):
	try:
		file_name = os.path.basename(src_file)
		dest_file = os.path.join(dest_dir, file_name)
		if not os.path.exists(dest_file):
			shutil.copy2(src_file, dest_file)
			print("File copied")
		else:
			print("File already exists" )
	except Exception as e:
		print(f"{e}")

source_file = '/storage/self/primary/Download/Ten years (rap).pdf'
destination_dir =  '/storage/self/primary/Download/TeraBox/'

copy_file(source_file, destination_dir)
