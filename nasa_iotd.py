#!/usr/bin/python
# 2016-12-08
# Grab NASA's 'Image of the Day', resize it, and save it as a PNG.
# https://www.nasa.gov/multimedia/imagegallery/iotd.html
#
# Dependencies:
#   feedparser
#   pillow
#   requests

import os
from io import BytesIO
from optparse import OptionParser

import feedparser
import requests
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont


DESKTOP_WIDTH = 2650
DESKTOP_HEIGHT = 1600
MAX_FILE_SIZE = 1 << 32

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


def downloadImage(image_url):
    """Download the image from NASA.
    
    Args:
        image_url: The string URI to download.
        
    Returns:
        A BytesIO object containing the image data.
    """
    req = requests.get(image_url)
    return BytesIO(req.content)


def resizeImage(image):
    """Resizes the image and maintains aspect ratio.
    
    The global variables DESKTOP_WIDTH and DESKTOP_HEIGHT are used to calculate
    the aspect ratio of the original image. The ratio is then maintained when resizing
    the image such that the maximum size is within the global variables defined.
    
    Args:
        image: A pillow Image.
        
    Returns:
        A pillow Image that has been resized.
    """
    if nasa_image.size[0] == DESKTOP_WIDTH and nasa_image.size[1] == DESKTOP_HEIGHT:
        return image
    
    x_ratio = float(DESKTOP_WIDTH / image.size[0])
    y_ratio = float(DESKTOP_HEIGHT / image.size[1])

    if x_ratio < y_ratio:
        width, height = DESKTOP_WIDTH, int(image.size[1] * x_ratio)
    else:
        width, height = int(image.size[0] * y_ratio), DESKTOP_HEIGHT
    return image.resize((width, height))


def main():
    parser = OptionParser()
    parser.add_option('-i', '--input_file', help='path to input file')
    parser.add_option('-o', '--output_file', help='path to output file')
    (options, args) = parser.parse_args()

    (image_url, description) = parseRss()

    if options.input_file is None:
        nasa_image = Image.open(downloadImage(image_url))
    else:
        nasa_image = Image.open(options.input_file)

    nasa_image = resizeImage(nasa_image)

    draw = ImageDraw.Draw(nasa_image)
    font = ImageFont.truetype('/usr/share/fonts/TTF/LiberationSerif-Regular.ttf', 18)
    w, h = font.getsize(description)
    x, y = (5, nasa_image.size[1] - h)
    draw.rectangle((x, y, x + w, y + h), fill='black')
    draw.text((x, y), description, fill=(164, 244, 66), font=font)
    # draw.text((x, y), description, fill='green', font=font)

    # If the resized NASA image does not have the same dimensions as the
    # desktop, create a new image that is the same dimensions as the desktop
    # and is entirely black. The NASA image will be pasted over the top of this
    # to create a matte.
    if nasa_image.size[0] != DESKTOP_WIDTH or nasa_image.size[1] != DESKTOP_HEIGHT:
        image = Image.new('RGB', (DESKTOP_WIDTH, DESKTOP_HEIGHT))
        width_diff = DESKTOP_WIDTH-nasa_image.size[0]
        height_diff = DESKTOP_HEIGHT-nasa_image.size[1]

        if width_diff > 0:
            box = (int(width_diff / 4), 0)
        elif height_diff > 0:
            box = (0, int(height_diff / 4))

        image.paste(nasa_image, box)

    if options.output_file is None:
        output_file = os.path.join(os.environ['HOME'], '.lockimg')

    image.save(output_file, 'PNG')


if __name__ == '__main__':
    main()
