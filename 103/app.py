#!/usr/bin/python
import os
import sys
import signal
import json
import time
import thread
import threading
import logging
import subprocess
from datetime import datetime

from mksdk import MkSFile
from mksdk import MkSSlaveNode
from mksdk import MkSLocalHWConnector
from mksdk import MkSUSBAdaptor
from mksdk import MkSProtocol
from mksdk import MkSUtils

from flask import Response, request

class Context():
	def __init__(self, node):
		self.ClassName 					= "IP Scanner"
		self.Interval					= 10
		self.CurrentTimestamp 			= time.time()
		self.Node						= node
		# States
		self.States = {
		}
		# Handlers
		self.RequestHandlers		= {
			'get_online_devices':		self.GetOnlineDevicesHandler,
			'undefined':				self.UndefindHandler
		}
		self.ResponseHandlers		= {
			'undefined':				self.UndefindHandler
		}

		# TODO - Find these networks automaticaly
		self.Networks					= []
		self.OnlineDevices 				= {}
		self.ThreadWorking 				= True
		self.ThreadLock					= threading.Lock()
		
		self.Utilities = MkSUtils.Utils()
		
		items = self.Utilities.GetSystemIPs()
		for item in items:
			if ("127.0.0" not in item[0]):
				net = ".".join(item[0].split('.')[0:-1]) + '.'
				if net not in self.Networks:
					self.Networks.append(net)
		
		for network in self.Networks:
			thread.start_new_thread(self.PingDevicesThread, (network, range(1,100), ))
			thread.start_new_thread(self.PingDevicesThread, (network, range(101,200), ))

	def PingDevicesThread(self, network, range):
		while (self.ThreadWorking is True):
			for client in range:
				if (self.ThreadWorking is False):
					return
				ip = network + str(client)
				res = MkSUtils.Ping(ip)
				self.ThreadLock.acquire()
				if (res is True):
					self.OnlineDevices[ip] = {
						'ip':		ip, 
						'datetime':	datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
						'ts':		time.time()
					}
				self.ThreadLock.release()
	
	def DisconnectedAddressesMonitorThread(self):
		pass

	def UndefindHandler(self, message_type, source, data):
		print ("UndefindHandler")
	
	def GetOnlineDevicesHandler(self, sock, packet):
		print ("({classname})# Online device request ...".format(classname=self.ClassName))
		
		listOfDevice = []
		for key in self.OnlineDevices:
			listOfDevice.append(self.OnlineDevices[key]["ip"])

		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'online_devices': listOfDevice
		})
	
	# Websockets
	def NodeSystemLoadedHandler(self):
		print ("({classname})# Node system loaded ...".format(classname=self.ClassName))
	
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
			self.CurrentTimestamp = time.time()

			print("\nTables:")
			for idx, item in enumerate(THIS.Node.GetConnections()):
				print ("  {0}\t{1}\t{2}\t{3}\t{4}\t{5}".format(str(idx),item.LocalType,item.UUID,item.IP,item.Port,item.Type))
			print("")
			network_device_to_delete = []
			for key in self.OnlineDevices:
				network_device = self.OnlineDevices[key]
				if (MkSUtils.Ping(network_device["ip"]) is False):
					print("Offline device " + network_device["ip"])
					network_device_to_delete.append(key)
				else:
					print ("  {0}\t{1}\t{2}".format(network_device["ip"],network_device["datetime"],network_device["ts"]))
			
			for key in network_device_to_delete:
				del self.OnlineDevices[key]
			
			listOfDevice = []
			for key in self.OnlineDevices:
				listOfDevice.append(self.OnlineDevices[key]["ip"])
			THIS.Node.EmitOnNodeChange({
				'online_devices': listOfDevice
			})

Node = MkSSlaveNode.SlaveNode()
THIS = Context(Node)

def signal_handler(signal, frame):
	THIS.ThreadWorking = False
	THIS.Node.Stop()

def main():
	signal.signal(signal.SIGINT, signal_handler)
	THIS.Node.SetLocalServerStatus(True)
	
	# Node callbacks
	THIS.Node.NodeSystemLoadedCallback						= THIS.NodeSystemLoadedHandler
	THIS.Node.OnLocalServerListenerStartedCallback 			= THIS.OnLocalServerListenerStartedHandler	
	THIS.Node.OnApplicationRequestCallback					= THIS.OnApplicationCommandRequestHandler
	THIS.Node.OnApplicationResponseCallback					= THIS.OnApplicationCommandResponseHandler
	
	THIS.Node.Run(THIS.WorkingHandler)
	THIS.ThreadWorking = False
	print ("Exit Node ...")

if __name__ == "__main__":
    main()

