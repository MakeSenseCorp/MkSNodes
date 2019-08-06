#!/usr/bin/python
import os
import sys
import gc
import signal
import json
import time
import thread
import threading
import logging
logging.basicConfig(
	filename='app.log',
	level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

import subprocess
import urllib2
import urllib

from mksdk import MkSFile
from mksdk import MkSNode
from mksdk import MkSSlaveNode
from mksdk import MkSLocalHWConnector
from mksdk import MkSUSBAdaptor
from mksdk import MkSProtocol

from flask import Response, request

class EthernetDeviceScanner():
	def __init__(self):
		self.ObjName 			= "EthernetDeviceScanner"
		self.IPList				= []
		self.ThreadCounter 		= 0
		self.ThreadCounterLock	= threading.Lock()

	def Ping(self, address):
		response = subprocess.call("ping -c 1 %s" % address,
				shell=True,
				stdout=open('/dev/null', 'w'),
				stderr=subprocess.STDOUT)
		# Check response
		if response == 0:
			return True
		else:
			return False
	
	def PingThread(self, address):
		res = self.Ping(address)
		self.ThreadCounterLock.acquire()
		if True == res:
			self.IPList.append(address)
		self.ThreadCounter += 1
		self.ThreadCounterLock.release()

	def Scan(self, network, index):
		self.ThreadCounter 		= 0
		self.Network		 	= network
		self.IPCount 			= index[1] - index[0]

		if (self.IPCount < 0):
			return []
		
		for i in range(index[0], index[1]):
			address = self.Network + str(i)
			thread.start_new_thread(self.PingThread, (address,))
		
		while (self.ThreadCounter != self.IPCount):
			pass
		
		return self.IPList

class SonoffScanner():
	def __init__(self):
		self.ObjName 			= "SonoffScanner"
		self.Devices			= []
		self.ThreadCounter 		= 0
		self.ThreadCounterLock	= threading.Lock()

	def SendRequest(self, url):
		try:
			res = urllib2.urlopen("http://" + url, timeout = 2).read()
			if res in "Sonoff":
				return True
		except urllib2.HTTPError as e:
			return False
		except:
			pass
		
		return False
	
	def RequestThread(self, address):
		res = self.SendRequest(address)
		print(res)
		self.ThreadCounterLock.acquire()
		if True == res:
			self.Devices.append(address)
		self.ThreadCounter += 1
		self.ThreadCounterLock.release()

	def Scan(self, addresses):
		self.ThreadCounter 		= 0
		self.CamerasCount 		= len(addresses)

		if (self.CamerasCount < 0):
			return []
		
		for ip in addresses:
			thread.start_new_thread(self.RequestThread, (ip,))
		
		while (self.ThreadCounter != self.CamerasCount):
			pass
		
		return self.Devices

class Sonoff():
	def __init__(self, ip):
		self.Address 	= ip
		self.Id 		= ""
	
	def SonnofRequest(self, request):
		try:
			res = urllib2.urlopen("http://" + self.Address + "/" + request, timeout = 2).read()
			return res
		except urllib2.HTTPError as e:
			return ""
		except:
			pass
		
		return ""
	
	def GetSwitchID(self):
		res = self.SonnofRequest("id")
		res = res.replace("'", "\"")
		jsonRes = json.loads(res)
		
		if jsonRes is not None:
			return jsonRes["id"]
		
		return ""
	
	def GetIp(self):
		return self.Address
	
	def SetSwitchOn(self):
		return self.SonnofRequest("on")
	
	def SetSwitchOff(self):
		return self.SonnofRequest("off")

class Context():
	def __init__(self, node):
		self.Interval					= 10
		self.CurrentTimestamp 			= time.time()
		self.Node						= node
		# States
		self.States = {
		}
		# Handlers
		self.Handlers					= {
			'undefined':				self.UndefindHandler
		}
		self.CustomRequestHandlers				= {
			'switch_on': 							self.SwitchOnHandler,
			'switch_off': 							self.SwitchOffHandler,
		}
		self.CustomResponseHandlers				= {
		}

		self.DB							= None
		self.DeviceScanner 				= EthernetDeviceScanner()
		self.Switches 					= []
		self.ObjSwitches				= []
	
	def UndefindHandler(self, message_type, source, data):
		print ("UndefindHandler")
	
	# CustomRequestHandlers
	def SwitchOnHandler(self, sock, packet):
		print("SwitchOnHandler")
		for item in self.ObjSwitches:
			if (item.GetIp() in packet["payload"]["data"]["ip"]):
				res = item.SetSwitchOn()
				if ("on" not in res):
					res = "error"
				THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
					'return_code': 'on'
				})
				return
		
		THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
			'return_code': 'error'
		})
	
	def SwitchOffHandler(self, sock, packet):
		print("SwitchOffHandler")
		for item in self.ObjSwitches:
			if (item.GetIp() in packet["payload"]["data"]["ip"]):
				res = item.SetSwitchOff()
				if ("off" not in res):
					res = "error"
				THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
					'return_code': 'on'
				})
				return
		
		THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
			'return_code': 'error'
		})

	# Websockets
	def WSDataArrivedHandler(self, message_type, source, data):
		command = data['device']['command']
		self.Handlers[command](message_type, source, data)

	def WSConnectedHandler(self):
		print ("WSConnectedHandler")

	def WSConnectionClosedHandler(self):
		print ("WSConnectionClosedHandler")

	def NodeSystemLoadedHandler(self):
		print ("NodeSystemLoadedHandler")
		# Loading local database
		jsonSensorStr = self.Node.GetFileContent("db.json")
		if jsonSensorStr != "":
			self.DB = json.loads(jsonSensorStr)
			if self.DB is not None:
				for item in self.DB["switches"]:
					self.Switches.append(item)
		
		devices = self.DeviceScanner.Scan("192.168.0.", [1,64])
		print(devices)
		
		scanner = SonoffScanner()
		ips = scanner.Scan(devices)
		print(ips)
		
		dbSwitches = self.DB["switches"]
		for ip in ips:
			switch = Sonoff(ip)
			id = switch.GetSwitchID()
			print ("[Switch]>", "NodeSystemLoadedHandler", id, ip)
			
			switchFound = False
			# Update switch IP (if it was changed)
			for itemSwitch in dbSwitches:
				if id != "" and id in itemSwitch["id"]:
					# Update DB with current IP
					itemSwitch["ip"] = ip
					self.ObjSwitches.append(switch)
					switchFound = True
					print ("[Switch]>", "NodeSystemLoadedHandler - Switch UPDATED")
					break
			
			if switchFound is False:
				print ("[Switch]>", "NodeSystemLoadedHandler - NEW SWITCH")
				# Append new camera.
				dbSwitches.append({
								'id': str(id),
								'ip': str(ip),
								'name': 'Switch_' + str(id),
								'enable':1,
								'mac': 'AA:AA:AA:AA:AA:AA'
				})
				self.ObjSwitches.append(switch)
		
		self.DB["switches"] = dbSwitches
		# Save new camera to database
		self.Node.SetFileContent("db.json", json.dumps(self.DB))
	
	def OnMasterFoundHandler(self, masters):
		print ("OnMasterFoundHandler")

	def OnMasterSearchHandler(self):
		print ("OnMasterSearchHandler")

	def OnMasterDisconnectedHandler(self):
		print ("OnMasterDisconnectedHandler")

	def OnDeviceConnectedHandler(self):
		print ("OnDeviceConnectedHandler")

	def OnLocalServerStartedHandler(self):
		print ("OnLocalServerStartedHandler")

	def OnAceptNewConnectionHandler(self, sock):
		print ("OnAceptNewConnectionHandler")

	def OnTerminateConnectionHandler(self, sock):
		print ("OnTerminateConnectionHandler")

	def OnGetSensorInfoRequestHandler(self, packet, sock):
		print ("OnGetSensorInfoRequestHandler")
		payload = {
			'db': self.DB
		}
		THIS.Node.LocalServiceNode.SendSensorInfoResponse(sock, packet, payload)

	def OnSetSensorInfoRequestHandler(self, packet, sock):
		print ("OnSetSensorInfoRequestHandler")
	
	def OnCustomCommandRequestHandler(self, sock, json_data):
		print ("OnCustomCommandRequestHandler")
		command = json_data['command']
		if command in self.CustomRequestHandlers:
			self.CustomRequestHandlers[command](sock, json_data)

	def OnCustomCommandResponseHandler(self, sock, json_data):
		print ("OnCustomCommandResponseHandler")
		command = json_data['command']
		if command in self.CustomResponseHandlers:
			self.CustomResponseHandlers[command](sock, json_data)

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
		THIS.Node.LocalServiceNode.AppendFaceRestTable(endpoint="/get/node_info/<key>", 						endpoint_name="get_node_info", 			handler=THIS.GetNodeInfoHandler)
		THIS.Node.LocalServiceNode.AppendFaceRestTable(endpoint="/set/node_info/<key>/<id>", 					endpoint_name="set_node_info", 			handler=THIS.SetNodeInfoHandler, 	method=['POST'])
		THIS.Node.LocalServiceNode.AppendFaceRestTable(endpoint="/get/node_sensors_info/<key>", 				endpoint_name="get_node_sensors", 		handler=THIS.GetSensorsInfoHandler)
		THIS.Node.LocalServiceNode.AppendFaceRestTable(endpoint="/set/node_sensor_info/<key>/<id>/<value>", 	endpoint_name="set_node_sensor_value", 	handler=THIS.SetSensorInfoHandler)

	def WorkingHandler(self):
		if time.time() - self.CurrentTimestamp > self.Interval:
			print ("WorkingHandler")

			self.CheckingForUpdate = True
			self.CurrentTimestamp = time.time()

			for idx, item in enumerate(THIS.Node.LocalServiceNode.GetConnections()):
				print ("  ", str(idx), item.LocalType, item.UUID, item.IP, item.Port, item.Type)

