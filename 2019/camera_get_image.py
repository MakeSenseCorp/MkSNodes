import os
import urllib2
import urllib
import signal
#import cv2
import thread
import threading
import time
from subprocess import call

FRAMES_NUMBER 				= 60 * 60
IMAGES_FOLDER 				= "/home/ykiveish/mks/mksnodes/2017/video_fs/images/"
GET_REQUEST_INTERVAL_SEC 	= 1
GET_REQUEST_URL 			= "http://10.0.0.6/tmpfs/auto.jpg"

Running = True
VideoCounter = 1
def make_video():
	call(["bash", "make_video.sh", ""])
	return True

def GetRequest (url):
	username = 'admin'
	password = 'admin'

	p = urllib2.HTTPPasswordMgrWithDefaultRealm()
	p.add_password(None, url, username, password)

	handler = urllib2.HTTPBasicAuthHandler(p)
	opener = urllib2.build_opener(handler)
	urllib2.install_opener(opener)

	return urllib2.urlopen(url).read()


def signal_handler(signal, frame):
	global Running
	print "SIGNAL"
	Running = False

def main():
	signal.signal(signal.SIGINT, signal_handler)

	global Running
	while Running:
		framesCounter = 1
		print "# Start capturing frames."
		while (framesCounter != FRAMES_NUMBER):
			if False == Running:
				exit()
	
			data = GetRequest(GET_REQUEST_URL)
			file = open(IMAGES_FOLDER + str(framesCounter) + ".jpg", "w")
			file.write(data)
			file.close()
			framesCounter = framesCounter + 1
			time.sleep(GET_REQUEST_INTERVAL_SEC)
	
		make_video()
	print "Exit Node ..."

if __name__ == "__main__":
    main()
