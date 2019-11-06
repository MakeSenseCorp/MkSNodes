#!/usr/bin/python
import os
import sys
import signal
import json
import time
import thread
import threading

#logging.basicConfig(
#	 filename='app.log',
#	 level=logging.DEBUG,
#    format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
#    datefmt='%Y-%m-%d %H:%M:%S',
#)

from mksdk import MkSFile
from mksdk import MkSNode
from mksdk import MkSSlaveNode
from mksdk import MkSLocalHWConnector
from mksdk import MkSUSBAdaptor
from mksdk import MkSProtocol

from flask import Response, request

class Context():
	def __init__(self, node):
		self.ClassName 					= "Node Application"
		self.Interval					= 10
		self.CurrentTimestamp 			= time.time()
		self.Node						= node
		# States
		self.States = {
		}
		# Handlers
		self.RequestHandlers			= {
			'undefined':				self.UndefindHandler
		}
		self.ResponseHandlers			= {
			'undefined':				self.UndefindHandler
		}
	
	def OnCustomCommandRequestHandler(self, sock, packet):
		print ("({classname})# REQUEST".format(classname=self.ClassName))
		command = packet['command']
		if command in self.RequestHandlers:
			return self.RequestHandlers[command](sock, packet)

	def OnCustomCommandResponseHandler(self, sock, packet):
		print ("({classname})# RESPONSE".format(classname=self.ClassName))
		command = packet['command']
		if command in self.ResponseHandlers:
			self.ResponseHandlers[command](sock, packet)

	def UndefindHandler(self, sock, packet):
		print ("UndefindHandler")

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
		print ("({classname})# OnLocalServerStartedHandler".format(classname=self.ClassName))

	def OnAceptNewConnectionHandler(self, sock):
		print ("OnAceptNewConnectionHandler")

	def OnTerminateConnectionHandler(self, sock):
		print ("OnTerminateConnectionHandler")

	# Request from local network.
	def OnGetSensorInfoRequestHandler(self, packet, sock):
		print ("OnGetSensorInfoRequestHandler")

	# Request from local network.
	def OnSetSensorInfoRequestHandler(self, packet, sock):
		print ("OnSetSensorInfoRequestHandler")

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
			print ("({classname})# WorkingHandler".format(classname=self.ClassName))

			self.CheckingForUpdate = True
			self.CurrentTimestamp = time.time()

			for idx, item in enumerate(THIS.Node.GetConnections()):
				print ("  ", str(idx), item.LocalType, item.UUID, item.IP, item.Port, item.Type)

Node = MkSSlaveNode.SlaveNode()
THIS = Context(Node)

def signal_handler(signal, frame):
	THIS.Node.Stop()

def main():
	signal.signal(signal.SIGINT, signal_handler)
	THIS.Node.SetLocalServerStatus(True)
	
	# Node callbacks
	THIS.Node.OnNodeSystemLoaded					= THIS.NodeSystemLoadedHandler
	THIS.Node.OnDeviceConnected						= THIS.OnDeviceConnectedHandler
	THIS.Node.OnMasterFoundCallback					= THIS.OnMasterFoundHandler
	THIS.Node.OnMasterSearchCallback				= THIS.OnMasterSearchHandler
	THIS.Node.OnMasterDisconnectedCallback			= THIS.OnMasterDisconnectedHandler
	THIS.Node.OnLocalServerStartedCallback			= THIS.OnLocalServerStartedHandler
	THIS.Node.OnLocalServerListenerStartedCallback 	= THIS.OnLocalServerListenerStartedHandler
	THIS.Node.OnAceptNewConnectionCallback			= THIS.OnAceptNewConnectionHandler
	THIS.Node.OnTerminateConnectionCallback 		= THIS.OnTerminateConnectionHandler
	THIS.Node.OnGetSensorInfoRequestCallback 		= THIS.OnGetSensorInfoRequestHandler
	THIS.Node.OnSetSensorInfoRequestCallback 		= THIS.OnSetSensorInfoRequestHandler

	THIS.Node.OnApplicationRequestCallback			= THIS.OnCustomCommandRequestHandler
	THIS.Node.OnApplicationResponseCallback			= THIS.OnCustomCommandResponseHandler
	
	THIS.Node.Run(THIS.WorkingHandler)
	print ("Exit Node ...")

if __name__ == "__main__":
    main()
