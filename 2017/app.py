#!/usr/bin/python
import os
import sys
import signal
import json
import time
import thread
import threading

import subprocess
import urllib2
import urllib
import re
from subprocess import call
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
		thread.start_new_thread(self.OrdersManagerThread, ())
	
	def AddOrder(self, order):
		self.Orders.put(order)
		self.IsRunning = True

	def OrdersManagerThread(self):
		while (self.IsRunning is True):
			item = self.Orders.get(block=True,timeout=None)
			print (item)
			print ("[VideoCreator] Start video encoding...", str(item["path"]), str(item["index"]))
			call(["bash", "make_video.sh", str(item["index"])])
			print ("[VideoCreator] Start video encoding... DONE", str(item["path"]), str(item["index"]))

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
		self.ImP				= MkSImageProcessing()
		self.IPAddress 			= ip
		self.Address 			= "http://" + self.IPAddress + "/"
		self.IsRecoding 		= False
		self.ImagesPath 		= "images"
		self.videosPath 		= "videos"
		self.FramesPerVideo 	= 60 * 10
		self.CurrentImageIndex 	= 0

	def GetRequest (self, url):
		username = 'admin'
		password = 'admin'

		# print ("[Camera Surveillance]>", "GetRequest Enter", url)
		
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

		# print ("[Camera Surveillance]>", "GetRequest Exit", data)

		return data, False

	def GetCapturingProcess(self):
		return int((float(self.CurrentImageIndex / self.FramesPerVideo)) * 100)

	def Frame(self):
		command = self.GetFrame()
		frame, error = self.GetRequest(self.Address + command)
		return frame

	def StartRecording(self):
		if (self.IsRecoding is False):
			thread.start_new_thread(self.RecordingThread, ())

	def StopRecording(self):
		print ("[Camera] Stop recording", self.IPAddress)
		self.IsRecoding = False

	def RecordingThread(self):
		global GEncoder
		# TODO - Create folder path if there are none
		record_ticker = 0
		
		frameCurr = None
		framePrev = None

		# Count items in images folders 0 and 1
		# TODO - Each camera has its own folder
		#directory = "/tmp/video_fs/images/0"
		#imagesZero 	= len([name for name in os.listdir(directory) if os.path.isfile(os.path.join(directory, name))])
		#directory = "/tmp/video_fs/images/1"
		#imagesOne 	= len([name for name in os.listdir(directory) if os.path.isfile(os.path.join(directory, name))])

		# TODO - Percentage of threshhold should be managable from UI
		# TODO - Update record_ticker according to images in folder
		# TODO - Is video creation is on going?

		print ("[Camera] Start recording", self.IPAddress)
		self.IsRecoding = True
		indexer = 0
		while self.IsRecoding is True:
			frameCurr = self.Frame()
			diff = self.ImP.CompareJpegImages(frameCurr, framePrev)

			# print ("[Camera]", self.IPAddress, "Get frame", record_ticker, "Diff", diff)
			if (diff < 95.0):
				# TODO - Work with relative path or check "pwd"
				file = open("/tmp/video_fs/images/" + str(self.CurrentImageIndex) + "/" + str(record_ticker) + ".jpg", "w")
				file.write(frameCurr)
				file.close()
				print ("[Camera] Save frame", str(self.CurrentImageIndex), record_ticker)
				record_ticker += 1
				framePrev = frameCurr
			
			if self.FramesPerVideo <= record_ticker:
				GEncoder.AddOrder({
					'path': "/tmp/video_fs/images/" + str(self.CurrentImageIndex),
					'index': str(self.CurrentImageIndex)
				})
				# Switch to second buffer and prepare video
				# thread.start_new_thread(self.MakeVideoThread, (self.CurrentImageIndex,))
				# self.CurrentImageIndex = 1 - self.CurrentImageIndex
				indexer += 1
				self.CurrentImageIndex = indexer % 10
				record_ticker = 0
			
			#time.sleep(0.5)

