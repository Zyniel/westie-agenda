import argparse
import json
import yaml
import logging
from typing import Any
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

__doc__ = "Create an image mosaic of weekly events"

from mosaic_helper import MosaicHelper

# Define logger
log = logging.getLogger('com.zyniel.dance.westie-agenda.community-helper')
logging.basicConfig(level=logging.DEBUG)

class PILMosaicHelper(MosaicHelper):
    """
    PIL implementation of the MosaicHelper.
    Now uses 1200px images
    """

    def __init__(self, config, data):
        super().__init__(config, data)
        self.image = None
        self.draw = None

    def _MosaicHelper__draw_canvas(self, width, height, background_color) -> Any:
        self.image = Image.new("RGB", (width, height), self.config['mosaic']['background_color'])
        self.draw = ImageDraw.Draw(self.image)

    def _MosaicHelper__draw_logo(self, picture_size: tuple[int,int]):
        """
        Draw the logo/trademark.

        :return:
        """
        width = self.config['mosaic']['logo']['size']['width']
        height = self.config['mosaic']['logo']['size']['height']
        file = Path(self.config['app']['misc_folder'], self.config['mosaic']['logo']['file']).absolute().as_posix()

        event_image = Image.open(file).resize((width, height))
        event_image.convert("RGBA")
        x_pos = picture_size[0] - width - 10
        y_pos = 10
        self.image.paste(event_image, (x_pos, y_pos), event_image)
        log.debug(f'Banner: ({x_pos},{y_pos})')

    def _MosaicHelper__draw_event(self, title: str, event_image_path: str, x_pos: int, y_pos: int, title_size: (int, int), event_title_font):
        """
        Draw a new event tile.

        :param title: Title of the event
        :param event_image_path: Image filepath to open and paste
        :param x_pos: X axis of the initial TL corner of the event zone
        :param y_pos: Y axis of the initial TL corner of the event zone
        :param title_size: Size of the event title zone
        :param event_title_font: Font size of the event title

        :return: None
        """
        event_title_width = self.draw.textlength(title, font=event_title_font)
        title_x_pos = x_pos + (title_size[0] - event_title_width) // 2
        title_y_pos = y_pos + self.config['mosaic']['event']['title']['padding']['top']
        self.draw.text(
            xy=(title_x_pos, title_y_pos),
            text=title,
            fill=self.config['mosaic']['event']['title']['font_color'],
            font=event_title_font
        )
        log.debug(f'Event Title: ({title_x_pos},{title_y_pos})')

        event_image = Image.open(event_image_path).resize((self.config['mosaic']['event']['banner']['size']['width'], self.config['mosaic']['event']['banner']['size']['height']))
        event_image.convert("RGBA")
        banner_x_pos = x_pos + self.config['mosaic']['event']['banner']['border']['left']
        banner_y_pos = y_pos + title_size[1] + self.config['mosaic']['event']['banner']['border']['top']
        self.image.paste(event_image, (banner_x_pos, banner_y_pos), event_image)
        log.debug(f'Event Banner: ({banner_x_pos},{banner_y_pos})')

    def _MosaicHelper__draw_global_title(self, title: str, total_width: int, title_font):
        """
        Draw the top main title of the picture.

        :param draw: Target canvas to write on
        :param title: Text to use as a title
        :param total_width: Computed text width
        :param title_font: ImageFont to use
        """
        title_width = self.draw.textlength(title, font=title_font)
        self.draw.text(
            xy=((total_width - title_width) / 2, self.config['mosaic']['padding']['top']),
            text=title,
            fill=self.config['mosaic']['title']['font_color'],
            font=title_font
        )

    def _MosaicHelper__build_title_font(self) -> Any:
        title_font = ImageFont.truetype(f"./fonts/{self.config['mosaic']['title']['font_file']}", self.config['mosaic']['title']['font_size'])
        return title_font

    def _MosaicHelper__build_event_title_font(self) -> Any:
        event_title_font = ImageFont.truetype(f"./fonts/{self.config['mosaic']['event']['title']['font_file']}", self.config['mosaic']['event']['title']['font_size'])
        return event_title_font

    def _MosaicHelper__build_event_image_path(self, file_name) -> Any:
        path = Path(file_name)
        path = path.with_name(path.stem + '-1200px' + path.suffix)
        full_path = Path(self.config['app']['png_folder'], path).absolute().as_posix()
        return full_path

    def save_as_png(self, path: str):
        """
        Generate a mosaic of events and save it as PNG.

        :param path: Target PNG file path
        :return: None
        """
        # Save the final image in the highest quality
        self.image.save(path)
        log.info(f'Save as PNG: {path}')

    def save_as_jpg(self, path: str):
        """
        Generate a mosaic of events and save it as JPG (HQ).

        :param path: Target PNG file path
        :return: None
        """
        # Save the final image in the highest quality
        self.image.save(path, quality=95)
        log.info(f'Save as JPG: {path}')

def main():

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--conf', action='append')
    args = parser.parse_args()

    if args.conf is not None:
        log.setLevel(level=logging.INFO)

        # Load configuration file
        with open(args.conf[0], 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)

        # Load data file
        with open(config['app']['data_file'], 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Create image and save in both PNG and JPG
        helper = PILMosaicHelper(config=config, data=data)
        helper.create()
        helper.save_as_jpg(str(Path(config['app']['export_folder'], f'{data['week_full'][0]}.jpg').absolute()))
        helper.save_as_png(str(Path(config['app']['export_folder'], f'{data['week_full'][0]}.png').absolute()))

if __name__ == '__main__':
    main()