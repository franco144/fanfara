#!/usr/bin/python

import threading
import logging

import RPi.GPIO as GPIO

from time import sleep
import datetime
from math import floor

import sys

sys.path.insert(0, "lcd/rpi-lcd")
import RPi_I2C_driver

logging.basicConfig(level=logging.DEBUG,
                    format='[%(levelname)s] (%(threadName)-10s) %(message)s', )

# get a display
display = RPi_I2C_driver.lcd()

GPIO.setmode(GPIO.BCM)

# button setup
START_PAUSE_BTN_PIN = 24
RESET_BTN_PIN = 7

GPIO.setup(START_PAUSE_BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(RESET_BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# rele setup
SIREN_PIN = 4
# init rele pin as output, and turns it off
GPIO.setup(SIREN_PIN, GPIO.OUT)
GPIO.output(SIREN_PIN, GPIO.HIGH)

# session details
NO_GAME_SESSIONS = 24
# one session duration in seconds
SESSION_TIME = 60

# rele commands
RELE_ON = GPIO.LOW
RELE_OFF = GPIO.HIGH

# siren duration
END_SESSION_SIREN_DURATION = 1.5


def switch_siren(mode):
    GPIO.output(SIREN_PIN, mode)


def fire_siren(fire_duration):
    switch_siren(RELE_ON)
    sleep(fire_duration)
    switch_siren(RELE_OFF)
    sleep(.300)


def fire_siren_end_game():
    fire_siren(1.8)
    fire_siren(1.8)
    fire_siren(2.5)


def start_pause_button_callback(channel):
    global is_start_pause_btn_pressed
    # sleep(0.005) #edge de-bounce of 5ms
    logging.debug("\n<---start/pause btn detected--->\n")
    is_start_pause_btn_pressed = True


def reset_button_callback(channel):
    global is_reset_btn_pressed, is_session_running

    if not is_session_running:
        logging.info("Cannot reset while session is not running")
        return

    GPIO.remove_event_detect(channel)

    if GPIO.input(channel) == 0:
        logging.info("Reset button has been pressed")
        is_reset_btn_pressed = True

    # event is added when resuming. see main loop
    # GPIO.add_event_detect(channel, GPIO.FALLING, callback=reset_button_callback, bouncetime=300)


def wait_for_input():
    waiting = True

    logging.info("Waiting for input...")
    while waiting:
        sleep(0.1)
        if not GPIO.input(START_PAUSE_BTN_PIN):
            waiting = False


def to_display_clear(message="-_-", row=1, col=0):
    display.lcd_display_string_pos("                ", row, col)
    display.lcd_display_string_pos(message, row, col)
    logging.info(message)


def to_display_and_screen(message, row=1, col=0):
    display.lcd_display_string_pos(message, row, col)
    logging.info(message)


# variable initiation
is_start_pause_btn_pressed = False
is_reset_btn_pressed = False
is_game_finished = False
is_session_running = False
is_session_new = True
no_curr_session = 0
remaining_time_session = 0
remaining_time_game = 0


def blocking_init_game():
    """
    This function can be called every time a new game, not session, has to start.
    Either on first run or after the reset button has been pressed.
    It resets the status so that a new game can start and waits for user to press 'start' button
    """
    global is_game_finished, remaining_time_session, no_curr_session, remaining_time_game, script_start_time, \
        is_session_new

    logging.info("Initiating new game")
    # in seconds
    remaining_time_session = SESSION_TIME

    no_curr_session = 1
    is_game_finished = False
    is_session_new = True  # True if there has been no loop for this session yet

    to_display_and_screen("Ready to start..")
    to_display_and_screen('{0:.1f}'.format(remaining_time_session), 2, 0)
    to_display_and_screen('{:02d}/{:02d}'.format(no_curr_session, NO_GAME_SESSIONS), 2, 5)
    to_display_and_screen('{:02d}:{:02d}'.format(0, 0), 2, 11)

    # how long does the match last ?
    remaining_time_game = datetime.timedelta(seconds=NO_GAME_SESSIONS * SESSION_TIME)  # in seconds
    remaining_time_game_split = divmod(remaining_time_game.total_seconds(), 60)
    to_display_and_screen("{:02.0f}:{:02.0f}".format(remaining_time_game_split[0],
                                                     floor(remaining_time_game_split[1])), 2, 11)

    remove_button_callbacks()
    wait_for_input()  # wait input on start/pause button
    add_button_callbacks()

    logging.info("Started new game")
    # debug
    script_start_time = datetime.datetime.now()
    logging.debug("Script started at {}", str(script_start_time))


def add_button_callbacks():
    # add callbacks for reset and start/pause buttons
    GPIO.add_event_detect(RESET_BTN_PIN,
                          GPIO.FALLING,
                          callback=reset_button_callback,
                          bouncetime=300)
    GPIO.add_event_detect(START_PAUSE_BTN_PIN,
                          GPIO.FALLING,
                          callback=start_pause_button_callback,
                          bouncetime=1000)


def remove_button_callbacks():
    GPIO.remove_event_detect(START_PAUSE_BTN_PIN)
    GPIO.remove_event_detect(RESET_BTN_PIN)


#
# Main loop
#
def start():
    global is_session_running, is_reset_btn_pressed, is_game_finished, remaining_time_session, \
        no_curr_session, remaining_time_game, is_start_pause_btn_pressed, is_session_new

    try:
        is_session_running = False

        # initialize new game
        blocking_init_game()

        while not is_game_finished:
            logging.info("[==> session remaining time : {}".format(str(remaining_time_session)))

            if is_reset_btn_pressed:
                blocking_init_game()
                is_reset_btn_pressed = False

            while remaining_time_session > 0.1:
                if is_reset_btn_pressed:
                    break

                if is_session_new:
                    is_session_running = True
                    is_session_new = False
                    to_display_clear("Session {}".format(str(no_curr_session)))

                if is_session_running:
                    sleep(0.430)  # 0.430 is tested on a 60 seconds session
                    elapsed = 0.5
                    remaining_time_session -= elapsed

                    time_format = '{0:.1f}'.format(remaining_time_session)
                    to_display_and_screen(time_format, 2, 0)  # 0.0

                    # calculate and log time
                    remaining_time_game = remaining_time_game - datetime.timedelta(seconds=elapsed)
                    time_game_left = divmod(remaining_time_game.total_seconds(), 60)
                    time_game_left_split = "{:02.0f}:{:02.0f}".format(time_game_left[0], floor(time_game_left[1]))
                    logging.debug("Game remaining time: " + time_game_left_split)
                    # update display with game remaining time
                    to_display_and_screen(time_game_left_split, 2, 11)  # time

                if is_start_pause_btn_pressed:
                    if is_session_running:
                        to_display_clear("Paused...")
                        logging.debug("\n")
                        is_session_running = False
                    else:
                        to_display_clear("Session {}".format(str(no_curr_session)))
                        is_session_running = True

                    is_start_pause_btn_pressed = False

            """ 
            At this point the session has finished
            """

            partial = divmod((datetime.datetime.now() - script_start_time).total_seconds(), 60)
            logging.debug("<==] session duration {:02.0f}:{:02.3f}".format(partial[0], partial[1]))

            # check if game is finished
            if no_curr_session >= NO_GAME_SESSIONS:
                to_display_clear("End of Game!")
                is_game_finished = True
                fire_siren_end_game()
            elif not is_reset_btn_pressed:
                # session ended: fire the siren
                fire_siren_thread = threading.Thread(target=fire_siren, args=(END_SESSION_SIREN_DURATION,))
                fire_siren_thread.start()
                to_display_clear("End of session!")

                no_curr_session += 1
                remaining_time_session = SESSION_TIME
                is_session_new = True

                # to_display_and_screen("Start session {}".format(str(no_curr_session)))
                to_display_and_screen('{0:.1f}'.format(remaining_time_session), 2, 0)
                to_display_and_screen("{:02d}/{:02d}".format(no_curr_session, NO_GAME_SESSIONS), 2, 5)  # i.e. 02/24
            else:
                logging.info("Unhandled flow... reset button is expected to be pressed at this point")

    except KeyboardInterrupt:
        logging.info("Caught keyboard interrupt")
    finally:
        logging.info("Exited main loop")
        to_display_clear("Finished!")

        # turn it off to be sure
        switch_siren(RELE_OFF)

        # Reset the GPIO pin to a safe state
        GPIO.cleanup()
        display.lcd_clear()

