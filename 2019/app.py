#!/usr/bin/python
import os
import sys
import signal
import json
import time
import thread
import threading
import base64

from mksdk import MkSFile
from mksdk import MkSSlaveNode
from mksdk import MkSShellExecutor
from mksdk import MkSUVCCamera
from mksdk import MkSScheduling

'''
BUG LIST:
---------

TASK LIST:
---------
#1
	a. Add resolution selection.
	b. Add quality selection.
#2
	State machine for MKSDK.
'''

class BasicSMThreadless():
	def __init__(self):
		self.ClassName		= "BasicSMThreadless"

class FolderMonitorThreadless():
	def __init__(self, path, search_fn):
		self.ClassName					= "FolderMonitorThreadless"
		self.Path 						= path
		self.Items 						= []
		self.SearchHandler 				= search_fn
	
	def SetPath(self, path):
		self.Path = path
	
	def GetItemsList(self):
		return self.Items

	def GetItems(self):
		return self.SearchHandler(self.Path)

	def GetItemsCompare(self):
		ret_items = []
		items = self.GetItems()
		if len(self.Items) == 0:
			for item in items:
				ret_items.append({
					"item": item,
					"status": "append"
				})
			self.Items = items
			return ret_items, (len(ret_items) > 0)
		else:
			# Find removed items
			for item in self.Items:
				if item not in items:
					ret_items.append({
						"item": item,
						"status": "remove"
					})
					self.Items.remove(item)
			# Find appended items
			for item in items:
				if item not in self.Items:
					ret_items.append({
						"item": item,
						"status": "append"
					})
					self.Items.append(item)
		return ret_items, (len(ret_items) > 0)

