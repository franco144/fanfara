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
startPauseButtonPin = 24
resetButtonPin = 7

GPIO.setup(startPauseButtonPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(resetButtonPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# rele setup
pinSiren = 4
# init rele pin as output, and turns it off
GPIO.setup(pinSiren, GPIO.OUT)
GPIO.output(pinSiren, GPIO.HIGH)

# session details
totSessions = 24
# one session duration in seconds
sessionTime = 60

# rele commands
ON = GPIO.LOW
OFF = GPIO.HIGH

# siren duration
sirenDurationEndSession = 1.5


def switch_siren(mode):
    # print "switching "+ str(mode)
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

    if started == False:
        return

    GPIO.remove_event_detect(channel)

    if GPIO.input(channel) == 0:
        reset = True

    logging.debug('reset_button_callback called. Reset is ' + str(reset))
    # event is added when resuming. see main loop
    # GPIO.add_event_detect(channel, GPIO.FALLING, callback=reset_button_callback, bouncetime=300)


def wait_for_input():
    waiting = True
    # print "waiting for input"
    while waiting == True:
        sleep(0.1)
        if False == GPIO.input(startPauseButtonPin):
            waiting = False


def to_display_clear(message="-_-", row=1, col=0):
    display.lcd_display_string_pos("                ", row, col)
    display.lcd_display_string_pos(message, row, col);
    logging.info(message)


def to_display_and_screen(message, row=1, col=0):
    display.lcd_display_string_pos(message, row, col)
    logging.info(message)


# variable initiation
gameFinished = detected = False
remainingTime = currSession = matchCountdown = 0
reset = True
started = False


def blocking_init():
    global gameFinished, remainingTime, currSession, totSessions, matchCountdown, sessionTime, scriptstart

    # in seconds
    remainingTime = sessionTime

    currSession = 1
    gameFinished = False

    to_display_and_screen("Ready to start..")
    to_display_and_screen('{0:.1f}'.format(remainingTime), 2, 0)
    to_display_and_screen('{:02d}/{:02d}'.format(currSession, totSessions), 2, 5)
    to_display_and_screen('{:02d}:{:02d}'.format(0, 0), 2, 11)
    # switch_siren( OFF )

    # how long does the match last ?
    matchCountdown = datetime.timedelta(seconds=totSessions * sessionTime)  # in seconds
    matchCountdownTuple = divmod(matchCountdown.total_seconds(), 60)
    to_display_and_screen("{:02.0f}:{:02.0f}".format(matchCountdownTuple[0], floor(matchCountdownTuple[1])), 2, 11)

    wait_for_input()

    # debug
    scriptstart = datetime.datetime.now()
    logging.debug("==> started at " + str(scriptstart))


#
# Main loop
#
def start():
    global started, reset, gameFinished, remainingTime, currSession, totSessions, matchCountdown, detected, sessionTime, startPauseButtonPin, resetButtonPin, sirenDurationEndSession

    try:
        started = False

        while not gameFinished:

            if reset == True:
                GPIO.remove_event_detect(startPauseButtonPin)
                GPIO.remove_event_detect(resetButtonPin)

                blocking_init()

                reset = False
                GPIO.add_event_detect(resetButtonPin, GPIO.FALLING, callback=reset_button_callback, bouncetime=300)

            logging.debug("remainingTime: " + str(remainingTime))

            initiated = False
            # wait for pin to fall to zero
            GPIO.add_event_detect(startPauseButtonPin, GPIO.FALLING, callback=start_pause_button_callback,
                                  bouncetime=1000)

            while remainingTime > 0.1:
                if reset == True:
                    break
                if initiated == False:
                    started = True
                    initiated = True
                    to_display_clear("Session " + str(currSession))

                if started == True:
                    sleep(0.430)  # 0.430 is tested on a 60 seconds session
                    elapsed = 0.5
                    remainingTime -= elapsed
                    timeformat = '{0:.1f}'.format(remainingTime)
                    to_display_and_screen(timeformat, 2, 0)  # 0.0

                    # calculate and log time
                    matchCountdown = matchCountdown - datetime.timedelta(seconds=elapsed)
                    totalTime = divmod(matchCountdown.total_seconds(), 60)
                    totalTimeFormatted = "{:02.0f}:{:02.0f}".format(totalTime[0], floor(totalTime[1]))
                    logging.debug("total time: " + totalTimeFormatted)
                    # update display with total time
                    to_display_and_screen(totalTimeFormatted, 2, 11)  # time

                if detected == True:
                    if started == True:
                        to_display_clear("Paused...")
                        print "\n"
                        started = False
                    else:
                        to_display_clear("Session " + str(currSession))
                        started = True

                    detected = False

            detected = False  # in case it was pressed right at the end

            partial = divmod((datetime.datetime.now() - scriptstart).total_seconds(), 60)
            logging.debug("<== session duration {:02.0f}:{:02.3f}".format(partial[0], partial[1]))

            GPIO.remove_event_detect(startPauseButtonPin)
            # avoid to issue a reset between sessions
            GPIO.remove_event_detect(resetButtonPin)

            # game code
            if currSession >= totSessions:
                to_display_clear("End of the match")
                gameFinished = True
                fire_end_game()
            elif reset == False:
                t = threading.Thread(target=fire_siren, args=(sirenDurationEndSession,))
                t.start()
                to_display_clear("End of session!")

                currSession += 1
                remainingTime = sessionTime

                to_display_and_screen("Start session " + str(currSession))
                to_display_and_screen('{0:.1f}'.format(remainingTime), 2, 0)
                to_display_and_screen("{:02d}/{:02d}".format(currSession, totSessions), 2, 5)  # 02/24
                wait_for_input()

    except KeyboardInterrupt:
        print "Caught keyboard interrupt"
    finally:
        print "Exited loop"
        to_display_clear("Exited!")

        switch_siren(OFF)

        # Reset the GPIO pin to a safe state
        GPIO.cleanup()
        display.lcd_clear()

