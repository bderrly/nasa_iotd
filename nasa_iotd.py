#!/usr/bin/env python
#
# Grab NASA's 'Image of the Day', resize it, and save it as a PNG.
# https://www.nasa.gov/multimedia/imagegallery/iotd.html
#
# Dependencies:
#   feedparser
#   pillow
#   requests

import argparse
import os
from io import BytesIO

import feedparser
import requests
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

DESKTOP_WIDTH = 2560
DESKTOP_HEIGHT = 1600


def parseRss(verbose=False):
    """Extracts the URL and description of the most recent 'Image of the Day'.
    
    Returns:
        A tuple containing the URL of the image and a string description of the image.
    """
    nasa_rss = feedparser.parse('https://www.nasa.gov/rss/dyn/lg_image_of_the_day.rss')

    recent = nasa_rss.entries[0]
    if verbose:
        print('grabbing image published {}'.format(recent.get('published', 'unknown')))
    description = recent.get('description', None)

    image_url = str()
    for enclosure in recent.links:
        if enclosure['type'] == 'image/jpeg':
            image_url = enclosure['href']

    return image_url, description


def downloadImage(image_url):
    """Download the image from NASA.
    
    Args:
        image_url: The string URL to download.
        
    Returns:
        A BytesIO object containing the image data.
    """
    req = requests.get(image_url)
    return BytesIO(req.content)


def resizeImage(image, verbose=False):
    """Resizes the image while maintaining aspect ratio.
    
    The global variables DESKTOP_WIDTH and DESKTOP_HEIGHT are used to calculate
    the aspect ratio of the original image. The ratio is then maintained when resizing
    the image such that the maximum size is within the global variables defined.
    
    Args:
        image: A Pillow Image object.
        
    Returns:
        A new Pillow Image object that has been resized.
    """
    image_width = image.size[0]
    image_height = image.size[1]
    if image_width == DESKTOP_WIDTH and image_height == DESKTOP_HEIGHT:
        if verbose:
            print('image is same size as desktop dimensions, nothing to do')
        return image
    
    if verbose:
        print('unmodified image is {}×{}'.format(image_width, image_height))

    x_ratio = float(DESKTOP_WIDTH / image_width)
    y_ratio = float(DESKTOP_HEIGHT / image_height)

    if x_ratio < y_ratio:
        width, height = DESKTOP_WIDTH, int(image_height * x_ratio)
    else:
        width, height = int(image_width * y_ratio), DESKTOP_HEIGHT

    if verbose:
        print('resized image to {}×{}'.format(width, height))

    return image.resize((width, height))


def drawDescription(image, font, description):
    """
    Draw the description onto the image.

    This function will wrap the text if it is wider than the image.

    Args:
        image: A Pillow Image object.
        font: A Pillow ImageFont object.
        description: A string.
    """
    def _toowide(line):
        width, _ = font.getsize(line)
        # Subtract 5 pixels from the width to allow a little space for
        # readability on the right side of the image.
        if width > image.size[0] - 5:
            return True
        return False

    line = description.split()
    wrapped = []
    continuation = []
    while True:
        # Loop over the description popping off the last word until it is less
        # wide than the image. The words popped off are inserted into the
        # beginning of continuation to provide proper word order.
        while _toowide(' '.join(line)):
            continuation.insert(0, line.pop())

        wrapped.append(' '.join(line))
        if _toowide(' '.join(continuation)):
            # Still need to wrap another line.
            line = continuation
        else:
            wrapped.append(' '.join(continuation))
            break

    draw = ImageDraw.Draw(image)

    width, height = draw.multiline_textsize('\n'.join(wrapped), font)
    x, y = (5, image.size[1] - height)
    draw.rectangle((x, y, x + width, y + height), fill='black')
    draw.multiline_text((x, y), '\n'.join(wrapped), fill='lime', font=font)


def addMatte(image):
    """Create a black matte and paste image over the top.

    Args:
        image: A Pillow Image object.

    Returns:
        A new Pillow Image object.
    """
    image_width = image.size[0]
    image_height = image.size[1]
    width_diff = DESKTOP_WIDTH - image_width
    height_diff = DESKTOP_HEIGHT - image_height

    origin_x, origin_y = 0, 0
    if width_diff > 0:
        origin_x = int(width_diff / 2)

    if height_diff > 0:
        origin_y = int(height_diff / 2)

    # Defines the x & y coordinates to begin pasting the image over the matte.
    origin = (origin_x, origin_y)

    matte = Image.new('RGB', (DESKTOP_WIDTH, DESKTOP_HEIGHT))
    matte.paste(image, origin)
    return matte


def parseArguments():
    parser = argparse.ArgumentParser(description='Download NASA\'s Image of the Day')
    parser.add_argument('-i', '--input_file', help='path to input file')
    parser.add_argument('-o', '--output_file', help='path to output file')
    parser.add_argument('-c', '--cache_image', action='store_true', help='save unmodified image to /tmp')
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose logging')
    return parser.parse_args()


def main():
    args = parseArguments()

    image_url, description = parseRss(args.verbose)

    if args.input_file is None:
        nasa_image = Image.open(downloadImage(image_url))
    else:
        nasa_image = Image.open(args.input_file)

    output_filename = image_url.rsplit('/', 1)[1]
    if args.cache_image:
        if args.verbose:
            print('writing unmodified image to /tmp/{}'.format(output_filename))
        nasa_image.save('/tmp/' + output_filename)

    if args.output_file is None:
        output_file = os.path.join(os.environ['HOME'], output_filename)
    else:
        output_file = args.output_file

    resized_image = resizeImage(nasa_image, args.verbose)
    font = ImageFont.truetype('/usr/share/fonts/TTF/LiberationSerif-Regular.ttf', 18)
    drawDescription(resized_image, font, description)
    completed_image = addMatte(resized_image)

    if args.verbose:
        print('writing modified image to', output_file)

    completed_image.save(output_file, 'PNG')


if __name__ == '__main__':
    main()
