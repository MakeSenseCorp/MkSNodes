#!/usr/bin/python
import os
import sys
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

from mksdk import MkSFile
from mksdk import MkSNode
from mksdk import MkSSlaveNode
from mksdk import MkSLocalHWConnector
from mksdk import MkSUSBAdaptor
from mksdk import MkSProtocol

from flask import Response, request

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
		while (self.IsRunning is True):
			item = self.Orders.get(block=True,timeout=None)
			logging.info("[VideoCreator] Start video encoding...")
			images = item["images"]
			recordingProcess = Popen(['ffmpeg', '-y', '-f', 'image2pipe', '-vcodec', 'mjpeg', '-r', str(self.FPS), '-i', '-', '-vcodec', 'mpeg4', '-qscale', '5', '-r', str(self.FPS), '/tmp/video_fs/videos/video'+str(time.time())+'.avi'], stdin=PIPE)
			for frame in images:
				image = Image.open(BytesIO(frame))
				image.save(recordingProcess.stdin, 'JPEG')
			recordingProcess.stdin.close()
			recordingProcess.wait()
			logging.debug("[VideoCreator] {images} {item}".format(images = str(id(images)), item = str(id(item))))
			images = []
			item = None
			logging.info("[VideoCreator] Start video encoding... DONE")

GEncoder = VideoCreator()

class MkSImageProcessing():
	def __init__(self):
		self.ObjName 	= "ImageProcessing"
		self.MAX_DIFF	= 5000 # MAX = 261120
	
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
			diff_precentage = (float(self.MAX_DIFF - (np.abs(im[0] - im[1]).sum())) / self.MAX_DIFF) * 100
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
		self.IsGetFrame 				= False
		self.IsRecoding 				= False
		self.IsCameraWorking 			= False
		self.IsSecurity					= False
		self.FramesPerVideo 			= 2000
		self.RecordingSensetivity 		= 95
		self.SecuritySensitivity 		= 92
		self.CurrentImageIndex 			= 0
		self.OnImageDifferentCallback	= None

	def SetFramesPerVideo(self, value):
		self.FramesPerVideo = value

	def SetRecordingSensetivity(self, value):
		self.RecordingSensetivity = value

	def GetRequest (self, url):
		username = 'admin'
		password = 'admin'
		
		try:
			p = urllib2.HTTPPasswordMgrWithDefaultRealm()
			p.add_password(None, url, username, password)

			handler = urllib2.HTTPBasicAuthHandler(p)
			opener = urllib2.build_opener(handler)
			urllib2.install_opener(opener)
			data = urllib2.urlopen(url).read()
		except Exception as e:
			# TODO - Exit node
			print ("HTTPException", e)
			return "", True

		return data, False

	def GetCapturingProcess(self):
		return int((float(self.CurrentImageIndex) / float(self.FramesPerVideo)) * 100.0)

	def Frame(self):
		command = self.GetFrame()
		frame, error = self.GetRequest(self.Address + command)
		return frame

	def StartSecurity(self):
		self.IsSecurity = True
		self.IsGetFrame = True

	def StopSecurity(self):
		self.IsSecurity = False
		if self.IsRecoding is False:
			self.IsGetFrame = False
	
	def StartGettingFrames(self):
		self.IsGetFrame = True

	def StopGettingFrames(self):
		self.IsGetFrame = False
	
	def StartRecording(self):
		self.IsRecoding = True
		self.IsGetFrame = True

	def StopRecording(self):
		self.IsRecoding = False
		if self.IsSecurity is False:
			self.IsGetFrame = False

	def StartCamera(self):
		if (self.IsCameraWorking is False):
			thread.start_new_thread(self.CameraThread, ())

	def StopCamera(self):
		print ("[Camera] Stop recording", self.IPAddress)
		self.IsCameraWorking = False

	def CameraThread(self):
		global GEncoder
		
		frameCurr 		= None
		framePrev 		= None
		frameDifference = 0

		# TODO - Create logging to file system.
		# TODO - Create common print message format
		# TODO - Create folder path if there are none
		# TODO - Each camera has its own folder
		# TODO - Percentage of threshhold should be managable from UI
		# TODO - Update record_ticker according to images in folder
		# TODO - Is video creation is on going?
		# TODO - Each camera must have its own video folder.

		recordingBuffer = []
		self.IsCameraWorking = True
		while self.IsCameraWorking is True:
			if self.IsGetFrame is True:
				frameCurr = self.Frame()
				frameDifference = self.ImP.CompareJpegImages(frameCurr, framePrev)
			else:
				time.sleep(0.5)
			
			if self.IsSecurity is True:
				if (frameDifference < self.SecuritySensitivity):
					print("[Camera] Security {diff} {sensitivity}".format(diff = str(frameDifference), sensitivity = str(self.SecuritySensitivity)))
					framePrev = frameCurr
					if self.OnImageDifferentCallback is not None:
						self.OnImageDifferentCallback(self.IPAddress, None)
			
			if self.IsRecoding is True:
				if (frameDifference < self.RecordingSensetivity):
					recordingBuffer.append(frameCurr)
					print("[Camera] Recording {frames} {diff} {sensitivity}".format(frames = str(len(recordingBuffer)), diff = str(frameDifference), sensitivity = str(self.RecordingSensetivity)))
					framePrev = frameCurr
					self.CurrentImageIndex = len(recordingBuffer)
				
				if self.FramesPerVideo <= self.CurrentImageIndex:
					GEncoder.AddOrder({
						'images': recordingBuffer
					})
					logging.debug("Sent recording order " + str(id(recordingBuffer)))
					recordingBuffer = []
					self.CurrentImageIndex = len(recordingBuffer)

