import argparse
import json
from datetime import datetime

import yaml
import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

__doc__ = "Create an image mosaic of weekly events"

class MosaicHelper:
    config = None     # Global Configuration JSON object
    data = None       # Event data
    layouts = None    # Grid layout per number of events

    def __init__(self, config, data):
        """
        Initialize the MosaicHelper with configuration and data.

        :param config: A JSON structure of configuration elements.
        :param data: A JSON structure of event data.
        """
        self.config = config
        self.data = data
        self.layouts = config['mosaic']['layouts']

    def __calculate_grid_size(self, size) -> tuple[int,int]:
        """
        Return the

        :param size:
        :return:
        """
        return self.layouts.get(size, (1, 1))

    def __get_grid_coordinates(self, idx: int, num_events: int) -> tuple[int,int]:
        """

        :param idx:
        :param num_events:
        :return:
        """
        cols, rows = self.__calculate_grid_size(num_events)
        x_idx = idx % cols
        y_idx = idx // cols
        logging.debug(f'Item {idx % cols}: ({x_idx},{y_idx})')
        return x_idx, y_idx

    def __get_event_full_size(self) -> tuple[int,int]:
        """
        Return the dimensions of an event zone including title, banner, padding ...
        :return: A tuple of width, height
        """
        width = (
                self.config['mosaic']['event']['banner']['padding']['left'] + self.config['mosaic']['event']['banner']['border']['left'] +
                self.config['mosaic']['event']['banner']['size']['width'] + self.config['mosaic']['event']['banner']['padding']['right'] +
                self.config['mosaic']['event']['banner']['border']['right']
        )
        height = (
                self.config['mosaic']['event']['banner']['padding']['top'] + self.config['mosaic']['event']['banner']['border']['top'] +
                self.config['mosaic']['event']['banner']['size']['height'] + self.config['mosaic']['event']['banner']['border']['bottom'] +
                self.config['mosaic']['event']['banner']['padding']['bottom'] + self.config['mosaic']['event']['title']['padding']['top'] +
                self.config['mosaic']['event']['title']['font_size'] + self.config['mosaic']['event']['title']['padding']['bottom']
        )
        return width, height

    def __get_event_title_size(self) -> tuple[int,int]:
        """
        Return the dimensions of an event title
        :return: A tuple of width, height
        """
        width = (
                self.config['mosaic']['event']['banner']['padding']['left'] + self.config['mosaic']['event']['banner']['border']['left'] +
                self.config['mosaic']['event']['banner']['size']['width'] + self.config['mosaic']['event']['banner']['border']['right'] +
                self.config['mosaic']['event']['banner']['padding']['right']
        )
        height = (
                self.config['mosaic']['event']['title']['padding']['top'] + self.config['mosaic']['event']['title']['font_size'] +
                self.config['mosaic']['event']['title']['padding']['bottom']
        )
        return width, height

    ####################### Main Functions ####################

    def __draw_logo(self, draw: ImageDraw, picture_size: tuple[int,int], image : Image):
        """
        Draw the logo/trademark.

        :param draw: Target canvas to write on
        :param image: Target PIL Image
        :return:
        """
        width = self.config['mosaic']['logo']['size']['width']
        height = self.config['mosaic']['logo']['size']['height']
        file = Path(self.config['app']['misc_folder'], self.config['mosaic']['logo']['file']).absolute().as_posix()

        event_image = Image.open(file).resize((width, height))
        event_image.convert("RGBA")
        x_pos = picture_size[0] - width - 10
        y_pos = 10
        image.paste(event_image, (x_pos, y_pos), event_image)
        logging.info(f'Banner: ({x_pos},{y_pos})')

    def __draw_global_title(self, draw: ImageDraw, title: str, total_width: int, title_font: ImageFont):
        """
        Draw the top main title of the picture.

        :param draw: Target canvas to write on
        :param title: Text to use as a title
        :param total_width: Computed text width
        :param title_font: ImageFont to use
        """
        title_width = draw.textlength(title, font=title_font)
        draw.text(
            xy=((total_width - title_width) / 2, self.config['mosaic']['padding']['top']),
            text=title,
            fill=self.config['mosaic']['title']['font_color'],
            font=title_font
        )

    def __draw_event(self, draw: ImageDraw, title: str, event_image_path: str, x_pos: int, y_pos: int, title_size: (int, int), event_title_font: ImageFont, image : Image):
        """
        Draw a new event tile.

        :param draw: Target canvas to write on
        :param title: Title of the event
        :param event_image_path: Image filepath to open and paste
        :param x_pos: X axis of the initial TL corner of the event zone
        :param y_pos: Y axis of the initial TL corner of the event zone
        :param title_size: Size of the event title zone
        :param event_title_font: Font size of the event title
        :param image: Target PIL Image

        :return: None
        """
        event_title_width = draw.textlength(title, font=event_title_font)
        title_x_pos = x_pos + (title_size[0] - event_title_width) // 2
        title_y_pos = y_pos + self.config['mosaic']['event']['title']['padding']['top']
        draw.text(
            xy=(title_x_pos, title_y_pos),
            text=title,
            fill=self.config['mosaic']['event']['title']['font_color'],
            font=event_title_font
        )
        logging.info(f'Title: ({title_x_pos},{title_y_pos})')

        event_image = Image.open(event_image_path).resize((self.config['mosaic']['event']['banner']['size']['width'], self.config['mosaic']['event']['banner']['size']['height']))
        event_image.convert("RGBA")
        banner_x_pos = x_pos + self.config['mosaic']['event']['banner']['border']['left']
        banner_y_pos = y_pos + title_size[1] + self.config['mosaic']['event']['banner']['border']['top']
        image.paste(event_image, (banner_x_pos, banner_y_pos), event_image)
        logging.info(f'Banner: ({banner_x_pos},{banner_y_pos})')

    def __create(self) -> Image:
        """
        Private function to instanciate a new Image and dra the mosaic from event data.

        :return: The newly created Image
        """
        # Compute number of events
        num_events = len(self.data['events'])

        ####################### Footer #######################
        footer_height = self.config['mosaic']['footer_height']
        ####################### Header #######################
        header_height = self.config['mosaic']['header_height']
        title_size = self.__get_event_title_size()
        ####################### Body #########################
        cols, rows = self.__calculate_grid_size(num_events)
        event_size = self.__get_event_full_size()
        body_width = cols * event_size[0] + self.config['mosaic']['event']['spacing']['right'] * (cols - 1)
        body_height = rows * event_size[1] + self.config['mosaic']['event']['spacing']['bottom'] * (rows - 1)
        ####################### Overall ######################
        total_width = self.config['mosaic']['padding']['left'] + body_width + self.config['mosaic']['padding']['right']
        total_height = self.config['mosaic']['padding']['top'] + header_height + body_height + footer_height + self.config['mosaic']['padding']['bottom']
        ######################################################
        # Font settings (make sure to have a suitable .ttf font file)
        title_font = ImageFont.truetype(f"./fonts/{self.config['mosaic']['title']['font_file']}", self.config['mosaic']['title']['font_size'])
        event_title_font = ImageFont.truetype(f"./fonts/{self.config['mosaic']['event']['title']['font_file']}", self.config['mosaic']['event']['title']['font_size'])

        # Create the base image
        image = Image.new("RGB", (total_width, total_height), self.config['mosaic']['background_color'])
        draw = ImageDraw.Draw(image)

        # Draw the global title
        global_title = f"Planning - Semaine du {self.data['week']}"
        self.__draw_global_title(draw, global_title, total_width, title_font)
        self.__draw_logo(draw, (total_width, total_height), image)

        # Draw each event
        for idx, event in enumerate(self.data['events']):
            x_idx, y_idx = self.__get_grid_coordinates(idx, num_events)
            event_title = event['Planning']
            event_image_path = Path(
                self.config['app']['png_folder'],
                event['Image']
            ).absolute().as_posix()

            # Calculate position and horizontal adjustment for partial rows
            if y_idx == num_events // cols:  # Only adjust for the last line
                num_events_in_last_row = num_events % cols  # Number of events in the last row
                total_event_width = num_events_in_last_row * event_size[0] + (num_events_in_last_row - 1) * self.config['mosaic']['event']['spacing']['right']
                blank_space = (body_width - total_event_width) // 2
                blank_space = max(0, blank_space)  # Ensure it's not negative
            else:
                blank_space = 0  # No adjustment for complete rows

            # Calculate position
            x_pos = self.config['mosaic']['padding']['left'] + x_idx * (self.config['mosaic']['event']['spacing']['right'] + event_size[0]) + blank_space
            y_pos = self.config['mosaic']['padding']['top'] + header_height + y_idx * (self.config['mosaic']['event']['spacing']['bottom'] + event_size[1])

            # Draw the event on the ImageDraw layer
            self.__draw_event(draw, event_title, event_image_path, x_pos, y_pos, title_size, event_title_font, image)

        return image

    def create_as_png(self, path: str):
        """
        Generate a mosaic of events and save it as PNG.

        :param path: Target PNG file path
        :return: None
        """
        # Save the final image in the highest quality
        image = self.__create()
        image.save(path)
        logging.info(f'Saving mosaic: {path}')

    def create_as_jpg(self, path: str):
        """
        Generate a mosaic of events and save it as JPG (HQ).

        :param path: Target PNG file path
        :return: None
        """
        # Save the final image in the highest quality
        image = self.__create()
        image.save(path, quality=95)
        logging.info(f'Saving mosaic: {path}')

def main():

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--conf', action='append')
    args = parser.parse_args()

    if args.conf is not None:
        logging.basicConfig(level=logging.INFO)

        # Load configuration file
        with open(args.conf[0], 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)

        # Load data file
        with open(config['app']['data_file'], 'r', encoding='utf-8') as f:
            data = json.load(f)

        helper = MosaicHelper(config=config, data=data)
        helper.create_as_jpg(Path(config['app']['export_folder'], f'{data['week_full'][0]}.jpg'))
        helper.create_as_png(Path(config['app']['export_folder'], f'{data['week_full'][0]}.png'))

if __name__ == '__main__':
    main()