Service = MkSSlaveNode.SlaveNode()
Node 	= MkSNode.Node("Sonoff Manager", Service)
THIS 	= Context(Node)

def signal_handler(signal, frame):
	THIS.Node.Stop()

def main():
	signal.signal(signal.SIGINT, signal_handler)
	THIS.Node.SetLocalServerStatus(True)
	
	# Node callbacks
	THIS.Node.OnWSDataArrived 										= THIS.WSDataArrivedHandler
	THIS.Node.OnWSConnected 										= THIS.WSConnectedHandler
	THIS.Node.OnWSConnectionClosed 									= THIS.WSConnectionClosedHandler
	THIS.Node.OnNodeSystemLoaded									= THIS.NodeSystemLoadedHandler
	THIS.Node.OnDeviceConnected										= THIS.OnDeviceConnectedHandler
	# Local service callbacks (TODO - please bubble these callbacks via Node)
	THIS.Node.LocalServiceNode.OnMasterFoundCallback				= THIS.OnMasterFoundHandler
	THIS.Node.LocalServiceNode.OnMasterSearchCallback				= THIS.OnMasterSearchHandler
	THIS.Node.LocalServiceNode.OnMasterDisconnectedCallback			= THIS.OnMasterDisconnectedHandler
	THIS.Node.LocalServiceNode.OnLocalServerStartedCallback			= THIS.OnLocalServerStartedHandler
	THIS.Node.LocalServiceNode.OnLocalServerListenerStartedCallback = THIS.OnLocalServerListenerStartedHandler
	THIS.Node.LocalServiceNode.OnAceptNewConnectionCallback			= THIS.OnAceptNewConnectionHandler
	THIS.Node.LocalServiceNode.OnTerminateConnectionCallback 		= THIS.OnTerminateConnectionHandler
	THIS.Node.LocalServiceNode.OnGetSensorInfoRequestCallback 		= THIS.OnGetSensorInfoRequestHandler
	THIS.Node.LocalServiceNode.OnSetSensorInfoRequestCallback 		= THIS.OnSetSensorInfoRequestHandler
	# TODO - On file upload event.
	THIS.Node.LocalServiceNode.OnCustomCommandRequestCallback		= THIS.OnCustomCommandRequestHandler
	THIS.Node.LocalServiceNode.OnCustomCommandResponseCallback		= THIS.OnCustomCommandResponseHandler
	
	THIS.Node.Run(THIS.WorkingHandler)
	print ("Exit Node ...")

if __name__ == "__main__":
    main()
