from time import sleep, time
import subprocess
import threading
import os
import RPi.GPIO as GPIO
from settings import MEDIA_PATH, PREV_BUTTON_PIN, PLAY_BUTTON_PIN, NEXT_BUTTON_PIN

import logging
logging.basicConfig(filename='player.log',level=logging.DEBUG)


GPIO.setmode(GPIO.BCM)

# Set up button pins as input, pulled-up.
GPIO.setup(PREV_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(PLAY_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(NEXT_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)


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
    pass
    # TODO: display error message (espeak?)


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

def load(track):
    state['current_track'] = track
    cmd = 'LOAD %s\n' % track.full_path
    logging.info(cmd)
    popen.stdin.write(cmd)

def play_pause_button(channel):
    popen.stdin.write('PAUSE\n')
    # TODO: SAVE

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
        load(get_next_track())
    elif t == 'long':
        load(get_next_folder())
    # TODO: SAVE

def prev_button(channel):
    t = pressed_time(channel)
    if t == 'short':
        load(get_prev_track())
    elif t == 'long':
        load(get_prev_folder())
    # TODO: SAVE

GPIO.add_event_detect(PREV_BUTTON_PIN, GPIO.BOTH, callback=prev_button, bouncetime=50)
GPIO.add_event_detect(PLAY_BUTTON_PIN, GPIO.FALLING, callback=play_pause_button, bouncetime=300)
GPIO.add_event_detect(NEXT_BUTTON_PIN, GPIO.BOTH, callback=next_button, bouncetime=50)


for line in iter(popen.stdout.readline, ""):
    if line == '@R MPG123\n':
        # saved previous
        load(folders[0].tracks[0])
    elif line == '@P 3\n':
        # start next track when finished
        load(get_next_track())
    elif line.startswith('@F'):
        # store current frame and elapsed seconds
        state['current_frame'] = int(line.split()[1])
        state['current_sec'] = float(line.split()[3])
