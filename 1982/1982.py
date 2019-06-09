#!/usr/bin/python
import os
import sys
import signal
import json
import time
import thread
import threading

import pafy
import vlc

from mksdk import MkSFile
from mksdk import MkSNode
from mksdk import MkSSlaveNode
from mksdk import MkSLocalHWConnector

from flask import Flask, render_template, jsonify, Response, request

class Context():
	def __init__(self, node):
		self.Interval			= 10
		self.CurrentTimestamp 	= time.time()
		self.Node				= node
		self.SystemLoaded		= False
		# States
		self.States = {
		}
		# Handlers
		self.Handlers					= {
			'get_node_sensor_info':	self.GetNodeSensorInfoHandler,
			'set_node_sensor_info':	self.SetNodeSensorInfoHandler,
			'undefined':			self.UndefindHandler
		}
		# Local network
		self.LocalNetworkSocketList		= []
		# Sensors
		self.SensorList 				= []
		# Web interface
		self.UI 						= None
		# Player
		self.URL						= ""
		self.Volume 					= 0
		# Pafy
		self.Video 						= None
		self.Best 						= None
		self.PlayURL 					= None
		# VLC
		self.VLCInstance				= vlc.Instance('--novideo')
		self.Player 					= None
		self.Media 						= None

	def InitiatePyfy(self, url):
		print "InitiatePyfy", url
		self.Video 		= pafy.new(url)
		print "1"
		self.Best 		= self.Video.getbest()
		print "2"
		self.PlayURL 	= self.Best.url

	def InitiateVLC(self):
		print "InitiateVLC"
		self.Player = self.VLCInstance.media_player_new()
		self.Media 	= self.VLCInstance.media_new(self.PlayURL)
		self.Media.get_mrl()
		self.Player.set_media(self.Media)

	# Request from global network (basicaly websocket).
	def GetNodeSensorInfoHandler(self, message_type, source, data):
		print "GetNodeSensorInfoHandler"

	# Request from global network (basicaly websocket).
	def SetNodeSensorInfoHandler(self, message_type, source, data):
		print "SetNodeSensorInfoHandler", data
		sensors = data["payload"]["sensors"]
	
		self.GetNodeSensorInfoHandler(message_type, source, data)

	# Request from local network.
	def OnGetSensorInfoRequestHandler(self, json_data, sock):
		print "OnGetSensorInfoRequestHandler"
		sensors = ""

		for item in self.SensorList:
			sensors += "{\"uuid\":\"" + str(item[0]) + "\",\"type\":\"" + str(item[2]) + "\",\"name\":\"" + str(item[1]) + "\",\"value\":" + str(item[3]) + "},"

		THIS.Node.LocalServiceNode.SendSensorInfoResponse(sock, sensors[:-1])

	# Request from local network.
	def OnSetSensorInfoRequestHandler(self, json_data, sock):
		print "OnSetSensorInfoRequestHandler"

		connector = THIS.Node.GetConnector()
		sensors = json_data['sensors']
		for sensor in sensors:
			if "Switch" == sensor["type"]:
				info = "{\"sensor\":{\"id\":\"" + str(sensor["uuid"]) + "\",\"value\":" + str(sensor["value"]) + "}}"
				connector.SetSensorInfo(info)
				
		sensors = connector.GetSensorListInfo()
		for item in sensors["sensors"]:
			index = self.FindSwitchIndex(item["id"])
			if -1 != index:
					self.SensorList[index][3] = item["value"]

	def FindSwitchIndex(self, uuid):
		for idx, item in enumerate(self.SensorList):
			if uuid in item[0]:
				return idx
		return -1

	def UndefindHandler(self, message_type, source, data):
		print "UndefindHandler"

	def OnAceptNewConnectionHandler(self, sock):
		self.LocalNetworkSocketList.append(sock)

	def OnTerminateConnectionHandler(self, sock):
		self.LocalNetworkSocketList.remove(sock)

	def OnLocalServerStartedHandler(self):
		pass

	def WSDataArrivedHandler(self, message_type, source, data):
		command = data['device']['command']
		self.Handlers[command](message_type, source, data)

	def WSConnectedHandler(self):
		print "WSConnectedHandler"

	def WSConnectionClosedHandler(self):
		print "WSConnectionClosedHandler"

	def NodeSystemLoadedHandler(self):
		print "NodeSystemLoadedHandler"
		self.SystemLoaded = True

		jsonSensorStr = self.Node.GetFileContent("db.json")
		if jsonSensorStr != "":
			data = json.loads(jsonSensorStr) 
			self.URL = data["url"]
			self.Volume = int(data["vol"])
			self.InitiatePyfy(self.URL)
			self.InitiateVLC()

	def OnMasterFoundHandler(self, masters):
		print "OnMasterFoundHandler"

	def OnMasterSearchHandler(self):
		print "OnMasterSearchHandler"

	def OnMasterDisconnectedHandler(self):
		print "OnMasterDisconnectedHandler"

	def OnDeviceConnectedHandler(self):
		connector 		= THIS.Node.GetConnector()
		self.DeviceInfo = connector.GetDeviceInfo()
		sensors 		= connector.GetSensorListInfo()

		for item in sensors["sensors"]:
			self.SensorList.append([item["id"], "Name", "Switch", item["value"]])

	def TestWithKeyHandler(self, key):
		if "ykiveish" in key:
			return "{\"response\":\"OK\"}"
		else:
			return ""

	def GetNodeInfoHandler(self, key):
		data = {
			'hello'  : 'world',
			'number' : 3
		}
		js = json.dumps(data)

		resp = Response(js, status=200, mimetype='application/json')
		return resp

	def GetNodeWidgetHandler(self, key):
		objFile = MkSFile.File()
		js = objFile.LoadStateFromFile("static/js/node/widget.js")
		return js

	def SetNodeInfoHandler(self, key):
		fields = [k for k in request.form]
		values = [request.form[k] for k in request.form]

		print fields, values
		print "JSON",request.json
		data = {
			'hello'  : 'world',
			'number' : 3
		}
		js = json.dumps(data)

		resp = Response(js, status=200, mimetype='application/json')
		return resp

	def SetUrlHandler(self, key):
		fields = [k for k in request.form]
		values = [request.form[k] for k in request.form]

		print fields, values
		return "{\"response\":\"OK\"}" 

	def PlayHandler(self, key):
		if self.Player is not None:
			self.Player.play()
			return "{\"response\":\"OK\"}"
		return "{\"response\":\"FAILED\"}"

	def StopHandler(self, key):
		if self.Player is not None:
			self.Player.stop()
			return "{\"response\":\"OK\"}"
		return "{\"response\":\"FAILED\"}"

	def PauseHandler(self, key):
		if self.Player is not None:
			self.Player.pause()
			return "{\"response\":\"OK\"}"
		return "{\"response\":\"FAILED\"}"

	def VolumeUpHandler(self, key):
		self.Volume = self.Volume + 5
		print "CMD_VOL_UP " + str(self.Volume)
		self.Player.audio_set_volume(self.Volume)
		self.Node.SetFileContent("db.json", "{\"url\":\"" + self.URL + "\",\"vol\":\"" + str(self.Volume) + "\"}")
		return "{\"response\":\"OK\",\"vol\":" + str(self.Volume) + "}" 

	def VolumeDownHandler(self, key):
		self.Volume = self.Volume - 5
		print "CMD_VOL_DOWN " + str(self.Volume)
		self.Player.audio_set_volume(self.Volume)
		self.Node.SetFileContent("db.json", "{\"url\":\"" + self.URL + "\",\"vol\":\"" + str(self.Volume) + "\"}")
		return "{\"response\":\"OK\",\"vol\":" + str(self.Volume) + "}" 

	def OnLocalServerListenerStartedHandler(self, sock, ip, port):
		pass
		if self.UI is None:
			print "Start WebUI"
			webPort = 8000 + (port - 10000)
			self.UI = WebInterface("Context", webPort)
			# UI Pages
			data = "{\"ip\":\"" + str(ip) + "\",\"port\":" + str(webPort) + "}"
			THIS.UI.AddEndpoint("/", "index", None, data)
			THIS.UI.AddEndpoint("/config", "config", None, data)
			# UI RestAPI
			THIS.UI.AddEndpoint("/test/<key>", 				"test", 			THIS.TestWithKeyHandler)
			THIS.UI.AddEndpoint("/get/node_info/<key>", 	"get_node_info", 	THIS.GetNodeInfoHandler)
			THIS.UI.AddEndpoint("/get/node_widget/<key>", 	"get_node_widget", 	THIS.GetNodeWidgetHandler)
			THIS.UI.AddEndpoint("/set/node_info/<key>", 	"set_node_info", 	THIS.SetNodeInfoHandler, 	method=['POST'])
			THIS.UI.AddEndpoint("/player/set_url/<key>", 	"set_url", 			THIS.SetUrlHandler, 		method=['POST'])
			THIS.UI.AddEndpoint("/player/play/<key>", 		"play", 			THIS.PlayHandler)
			THIS.UI.AddEndpoint("/player/pause/<key>", 		"pause", 			THIS.PauseHandler)
			THIS.UI.AddEndpoint("/player/stop/<key>", 		"stop", 			THIS.StopHandler)
			THIS.UI.AddEndpoint("/player/vol_up/<key>", 	"vol_up", 			THIS.VolumeUpHandler)
			THIS.UI.AddEndpoint("/player/vol_down/<key>", 	"vol_down", 		THIS.VolumeDownHandler)
			# Run UI
			self.UI.Run()

	def WorkingHandler(self):
		if time.time() - self.CurrentTimestamp > self.Interval:
			print "WorkingHandler"

			self.CheckingForUpdate = True
			self.CurrentTimestamp = time.time()

			for idx, item in enumerate(THIS.Node.LocalServiceNode.GetConnections()):
				print "  ", str(idx), item.LocalType, item.UUID, item.IP, item.Port, item.Type

