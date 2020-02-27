#!/usr/bin/python
import os
import sys
import gc
import signal
import json
import time
import thread
import threading
import logging
logging.basicConfig(
	filename='app.log',
	level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

import subprocess
import urllib2
import urllib
import re
from subprocess import call
from subprocess import Popen, PIPE
import Queue

import numpy as np
from PIL import Image
from PIL import ImageFilter
from io import BytesIO

import base64

from mksdk import MkSFile
from mksdk import MkSSlaveNode
from mksdk import MkSLocalHWConnector
from mksdk import MkSUSBAdaptor
from mksdk import MkSProtocol

from flask import Response, request
from flask import send_file
import v4l2
import fcntl
import mmap

class VideoCreator():
	def __init__(self):
		self.ObjName 	= "VideoCreator"
		self.Orders 	= Queue.Queue()
		self.IsRunning	= True
		self.FPS		= 8
		thread.start_new_thread(self.OrdersManagerThread, ())
	
	def SetFPS(self, fps):
		self.FPS = fps

	def AddOrder(self, order):
		self.Orders.put(order)
		self.IsRunning = True

	def OrdersManagerThread(self):
		# TODO - Put in TRY CATCH
		while (self.IsRunning is True):
			item = self.Orders.get(block=True,timeout=None)
			try:
				logging.info("[VideoCreator] Start video encoding...")
				images = item["images"]
				file_path = "{0}/video_{1}.avi".format(item["path"], str(time.time()))
				print("[VideoCreator] Start recording, " + file_path)
				recordingProcess = Popen(['ffmpeg', '-y', '-f', 'image2pipe', '-vcodec', 'mjpeg', '-r', str(self.FPS), '-i', '-', '-vcodec', 'mpeg4', '-qscale', '5', '-r', str(self.FPS), file_path], stdin=PIPE)
				for frame in images:
					image = Image.open(BytesIO(frame))
					image.save(recordingProcess.stdin, 'JPEG')
				recordingProcess.stdin.close()
				recordingProcess.wait()
				logging.debug("[VideoCreator] {images} {item}".format(images = str(id(images)), item = str(id(item))))
				images = []
				item = None
				logging.info("[VideoCreator] Start video encoding... DONE")
				gc.collect()
			except Exception as e:
				print ("[VideoCreator] Exception", e)

GEncoder = VideoCreator()

class MkSImageProcessing(): # TODO - Change name MkSImageComperator
	def __init__(self):
		self.ObjName 	= "ImageProcessing"
		self.HighDiff	= 5000 # MAX = 261120
	
	def SetHighDiff(self, value):
		self.HighDiff = value

	def CompareJpegImages(self, img_one, img_two):
		if (img_one is None or img_two is None):
			return 0
		
		try:
			emboss_img_one = Image.open(BytesIO(img_one)).filter(ImageFilter.EMBOSS)
			emboss_img_two = Image.open(BytesIO(img_two)).filter(ImageFilter.EMBOSS)

			im = [None, None] 								# to hold two arrays
			for i, f in enumerate([emboss_img_one, emboss_img_two]):
				# .filter(ImageFilter.GaussianBlur(radius=2))) # blur using PIL
				im[i] = (np.array(f
				.convert('L')            					# convert to grayscale using PIL
				.resize((32,32), resample=Image.BICUBIC)) 	# reduce size and smooth a bit using PIL
				).astype(np.int)   							# convert from unsigned bytes to signed int using numpy
			diff_precentage = (float(self.HighDiff - (np.abs(im[0] - im[1]).sum())) / self.HighDiff) * 100
			
			if (diff_precentage < 0):
				return 0
			
			return diff_precentage
		except Exception as e:
			print ("[MkSImageProcessing] Exception", e)
			return 0

class UVCCamera():
	def __init__(self, path):
		self.ClassName 					= "UVCCamera"
		self.ImP						= MkSImageProcessing()
		self.Name 						= ""
		self.IsGetFrame 				= False
		self.IsRecoding 				= False
		self.IsCameraWorking 			= False
		self.IsSecurity					= False
		self.FramesPerVideo 			= 2000
		self.SecondsPerFrame			= 0.4
		self.RecordingSensetivity 		= 95
		self.SecuritySensitivity 		= 92
		self.CurrentImageIndex 			= 0
		self.OnImageDifferentCallback	= None
		self.State 						= 0
		self.FrameCount  				= 0
		self.FPS 						= 0.0
		self.RecordingPath 				= ""
		# Events
		self.StopRecordingEvent 		= None
		# Synchronization
		self.WorkingStatusLock 			= threading.Lock()

		self.Device 					= None
		self.DevicePath 				= path
		self.Memory 					= None
		self.CameraDriverValid 			= True
		self.Buffer 					= None
		self.CameraDriverName 			= ""
		self.UID 						= self.CameraDriverName

		self.InitCameraDriver()
	
	def SetSecuritySensetivity(self, value):
		self.SecuritySensitivity = value

	def SetRecordingPath(self, path):
		self.RecordingPath = path

	def SetFramesPerVideo(self, value):
		self.FramesPerVideo = value

	def SetRecordingSensetivity(self, value):
		self.RecordingSensetivity = value
	
	def SetHighDiff(self, value):
		self.ImP.SetHighDiff(value)
	
	def SetSecondsPerFrame(self, value):
		self.SecondsPerFrame = value

	def GetCapturingProcess(self):
		return int((float(self.CurrentImageIndex) / float(self.FramesPerVideo)) * 100.0)
	
	def GetFPS(self):
		return self.FPS
	
	def InitCameraDriver(self):
		self.Device = os.open(self.DevicePath, os.O_RDWR | os.O_NONBLOCK, 0)

		if self.Device is None:
			self.CameraDriverValid = False
			return
		
		capabilities = v4l2.v4l2_capability()
		fcntl.ioctl(self.Device, v4l2.VIDIOC_QUERYCAP, capabilities)

		if capabilities.capabilities & v4l2.V4L2_CAP_VIDEO_CAPTURE == 0:
			self.CameraDriverValid = False
			return
		# Set camera name
		self.CameraDriverName = capabilities.card.replace(" ", "")

		# Setup video format (V4L2_PIX_FMT_MJPEG)
		capture_format 						= v4l2.v4l2_format()
		capture_format.type 				= v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
		capture_format.fmt.pix.pixelformat 	= v4l2.V4L2_PIX_FMT_MJPEG
		capture_format.fmt.pix.width  		= 640
		capture_format.fmt.pix.height 		= 480
		fcntl.ioctl(self.Device, v4l2.VIDIOC_S_FMT, capture_format)

		# Tell the driver that we want some buffers
		req_buffer         = v4l2.v4l2_requestbuffers()
		req_buffer.type    = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
		req_buffer.memory  = v4l2.V4L2_MEMORY_MMAP
		req_buffer.count   = 1
		fcntl.ioctl(self.Device, v4l2.VIDIOC_REQBUFS, req_buffer)

		# Map driver to buffer
		self.Buffer         	= v4l2.v4l2_buffer()
		self.Buffer.type    	= v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
		self.Buffer.memory  	= v4l2.V4L2_MEMORY_MMAP
		self.Buffer.index   	= 0
		fcntl.ioctl(self.Device, v4l2.VIDIOC_QUERYBUF, self.Buffer)
		self.Memory 		= mmap.mmap(self.Device, self.Buffer.length, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=self.Buffer.m.offset)
		# Queue the buffer for capture
		fcntl.ioctl(self.Device, v4l2.VIDIOC_QBUF, self.Buffer)

		# Start streaming
		self.BufferType = v4l2.v4l2_buf_type(v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE)
		fcntl.ioctl(self.Device, v4l2.VIDIOC_STREAMON, self.BufferType)
		time.sleep(5)

	def Frame(self):
		# Allocate new buffer
		self.Buffer 		= v4l2.v4l2_buffer()
		self.Buffer.type 	= v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
		self.Buffer.memory 	= v4l2.V4L2_MEMORY_MMAP
		frame_garbed 	= False
		retry_counter	= 0
		while frame_garbed is False and retry_counter < 5:
			# Needed for virtual FPS and UVC driver
			time.sleep(self.SecondsPerFrame)
			# Get image from the driver queue
			try:
				fcntl.ioctl(self.Device, v4l2.VIDIOC_DQBUF, self.Buffer)
				frame_garbed = True
			except Exception as e:
				retry_counter += 1
				print ("({classname})# [ERROR] UVC driver cannot dqueue frame ... ({0})".format(retry_counter, classname=self.ClassName))
		
		if frame_garbed is False:
			return None, True
		
		# Read frame from memory maped object
		raw_frame 		= self.Memory.read(self.Buffer.length)
		img_raw_Frame 	= Image.open(BytesIO(raw_frame))
		output 			= BytesIO()
		img_raw_Frame.save(output, "JPEG", quality=15, optimize=True, progressive=True)
		frame 			= output.getvalue()

		self.Memory.seek(0)
		# Requeue the buffer
		fcntl.ioctl(self.Device, v4l2.VIDIOC_QBUF, self.Buffer)
		self.FrameCount +=  1

		return frame, False
	
	def SetState(self, state):
		self.State = state
	
	def GetState(self):
		return self.State

	def StartSecurity(self):
		self.IsSecurity = True
		self.IsGetFrame = True

	def StopSecurity(self):
		self.IsSecurity = False
	
	def StartGettingFrames(self):
		self.IsGetFrame = True

	def StopGettingFrames(self):
		self.IsGetFrame = False
	
	def StartRecording(self):
		self.IsRecoding = True
		self.IsGetFrame = True

	def StopRecording(self):
		self.IsRecoding = False

	def StartCamera(self):
		self.WorkingStatusLock.acquire()
		if (self.IsCameraWorking is False):
			thread.start_new_thread(self.CameraThread, ())
		self.WorkingStatusLock.release()

	def StopCamera(self):
		self.WorkingStatusLock.acquire()
		print ("[Camera] Stop recording {0}".format(self.Device))
		if self.CameraDriverValid is True:
			fcntl.ioctl(self.Device, v4l2.VIDIOC_STREAMOFF, self.BufferType)
		self.IsCameraWorking = False
		self.WorkingStatusLock.release()

	def CameraThread(self):
		global GEncoder
		
		# TODO - Is video creation is on going?
		# TODO - Each camera must have its own video folder.
		# TODO - Enable/Disable camera - self.IsGetFrame(T/F)
		# TODO - Stop recording will not kill this thread

		frame_cur 			 = None
		frame_pre 			 = None
		frame_dif 	 		 = 0
		rec_buffer 			 = [[],[]]
		rec_buffer_idx 		 = 0
		ts 					 = time.time()

		self.IsCameraWorking = True
		self.IsGetFrame 	 = True
		
		self.WorkingStatusLock.acquire()
		while self.IsCameraWorking is True:
			self.WorkingStatusLock.release()
			if self.IsGetFrame is True:
				frame_cur, error = self.Frame()
				if (error is False):
					frame_dif = self.ImP.CompareJpegImages(frame_cur, frame_pre)
					frame_pre = frame_cur

					self.FPS = 1.0 / float(time.time()-ts)
					print("[FRAME] ({0}) ({1}) ({dev}) (diff={diff}) (sensitivity={sensy}) (fps={fps})".format(	str(self.FrameCount),
																						str(len(frame_cur)),
																						diff=str(frame_dif),
																						fps=str(self.FPS),
																						sensy=str(self.SecuritySensitivity),
																						dev=str(self.Device)))
					ts = time.time()
					if (frame_dif < self.SecuritySensitivity):
						THIS.Node.EmitOnNodeChange({
									'dev': self.DevicePath.split('/')[-1],
									'event': "new_frame", 
									'frame': base64.encodestring(frame_cur)
						})

					if self.IsSecurity is True:
						if (frame_dif < self.SecuritySensitivity):
							print("[Camera] Security {diff} {sensitivity}".format(diff = str(frame_dif), sensitivity = str(self.SecuritySensitivity)))
							if self.OnImageDifferentCallback is not None:
								self.OnImageDifferentCallback(self.Device, frame_cur)
				
					if self.IsRecoding is True:
						# Check for valid storage
						if not os.path.exists(self.RecordingPath):
							if self.StopRecordingEvent is not None:
								self.StopRecordingEvent({
									'path': self.RecordingPath,
									'ip': "",
									'dev': self.Device,
									'mac': "",
									'uid': self.UID
								})
							self.IsRecoding = False
						else:
							if (frame_dif < self.RecordingSensetivity):
								rec_buffer[rec_buffer_idx].append(frame_cur)
								print("[Camera] Recording {frames} {diff} {sensitivity}".format(frames = str(len(rec_buffer[rec_buffer_idx])), diff = str(frame_dif), sensitivity = str(self.RecordingSensetivity)))
								self.CurrentImageIndex = len(rec_buffer[rec_buffer_idx])
							
							if self.FramesPerVideo <= self.CurrentImageIndex:
								path = "{0}/{1}/video".format(self.RecordingPath, self.UID)
								try:
									if not os.path.exists(path):
										os.makedirs(path)
									GEncoder.AddOrder({
										'images': rec_buffer[rec_buffer_idx],
										'path': path
									})
									logging.debug("Sent recording order " + str(id(rec_buffer[rec_buffer_idx])))
								except Exception as e:
									print ("[Camera] Exception", e)

								if 1 == rec_buffer_idx:
									rec_buffer_idx = 0
								else:
									rec_buffer_idx = 1
								
								rec_buffer[rec_buffer_idx] = []
								self.CurrentImageIndex = len(rec_buffer[rec_buffer_idx])
								gc.collect()
				else:
					print ("({classname})# ERROR - Cannot fetch frame ...".format(classname=self.ClassName))
			else:
				time.sleep(1)
			self.WorkingStatusLock.acquire()
		print ("({classname})# Exit RECORDING THREAD ...".format(classname=self.ClassName))

class Context():
	def __init__(self, node):
		self.ClassName					= "Apllication"
		self.Interval					= 10
		self.CurrentTimestamp 			= time.time()
		self.File 						= MkSFile.File()
		self.Node						= node
		# States
		self.States = {
		}
		# Handlers
		self.RequestHandlers		= {
			'get_frame':				self.GetFrameHandler,
			'get_sensor_info':			self.GetSensorInfoHandler,
			'start_recording': 			self.StartRecordingHandler,
			'stop_recording': 			self.StopRecordingHandler,
			'start_motion_detection': 	self.StartMotionDetectionHandler,
			'stop_motion_detection': 	self.StopMotionDetectionHandler,
			'start_security': 			self.StartSecurityHandler,
			'stop_security': 			self.StopSecurityHandler,
			'set_camera_name': 			self.SetCameraNameHandler,
			'get_changed_misc_info':	self.GetChangedMiscInfoHandler,
			'set_face_detection':		self.SetFaceDetectionHandler,
			'set_camera_sensetivity':	self.SetCameraSensetivityHandler,
			'get_videos_list':			self.GetVideosListHandler,
			'get_misc_information':		self.GetMiscInformationHandler,
			'set_misc_information':		self.SetMiscInformationHandler,
			'undefined':				self.UndefindHandler
		}
		self.ResponseHandlers		= {
			'undefined':				self.UndefindHandler
		}
		# Application variables
		self.DB							= None
		self.Cameras 					= []
		self.ObjCameras					= []
		self.DeviceScanner 				= None
		self.UVCScanner 				= None
		self.SecurityEnabled 			= False
		self.SMSService					= ""
		self.EmailService				= ""

		self.LastTSEmailSent			= 0
		self.HJTDetectorTimestamp 		= time.time()
		self.LocalStorageEnabled 		= 0
		self.USBDevices 				= []
		self.USBDevice 					= None
		self.LocalStoragePath 			= "/home/ykiveish/mks/nodes/2019/videos/local"
		self.USBStoragePath 			= "/home/ykiveish/mks/nodes/2019/videos/usb"

	def UndefindHandler(self, sock, packet):
		print ("UndefindHandler")

	def GetSensorInfoHandler(self, sock, packet):
		print ("({classname})# GetSensorInfoHandler ...".format(classname=self.ClassName))
		payload = {
			'db': self.DB,
			'device': {
				'ip': THIS.Node.MyLocalIP,
				'webport': THIS.Node.LocalWebPort
			}
		}

		return THIS.Node.BasicProtocol.BuildResponse(packet, payload)
	
	def GetFrameHandler(self, sock, packet):
		print ("({classname})# GetFrameHandler ...".format(classname=self.ClassName))
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		# Find camera
		for item in self.ObjCameras:
			if (item.CameraDriverName in payload["uid"]):
				frame, error = item.Frame()
				if error is False:
					return THIS.Node.BasicProtocol.BuildResponse(packet, {
									'uid': item.CameraDriverName,
									'dev': item.DevicePath.split('/')[-1],
									'frame': base64.encodestring(frame)
					})

		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'return_code': 'no_frame'
		})

	def StartRecordingHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		# Find camera
		for item in self.ObjCameras:
			if (item.GetIp() in payload["ip"]):
				# TODO - Each camera must have its own directory
				item.StartRecording()
				cameras = self.DB["cameras"]
				for item in cameras:
					if (item["ip"] in payload["ip"]):
						item["recording"] = 1
						self.File.Save("db.json", json.dumps(self.DB))

		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'return_code': 'STARTED'
		})

	def StopRecordingHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		# Find camera
		for item in self.ObjCameras:
			if (item.GetIp() in payload["ip"]):
				# TODO - Each camera must have its own directory
				item.StopRecording()
				cameras = self.DB["cameras"]
				for item in cameras:
					if (item["ip"] in payload["ip"]):
						item["recording"] = 0
						self.File.Save("db.json", json.dumps(self.DB))
		
		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'return_code': 'STOPPED'
		})

	def StartMotionDetectionHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		cameras = self.DB["cameras"]
		for item in cameras:
			if (item["ip"] in payload["ip"]):
				item["motion_detection"] = 1
				self.File.Save("db.json", json.dumps(self.DB))
		
		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'return_code': 'STARTED'
		})

	def StopMotionDetectionHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		cameras = self.DB["cameras"]
		for item in cameras:
			if (item["ip"] in payload["ip"]):
				item["motion_detection"] = 0
				self.File.Save("db.json", json.dumps(self.DB))

		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'return_code': 'STOPPED'
		})

	def StartSecurityHandler(self, sock, packet):
		self.DB["security"] = 1
		self.SecurityEnabled = True
		cameras = self.DB["cameras"]
		ips = []
		for item in cameras:
			item["security"]  		 = 1
			item["motion_detection"] = 1
			ips.append(item["ip"])
		self.DB["cameras"] = cameras
		for item in self.ObjCameras:
			item.StartSecurity()
		self.File.Save("db.json", json.dumps(self.DB))

		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'return_code': 'STARTED',
			'ips': ips
		})

	def StopSecurityHandler(self, sock, packet):
		self.DB["security"] = 0
		self.SecurityEnabled = False
		cameras = self.DB["cameras"]
		ips = []
		for item in cameras:
			item["security"]  		 = 0
			item["motion_detection"] = 0
			ips.append(item["ip"])
		for item in self.ObjCameras:
			item.StopSecurity()
		self.DB["cameras"] = cameras
		self.File.Save("db.json", json.dumps(self.DB))

		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'return_code': 'STOPPED',
			'ips': ips
		})

	def SetCameraNameHandler(self, sock, packet):
		print("SetCameraNameHandler")
	
	def GetChangedMiscInfoHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		# Find camera
		camera = None
		for item in self.ObjCameras:
			if (payload["dev"] in item.DevicePath):
				camera = item
				break
		
		if camera is not None:
			process = camera.GetCapturingProcess()
			fps 	= camera.GetFPS()
			print({
				'progress': str(process),
				'fps': str(fps),
				'usb_device': self.USBDevice,
				'usb_devices': self.USBDevices,
				'local_storage_enabled': self.LocalStorageEnabled
			})
			return THIS.Node.BasicProtocol.BuildResponse(packet, {
				'progress': str(process),
				'fps': str(fps),
				'usb_device': self.USBDevice,
				'usb_devices': self.USBDevices,
				'local_storage_enabled': self.LocalStorageEnabled
			})
		
		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'error': 'error'
		})

	def SetFaceDetectionHandler(self, sock, packet):
		print("SetFaceDetectionHandler")

	def SetCameraSensetivityHandler(self, sock, packet):
		print("SetCameraSensetivityHandler")
	
	def GetVideosListHandler(self, sock, packet):
		print("GetVideosListHandler")
	
	def GetMiscInformationHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		dbCameras = self.DB["cameras"]
		for itemCamera in dbCameras:
			if itemCamera["dev"] in payload["dev"]:
				if self.LocalStorageEnabled:
					videosList = os.listdir("{0}/{1}/video".format(self.LocalStoragePath,itemCamera["uid"]))
				else:
					videosList = os.listdir("{0}/{1}/{2}/video".format(self.USBStoragePath,self.USBDevice["name"],itemCamera["uid"]))
				return THIS.Node.BasicProtocol.BuildResponse(packet, {
					'name': itemCamera["name"],
					'email': itemCamera["email"],
					'phone': itemCamera["phone"],
					'frame_per_video': str(itemCamera["frame_per_video"]),
					'seconds_per_frame': itemCamera["seconds_per_frame"],
					'camera_sensetivity_recording': str(itemCamera["camera_sensetivity_recording"]),
					'camera_sensetivity_security': str(itemCamera["camera_sensetivity_security"]),
					'high_diff': itemCamera["high_diff"],
					'face_detect': str(itemCamera["face_detect"]),
					'video_list': videosList,
					'access_from_www': str(itemCamera["access_from_www"]),
					'motion_detection': str(itemCamera["motion_detection"]),
					'recording': str(itemCamera["recording"]),
					'usb_device_name': self.USBDevice["name"],
					'usb_devices': self.USBDevices,
					'local_storage_enabled': self.LocalStorageEnabled
				})
		
		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'error': 'bad camera'
		})

	def SetMiscInformationHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		dbCameras = self.DB["cameras"]
		self.DB["local_storage"] 							= payload["local_storage_enabled"]
		self.DB["usb_device"]["name"]						= payload["usb_device_name"]
		self.USBDevice 										= self.DB["usb_device"]
		self.LocalStorageEnabled 							= self.DB["local_storage"]

		if self.USBDevice["name"] == "":
			self.DB["usb_device"]["enabled"] = 0
		else:
			self.DB["usb_device"]["enabled"] = 1

		for itemCamera in dbCameras:
			if itemCamera["dev"] in payload["dev"]:
				itemCamera["frame_per_video"] 				= payload["frame_per_video"]
				itemCamera["camera_sensetivity_recording"] 	= payload["camera_sensetivity_recording"]
				itemCamera["face_detect"] 					= payload["face_detect"]
				itemCamera["high_diff"] 					= payload["high_diff"]
				itemCamera["name"] 							= payload["name"]
				itemCamera["seconds_per_frame"] 			= payload["seconds_per_frame"]
				itemCamera["phone"] 						= payload["phone"]
				itemCamera["email"] 						= payload["email"]
				itemCamera["access_from_www"] 				= payload["access_from_www"]
				itemCamera["motion_detection"] 				= payload["motion_detection"]
				itemCamera["recording"] 					= payload["recording"]
				itemCamera["camera_sensetivity_security"] 	= payload["camera_sensetivity_security"]

				self.DB["cameras"] = dbCameras
				# Save new camera to database
				self.File.Save("db.json", json.dumps(self.DB))

				for item in self.ObjCameras:
					if (payload["dev"] in item.DevicePath):
						item.SetFramesPerVideo(int(itemCamera["frame_per_video"]))
						item.SetRecordingSensetivity(int(itemCamera["camera_sensetivity_recording"]))
						item.SetSecuritySensetivity(int(itemCamera["camera_sensetivity_security"]))
						item.SetHighDiff(int(itemCamera["high_diff"]))
						item.SetSecondsPerFrame(float(itemCamera["seconds_per_frame"]))

						# Update camera recording status
						if (1 == itemCamera["recording"]):
							item.StartRecording()
						else:
							item.StopRecording()

						# TODO - Update cmaera motion detection staus

						# Update storage path
						if (self.LocalStorageEnabled == 1):
							item.SetRecordingPath(self.LocalStoragePath)
						else:
							# Get USB device
							self.USBDevice = self.DB["usb_device"]
							item.SetRecordingPath("{0}/{1}".format(self.USBStoragePath,self.USBDevice["name"]))

				return THIS.Node.BasicProtocol.BuildResponse(packet, {
					'error': 'success'
				})
		
		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'error': 'bad camera'
		})
	
	# Sending SMS via RESTApi of SMS service Node
	def SendSMSRequest(self):
		try:
			payload = json.dumps({	
							'request': 'task_order',
							'json': {
								'number': '0547884156',
								'message': 'hello' 
							}
						})
			url = "http://{ip}:{port}/set/add_request/{user_id}".format(
				ip 	 	= str(THIS.Node.LocalServiceNode.MyLocalIP), 
				port 	= str(8032), 
				user_id	= str(self.Node.Key))
			data = urllib2.urlopen(url, payload).read()
			print (data)
		except Exception as e:
			print ("HTTPException on requesting SMS service", e)
	
	def OnCameraDiffrentHandler(self, ip, image):
		print("OnCameraDiffrentHandler")
	
	def OnMasterAppendNodeHandler(self, uuid, type, ip, port):
		print ("[OnMasterAppendNodeHandler]", str(uuid), str(type), str(ip), str(port))
	
	def OnMasterRemoveNodeHandler(self, uuid, type, ip, port):
		print ("[OnMasterRemoveNodeHandler]", str(uuid), str(type), str(ip), str(port))

	def OnGetNodeInfoHandler(self, info, online):
		print ("({classname})# Node Info Recieved ...\n\t{0}\t{1}\t{2}\t{3}".format(online, info["uuid"],info["name"],info["type"],classname=self.ClassName))

	def SerachForCameras(self):
		devices = ["/dev/video0"]
		return devices
	
	def UpdateCameraStracture(self, dbCameras, dev_path):
		cameradb 	= None
		camera 		= UVCCamera(dev_path)
		uid 		= camera.CameraDriverName
		cameraFound = False

		# Update camera IP (if it was changed)
		for itemCamera in dbCameras:
			# Invalid MAC or UID (TODO - Do re.compile for MAC)
			if uid == "":
				print ("({classname})# Found path is not valid camera".format(classname=self.ClassName))
				return
			else:
				# Is camera exist in DB
				if uid in itemCamera["uid"]:
					cameraFound = True
					cameradb 	= itemCamera
					break
		
		if cameraFound is True:
			cameradb["dev"] = dev_path.split('/')[-1]
			camera.SetFramesPerVideo(int(cameradb["frame_per_video"]))
			camera.SetRecordingSensetivity(int(cameradb["camera_sensetivity_recording"]))
			camera.SetSecuritySensetivity(int(cameradb["camera_sensetivity_security"]))
			camera.SetHighDiff(int(cameradb["high_diff"]))
			camera.SetSecondsPerFrame(float(cameradb["seconds_per_frame"]))
		else:
			print ("({classname})# New camera... Adding to the database...".format(classname=self.ClassName))
			cameradb = {
				'uid': str(uid),
				'name': 'Camera_' + str(uid),
				'dev': dev_path,
				'enable':1,
				"frame_per_video": 2000,
				"camera_sensetivity_recording": 95,
				"camera_sensetivity_security": 95,
				"recording": 0,
				"face_detect": 0,
				"security": 0,
				"motion_detection": 0,
				"status": "connected",
				"high_diff": 5000, 
				"seconds_per_frame": 1, 
				"phone": "+972544784156",
				"email": "yevgeniy.kiveisha@gmail.com",
				'access_from_www': 1
			}
			# Append new camera.
			dbCameras.append(cameradb)
			camera.SetFramesPerVideo(2000)
			camera.SetRecordingSensetivity(95)
			camera.SetSecuritySensetivity(95)
			camera.SetHighDiff(5000)
			camera.SetSecondsPerFrame(1)
			# Add camera to camera obejct DB
			self.ObjCameras.append(camera)
			cameradb["enable"] = 1
		
		# Start camera thread
		camera.StartCamera()
		# Check weither need to start recording
		if 1 == cameradb["recording"]:
			camera.StartRecording()
		# Do we record into local storage
		if (self.LocalStorageEnabled == 1):
			camera.SetRecordingPath(self.LocalStoragePath)
		else:
			camera.SetRecordingPath("{0}/{1}".format(self.USBStoragePath,self.USBDevice["name"]))
			path = "{0}/{1}/{2}/video".format(self.USBStoragePath,self.USBDevice["name"],cameradb["uid"])
			if not os.path.exists(path):
				os.makedirs(path)
		# Create local storage folder
		path = "{0}/{1}/video".format(self.LocalStoragePath,cameradb["uid"])
		if not os.path.exists(path):
			os.makedirs(path)
		else:
			pass
		# If security is ON we need to get frames
		if self.SecurityEnabled is True:
			camera.StartSecurity()
		# Update camera object with values from database
		camera.Name = cameradb["name"]
		camera.UID 	= uid
		camera.OnImageDifferentCallback = self.OnCameraDiffrentHandler
		camera.StopRecordingEvent 		= self.StopRecordingEventHandler
		cameradb["enable"] = 1
		# Add camera to camera obejct DB
		self.ObjCameras.append(camera)
			
		print ("({classname})# Emit camera_connected {dev}".format(classname=self.ClassName,dev=cameradb["dev"]))
		THIS.Node.EmitOnNodeChange({
				'event': "camera_connected",
				'camera': cameradb
		})

	def NodeSystemLoadedHandler(self):
		print ("({classname})# Loading system ...".format(classname=self.ClassName))
		objFile = MkSFile.File()
		# THIS.Node.GetListOfNodeFromGateway()
		# Loading local database
		jsonSensorStr = objFile.Load("db.json")
		if jsonSensorStr != "":
			self.DB = json.loads(jsonSensorStr)
			if self.DB is not None:
				for item in self.DB["cameras"]:
					self.Cameras.append(item)
		
		'''
		1. Check if USB device available.
			- If not availabale, set flag ('can_not_record') cannot record.
			- If available, continue as expected.
			- Note, camera will store frames into buffer 
			  but want save to file until device will be available.
		'''
		self.LocalStorageEnabled = self.DB["local_storage"]

		# Get USB device
		self.USBDevice = self.DB["usb_device"]

		# Create file system for storing videos
		if not os.path.exists(self.LocalStoragePath):
			os.makedirs(self.LocalStoragePath)
		
		if not os.path.exists(self.USBStoragePath):
			os.makedirs(self.USBStoragePath)
		
		# Check if security is ON
		if self.DB["security"] == 1:
			self.SecurityEnabled = True

		# Search for cameras
		print ("({classname})# Searching for cameras ...".format(classname=self.ClassName))
		paths = self.SerachForCameras()
		# Get ipscameras from db
		dbCameras = self.DB["cameras"]
		# Disable all cameras
		for itemCamera in dbCameras:
			itemCamera["enable"] = 0
		# Check all connected ips
		print ("({classname})# Updating cameras database ...".format(classname=self.ClassName))
		for path in paths:
			self.UpdateCameraStracture(dbCameras, path)
		
		self.DB["cameras"] = dbCameras
		# Save new camera to database
		objFile.Save("db.json", json.dumps(self.DB))
		self.HJTDetectorTimestamp = time.time()
		print ("({classname})# Loading system ... DONE.".format(classname=self.ClassName))
	
	def OnApplicationCommandRequestHandler(self, sock, packet):
		command = self.Node.BasicProtocol.GetCommandFromJson(packet)
		if command in self.RequestHandlers:
			return self.RequestHandlers[command](sock, packet)
		
		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'error': '-1'
		})

	def OnApplicationCommandResponseHandler(self, sock, packet):
		command = self.Node.BasicProtocol.GetCommandFromJson(packet)
		if command in self.ResponseHandlers:
			self.ResponseHandlers[command](sock, packet)
	
	def OnGetNodesListHandler(self, uuids):
		print (" ?????????????????????? OnGetNodesListHandler", uuids)
		# TODO - Find SMS service
		#for uuid in uuids:
		#	THIS.Node.LocalServiceNode.GetNodeInfo(uuid)

	def GetNodeInfoHandler(self, key):
		return json.dumps({
			'response':'OK'
		})

	def SetNodeInfoHandler(self, key, id):
		return json.dumps({
			'response':'OK'
		})

	def GetSensorsInfoHandler(self, key):
		return json.dumps({
			'response':'OK'
		})

	def SetSensorInfoHandler(self, key, id, value):
		return json.dumps({
			'response':'OK'
		})
	
	def FileDownloadHandler(self, name):
		print ("[WEB API] FileDownloadHandler", name)

		FilePath = "./videos/" + name
		return send_file(FilePath)

	def OnLocalServerListenerStartedHandler(self, sock, ip, port):
		THIS.Node.AppendFaceRestTable(endpoint="/get/node_info/<key>", 						endpoint_name="get_node_info", 			handler=THIS.GetNodeInfoHandler)
		THIS.Node.AppendFaceRestTable(endpoint="/set/node_info/<key>/<id>", 				endpoint_name="set_node_info", 			handler=THIS.SetNodeInfoHandler, 	method=['POST'])
		THIS.Node.AppendFaceRestTable(endpoint="/get/node_sensors_info/<key>", 				endpoint_name="get_node_sensors", 		handler=THIS.GetSensorsInfoHandler)
		THIS.Node.AppendFaceRestTable(endpoint="/set/node_sensor_info/<key>/<id>/<value>", 	endpoint_name="set_node_sensor_value", 	handler=THIS.SetSensorInfoHandler)
		THIS.Node.AppendFaceRestTable(endpoint="/file/download/<name>", 					endpoint_name="file_download", 			handler=THIS.FileDownloadHandler)

	def CameraRunningStatus(self, dev):
		for camera in self.ObjCameras:
			if (camera.DevicePath == dev):
				return True
		return False

	def WorkingHandler(self):
		if time.time() - self.CurrentTimestamp > self.Interval:
			self.CheckingForUpdate = True
			self.CurrentTimestamp = time.time()

			print("\nTables:")
			for idx, item in enumerate(THIS.Node.GetConnections()):
				print ("  {0}\t{1}\t{2}\t{3}\t{4}\t{5}".format(str(idx),item.LocalType,item.UUID,item.IP,item.Port,item.Type))
			print("")
			return
			for idx, camera in enumerate(self.ObjCameras):
				print ("  {0}\t{1}\t{2}\t{3}\t{4}".format(str(idx),camera.IPAddress,camera.UID,camera.MAC,camera.Address))
			print("")

			# Search for usb storage in /media/[USER]/
			self.USBDevices = self.File.ListAllInFolder(self.USBStoragePath)

			dbCameras = self.DB["cameras"]
			for itemCamera in dbCameras:
				camera = None
				for item in self.ObjCameras:
					if (item.GetIp() in itemCamera["ip"]):
						camera = item
						break
				if camera is not None:
					THIS.Node.EmitOnNodeChange({
							'event': "misc_info",
							'camera': itemCamera,
							'data': {
								'progress': str(camera.GetCapturingProcess()),
								'fps': str(camera.GetFPS()),
								'usb_device': self.USBDevice,
								'usb_devices': self.USBDevices,
								'local_storage_enabled': self.LocalStorageEnabled
							}
					})
			
		if time.time() - self.HJTDetectorTimestamp > 60 * 1:
			return
			print ("({classname})# Seraching for cameras ...".format(classname=self.ClassName))
			# Search for cameras
			ips = self.SerachForCameras()
			
			# Get cameras from db
			dbCameras = self.DB["cameras"]
			# Remove disconnected devices
			for camera in self.ObjCameras:
				if (camera.GetIp() not in ips):
					# Camera was disconnected
					print ("({classname})# Deleting camera ({ip}) ...".format(classname=self.ClassName, ip=camera.GetIp()))
					# Disable camera in database
					for itemCamera in dbCameras:
						if camera.GetIp() in itemCamera["ip"]:
							itemCamera["enable"] = 0
							THIS.Node.EmitOnNodeChange({
									'event': "camera_disconnected",
									'camera': itemCamera
							})
					# Remove camera from object list
					camera.StopCamera()
					time.sleep(2)
					self.ObjCameras.remove(camera)
			
			# Check all connected ips
			for ip in ips:
				# This camera is running
				if (self.CameraRunningStatus(ip) is True):
					print ("({classname})# Camera is running ... ({ip}) ...".format(classname=self.ClassName, ip=ip))
				else:
					# Update camera
					self.UpdateCameraStracture(dbCameras, ip)
			
			self.DB["cameras"] = dbCameras
			# Save new camera to database
			self.File.Save("db.json", json.dumps(self.DB))
			self.HJTDetectorTimestamp = time.time()
	
	def StopRecordingEventHandler(self, data):
		print ("({classname})# Recording path ({path}) is invalid for camera({ip})".format(classname=self.ClassName,path=data["path"],ip=data["ip"]))
		objFile 	= MkSFile.File()
		dbCameras 	= self.DB["cameras"]
		for camera in dbCameras:
			if data["uid"] in camera["uid"] and data["mac"] in camera["mac"]:
				camera["recording"] = 0
				# Send event to application
				THIS.Node.EmitOnNodeChange({
								'camera_ip': data["ip"],
								'event': "stop_recording",
							})
				self.DB["cameras"] = dbCameras
				# Save new camera to database
				objFile.Save("db.json", json.dumps(self.DB))
				return

Node = MkSSlaveNode.SlaveNode()
THIS = Context(Node)

def signal_handler(signal, frame):
	THIS.Node.Stop()

def main():
	signal.signal(signal.SIGINT, signal_handler)
	THIS.Node.SetLocalServerStatus(True)
	
	# Node callbacks
	THIS.Node.NodeSystemLoadedCallback				= THIS.NodeSystemLoadedHandler
	THIS.Node.OnLocalServerListenerStartedCallback 	= THIS.OnLocalServerListenerStartedHandler
	THIS.Node.OnApplicationRequestCallback			= THIS.OnApplicationCommandRequestHandler
	THIS.Node.OnApplicationResponseCallback			= THIS.OnApplicationCommandResponseHandler
	THIS.Node.OnGetNodesListCallback				= THIS.OnGetNodesListHandler
	THIS.Node.OnGetNodeInfoCallback					= THIS.OnGetNodeInfoHandler
	
	THIS.Node.Run(THIS.WorkingHandler)
	print ("Exit Node ...")

if __name__ == "__main__":
    main()
