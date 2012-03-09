#!/bin/sh
exec startx /usr/bin/python3 runtilenol -- /usr/bin/Xephyr :20 +xinerama +extension RANDR -screen 800x300 -origin 0,300 -screen 800x300
