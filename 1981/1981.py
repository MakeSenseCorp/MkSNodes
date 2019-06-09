#!/usr/bin/python
import os
import sys
import signal
import json
import time
import thread
import threading

from mksdk import MkSFile
from mksdk import MkSNode
from mksdk import MkSSlaveNode
from mksdk import MkSLocalHWConnector
from mksdk import MkSUSBAdaptor
from mksdk import MkSProtocol

from flask import Response, request

import ConnectorArduino
import HWDevice
import MkSTimer

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
			'undefined':			self.UndefindHandler
		}
		# Local network
		self.LocalNetworkSocketList		= []
		# Sensors
		self.DB 						= None
		self.DatabaseChanged			= False
		self.File 						= MkSFile.File()
		self.Timer 						= MkSTimer.MkSTimer();

		self.Timer.OnTimerTriggerEvent  = self.OnTimerTriggerHandler

	# Request from local network.
	def OnGetSensorInfoRequestHandler(self, packet, sock):
		print "OnGetSensorInfoRequestHandler"
		THIS.Node.LocalServiceNode.SendSensorInfoResponse(sock, packet, self.DB["sensors"])

	# Request from local network.
	def OnSetSensorInfoRequestHandler(self, packet, sock):
		print "OnSetSensorInfoRequestHandler"
		sensors = packet['payload']['data']['sensors']
		print sensors
		for sensor in sensors:
			if sensor["type"] in ["Single Switch", "Dual Switch"]:
				if sensor["action"] == "trigger_switch":
					self.SetSwitch(str(sensor["id"]), str(sensor["value"]))
				elif sensor["action"] == "update_sensor_info":
					# Update sensor info
					sw = self.FindSensor(str(sensor["id"]))
					if sensor["name"] is not None:
						sw["name"] = str(sensor["name"])

					if sensor["is_private"] is not None:
						sw["is_private"] = str(sensor["is_private"])

					if sensor["is_triggered_by_luminance"] is not None:
						sw["is_triggered_by_luminance"] = str(sensor["is_triggered_by_luminance"])

					if sensor["is_triggered_by_movement"] is not None:
						sw["is_triggered_by_movement"] = str(sensor["is_triggered_by_movement"])

					# Trigger update
					self.DatabaseChanged = True

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
		self.SystemLoaded = True

	def OnMasterFoundHandler(self, masters):
		print "OnMasterFoundHandler"

	def OnMasterSearchHandler(self):
		print "OnMasterSearchHandler"

	def OnMasterDisconnectedHandler(self):
		print "OnMasterDisconnectedHandler"

	def OnDeviceConnectedHandler(self):
		connector 		= THIS.Node.GetConnector()
		data 			= connector.GetDeviceInfo()
		self.DeviceInfo = data["payload"]

		# Load database.
		self.DB = json.loads(self.Node.GetFileContent("db.json"))

		# TODO - At first run db.json is empty, we need to create initial database.
		if self.DB is not None:
			idList = []
			for item in self.DB["sensors"]:
				info = "{\"id\":" + str(item["id"]) + ",\"value\":" + str(item["value"]) + "}"
				data = connector.SetSensorInfo(info)

				# Load timers.
				idList.append(str(item["id"]))
			self.Timer.LoadClocks(idList)
			self.Timer.Run()
		else:
			pass

	def FindSensor (self, id):
		for sensor in self.DB["sensors"]:
			if str(sensor["id"]) == str(id):
				return sensor
		return None

	# Hardware callbacks
	def OnSensorDeviceDataArrivedAsync(self, data):
		pass

	def OnDeviceDisconnectHandler(self, device_com):
		print "[DEBUG::Main] OnDeviceDisconnectHandler", str(device_com)

	def OnTimerTriggerHandler(self, uuid, action):
		print "[DEBUG::Main] OnTimerTriggerHandler", uuid, action

		if "On" in action:
			value = "1"
		elif "Off" in action:
			value = "0"
		elif "Press Up" in action:
			value = "1"
		elif "Press Down" in action:
			value = "1"

		self.SetSwitch(uuid, value)

	# Hardware handlers
	def TriggerSwitch(self, uuid, value):
		# Get connector instanse
		print "TRIGGER_SWITCH"
		connector 	= THIS.Node.GetConnector()

		info = "{\"id\":" + uuid + ",\"value\":" + value + "}"
		data = connector.SetSensorInfo(info)

	def SetSwitch (self, uuid, value):
		# TODO - If switch is dual (window) need to set a timeout.
		# Get requested sensor
		print "SET_SWITCH"
		sensor = self.FindSensor(uuid)
		if sensor is None:
			print "NO SENSOR FOUND"
			return

		if sensor["group"] is 255:
			# Single switch
			self.TriggerSwitch(uuid, value)
			
		elif sensor["group"] is not 255:
			# Double switch
			idOther = sensor["id_other"]
			otherSwitch = self.FindSensor(idOther)
			if otherSwitch is not None:
				self.TriggerSwitch(str(idOther), '0')
				otherSwitch["value"] = '0'
			self.TriggerSwitch(uuid, value)
		
		# Update local DB (not file)
		sensor["value"] = value
		self.DatabaseChanged = True

	# Web API an UI
	def GetSensorsInfoHandler(self, key):
		connector 	= THIS.Node.GetConnector()
		data		= connector.GetSensorListInfo()
		js 			= json.dumps(data["payload"])
		resp 		= Response(js, status=200, mimetype='application/json')
		return resp

	def SetSensorInfoHandler(self, key, id, value):
		# Activate action
		self.SetSwitch(id, value)
		# TODO - LoaclaServiceNode must return error if no connection to gateway
		# Send sensor changed data to Gateway
		THIS.Node.LocalServiceNode.SendSensorInfoChange(self.DB["sensors"])
		# Send response
		return "{\"response\":\"OK\"}"

	def GetNodeInfoHandler(self, key):
		js		= json.dumps(self.DB)
		resp	= Response(js, status=200, mimetype='application/json')
		return resp

	def SetNodeInfoHandler(self, key, id):
		fields = [k for k in request.form]
		values = [request.form[k] for k in request.form]

		req   = request.form["request"]
		data  = json.loads(request.form["json"])

		sensor = self.FindSensor(id)
		sensor["name"] 						= data["name"]
		sensor["is_private"] 				= data["is_private"]
		sensor["is_triggered_by_luminance"] = data["is_triggered_by_luminance"]
		sensor["is_triggered_by_movement"] 	= data["is_triggered_by_movement"]
		self.DatabaseChanged = True

		# Send response
		return "{\"response\":\"OK\"}"

	def SetTimerHandler(self, key, id):
		fields = [k for k in request.form]
		values = [request.form[k] for k in request.form]

		req   = request.form["request"]
		data  = json.loads(request.form["json"])

		if "add" in req:
			self.Timer.AddTimer(id, data)
		elif "remove" in req:
			timerID = data["id"]
			self.Timer.RemoveTimer(id, timerID)

		# Send response
		return "{\"response\":\"OK\"}"

	def GetTimerHandlers(self, key, id):
		data = self.Timer.GetTimers(str(id))
		resp = Response(data, status=200, mimetype='application/json')
		return resp

	def OnLocalServerListenerStartedHandler(self, sock, ip, port):
		THIS.Node.LocalServiceNode.AppendFaceRestTable(endpoint="/get/node_info/<key>", 						endpoint_name="get_node_info", 			handler=THIS.GetNodeInfoHandler)
		THIS.Node.LocalServiceNode.AppendFaceRestTable(endpoint="/set/node_info/<key>/<id>", 					endpoint_name="set_node_info", 			handler=THIS.SetNodeInfoHandler, 	method=['POST'])
		THIS.Node.LocalServiceNode.AppendFaceRestTable(endpoint="/get/node_sensors_info/<key>", 				endpoint_name="get_node_sensors", 		handler=THIS.GetSensorsInfoHandler)
		THIS.Node.LocalServiceNode.AppendFaceRestTable(endpoint="/set/node_sensor_info/<key>/<id>/<value>", 	endpoint_name="set_node_sensor_value", 	handler=THIS.SetSensorInfoHandler)
		THIS.Node.LocalServiceNode.AppendFaceRestTable(endpoint="/set/node_timer_item/<key>/<id>", 				endpoint_name="set_node_timer_item", 	handler=THIS.SetTimerHandler, 		method=['POST'])
		THIS.Node.LocalServiceNode.AppendFaceRestTable(endpoint="/get/node_timer_items/<key>/<id>", 			endpoint_name="get_node_timer_items", 	handler=THIS.GetTimerHandlers)

	def WorkingHandler(self):
		if time.time() - self.CurrentTimestamp > self.Interval:
			print "WorkingHandler"

			self.CheckingForUpdate = True
			self.CurrentTimestamp = time.time()

			if self.DatabaseChanged is True:
				print "[INFO] Save database to file"
				self.DatabaseChanged = False
				self.Node.SetFileContent("db.json", json.dumps(self.DB))

			for idx, item in enumerate(THIS.Node.LocalServiceNode.GetConnections()):
				print "  ", str(idx), item.LocalType, item.UUID, item.IP, item.Port, item.Type

