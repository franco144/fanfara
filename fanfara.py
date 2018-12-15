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
start_pause_button_pin = 24
reset_button_pin = 7

GPIO.setup(start_pause_button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(reset_button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# rele setup
siren_pin = 4
# init rele pin as output, and turns it off
GPIO.setup(siren_pin, GPIO.OUT)
GPIO.output(siren_pin, GPIO.HIGH)

# session details
NO_SESSIONS = 24
# one session duration in seconds
SESSION_TIME = 60

# rele commands
RELE_ON = GPIO.LOW
RELE_OFF = GPIO.HIGH

# siren duration
END_SESSION_SIREN_DURATION = 1.5


def switch_siren(mode):
    GPIO.output(siren_pin, mode)


def fire_siren(fire_duration):
    switch_siren(RELE_ON)
    sleep(fire_duration)
    switch_siren(RELE_OFF)
    sleep(.300)


def fire_siren_end_game():
    fire_siren(1.5)
    fire_siren(1.5)
    fire_siren(2.5)


def start_pause_button_callback(channel):
    global is_start_pause_btn_pressed
    # sleep(0.005) #edge de-bounce of 5ms
    print "---detected---"
    is_start_pause_btn_pressed = True


def reset_button_callback(channel):
    global is_reset_btn_pressed, is_session_running

    if not is_session_running:
        return

    GPIO.remove_event_detect(channel)

    if GPIO.input(channel) == 0:
        is_reset_btn_pressed = True

    # event is added when resuming. see main loop
    # GPIO.add_event_detect(channel, GPIO.FALLING, callback=reset_button_callback, bouncetime=300)


def wait_for_input():
    waiting = True

    logging.debug("Waiting for input...")
    while waiting:
        sleep(0.1)
        if not GPIO.input(start_pause_button_pin):
            waiting = False


def to_display_clear(message="-_-", row=1, col=0):
    display.lcd_display_string_pos("                ", row, col)
    display.lcd_display_string_pos(message, row, col)
    logging.info(message)


def to_display_and_screen(message, row=1, col=0):
    display.lcd_display_string_pos(message, row, col)
    logging.info(message)


# variable initiation
is_game_finished = False
is_start_pause_btn_pressed = False
remaining_time_session = 0
no_curr_session = 0
remaining_time_game = 0
is_reset_btn_pressed = True
is_session_running = False


def blocking_init():
    global is_game_finished, remaining_time_session, no_curr_session, remaining_time_game, script_start_time

    # in seconds
    remaining_time_session = SESSION_TIME

    no_curr_session = 1
    is_game_finished = False

    to_display_and_screen("Ready to start..")
    to_display_and_screen('{0:.1f}'.format(remaining_time_session), 2, 0)
    to_display_and_screen('{:02d}/{:02d}'.format(no_curr_session, NO_SESSIONS), 2, 5)
    to_display_and_screen('{:02d}:{:02d}'.format(0, 0), 2, 11)
    # switch_siren( OFF )

    # how long does the match last ?
    remaining_time_game = datetime.timedelta(seconds=NO_SESSIONS * SESSION_TIME)  # in seconds
    remaining_time_game_split = divmod(remaining_time_game.total_seconds(), 60)
    to_display_and_screen("{:02.0f}:{:02.0f}".format(remaining_time_game_split[0],
                                                     floor(remaining_time_game_split[1])), 2, 11)

    wait_for_input()

    # debug
    script_start_time = datetime.datetime.now()
    logging.debug("Script started at {}", str(script_start_time))


#
# Main loop
#
def start():
    global is_session_running, is_reset_btn_pressed, is_game_finished, remaining_time_session, \
        no_curr_session, remaining_time_game, is_start_pause_btn_pressed, start_pause_button_pin, reset_button_pin

    try:
        is_session_running = False

        while not is_game_finished:

            if is_reset_btn_pressed:
                GPIO.remove_event_detect(start_pause_button_pin)
                GPIO.remove_event_detect(reset_button_pin)

                blocking_init()

                is_reset_btn_pressed = False
                GPIO.add_event_detect(reset_button_pin, GPIO.FALLING, callback=reset_button_callback, bouncetime=300)

            logging.debug("Time remained: {}".format(str(remaining_time_session)))
            is_new_session = True
            # wait for pin to fall to zero
            GPIO.add_event_detect(start_pause_button_pin, GPIO.FALLING, callback=start_pause_button_callback,
                                  bouncetime=1000)

            while remaining_time_session > 0.1:
                if is_reset_btn_pressed:
                    break
                if is_new_session:
                    is_session_running = True
                    is_new_session = False
                    to_display_clear("Session " + str(no_curr_session))

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
                    logging.debug("total time: " + time_game_left_split)
                    # update display with total time
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

            # FRAN remove, pause btn should always be possible to press
            is_start_pause_btn_pressed = False  # in case it was pressed right at the end

            partial = divmod((datetime.datetime.now() - script_start_time).total_seconds(), 60)
            logging.debug("<== session duration {:02.0f}:{:02.3f}".format(partial[0], partial[1]))

            GPIO.remove_event_detect(start_pause_button_pin)
            # avoid to issue a reset between sessions
            GPIO.remove_event_detect(reset_button_pin)  # FRAN remove, reset should always be possible

            # game code
            if no_curr_session >= NO_SESSIONS:
                to_display_clear("End of the match")
                is_game_finished = True
                fire_siren_end_game()
            elif not is_reset_btn_pressed:
                fire_siren_thread = threading.Thread(target=fire_siren, args=(END_SESSION_SIREN_DURATION,))
                fire_siren_thread.start()
                to_display_clear("End of session!")

                no_curr_session += 1
                remaining_time_session = SESSION_TIME

                to_display_and_screen("Start session " + str(no_curr_session))
                to_display_and_screen('{0:.1f}'.format(remaining_time_session), 2, 0)
                to_display_and_screen("{:02d}/{:02d}".format(no_curr_session, NO_SESSIONS), 2, 5)  # i.e. 02/24
                wait_for_input()

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

