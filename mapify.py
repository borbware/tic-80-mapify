import re
import argparse
import textwrap
from math import floor
import png

EXE_NAME = "mapify"
VERSION = "1.0.0"

COLOR_BLACK = 0
EMPTY_TILE = [COLOR_BLACK] * 64
NTILES = 256

IMAGE_WIDTH = 1920
IMAGE_HEIGHT = 1088
TILE_SIZE = 8

ROOM_WIDTH = 240
ROOM_HEIGHT = 136

HIDDEN_ROOMS = [
	11, 12, 13, 14, 15, 16, 17, 18,
	21, 22, 			26, 27, 28,
	31, 32, 				37, 38,
	41, 42, 					48,
	51, 52, 53, 54, 		57, 58,
	61, 62, 63, 64, 65, 66, 67, 68,
	71, 72, 73, 74, 75, 76, 77, 78,
	81, 82, 83, 84, 85, 86, 87, 88
]
REMOVE_COLUMNS = [1, 2, 8]
REMOVE_ROWS = [1, 6, 7, 8]

def room_number(x, y):
	return y * 10 + x

def split_to_chunks(text, chunk_size):
	return textwrap.wrap(text, chunk_size)

def hex2int(hex_number):
	return int(hex_number, 16)

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


def get_palette(cart, modify_palette = None):
	# The section data is at address 0.
	palette_data = read_section("PALETTE", cart)[0]
	palette = []
	# Each color is 3 bytes (x 2 characters), so split string into 6 character chunks
	for color_bytes in split_to_chunks(palette_data, 6):
		r, g, b = split_to_chunks(color_bytes, 2) # Each color is a single byte, or 2 characters
		palette.append([hex2int(r), hex2int(g), hex2int(b)])
	if modify_palette:
		palette = modify_palette(palette)
	return palette

def get_map(cart):
	map_section = read_section("MAP", cart)
	map_rows = []
	for data in map_section.values():
		# The cell represents an index into the cart tiles encoded in a singe big endian hex byte
		map_rows.append([hex2int_bigendian(byte) for byte in split_to_chunks(data, 2)])
	return map_rows

def get_tiles(cart):
	tile_section = read_section("TILES", cart)
	# Since some tiles might be missing, initialize all as empty tiles
	tiles = [EMPTY_TILE] * NTILES
	for address in tile_section.keys():
		# Each row of data corresponds to a tile with the address as the id
		data = tile_section[address]
		# The data encodes the index to a palette color as 4 bits, with each byte representing
		# two adjacent pixels. The low 4 bits are the left pixel, the 4 high bits are the right
		# pixel. But, as the values are big endian, the low bits are actually the highs bits and
		# vice versa.
		tile = []
		for byte in split_to_chunks(data, 2):
			high, low = byte[1], byte[0]
			tile.append(hex2int(low))
			tile.append(hex2int(high))
		tiles[address] = tile
	return tiles

def save_palette_as_png(cart, scale = 1, modify_palette = None):
	palette = get_palette(cart, modify_palette)
	first_row = []
	for color in palette[:8]:
		first_row += color * scale
	second_row = []
	for color in palette[8:]:
		second_row += color * scale
	png.from_array([first_row] * scale + [second_row] * scale, "RGB").save("palette.png")

def save_tile_as_png(cart, tile_id, modify_palette = None):
	tiles = get_tiles(cart)
	palette = get_palette(cart, modify_palette)
	rows = []
	for i in range(8):
		row = []
		start = i * 8
		end = start + 8
		colors = tiles[tile_id][start:end]
		for color in colors:
			row += palette[color]
		rows.append(row)
	png.from_array(rows, "RGB").save("tile_{}.png".format(tile_id))

def number_array(n, numbers_array): #n=number to print
	number_width = 6 #pixels
	channels = 4
	return [row[(n * number_width) * channels : ((n + 1) * number_width) * channels] for row in numbers_array]

