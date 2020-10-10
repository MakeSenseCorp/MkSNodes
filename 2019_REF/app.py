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
from subprocess import Popen, PIPE
import Queue

import numpy as np
from PIL import Image
from PIL import ImageFilter
from io import BytesIO

import base64

from mksdk import MkSFile
from mksdk import MkSSlaveNode
from mksdk import MkSShellExecutor
from mksdk import MkSUVCCamera

from flask import Response, request
from flask import send_file

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

		self.LastTSEmailSent			= 0
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
			if (item.UID in payload["uid"]):
				frame, error = item.Frame()
				if error is False:
					return THIS.Node.BasicProtocol.BuildResponse(packet, {
									'uid': item.UID,
									'dev': item.DevicePath.split('/')[-1],
									'frame': base64.encodestring(frame)
					})

		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'return_code': 'no_frame'
		})

	def StartRecordingHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		# Find camera
		for obj_camera in self.ObjCameras:
			if (obj_camera.UID in payload["uid"]):
				# TODO - Each camera must have its own directory
				obj_camera.StartRecording()
				cameras = self.DB["cameras"]
				for camera in cameras:
					if (camera["uid"] in payload["uid"]):
						camera["recording"] = 1
						self.File.Save("db.json", json.dumps(self.DB))

		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'return_code': 'STARTED'
		})

	def StopRecordingHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		# Find camera
		for obj_camera in self.ObjCameras:
			if (obj_camera.UID in payload["uid"]):
				# TODO - Each camera must have its own directory
				obj_camera.StopRecording()
				cameras = self.DB["cameras"]
				for camera in cameras:
					if (camera["uid"] in payload["uid"]):
						camera["recording"] = 0
						self.File.Save("db.json", json.dumps(self.DB))
		
		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'return_code': 'STOPPED'
		})

	def StartMotionDetectionHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		cameras = self.DB["cameras"]
		for camera in cameras:
			if (camera["uid"] in payload["uid"]):
				camera["motion_detection"] = 1
				self.File.Save("db.json", json.dumps(self.DB))
		
		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'return_code': 'STARTED'
		})

	def StopMotionDetectionHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		cameras = self.DB["cameras"]
		for camera in cameras:
			if (camera["uid"] in payload["uid"]):
				camera["motion_detection"] = 0
				self.File.Save("db.json", json.dumps(self.DB))

		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'return_code': 'STOPPED'
		})

	def StartSecurityHandler(self, sock, packet):
		self.DB["security"] = 1
		self.SecurityEnabled = True
		cameras = self.DB["cameras"]
		devices = []
		for camera in cameras:
			camera["security"]			= 1
			camera["motion_detection"] 	= 1
			devices.append(camera["dev"])
		self.DB["cameras"] = cameras
		for obj_camera in self.ObjCameras:
			obj_camera.StartSecurity()
		self.File.Save("db.json", json.dumps(self.DB))

		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'return_code': 'STARTED',
			'devices': devices
		})

	def StopSecurityHandler(self, sock, packet):
		self.DB["security"] = 0
		self.SecurityEnabled = False
		cameras = self.DB["cameras"]
		devices = []
		for camera in cameras:
			camera["security"]  		= 0
			camera["motion_detection"] 	= 0
			devices.append(camera["dev"])
		for obj_camera in self.ObjCameras:
			obj_camera.StopSecurity()
		self.DB["cameras"] = cameras
		self.File.Save("db.json", json.dumps(self.DB))

		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'return_code': 'STOPPED',
			'devices': devices
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
		shell = MkSShellExecutor.ShellExecutor()
		# Get all video devices
		data = shell.ExecuteCommand("ls /dev/video*")
		devices = data.split("\n")[:-1]
		return devices
	
	def UpdateCameraStracture(self, dbCameras, dev_path):
		cameradb 		= None
		camera 			= MkSUVCCamera.UVCCamera(dev_path)
		camera_drv_name	= camera.CameraDriverName
		cameraFound 	= False

		# Update camera path (if it was changed)
		for itemCamera in dbCameras:
			# Invalid driver name
			if camera_drv_name == "":
				print ("({classname})# Found path is not valid camera".format(classname=self.ClassName))
				return
			else:
				# Is camera exist in DB
				if camera_drv_name in itemCamera["driver_name"]:
					cameraFound = True
					cameradb 	= itemCamera
					break
		
		if cameraFound is True:
			cameradb["dev"] 	= dev_path.split('/')[-1]
			cameradb["path"] 	= dev_path
			camera.SetFramesPerVideo(int(cameradb["frame_per_video"]))
			camera.SetRecordingSensetivity(int(cameradb["camera_sensetivity_recording"]))
			camera.SetSecuritySensetivity(int(cameradb["camera_sensetivity_security"]))
			camera.SetHighDiff(int(cameradb["high_diff"]))
			camera.SetSecondsPerFrame(float(cameradb["seconds_per_frame"]))
		else:
			print ("({classname})# New camera... Adding to the database...".format(classname=self.ClassName))
			cameradb = {
				'uid': camera.UID,
				'name': 'Camera_' + camera.UID,
				'dev': dev_path.split('/')[-1],
				'path': dev_path,
				'driver_name': camera_drv_name,
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
		camera.OnFrameChangeHandler = self.OnFrameChangeCallback
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
		print ("OnGetNodesListHandler", uuids)

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
	
	def OnFrameChangeCallback(self, data):
		THIS.Node.EmitOnNodeChange(data)

Node = MkSSlaveNode.SlaveNode()
THIS = Context(Node)

def signal_handler(signal, frame):
	THIS.Node.Stop("Accepted signal from other app")

def main():
	signal.signal(signal.SIGINT, signal_handler)
	THIS.Node.SetLocalServerStatus(True)
	
	# Node callbacks
	THIS.Node.NodeSystemLoadedCallback				= THIS.NodeSystemLoadedHandler
	# THIS.Node.OnLocalServerListenerStartedCallback 	= THIS.OnLocalServerListenerStartedHandler
	THIS.Node.OnApplicationRequestCallback			= THIS.OnApplicationCommandRequestHandler
	THIS.Node.OnApplicationResponseCallback			= THIS.OnApplicationCommandResponseHandler
	THIS.Node.OnGetNodesListCallback				= THIS.OnGetNodesListHandler
	THIS.Node.OnGetNodeInfoCallback					= THIS.OnGetNodeInfoHandler
	# Stream sockets events
	THIS.Node.OnStreamSocketCreatedEvent 			= THIS.OnStreamSocketCreatedHandler
	THIS.Node.OnStreamSocketDataEvent 				= THIS.OnStreamSocketDataHandler
	THIS.Node.OnStreamSocketDisconnectedEvent		= THIS.OnStreamSocketDisconnectedHandler
	
	THIS.Node.Run(THIS.WorkingHandler)
	THIS.Node.LogMSG("({classname})# Exit node.".format(classname=THIS.Node.ClassName),5)

if __name__ == "__main__":
    main()
