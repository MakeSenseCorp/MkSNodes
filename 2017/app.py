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
from mksdk import MkSNode
from mksdk import MkSSlaveNode
from mksdk import MkSLocalHWConnector
from mksdk import MkSUSBAdaptor
from mksdk import MkSProtocol

from flask import Response, request
from flask import send_file

class EthernetDeviceScanner():
	def __init__(self):
		self.ObjName 			= "EthernetDeviceScanner"
		self.IPList				= []
		self.ThreadCounter 		= 0
		self.ThreadCounterLock	= threading.Lock()

	def Ping(self, address):
		response = subprocess.call("ping -c 1 %s" % address,
				shell=True,
				stdout=open('/dev/null', 'w'),
				stderr=subprocess.STDOUT)
		# Check response
		if response == 0:
			return True
		else:
			return False
	
	def PingThread(self, address):
		res = self.Ping(address)
		self.ThreadCounterLock.acquire()
		if True == res:
			self.IPList.append(address)
		self.ThreadCounter += 1
		self.ThreadCounterLock.release()

	def Scan(self, network, index):
		self.ThreadCounter 		= 0
		self.Network		 	= network
		self.IPCount 			= index[1] - index[0]
		self.IPList 			= []

		if (self.IPCount < 0):
			return []
		
		for i in range(index[0], index[1]):
			address = self.Network + str(i)
			thread.start_new_thread(self.PingThread, (address,))
		
		while (self.ThreadCounter != self.IPCount):
			pass
		
		return self.IPList

class HJTCameraScanner():
	def __init__(self):
		self.ObjName 			= "HJTCameraScanner"
		self.Cameras			= []
		self.ThreadCounter 		= 0
		self.ThreadCounterLock	= threading.Lock()

	def SendRequest(self, url):
		try:
			urllib2.urlopen("http://" + url, timeout = 1).read()
		except urllib2.HTTPError as e:
			if 401 == e.code:
				return True
		except:
			pass
		
		return False
	
	def RequestThread(self, address):
		res = self.SendRequest(address)
		self.ThreadCounterLock.acquire()
		if True == res:
			self.Cameras.append(address)
		self.ThreadCounter += 1
		self.ThreadCounterLock.release()

	def Scan(self, addresses):
		self.ThreadCounter 		= 0
		self.CamerasCount 		= len(addresses)
		self.Cameras 			= []

		if (self.CamerasCount < 0):
			return []
		
		for ip in addresses:
			thread.start_new_thread(self.RequestThread, (ip,))
		
		while (self.ThreadCounter != self.CamerasCount):
			pass
		
		return self.Cameras

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

