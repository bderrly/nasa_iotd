#!/usr/bin/env python3

"""NASA Image of the Day fetcher

Grab NASA's 'Image of the Day' from RSS, resize it (if necessary, keeping the
scaling ratio the same), and add a text overlay of the description from the RSS
feed if it is available.

https://www.nasa.gov/multimedia/imagegallery/iotd.html

Dependencies:
  feedparser
  pillow
  requests
  Xlib
"""

import argparse
import os
import sys
from io import BytesIO

import feedparser
import requests
from PIL import Image, ImageDraw, ImageFont
from Xlib import display
import Xlib.error


MAX_FILE_SIZE = 1 << 25  # 2^25 == 33.6 MiB


def getRssItems(count):
    """Returns the image URI, size, and description of the latest count items.
    
    Returns:
        A list of dicts containing the URI and size of the image to download,
        and a string description of the image.
    """
    nasa_rss = feedparser.parse('https://www.nasa.gov/rss/dyn/lg_image_of_the_day.rss')

    parsed_items = list()
    entries = nasa_rss.entries[:count]
    for entry in entries:
        description = entry.get('description')

        if len(entry.enclosures) < 1:
            # If there are no enclosures then there are no images so let's move on.
            continue

        # Only attempt to process the first enclosure.
        enclosure = entry.enclosures[0]
        if enclosure['type'] != 'image/jpeg':
            # If the enclosure does not have a JPEG then there's nothing to do.
            continue

        image_url = enclosure['href']
        image_size = enclosure['length']
        parsed_items.append({'url': image_url, 'size': image_size, 'desc': description})

    return parsed_items


def getImage(image_url):
    """Download the image from NASA.
    
    Args:
        image_url: The string URI to download.
        
    Returns:
        A buffer of bytes containing the image data.
    """
    req = requests.get(image_url)
    return req.content


def getScreenResolution():
    """Return the root screen resolution using Xlib.

    Returns:
        A two-tuple, the width and height of the root screen in pixels.
    """
    try:
        d = display.Display()
    except Xlib.error.DisplayError:
        print("Failed attempting to retrieve display information from X. Perhaps you are not running in X?",
                file=sys.stderr)
        print("If you are not running in X you must supply the --resolution flag.", file=sys.stderr)
        sys.exit(1)
    root_screen = d.screen()
    return (root_screen.width_in_pixels, root_screen.height_in_pixels)


def writeImageToDisk(file_name, image):
    try:
        image.save(file_name, 'JPEG', quality=95)
    except OSError as ose:
        print(f"I/O failure: {ose}", file=sys.stderr)
        sys.exit(1)


def reflowText(text, width, font=None):
    """Adds line breaks, if necessary, so all text can fit within width.

    Args:
        text: A string, the text to reformat.
        width: An int, the width of the screen in pixels.
        font: (optional) An ImageFont, the font to use on the image.

    Returns:
        A string, the reformatted text.
    """
    if font is None:
        font = ImageFont.truetype('/usr/share/fonts/TTF/LiberationSerif-Regular.ttf', 18)
    if font.getlength(text) <= width - 20:
        return text

    lines = []
    line = []
    for word in text.split():
        line.append(word)
        if font.getlength(" ".join(line)) > width - 20:
            line.pop()
            lines.append(line.copy())
            line.clear()
            line.append(word)
    # Don't forget to append the final line!
    lines.append(line)
    return "\n".join([
        " ".join(line) for line in lines
        ])


