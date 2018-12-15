import logging
from time import sleep
import os.path
import datetime
from sys import exit

import fanfara

logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] (%(threadName)-10s) %(message)s',)

# check if it's not already started

fname = '/tmp/fanfara.lock'
# if lock file exists another login is in execution. hence ignore this one
try:
    if os.path.isfile(fname):
        f = open(fname, "r")
        content = f.read()
        logging.info('Found existing lock file in the system with value: %s ' % content)
        f.close()
        exit(0)
    else:
        # create lock file in writing - truncate mode
        f = open(fname, "w")
        f.write( str(datetime.datetime.now()) )
        f.close()
except IOError:
    logging.error('Error while accessing file %s' % fname)
    exit(1)


def button_pressed():
    logging.info('Green button pressed')
    sleep(0.8)
    fanfara.start()


try:
    for x in range(0, 3):
        msg = "%d" % (x+1)
        fanfara.to_display_clear(msg)
        sleep(1)

    fanfara.to_display_clear("Press green")

    # main loop
    while True:
        if not fanfara.GPIO.input(fanfara.START_PAUSE_BTN_PIN):
            button_pressed()
            break
        sleep(0.2)

finally:
    logging.debug('Removing lock file')
    if os.path.isfile(fname):
        os.remove(fname)
    else:
        logging.error('Could not find lock file with name %s' % fname)

logging.debug('Exiting main')

