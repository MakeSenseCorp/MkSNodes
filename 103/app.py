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
from mksdk import MkSNode
from mksdk import MkSSlaveNode
from mksdk import MkSLocalHWConnector
from mksdk import MkSUSBAdaptor
from mksdk import MkSProtocol
from mksdk import MkSUtils

from flask import Response, request

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
		self.CustomRequestHandlers		= {
			'get_online_devices':		self.GetOnlineDevicesHandler
		}
		self.CustomResponseHandlers		= {
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
				self.Networks.append(net)

		for network in self.Networks:
			thread.start_new_thread(self.PingDevicesThread, (network, range(1,100), ))
			thread.start_new_thread(self.PingDevicesThread, (network, range(101,200), ))
	
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

	def PingDevicesThread(self, network, range):
		while (self.ThreadWorking is True):
			for client in range:
				if (self.ThreadWorking is False):
					return
				ip = network + str(client)
				res = self.Ping(ip)
				self.ThreadLock.acquire()
				if (res is True):
					print(ip, "ONLINE")
					self.OnlineDevices[ip] = [ip, datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
				else:
					print(ip, "OFFLINE")
				self.ThreadLock.release()

	def UndefindHandler(self, message_type, source, data):
		print ("UndefindHandler")
	
	# { 
	# 	u'direction': u'proxy_request', 
	# 	u'command': u'send_email', 
	# 	u'piggybag': 0, 
	# 	u'payload': {
	# 		u'header': {
	# 			u'source': u'ac6de837-9863-72a9-c789-a0aae7e9d021', 
	# 			u'destination': u'ac6de837-9863-72a9-c789-a0aae7e9d023'
	# 		}, u'data': {
	# 			u'json': {
	# 				u'body': u'Hello', 
	# 				u'to': [u'yevgeniy.kiveisha@gmail.com'], 
	# 				u'type': u'text', 
	# 				u'subject': u'Test'
	# 			}, 
	# 			u'request': u'task_order'
	# 		}
	# 	}
	# }
	
	def GetOnlineDevicesHandler(self, sock, packet):
		print ("GetOnlineDevicesHandler", packet, self.OnlineDevices)
		
		listOfDevice = []
		for key in self.OnlineDevices:
			listOfDevice.append(self.OnlineDevices[key])

		THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
			'online_devices': listOfDevice
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
Node 	= MkSNode.Node("IP Scanner Service", Service)
THIS 	= Context(Node)

def signal_handler(signal, frame):
	THIS.ThreadWorking = False
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
	THIS.ThreadWorking = False
	print ("Exit Node ...")

if __name__ == "__main__":
    main()