Service = MkSSlaveNode.SlaveNode()
Node 	= MkSNode.Node("Switch", Service)
THIS 	= Context(Node)

def signal_handler(signal, frame):
	THIS.Timer.Stop()
	THIS.Node.Stop()

def main():
	signal.signal(signal.SIGINT, signal_handler)

	Protocol 	= MkSProtocol.Protocol()
	Adaptor 	= MkSUSBAdaptor.Adaptor(THIS.OnSensorDeviceDataArrivedAsync)
	Connector	= ConnectorArduino.Connector(None)
	Connector.SetProtocol(Protocol)
	Connector.SetAdaptor(Adaptor)
	Connector.SetDeviceDisconnectCallback(THIS.OnDeviceDisconnectHandler)

	# Device 		= HWDevice.LocalHWDevice()
	# Connector 	= MkSLocalHWConnector.LocalHWConnector(Device)

	THIS.Node.SetConnector(Connector)
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
	THIS.Node.LocalServiceNode.OnTerminateConnectionCallback 		= THIS.OnTerminateConnectionHandler

	# Communication events
	THIS.Node.LocalServiceNode.OnGetSensorInfoRequestCallback 		= THIS.OnGetSensorInfoRequestHandler
	THIS.Node.LocalServiceNode.OnSetSensorInfoRequestCallback 		= THIS.OnSetSensorInfoRequestHandler
	
	THIS.Node.Run(THIS.WorkingHandler)
	
	print "Exit Node ..."

if __name__ == "__main__":
    main()
