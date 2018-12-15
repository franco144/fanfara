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
        format='[%(levelname)s] (%(threadName)-10s) %(message)s',)

# get a display
display = RPi_I2C_driver.lcd()

GPIO.setmode(GPIO.BCM)

# button setup
startPauseButtonPin = 24
resetButtonPin = 7

GPIO.setup(startPauseButtonPin, GPIO.IN, pull_up_down = GPIO.PUD_UP)
GPIO.setup(resetButtonPin, GPIO.IN, pull_up_down = GPIO.PUD_UP)

#rele setup
pinSiren = 4
# init rele pin as output, and turns it off
GPIO.setup(pinSiren, GPIO.OUT)
GPIO.output(pinSiren, GPIO.HIGH)

# session details
totSessions = 24
# one session duration in seconds
session_time = 60

# rele commands
ON = GPIO.LOW
OFF = GPIO.HIGH

# siren duration
sirenDurationEndSession = 1.5


def switch_siren(mode):
    #print "switching "+ str(mode)
    GPIO.output(pinSiren, mode)


def fire_siren(fireDuration):
    switch_siren(ON)
    sleep(fireDuration)
    switch_siren(OFF)
    sleep(.300)


def fire_end_game():
    fire_siren(1.5)
    fire_siren(1.5)
    fire_siren(2)


def start_pause_button_callback(channel):
    global detected
    # sleep(0.005) #edge de-bounce of 5ms
    print "---detected---"
    detected = True


def reset_button_callback(channel):
    global reset, started

    if not started:
        return
    
    GPIO.remove_event_detect(channel)

    if GPIO.input(channel) == 0:
        reset = True
   
    logging.debug('reset_button_callback called. Reset is '+ str(reset))
    # event is added when resuming. see main loop
    # GPIO.add_event_detect(channel, GPIO.FALLING, callback=reset_button_callback, bouncetime=300)


def wait_for_input():
    waiting = True
    while waiting:
        sleep(0.1)
        if not GPIO.input(startPauseButtonPin):
            waiting = False


def to_display_clear(message="-_-", row=1, col=0):
    display.lcd_display_string_pos("                ", row, col )
    display.lcd_display_string_pos(message, row, col);
    logging.info( message )


def to_display_and_screen(message, row=1, col=0):
    display.lcd_display_string_pos(message, row, col)
    logging.info( message )


# variable initiation
gameFinished = detected = False
remaining_time = currSession = matchCountdown = 0
reset = False
started = False


def blocking_init():
    global gameFinished, remaining_time, currSession, totSessions, matchCountdown, session_time, script_start

    # in seconds
    remaining_time = session_time

    currSession = 1
    gameFinished = False
    
    to_display_and_screen("Ready to start..")
    to_display_and_screen('{0:.1f}'.format(remaining_time), 2, 0)
    to_display_and_screen('{:02d}/{:02d}'.format(currSession, totSessions), 2, 5)
    to_display_and_screen('{:02d}:{:02d}'.format(0, 0), 2, 11)
    # switch_siren( OFF )

    # how long does the match last ?
    matchCountdown = datetime.timedelta(seconds=totSessions * session_time)  # in seconds
    match_countdown_tuple = divmod(matchCountdown.total_seconds(), 60)
    to_display_and_screen("{:02.0f}:{:02.0f}".format(match_countdown_tuple[0], floor(match_countdown_tuple[1])), 2, 11)

    wait_for_input()

    # debug
    script_start = datetime.datetime.now()
    logging.debug("==> started at " + str(script_start))


#
# Main loop
#
def start():
    global started, reset, gameFinished, remaining_time, currSession, totSessions, matchCountdown, detected, session_time, startPauseButtonPin, resetButtonPin, sirenDurationEndSession

    try:
        while not gameFinished:
            if not started:
                logging.info('Not started yet. Wait for input')
                blocking_init()
                started = True

            # at this point button is pressed, loop until end of game is started
            to_display_and_screen("Session "+str(currSession))
            to_display_and_screen("Session "+str(currSession))

            # if reset:
            #     GPIO.remove_event_detect(startPauseButtonPin)
            #     GPIO.remove_event_detect(resetButtonPin)
            #
            #     blocking_init()
            #
            #     reset = False
            #     GPIO.add_event_detect(resetButtonPin, GPIO.FALLING, callback=reset_button_callback, bouncetime=300)

            # waits for pin to fall to zero
            GPIO.add_event_detect(startPauseButtonPin,
                                  GPIO.FALLING,
                                  callback=start_pause_button_callback,
                                  bouncetime=1500)

            logging.debug("remainingTime: "+str(remaining_time))
            while remaining_time > 0.1:
                if started:
                    sleep(0.430)  # 0.430 is tested on a 60 seconds session
                    elapsed = 0.5
                    remaining_time -= elapsed
                    time_format = '{0:.1f}'.format(remaining_time)
                    to_display_and_screen(time_format, 2, 0)  # 0.0

                    # calculate and log time
                    matchCountdown = matchCountdown - datetime.timedelta(seconds=elapsed)
                    total_time = divmod(matchCountdown.total_seconds(), 60)
                    total_time_formatted = "{:02.0f}:{:02.0f}".format(total_time[0], floor(total_time[1]))
                    logging.debug("total time: "+ total_time_formatted)
                    # update display with total time
                    to_display_and_screen(total_time_formatted, 2, 11)  # time

                if detected:
                    if started:
                        to_display_clear("Paused...")
                        started = False
                    else:
                        to_display_clear("Session "+str(currSession))
                        started = True

                    detected = False

            GPIO.remove_event_detect(startPauseButtonPin)

            partial = divmod((datetime.datetime.now() - script_start).total_seconds(), 60)
            logging.debug("<== session duration {:02.0f}:{:02.3f}".format(partial[0], partial[1]))

            # at this point session is finished
            if currSession >= totSessions:
                to_display_clear("End of the match")
                gameFinished = True
                fire_end_game()
            elif not reset:
                t = threading.Thread(target=fire_siren, args=(sirenDurationEndSession,))
                t.start()

                currSession += 1
                remaining_time = session_time

                to_display_and_screen("Session "+str(currSession))
                to_display_and_screen('{0:.1f}'.format(remaining_time), 2, 0)
                to_display_and_screen("{:02d}/{:02d}".format(currSession, totSessions), 2, 5)  # 02/24

    except KeyboardInterrupt:
        print "Caught keyboard interrupt"
    finally:
        print "Exited loop"
        to_display_clear("Exited!")

        switch_siren(OFF)

        # Reset the GPIO pin to a safe state
        GPIO.cleanup()
        display.lcd_clear()

