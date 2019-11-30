""" This is the script that compiles and builds the Racing+ client. """

# Standard imports
import argparse
import sys
import json
import subprocess
import os
import re
import shutil
import hashlib

# Non-standard imports
import psutil
import paramiko
import dotenv
from PIL import Image, ImageFont, ImageDraw

# Configuration
REPOSITORY_NAME = 'isaac-racing-client'
MOD_DIR = 'C:\\Users\\james\\Documents\\My Games\\Binding of Isaac Afterbirth+ Mods\\racing+_dev'
TITLE_SCREEN_PATH = os.path.join(MOD_DIR, 'resources', 'gfx', 'ui', 'main menu')
REPOSITORY_DIR = os.path.join('C:\\Repositories\\', REPOSITORY_NAME)
os.chdir(REPOSITORY_DIR)

# This script is written for Pyhton 3
if sys.version_info < (3, 0):
    print('This script requires Python 3.')
    sys.exit(1)

# Subroutines
def error(message, exception=None):
    if exception is None:
        print(message)
    else:
        print(message, exception)
    sys.exit(1)

# From: https://gist.github.com/techtonik/5175896
def filehash(filepath):
    blocksize = 64 * 1024
    sha = hashlib.sha1()
    with open(filepath, 'rb') as file_pointer: #pylint: disable=W0621
        while True:
            data = file_pointer.read(blocksize)
            if not data:
                break
            sha.update(data)
    return sha.hexdigest()

# Get command-line arguments
PARSER = argparse.ArgumentParser()
PARSER.add_argument('-gh', '--github', help='upload to GitHub in addition to building locally', action='store_true')
PARSER.add_argument('-l', '--logo', help='only update the logo', action='store_true')
PARSER.add_argument('-s', '--skipmod', help='skip all mod related stuff', action='store_true')
PARSER.add_argument('-m', '--mod', help='only do mod related stuff', action='store_true')
ARGS = PARSER.parse_args()

# Load environment variables
dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Get the version
with open('package.json') as package_JSON:
    DATA = json.load(package_JSON)
NUMBER_VERSION = DATA['version']
VERSION = 'v' + DATA['version']