class HJTCamera(ICamera):
	def __init__(self, ip):
		ICamera.__init__(self, ip)
		self.Commands = {
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
		return 0

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
		self.Interval					= 10
		self.CurrentTimestamp 			= time.time()
		self.Node						= node
		# States
		self.States = {
		}
		# Handlers
		self.Handlers					= {
			'undefined':				self.UndefindHandler
		}
		self.CustomRequestHandlers				= {
			'start_recording': 							self.StartRecordingHandler,
			'stop_recording': 							self.StopRecordingHandler,
			'start_motion_detection': 					self.StartMotionDetectionHandler,
			'stop_motion_detection': 					self.StopMotionDetectionHandler,
			'start_security': 							self.StartSecurityHandler,
			'stop_security': 							self.StopSecurityHandler,
			'set_camera_name': 							self.SetCameraNameHandler,
			'get_capture_progress':						self.GetCaptureProgressHandler,
			'set_face_detection':						self.SetFaceDetectionHandler,
			'set_camera_sensetivity':					self.SetCameraSensetivityHandler,
			'get_videos_list':							self.GetVideosListHandler,
			'get_misc_information':						self.GetMiscInformationHandler,
			'set_misc_information':						self.SetMiscInformationHandler,
		}
		self.CustomResponseHandlers				= {
		}

		self.DB							= None
		self.Cameras 					= []
		self.ObjCameras					= []
		self.DeviceScanner 				= EthernetDeviceScanner()
		self.SecurityEnabled 			= False

	def UndefindHandler(self, message_type, source, data):
		print ("UndefindHandler")

	# CustomRequestHandlers
	def StartRecordingHandler(self, sock, packet):
		print("StartRecordingHandler")
		print (packet)
		# Find camera
		for item in self.ObjCameras:
			if (item.GetIp() in packet["payload"]["data"]["ip"]):
				# TODO - Each camera must have its own directory
				item.StartRecording()
				cameras = self.DB["cameras"]
				for item in cameras:
					if (item["ip"] in packet["payload"]["data"]["ip"]):
						item["recording"] = 1
						self.Node.SetFileContent("db.json", json.dumps(self.DB))
				
		THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
			'return_code': 'STARTED'
		})

	def StopRecordingHandler(self, sock, packet):
		print("StopRecordingHandler")
		# Find camera
		for item in self.ObjCameras:
			if (item.GetIp() in packet["payload"]["data"]["ip"]):
				# TODO - Each camera must have its own directory
				item.StopRecording()
				cameras = self.DB["cameras"]
				for item in cameras:
					if (item["ip"] in packet["payload"]["data"]["ip"]):
						item["recording"] = 0
						self.Node.SetFileContent("db.json", json.dumps(self.DB))
		
		THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
			'return_code': 'STOPPED'
		})

	def StartMotionDetectionHandler(self, sock, packet):
		print("StartMotionDetectionHandler")
		cameras = self.DB["cameras"]
		for item in cameras:
			if (item["ip"] in packet["payload"]["data"]["ip"]):
				item["motion_detection"] = 1
				self.Node.SetFileContent("db.json", json.dumps(self.DB))
		THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
			'return_code': 'STARTED'
		})

	def StopMotionDetectionHandler(self, sock, packet):
		print("StopMotionDetectionHandler")
		cameras = self.DB["cameras"]
		for item in cameras:
			if (item["ip"] in packet["payload"]["data"]["ip"]):
				item["motion_detection"] = 0
				self.Node.SetFileContent("db.json", json.dumps(self.DB))
		THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
			'return_code': 'STOPPED'
		})

	def StartSecurityHandler(self, sock, packet):
		print("StartSecurityHandler")
		self.DB["security"] = 1
		self.SecurityEnabled = True
		cameras = self.DB["cameras"]
		for item in cameras:
			item["security"] = 1
		self.DB["cameras"] = cameras
		for item in self.ObjCameras:
			item.StartSecurity()
		self.Node.SetFileContent("db.json", json.dumps(self.DB))
		THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
			'return_code': 'STARTED'
		})

	def StopSecurityHandler(self, sock, packet):
		print("StopSecurityHandler")
		self.DB["security"] = 0
		self.SecurityEnabled = False
		cameras = self.DB["cameras"]
		for item in cameras:
			item["security"] = 0
		for item in self.ObjCameras:
			item.StopSecurity()
		self.DB["cameras"] = cameras
		self.Node.SetFileContent("db.json", json.dumps(self.DB))
		THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
			'return_code': 'STOPPED'
		})

	def SetCameraNameHandler(self, sock, packet):
		print("SetCameraNameHandler")
	
	def GetCaptureProgressHandler(self, sock, packet):
		# Find camera
		ret = 0
		for item in self.ObjCameras:
			if (item.GetIp() in packet["payload"]["data"]["ip"]):
				ret = item.GetCapturingProcess()
				break
				
		THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
			'progress': str(ret)
		})

	def SetFaceDetectionHandler(self, sock, packet):
		print("SetFaceDetectionHandler")

	def SetCameraSensetivityHandler(self, sock, packet):
		print("SetCameraSensetivityHandler")
	
	def GetVideosListHandler(self, sock, packet):
		print("GetVideosListHandler")
	
	def GetMiscInformationHandler(self, sock, packet):
		print ("GetMiscInformationHandler")
		dbCameras = self.DB["cameras"]
		for itemCamera in dbCameras:
			if itemCamera["ip"] in packet["payload"]["data"]["ip"]:
				THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
					'frame_per_video': str(itemCamera["frame_per_video"]),
					'camera_sensetivity_recording': str(itemCamera["camera_sensetivity_recording"]),
					'face_detect': str(itemCamera["face_detect"])
				})
				return
		
		THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
			'error': 'bad camera'
		})

	def SetMiscInformationHandler(self, sock, packet):
		print ("SetMiscInformationHandler")
		dbCameras = self.DB["cameras"]
		for itemCamera in dbCameras:
			if itemCamera["ip"] in packet["payload"]["data"]["ip"]:
				itemCamera["frame_per_video"] = packet["payload"]["data"]["frame_per_video"]
				itemCamera["camera_sensetivity_recording"] = packet["payload"]["data"]["camera_sensetivity_recording"]
				itemCamera["face_detect"] = packet["payload"]["data"]["face_detect"]

				self.DB["cameras"] = dbCameras
				# Save new camera to database
				self.Node.SetFileContent("db.json", json.dumps(self.DB))

				for item in self.ObjCameras:
					if (item.GetIp() in packet["payload"]["data"]["ip"]):
						item.SetFramesPerVideo(int(itemCamera["frame_per_video"]))
						item.SetRecordingSensetivity(int(itemCamera["camera_sensetivity_recording"]))
		
				THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
					'error': 'success'
				})
				return
		
		THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
			'error': 'bad camera'
		})
	
	def OnCameraDiffrentHandler(self, ip, image):
		pass
		# logging.info("[OnCameraDiffrentHandler] SECURITY " + str(ip))
		# Find camera object
		# Send SMS via service
	
	# Websockets
	def WSDataArrivedHandler(self, message_type, source, data):
		command = data['device']['command']
		self.Handlers[command](message_type, source, data)

	def WSConnectedHandler(self):
		print ("WSConnectedHandler")

	def WSConnectionClosedHandler(self):
		print ("WSConnectionClosedHandler")

	def NodeSystemLoadedHandler(self):
		print ("NodeSystemLoadedHandler")
		# Loading local database
		jsonSensorStr = self.Node.GetFileContent("db.json")
		if jsonSensorStr != "":
			self.DB = json.loads(jsonSensorStr)
			if self.DB is not None:
				for item in self.DB["cameras"]:
					self.Cameras.append(item)

		# Create file system for storing videos
		if not os.path.exists("/tmp/video_fs"):
			os.mkdir("/tmp/video_fs")
		if not os.path.exists("/tmp/video_fs/videos"):
			os.mkdir("/tmp/video_fs/videos")
		
		# Check if security is ON
		if self.DB["security"] == 1:
			self.SecurityEnabled = True

		# Search for cameras and update local database
		cameras = self.DeviceScanner.Scan("192.168.0.", [1,253])
		HJTScanner = HJTCameraScanner()
		ips = HJTScanner.Scan(cameras)
		# Foreach camera,
		#	1. Get UID and MAC.
		#	2. Check DB if MAC and UID exist, is so save found IP.
		#	3. If camera does not exist, save it.
		dbCameras = self.DB["cameras"]
		for ip in ips:
			camera = HJTCamera(ip)
			mac = camera.GetMACAddress()
			uid = camera.GetUID()
			print ("[Camera Surveillance]>", "NodeSystemLoadedHandler", mac, uid, ip)

			cameraFound = False
			# Update camera IP (if it was changed)
			for itemCamera in dbCameras:
				if uid in itemCamera["uid"] and mac in itemCamera["mac"]:
					# Update DB with current IP
					itemCamera["ip"] = ip
					camera.StartCamera()
					# Check weither need to start recording
					if 1 == itemCamera["recording"]:
						print ("[Camera Surveillance]>", "Start recording", mac, uid, ip)
						camera.StartRecording()
					# If security is ON we need to get frames
					if self.SecurityEnabled is True:
						camera.StartSecurity()
					camera.SetFramesPerVideo(int(itemCamera["frame_per_video"]))
					camera.SetRecordingSensetivity(int(itemCamera["camera_sensetivity_recording"]))
					camera.OnImageDifferentCallback = self.OnCameraDiffrentHandler
					# Add camera to camera obejct DB
					self.ObjCameras.append(camera)
					cameraFound = True
					print ("[Camera Surveillance]>", "NodeSystemLoadedHandler - True")
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
								"recording": 0,
								"face_detect": 0,
								"security": 0,
								"motion_detection": 0
				})
				camera.SetFramesPerVideo(2000)
				camera.SetRecordingSensetivity(95)
				# Add camera to camera obejct DB
				self.ObjCameras.append(camera)
		self.DB["cameras"] = dbCameras
		# Save new camera to database
		self.Node.SetFileContent("db.json", json.dumps(self.DB))
	
	def OnMasterFoundHandler(self, masters):
		print ("OnMasterFoundHandler")

	def OnMasterSearchHandler(self):
		print ("OnMasterSearchHandler")

	def OnMasterDisconnectedHandler(self):
		print ("OnMasterDisconnectedHandler")

	def OnDeviceConnectedHandler(self):
		print ("OnDeviceConnectedHandler")

	def OnLocalServerStartedHandler(self):
		print ("OnLocalServerStartedHandler")

	def OnAceptNewConnectionHandler(self, sock):
		print ("OnAceptNewConnectionHandler")

	def OnTerminateConnectionHandler(self, sock):
		print ("OnTerminateConnectionHandler")

	def OnGetSensorInfoRequestHandler(self, packet, sock):
		print ("OnGetSensorInfoRequestHandler")
		# enabledCameras = [camera for camera in self.Cameras if camera["enable"] == 1] # Comprehension
		# THIS.Node.LocalServiceNode.SendSensorInfoResponse(sock, packet, enabledCameras)
		THIS.Node.LocalServiceNode.SendSensorInfoResponse(sock, packet, self.DB)

	def OnSetSensorInfoRequestHandler(self, packet, sock):
		print ("OnSetSensorInfoRequestHandler")
	
	def OnCustomCommandRequestHandler(self, sock, json_data):
		print ("OnCustomCommandRequestHandler")
		command = json_data['command']
		if command in self.CustomRequestHandlers:
			self.CustomRequestHandlers[command](sock, json_data)

	def OnCustomCommandResponseHandler(self, sock, json_data):
		print ("OnCustomCommandResponseHandler")
		command = json_data['command']
		if command in self.CustomResponseHandlers:
			self.CustomResponseHandlers[command](sock, json_data)

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

	def OnLocalServerListenerStartedHandler(self, sock, ip, port):
		THIS.Node.LocalServiceNode.AppendFaceRestTable(endpoint="/get/node_info/<key>", 						endpoint_name="get_node_info", 			handler=THIS.GetNodeInfoHandler)
		THIS.Node.LocalServiceNode.AppendFaceRestTable(endpoint="/set/node_info/<key>/<id>", 					endpoint_name="set_node_info", 			handler=THIS.SetNodeInfoHandler, 	method=['POST'])
		THIS.Node.LocalServiceNode.AppendFaceRestTable(endpoint="/get/node_sensors_info/<key>", 				endpoint_name="get_node_sensors", 		handler=THIS.GetSensorsInfoHandler)
		THIS.Node.LocalServiceNode.AppendFaceRestTable(endpoint="/set/node_sensor_info/<key>/<id>/<value>", 	endpoint_name="set_node_sensor_value", 	handler=THIS.SetSensorInfoHandler)

	def WorkingHandler(self):
		if time.time() - self.CurrentTimestamp > self.Interval:
			print ("WorkingHandler")

			self.CheckingForUpdate = True
			self.CurrentTimestamp = time.time()

			for idx, item in enumerate(THIS.Node.LocalServiceNode.GetConnections()):
				print ("  ", str(idx), item.LocalType, item.UUID, item.IP, item.Port, item.Type)

