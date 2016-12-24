from time import sleep, time
import subprocess
import threading
from Queue import Queue
import os
import sys
import RPi.GPIO as GPIO
from settings import MEDIA_PATH, PREV_BUTTON_PIN, PLAY_BUTTON_PIN, \
    NEXT_BUTTON_PIN, STATUS_LED_PIN
from enum import Enum
import redis
redis_db = redis.StrictRedis()

import logging
from logging.handlers import RotatingFileHandler
logger = logging.getLogger('my_logger')
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(filename='player.log', maxBytes=5*1024*1024, backupCount=5)
logger.addHandler(handler)

logger.info('\nStarting...')


GPIO.setmode(GPIO.BCM)

# Set up button pins as input, pulled-up.
GPIO.setup(PREV_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(PLAY_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(NEXT_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)


# LED pin as output
GPIO.setup(STATUS_LED_PIN, GPIO.OUT)
GPIO.output(STATUS_LED_PIN, 0)


class STATUS(Enum):
    nothing = 0
    playing = 1
    loading = 2
    error = 3


led_thread_queue = Queue()
def status_led_func():
    c = 0
    status = STATUS.loading
    while True:
        if not led_thread_queue.empty():
            status = led_thread_queue.get_nowait()

        if status == None:
            break # Finish this thread

        if status == STATUS.nothing and GPIO.input(STATUS_LED_PIN) == 1:
            GPIO.output(STATUS_LED_PIN, 0)
        elif status == STATUS.playing:
            GPIO.output(STATUS_LED_PIN, (GPIO.input(STATUS_LED_PIN) + 1) % 2)
            sleep(0.4)
        elif status == STATUS.loading:
            GPIO.output(STATUS_LED_PIN, (GPIO.input(STATUS_LED_PIN) + 1) % 2)
            sleep(0.1)
        elif status == STATUS.error:
            if c == 0:
                GPIO.output(STATUS_LED_PIN, 0)
            elif c < 7:
                GPIO.output(STATUS_LED_PIN, (GPIO.input(STATUS_LED_PIN) + 1) % 2)
            c += 1
            c %= 12
            sleep(0.05)

        sleep(0.0001)


# start led thread
threading.Thread(target=status_led_func).start()


state = {
    'current_track': None,
    'current_frame': 0,
    'current_sec': 0,
}

class Track(object):
    def __init__(self, folder, name):
        self.folder = folder
        self.name = name

    @property
    def next(self):
        own_index = self.folder.tracks.index(self)
        next_index = own_index + 1
        if next_index >= len(self.folder.tracks):
            return None
        else:
            return self.folder.tracks[next_index]

    @property
    def prev(self):
        own_index = self.folder.tracks.index(self)
        if own_index >= 1:
            return self.folder.tracks[own_index -1]
        else:
            return None

    @property
    def full_path(self):
        return os.path.join(MEDIA_PATH, self.folder.name, self.name)

    def __repr__(self):
        return self.name

class Folder(object):
    def __init__(self, name):
        self.name = name
        track_names = sorted([f for f in os.listdir(os.path.join(MEDIA_PATH, self.name)) if f.endswith('.mp3')])
        self.tracks = [Track(self, name) for name in track_names]

    def __repr__(self):
        return self.name

all_folders = [Folder(name) for name in sorted(os.listdir(MEDIA_PATH))]
folders = [f for f in all_folders if f.tracks] # filter out empty folders

if not folders:
    led_thread_queue.put(STATUS.error)
    # TODO: say error with espeak?
    try:
        while True:
            sleep(0.0001)
    except KeyboardInterrupt:
        logger.info("Closing threads...")
        led_thread_queue.put(None)
        logger.info("Cleaning up GPIO...")
        GPIO.cleanup()
        logger.info("Exiting program...")
        sys.exit()



def get_continue_from():
    logger.info('Loading previous:')
    continue_from = redis_db.hgetall('continue_from')
    logger.info('\tcontinue_from: %s' % continue_from)
    if 'folder' in continue_from and 'track' in continue_from and 'frame' in continue_from:
        folder = next((f for f in folders if f.name == continue_from['folder']), None)
        if folder:
            logger.info('\tFolder found: %s' % folder)
            track = next((t for t in folder.tracks if t.name == continue_from['track']), None)
            if track and os.path.exists(track.full_path):
                logger.info('\tTrack found: %s' % track)
                return track, int(continue_from['frame'])

    logger.info('\tNo folder or track found. Falling back to the first one.')
    return folders[0].tracks[0], 0

def save():
    data = {
        'folder': state['current_track'].folder.name, 
        'track': state['current_track'].name, 
        'frame': state['current_frame']}
    redis_db.hmset('continue_from', data)
    logger.info('Saved: %s' % data)


def get_next_track():
    track = state['current_track']
    next_track = track.next
    if not next_track:
        # TODO: get next folder, first track
        current_folder_index = folders.index(track.folder)
        next_folder_index = current_folder_index + 1
        if next_folder_index >= len(folders):
            next_folder = folders[0]
        else:
            next_folder = folders[next_folder_index]
        return next_folder.tracks[0]
    else:
        return next_track

def get_prev_track():
    if state['current_sec'] <= 3 and state['current_track'].prev:
        return state['current_track'].prev
    else:
        return state['current_track']

def get_next_folder():
    next_folder_index = folders.index(state['current_track'].folder) + 1
    if next_folder_index >= len(folders):
        next_folder = folders[0]
    else:
        next_folder = folders[next_folder_index]
    return next_folder.tracks[0]

def get_prev_folder():
    folder_index = folders.index(state['current_track'].folder)
    if folder_index >= 1:
        prev_folder = folders[folder_index - 1]
    else:
        prev_folder = folders[-1]
    return prev_folder.tracks[0]


popen = subprocess.Popen(['mpg321', '-g', '50', '-R', 'anyword'], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)

def load(track, frame=0):
    state['current_track'] = track
    state['current_frame'] = frame
    cmd = 'LOAD %s\n' % track.full_path
    logger.info(cmd)
    popen.stdin.write(cmd)

    if not frame == 0:
        cmd = 'JUMP %s\n' % frame
        logger.info(cmd)
        popen.stdin.write(cmd)

    save()

def play_pause_button(channel):
    led_thread_queue.put(STATUS.nothing)
    popen.stdin.write('PAUSE\n')
    save()

button_state = {
    'down': False,
}

def pressed_time(channel):
    if GPIO.input(channel): # up
        button_state['down'] = False
    else: # down
        if not button_state['down']:
            button_state['down'] = True

            for i in range(100):
                sleep(0.01)
                if GPIO.input(channel) == 1:
                    # released
                    button_state['down'] = False
                    return "short"
            return "long"

def next_button(channel):
    t = pressed_time(channel)
    if t == 'short':
        led_thread_queue.put(STATUS.loading)
        load(get_next_track())
    elif t == 'long':
        led_thread_queue.put(STATUS.loading)
        load(get_next_folder())

def prev_button(channel):
    t = pressed_time(channel)
    if t == 'short':
        led_thread_queue.put(STATUS.loading)
        load(get_prev_track())
    elif t == 'long':
        led_thread_queue.put(STATUS.loading)
        load(get_prev_folder())

GPIO.add_event_detect(PREV_BUTTON_PIN, GPIO.BOTH, callback=prev_button, bouncetime=50)
GPIO.add_event_detect(PLAY_BUTTON_PIN, GPIO.FALLING, callback=play_pause_button, bouncetime=300)
GPIO.add_event_detect(NEXT_BUTTON_PIN, GPIO.BOTH, callback=next_button, bouncetime=50)

try:
    for line in iter(popen.stdout.readline, ""):
        if line == '@R MPG123\n':
            # saved previous
            load(*get_continue_from())
        elif line == '@P 3\n':
            # start next track when finished
            load(get_next_track())
        elif line.startswith('@F'):
            # store current frame and elapsed seconds
            state['current_frame'] = int(line.split()[1])
            state['current_sec'] = float(line.split()[3])
        elif line.startswith('@S') or line == '@P 2\n':
            led_thread_queue.put(STATUS.playing)

except KeyboardInterrupt:
    logger.info("KeyboardInterrupt")
except Exception as e:
    logger.error('%s' % e)
finally:
    logger.info("Terminating mpg321 process...")
    popen.terminate()
    logger.info("Closing threads...")
    led_thread_queue.put(None)
    logger.info("Cleaning up GPIO...")
    GPIO.cleanup()
    logger.info("Exiting program...")
    sys.exit()
