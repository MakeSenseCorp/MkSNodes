#!/usr/bin/python
import os
import sys
import signal
import json
import time
import thread
import threading
import re

from mksdk import MkSGlobals
from mksdk import MkSFile
from mksdk import MkSNode
from mksdk import MkSMasterNode
from mksdk import MkSShellExecutor
from mksdk import MkSExternalProcess
from mksdk import MkSUtils

class Context():
	def __init__(self, node):
		self.Interval			= 10
		self.CurrentTimestamp 	= time.time()
		self.Node				= node
		self.SystemLoaded		= False
		# Handlers for remote module (websocket)
		self.GatewayRequestHandlers				= {
			'get_connections_list':			self.GetConnectionsListRequestHandler,
			'get_installed_nodes_list':		self.GetInstalledNodesListRequestHandler,
			'get_master_public_info':		self.GetMasterPublicInfoHandler,
			'get_services_info': 			self.GetServicesInfoHandler,
			'set_service_info': 			self.SetServiceInfoHandler,
			'undefined':					self.UndefindHandler
		}
		# Handlers for local module (socket)
		self.SocketRequestHandlers				= {
			'get_connections_list':			self.GetConnectionsListRequestHandler,
			'get_installed_nodes_list':		self.GetInstalledNodesListRequestHandler,
		}
		self.SocketResponseHandlers				= {
		}
		self.InstalledNodesDB					= None
		self.ServicesDB 						= None
		self.RunningServices					= []

	def UndefindHandler(self, packet):
		print ("UndefindHandler")
	
	def GetConnectionsListRequestHandler(self, packet):
		print ("GetConnectionsListRequestHandler")
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
			message = THIS.Node.Network.BasicProtocol.BuildResponse(packet, payload)
			THIS.Node.Network.SendWebSocket(message)

	def GetInstalledNodesListRequestHandler(self, packet):
		print ("GetInstalledNodesListRequestHandler")
		payload = {
			'installed_nodes': self.InstalledNodesDB["installed_nodes"],
		}
		message = THIS.Node.Network.BasicProtocol.BuildResponse(packet, payload)
		THIS.Node.Network.SendWebSocket(message)
	
	def GetMasterPublicInfoHandler(self, packet):
		print ("GetMasterPublicInfoHandler")
		# Read
		# 	Temperature						cat /sys/class/thermal/thermal_zone0/temp
		#	CPU/RAM Usage, 10 Tasks List	top -n 1
		#									ps -eo pcpu,pid,user,args | sort -k 1 -r | head -10
		#
		cpuUsage 		= 0
		temperature 	= 0
		ramTotal 		= 0
		ramUsed 		= 0
		hdTotal 		= 0
		hdUsed 			= 0
		hdAvailable 	= 0
		osType 			= ""
		boardType 		= ""
		cpuType			= ""
		shell = MkSShellExecutor.ShellExecutor()
		
		# Get CPU usage
		data = shell.ExecuteCommand("ps -eo pcpu,pid,user,args | sort -k 1 -r | head -20")
		data = re.sub(' +', ' ', data)
		cmdRows = data.split("\n")
		for row in cmdRows[1:-1]:
			cols = row.split(" ")
			if (cols[0] != ""):
				cpuUsage += float(cols[0])
			else:
				cpuUsage += float(cols[1])
		
		# Get CPU temperature
		data = shell.ExecuteCommand("cat /sys/class/thermal/thermal_zone0/temp")
		temperature = float(float(data[:-3]) / 10.0)
		
		# Get RAM free space
		data = shell.ExecuteCommand("free")
		data = re.sub(' +', ' ', data)
		cmdRows = data.split("\n")
		col = cmdRows[1].split(" ")
		ramTotal = int(col[1]) / 1023
		ramUsed  = int(col[2]) / 1023
		ramAvailable = ramTotal - ramUsed
		
		# Get CPU usage
		data = shell.ExecuteCommand("df")
		data = re.sub(' +', ' ', data)
		cmdRows = data.split("\n")
		for row in cmdRows[1:-1]:
			cols = row.split(" ")
			if (cols[5] == "/"):
				hdTotal 		= int(cols[1]) / (1023 * 1023)
				hdUsed 			= int(cols[2]) / (1023 * 1023)
				hdAvailable 	= int(cols[3]) / (1023 * 1023)
				break
		
		# Get OS info
		data = shell.ExecuteCommand("uname -a")
		data = re.sub(' +', ' ', data)
		col = data.split(" ")
		osType 		= col[0]
		machineName = col[1]
		cpuType		= col[11]
		
		# Get network data
		interfaces = []
		self.Utilities = MkSUtils.Utils()
		items = self.Utilities.GetSystemIPs()
		for item in items:
			if ("127.0.0" not in item[0]):
				interfaces.append(item)
				
		network = {
			'interfaces': interfaces
		}
		
		onBootServices = []
		if (self.ServicesDB is not None):
			onBootServices = self.ServicesDB["on_boot_services"]

		payload = {
			'cpu_usage': str(cpuUsage),
			'cpu_temperature': str(temperature),
			'ram_total': str(ramTotal),
			'ram_used': str(ramUsed),
			'ram_available': str(ramAvailable),
			'hd_total': str(hdTotal),
			'hd_used': str(hdUsed),
			'hd_available': str(hdAvailable),
			'os_type': str(osType),
			'board_type': str(THIS.Node.BoardType),
			'cpu_type': str(cpuType),
			'machine_name': str(machineName),
			'network': network,
			'on_boot_services': onBootServices,
		}
		message = THIS.Node.Network.BasicProtocol.BuildResponse(packet, payload)
		THIS.Node.Network.SendWebSocket(message)
	
	def GetServicesInfoHandler(self, packet):
		print ("GetServicesInfoHandler")
		payload = {
			'on_boot_services': self.ServicesDB["on_boot_services"],
		}
		message = THIS.Node.Network.BasicProtocol.BuildResponse(packet, payload)
		THIS.Node.Network.SendWebSocket(message)
	
	def SetServiceInfoHandler(self, packet):
		print ("SetServiceInfoHandler", packet)
		uuid 	= packet["data"]["payload"]["uuid"]
		enabled = packet["data"]["payload"]["enabled"]
		
		dbOnBootServices = self.ServicesDB["on_boot_services"]
		for item in dbOnBootServices:
			if (item["uuid"] == uuid):
				item["enabled"] = enabled
				break
		
		self.ServicesDB["on_boot_services"] = dbOnBootServices
		# Save new switch to database
		MKS_PATH = os.environ['HOME'] + "/mks/"
		self.Node.SetFileContent(MKS_PATH + "services.json", json.dumps(self.ServicesDB))
		
		payload = { 'error': 'ok' }
		message = THIS.Node.Network.BasicProtocol.BuildResponse(packet, payload)
		THIS.Node.Network.SendWebSocket(message)
		
	def OnCustomCommandRequestHandler(self, sock, packet):
		print ("OnCustomCommandRequestHandler")
		command = packet['command']
		if command in self.SocketRequestHandlers:
			self.SocketRequestHandlers[command](sock, packet)

	def OnCustomCommandResponseHandler(self, sock, packet):
		print ("OnCustomCommandResponseHandler")
		command = packet['command']
		if command in self.SocketResponseHandlers:
			self.SocketResponseHandlers[command](sock, packet)

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
		print ("(Master Appplication)# [Gateway] Data arrived.")
		command = packet['data']['header']['command']
		self.GatewayRequestHandlers[command](packet)
	
	def WSConnectedHandler(self):
		print ("(Master Appplication)# Connection to Gateway was established.")

	def WSConnectionClosedHandler(self):
		print ("(Master Appplication)# Connection to Gateway was lost.")

	def NodeSystemLoadedHandler(self):
		print ("(Master Appplication)# Node system was succesfully loaded.")
		self.SystemLoaded = True
		
		# Loading on master boot service database
		if MkSGlobals.OS_TYPE in ["linux", "linux2"]:
			MKS_PATH = os.environ['HOME'] + "/mks/"
		else:
			MKS_PATH = "C:\\mks\\"
		
		print ("(Master Appplication)# Loading on master boot service database.")
		jsonStr = self.Node.GetFileContent(MKS_PATH + "services.json")
		if jsonStr != "":
			self.ServicesDB = json.loads(jsonStr)
			if (self.ServicesDB is not None):
				services = self.ServicesDB["on_boot_services"]
				for service in services:
					if (service["enabled"] == 1):
						print("(Master Appplication)# Start service name ", service["name"])
						node = MkSExternalProcess.ExternalProcess()
						self.RunningServices.append(node)
						if MkSGlobals.OS_TYPE in ["linux", "linux2"]:
							node.CallProcess("python app.py", "../" + str(service["type"]), "")
						else:
							node.CallProcess("python app.py", "..\\" + str(service["type"]), "")
		else:
			print("(Master Appplication)# ERROR - Cannot find service.json or it is empty.")
		
		# Load all installed nodes
		print ("(Master Appplication)# Load all installed nodes.")
		jsonStr = self.Node.GetFileContent(MKS_PATH + "nodes.json")
		if jsonStr != "":
			self.InstalledNodesDB = json.loads(jsonStr)
		else:
			print("(Master Appplication)# ERROR - Cannot find nodes.json or it is empty.")

	def OnNodeWorkTick(self):
		if time.time() - self.CurrentTimestamp > self.Interval:			
			self.CheckingForUpdate = True
			self.CurrentTimestamp = time.time()

			for idx, item in enumerate(THIS.Node.LocalServiceNode.GetConnections()):
				print ("  ", str(idx), item.LocalType, item.UUID, item.IP, item.Port, item.Type)

Service = MkSMasterNode.MasterNode()
Node 	= MkSNode.Node("MASTER", Service)
THIS 	= Context(Node)

def signal_handler(signal, frame):
	for service in THIS.RunningServices:
		print("(Master Appplication)# Stop service.")
		service.KillProcess()
		time.sleep(2)
	THIS.Node.Stop()

def main():
	signal.signal(signal.SIGINT, signal_handler)

	THIS.Node.SetLocalServerStatus(False)
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
	print("(Master Application)# Start Node ...")
	THIS.Node.Run(THIS.OnNodeWorkTick)
	
	print("(Master Application)# Exit Node ...")

if __name__ == "__main__":
	main()
