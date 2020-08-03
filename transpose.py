import re
import argparse
import textwrap
from math import floor

EXE_NAME = "transpose"
VERSION = "1.0.0"

def split_to_chunks(text, chunk_size):
	return textwrap.wrap(text, chunk_size)

def hex2int(hex_number):
	return int(hex_number, 16)

def int2hex(number):
	return str(hex(number))[2:]  # [2:] gets rid of "0x"

def hex2int_bigendian(hex_number):
	#swap the order of the bytes for big endian
	return int(hex_number[1] + hex_number[0], 16)

def section_start_regex(section_name):
	return re.compile("-- <{}>".format(section_name))
def section_end_regex(section_name):
	return re.compile("-- </{}>".format(section_name))

def read_section(section_name, cart):
	cart_size = len(cart)
	start_tag = section_start_regex(section_name)
	end_tag = section_end_regex(section_name)
	line = 0
	section = {}
	while not start_tag.match(cart[line]):
		line += 1
		if line >= cart_size:
			raise Error("Section {} not found".format(section_name))
	line += 1
	while not end_tag.match(cart[line]):
		# each line contains quote characters ("--"), a single space character,
		# the address of the line within the section as three integers (e.g. "003"),
		# a colon character and variable number of characters [a-f0-9] as the data
		# for that address

		# skip the quote characters and the space and split the rest by the colo to
		# get the address and data separately
		address, data = cart[line][3:].split(':')
		address = int(address)
		section[address] = data
		line += 1
	return section

def write_section(section_name, cart, new_section):
	cart_size = len(cart)
	start_tag = section_start_regex(section_name)
	end_tag = section_end_regex(section_name)
	line = 0
	while not start_tag.match(cart[line]):
		line += 1
		if line >= cart_size:
			raise Error("Section {} not found".format(section_name))
	line += 1
	while not end_tag.match(cart[line]):
		# each line contains quote characters ("--"), a single space character,
		# the address of the line within the section as three integers (e.g. "003"),
		# a colon character and variable number of characters [a-f0-9] as the data
		# for that address

		# skip the quote characters and the space and split the rest by the colo to
		# get the address and data separately
		address, data = cart[line][3:].split(':')
		int_address = int(address)
		try:
			cart[line] = "-- " + address + ":" + new_section[int_address]
			print(address + " modified.")
			print(cart[line])
		except: # ;D
			pass
		line += 1
	return cart


def get_patterns(cart, start, end):
	start = int(start)
	end = int(end)
	if start < 1 or start > 60 or end < 1 or end > 60:
		raise TypeError("Start and end values should be 1..60.")
	if end < start:
		print("end smaller than start. now end=start.")
		end = start
	pattern_section = read_section("PATTERNS", cart)
	patterns = {}
	print("Getting patterns from {} to {}.".format(start, end))
	for i in range(start - 1, end):

		decoded_pattern = []
		# pattern 01 is line -- 000, 02 is -- 001 and so on.
		# if start = 1 and end = 3, will transpose patterns 000, 001 and 002.
		
		# a pattern consists of 64 rows
		for row in split_to_chunks(pattern_section[i], 6):
			# each row is encoded as 6 characters, ABCDEF
			# A: note	from C to B 	(4..f) or no note (0) or break (1)
			# B: volume	from 0 to 15	(f..0)
			# C: effect i guess
			# D,E,F: used sfx
			# F: octave from 1 to 7		either 1,3,5,7,9,b,d or 2,4,6,8,a,c,e, depending on sfx
			decoded_row = []
			for character in split_to_chunks(row, 1):
				decoded_row.append(hex2int(character))
			decoded_pattern.append(decoded_row)
		patterns[i] = decoded_pattern

	return patterns

def transpose_patterns(cart, cartname, start, end, transpose_halfstep = 0, overwrite = False):
	patterns = get_patterns(cart, start, end)
	transpose_halfstep = int(transpose_halfstep)
	encoded_patterns = {}
	for index, pattern in patterns.items():
		encoded_pattern = ""
		for row in pattern:
			if not (row[0] == 0 or row[0] == 1):
				row[0] += transpose_halfstep
				if transpose_halfstep > 0:
					while row[0] > 15:
						row[0] -= 12
						row[5] += 2
					while row[5] > 14:
						print("TOO BIG OCTAVE")
						row[5] -= 2
				elif transpose_halfstep < 0:
					while row[0] < 4:
						row[0] += 12
						row[5] -= 1
					while row[5] < 1:
						print("TOO SMALL OCTAVE")
						row[5] += 2
			encoded_row = ""
			for char in row:
				encoded_row += int2hex(char)
			encoded_pattern += encoded_row
		encoded_patterns[index]=encoded_pattern

	cart = write_section("PATTERNS", cart, encoded_patterns)
	filename = cartname.rstrip(".lua") + "_transposed.lua"
	if overwrite:
		filename = cartname
	with open(filename, 'w') as f:
		for line in cart:
			f.write("%s\n" % line)

if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		prog=EXE_NAME,
		description = "Transpose chosen patterns from a TIC-80 .lua cart. Output: [cartname]_transposed.lua"
	)
	parser.add_argument("--version", action="version", version="%(prog)s {}".format(VERSION))
	parser.add_argument("cartfile", type=argparse.FileType("r"))
	parser.add_argument("start", action="store")
	parser.add_argument("end", action="store")
	parser.add_argument("--transpose", action="store")
	parser.add_argument("--overwrite", action="store_true")
	arguments = parser.parse_args()
	transpose = 0
	if arguments.transpose:
		transpose = arguments.transpose
	with arguments.cartfile as cartfile:
		cart = [line.rstrip() for line in cartfile.readlines()]

	transpose_patterns(
		cart,
		arguments.cartfile.name,
		arguments.start,
		arguments.end,
		transpose,	
		arguments.overwrite,
	)