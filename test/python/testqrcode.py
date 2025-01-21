from pyqrcode import url

def png_to_terminal(filename):
    # Read the PNG file
    reader = png.Reader(filename)
    w, h, pixels, metadata = reader.read_flat()
    pixel_byte_width = 4 if metadata['alpha'] else 3

    # Loop through each row
    for row in range(h):
        row_pixels = pixels[row * w * pixel_byte_width:(row + 1) * w * pixel_byte_width]
        line = ''
        for col in range(w):
            i = col * pixel_byte_width
            r, g, b = row_pixels[i:i+3]
            line += colored('  ', 'white', f'on_rgb({r},{g},{b})')
        print(line)

# Display the QR code in the terminal
url.png('img.png', scale=6,module_color=[0, 0, 0, 128],background=[0xff, 0xff, 0xcc])
