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
import io
import logging
import os
import sys
from io import BytesIO

import feedparser
import requests
from PIL import Image, ImageDraw, ImageFont
from Xlib import display
import Xlib.error


NASA_RSS = 'https://www.nasa.gov/rss/dyn/lg_image_of_the_day.rss'
MAX_FILE_SIZE = 1 << 25  # 2^25 == 33.6 MiB

logger = logging.getLogger('nasa_iotd')

def getRssItems(rss, count):
    """Returns the image URI, size, and description of the latest count items.

    Args:
        rss: The RSS URI or local file to parse.
        count: The number of items to fetch from the RSS feed.
    
    Returns:
        A list of dicts containing the URI and size of the image to download,
        and a string description of the image.
    """
    rss = feedparser.parse(rss)

    parsed_items = list()
    entries = rss.entries[:count]
    for entry in entries:
        description = entry.get('description')

        # Ensure the description is a single line of text. The Pillow library expects
        # a single line when determining the size of the rendered text.
        description = ' '.join([l.strip() for l in description.splitlines()])

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
        image_url: The string URI to download, or a path to a local file for testing.
        
    Returns:
        A BufferedIO object containing the image data.

        N.B. Be sure to close() the buffer when you are done with it.
    """
    if image_url.startswith('http'):
        req = requests.get(image_url)
        return io.BytesIO(req.content)
    return open(image_url, 'rb')


def getScreenResolution():
    """Return the root screen resolution using Xlib.

    Returns:
        A 2-tuple, the width and height of the root screen in pixels.
    """
    try:
        d = display.Display()
    except Xlib.error.DisplayError:
        logger.error("If you are not running in X you must supply the --resolution flag.")
        logger.exception("Failed attempting to retrieve display information from X. "
                "Perhaps you are not running in X or $DISPLAY is unset?")
        sys.exit(1)
    root_screen = d.screen()
    return (root_screen.width_in_pixels, root_screen.height_in_pixels)


def writeImageToDisk(file_name, image):
    try:
        image.save(file_name, 'JPEG', quality=95)
    except OSError as ose:
        logger.exception('Could not save image.')


def reflowText(text, width, font):
    """Adds line breaks, if necessary, so all text can fit within width.

    Args:
        text: A string, the text to reformat.
        width: An int, the width of the screen in pixels.
        font: An ImageFont, the font to use on the image.

    Returns:
        A string, the reformatted text.
    """
    logger.debug(f'Original description length {font.getlength(text)} pixels')
    if font.getlength(text) <= width - 20:
        return text

    lines = []
    line = []
    for word in text.split():
        line.append(word)
        if font.getlength(' '.join(line)) > width - 20:
            line.pop()
            lines.append(' '.join(line.copy()))
            line.clear()
            line.append(word)
    # Don't forget to append the final line!
    lines.append(' '.join(line))
    logger.debug(f'Description is {len(lines)} line(s)')
    for line in lines:
        logger.debug(f'Line length {font.getlength(line)} pixels')
    return '\n'.join(line for line in lines)


def renderDescription(text, image, font, font_size=24):
    """Render the background box and text overlay.

    Args:
        text: A string, the description to render.
        image: A PIL.Image, the image to draw on.
        font: A PIL.ImageFont, the font to use when rendering.
        font_size: An int, the font size for rendering the text.
    """
    draw = ImageDraw.Draw(image, 'RGBA')
    desc_font = ImageFont.truetype(font=font, size=font_size)
    description = reflowText(text, image.width, desc_font)

    desc_xy = (image.width//2, image.height-10)
    desc_bbox = draw.textbbox(desc_xy, description, anchor='md', align='center', font=desc_font)
    logger.debug(f'Text bbox: {desc_bbox}')
    desc_matte = list()
    desc_matte.append(desc_bbox[0] - 5)
    desc_matte.append(desc_bbox[1] - 5)
    desc_matte.append(desc_bbox[2] + 5)
    desc_matte.append(desc_bbox[3] + 5)
    logger.debug(f'Text matte: {desc_matte}')
    draw.rectangle(desc_matte, fill=(0, 0, 0, int(256*.75)))
    draw.text(desc_xy, description, anchor='md', fill=(20, 148, 20), align='center', font=desc_font)


def main(argv):
    parser = argparse.ArgumentParser(
            description='Downloads, modifies, and saves the "Image of the Day" from nasa.gov.')
    parser.add_argument('-c', '--count', type=int, default=1, help="The number of RSS items to retrieve. (default: 1)")
    parser.add_argument('-d', '--directory', help='Directory to write image file. (defaults to $PWD)')
    parser.add_argument('-i', '--input-file',
            help="The name of the file to read from disk. (Does not read from RSS and adds no description to the final image.)")
    parser.add_argument('-f', '--font', default="fonts/Play/Play-Bold.ttf",
            help="The path to the TrueType font to use for the image description.")
    parser.add_argument('-o', '--output-file', help="The name of the file to write to disk.")
    parser.add_argument('-s', '--font-size', type=int, default=24,
            help="The size of the font when rendering the image description.")
    parser.add_argument('-r', '--resolution', nargs=2, metavar=("WIDTH", "HEIGHT"),
            help="The resolution of the final image. If not supplied the program will attempt to determine the resolution of the monitor using Xlib.")
    parser.add_argument('--rss-file', help="The RSS file or URI to use (for testing).")
    parser.add_argument('-v', '--verbose', action='count', default=0, help="Print information about what the program is doing.")
    args = parser.parse_args()

    if args.resolution is None:
        resolution = getScreenResolution()
    else:
        resolution = tuple(args.resolution)

    # Setup logging
    log_level = max(10, 30 - args.verbose * 10)
    output_file = args.output_file
    logger.setLevel(log_level)
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

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

    rss = next(rf for rf in [args.rss_file, NASA_RSS] if rf is not None)
    rss_items = getRssItems(rss, args.count)
    for item in rss_items:
        image_data = getImage(item['url'])
        logger.info(f"Processing {item['url']}…")

        # Cut out only the file name portion of the image's URL. This will
        # potentially be used for the output file name.
        nasa_image_filename = item['url'].rsplit('/', 1)[1]
        nasa_image = Image.open(image_data)

        logger.debug('Original NASA image is %dx%d pixels', nasa_image.width, nasa_image.height)

        # Resize the image (keeping aspect ratio) to fit within the specified resolution.
        nasa_image.thumbnail(resolution)
        logger.debug(f'Thumbnailed NASA image is {nasa_image.width}x{nasa_image.height} pixels')

        # Create a black image the size of the desktop resolution.
        black_image = Image.new('RGB', resolution)
        logger.debug(f'Black matte is {black_image.width}x{black_image.height} pixels')

        # Define the origin coordinates to begin pasting the NASA image
        # over the blank image. This is a tuple of (x, y).
        nasa_origin = (
            int((.5 * black_image.width) - (.5 * nasa_image.width)),
            int((.5 * black_image.height) - (.5 * nasa_image.height))
        )

        # Paste the NASA image over the newly created black image.
        black_image.paste(nasa_image, nasa_origin)

        # Now that we are done with the original Image data we can safely close the byte buffer.
        image_data.close()

        # Overlay the description from the RSS item over the NASA image.
        description = item.get('desc')
        if description is not None:
            renderDescription(description, black_image, args.font, args.font_size)

        directory = next(d for d in [args.directory, os.environ['PWD']] if d is not None)
        output_file = os.path.join(directory, nasa_image_filename)
        writeImageToDisk(output_file, black_image)


if __name__ == '__main__':
    main(sys.argv)
