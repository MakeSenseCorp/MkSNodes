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
		self.MasterConnected				= False
		self.MasterConnection				= None
		self.ServicesLoaded 				= False

	def UndefindHandler(self, sock, packet):
		print ("({classname})# UndefindHandler".format(classname=self.ClassName))
	
	def GetNodeStatusHandler(self, sock, packet):
		print ("({classname})# [GetNodeStatusHandler]".format(classname=self.ClassName))
		payload = self.Node.BasicProtocol.GetPayloadFromJson(packet)
		source = self.Node.BasicProtocol.GetSourceFromJson(packet)

		if self.MasterConnection.Obj["uuid"] == source or "MASTER" == source:
			print ("({classname})# Master status '{0}'".format(payload,classname=self.ClassName))
			if self.ServicesLoaded is False:
				self.LoadServices()
				self.ServicesLoaded = True
		else:
			conn = self.Node.SocketServer.GetConnectionBySock(sock)
			if conn is not None:
				print ("({classname})# Node '{0}' status '{1}'".format(conn.Obj["uuid"],payload,classname=self.ClassName))
		
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
	
	def OnTerminateConnectionHandler(self, conn):
		self.Node.LogMSG("({classname})# [OnTerminateConnectionHandler]".format(classname=self.ClassName),5)
		if conn.Socket == self.MasterConnection.Socket:
			self.MasterConnected = False

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

	def RequestStatus(self, uuid):
		message = self.Node.BasicProtocol.BuildRequest("DIRECT", uuid, self.Node.UUID, "get_node_status", {}, {})
		packet  = self.Node.BasicProtocol.AppendMagic(message)
		self.Node.SocketServer.Send(self.MasterConnection.Socket, packet)

	def LoadServices(self):
		strServicesJson = self.File.Load(os.path.join(self.Node.MKSPath,"services.json"))
		if strServicesJson == "":
			self.Node.LogMSG("({classname})# ERROR - Cannot find service.json or it is empty.".format(classname=self.ClassName),3)
			return
		
		self.ServicesDB = json.loads(strServicesJson)
		services = self.ServicesDB["on_boot_services"]
		for service in services:
			if (service["enabled"] == 1):
				self.Node.LogMSG("({classname})# Start service - {0}".format(service["name"],classname=self.ClassName),5)
				service_path = os.path.join(self.Node.MKSPath,"nodes",str(service["type"]))
				proc = MkSExternalProcess.ExternalProcess()
				proc_str = "python app.py --type {0} &".format(service["type"])
				proc.CallProcess(proc_str, service_path, "")
	
	def LoadMasterNode(self):
		print("({classname})# Loading MASTER ...".format(classname=self.ClassName))
		master_path = os.path.join(self.Node.MKSPath,"nodes","master")
		node = MkSExternalProcess.ExternalProcess()
		node.CallProcess("python app.py --type 1 &", master_path, "")
	
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
		self.ServicesLoaded = False
		self.TerminatePythonProcs()
		time.sleep(2)
		self.LoadMasterNode()
		time.sleep(2)
		self.MasterConnection, self.MasterConnected = self.Node.ConnectNode(self.Node.MyLocalIP, 16999)
		self.Node.LogMSG("({classname})# [StartSystem] {0}".format(self.MasterConnected, classname=self.ClassName),5)

	def NodeSystemLoadedHandler(self):
		self.Node.LogMSG("({classname})# Node system was succesfully loaded.".format(classname=self.ClassName),5)
		self.SystemLoaded = True
		self.StartSystem()
		
	def OnNodeWorkTick(self):
		if (self.Node.Ticker % 10) == 0:
			self.Node.LogMSG("({classname})# [HeartBeat] ({0})".format(self.Node.Ticker, classname=self.ClassName),5)
			if (self.Node.Ticker % 30) == 0:
				if self.MasterConnected is True:
					self.RequestStatus("MASTER")
					# Send status to services
					if self.ServicesLoaded is True:
						for key in THIS.Node.Services:
							if "" != THIS.Node.Services[key]["uuid"]:
								self.Node.LogMSG("({classname})# Request Status Service {0}".format(THIS.Node.Services[key]["uuid"], classname=self.ClassName),5)
								self.RequestStatus(THIS.Node.Services[key]["uuid"])
						# Check if service closed
				else:
					self.StartSystem()

# TODO - Need state machine for guardian work.
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
	THIS.Node.OnTerminateConnectionCallback			= THIS.OnTerminateConnectionHandler

	# Run Node
	print("(Node)# Start Node ...")
	THIS.Node.Run(THIS.OnNodeWorkTick)
	print("(Node)# Wait (5 Sec)")
	time.sleep(5)
	
	print("(Node)# Exit Node ...")

if __name__ == "__main__":
	main()