if not ARGS.skipmod:
    # Search for debug print statements
    output = ''
    try:
        output = subprocess.check_output(['grep', '-rni', 'getting here', MOD_DIR]).strip()
    except subprocess.CalledProcessError:
        # We except a return value of 1 since it should not find any results
        pass
    if output != '':
        print('Found leftover debug statements.')
        sys.exit(1)

    # Put the version in the "Globals.lua" file
    # http://stackoverflow.com/questions/17140886/how-to-search-and-replace-text-in-a-file-using-python
    LUA_FILE = os.path.join(MOD_DIR, 'racing_plus', 'Globals.lua')
    with open(LUA_FILE, 'r') as file_handle:
        FILE_DATA = file_handle.read()

    # Replace the target string
    NEW_FILE = ''
    for line in iter(FILE_DATA.splitlines()):
        match = re.search(r'g.version = ', line)
        if match:
            NEW_FILE += 'g.version = "' + VERSION + '"\n'
        else:
            NEW_FILE += line + '\n'

    # Also ensure that the debug flag is turned to false
    if ARGS.github:
        NEW_FILE2 = ''
        for line in iter(NEW_FILE.splitlines()):
            match = re.search(r'g.debug = true', line)
            if match:
                NEW_FILE2 += 'g.debug = false\n'
            else:
                NEW_FILE2 += line + '\n'
        NEW_FILE = NEW_FILE2

    # Write the file out again
    with open(LUA_FILE, 'w', newline='\n') as file:
        file.write(NEW_FILE)

    # Draw the version number on the title menu graphic
    LARGE_FONT = ImageFont.truetype(os.path.join('src', 'fonts', 'Jelly Crazies.ttf'), 9)
    SMALL_FONT = ImageFont.truetype(os.path.join('src', 'fonts', 'Jelly Crazies.ttf'), 6)
    URL_FONT = ImageFont.truetype(os.path.join('src', 'fonts', 'Vera.ttf'), 11)
    TITLE_IMG = Image.open(os.path.join(TITLE_SCREEN_PATH, 'titlemenu-orig.png'))
    TITLE_DRAW = ImageDraw.Draw(TITLE_IMG)
    WIDTH, HEIGHT = TITLE_DRAW.textsize(VERSION, font=LARGE_FONT)
    COLOR = (67, 93, 145)
    TITLE_DRAW.text((420 - WIDTH / 2, 236), 'V', COLOR, font=SMALL_FONT)
    TITLE_DRAW.text((430 - WIDTH / 2, 230), NUMBER_VERSION, COLOR, font=LARGE_FONT)

    # Draw the URL on the title menu graphic
    URL = 'isaacracing.net'
    WIDTH, HEIGHT = TITLE_DRAW.textsize(URL, font=URL_FONT)
    TITLE_DRAW.text((420 - WIDTH / 2, 250), URL, COLOR, font=URL_FONT)

    TITLE_IMG.save(os.path.join(TITLE_SCREEN_PATH, 'titlemenu.png'))
    print('Title screen image updated.')

    # We are done if all we need to do is update the title screen
    if ARGS.logo:
        sys.exit()

    # Check to see if we had any floor STBs in testing mode
    ROOMS_DIR = os.path.join(MOD_DIR, 'resources', 'rooms')
    for file_name in os.listdir(ROOMS_DIR):
        if file_name.endswith('2.stb'):
            match = re.search(r'(.+)2\.stb$', file_name)
            new_file_name = match.group(1) + '.stb'
            os.rename(os.path.join(ROOMS_DIR, file_name), os.path.join(ROOMS_DIR, new_file_name))

    # Delete the "disable.it" file, if present
    DISABLE_IT_PATH = os.path.join(MOD_DIR, 'disable.it')
    try:
        if os.path.exists(DISABLE_IT_PATH):
            os.remove(DISABLE_IT_PATH)
    except Exception as err:
        error('Failed to remove the "' + DISABLE_IT_PATH + '" file:', err)

    # Delete any XML files in the rooms subdirectory, if present
    for file_name in os.listdir(ROOMS_DIR):
        if file_name.endswith('.xml'):
            os.remove(os.path.join(ROOMS_DIR, file_name))
    ROOMS_DIR2 = os.path.join(ROOMS_DIR, 'pre-flipping')
    for file_name in os.listdir(ROOMS_DIR2):
        if file_name.endswith('.xml'):
            os.remove(os.path.join(ROOMS_DIR2, file_name))

    # Get the SHA1 hash of every file in the mod directory
    # From: https://gist.github.com/techtonik/5175896
    HASHES = {}
    for root, subdirs, files in os.walk(MOD_DIR):
        for fpath in [os.path.join(root, f) for f in files]:
            # We don't care about certain files
            name = os.path.relpath(fpath, root)
            if (name == 'metadata.xml' or # This file will be one version number ahead of the one distributed through steam
                    name == 'save1.dat' or # These are the IPC files, so it doesn't matter if they are different
                    name == 'save2.dat' or
                    name == 'save3.dat'):

                continue

            choppedPath = fpath[80:] # Chop off the "C:\\Users\\james\\Documents\\My Games\\Binding of Isaac Afterbirth+ Mods\\racing+_dev\\" prefix
            HASHES[choppedPath] = filehash(fpath)

    # Write the dictionary to a JSON file
    SHA1_FILE_PATH = os.path.join(MOD_DIR, 'sha1.json')
    # By default, the file will be created with "\r\n" end-of-line-separators
    with open(SHA1_FILE_PATH, 'w', newline='\n') as file_pointer:
        # By default, the JSON will be all combined into a single line, so we specify the indent to make it pretty
        # By default, the JSON will be dumped in a random order, so we use "sort_keys" to make it alphabetical
        json.dump(HASHES, file_pointer, indent=4, sort_keys=True)

    # Copy the mod
    MOD_DIR2 = os.path.join(REPOSITORY_DIR, 'mod')
    if os.path.exists(MOD_DIR2):
        try:
            subprocess.call(['rm', '-rf', MOD_DIR2]) # Works on Windows if "GnuWinCoreutils-5.3.0.exe" is installed
        except Exception as err:
            error('Failed to remove the "' + MOD_DIR2 + '" directory:', err)
    try:
        shutil.copytree(MOD_DIR, MOD_DIR2)
    except Exception as err:
        error('Failed to copy the "' + MOD_DIR + '" directory:', err)
    print('Copied the mod.')

    # Delete the 3 "save.dat" files, since if they are included, it will overwrite the existing user's settings
    for i in range(1, 4): # This will go from 1 to 3
        save_dat = os.path.join(MOD_DIR2, 'save' + str(i) + '.dat')
        os.remove(save_dat)

