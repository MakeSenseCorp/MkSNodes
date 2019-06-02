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

from mksdk import MkSFile
from mksdk import MkSNode
from mksdk import MkSSlaveNode
from mksdk import MkSLocalHWConnector
from mksdk import MkSUSBAdaptor
from mksdk import MkSProtocol

from flask import Response, request

class ICamera():
	def __init__(self, ip):
		self.IPAddress 			= ip
		self.Address 			= "http://" + self.IPAddress + "/"
		self.IsRecoding 		= False
		self.ImagesPath 		= "images"
		self.videosPath 		= "videos"
		self.FramesPerVideo 	= 60 * 15
		self.CurrentImageIndex 	= 0 # Can be 0 or 1

	def GetRequest (self, url):
		username = 'admin'
		password = 'admin'

		# print ("[Camera Surveillance]>", "GetRequest Enter", url)

		p = urllib2.HTTPPasswordMgrWithDefaultRealm()
		p.add_password(None, url, username, password)

		handler = urllib2.HTTPBasicAuthHandler(p)
		opener = urllib2.build_opener(handler)
		urllib2.install_opener(opener)
		data = urllib2.urlopen(url).read()

		# print ("[Camera Surveillance]>", "GetRequest Exit", data)

		return data

	def Frame(self):
		command = self.GetFrame()
		return self.GetRequest(self.Address + command)

	def StartRecording(self):
		thread.start_new_thread(self.RecordingThread, ())

	def StopRecording(self):
		self.IsRecoding = False

	def MakeVideoThread(self, index):
		call(["bash", "make_video.sh", str(index)])
		return True

	def RecordingThread(self):
		record_ticker = 0;
		while self.IsRecoding is True:
			frame = self.Frame()
			file = open("videos_fs/images/" + str(self.CurrentImageIndex) + "/" + str(time.time()) + ".jpg", "w")
			file.write(frame)
			file.close()
			record_ticker += 1
			time.sleep(1)

			if self.FramesPerVideo == record_ticker:
				# Switch to second buffer and prepare video
				thread.start_new_thread(self.RecordingThread, (self.CurrentImageIndex,))
				self.CurrentImageIndex = 1 - self.CurrentImageIndex
				record_ticker = 0

class HJTCamera(ICamera):
	def __init__(self, ip):
		ICamera.__init__(self, ip)
		self.Commands = {
			'frame': 			"tmpfs/auto.jpg",
			'getnetattr': 		"web/cgi-bin/hi3510/param.cgi?cmd=getnetattr",
			'getserverinfo': 	"web/cgi-bin/hi3510/param.cgi?cmd=getserverinfo",
			'getxqp2pattr': 	"web/cgi-bin/hi3510/param.cgi?cmd=getxqp2pattr"
		}

	def GetAPIName(self):
		return "hjt-ipc6100-b1w"

	def GetFrame(self):
		return self.Commands['frame']

	def GetUID(self):
		data = self.GetRequest(self.Address + self.Commands['getxqp2pattr'])
		items = data.split("\r\n")
		for item in items:
			if "xqp2p_uid" in item:
				uid = item.split('\"')
				return uid[1]
		return 0

	def GetMACAddress(self):
		data = self.GetRequest(self.Address + self.Commands['getnetattr'])
		# Find MAC address from recieved string
		p = re.compile(ur'(?:[0-9a-fA-F]:?){12}')
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
			'start_recording': 			self.StartRecordingHandler,
			'stop_recording': 			self.StopRecordingHandler,
			'start_motion_detection': 	self.StartMotionDetectionHandler,
			'stop_motion_detection': 	self.StopMotionDetectionHandler,
			'start_security': 			self.StartSecurityHandler,
			'stop_security': 			self.StopSecurityHandler,
			'set_camera_name': 			self.SetCameraNameHandler,
		}
		self.CustomResponseHandlers				= {
		}

		self.Cameras 					= []

	# TODO - Should be part of MKSDK
	def OpenURL(self, url):
		try: 
			response = urllib2.urlopen(url).read()
		except urllib2.HTTPError, e:
			if 401 == e.code:
				return True
		except urllib2.URLError, e:
			pass
			# print "URLError", e
		except httplib.HTTPException, e:
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
			print "Scanning ", IPAddress
			res = self.Ping(IPAddress)
			if True == res:
				print "Device found, ", IPAddress
				res = self.OpenURL("http://" + IPAddress)
				if True == res:
					print "Camera found, ", IPAddress
					itemsFound.append(IPAddress)
		return itemsFound
    
	def UndefindHandler(self, message_type, source, data):
		print ("UndefindHandler")

	# CustomRequestHandlers
	def StartRecordingHandler(self, sock, packet):
		print("StartRecordingHandler")

	def StopRecordingHandler(self, sock, packet):
		print("StopRecordingHandler")

	def StartMotionDetectionHandler(self, sock, packet):
		print("StartMotionDetectionHandler")

	def StopMotionDetectionHandler(self, sock, packet):
		print("StopMotionDetectionHandler")

	def StartSecurityHandler(self, sock, packet):
		print("StartSecurityHandler")

	def StopSecurityHandler(self, sock, packet):
		print("StopSecurityHandler")

	def SetCameraNameHandler(self, sock, packet):
		print("SetCameraNameHandler")

	# Websockets
	def WSDataArrivedHandler(self, message_type, source, data):
		command = data['device']['command']
		self.Handlers[command](message_type, source, data)

	def WSConnectedHandler(self):
		print "WSConnectedHandler"

	def WSConnectionClosedHandler(self):
		print "WSConnectionClosedHandler"

	def NodeSystemLoadedHandler(self):
		print "NodeSystemLoadedHandler"
		# Loading local database
		jsonSensorStr = self.Node.GetFileContent("db.json")
		if jsonSensorStr != "":
			data = json.loads(jsonSensorStr)
			if data is not None:
				for item in data["cameras"]:
					self.Cameras.append(item)

		# Search for cameras and update local database
		# ips = self.Scan()
		ips = ["10.0.0.20"]
		for ip in ips:
			camera = HJTCamera(ip)
			mac = camera.GetMACAddress()
			print ("[Camera Surveillance]>", "NodeSystemLoadedHandler", mac)
			# Search for this MAC address in local database
			found = False
			for item in self.Cameras:
				if mac in item["mac"]:
					found = True
					break
			# print ("[Camera Surveillance]>", "NodeSystemLoadedHandler", found)
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
		print "OnMasterFoundHandler"

	def OnMasterSearchHandler(self):
		print "OnMasterSearchHandler"

	def OnMasterDisconnectedHandler(self):
		print "OnMasterDisconnectedHandler"

	def OnDeviceConnectedHandler(self):
		print "OnDeviceConnectedHandler"

	def OnLocalServerStartedHandler(self):
		print "OnLocalServerStartedHandler"

	def OnAceptNewConnectionHandler(self, sock):
		print "OnAceptNewConnectionHandler"

	def OnTerminateConnectionHandler(self, sock):
		print "OnTerminateConnectionHandler"

	def OnGetSensorInfoRequestHandler(self, packet, sock):
		print "OnGetSensorInfoRequestHandler"

	def OnSetSensorInfoRequestHandler(self, packet, sock):
		print "OnSetSensorInfoRequestHandler"
	
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
			print "WorkingHandler"

			self.CheckingForUpdate = True
			self.CurrentTimestamp = time.time()

			for idx, item in enumerate(THIS.Node.LocalServiceNode.GetConnections()):
				print "  ", str(idx), item.LocalType, item.UUID, item.IP, item.Port, item.Type

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
	print "Exit Node ..."

if __name__ == "__main__":
    main()
