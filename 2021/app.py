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
from mksdk import MkSFileUploader

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
		self.Uploader 					= None
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
			'upload_file':				self.Request_UploadFileHandler,
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
		self.SoundCards					= []
		self.CurrentInterface 			= None
		self.CurrentPlayingSongName		= ""
		self.CurrentPlayerState 		= "IDLE"

		self.Timer 						= MkSTimer.MkSTimer()
		self.Timer.OnTimerTriggerEvent  = self.OnTimerTriggerHandler

		self.UploadLocker				= threading.Lock()

	def GetPlayerState(self):
		state = self.Player.get_state()
		if state == vlc.State.Buffering:
			return "BUFFER"
		elif state == vlc.State.Ended:
			return "END"
		elif state == vlc.State.Error:
			return "ERROR"
		elif state == vlc.State.NothingSpecial:
			return "IDLE"
		elif state == vlc.State.Opening:
			return "OPEN"
		elif state == vlc.State.Paused:
			return "PAUSE"
		elif state == vlc.State.Playing:
			return "PLAY"
		elif state == vlc.State.Stopped:
			return "STOP"

	def OnTimerTriggerHandler(self, uuid, action):
		self.Node.LogMSG("({classname})# OnTimerTriggerHandler ...".format(classname=self.ClassName),5)

	def UndefindHandler(self, sock, packet):
		self.Node.LogMSG("UndefindHandler",5)
	
	def Request_UploadFileHandler(self, sock, packet):
		self.UploadLocker.acquire()
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		self.Node.LogMSG("({classname})# [Request_UploadFileHandler] {0}".format(payload["upload"]["chunk"], classname=self.ClassName),5)

		if payload["upload"]["chunk"] == 1:
			self.Uploader.AddNewUploader(payload["upload"])
		else:
			self.Uploader.UpdateUploader(payload["upload"])
		
		self.UploadLocker.release()
		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'status': 'accept',
			'chunk': payload["upload"]["chunk"],
			'file': payload["upload"]["file"]
		})
	
	def GetSensorInfoHandler(self, sock, packet):
		self.Node.LogMSG("({classname})# GetSensorInfoHandler ...".format(classname=self.ClassName),5)
		info = {
			'duration': self.Player.get_length(),
			'position': self.Player.get_time(),
			'name': self.CurrentPlayingSongName,
			'state': self.CurrentPlayerState,
			'volume': self.Player.audio_get_volume()
		}
		payload = {
			'playlists': self.DB["playlists"],
			'songs': self.SongsFolder.GetItemsList(),
			'info': info
		}

		return THIS.Node.BasicProtocol.BuildResponse(packet, payload)
	
	def PlayerOperationHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		self.Node.LogMSG("({classname})# PlayerOperationHandler ... payload: {0}".format(payload, classname=self.ClassName),5)

		self.CurrentPlayerState = self.GetPlayerState()
		error = "none"
		info = {
			'duration': self.Player.get_length(),
			'position': self.Player.get_time(),
			'volume': self.Player.audio_get_volume(),
			'name': self.CurrentPlayingSongName,
			'state': self.CurrentPlayerState
		}
		
		if "play" in payload["operation"]:
			self.Player.stop()

			if payload["song"] is None:
				error = "Incorrect structure"
				self.Node.LogMSG("({classname})# PlayerOperationHandler [ERROR] {0}".format(error, classname=self.ClassName),3)
			else:
				if not payload["song"]["name"]:
					error = "No song name provided"
					self.Node.LogMSG("({classname})# PlayerOperationHandler [ERROR] {0}".format(error, classname=self.ClassName),3)
				else:
					song_path = os.path.join(self.SelectedStoragePath, "songs", payload["song"]["name"])
					# Check if file valid
					if not os.path.exists(song_path):
						error = "File not exist"
						self.Node.LogMSG("({classname})# PlayerOperationHandler [ERROR] {0} {1}".format(error, song_path, classname=self.ClassName),3)
					else:
						self.Player.set_mrl(song_path)
						self.Player.play()
						# Let VLC load the song content
						time.sleep(1)
						# Update Node context
						self.CurrentPlayerState 	= self.GetPlayerState()
						self.CurrentPlayingSongName = payload["song"]["name"]
						# Info structure respone
						info["duration"] 	= self.Player.get_length()
						info["position"] 	= 0
						info["volume"] 		= self.Player.audio_get_volume()
						info["name"] 		= payload["song"]["name"]
						info["state"] 		= self.CurrentPlayerState

						self.Player.audio_output_device_set(None, self.CurrentInterface)
		elif "stop" in payload["operation"]:
			self.Player.stop()
			self.CurrentPlayerState = self.GetPlayerState()
			info["state"] 			= self.CurrentPlayerState
		elif "pause" in payload["operation"]:
			self.CurrentPlayerState = self.GetPlayerState()
			self.Player.pause()
			time.sleep(0.2)
			self.CurrentPlayerState = self.GetPlayerState()
			info["state"] 			= self.CurrentPlayerState
		elif "set_time" in payload["operation"]:
			self.Player.set_time(int(payload["song"]["time"]))
			time.sleep(0.2)
			info["position"] = self.Player.get_time()
		elif "set_volume" in payload["operation"]:
			self.Player.audio_set_volume(payload["song"]["volume"])
			time.sleep(0.2)
			info["volume"] = self.Player.audio_get_volume()

		data = {
			"error": error,
			"info": info
		}
		return THIS.Node.BasicProtocol.BuildResponse(packet, data)
	
	def PlaylistOperationHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		self.Node.LogMSG("({classname})# PlaylistOperationHandler ... payload: {0}".format(payload, classname=self.ClassName),5)
		
		data = {}
		return THIS.Node.BasicProtocol.BuildResponse(packet, data)
	
	def CriticalOperationHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		self.Node.LogMSG("({classname})# CriticalOperationHandler ... payload: {0}".format(payload, classname=self.ClassName),5)
		
		data = {}
		return THIS.Node.BasicProtocol.BuildResponse(packet, data)
	
	def OnStreamSocketCreatedHandler(self, name, identity):
		self.Node.LogMSG("({classname})# [OnStreamSocketCreatedHandler] {0} {1}".format(name,str(identity),classname=self.ClassName),5)

	def OnStreamSocketDataHandler(self, name, data):
		self.Node.LogMSG("({classname})# [OnStreamSocketDataHandler] {0} {1}".format(name,str(len(data)),classname=self.ClassName),5)
	
	def OnStreamSocketDisconnectedHandler(self, name, identity):
		self.Node.LogMSG("({classname})# [OnStreamSocketDisconnectedHandler] {0} {1}".format(name,str(identity),classname=self.ClassName),5)

	def OnMasterAppendNodeHandler(self, uuid, type, ip, port):
		self.Node.LogMSG("({classname})# [OnMasterAppendNodeHandler] {0} {1} {2} {3}".format(str(uuid), str(type), str(ip), str(port), classname=self.ClassName),5)
	
	def OnMasterRemoveNodeHandler(self, uuid, type, ip, port):
		self.Node.LogMSG("({classname})# [OnMasterRemoveNodeHandler]{0} {1} {2} {3}".format(str(uuid), str(type), str(ip), str(port), classname=self.ClassName),5)

	def OnGetNodeInfoHandler(self, info):
		self.Node.LogMSG("({classname})# [OnGetNodeInfoHandler] [{0}, {1}, {2}]".format(info["uuid"],info["name"],info["type"],classname=self.ClassName),5)
	
	def NodeSystemLoadedHandler(self):
		self.Node.LogMSG("({classname})# Loading system ...".format(classname=self.ClassName),5)		
		objFile = MkSFile.File()
		self.Uploader = MkSFileUploader.Manager(self)
		self.Uploader.SetUploadPath(os.path.join(self.LocalStoragePath, "songs"))
		self.Uploader.Run()
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

		ifaces = [	'alsa_output.pci-0000_00_1b.0.analog-stereo', 
					'bluez_sink.79_8F_BC_00_35_85.a2dp_sink', 
					'alsa_output.usb-Plantronics_Plantronics_C520-M_EEBA9F757CA8EF49A0CBAA3AC0D6E280-00.analog-stereo']
		interfaces = self.Player.audio_output_device_enum()
		if interfaces:
			iface = interfaces
			while iface:
				iface = iface.contents
				if "bluez_sink.79_8F_BC_00_35_85" in iface.device:
					self.Player.audio_output_device_set(None, iface.device)
					self.CurrentInterface = iface.device
					self.Node.LogMSG("({classname})# Bluetooth device was selected...".format(classname=self.ClassName),5)
				self.SoundCards.append(iface.device)
				iface = iface.next

		vlc.libvlc_audio_output_device_list_release(interfaces)
		self.Node.LogMSG(self.SoundCards,5)

		# self.Timer.LoadClocks(addrs)
		# self.Timer.Run()
		
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
		self.Node.LogMSG("({classname})# [OnGetNodesListHandler]".format(uuids,classname=self.ClassName),5)

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

			self.Node.LogMSG("\nTables:",5)
			connections = THIS.Node.GetConnectedNodes()
			for idx, key in enumerate(connections):
				node = connections[key]
				self.Node.LogMSG("  {0}\t{1}\t{2}\t{3}\t{4}\t{5}\t{6}\t{7}".format(str(idx),node.Obj["local_type"],node.Obj["uuid"],node.IP,node.Obj["listener_port"],node.Obj["type"],node.Obj["pid"],node.Obj["name"]),5)
			self.Node.LogMSG("",5)

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
			# self.Node.LogMSG(self.Player.audio_output_device_get())
			self.CurrentPlayerState = self.GetPlayerState()
			THIS.Node.EmitOnNodeChange({
				'event': "media_info",
				'data': {
					'info': {
						'duration': self.Player.get_length(),
						'position': self.Player.get_time(),
						'name': self.CurrentPlayingSongName,
						'state': self.CurrentPlayerState,
						'volume': self.Player.audio_get_volume()
					}
				}
			})

Node = MkSSlaveNode.SlaveNode()
THIS = Context(Node)

def signal_handler(signal, frame):
	THIS.Node.Stop("Accepted signal from other app")
	
def main():
	signal.signal(signal.SIGINT, signal_handler)
	THIS.Node.SetLocalServerStatus(True)
	
	# Node callbacks
	THIS.Node.NodeSystemLoadedCallback				= THIS.NodeSystemLoadedHandler
	#THIS.Node.OnLocalServerListenerStartedCallback 	= THIS.OnLocalServerListenerStartedHandler
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
