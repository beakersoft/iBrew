#!/usr/bin/env python
from pyimagesearch.tempimage import TempImage
from azure.storage.blob import BlobService
from picamera.array import PiRGBArray
from picamera import PiCamera
import argparse
import warnings
import datetime
import imutils
import json
import time
import cv2

def LogMessage( str ):

	timestamp = datetime.datetime.now()			
	ts = timestamp.strftime("%A %d %B %Y %I:%M:%S%p")
	with open("/home/pi/iBrew/iBrew.log", "a") as text_file:
		text_file.write("\n[INFO]: " + ts + " " + str)
	return

# construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-c", "--conf", required=True,
	help="path to the JSON configuration file")
args = vars(ap.parse_args())
 
# filter warnings, load the configuration 
warnings.filterwarnings("ignore")
conf = json.load(open(args["conf"]))
client = None

#create our azure object
blob_service = BlobService(account_name=conf["blob_storage"], account_key=conf["blob_key"])

# initialize the camera and grab a reference to the raw camera capture
camera = PiCamera()
camera.resolution = tuple(conf["resolution"])
camera.framerate = conf["fps"]
rawCapture = PiRGBArray(camera, size=tuple(conf["resolution"]))
 
# allow the camera to warmup, then initialize the average frame, last
# uploaded timestamp, and frame motion counter
LogMessage("warming up...")
time.sleep(conf["camera_warmup_time"])
avg = None
lastUploaded = datetime.datetime.now()
motionCounter = 0

# capture frames from the camera
for f in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
        # grab the current frame and initialize the occupied/unoccupied  text
        frame = f.array
	timestamp = datetime.datetime.now()
        text = "Unoccupied"

        # resize the frame, convert it to grayscale, and blur it
        frameOrig = frame.copy()
        frame = imutils.resize(frame, width=500)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

	# if the average frame is None, initialize it
        if avg is None:
                LogMessage("starting background model...")
                avg = gray.copy().astype("float")
                continue

        # accumulate the weighted average between the current frame and
        # previous frames, then compute the difference between the current
        # frame and running average
        cv2.accumulateWeighted(gray, avg, 0.5)
        frameDelta = cv2.absdiff(gray, cv2.convertScaleAbs(avg))

        # threshold the delta image, dilate the thresholded image to fill
        # in holes, then find contours on thresholded image
        thresh = cv2.threshold(frameDelta, conf["delta_thresh"], 255,
                cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        (cnts, _) = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE)

        # loop over the contours
        for c in cnts:
                #if the contour is too small, ignore it
                if cv2.contourArea(c) < conf["min_area"]:
                        continue

                # compute the bounding box for the contour, draw it on the frame,
                # and update the text
                (x, y, w, h) = cv2.boundingRect(c)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                text = "Occupied"

        # draw the text and timestamp on the frame
        ts = timestamp.strftime("%A %d %B %Y %I:%M:%S%p")

        if text == "Occupied":
                # check to see if enough time has passed between uploads
                if (timestamp - lastUploaded).seconds >= conf["min_upload_seconds"]:
                        # increment the motion counter
                        motionCounter += 1

                        # check to see if the number of frames with consistent motion is high enough
                        if motionCounter >= conf["min_motion_frames"]:
				LogMessage("detected movement....")
				timestr = time.strftime("%Y%m%d-%H%M%S")
				t = TempImage()
				cv2.imwrite(t.path, frame)
				blob_service.put_blob('uploadimages', 'grab' + timestr + '.jpg', file(t.path).read(),'BlockBlob')
				LogMessage("uploaded file grab" + timestr + ".jpg to azure...")
				t.cleanup()

                                # update the last uploaded timestamp and reset the motion counter
                                lastUploaded = timestamp
                                motionCounter = 0

        # otherwise, the room is not occupied
        else:
                motionCounter = 0

	# if the `q` key is pressed, break from the lop
		if key == ord("q"):
			break

	rawCapture.truncate(0)
