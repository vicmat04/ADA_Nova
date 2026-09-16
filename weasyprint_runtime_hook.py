import os
import sys

if getattr(sys, 'frozen', False):
    # PyInstaller extracts to sys._MEIPASS
    os.environ['FONTCONFIG_PATH'] = os.path.join(sys._MEIPASS, 'etc', 'fonts')
    os.environ['FONTCONFIG_FILE'] = os.path.join(sys._MEIPASS, 'etc', 'fonts', 'fonts.conf')
