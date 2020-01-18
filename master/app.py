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
from mksdk import MkSMasterNode
from mksdk import MkSShellExecutor
from mksdk import MkSExternalProcess
from mksdk import MkSUtils

class Context():
	def __init__(self, node):
		self.ClassName 						= "Master Application"
		self.Interval						= 10
		self.CurrentTimestamp 				= time.time()
		self.File 							= MkSFile.File()
		self.Node							= node
		self.SystemLoaded					= False
		self.RequestHandlers				= {
			'on_node_change':				self.OnNodeChangeHandler,
			'get_connections_list':			self.GetConnectionsListRequestHandler,
			'get_installed_nodes_list':		self.GetInstalledNodesListRequestHandler,
			'get_master_public_info':		self.GetMasterPublicInfoHandler,
			'get_services_info': 			self.GetServicesInfoHandler,
			'set_service_info': 			self.SetServiceInfoHandler,
			'undefined':					self.UndefindHandler
		}
		self.ResponseHandlers				= {
			'get_online_devices':			self.GetOnlineDevicesHandler,
		}
		self.InstalledNodesDB				= None
		self.ServicesDB 					= None
		self.RunningServices				= []
		self.NetworkDevicesList 			= []

	def UndefindHandler(self, packet):
		print ("UndefindHandler")

	def OnNodeChangeHandler(self, sock, packet):
		print ("({classname})# Node change event recieved ...".format(classname=self.ClassName))
		payload = THIS.Node.Network.BasicProtocol.GetPayloadFromJson(packet)
		src = THIS.Node.Network.BasicProtocol.GetSourceFromJson(packet)

		if src in THIS.Node.IPScannerServiceUUID:
			self.NetworkDevicesList = payload["online_devices"]

		return THIS.Node.Network.BasicProtocol.BuildResponse(packet, {
			'error': 'none'
		})
	
	def GetOnlineDevicesHandler(self, sock, packet):
		print ("({classname})# Online network device list ...".format(classname=self.ClassName))
		payload = THIS.Node.Network.BasicProtocol.GetPayloadFromJson(packet)
		print(payload)
	
	def GetConnectionsListRequestHandler(self, sock, packet):
		if THIS.Node.Network.GetNetworkState() is "CONN":
			connections = []
			for item in THIS.Node.GetConnections():
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

			return THIS.Node.Network.BasicProtocol.BuildResponse(packet, payload)

	def GetInstalledNodesListRequestHandler(self, sock, packet):
		if self.InstalledNodesDB is None:
			installed = []
		else:
			installed = self.InstalledNodesDB["installed_nodes"]
		payload = {
			'installed_nodes': installed,
		}

		return THIS.Node.Network.BasicProtocol.BuildResponse(packet, payload)
	
	def GetMasterPublicInfoHandler(self, sock, packet):
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
		boardType 		= THIS.Node.BoardType
		cpuType			= ""
		shell = MkSShellExecutor.ShellExecutor()
		
		# Get CPU usage (TODO - Not returning correct CPU values use this "top -b -d 1 -n 1")
		data = shell.ExecuteCommand("ps -eo pcpu,pid | sort -k 1 -r | head -20")
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
			'board_type': str(boardType),
			'cpu_type': str(cpuType),
			'machine_name': str(machineName),
			'network': network,
			'on_boot_services': onBootServices,
			'network_devices': self.NetworkDevicesList
		}

		return THIS.Node.Network.BasicProtocol.BuildResponse(packet, payload)
	
	def GetServicesInfoHandler(self, sock, packet):
		if self.ServicesDB is None:
			installed = []
		else:
			installed = self.ServicesDB["on_boot_services"]
		payload = {
			'installed_nodes': installed,
		}

		return THIS.Node.Network.BasicProtocol.BuildResponse(packet, payload)
	
	def SetServiceInfoHandler(self, sock, packet):
		print ("SetServiceInfoHandler", packet)
		payload = THIS.Node.Network.BasicProtocol.GetPayloadFromJson(packet)
		uuid 	= payload["uuid"]
		enabled = payload["enabled"]
		
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
		return THIS.Node.Network.BasicProtocol.BuildResponse(packet, payload)
		
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
			#print ("(Master Appplication)# [Gateway] Data arrived.")
			command = packet['data']['header']['command']
			message = self.RequestHandlers[command](sock, packet)
			THIS.Node.Network.SendWebSocket(message)
		except Exception as e:
			print("({classname})# ERROR - Data arrived issue\n(EXEPTION)# {error}".format(
						classname=self.ClassName,
						error=str(e)))
	
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
		jsonStr = self.File.Load(MKS_PATH + "services.json")
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
		jsonStr = self.File.Load(MKS_PATH + "nodes.json")
		if jsonStr != "":
			self.InstalledNodesDB = json.loads(jsonStr)
		else:
			print("(Master Appplication)# ERROR - Cannot find nodes.json or it is empty.")

	def OnNodeWorkTick(self):
		if time.time() - self.CurrentTimestamp > self.Interval:			
			self.CheckingForUpdate = True
			self.CurrentTimestamp = time.time()

			for idx, item in enumerate(THIS.Node.GetConnections()):
				print ("  ", str(idx), item.LocalType, item.UUID, item.IP, item.Port, item.Type)
			
			#THIS.Node.SendRequestToNode(THIS.Node.IPScannerServiceUUID, "get_online_devices", {})
			#THIS.Node.RegisterOnNodeChangeEvent(THIS.Node.IPScannerServiceUUID)

Node = MkSMasterNode.MasterNode()
THIS = Context(Node)

def signal_handler(signal, frame):
	for service in THIS.RunningServices:
		print("(Master Appplication)# Stop service.")
		service.KillProcess()
		time.sleep(2)
	THIS.Node.Stop()

def main():
	signal.signal(signal.SIGINT, signal_handler)

	THIS.Node.SetLocalServerStatus(True)
	THIS.Node.SetWebServiceStatus(True)

	# Node callbacks
	THIS.Node.GatewayDataArrivedCallback			= THIS.WSDataArrivedHandler
	THIS.Node.GatewayConnectedCallback 				= THIS.WSConnectedHandler
	THIS.Node.OnWSConnectionClosed 					= THIS.WSConnectionClosedHandler
	THIS.Node.NodeSystemLoadedCallback				= THIS.NodeSystemLoadedHandler
	THIS.Node.OnApplicationRequestCallback			= THIS.OnApplicationCommandRequestHandler
	THIS.Node.OnApplicationResponseCallback			= THIS.OnApplicationCommandResponseHandler

	# Run Node
	print("(Master Application)# Start Node ...")
	THIS.Node.Run(THIS.OnNodeWorkTick)
	
	print("(Master Application)# Exit Node ...")

if __name__ == "__main__":
	main()
