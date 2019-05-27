#!/usr/bin/python
import os
import sys
import signal
import json
import time
import thread
import threading

from mksdk import MkSGlobals
from mksdk import MkSFile
from mksdk import MkSUSBAdaptor
from mksdk import MkSProtocol
from mksdk import MkSConnectorArduino
from mksdk import MkSNode
from mksdk import MkSMasterNode
from mksdk import MkSShellExecutor

class Context():
	def __init__(self, node):
		self.Interval			= 10
		self.CurrentTimestamp 	= time.time()
		self.Node				= node
		self.SystemLoaded		= False
		# Handlers for remote module (websocket)
		self.Handlers					= {
			'get_connections_list':			self.GetConnectionsListRequestHandler,
			'get_installed_nodes_list':		self.GetInstalledNodesListRequestHandler,
			'undefined':					self.UndefindHandler
		}
		# Handlers for local module (socket)
		self.CustomRequestHandlers				= {
			'get_connections_list':			self.GetConnectionsListRequestHandler,
			'get_installed_nodes_list':		self.GetInstalledNodesListRequestHandler,
		}
		self.CustomResponseHandlers				= {
		}

	def UndefindHandler(self, packet):
		print "UndefindHandler"
	
	def GetConnectionsListRequestHandler(self, packet):
		print "GetConnectionsListRequestHandler"
		if THIS.Node.Network.GetNetworkState() is "CONN":
			connections = []
			for item in THIS.Node.LocalServiceNode.GetConnections():
				connections.append({
					'local_type':	item.LocalType,
					'uuid':			item.UUID,
					'ip':			item.IP,
					'port':			item.Port,
					'type':			item.Type
				})
			payload = {
				'connections': connections
			}
			message = THIS.Node.Network.BuildResponse(packet, payload)
			THIS.Node.Network.SendWebSocket(message)

	def GetInstalledNodesListRequestHandler(self, packet):
		print "GetInstalledNodesListRequestHandler"
	
	def OnCustomCommandRequestHandler(self, sock, packet):
		print ("OnCustomCommandRequestHandler")
		command = packet['command']
		if command in self.CustomRequestHandlers:
			self.CustomRequestHandlers[command](sock, packet)

	def OnCustomCommandResponseHandler(self, sock, packet):
		print ("OnCustomCommandResponseHandler")
		command = packet['command']
		if command in self.CustomResponseHandlers:
			self.CustomResponseHandlers[command](sock, packet)

	'''
		{
			'header': {	
				'source': 'WEBFACE',
				'destination': 'ac6de837-9863-72a9-c789-a0aae7e9d020', 
				'message_type': 'DIRECT'
				}, 
			'piggybag': {
				'identifier': 9
			}, 
			'data': {
				'header': {
					'timestamp': 1554159118729, 
					'command': 'command'
				}, 
				'payload': {
				}
			},
			'user': {
				'key': 'ac6de837-7863-72a9-c789-a0aae7e9d93e'
			},
			'additional': {				
			}
		}
		'''
	
	# Websockets
	def WSDataArrivedHandler(self, packet):
		command = packet['data']['header']['command']
		self.Handlers[command](packet)
	
	def WSConnectedHandler(self):
		print "WSConnectedHandler"

	def WSConnectionClosedHandler(self):
		print "WSConnectionClosedHandler"

	def NodeSystemLoadedHandler(self):
		print "NodeSystemLoadedHandler"
		self.SystemLoaded = True

	def OnNodeWorkTick(self):
		if time.time() - self.CurrentTimestamp > self.Interval:			
			self.CheckingForUpdate = True
			self.CurrentTimestamp = time.time()

			for idx, item in enumerate(THIS.Node.LocalServiceNode.GetConnections()):
				print "  ", str(idx), item.LocalType, item.UUID, item.IP, item.Port, item.Type

Service = MkSMasterNode.MasterNode()
Node 	= MkSNode.Node("MASTER", Service)
THIS 	= Context(Node)

def signal_handler(signal, frame):
	THIS.Node.Stop()

def main():
	signal.signal(signal.SIGINT, signal_handler)

	THIS.Node.SetLocalServerStatus(True)
	THIS.Node.SetWebServiceStatus(True)

	# Node callbacks
	THIS.Node.OnWSDataArrived		= THIS.WSDataArrivedHandler
	THIS.Node.OnWSConnected 		= THIS.WSConnectedHandler
	THIS.Node.OnWSConnectionClosed 	= THIS.WSConnectionClosedHandler
	THIS.Node.OnNodeSystemLoaded	= THIS.NodeSystemLoadedHandler

	# Local service callbacks (TODO - please bubble these callbacks via Node)
	THIS.Node.LocalServiceNode.OnCustomCommandRequestCallback		= THIS.OnCustomCommandRequestHandler
	THIS.Node.LocalServiceNode.OnCustomCommandResponseCallback		= THIS.OnCustomCommandResponseHandler

	# Run Node
	THIS.Node.Run(THIS.OnNodeWorkTick)
	
	print "Exit Node ..."

if __name__ == "__main__":
	main()