def renderDescription(text, image, font, font_size=24):
    """Render the background box and text overlay.

    Args:
        text: A string, the description to render.
        image: A PIL.Image, the image to draw on.
        font: A PIL.ImageFont, the font to use when rendering.
        font_size: An int, the font size for rendering the text.
    """
    draw = ImageDraw.Draw(image)
    desc_font = ImageFont.truetype(font=font, size=font_size)
    description = reflowText(text, image.width, desc_font)
    
    # Find the bounding box (bbox) of the rendered text. These points
    # will be used for placing the background rectangle and text
    # overlay. Return is a 4-tuple: (x anchor, y anchor, x destination,
    # y destination).
    bbox = draw.textbbox((0,0), description, font=desc_font)

    # Add some extra pixels to the width and height of the bbox. This
    # will allow for better framing of the background box and text
    # within it.
    bbox_padding = 20
    textbox = (bbox[0], bbox[1], bbox[2] + bbox_padding, bbox[3] + bbox_padding)

    # The four points for the background rectangle behind the text.
    bbox_x_anchor = (image.width - textbox[2]) // 2
    bbox_y_anchor = image.height - textbox[3] - (bbox_padding // 2) 
    bbox_x_length = bbox_x_anchor + textbox[2]
    bbox_y_length = bbox_y_anchor + textbox[3]

    # Anchor the text a little inside the black rectangle behind it.
    text_x_anchor = bbox_x_anchor + 5
    text_y_anchor = bbox_y_anchor + 5

    draw.rectangle((bbox_x_anchor, bbox_y_anchor, bbox_x_length, bbox_y_length), fill='black')
    draw.text((text_x_anchor, text_y_anchor), text, fill=(20, 148, 20), font=desc_font)


def main(argv):
    parser = argparse.ArgumentParser(
            description='Downloads, modifies, and saves the "Image of the Day" from nasa.gov.')
    parser.add_argument('-c', '--count', type=int, default=1, help="The number of RSS items to retrieve. (default: 1)")
    parser.add_argument('-d', '--directory', default=os.environ['PWD'], help='Directory to write image file. (default: $PWD)')
    parser.add_argument('-i', '--input-file',
            help="The name of the file to read from disk. (Does not read from RSS and adds no description to the final image.)")
    parser.add_argument('-f', '--font', default="fonts/Play-Bold.ttf",
            help="The path to the TrueType font to use for the image description.")
    parser.add_argument('-o', '--output-file', help="The name of the file to write to disk.")
    parser.add_argument('-s', '--font-size', type=int, default=24,
            help="The size of the font when rendering the image description.")
    parser.add_argument('-r', '--resolution', nargs=2, metavar=("WIDTH", "HEIGHT"),
            help="The resolution of the final image. If not supplied the program will attempt to determine the resolution of the monitor using Xlib.")
    parser.add_argument('-v', '--verbose', action="store_true", help="Print information about what the program is doing.")
    args = parser.parse_args()

    if args.resolution is None:
        resolution = getScreenResolution()
    else:
        resolution = tuple(args.resolution)

    output_file = args.output_file

    if args.input_file is not None:
        # If we are operating on a local file it is probably for testing purposes.
        # All we are going to do is resize the image and write it to disk.
        with open(args.input_file, 'rb') as f:
            image_data = f.read(MAX_FILE_SIZE)
            image = Image.open(BytesIO(image_data))
            image.thumbnail(resolution)
        if output_file is None:
            output_file = os.path.join(args.directory, os.path.basename(args.input_file))
        writeImageToDisk(output_file, image)
        return

    rss_items = getRssItems(args.count)
    for item in rss_items:
        image_data = getImage(item['url'])
        if (args.verbose):
            print(f"Processing {item['url']}…")

        if int(item['size']) != int(len(image_data)):
            print(f"File size differs between RSS and downloaded image: {item['size']} versus {len(image_data)} bytes.")
        # Cut out only the file name portion of the image's URL. This will
        # potentially be used for the output file name.
        nasa_image_filename = item['url'].rsplit('/', 1)[1]
        nasa_image = Image.open(BytesIO(image_data))

        # Resize the image (keeping aspect ratio) to fit within the specified resolution.
        nasa_image.thumbnail(resolution)

        # Create a black image the size of the desktop resolution.
        black_image = Image.new('RGB', resolution)

        # Define the origin coordinates to begin pasting the NASA image
        # over the blank image. This is a tuple of (x, y).
        nasa_origin= (
                int((.5 * black_image.width) - (.5 * nasa_image.width)),
                int((.5 * black_image.height) - (.5 * nasa_image.height)))

        # Paste the NASA image over the newly created black image.
        black_image.paste(nasa_image, nasa_origin)

        # Overlay the description from the RSS item over the NASA image.
        description = item.get('desc')
        if description is not None:
            renderDescription(description, black_image, args.font, args.font_size)

        output_file = os.path.join(args.directory, nasa_image_filename)
        writeImageToDisk(output_file, black_image)


if __name__ == '__main__':
    main(sys.argv)
