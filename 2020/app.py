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
			'set_sensor_addr':			self.SetSensorAddrHandler,
			'save_sensor_to_db':		self.SaveSensorToDBHandler,
			'append_sensor_to_db':		self.AppendSensorToDBHandler,
			'remove_sensor_to_db':		self.RemoveSensorToDBHandler,
			'sensors_graph': 			self.SensorGraphHandler,
			'get_timer': 				self.GetTimerHandlers,
			'append_timer': 			self.AppendTimerHandlers,
			'remove_timer':				self.RemoveTimerHandlers,
			'undefined':				self.UndefindHandler
		}
		self.ResponseHandlers		= {
			'undefined':				self.UndefindHandler
		}
		# Application variables
		self.SensorsDB                  = MkSDBcsv.Database()
		self.DB							= None
		self.SecurityEnabled 			= False
		self.SMSService					= ""
		self.EmailService				= ""
		self.MasterTX 					= None
		self.MasterRX 					= None
		self.DeviceList 				= []
		self.HW 						= MkSConnectorUART.Connector()
		self.SensorLastValue            = {}

		self.HW.AdaptorDisconnectedEvent = self.AdaptorDisconnectedCallback
		self.HW.AdaptorAsyncDataEvent	 = self.AdaptorAsyncDataCallback

		self.Timer 						= MkSTimer.MkSTimer()
		self.Timer.OnTimerTriggerEvent  = self.OnTimerTriggerHandler
	
	def AdaptorAsyncDataCallback(self, path, packet):
		if self.MasterRX is not None:
			if path == self.MasterRX["path"]:
				if packet[1] == 101:
					print ("({classname})# [{0}] (RF RX) {1}".format(path, packet, classname=self.ClassName))
					if len(packet) > 6:
						sensor = self.FindSensor(packet[3])
						
						try:
							update = True
							# Do we nned to update UI?
							if packet[3] in self.SensorLastValue:
								value = self.SensorLastValue[packet[3]]["value"] # Key is ADDR
								update = (value != (int(packet[6]) << 8) | int(packet[5]))
								# print ("({classname})# [UPDATE] {0} = {1} ? {2}".format(update, value, (int(packet[6]) << 8) | int(packet[5]), classname=self.ClassName))
								value = (int(packet[6]) << 8) | int(packet[5])
								self.SensorLastValue[packet[3]]["ts"] = time.time()
								self.SensorLastValue[packet[3]]["value"] = value
							else:
								self.SensorLastValue[packet[3]] = {
									'value': (int(packet[6]) << 8) | int(packet[5]),
									'ts': time.time(),
									'addr': packet[3]
								}
							
							if sensor is not None:
								if update is True:
									if int(sensor["rf_type"]) == 5:
										motion = int(packet[5]) & 1
										temperature = (int(packet[5]) & 0xfe) >> 1
										humidity = int(packet[6])
										self.SensorsDB.WriteDB(str(packet[3]), [str(motion), str(temperature), str(humidity)])
										value = {
											'motion': motion,
											'temperature': temperature,
											'humidity': humidity
										}
										THIS.Node.EmitOnNodeChange({
											'event': "sensor_value_change",
											'sensor': {
												'addr': str(packet[3]),
												'rf_type': sensor["rf_type"],
												'motion': motion,
												'temperature': temperature,
												'humidity': humidity
											}
										})
									elif int(sensor["rf_type"]) == 6:
										temperature = int(packet[5])
										humidity = int(packet[6])
										self.SensorsDB.WriteDB(str(packet[3]), [str(temperature), str(humidity)])
										value = {
											'temperature': temperature,
											'humidity': humidity
										}
										THIS.Node.EmitOnNodeChange({
											'event': "sensor_value_change",
											'sensor': {
												'addr': str(packet[3]),
												'rf_type': sensor["rf_type"],
												'temperature': temperature,
												'humidity': humidity
											}
										})
									else:
										value = (int(packet[6]) << 8) | int(packet[5])
										self.SensorsDB.WriteDB(str(packet[3]), [str((int(packet[6]) << 8) | int(packet[5]))])
										THIS.Node.EmitOnNodeChange({
											'event': "sensor_value_change",
											'sensor': {
												'addr': str(packet[3]),
												'rf_type': sensor["rf_type"],
												'value': value
											}
										})
									sensor["value"] = value
									self.File.SaveJSON("db.json", self.DB)
						except Exception as e:
							print("(MkSNode)# ERROR - AdaptorAsyncDataCallback\n(EXEPTION)# {error}".format(error=str(e)))
					else:
						print ("({classname})# [ERROR] (RF RX) {0}".format(len(packet), classname=self.ClassName))
				else:
					pass

	def AdaptorDisconnectedCallback(self, path, rf_type):
		print ("({classname})# (AdaptorDisconnectedCallback) {0} {1} ...".format(path, rf_type, classname=self.ClassName))
		if rf_type == 1:
			if self.MasterTX is not None:
				self.DB["confuguration"]["devices"]["tx"]["state"] = 0
				self.MasterTX = None
				THIS.Node.EmitOnNodeChange({
					'event': "device_remove",
					'rf_type': rf_type,
					'path': path
				})
		elif rf_type == 2:
			if self.MasterRX is not None:
				self.DB["confuguration"]["devices"]["rx"]["state"] = 0
				self.MasterRX = None
				THIS.Node.EmitOnNodeChange({
					'event': "device_remove",
					'rf_type': rf_type,
					'path': path
				})
		else:
			adaptor = None
			for device in self.DeviceList:
				if device["path"] in path:
					adaptor = device
					break
			if adaptor is not None:
				THIS.Node.EmitOnNodeChange({
					'event': "device_remove",
					'rf_type': rf_type,
					'path': path,
					'dev': adaptor["path"].split('/')[2]
				})
				self.DeviceList.remove(adaptor)

	def OnTimerTriggerHandler(self, uuid, action):
		print ("({classname})# OnTimerTriggerHandler ...".format(classname=self.ClassName))

		if action == "On":
			value = 1
		elif action == "Off":
			value = 0
		else:
			return

		if self.MasterTX is not None:
			message = struct.pack("<BBBBBBBH", 0xDE, 0xAD, 0x1, 100, 4, int(uuid), 1, value)
			self.SendRFData(message, 5)
			sensor = self.FindSensor(int(uuid))
			sensor["value"] = value
			self.File.SaveJSON("db.json", self.DB)
			THIS.Node.EmitOnNodeChange({
				'event': "sensor_value_change",
				'sensor': {
					'addr': str(uuid),
					'rf_type': sensor["rf_type"],
					'value': value
				}
			})

	def UndefindHandler(self, sock, packet):
		print ("UndefindHandler")

	def SendRFData(self, message, repeat):
		if self.MasterTX is not None:
			str_message = ", ".join("{:02x}".format(ord(c)) for c in message)
			for x in range(repeat):
				print ("({classname})# [{0}] (RF TX) {1}".format(self.MasterTX["path"], str_message, classname=self.ClassName))
				data = self.MasterTX["dev"].Send(message)
				time.sleep(0.2)

	def FindSensor(self, addr):
		for sensor in self.DB["sensors"]:
			if sensor["addr"] == addr:
				return sensor
		return None
	
	def GetTimerHandlers(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		print ("({classname})# GetTimerHandlers ... payload: {0}".format(payload, classname=self.ClassName))

		data = self.Timer.GetTimers(str(payload["id"]))
		if data is None or data == "":
			data = {}
		
		return THIS.Node.BasicProtocol.BuildResponse(packet, data)
	
	def AppendTimerHandlers(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		print ("({classname})# AppendTimerHandlers ... payload: {0}".format(payload, classname=self.ClassName))

		self.Timer.AddTimer(payload["addr"], payload["timer"])

		return THIS.Node.BasicProtocol.BuildResponse(packet, {"status": "ok"})
	
	def RemoveTimerHandlers(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		print ("({classname})# RemoveTimerHandlers ... payload: {0}".format(payload, classname=self.ClassName))

		self.Timer.RemoveTimer(payload["addr"], payload["id"])

		return THIS.Node.BasicProtocol.BuildResponse(packet, {"status": "ok"}) 

	def SensorGraphHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		print ("({classname})# AppendSensorToDBHandler ... payload: {0}".format(payload, classname=self.ClassName))
		rf_type = payload["rf_type"]
		year 	= payload["year"]
		month 	= payload["month"]
		day 	= payload["day"]
		addr 	= payload["addr"]

		if rf_type == 3:
			graph_type = ["change"]
		elif rf_type == 4:
			graph_type = ["change"]
		elif rf_type == 5:
			graph_type = ["change","avg","avg"]
		elif rf_type == 6:
			graph_type = ["avg","avg"]

		try:
			data = self.SensorsDB.ReadDB(os.path.join(year, month, day, addr))
			graph, sensors = self.SensorsDB.SplitDataByHourSegment({
				"year": year,
				"month": month,
				"day": day
			}, data, graph_type)

			payload = {
				'graph': graph,
				'sensors': sensors
			}
			return THIS.Node.BasicProtocol.BuildResponse(packet, payload)
		except:
			return THIS.Node.BasicProtocol.BuildResponse(packet, {
				'graph': [],
				'sensors': 0
			})

	def AppendSensorToDBHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		print ("({classname})# AppendSensorToDBHandler ... payload: {0}".format(payload, classname=self.ClassName))

		item = self.FindSensor(payload["addr"])
		if item is None:
			sensor_type = int(payload["rf_type"]) - 2
			sensor = {
				"rf_type": payload["rf_type"], 
				"enable": 1, 
				"addr": payload["addr"], 
				"access_from_www": 1, 
				"value": 0, 
				"custom": {}, 
				"recording": 1, 
				"type": sensor_type, 
				"name": "New Sensor"
			}
			self.DB["sensors"].append(sensor)
			self.File.SaveJSON("db.json", self.DB)
			payload = {
				'sensors': self.DB["sensors"]
			}
			return THIS.Node.BasicProtocol.BuildResponse(packet, payload)
		return THIS.Node.BasicProtocol.BuildResponse(packet, {"status": "error"}) 
	
	def RemoveSensorToDBHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		print ("({classname})# RemoveSensorToDBHandler ... payload: {0}".format(payload, classname=self.ClassName))
		sensor	= self.FindSensor(payload["addr"])
		if sensor is not None:
			self.DB["sensors"].remove(sensor)
			self.File.SaveJSON("db.json", self.DB)
			payload = {
				'sensors': self.DB["sensors"]
			}
			return THIS.Node.BasicProtocol.BuildResponse(packet, payload)
		return THIS.Node.BasicProtocol.BuildResponse(packet, {"status": "error"})

	def SaveSensorToDBHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		print ("({classname})# SaveSensorToDBHandler ... payload: {0}".format(payload, classname=self.ClassName))
		addr	= payload["addr"]
		sensor	= self.FindSensor(addr)
		if sensor is not None:
			sensor["name"] 				= payload["name"]
			sensor["recording"] 		= payload["recording"]
			sensor["enable"] 			= payload["enable"]
			sensor["access_from_www"] 	= payload["access_from_www"]
			self.File.SaveJSON("db.json", self.DB)
			payload = {
				'sensors': self.DB["sensors"]
			}
			return THIS.Node.BasicProtocol.BuildResponse(packet, payload)
		return THIS.Node.BasicProtocol.BuildResponse(packet, {"status": "error"})

	def SetSensorAddrHandler(self, sock, packet):
		payload = THIS.Node.BasicProtocol.GetPayloadFromJson(packet)
		print ("({classname})# SetSensorAddrHandler ... dev: {0}, addr: {1}".format(payload["dev"], payload["addr"], classname=self.ClassName))
		for device in self.DeviceList:
			if payload["dev"] in device["path"]:
				adaptor = device
				break
		if adaptor is not None:
			data = adaptor["dev"].Send(struct.pack("<BBBBBB", 0xDE, 0xAD, 0x1, 150, 1, payload["addr"]))
			adaptor["addr"] = payload["addr"]

			devices = []
			for device in self.DeviceList:
				devices.append({
					'dev': device["path"].split('/')[2],
					'rf_type': device["rf_type"],
					'addr': device["addr"]
				})
			payload = {
				'config_sensors': devices
			}

			return THIS.Node.BasicProtocol.BuildResponse(packet, payload)

		return THIS.Node.BasicProtocol.BuildResponse(packet, {"status":"error"})
		
	def GetSensorInfoHandler(self, sock, packet):
		print ("({classname})# GetSensorInfoHandler ...".format(classname=self.ClassName))
		devices = []
		for device in self.DeviceList:
			devices.append({
				'dev': device["path"].split('/')[2],
				'rf_type': device["rf_type"],
				'addr': device["addr"]
			})
		payload = {
			'sensors': self.DB["sensors"],
			'devices': self.DB["confuguration"]["devices"],
			'config_sensors': devices
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
			message = struct.pack("<BBBBBBBH", 0xDE, 0xAD, 0x1, 100, 4, addr, 1, value)
			self.SendRFData(message, 5)
			sensor = self.FindSensor(addr)
			sensor["value"] = value
			self.File.SaveJSON("db.json", self.DB)
			THIS.Node.EmitOnNodeChange({
				'event': "sensor_value_change",
				'sensor': {
					'addr': str(addr),
					'rf_type': sensor["rf_type"],
					'value': value
				}
			})

		return THIS.Node.BasicProtocol.BuildResponse(packet, {})
	
	def OnMasterAppendNodeHandler(self, uuid, type, ip, port):
		print ("[OnMasterAppendNodeHandler]", str(uuid), str(type), str(ip), str(port))
	
	def OnMasterRemoveNodeHandler(self, uuid, type, ip, port):
		print ("[OnMasterRemoveNodeHandler]", str(uuid), str(type), str(ip), str(port))

	def OnGetNodeInfoHandler(self, info, online):
		print ("({classname})# Node Info Recieved ...\n\t{0}\t{1}\t{2}\t{3}".format(online, info["uuid"],info["name"],info["type"],classname=self.ClassName))
	
	def CheckDeviceType(self, adapter):
		data = adapter["dev"].Send(struct.pack("BBBB", 0xDE, 0xAD, 0x1, 52))
		direction 		= data[0]
		op_code			= data[1]
		content_length	= data[2]
		rf_type 		= data[3]
		print("({classname})# RF DEVICE FOUND ... {0}".format(rf_type, classname=self.ClassName))
		adapter["rf_type"] 	= rf_type
		if rf_type == 1:
			adapter["addr"] = 0
			self.MasterTX 	= adapter
			self.DB["confuguration"]["devices"]["tx"]["state"] = 1
			print("({classname})# MASTER TX Found ...".format(classname=self.ClassName))
			THIS.Node.EmitOnNodeChange({
				'event': "device_append",
				'rf_type': rf_type,
				'path': adapter["path"],
				'addr': 0
			})
		elif rf_type == 2:
			adapter["addr"] = 0
			self.MasterRX 	= adapter
			self.DB["confuguration"]["devices"]["rx"]["state"] = 1
			print("({classname})# MASTER RX Found ...".format(classname=self.ClassName))
			THIS.Node.EmitOnNodeChange({
				'event': "device_append",
				'rf_type': rf_type,
				'path': adapter["path"],
				'addr': 0
			})
		elif rf_type == 3:
			print("({classname})# SLAVE SWITCH Found ...".format(classname=self.ClassName))
			addr 			= data[4]
			adapter["addr"] = addr
			dev 			= adapter["path"].split('/')
			THIS.Node.EmitOnNodeChange({
				'event': "device_append",
				'rf_type': rf_type,
				'path': adapter["path"],
				'dev': dev[2],
				'addr': addr
			})
			self.DeviceList.append(adapter)
		elif rf_type == 4:
			print("({classname})# SLAVE MOTION (PIR) Found ...".format(classname=self.ClassName))
			addr 			= data[4]
			adapter["addr"] = addr
			dev 			= adapter["path"].split('/')
			THIS.Node.EmitOnNodeChange({
				'event': "device_append",
				'rf_type': rf_type,
				'path': adapter["path"],
				'dev': dev[2],
				'addr': addr
			})
			self.DeviceList.append(adapter)
		elif rf_type == 5:
			print("({classname})# SLAVE PIR and DHT11 Found ...".format(classname=self.ClassName))
			addr 			= data[4]
			adapter["addr"] = addr
			dev 			= adapter["path"].split('/')
			THIS.Node.EmitOnNodeChange({
				'event': "device_append",
				'rf_type': rf_type,
				'path': adapter["path"],
				'dev': dev[2],
				'addr': addr
			})
			self.DeviceList.append(adapter)
		elif rf_type == 6:
			print("({classname})# SLAVE DHT11 Found ...".format(classname=self.ClassName))
			addr 			= data[4]
			adapter["addr"] = addr
			dev 			= adapter["path"].split('/')
			THIS.Node.EmitOnNodeChange({
				'event': "device_append",
				'rf_type': rf_type,
				'path': adapter["path"],
				'dev': dev[2],
				'addr': addr
			})
			self.DeviceList.append(adapter)

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
		
		adapters = self.HW.Connect("2020")
		for adapter in adapters:
			self.CheckDeviceType(adapter)
		
		addrs = []
		for item in self.DB["sensors"]:
			if item["type"] == 1:
				addrs.append(str(item["addr"]))
				self.Timer.CreateTimer(str(item["addr"]), ["On", "Off"])
			
			self.SensorLastValue[item["addr"]] = {
				'value': item["value"],
				'ts': time.time(),
				'addr': item["addr"]
			}

		self.Timer.LoadClocks(addrs)
		self.Timer.Run()
		
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
					if sensor["type"] == 1:
						message = struct.pack("<BBBBBBBH", 0xDE, 0xAD, 0x1, 100, 4, sensor["addr"], 1, sensor["value"])
						self.SendRFData(message, 1)

			offline_sensors = []
			online_sensors = []
			for key in self.SensorLastValue:
				if self.CurrentTimestamp - self.SensorLastValue[key]["ts"] > 30:
					offline_sensors.append(self.SensorLastValue[key])
				else:
					online_sensors.append(self.SensorLastValue[key])
			
			THIS.Node.EmitOnNodeChange({
				'event': "status_sensors",
				'offline_sensors': offline_sensors,
				'online_sensors': online_sensors
			})

Node = MkSSlaveNode.SlaveNode()
THIS = Context(Node)

def signal_handler(signal, frame):
	THIS.HW.Disconnect()
	time.sleep(0.5)
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

'''
-----
NOTES
-----

APPEND NEW SENSOR
-------
Python:
-------
1. Add "rf_type" to CheckDeviceType().
2. If data is not one sensor but several need to add handler to AdaptorAsyncDataCallback().
------------------
Javascript + HTML:
------------------
3. Add handler to OpenModal().
4. Add handler to SensorUIGenerate().
5. Add handler to OnNodeChangeEvent().
'''
