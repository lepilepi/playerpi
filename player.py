from time import sleep
import subprocess
import os
import RPi.GPIO as GPIO
from settings import MEDIA_PATH

import logging
logging.basicConfig(filename='player.log',level=logging.DEBUG)


GPIO.setmode(GPIO.BCM)

# GPIO 23 set up as input. It is pulled up to stop false signals  
GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(23, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(24, GPIO.IN, pull_up_down=GPIO.PUD_UP)


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
    # print state['current_sec'], state['current_track'].prev
    if state['current_sec'] <= 3 and state['current_track'].prev:
        return state['current_track'].prev
    else:
        return state['current_track']


popen = subprocess.Popen(['mpg321', '-g', '100', '-R', 'anyword'], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)

def load(track):
    state['current_track'] = track
    cmd = 'LOAD %s\n' % track.full_path
    # print(cmd)
    popen.stdin.write(cmd)

def play_pause_button(channel):
    popen.stdin.write('PAUSE\n')
    # TODO: SAVE

def prev_button(channel):
    load(get_prev_track())
    # TODO: SAVE

def next_button(channel):
    # print("next button pressed")
    load(get_next_track())
    # TODO: SAVE

GPIO.add_event_detect(22, GPIO.FALLING, callback=prev_button, bouncetime=300)
GPIO.add_event_detect(23, GPIO.FALLING, callback=play_pause_button, bouncetime=300)
GPIO.add_event_detect(24, GPIO.FALLING, callback=next_button, bouncetime=300)

# for line in iter(popen.stdout.readline, ""):
while True:
    line = popen.stdout.readline()
    logging.debug(line)
    if line == '@R MPG123\n':
        load(folders[0].tracks[0])
    elif line == '@P 3\n':
        pass
        # TODO: start next one
    elif line.startswith('@F'):
        state['current_frame'] = int(line.split()[1])
        state['current_sec'] = float(line.split()[3])
    


# p.stdin.write('LOAD mp3/rj/546aa00.mp3\n')
# sleep(2)
# p.stdin.write('PAUSE\n')
# sleep(2)
# p.stdin.write('PAUSE\n')
# sleep(2)
# p.stdin.write('STOP\n')
# sleep(2)


# p.kill()
