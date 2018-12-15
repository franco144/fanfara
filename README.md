# fanfara

Raspberry pi project to be used during an ice hockey game to show game information and also signal sessions and end of the game by firing a horn.
The raspberry pi is connected to a two line LCD display which shows information, two push buttons to reset and start/pause sessions and a relay which the horn is connected to.

File needed:
file RPi_I2C_driver.py is used to interact with LCD display.

from repo: https://github.com/emcniece/rpi-lcd.git 
Thanks to emcniece

- Make sure pin for buttons correspond to `fanfara-pinout.png` image. If buttons are attached to different pin than what the image says, don't forget to update the code with the new pins
- run `python main.py`