# Exit if we are only supposed to be doing work on the mod
if ARGS.mod:
    sys.exit(0)

if ARGS.github:
    # Make sure that the localhost version of the client is not activated
    # http://stackoverflow.com/questions/17140886/how-to-search-and-replace-text-in-a-file-using-python
    GLOBALS_FILE = os.path.join('src', 'js', 'globals.js')
    with open(GLOBALS_FILE, 'r') as file_handle:
        FILE_DATA = file_handle.read()
    NEW_FILE = ''
    for line in iter(FILE_DATA.splitlines()):
        match = re.search(r'const localhost = true;(.*)', line)
        if match:
            NEW_FILE += 'const localhost = false;' + match.group(1) + '\n'
        else:
            NEW_FILE += line + '\n'
    with open(GLOBALS_FILE, 'w', newline='\n') as file:
        file.write(NEW_FILE)

    # Commit to the client repository
    RETURN_CODE = subprocess.call(['git', 'add', '-A'])
    if RETURN_CODE != 0:
        error('Failed to git add.')
    RETURN_CODE = subprocess.call(['git', 'commit', '-m', VERSION])
    if RETURN_CODE != 0:
        error('Failed to git commit.')
    RETURN_CODE = subprocess.call(['git', 'pull', '--rebase'])
    if RETURN_CODE != 0:
        error('Failed to git pull.')
    RETURN_CODE = subprocess.call(['git', 'push'])
    if RETURN_CODE != 0:
        error('Failed to git push.')

    # Open the mod updater tool from Nicalis
    if not ARGS.skipmod:
        UPLOADER_PATH = 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\The Binding of Isaac Rebirth\\tools\\ModUploader\\ModUploader.exe'
        subprocess.Popen([UPLOADER_PATH], cwd=MOD_DIR2) # Popen will run it in the background

# Close the program if it is running
# (having it open can cause corrupted ASAR archives)
for process in psutil.process_iter():
    if process.name() == 'electron.exe':
        process.kill()

# Build/package
print('Building:', REPOSITORY_NAME, VERSION)
if ARGS.github:
    RUN_COMMAND = 'distPub'
else:
    RUN_COMMAND = 'dist'
RETURN_CODE = subprocess.call([
    'npm',
    'run',
    RUN_COMMAND,
    '--python="C:/Python27/python.exe"'
], shell=True)
if RETURN_CODE != 0:
    error('Failed to build.')

# Set the latest client version number on the server
if ARGS.github:
    LATEST_CLIENT_VERSION_FILE = 'latest_client_version.txt'
    with open(LATEST_CLIENT_VERSION_FILE, 'w') as version_file:
        print(VERSION, file=version_file)

    TRANSPORT = paramiko.Transport((os.environ.get('VPS_IP'), 22))
    TRANSPORT.connect(None, os.environ.get('VPS_USER'), os.environ.get('VPS_PASS'))
    SFTP = paramiko.SFTPClient.from_transport(TRANSPORT)
    REMOTE_PATH = 'go/src/github.com/Zamiell/isaac-racing-server/' + LATEST_CLIENT_VERSION_FILE
    SFTP.put(LATEST_CLIENT_VERSION_FILE, REMOTE_PATH)
    TRANSPORT.close()
    os.remove(LATEST_CLIENT_VERSION_FILE)

# Done
print('Released version', NUMBER_VERSION, 'successfully.')