class HJTCamera(ICamera):
	def __init__(self, ip):
		ICamera.__init__(self, ip)
		self.Commands = {
			'frame': 			"tmpfs/auto.jpg",
			'getnetattr': 		"web/cgi-bin/hi3510/param.cgi?cmd=getnetattr",
			'getserverinfo': 	"web/cgi-bin/hi3510/param.cgi?cmd=getserverinfo",
			'getxqp2pattr': 	"web/cgi-bin/hi3510/param.cgi?cmd=getxqp2pattr"
		}

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
		}
		self.CustomResponseHandlers				= {
		}

		self.DB							= None
		self.Cameras 					= []
		self.ObjCameras					= []
		self.DeviceScanner 				= EthernetDeviceScanner()

	# TODO - Should be part of MKSDK
	def OpenURL(self, url):
		try: 
			response = urllib2.urlopen(url).read()
		except urllib2.HTTPError as e:
			if 401 == e.code:
				return True
		except urllib2.URLError as e:
			pass
			# print "URLError", e
		except httplib.HTTPException as e:
			pass
			# print "HTTPException", e
		
		return False

	# TODO - Should be part of MKSDK
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

	def Scan(self):
		IPAddressPrefix = "10.0.0."
		itemsFound = []
		for i in range(1, 16):
			IPAddress = IPAddressPrefix + str(i)
			print ("Scanning ", IPAddress)
			res = self.Ping(IPAddress)
			if True == res:
				print ("Device found, ", IPAddress)
				res = self.OpenURL("http://" + IPAddress)
				if True == res:
					print ("Camera found, ", IPAddress)
					itemsFound.append(IPAddress)
		return itemsFound
    
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
		cameras = self.DB["cameras"]
		for item in cameras:
			if (item["ip"] in packet["payload"]["data"]["ip"]):
				item["security"] = 1
				self.Node.SetFileContent("db.json", json.dumps(self.DB))
		THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
			'return_code': 'STARTED'
		})

	def StopSecurityHandler(self, sock, packet):
		print("StopSecurityHandler")
		cameras = self.DB["cameras"]
		for item in cameras:
			if (item["ip"] in packet["payload"]["data"]["ip"]):
				item["security"] = 0
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
				# TODO - Each camera must have its own directory
				ret = item.GetCapturingProcess()
				
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
		print ("GetFramesCountToVideoCreationHandler")

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

		if not os.path.exists("/tmp/video_fs"):
			os.mkdir("/tmp/video_fs")
		if not os.path.exists("/tmp/video_fs/videos"):
			os.mkdir("/tmp/video_fs/videos")
		if not os.path.exists("/tmp/video_fs/images"):
			os.mkdir("/tmp/video_fs/images")
		for i in range(0,10):
			if not os.path.exists("/tmp/video_fs/images/" + str(i)):
				os.mkdir("/tmp/video_fs/images/" + str(i))

		# Search for cameras and update local database
		cameras = self.DeviceScanner.Scan("192.168.0.", [1,253])
		HJTScanner = HJTCameraScanner()
		ips = HJTScanner.Scan(cameras)
		for ip in ips:
			camera = HJTCamera(ip)
			self.ObjCameras.append(camera)
			mac = camera.GetMACAddress()
			for item in self.Cameras:
				if ip in item["ip"] and 1 == item["recording"]:
					camera.StartRecording()
					break
			print ("[Camera Surveillance]>", "NodeSystemLoadedHandler", mac)
			# Search for this MAC address in local database
			found = False
			for item in self.Cameras:
				if mac in item["mac"]:
					found = True
					break
			# print ("[Camera Surveillance]>", "NodeSystemLoadedHandler", found)
			# TODO - Make it work
			break
			if found is False:
				# New camera found
				uid = camera.GetUID()
				self.Cameras.append({
								'mac': str(mac),
								'uid': str(uid),
								'ip': str(ip),
								'name': 'Camera_' + str(uid),
								'enable':1 
				})
				# Save new camera to database
				self.Node.SetFileContent("db.json", json.dumps({
								'cameras': self.Cameras
				}))
	
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
		enabledCameras = [camera for camera in self.Cameras if camera["enable"] == 1] # Comprehension
		THIS.Node.LocalServiceNode.SendSensorInfoResponse(sock, packet, enabledCameras)

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
