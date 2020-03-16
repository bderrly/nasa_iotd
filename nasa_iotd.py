#!/usr/bin/env python3
# 2016-12-08

# Grab NASA's 'Image of the Day', resize it to fit the desktop resolution,
# add the description from the RSS feed if it is available.
#
# https://www.nasa.gov/multimedia/imagegallery/iotd.html
#
# Dependencies:
#   feedparser
#   pillow
#   requests
#   Xlib

import argparse
import os
import sys
from io import BytesIO

import feedparser
import requests
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

from Xlib import display


MAX_FILE_SIZE = 1 << 25  # 2^25 == 33.6 MiB


def getRssItems(count):
    """Returns the image URI, size, and description of the latest _count_ items.
    
    Returns:
        A list of dicts containing the URI and size of the image to download and a string description of the image.
    """
    nasa_rss = feedparser.parse('https://www.nasa.gov/rss/dyn/lg_image_of_the_day.rss')

    parsed_items = list()
    entries = nasa_rss.entries[:count]
    for entry in entries:
        description = entry.get('description')

        if len(entry.enclosures) < 1:
            # If there are no enclosures then there are no images so let's move on.
            continue

        enclosure = entry.enclosures[0]
        if enclosure['type'] != 'image/jpeg':
            # If the enclosure does not have a JPEG then there's nothing to do.
            continue

        if len(entry.enclosures) > 1:
            print("Found more than one image in item {}; taking the first image.".format(entry['guid']), file=sys.stderr)

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


def resizeImage(image, desktop_width, desktop_height):
    """Resizes the image and maintains aspect ratio.
    
    The desktop_width and desktop_height are used to calculate the aspect ratio
    of the original image. The ratio is then maintained when resizing the image
    such that the maximum size is no more than screen resolution.
    
    Args:
        image: A pillow Image.
        desktop_width: An integer, the width of monitor in pixels.
        desktop_height: An integer, the height of monitor in pixels.
        
    Returns:
        A pillow Image that has been resized.
    """
    if image.width <= desktop_width and image.height <= desktop_height:
        # The image is already smaller than the desktop resolution so there is
        # no reason to resize it.
        return image

    x_ratio = float(desktop_width/image.width)
    y_ratio = float(desktop_height/image.height)

    if x_ratio < y_ratio:
        w, h = desktop_width, int(image.height*x_ratio)
    else:
        w, h = int(image.width*y_ratio), desktop_height
    return image.resize((w, h))


def getScreenResolution():
    """Return the desktop screen resolution using Xlib.

    Returns:
        An integer, width of display in pixels
        An integer, height of the display in pixels
    """
    d = display.Display()
    scr = d.screen()
    return (scr.width_in_pixels, scr.height_in_pixels)
    

def writeImageToDisk(file_name, image):
    try:
        image.save(file_name, 'JPEG')
    except IOError as ioe:
        print('IO failure: {}'.format(ioe), file=sys.stderr)


def main(argv):
    desktop_width, desktop_height = getScreenResolution()

    if desktop_width == 0 or desktop_height == 0:
        print('Failed to get screen resolution: have {}x{}'.format(desktop_width, desktop_height), file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(
            description='Downloads and formats the Image of the Day from nasa.org.')
    parser.add_argument('-c', '--count', type=int, default=1, help="The number of RSS items to retrieve. (default: 1)")
    parser.add_argument('-i', '--input_file', help="The name of the file to read from disk. (Does not read from RSS and adds no description to the final image.)")
    parser.add_argument('-o', '--output_file', help="The name of the file to write to disk.")
    parser.add_argument('-d', '--directory', default=os.environ['PWD'], help='Directory to write image file. (default: $PWD)')
    args = parser.parse_args()

    # If we are operating on a local file it is probably for testing purposes
    # because all we're going to do is resize the image and write it to disk.
    if args.input_file is not None:
        with open(args.input_file, 'rb') as f:
            image_data = f.read(MAX_FILE_SIZE)
            image = Image.open(BytesIO(image_data))
            image = resizeImage(image, desktop_width, desktop_height)
        output_file = args.output_file
        if output_file is None:
            output_file = os.path.join(args.directory, os.path.basename(args.input_file))
        writeImageToDisk(output_file, image)
        return

    rss_items = getRssItems(args.count)
    for item in rss_items:
        print("Processing {}…".format(item['url']))
        image_data = getImage(item['url'])
        if int(item['size']) != int(len(image_data)):
            print("File size differs between RSS and downloaded image: {} versus {} bytes.".format(item['size'], len(image_data)))
        # Cut out only the file name portion of the image's URL. This will
        # potentially be used for the output file name.
        nasa_image_filename = item['url'].rsplit('/', 1)[1]
        nasa_image = Image.open(BytesIO(image_data))
        nasa_image = resizeImage(nasa_image, desktop_width, desktop_height)

        # Overlay the description from the RSS item over the NASA image.
        description = item.get('desc')
        if description is not None:
            draw = ImageDraw.Draw(nasa_image)
            font = ImageFont.truetype('/usr/share/fonts/TTF/LiberationSerif-Regular.ttf', 18)
            w, h = font.getsize(description)
            if int(w) > int(nasa_image.width):
                print("The text overlay is wider than the image: {} versus {}".format(w, nasa_image.width))
            x, y = (5, nasa_image.height-h)
            draw.rectangle((x, y, x+w, y+h), fill='black')
            draw.text((x, y), description, fill=(164, 244, 66), font=font)

        # Create a new, blank image the size of the desktop resolution.
        image = Image.new('RGB', (desktop_width, desktop_height))

        # Define the origin coordinates to begin pasting the NASA image
        # over the blank image. This is a tuple of (x, y).
        box = (int(.5*desktop_width-.5*nasa_image.width),
               int(.5*desktop_height-.5*nasa_image.height))

        # Paste the NASA image over the newly created black image.
        image.paste(nasa_image, box)

        output_file = os.path.join(args.directory, nasa_image_filename)
        writeImageToDisk(output_file, image)


if __name__ == '__main__':
    main(sys.argv)
