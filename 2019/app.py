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
			'options':					self.OptionsHandler
			'undefined':				self.UndefindHandler
		}
		self.ResponseHandlers		= {
			'undefined':				self.UndefindHandler
		}
		# Application variables
		self.DB							= None
		self.Cameras 					= []
		self.ObjCameras					= []
		self.USBDevices 				= []
		self.USBDevice 					= None

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
				"camera_sensetivity_recording": 95,
				"camera_sensetivity_security": 95,
				"status": "connected",
				"high_diff": 5000,
				"seconds_per_frame": 1, 
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

		# Get USB device
		self.USBDevice = self.DB["usb_device"]

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
								'fps': str(camera.GetFPS()),
								'usb_device': self.USBDevice,
								'usb_devices': self.USBDevices,
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
