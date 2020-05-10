#!/usr/bin/python
import os
import sys
import signal
import json
import time
import thread
import threading
import struct

import subprocess
from subprocess import call
from subprocess import Popen, PIPE
import Queue

from mksdk import MkSFile
from mksdk import MkSSlaveNode
from mksdk import MkSShellExecutor
from mksdk import MkSConnectorUART
from mksdk import MkSUSBAdaptor
from mksdk import MkSProtocol
from mksdk import MkSDBcsv
from mksdk import MkSTimer

from flask import Response, request
from flask import send_file

import vlc
import hashlib

class FolderMonitor():
	def __init__(self, path):
		self.ClassName					= "FolderMonitor"
		self.Path 						= path
		self.Items 						= []
		self.File 						= MkSFile.File()

		self.WorkerThread				= None
		self.FolderContentChangedEvent	= None
	
	def SetPath(self, path):
		self.Path = path
	
	def GetItemsList(self):
		return self.Items

	def GetItems(self):
		return self.File.ListAllInFolder(self.Path)

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

class Security():
	def __init__(self):
		pass
	
	def GetMD5Hash(self, content):
		return hashlib.md5(content).hexdigest()
		# For Python 3+ hashlib.md5("whatever your string is".encode('utf-8')).hexdigest()

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
			'get_sensor_info':			self.GetSensorInfoHandler,
			'player_operation':			self.PlayerOperationHandler,
			'playlist_operation':		self.PlaylistOperationHandler,
			'critical_operation':		self.CriticalOperationHandler,
			'undefined':				self.UndefindHandler
		}
		self.ResponseHandlers		= {
			'undefined':				self.UndefindHandler
		}
		# Application variables
		self.DB							= None
		self.SecurityEnabled 			= False
		self.SMSService					= ""
		self.EmailService				= ""
		self.SensorLastValue            = {}

		self.LocalStorageEnabled 		= 0
		self.USBDevice 					= None
		self.LocalStoragePath 			= "./media/local"
		self.USBStoragePath 			= "./media/usb"
		self.SelectedStoragePath 		= None
		self.SongsFolder				= None
		self.Player 					= vlc.MediaPlayer()

		self.Timer 						= MkSTimer.MkSTimer()
		self.Timer.OnTimerTriggerEvent  = self.OnTimerTriggerHandler


	def OnTimerTriggerHandler(self, uuid, action):
		print ("({classname})# OnTimerTriggerHandler ...".format(classname=self.ClassName))

	def UndefindHandler(self, sock, packet):
		print ("UndefindHandler")
	
	def GetSensorInfoHandler(self, sock, packet):
		print ("({classname})# GetSensorInfoHandler ...".format(classname=self.ClassName))
		payload = {
			'playlists': self.DB["playlists"],
			'songs': self.SongsFolder.GetItemsList()
		}

		return THIS.Node.BasicProtocol.BuildResponse(packet, payload)
	
	def PlayerOperationHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		print ("({classname})# PlayerOperationHandler ... payload: {0}".format(payload, classname=self.ClassName))

		if "play" in payload["operation"]:
			self.Player.stop()
			self.Player.set_mrl(os.path.join(self.SelectedStoragePath, "songs", payload["song"]["name"]))
			self.Player.play()
			info = {
				"duration": self.Player.get_length(),
				"location": 0
			}
			print(info)
		elif "stop" in payload["operation"]:
			self.Player.stop()
			info = {
			}
		elif "pause" in payload["operation"]:
			pass
		elif "skip_back" in payload["operation"]:
			pass
		elif "skip_forward" in payload["operation"]:
			pass
		
		data = {
			"error": "none",
			"info": info
		}
		return THIS.Node.BasicProtocol.BuildResponse(packet, data)
	
	def PlaylistOperationHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		print ("({classname})# PlaylistOperationHandler ... payload: {0}".format(payload, classname=self.ClassName))
		
		data = {}
		return THIS.Node.BasicProtocol.BuildResponse(packet, data)
	
	def CriticalOperationHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		print ("({classname})# CriticalOperationHandler ... payload: {0}".format(payload, classname=self.ClassName))
		
		data = {}
		return THIS.Node.BasicProtocol.BuildResponse(packet, data)
	
	def OnMasterAppendNodeHandler(self, uuid, type, ip, port):
		print ("[OnMasterAppendNodeHandler]", str(uuid), str(type), str(ip), str(port))
	
	def OnMasterRemoveNodeHandler(self, uuid, type, ip, port):
		print ("[OnMasterRemoveNodeHandler]", str(uuid), str(type), str(ip), str(port))

	def OnGetNodeInfoHandler(self, info, online):
		print ("({classname})# Node Info Recieved ...\n\t{0}\t{1}\t{2}\t{3}".format(online, info["uuid"],info["name"],info["type"],classname=self.ClassName))
	
	def NodeSystemLoadedHandler(self):
		print ("({classname})# Loading system ...".format(classname=self.ClassName))		
		objFile = MkSFile.File()
		# Loading local database
		jsonSensorStr = objFile.Load("db.json")
		if jsonSensorStr != "":
			self.DB = json.loads(jsonSensorStr)
		
		self.LocalStorageEnabled = self.DB["local_storage"]

		# Get USB device
		self.USBDevice = self.DB["usb_device"]

		# Create file system for storing videos
		if not os.path.exists(self.LocalStoragePath):
			os.makedirs(self.LocalStoragePath)
		
		if not os.path.exists(self.USBStoragePath):
			os.makedirs(self.USBStoragePath)
		
		if self.LocalStorageEnabled == 1:
			self.SelectedStoragePath = self.LocalStoragePath
		else:
			self.SelectedStoragePath = self.USBStoragePath
		
		if not os.path.exists(os.path.join(self.SelectedStoragePath, "songs")):
			os.makedirs(os.path.join(self.SelectedStoragePath, "songs"))
		
		self.SongsFolder = FolderMonitor(os.path.join(self.SelectedStoragePath, "songs"))
		self.SongsFolder.GetItemsCompare()

		# self.Timer.LoadClocks(addrs)
		# self.Timer.Run()
		
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

	def OnLocalServerListenerStartedHandler(self, sock, ip, port):
		THIS.Node.AppendFaceRestTable(endpoint="/get/node_info/<key>", 						endpoint_name="get_node_info", 			handler=THIS.GetNodeInfoHandler)
		THIS.Node.AppendFaceRestTable(endpoint="/set/node_info/<key>/<id>", 				endpoint_name="set_node_info", 			handler=THIS.SetNodeInfoHandler, 	method=['POST'])
		THIS.Node.AppendFaceRestTable(endpoint="/get/node_sensors_info/<key>", 				endpoint_name="get_node_sensors", 		handler=THIS.GetSensorsInfoHandler)
		THIS.Node.AppendFaceRestTable(endpoint="/set/node_sensor_info/<key>/<id>/<value>", 	endpoint_name="set_node_sensor_value", 	handler=THIS.SetSensorInfoHandler)

	def WorkingHandler(self):
		if time.time() - self.CurrentTimestamp > self.Interval:
			self.CheckingForUpdate = True
			self.CurrentTimestamp = time.time()

			print("\nTables:")
			for idx, item in enumerate(THIS.Node.GetConnections()):
				print ("  {0}\t{1}\t{2}\t{3}\t{4}\t{5}".format(str(idx),item.LocalType,item.UUID,item.IP,item.Port,item.Type))
			print("")

			# Search for change in MP3 folder
			items, is_change = self.SongsFolder.GetItemsCompare()
			if is_change is True:
				THIS.Node.EmitOnNodeChange({
					'event': "media_folder_changed",
					'data': {
						'songs': items
					}
				})
		
		if (self.Node.Ticker % 5) == 0:
			if self.Player.get_state() == vlc.State.Playing:
				THIS.Node.EmitOnNodeChange({
					'event': "media_info",
					'data': {
						"duration": self.Player.get_length(),
						'location': self.Player.get_position()
					}
				})

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


"""
p = vlc.MediaPlayer("mks/mp3/1.mp3")
p.play()
p.audio_set_volume(50)
p.set_position(0.5)
p.get_position()
p.get_state()
duration = player.get_length() / 1000
p.set_mrl("mks/mp3/2.mp3")
"""