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
			'get_sensor_info':			self.GetSensorInfoHandler,
			'read_sensor_info':			self.ReadSensorInfoHandler,
			'write_sensor_info':		self.WriteSensorInfoHandler,
			'undefined':				self.UndefindHandler
		}
		self.ResponseHandlers		= {
			'undefined':				self.UndefindHandler
		}
		# Application variables
		self.DB							= None
		self.SensorsLive				= {}
		self.SecurityEnabled 			= False
		self.SMSService					= ""
		self.EmailService				= ""
		self.MasterTX 					= None
		self.MasterRX 					= None
		self.TestData 					= 500
		self.SwitchTestValue 			= 0

		self.HW 						= MkSConnectorUART.Connector()

		self.HW.AdaptorDisconnectedEvent = self.AdaptorDisconnectedCallback
	
	def AdaptorDisconnectedCallback(self, path, type):
		print ("({classname})# (AdaptorDisconnectedCallback) {0} {1} ...".format(path, type, classname=self.ClassName))
		if self.MasterTX is not None:
			if self.MasterTX["path"] in path:
				self.MasterTX = None
				THIS.Node.EmitOnNodeChange({
					'event': "device_remove",
					'type': "master_tx",
					'path': path
				})
		if self.MasterRX is not None:
			if self.MasterRX["path"] in path:
				self.MasterRX = None
				THIS.Node.EmitOnNodeChange({
					'event': "device_remove",
					'type': "master_rx",
					'path': path
				})

	def UndefindHandler(self, sock, packet):
		print ("UndefindHandler")

	def FindSensor(self, addr):
		for sensor in self.DB["sensors"]:
			if sensor["addr"] == addr:
				return sensor
		return None
	
	def GetSensorInfoHandler(self, sock, packet):
		print ("({classname})# GetSensorInfoHandler ...".format(classname=self.ClassName))
		payload = {
			'sensors': self.DB["sensors"],
			'devices': self.DB["confuguration"]["devices"]
		}

		return THIS.Node.BasicProtocol.BuildResponse(packet, payload)
	
	def ReadSensorInfoHandler(self, sock, packet):
		print ("({classname})# ReadSensorInfoHandler ...".format(classname=self.ClassName))
	
	def WriteSensorInfoHandler(self, sock, packet):
		print ("({classname})# WriteSensorInfoHandler ...".format(classname=self.ClassName))
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)

		addr  = payload["addr"]
		value = payload["value"]
		if self.MasterTX is not None:
			data = self.MasterTX["dev"].Send(struct.pack("<BBBBBBBH", 0xDE, 0xAD, 0x1, 100, 4, addr, 1, value))
			sensor = self.FindSensor(addr)
			sensor["value"] = value
			self.File.SaveJSON("db.json", self.DB)

		return THIS.Node.BasicProtocol.BuildResponse(packet, {})
	
	def RFDataArrivedHandler(self, packet):
		pass
	
	def OnMasterAppendNodeHandler(self, uuid, type, ip, port):
		print ("[OnMasterAppendNodeHandler]", str(uuid), str(type), str(ip), str(port))
	
	def OnMasterRemoveNodeHandler(self, uuid, type, ip, port):
		print ("[OnMasterRemoveNodeHandler]", str(uuid), str(type), str(ip), str(port))

	def OnGetNodeInfoHandler(self, info, online):
		print ("({classname})# Node Info Recieved ...\n\t{0}\t{1}\t{2}\t{3}".format(online, info["uuid"],info["name"],info["type"],classname=self.ClassName))
	
	def CheckDeviceType(self, adapter):
		data = adapter["dev"].Send(struct.pack("BBBB", 0xDE, 0xAD, 0x1, 52))
		magic_one, magic_two, direction, op_code, content_length, rf_type = struct.unpack("BBBBBB", data[0:6])
		adapter["type"] = rf_type
		if rf_type == 1:
			self.MasterTX = adapter
			self.DB["confuguration"]["devices"]["tx"]["state"] = 1
			print("({classname})# MASTER TX Found ...".format(classname=self.ClassName))
			THIS.Node.EmitOnNodeChange({
				'event': "device_found",
				'type': rf_type,
				'path': adapter["path"]
			})
		elif rf_type == 2:
			self.MasterRX = adapter
			self.DB["confuguration"]["devices"]["rx"]["state"] = 1
			print("({classname})# MASTER RX Found ...".format(classname=self.ClassName))
			THIS.Node.EmitOnNodeChange({
				'event': "device_found",
				'type': rf_type,
				'path': adapter["path"]
			})
		elif rf_type == 3:
			print("({classname})# SLAVE Found ...".format(classname=self.ClassName))
			THIS.Node.EmitOnNodeChange({
				'event': "device_found",
				'type': rf_type,
				'path': adapter["path"]
			})
			adapter["dev"].Disconnect()

	def NodeSystemLoadedHandler(self):
		print ("({classname})# Loading system ...".format(classname=self.ClassName))		
		objFile = MkSFile.File()
		# THIS.Node.GetListOfNodeFromGateway()
		# Loading local database
		jsonSensorStr = objFile.Load("db.json")
		if jsonSensorStr != "":
			self.DB = json.loads(jsonSensorStr)

			self.DB["confuguration"]["devices"]["rx"]["state"] = 0
			self.DB["confuguration"]["devices"]["tx"]["state"] = 0

			for db_sensor in self.DB["sensors"]:
				self.SensorsLive[db_sensor["addr"]] = {
					'value': db_sensor["value"],
					'access': db_sensor["access"]
				}
		
		adapters = self.HW.Connect("2020")
		for adapter in adapters:
			self.CheckDeviceType(adapter)
		
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

			changes = self.HW.UpdateUARTInterfaces()
			for change in changes:
				if change["change"] in "append":
					adapter = self.HW.FindAdaptor(change["path"])
					self.CheckDeviceType(adapter)

			if self.MasterTX is not None:
				for sensor in self.DB["sensors"]:
					data = self.MasterTX["dev"].Send(struct.pack("<BBBBBBBH", 0xDE, 0xAD, 0x1, 100, 4, sensor["addr"], 1, sensor["value"]))
					#magic_one, magic_two, direction, op_code, content_length, ack = struct.unpack("<BBBBBH", data[0:7])

Node = MkSSlaveNode.SlaveNode()
THIS = Context(Node)

def signal_handler(signal, frame):
	THIS.Node.Stop()
	time.sleep(0.5)
	THIS.HW.Disconnect()

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