def draw_number(n, x, y, image, numbers_array):
	number = number_array(n, numbers_array)
	for row_i in range(len(number)):
		row = number[row_i]
		del row[3::4] #remove alpha channel
		for r in range(0, len(row), 3):
			g = r + 1
			b = r + 2
			if row[r]==208 and row[g]==70 and row[b]==72: #only draw red
				image[row_i + y][r + x * 3] = row[r]
				image[row_i + y][g + x * 3] = row[g]
				image[row_i + y][b + x * 3] = row[b]
	return image

def save_map_as_png(cart, cartname, modify_palette = None, borders = False, hidden = False, numbers = False):
	tiles = get_tiles(cart)
	palette = get_palette(cart, modify_palette)
	map_cells = get_map(cart)
	image = []

	# loop over the pixels of the image and get the corresponding color
	for image_y in range(IMAGE_HEIGHT):
		image_row = []
		for image_x in range(IMAGE_WIDTH):
			map_x, map_y = floor(image_x / TILE_SIZE), floor(image_y / TILE_SIZE)
			tile_x, tile_y = image_x % TILE_SIZE, image_y % TILE_SIZE
			tile_id = map_cells[map_y][map_x]

			room_x, room_y = floor(image_x / ROOM_WIDTH) + 1, floor(image_y / ROOM_HEIGHT) + 1

			if borders and (image_x % ROOM_WIDTH == ROOM_WIDTH - 1 or image_y % ROOM_HEIGHT == ROOM_HEIGHT - 1 ):
				color = 2
			else:
				if hidden and room_number(room_x, room_y) in HIDDEN_ROOMS:
					color = 0
				else:
					color = tiles[tile_id][tile_y * TILE_SIZE + tile_x]
		
			image_row += palette[color]
		image.append(image_row)

	#add room numbers
	if numbers:
		numbers_array = list(png.Reader("numbers.png").asDirect()[2])
		for x in range(0, 8):
			for y in range(0, 8):
				image = draw_number(x + 1, x * ROOM_WIDTH + 6, y * ROOM_HEIGHT, image, numbers_array)
				image = draw_number(y + 1, x * ROOM_WIDTH, 		y * ROOM_HEIGHT, image, numbers_array)

	if hidden:
		deleterows=[]
		deletecolumns=[]
		for image_x in range(IMAGE_WIDTH * 3):
			room_x = floor(floor(image_x / 3) / ROOM_WIDTH) + 1
			if room_x in REMOVE_COLUMNS:
				deletecolumns.append(image_x)
		for image_y in range(IMAGE_HEIGHT):
			image_row = image[image_y]
			room_y = floor(image_y / ROOM_HEIGHT) + 1
			if room_y in REMOVE_ROWS:
				deleterows.append(image_y)
		for image_y in range(IMAGE_HEIGHT):
			for image_x in reversed(deletecolumns):
				del image[image_y][image_x]
		for image_y in reversed(deleterows):
			del image[image_y]

	filename = cartname.rstrip(".lua")
	if numbers:
		filename += "_numbers"
	if borders:
		filename += "_borders"
	if hidden:
		filename += "_hidden"
	filename += ".png"

	png.from_array(image, "RGB").save(filename)

def swap_transparent_to_black(palette):
	palette[6] = palette[0]
	return palette

if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		prog=EXE_NAME,
		description = "Generate a png map from a TIC-80 .lua cart. Output: map.png"
	)
	parser.add_argument("--version", action="version", version="%(prog)s {}".format(VERSION))
	parser.add_argument("--borders", action="store_true", help="draw border lines between rooms")
	parser.add_argument("--hidden", action="store_true", help="hide rooms listed in HIDDEN_ROOMS array")
	parser.add_argument("--numbers", action="store_true", help="show room numbers")
	parser.add_argument("cartfile", type=argparse.FileType("r"))
	arguments = parser.parse_args()
	with arguments.cartfile as cartfile:
		cart = [line.rstrip() for line in cartfile.readlines()]

	save_map_as_png(
		cart,
		arguments.cartfile.name,
		swap_transparent_to_black,
		arguments.borders,
		arguments.hidden,
		arguments.numbers )