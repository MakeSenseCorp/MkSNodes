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

class FolderMonitor():
	def __init__(self, path, search_fn):
		self.ClassName					= "FolderMonitor"
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
		self.Interval					= 10
		self.CurrentTimestamp 			= time.time()
		self.Node						= node
		self.File 						= MkSFile.File()
		self.CameraSearcher 			= FolderMonitor("/dev", self.SerachForCameras)
		# States
		self.States = {
		}
		# Handlers
		self.RequestHandlers		= {
			'get_frame':				self.GetFrameHandler,
			'get_sensor_info':			self.GetSensorInfoHandler,
			'options':					self.OptionsHandler,
			'undefined':				self.UndefindHandler
		}
		self.ResponseHandlers		= {
			'undefined':				self.UndefindHandler
		}
		# Application variables
		self.DB							= None
		self.ObjCameras					= []

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
	
	def OptionsHandler(self, sock, packet):
		self.Node.LogMSG("({classname})# [OptionsHandler]".format(classname=self.ClassName),5)
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)

		camera = None
		for item in self.ObjCameras:
			if item.UID == payload["uid"]:
				camera = item
				break

		if camera is not None:
			if "set_sensetivity" in payload["option"]:
				camera.SetSensetivity(int(payload["value"]))
				self.UpdateCamerDB(payload["uid"], "sensetivity", int(payload["value"]))
			elif "set_fps" in payload["option"]:
				camera.SetFPS(int(payload["value"]))
				camera.SetSecondsPerFrame(1.0 / float(payload["value"]))
				self.UpdateCamerDB(payload["uid"], "user_fps", int(payload["value"]))
				self.UpdateCamerDB(payload["uid"], "seconds_between_frame", 1.0 / float(payload["value"]))
			else:
				pass
		
		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'return_code': 'ok'
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
		self.UpdateCamerDB(uid, "status", "disconnected")

		camera = None
		for item in self.ObjCameras:
			if item.UID == uid:
				camera = item
				break
		if camera is not None:
			self.ObjCameras.remove(camera)
	
	def OnStreamSocketCreatedHandler(self, name, identity):
		self.Node.LogMSG("({classname})# [OnStreamSocketCreatedHandler] {0} {1}".format(name,str(identity),classname=self.ClassName),5)

	def OnStreamSocketDataHandler(self, name, identity, data):
		self.Node.LogMSG("({classname})# [OnStreamSocketDataHandler] {0} {1}".format(name,data,classname=self.ClassName),5)
	
	def OnStreamSocketDisconnectedHandler(self, name, identity):
		self.Node.LogMSG("({classname})# [OnStreamSocketDisconnectedHandler] {0} {1}".format(name,str(identity),classname=self.ClassName),5)

	def OnGetNodeInfoHandler(self, info):
		self.Node.LogMSG("({classname})# [OnGetNodeInfoHandler] [{0}, {1}, {2}]".format(info["uuid"],info["name"],info["type"],classname=self.ClassName),5)

	def SerachForCameras(self, path):
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
				"status": "connected",
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
		camera.StartCamera()
		
		# Update camera object with values from database
		camera.Name = camera_db["name"]
		camera_db["enable"] = 1
		# Add camera to camera obejct DB
		self.ObjCameras.append(camera)
			
		self.Node.LogMSG("({classname})# Emit camera_connected {dev}".format(dev=camera_db["dev"],classname=self.ClassName),5)
		THIS.Node.EmitOnNodeChange({
			'event': "on_camera_connected",
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
		paths = self.SerachForCameras("/dev")
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

	def WorkingHandler(self):
		if time.time() - self.CurrentTimestamp > self.Interval:
			self.CheckingForUpdate = True
			self.CurrentTimestamp = time.time()

			self.Node.LogMSG("\nTables:",5)
			connections = THIS.Node.GetConnectedNodes()
			for idx, key in enumerate(connections):
				node = connections[key]
				self.Node.LogMSG("  {0}\t{1}\t{2}\t{3}\t{4}\t{5}\t{6}\t{7}".format(str(idx),node.Obj["local_type"],node.Obj["uuid"],node.IP,node.Obj["listener_port"],node.Obj["type"],node.Obj["pid"],node.Obj["name"]),5)
			self.Node.LogMSG("",5)

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

	def OnFrameChangeHandler(self, meta, frame):
		THIS.Node.EmitOnNodeChange({
			'event': "on_frame_change",
			'data': {
				'meta': meta,
				'frame': base64.encodestring(frame)
			}
		})
	
	def OnCameraFailHandler(self, uid):
		self.Node.LogMSG("({classname})# [OnCameraFailHandler] {0}".format(uid, classname=self.ClassName),5)
		self.RemoveCamera(uid)
		# Emit to UI

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
