# NASA Image of the Day downloader

Downloads the most recent image from NASA's [Image of the Day RSS](https://www.nasa.gov/rss/dyn/lg_image_of_the_day.rss)
feed. The image is downloaded, resized if necessary (maintaining aspect ratio), and finally the text description from
the RSS item is added to the image.

## Requirements

- [python](https://www.python.org/)
- [requests](https://pypi.org/project/requests/)
- [feedparser](https://pypi.org/project/feedparser/)
- [pillow](https://pypi.org/project/Pillow/)
- [python-xlib](https://pypi.org/project/xlib/)
