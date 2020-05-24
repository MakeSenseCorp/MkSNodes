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
			'get_node_status':				self.GetNodeStatusHandler
		}
		self.InstalledNodesDB				= None
		self.ServicesDB 					= None
		self.RunningServices				= []
		self.NetworkDevicesList 			= []
		self.Node.DebugMode 				= True
		# Members
		self.MasterConnection				= False
		self.MasterSocket					= None
		self.MasterStatus					= None

	def UndefindHandler(self, sock, packet):
		print ("({classname})# UndefindHandler".format(classname=self.ClassName))
	
	def GetNodeStatusHandler(self, sock, packet):
		payload = self.Node.BasicProtocol.GetPayloadFromJson(packet)
		print ("({classname})# Master status '{0}'".format(payload,classname=self.ClassName))
		self.MasterStatus = payload
		
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
			return self.RequestHandlers[command](sock, packet)
		except Exception as e:
			print("({classname})# ERROR - Data arrived issue\n(EXEPTION)# {error}".format(
				classname=self.ClassName,
				error=str(e)))
	
	def WSConnectedHandler(self):
		print ("({classname})# Connection to Gateway was established.".format(classname=self.ClassName))

	def WSConnectionClosedHandler(self):
		print ("({classname})# Connection to Gateway was lost.".format(classname=self.ClassName))

	def LoadMasterNode(self):
		print("({classname})# Loading MASTER ...".format(classname=self.ClassName))
		master_path = os.path.join(self.Node.MKSPath,"nodes","master")
		node = MkSExternalProcess.ExternalProcess()
		node.CallProcess("python app.py", master_path, "")
	
	def GetPythonProcs(self, mypid):
		procs = []
		for proc in [x.rstrip('\n').split(' ', 1) for x in os.popen('ps h -eo pid:1,command | grep python')]:
			if "python app.py" in proc[1]:
				if int(proc[0]) != mypid:
					procs.append(proc)
		return procs
	
	def TerminateProc(self, pid):
		os.kill(pid, signal.SIGTERM)
	
	def TerminatePythonProcs(self):
		print("({classname})# Terminating all processes ...".format(classname=self.ClassName))
		# Terminate all MKS python processes
		for proc in self.GetPythonProcs(self.Node.MyPID):
			self.TerminateProc(int(proc[0]))
	
	def StartSystem(self):
		self.TerminatePythonProcs()
		time.sleep(2)
		self.LoadMasterNode()
		time.sleep(2)
		self.MasterSocket, self.MasterConnection = self.Node.ConnectNode(self.Node.MyLocalIP, 16999)
		self.Node.LogMSG("({classname})# [StartSystem] {0}".format(self.MasterConnection, classname=self.ClassName))

	def NodeSystemLoadedHandler(self):
		self.Node.LogMSG("({classname})# Node system was succesfully loaded.".format(classname=self.ClassName))
		self.SystemLoaded = True
		self.StartSystem()
		#self.MasterSocket, self.MasterConnection = self.Node.ConnectNode()
		
	def OnNodeWorkTick(self):
		if (self.Node.Ticker % 10) == 0:
			self.Node.LogMSG("({classname})# Live ... ({0})".format(self.Node.Ticker, classname=self.ClassName))
			if self.MasterConnection is True:
				message = self.Node.BasicProtocol.BuildRequest("DIRECT", "MASTER", self.Node.UUID, "get_node_status", {}, {})
				packet  = self.Node.BasicProtocol.AppendMagic(message)
				self.Node.AppendTXRequest(self.MasterSocket, packet)
			else:
				self.StartSystem()

Node = MkSStandaloneNode.StandaloneNode(17999)
THIS = Context(Node)

def signal_handler(signal, frame):
	THIS.Node.Stop("Accepted signal from other app")

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
	time.sleep(3)
	
	print("(Node)# Exit Node ...")

if __name__ == "__main__":
	main()
