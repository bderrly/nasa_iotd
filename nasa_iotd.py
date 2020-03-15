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

def parseRss():
    """Extracts the URI and description of the most recent 'Image of the Day'.
    
    Returns:
        A tuple containing the URI of the image and a string description of the image.
    """
    nasa_rss = feedparser.parse('https://www.nasa.gov/rss/dyn/lg_image_of_the_day.rss')

    recent = nasa_rss.entries[0]
    description = recent.get('description', '')

    image_url = str()
    for enclosure in recent.links:
        if enclosure['type'] == 'image/jpeg':
            image_url = enclosure['href']

    return (image_url, description)


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
    if image.size[0] <= desktop_width and image.size[1] <= desktop_height:
        return image

    x_ratio = float(desktop_width/image.size[0])
    y_ratio = float(desktop_height/image.size[1])

    if x_ratio < y_ratio:
        w, h = desktop_width, int(image.size[1]*x_ratio)
    else:
        w, h = int(image.size[0]*y_ratio), desktop_height
    # print("NASA image resized from {}x{} ({}) to {}x{} ({})".format(image.size[0], image.size[1], image.size[0]/image.size[1], w, h, w/h))
    return image.resize((w,h))


def getScreenResolution():
    """Return the desktop screen resolution using Xlib.

    Returns:
        An integer, width of display in pixels
        An integer, height of the display in pixels
    """
    d = display.Display()
    scr = d.screen()
    return (scr.width_in_pixels, scr.height_in_pixels)
    

def main(argv):
    desktop_width, desktop_height = getScreenResolution()

    if desktop_width == 0 or desktop_height == 0:
        print('Failed to get screen resolution: have {}x{}'.format(desktop_width, desktop_height), file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(
            description='Downloads and formats the Image of the Day from nasa.org.')
    parser.add_argument('-i', '--input_file', help='The name of the file to read from disk. (Does not read from RSS and adds no description to the final image.)')
    parser.add_argument('-o', '--output_file', help='The name of the file to write to disk.')
    parser.add_argument('-d', '--directory', default=os.environ['PWD'], help='Directory to write image file. (default: $PWD)')
    args = parser.parse_args()

    image_url = None
    description = None
    if args.input_file is None:
        image_url, description = parseRss()
        image_data = getImage(image_url)
    else:
        with open(args.input_file, 'rb') as f:
            image_data = f.read(MAX_FILE_SIZE)

    nasa_image_filename = os.path.basename(image_url)
    nasa_image = Image.open(BytesIO(image_data))
    nasa_image = resizeImage(nasa_image, desktop_width, desktop_height)

    if description:
        draw = ImageDraw.Draw(nasa_image)
        font = ImageFont.truetype('/usr/share/fonts/TTF/LiberationSerif-Regular.ttf', 18)
        w, h = font.getsize(description)
        x, y = (5, nasa_image.size[1]-h)
        draw.rectangle((x, y, x+w, y+h), fill='black')
        draw.text((x, y), description, fill=(164, 244, 66), font=font)

    image = Image.new('RGB', (desktop_width, desktop_height))

    # Define the origin coordinates to begin pasting the NASA image
    # over the blank image. This is a tuple of (x, y).
    box = (int(.5*desktop_width-.5*nasa_image.size[0]),
           int(.5*desktop_height-.5*nasa_image.size[1]))
    image.paste(nasa_image, box)

    if args.output_file is None:
        if args.input_file is None:
            # File name from RSS feed
            output_file = os.path.join(args.directory, nasa_image_filename)
        else:
            output_file = os.path.join(args.directory, os.path.basename(args.input_file))
    else:
        output_file = os.path.join(args.directory, args.output_file)

    try:
        image.save(output_file, 'JPEG')
    except IOError as ioe:
        print('IO failure: {}'.format(ioe), file=sys.stderr)


if __name__ == '__main__':
    main(sys.argv)
