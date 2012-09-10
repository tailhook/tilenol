#!/bin/sh
exec startx /usr/bin/python3 runtilenol --log-stdout -- /usr/bin/Xephyr :20 +xinerama +extension RANDR -screen 800x500 -origin 0,500 -screen 800x500+0+500 -host-cursor
