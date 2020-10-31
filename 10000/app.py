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
from mksdk import MkSScheduling

class SimpleJsonDB():
	def __init__(self):
		self.ClassName					= "SimpleJsonDB"

class ICamera():
	def __init__(self):
		self.ClassName					= "ICamera"

class Context():
	def __init__(self, node):
		self.ClassName					= "Apllication"
		self.Timer 						= MkSScheduling.TimeSchedulerThreadless()
		self.Node						= node
		self.File 						= MkSFile.File()
		# States
		self.States = {
		}
		# Handlers
		self.RequestHandlers		= {
			'get_sensor_info':			self.GetSensorInfoHandler,
			'undefined':				self.UndefindHandler
		}
		self.ResponseHandlers		= {
			'operations':				self.OperationsHandler,
			'undefined':				self.UndefindHandler
		}
		# Application variables
		self.DB							= None
		self.ObjCameras					= []
		self.CameraNodes 				= {}

		self.Timer.AddTimeItem(10, self.PrintConnections)
		self.Timer.AddTimeItem(5, self.SearchForCameras)
		self.Timer.AddTimeItem(1, self.GetFrame)
	
	def SaveCameraDBToFile(self):
		# Save new camera to database
		objFile = MkSFile.File()
		objFile.SaveJSON("db.json", self.DB)

	def UpdateCamerDBCacheValue(self, uid, name, value):
		db_camera = self.DB["cameras"]
		for camera in db_camera:
			if uid == camera["uid"]:
				camera[name] = value
				self.DB["cameras"] = db_camera
				break
	
	def AppendNewCamerDBCacheByIndex(self, camera):
		db_cameras = self.DB["cameras"]
		db_cameras.append(camera)
		self.DB["cameras"] = db_cameras
	
	def UpdateCamerDBCacheByIndex(self, index, camera):
		db_camera = self.DB["cameras"][index]
		db_camera["sensetivity"] 	= camera["sensetivity"]
		db_camera["fps"] 			= camera["fps"]
		db_camera["enable"] 		= camera["enable"]
		db_camera["status"] 		= camera["status"]
		self.DB["cameras"][index] = db_camera
	
	def CameraExistInDB(self, uid):
		for idx, camera in enumerate(self.DB["cameras"]):
			if camera["uid"] in uid:
				return True, idx
		return False, None

	def UndefindHandler(self, sock, packet):
		print ("UndefindHandler")

	def GetSensorInfoHandler(self, sock, packet):
		print ("({classname})# GetSensorInfoHandler ...".format(classname=self.ClassName))
		payload = {
			'cameras': self.DB["cameras"]
		}

		return payload

	def OperationsHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		self.Node.LogMSG("({classname})# [OperationsHandler]".format(classname=self.ClassName),5)

		messageType = self.Node.BasicProtocol.GetMessageTypeFromJson(packet)
		direction 	= self.Node.BasicProtocol.GetDirectionFromJson(packet)
		destination = self.Node.BasicProtocol.GetDestinationFromJson(packet)
		source 		= self.Node.BasicProtocol.GetSourceFromJson(packet)
		command 	= self.Node.BasicProtocol.GetCommandFromJson(packet)

		if "index" in payload and "subindex" in payload:
			index = payload["index"]
			if index == 0x1000:
				# CAMERA			
				subindex  	= payload["subindex"]
				direction 	= payload["direction"]
				data 		= payload["data"]
				if 0x0 == subindex:
					self.Node.LogMSG("({classname})# [OperationsHandler] PING subindex {0}".format(source,classname=self.ClassName),5)
					# PING
					if source not in self.CameraNodes:
						self.Node.SendRequestToNode(source, "operations", {
							"index": 	 0x1000,
							"subindex":	 0x1,
							"direction": 0x1,
							"data": { }
						})
						# Open stream to this node
						# self.StreamIdentity = self.Node.ConnectStream(source, source)
						self.CameraNodes[source] = {
							"uuid": 			source,
							"stream_id": 		0,
							"register_events": 	0,
							"status":			"INIT",
							"ts":				time.time()
						}
						# self.Node.RegisterOnNodeChangeEvent(source)
					else:
						pass
				if 0x1 == subindex:
					# INFO
					self.Node.LogMSG("({classname})# [OperationsHandler] INFO {0}".format(data, classname=self.ClassName),5)
					cameras = None
					if "cameras" in data:
						cameras 	= data["cameras"]
						for camera in cameras:
							self.Node.LogMSG("({classname})# [OperationsHandler] INFO {0}".format(camera, classname=self.ClassName),5)
							status, idx = self.CameraExistInDB(camera["uid"])
							if status is False:
								# Append camera to DB
								self.AppendNewCamerDBCacheByIndex({
									"status": camera["status"], 
									"enable": camera["enable"], 
									"uid": camera["uid"], 
									"fps": camera["fps"], 
									"sensetivity": camera["sensetivity"],
									"name": "Camera_" + camera["uid"],
									"face_detect_enabled": 0,
									"security_enabled": 0,
									"motion_detection_enabled": 0,
									"uuid": source
								})
							else:
								# Update camera DB
								if idx is not None:
									self.UpdateCamerDBCacheByIndex(idx, camera)
						self.SaveCameraDBToFile()
						if self.CameraNodes[source]["status"] in "INIT":
							# Connect node using regualar MKS TCP connection
							conn_info = data["local_connection"]
							self.Node.LogMSG("({classname})# Connecting to {0}".format(conn_info["ip"], classname=self.ClassName),5)
							self.Node.ConnectNode(conn_info["ip"], conn_info["port"])
							self.CameraNodes[source]["status"] = "PREOP"
				elif 0x11 == subindex:
					# GETFRAME
					self.Node.LogMSG("({classname})# [OperationsHandler] GETFRAME {0}".format(payload, classname=self.ClassName),5)
					pass
				elif 0x12 == subindex:
					self.Node.LogMSG("({classname})# [OperationsHandler] CAMERAINFO {0}".format(payload, classname=self.ClassName),5)
					# CAMERAINFO
					enabled 	= payload["enabled"]
					uid 		= payload["uid"]
					fps 		= payload["fps"]
					sensetivity = payload["sensetivity"]
					pass
				elif 0x13 == subindex:
					# FPS
					if direction:
						# SET
						pass
					else:
						# GET
						pass
				if 0x14 == subindex:
					# SENSETIVITY
					if direction:
						# SET
						pass
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
				'event': "delete_camera_from_db",
				'data': {
					'uid': uid
				}
			})
			# Send response
			return {
				'return_code': 'ok'
			}
		# Send response
		return {
			'return_code': 'failed'
		}

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

	def OnStreamSocketDataHandler(self, name, identity, data):
		'''
		PLEASE NOE YOU ARE IN THE STREAM SOCKET CONTEXT, MAKE YOUR ACTIONS FAST
		'''
		self.Node.LogMSG("({classname})# [OnStreamSocketDataHandler] {0} {1}".format(name,identity,classname=self.ClassName),5)
		try:
			packet = json.loads(data)
		except Exception as e:
			self.Node.LogException("[DataArrivedEvent]",e,3)
	
	def OnStreamSocketDisconnectedHandler(self, name, identity):
		self.Node.LogMSG("({classname})# [OnStreamSocketDisconnectedHandler] {0} {1}".format(name,str(identity),classname=self.ClassName),5)

	def OnGetNodeInfoHandler(self, info):
		self.Node.LogMSG("({classname})# [OnGetNodeInfoHandler] [{0}, {1}, {2}]".format(info["uuid"],info["name"],info["type"],classname=self.ClassName),5)
		if info["uuid"] in self.CameraNodes:
			self.CameraNodes[info["uuid"]]["status"] = "OP"
			self.Node.LogMSG("({classname})# [OnGetNodeInfoHandler] Camera Node Operational {0}".format(info["uuid"],classname=self.ClassName),5)
	
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
				"status": "Disconnected", 
				"enable": 1, 
				"uid": camera.UID, 
				"fps": 1, 
				"name": 'Camera_' + camera.UID,
				"face_detect_enabled": 0,
				"security_enabled": 0,
				"motion_detection_enabled": 0
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

		self.Node.SearchNodes(0x1000)
		self.Node.LogMSG("({classname})# Loading system ... DONE.".format(classname=self.ClassName),5)
	
	def OnApplicationCommandRequestHandler(self, sock, packet):
		command = self.Node.BasicProtocol.GetCommandFromJson(packet)
		if command in self.RequestHandlers:
			return self.RequestHandlers[command](sock, packet)
		
		return {
			'error': 'cmd_no_support'
		}

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
		# Search for services
		self.Node.LogMSG("({classname})# [SearchForCameras] ".format(classname=self.ClassName),5)
		self.Node.SearchNodes(0x1000)
	
	def GetFrame(self):
		for uuid in self.CameraNodes:
			camera_node = self.CameraNodes[uuid]
			if camera_node["status"] in "OP":
				self.Node.SendRequestToNode(uuid, "operations", {
					"index": 	 0x1000,
					"subindex":	 0x11,
					"direction": 0x1,
					"data": { }
				})
	
	def WorkingHandler(self):
		self.Timer.Tick()

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

		db_camera = self.DB["cameras"]
		for camera in db_camera:
			if uid == camera["uid"]:
				# Emit to UI
				THIS.Node.EmitOnNodeChange({
					'event': "on_camera_disconnected",
					'data': {
						'camera': camera
					}
				})
				return
	
	def OnGenericEventHandler(self, event, data):
		pass

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
	THIS.Node.OnGenericEvent 						= THIS.OnGenericEventHandler
	# Stream sockets events
	THIS.Node.OnStreamSocketCreatedEvent 			= THIS.OnStreamSocketCreatedHandler
	THIS.Node.OnStreamSocketDataEvent 				= THIS.OnStreamSocketDataHandler
	THIS.Node.OnStreamSocketDisconnectedEvent		= THIS.OnStreamSocketDisconnectedHandler
	
	THIS.Node.Run(THIS.WorkingHandler)
	THIS.Node.LogMSG("({classname})# Exit node.".format(classname=THIS.Node.ClassName),5)

if __name__ == "__main__":
    main()