Service = MkSSlaveNode.SlaveNode()
Node 	= MkSNode.Node("YouTube Player", Service)
THIS 	= Context(Node)

def signal_handler(signal, frame):
	THIS.Node.Stop()

def main():
	signal.signal(signal.SIGINT, signal_handler)
	THIS.Node.SetLocalServerStatus(True)
	
	THIS.Node.OnWSDataArrived 					= THIS.WSDataArrivedHandler
	THIS.Node.OnWSConnected 					= THIS.WSConnectedHandler
	THIS.Node.OnWSConnectionClosed 				= THIS.WSConnectionClosedHandler
	THIS.Node.OnNodeSystemLoaded				= THIS.NodeSystemLoadedHandler
	THIS.Node.OnDeviceConnected					= THIS.OnDeviceConnectedHandler

	THIS.Node.LocalServiceNode.OnMasterFoundCallback				= THIS.OnMasterFoundHandler
	THIS.Node.LocalServiceNode.OnMasterSearchCallback				= THIS.OnMasterSearchHandler
	THIS.Node.LocalServiceNode.OnMasterDisconnectedCallback			= THIS.OnMasterDisconnectedHandler
	THIS.Node.LocalServiceNode.OnLocalServerStartedCallback			= THIS.OnLocalServerStartedHandler
	THIS.Node.LocalServiceNode.OnLocalServerListenerStartedCallback = THIS.OnLocalServerListenerStartedHandler

	THIS.Node.LocalServiceNode.OnAceptNewConnectionCallback			= THIS.OnAceptNewConnectionHandler
	THIS.Node.LocalServiceNodeOnTerminateConnectionCallback 		= THIS.OnTerminateConnectionHandler

	THIS.Node.LocalServiceNode.OnGetSensorInfoRequestCallback 		= THIS.OnGetSensorInfoRequestHandler
	THIS.Node.LocalServiceNode.OnSetSensorInfoRequestCallback 		= THIS.OnSetSensorInfoRequestHandler
	
	THIS.Node.Run(THIS.WorkingHandler)
	
	print "Exit Node ..."

if __name__ == "__main__":
    main()