Service = MkSSlaveNode.SlaveNode()
Node 	= MkSNode.Node("Camera Surveillance", Service)
THIS 	= Context(Node)

def signal_handler(signal, frame):
	THIS.Node.Stop()

def main():
	signal.signal(signal.SIGINT, signal_handler)
	THIS.Node.SetLocalServerStatus(True)
	
	# Node callbacks
	THIS.Node.OnWSDataArrived 										= THIS.WSDataArrivedHandler
	THIS.Node.OnWSConnected 										= THIS.WSConnectedHandler
	THIS.Node.OnWSConnectionClosed 									= THIS.WSConnectionClosedHandler
	THIS.Node.OnNodeSystemLoaded									= THIS.NodeSystemLoadedHandler
	THIS.Node.OnDeviceConnected										= THIS.OnDeviceConnectedHandler
	# Local service callbacks (TODO - please bubble these callbacks via Node)
	THIS.Node.LocalServiceNode.OnMasterFoundCallback				= THIS.OnMasterFoundHandler
	THIS.Node.LocalServiceNode.OnMasterSearchCallback				= THIS.OnMasterSearchHandler
	THIS.Node.LocalServiceNode.OnMasterDisconnectedCallback			= THIS.OnMasterDisconnectedHandler
	THIS.Node.LocalServiceNode.OnLocalServerStartedCallback			= THIS.OnLocalServerStartedHandler
	THIS.Node.LocalServiceNode.OnLocalServerListenerStartedCallback = THIS.OnLocalServerListenerStartedHandler
	THIS.Node.LocalServiceNode.OnAceptNewConnectionCallback			= THIS.OnAceptNewConnectionHandler
	THIS.Node.LocalServiceNode.OnTerminateConnectionCallback 		= THIS.OnTerminateConnectionHandler
	THIS.Node.LocalServiceNode.OnGetSensorInfoRequestCallback 		= THIS.OnGetSensorInfoRequestHandler
	THIS.Node.LocalServiceNode.OnSetSensorInfoRequestCallback 		= THIS.OnSetSensorInfoRequestHandler
	# TODO - On file upload event.
	THIS.Node.LocalServiceNode.OnCustomCommandRequestCallback		= THIS.OnCustomCommandRequestHandler
	THIS.Node.LocalServiceNode.OnCustomCommandResponseCallback		= THIS.OnCustomCommandResponseHandler
	
	THIS.Node.Run(THIS.WorkingHandler)
	print ("Exit Node ...")

if __name__ == "__main__":
    main()
