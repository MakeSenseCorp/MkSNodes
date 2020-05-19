#!/usr/bin/python
import os
import sys
import signal
import json
import time
if sys.version_info[0] < 3:
	import thread
else:
	import _thread
import threading

from mksdk import MkSGlobals
from mksdk import MkSFile
from mksdk import MkSStandaloneNode
from mksdk import MkSShellExecutor
from mksdk import MkSExternalProcess
from mksdk import MkSUtils

class Context():
	def __init__(self, node):
		self.ClassName 						= "Guardian Application"
		self.Interval						= 10
		self.CurrentTimestamp 				= time.time()
		self.File 							= MkSFile.File()
		self.Node							= node
		self.SystemLoaded					= False
		self.RequestHandlers				= {
			'undefined':					self.UndefindHandler
		}
		self.ResponseHandlers				= {
		}
		self.InstalledNodesDB				= None
		self.ServicesDB 					= None
		self.RunningServices				= []
		self.NetworkDevicesList 			= []
		self.Node.DebugMode 				= True

	def UndefindHandler(self, packet):
		print ("({classname})# UndefindHandler".format(classname=self.ClassName))
		
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
	
	def WSDataArrivedHandler(self, sock, packet):
		try:
			command = packet['data']['header']['command']
			message = self.RequestHandlers[command](sock, packet)
			THIS.Node.Network.SendWebSocket(message)
		except Exception as e:
			print("({classname})# ERROR - Data arrived issue\n(EXEPTION)# {error}".format(
				classname=self.ClassName,
				error=str(e)))
	
	def WSConnectedHandler(self):
		print ("({classname})# Connection to Gateway was established.".format(classname=self.ClassName))

	def WSConnectionClosedHandler(self):
		print ("({classname})# Connection to Gateway was lost.".format(classname=self.ClassName))

	def NodeSystemLoadedHandler(self):
		self.Node.LogMSG("({classname})# Node system was succesfully loaded.".format(classname=self.ClassName))
		self.SystemLoaded = True

		self.Node.LogMSG("({classname})# Loading MASTER Node ...".format(classname=self.ClassName))
		master_path = os.path.join(self.Node.MKSPath,"nodes","master")
		node = MkSExternalProcess.ExternalProcess()
		node.CallProcess("python app.py", master_path, "")
		self.Node.LogMSG("({classname})# MATER Node Loaded ...".format(classname=self.ClassName))

	def OnNodeWorkTick(self):
		if (self.Node.Ticker % 20) == 0:
			print("({classname})# MASTER is ALIVE ...".format(classname=self.ClassName))

Node = MkSStandaloneNode.StandaloneNode(17999)
THIS = Context(Node)

def signal_handler(signal, frame):
	THIS.Node.Stop()

def main():
	signal.signal(signal.SIGINT, signal_handler)

	THIS.Node.SetLocalServerStatus(True)
	THIS.Node.SetWebServiceStatus(False)

	# Node callbacks
	THIS.Node.GatewayDataArrivedCallback			= THIS.WSDataArrivedHandler
	THIS.Node.GatewayConnectedCallback 				= THIS.WSConnectedHandler
	THIS.Node.OnWSConnectionClosed 					= THIS.WSConnectionClosedHandler
	THIS.Node.NodeSystemLoadedCallback				= THIS.NodeSystemLoadedHandler
	THIS.Node.OnApplicationRequestCallback			= THIS.OnApplicationCommandRequestHandler
	THIS.Node.OnApplicationResponseCallback			= THIS.OnApplicationCommandResponseHandler

	# Run Node
	print("(Node)# Start Node ...")
	THIS.Node.Run(THIS.OnNodeWorkTick)
	
	print("(Node)# Exit Node ...")

if __name__ == "__main__":
	main()