class Context():
	def __init__(self, node):
		self.ClassName					= "Apllication"
		self.Timer 						= MkSScheduling.TimeSchedulerThreadless()
		self.Node						= node
		self.File 						= MkSFile.File()
		self.CameraSearcher 			= FolderMonitorThreadless("/dev", self.FolderMonitorOperator)
		self.Streams 					= {}
		# States
		self.States = {
		}
		# Handlers
		self.RequestHandlers		= {
			'get_sensor_info':			self.GetSensorInfoHandler,
			'operations':				self.OperationsHandler,
			'get_frame':				self.GetFrameHandler,
			'delete_camera_from_db':	self.DeleteCameraFromDBHandler,
			'undefined':				self.UndefindHandler
		}
		self.ResponseHandlers		= {
			'undefined':				self.UndefindHandler
		}
		# Application variables
		self.DB							= None
		self.ObjCameras					= []

		self.Timer.AddTimeItem(10, self.PrintConnections)
		self.Timer.AddTimeItem(10, self.SearchForCameras)

	def UndefindHandler(self, sock, packet):
		print ("UndefindHandler")

	def GetSensorInfoHandler(self, sock, packet):
		print ("({classname})# GetSensorInfoHandler ...".format(classname=self.ClassName))
		payload = {
			'cameras': self.DB["cameras"]
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
									'meta': {
										'uid': item.UID,
										"device_path": item.DevicePath,
										"fps": str(item.FPS),
										"sensetivity": item.Sensetivity
									},
									'frame': base64.encodestring(frame)
					})

		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'return_code': 'no_frame'
		})
	
	def OperationsHandler(self, sock, packet):
		self.Node.LogMSG("({classname})# [OperationsHandler]".format(classname=self.ClassName),5)
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)

		self.Node.LogMSG("({classname})# [OperationsHandler] {0}".format(payload,classname=self.ClassName),5)

		if "index" in payload and "subindex" in payload:
			index 		= payload["index"]
			subindex  	= payload["subindex"]
			direction 	= payload["direction"]
			data 		= {}
			if index == 0x1000: # CAMERA
				# Node details request
				if subindex >= 0 and subindex <= 10:
					if 0x0 == subindex:
						# PING
						self.Node.LogMSG("({classname})# [OperationsHandler] subindex PING".format(classname=self.ClassName),5)
						data = {
							'return_code': 'ok'
						}
					elif 0x1 == subindex:
						# INFO
						self.Node.LogMSG("({classname})# [OperationsHandler] subindex INFO".format(classname=self.ClassName),5)
						cameras = []
						for camera in self.DB["cameras"]:
							cameras.append({
								"uid": camera["uid"],
								"fps": camera["user_fps"],
								"sensetivity": camera["sensetivity"],
								"enable": camera["enable"],
								"status": camera["status"]
							})
						data = {
							'cameras': cameras,
							'node': self.Node.NodeInfo,
							'local_connection': {
								'ip': 	self.Node.MyLocalIP,
								'port': self.Node.SlaveListenerPort
							}
						}
				else:
					# Detailed camera request
					camera = None
					data = payload["data"]
					for item in self.ObjCameras:
						if item.UID == data["uid"]:
							camera = item
							break

					if camera is not None:
						if 0x11 == subindex:
							# GETFRAME
							pass
						elif 0x12 == subindex:
							# CAMERAINFO
							pass
						elif 0x13 == subindex:
							# FPS
							if direction:
								# SET
								camera.SetFPS(int(data["value"]))
								camera.SetSecondsPerFrame(1.0 / float(data["value"]))
								self.UpdateCamerDB(data["uid"], "user_fps", int(data["value"]))
								self.UpdateCamerDB(data["uid"], "seconds_between_frame", 1.0 / float(data["value"]))
							else:
								# GET
								pass
						if 0x14 == subindex:
							# SENSETIVITY
							if direction:
								# SET
								camera.SetSensetivity(int(data["value"]))
								self.UpdateCamerDB(data["uid"], "sensetivity", int(data["value"]))
							else:
								# GET
								pass
						if 0x15 == subindex:
							# RESOLUTION
							if direction:
								# SET
								pass
							else:
								# GET
								pass
						if 0x16 == subindex:
							# QUALITY
							if direction:
								# SET
								pass
							else:
								# GET
								pass
						else:
							pass
				
				return THIS.Node.BasicProtocol.BuildResponse(packet, {
					"index": 	 index,
					"subindex":	 subindex,
					"direction": direction,
					"data": data
				})
		
			return THIS.Node.BasicProtocol.BuildResponse(packet, {
				"index": 	 index,
				"subindex":	 subindex,
				"direction": direction,
				"data": {
					'return_code': 'fail'
				}
			})
		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'error': 'fail'
		})
	
	def DeleteCameraFromDBHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		uid = payload["uid"]

		self.Node.LogMSG("({classname})# [DeleteCameraFromDBHandler] {0}".format(uid,classname=self.ClassName),5)
		db_camera = self.DB["cameras"]
		camera = None
		for item in db_camera:
			if uid in item["uid"]:
				camera = item
				break
		if camera is not None:
			# Stop and delete camera
			# Delete from JSON file
			db_camera.remove(camera)
			self.DB["cameras"] = db_camera
			# Save new camera to database
			objFile = MkSFile.File()
			objFile.SaveJSON("db.json", self.DB)
			# Emit to registered UIs
			THIS.Node.EmitOnNodeChange({
				'index': 		0x1000,
				'subindex': 	0x23,
				'direction':	0x1,
				'data': {
					'uid': uid
				}
			})
			# Send response
			return THIS.Node.BasicProtocol.BuildResponse(packet, {
				'return_code': 'ok'
			})
		# Send response
		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'return_code': 'failed'
		})

	def UpdateCamerDB(self, uid, name, value):
		db_camera = self.DB["cameras"]
		for camera in db_camera:
			if uid == camera["uid"]:
				camera[name] = value
				self.DB["cameras"] = db_camera
				# Save new camera to database
				objFile = MkSFile.File()
				objFile.SaveJSON("db.json", self.DB)
				break
		
	def RemoveCamera(self, uid):
		self.UpdateCamerDB(uid, "enable", 0)
		self.UpdateCamerDB(uid, "status", "Disconnected")

		camera = None
		for item in self.ObjCameras:
			if item.UID == uid:
				camera = item
				break
		if camera is not None:
			self.ObjCameras.remove(camera)
	
	def OnStreamSocketCreatedHandler(self, name, identity):
		self.Node.LogMSG("({classname})# [OnStreamSocketCreatedHandler] {0} {1}".format(name,str(identity),classname=self.ClassName),5)
		self.Streams[identity] = {
			"name": name
		}

	def OnStreamSocketDataHandler(self, name, identity, data):
		self.Node.LogMSG("({classname})# [OnStreamSocketDataHandler] {0} {1}".format(name,data,classname=self.ClassName),5)
	
	def OnStreamSocketDisconnectedHandler(self, name, identity):
		self.Node.LogMSG("({classname})# [OnStreamSocketDisconnectedHandler] {0} {1}".format(name,str(identity),classname=self.ClassName),5)

	def OnGetNodeInfoHandler(self, info):
		self.Node.LogMSG("({classname})# [OnGetNodeInfoHandler] [{0}, {1}, {2}]".format(info["uuid"],info["name"],info["type"],classname=self.ClassName),5)

	def FolderMonitorOperator(self, path):
		files = self.File.ListAllInFolder(path)
		# Get all video devices
		return ["/dev/{0}".format(cam) for cam in files if "video" in cam]
	
	def UpdateCameraStracture(self, db_camera, dev_path):
		camera_db 		= None
		camera 			= MkSUVCCamera.UVCCamera(dev_path)
		camera_drv_name	= camera.CameraDriverName
		camera_found 	= False

		# Update camera path (if it was changed)
		for item in db_camera:
			# Invalid driver name
			if camera_drv_name == "":
				self.Node.LogMSG("({classname})# Found path is not valid camera {0}".format(camera_drv_name,classname=self.ClassName),5)
				return
			else:
				# Is camera exist in DB
				if camera_drv_name in item["driver_name"]:
					camera_found = True
					camera_db 	 = item
					break
		
		if camera_found is True:
			camera_db["dev"] 	= dev_path.split('/')[-1]
			camera_db["path"] 	= dev_path
			camera.SetHighDiff(int(camera_db["high_diff"]))
			camera.SetSecondsPerFrame(float(camera_db["seconds_between_frame"]))
			camera.SetSensetivity(int(camera_db["sensetivity"]))
			camera.SetFPS(int(camera_db["user_fps"]))
		else:
			self.Node.LogMSG("({classname})# New camera... Adding to the database... {0}".format(camera_drv_name,classname=self.ClassName),5)
			camera_db = {
				'uid': camera.UID,
				'name': 'Camera_' + camera.UID,
				'dev': dev_path.split('/')[-1],
				'path': dev_path,
				'driver_name': camera_drv_name,
				'enable':1,
				"sensetivity": 95,
				"status": "Disconnected",
				"high_diff": 5000,
				"seconds_between_frame": 1,
				"user_fps": 1
			}
			# Append new camera.
			db_camera.append(camera_db)
			camera.SetSensetivity(95)
			camera.SetHighDiff(5000)
			camera.SetSecondsPerFrame(1)
			# Add camera to camera obejct DB
			self.ObjCameras.append(camera)
			camera_db["enable"] = 1
		
		# Start camera thread
		camera.OnFrameChangeCallback = self.OnFrameChangeHandler
		camera.OnCameraFailCallback = self.OnCameraFailHandler
		camera.Start()
		
		# Update camera object with values from database
		camera.Name = camera_db["name"]
		camera_db["enable"] = 1
		camera_db["status"] = "Connected"
		# Add camera to camera obejct DB
		self.ObjCameras.append(camera)
			
		self.Node.LogMSG("({classname})# Emit camera_connected {dev}".format(dev=camera_db["dev"],classname=self.ClassName),5)
		THIS.Node.EmitOnNodeChange({
			'index': 		0x1000,
			'subindex': 	0x21,
			'direction':	0x1,
			'data': {
				'camera': camera_db
			}
		})

	def NodeSystemLoadedHandler(self):
		self.Node.LogMSG("({classname})# Loading system ...".format(classname=self.ClassName),5)
		objFile = MkSFile.File()
		# Loading local database
		# TODO - Check if file exist, if not create with default structure
		db_str = objFile.Load("db.json")
		if db_str != "":
			self.DB = json.loads(db_str)
		
		'''
		1. Check if USB device available.
			- If not availabale, set flag ('can_not_record') cannot record.
			- If available, continue as expected.
			- Note, camera will store frames into buffer 
			  but want save to file until device will be available.
		'''

		# Search for cameras
		self.Node.LogMSG("({classname})# Searching for cameras ...".format(classname=self.ClassName),5)
		# Initiate state of comparator
		self.CameraSearcher.GetItemsCompare()
		paths = self.FolderMonitorOperator("/dev")
		# Get ipscameras from db
		db_camera = self.DB["cameras"]
		# Disable all cameras
		for camera in db_camera:
			camera["enable"] = 0
		# Check all connected cameras and update db
		self.Node.LogMSG("({classname})# Updating cameras database ...".format(classname=self.ClassName),5)
		for path in paths:
			self.UpdateCameraStracture(db_camera, path)
		
		self.DB["cameras"] = db_camera
		# Save new camera to database
		objFile.SaveJSON("db.json", self.DB)
		self.Node.LogMSG("({classname})# Loading system ... DONE.".format(classname=self.ClassName),5)
	
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

	def PrintConnections(self):
		self.Node.LogMSG("\nTables:",5)
		connections = THIS.Node.GetConnectedNodes()
		for idx, key in enumerate(connections):
			node = connections[key]
			self.Node.LogMSG("  {0}\t{1}\t{2}\t{3}\t{4}\t{5}\t{6}\t{7}".format(str(idx),node.Obj["local_type"],node.Obj["uuid"],node.IP,node.Obj["listener_port"],node.Obj["type"],node.Obj["pid"],node.Obj["name"]),5)
		self.Node.LogMSG("",5)
	
	def SearchForCameras(self):
		# Search for change
		items, is_change = self.CameraSearcher.GetItemsCompare()
		if is_change is True:
			for item in items:
				if item["status"] == "append":
					# Update camera structure
					self.UpdateCameraStracture(self.DB["cameras"], item["item"])
				elif item["status"] == "remove":
					# Update camera structure
					pass
		self.Node.LogMSG("({classname})# Search {0} {1}".format(items, is_change, classname=self.ClassName),5)
	
	def OnNodeWorkTick(self):
		self.Timer.Tick()

	def OnFrameChangeHandler(self, meta, frame):
		THIS.Node.EmitOnNodeChange({
			'index': 		0x1000,
			'subindex': 	0x20,
			'direction':	0x1,
			'data': {
				'meta': meta,
				'frame': base64.encodestring(frame)
			}
		})
		for key in self.Streams:
			self.Node.SendStream(key, json.dumps({
				'data': {
					'meta': meta,
					'frame': base64.encodestring(frame)
				}
			}))
	
	def OnCameraFailHandler(self, uid):
		self.Node.LogMSG("({classname})# [OnCameraFailHandler] {0}".format(uid, classname=self.ClassName),5)
		self.RemoveCamera(uid)

		db_camera = self.DB["cameras"]
		for camera in db_camera:
			if uid == camera["uid"]:
				# Emit to UI
				THIS.Node.EmitOnNodeChange({
					'index': 		0x1000,
					'subindex': 	0x22,
					'direction':	0x1,
					'data': {
						'camera': camera
					}
				})
				return

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
	
	THIS.Node.Run(THIS.OnNodeWorkTick)
	THIS.Node.LogMSG("({classname})# Exit node.".format(classname=THIS.Node.ClassName),5)

if __name__ == "__main__":
	main()

'''
0x1000
	0x0 	(REQUIRED) 	PING
	0x1 	(REQUIRED) 	GETFRAME
	0x2		(REQUIRED) 	CAMERAINFO
	0x3		(REQUIRED) 	FPS
	0x4		(REQUIRED) 	SENSETIVITY
	0x5		(REQUIRED) 	RESOLUTION
	0x6		(REQUIRED) 	QUALITY
	0x20	(REQUIRED) 	ON_FRAME_CHANGE
	0x21	(REQUIRED) 	ON_CAMERA_CONNECTED
	0x22	(REQUIRED) 	ON_CAMERA_DISCONNECTED
	0x23 	(CUSTOM) 	ON_DELTE_CAMERA_FROM_DB
'''