class ICamera():
	def __init__(self, ip):
		self.ImP						= MkSImageProcessing()
		self.IPAddress 					= ip
		self.Address 					= "http://" + self.IPAddress + "/"
		self.Name 						= ""
		self.UID 						= ""
		self.MAC 						= ""
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

	def GetRequest (self, url):
		username = 'admin'
		password = 'admin'
		
		try:
			p = urllib2.HTTPPasswordMgrWithDefaultRealm()
			p.add_password(None, url, username, password)

			handler = urllib2.HTTPBasicAuthHandler(p)
			opener = urllib2.build_opener(handler)
			urllib2.install_opener(opener)
			reader = urllib2.urlopen(url, timeout = 2)
			if reader is not None:
				data = reader.read()
			else:
				return "", True
		except Exception as e:
			print ("HTTPException GetRequest ({url}) {error}".format(url=url,error=e))
			return "", True

		return data, False

	def GetCapturingProcess(self):
		return int((float(self.CurrentImageIndex) / float(self.FramesPerVideo)) * 100.0)
	
	def GetFPS(self):
		return self.FPS

	def Frame(self):
		command = self.GetFrame()
		self.FrameCount +=  1
		frame, error = self.GetRequest(self.Address + command)
		return frame, error
	
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
		print ("[Camera] Stop recording {0}".format(self.IPAddress))
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
					print("[FRAME] ({0}) ({1}) ({ip}) (diff={diff}) (sensitivity={sensy}) (fps={fps})".format(	str(self.FrameCount),
																						str(len(frame_cur)),
																						diff=str(frame_dif),
																						fps=str(self.FPS),
																						sensy=str(self.SecuritySensitivity),
																						ip=str(self.IPAddress)))
					ts = time.time()
					if (frame_dif < self.SecuritySensitivity):
						THIS.Node.EmitOnNodeChange({
									'camera_ip': str(self.IPAddress),
									'event': "new_frame", 
									'frame': base64.encodestring(frame_cur)
						})

					if self.IsSecurity is True:
						if (frame_dif < self.SecuritySensitivity):
							print("[Camera] Security {diff} {sensitivity}".format(diff = str(frame_dif), sensitivity = str(self.SecuritySensitivity)))
							if self.OnImageDifferentCallback is not None:
								self.OnImageDifferentCallback(self.IPAddress, frame_cur)
				
					if self.IsRecoding is True:
						# Check for valid storage
						if not os.path.exists(self.RecordingPath):
							if self.StopRecordingEvent is not None:
								self.StopRecordingEvent({
									'path': self.RecordingPath,
									'ip': self.IPAddress,
									'mac': self.MAC,
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
				time.sleep(self.SecondsPerFrame)
			else:
				time.sleep(1)
			self.WorkingStatusLock.acquire()
		print ("({classname})# Exit RECORDING THREAD ...".format(classname=self.ClassName))

class HJTCamera(ICamera):
	def __init__(self, ip):
		ICamera.__init__(self, ip)
		self.ClassName 	= "HJTCamera"
		self.Commands 	= {
			'frame': 			"tmpfs/auto.jpg",
			'getnetattr': 		"web/cgi-bin/hi3510/param.cgi?cmd=getnetattr",
			'getserverinfo': 	"web/cgi-bin/hi3510/param.cgi?cmd=getserverinfo",
			'getxqp2pattr': 	"web/cgi-bin/hi3510/param.cgi?cmd=getxqp2pattr"
		}
		self.UserSensitiviy = 0

	def GetIp(self):
		return self.IPAddress

	def GetAPIName(self):
		return "hjt-ipc6100-b1w"

	def GetFrame(self):
		return self.Commands['frame']

	def GetUID(self):
		data, error = self.GetRequest(self.Address + self.Commands['getxqp2pattr'])
		items = data.split("\r\n")
		for item in items:
			if "xqp2p_uid" in item:
				uid = item.split('\"')
				return uid[1]
		return ""

	def GetMACAddress(self):
		data, error = self.GetRequest(self.Address + self.Commands['getnetattr'])
		if error is True:
			return ""

		# Find MAC address from recieved string
		p = re.compile('(?:[0-9a-fA-F]:?){12}') # ur'(?:[0-9a-fA-F]:?){12}'
		mac = re.findall(p, data)
		return mac[0] # TODO - Check mac is not null

class Context():
	def __init__(self, node):
		self.ClassName					= "Apllication"
		self.Interval					= 10
		self.CurrentTimestamp 			= time.time()
		self.File 						= MkSFile.File()
		self.Node						= node
		self.IPNetwork 					= "10.0.0."
		self.IPAddresses				= [1,32]
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
		self.DeviceScanner 				= EthernetDeviceScanner()
		self.SecurityEnabled 			= False
		self.SMSService					= ""
		self.EmailService				= ""

		self.LastTSEmailSent			= 0
		self.HJTDetectorTimestamp 		= time.time()
		self.LocalStorageEnabled 		= 0
		self.USBDevices 				= []
		self.USBDevice 					= None
		self.LocalStoragePath 			= "/home/ykiveish/mks/nodes/2017/videos/local"
		self.USBStoragePath 			= "/home/ykiveish/mks/nodes/2017/videos/usb"

	def UndefindHandler(self, message_type, source, data):
		print ("UndefindHandler")

	def GetSensorInfoHandler(self, sock, packet):
		print ("({classname})# GetSensorInfoHandler ...".format(classname=self.ClassName))
		# enabledCameras = [camera for camera in self.Cameras if camera["enable"] == 1] # Comprehension
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
			if (item.GetIp() in payload["ip"]):
				frame, error = item.Frame()
				if error is False:
					return THIS.Node.BasicProtocol.BuildResponse(packet, {
									'camera_ip': str(item.GetIp()),
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
			if (item.GetIp() in payload["ip"]):
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
			if itemCamera["ip"] in payload["ip"]:
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
			if itemCamera["ip"] in payload["ip"]:
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
					if (item.GetIp() in payload["ip"]):
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
		"""
		if len(self.EmailService) > 0:
			if (time.time() - self.LastTSEmailSent > 30):
				print("Email service exist... Sending request...")
				THIS.Node.LocalServiceNode.SendMessageToNodeViaGateway(self.EmailService, "send_email_html_with_image",
							{	
								'request': 'task_order',
								'json': {
									'to': ['yevgeniy.kiveisha@gmail.com'],
									'subject': 'MakeSense - Security alert from camera',
									'body': '<b>Image taken by camera<br><img src="cid:image1"><br>',
									'type': 'text',
									'image': base64.encodebytes(image).decode("utf-8")
								}
							})
				self.LastTSEmailSent = time.time()
		else:
			print("Email service NOT FOUND... Canceling request...")
		
		if len(self.SMSService) > 0:
			THIS.Node.LocalServiceNode.SendMessageToNodeViaGateway(self.SMSService, "send_sms",
						{	
							'request': 'task_order',
							'json': {
								'number': '0547884156',
								'message': 'hello' 
							}
						})
		else:
			print("SMS service NOT FOUND... Canceling request...")
		"""
	
	def OnMasterAppendNodeHandler(self, uuid, type, ip, port):
		print ("[OnMasterAppendNodeHandler]", str(uuid), str(type), str(ip), str(port))
		if (101 == type):
			self.SMSService = uuid
			print("[OnMasterAppendNodeHandler]","SMS service found")
		if (102 == type):
			self.EmailService = uuid
			print("[OnMasterAppendNodeHandler]","Email service found")
	
	def OnMasterRemoveNodeHandler(self, uuid, type, ip, port):
		print ("[OnMasterRemoveNodeHandler]", str(uuid), str(type), str(ip), str(port))
		if (101 == type):
			self.SMSService = ""
			print("[OnMasterRemoveNodeHandler]","SMS service REMOVED... Please DON NOT use service!")
		if (102 == type):
			self.EmailService = ""
			print("[OnMasterRemoveNodeHandler]","Email service REMOVED... Please DON NOT use service!")

	def SerachForCameras(self):
		cameras 	= self.DeviceScanner.Scan(self.IPNetwork, self.IPAddresses)
		HJTScanner 	= HJTCameraScanner()
		return HJTScanner.Scan(cameras)
	
	def UpdateCameraStracture(self, dbCameras, ip):
		camera 	= HJTCamera(ip)
		mac 	= camera.GetMACAddress()
		uid 	= camera.GetUID()
		# Update camera IP (if it was changed)
		for itemCamera in dbCameras:
			cameraFound = False
			# Invalid MAC or UID (TODO - Do re.compile for MAC)
			if uid == "" or mac == "":
				print ("({classname})# Found IP is not valid camera".format(classname=self.ClassName))
			else:
				# Is camera exist in DB
				if uid in itemCamera["uid"] and mac in itemCamera["mac"]:
					# Update DB with current IP
					itemCamera["ip"] = ip
					# Start camera thread
					camera.StartCamera()
					# Check weither need to start recording
					if 1 == itemCamera["recording"]:
						camera.StartRecording()
					# Do we record into local storage
					if (self.LocalStorageEnabled == 1):
						camera.SetRecordingPath(self.LocalStoragePath)
					else:
						camera.SetRecordingPath("{0}/{1}".format(self.USBStoragePath,self.USBDevice["name"]))
						path = "{0}/{1}/{2}/video".format(self.USBStoragePath,self.USBDevice["name"],itemCamera["uid"])
						if not os.path.exists(path):
							os.makedirs(path)
					# Create local storage folder
					path = "{0}/{1}/video".format(self.LocalStoragePath,itemCamera["uid"])
					if not os.path.exists(path):
						os.makedirs(path)
					else:
						print (path)
					# If security is ON we need to get frames
					if self.SecurityEnabled is True:
						camera.StartSecurity()
					# Update camera object with values from database
					camera.Name = itemCamera["name"]
					camera.UID 	= uid
					camera.MAC 	= mac
					camera.SetFramesPerVideo(int(itemCamera["frame_per_video"]))
					camera.SetRecordingSensetivity(int(itemCamera["camera_sensetivity_recording"]))
					camera.SetSecuritySensetivity(int(itemCamera["camera_sensetivity_security"]))
					camera.SetHighDiff(int(itemCamera["high_diff"]))
					camera.SetSecondsPerFrame(float(itemCamera["seconds_per_frame"]))
					camera.OnImageDifferentCallback = self.OnCameraDiffrentHandler
					camera.StopRecordingEvent 		= self.StopRecordingEventHandler
					# Add camera to camera obejct DB
					self.ObjCameras.append(camera)
					cameraFound = True
					itemCamera["enable"] = 1
					break
			
				if cameraFound is False:
					print ("[Camera Surveillance]>", "NodeSystemLoadedHandler - False")
					# Append new camera.
					dbCameras.append({
									'mac': str(mac),
									'uid': str(uid),
									'ip': str(ip),
									'name': 'Camera_' + str(uid),
									'enable':1,
									"frame_per_video": 2000,
									"camera_sensetivity_recording": 95,
									"camera_sensetivity_security": 95,
									"recording": 0,
									"face_detect": 0,
									"security": 0,
									"motion_detection": 0,
									"status": "disconnected",
									"high_diff": 5000, 
									"seconds_per_frame": 1, 
									"phone": "+972544784156",
									"email": "yevgeniy.kiveisha@gmail.com",
									'access_from_www': 1
					})
					camera.SetFramesPerVideo(2000)
					camera.SetRecordingSensetivity(95)
					# Add camera to camera obejct DB
					self.ObjCameras.append(camera)
			
				print ("({classname})# Emit camera_connected {ip}".format(classname=self.ClassName,ip=itemCamera["ip"]))
				THIS.Node.EmitOnNodeChange({
						'event': "camera_connected",
						'camera': itemCamera
				})

	def NodeSystemLoadedHandler(self):
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
		ips = self.SerachForCameras()
		# Get cameras from db
		dbCameras = self.DB["cameras"]
		# Disable all cameras
		for itemCamera in dbCameras:
			itemCamera["enable"] = 0
		# Check all connected ips
		for ip in ips:
			self.UpdateCameraStracture(dbCameras, ip)
		
		self.DB["cameras"] = dbCameras
		# Save new camera to database
		objFile.Save("db.json", json.dumps(self.DB))
		self.HJTDetectorTimestamp = time.time()
	
	def OnApplicationCommandRequestHandler(self, sock, packet):
		print ("({classname})# REQUEST".format(classname=self.ClassName))
		command = self.Node.BasicProtocol.GetCommandFromJson(packet)
		if command in self.RequestHandlers:
			return self.RequestHandlers[command](sock, packet)
		
		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'error': '-1'
		})

	def OnApplicationCommandResponseHandler(self, sock, packet):
		print ("({classname})# RESPONSE".format(classname=self.ClassName))
		command = self.Node.BasicProtocol.GetCommandFromJson(packet)
		if command in self.ResponseHandlers:
			self.ResponseHandlers[command](sock, packet)
	
	def OnGetNodesListHandler(self, uuids):
		print (" ?????????????????????? OnGetNodesListHandler", uuids)
		# TODO - Find SMS service
		#for uuid in uuids:
		#	THIS.Node.LocalServiceNode.GetNodeInfo(uuid)
	
	def OnGetNodeInfoHandler(self, info):
		print ("OnGetNodeInfoHandler")
		# TODO - info must be only data of a device, not whole packet
		'''
		{
			u'direction': u'proxy_response', 
			u'command': u'get_node_info', u
			'piggybag': 0, 
			u'payload': {
				u'header': {
					u'source': u'ac6de837-9863-72a9-c789-a0aae7e9d021', 
					u'destination': u'ac6de837-9863-72a9-c789-a0aae7e9d021'
				}, 
				u'data': {
					u'isMasterNode': u'False', 
					u'isHW': u'False', 
					u'uuid': u'ac6de837-9863-72a9-c789-a0aae7e9d021', 
					u'name': u'HJT', 
					u'isLocalServerEnabled': u'True', 
					u'brandname': u'Camera Surveillance', 
					u'isWebEnabled': u'True', 
					u'ostype': u'Any', 
					u'osversion': u'Any', 
					u'type': 2017, 
					u'description': u'Camera Surveillance'
				}
			}
		}
		'''
		nodeType = info["payload"]["data"]["type"]
		nodeUUID = info["payload"]["data"]["uuid"]
		if (101 == nodeType):
			self.SMSService = nodeUUID
			print("[OnGetNodeInfoHandler]", "SMS service found")
		if (102 == nodeType):
			self.EmailService = nodeUUID
			print("[OnMasterAppendNodeHandler]","Email service found")

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

	def CameraRunningStatus(self, ip, ips):
		for camera in self.ObjCameras:
			if (camera.GetIp() in ips):
				return True
		return False

	def WorkingHandler(self):
		if time.time() - self.CurrentTimestamp > self.Interval:
			self.CheckingForUpdate = True
			self.CurrentTimestamp = time.time()

			for idx, item in enumerate(THIS.Node.GetConnections()):
				print ("  ", str(idx), item.LocalType, item.UUID, item.IP, item.Port, item.Type)
			
			# Search for usb storage in /media/[USER]/
			self.USBDevices = self.File.ListAllInFolder(self.USBStoragePath)
			
		if time.time() - self.HJTDetectorTimestamp > 60 * 1:
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
				if (self.CameraRunningStatus(ip, ips) is True):
					print ("({classname})# Camara is running ... ({ip}) ...".format(classname=self.ClassName, ip=ip))
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
	THIS.Node.OnMasterAppendNodeCallback			= THIS.OnMasterAppendNodeHandler
	THIS.Node.OnMasterRemoveNodeCallback			= THIS.OnMasterRemoveNodeHandler
	
	THIS.Node.Run(THIS.WorkingHandler)
	print ("Exit Node ...")

if __name__ == "__main__":
    main()
