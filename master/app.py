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

class FileDownload():
	def __init__(self, name, size, owner, chanks):
		self.Name 					= name
		self.Size 					= size
		self.LastFragmentNumber 	= chanks
		self.FragmentsCount			= 0
		self.Fragments 				= []
		self.Timestamp 				= 0
		self.OwnerUuid 				= owner

		for i in range(1, self.LastFragmentNumber + 1):
			self.FragmentsCount += i

	def AddFragment(self, content, index, size):
		self.Fragments.append({ 
				'content': content,
				'index': index,
				'size': size ,
			})
		self.Timestamp = time.time()
		return self.CheckFileUploaded()

	def CheckFileDownloaded(self):
		counter = 0
		for item in self.Fragments:
			counter += item["index"]

		if counter == self.FragmentsCount:
			return True
		return False

	def GetFileRaw(self):
		data = []
		for index in range(1, self.LastFragmentNumber+1):
			for item in self.Fragments:
				if str(item["index"]) == str(index):
					data += item["content"]
					break
		return data, len(data)

class Context():
	def __init__(self, node):
		self.ClassName 						= "Master Application"
		self.Interval						= 10
		self.CurrentTimestamp 				= time.time()
		self.File 							= MkSFile.File()
		self.Node							= node
		self.SystemLoaded					= False
		self.RequestHandlers				= {
			'on_node_change':				self.Request_OnNodeChangeHandler,
			'get_connections_list':			self.Request_GetConnectionsListRequestHandler,
			'get_master_public_info':		self.Request_GetMasterPublicInfoHandler,
			'get_installed_nodes_list':		self.Request_GetInstalledNodesListRequestHandler,
			'set_installed_node_info':		self.Request_SetInstalledNodeInfoRequestHandler,
			'get_services_info': 			self.Request_GetServicesInfoHandler,
			'set_service_info': 			self.Request_SetServiceInfoHandler,
			'reboot':						self.Request_RebootHandler,
			'shutdown':						self.Request_ShutdownHandler,
			'install':						self.Request_InstallHandler,
			'upload_file':					self.Request_UploadFileHandler,
			'undefined':					self.UndefindHandler
		}
		self.ResponseHandlers				= {
			'get_online_devices':			self.Response_GetOnlineDevicesHandler,
		}
		self.InstalledNodesDB				= None
		self.ServicesDB 					= None
		self.RunningServices				= []
		self.RunningNodes					= []
		self.NetworkDevicesList 			= []
		self.Node.DebugMode 				= True
		self.Shutdown 						= False

	def UndefindHandler(self, packet):
		self.Node.LogMSG("UndefindHandler",5)
		return THIS.Node.Network.BasicProtocol.BuildResponse(packet, {
			'error': 'none'
		})
	
	def Request_UploadFileHandler(self, sock, packet):
		payload = THIS.Node.Network.BasicProtocol.GetPayloadFromJson(packet)
		self.Node.LogMSG("({classname})# [Request_UploadFileHandler] {0}".format(payload["upload"]["chunk"], classname=self.ClassName),5)
		self.File.AppendArray(os.path.join("packages",payload["upload"]["file"]), payload["upload"]["content"])
		return THIS.Node.Network.BasicProtocol.BuildResponse(packet, {
			'error': 'none'
		})
	
	def Request_InstallHandler(self, sock, packet):
		self.Node.LogMSG("({classname})# [Request_InstallHandler]".format(classname=self.ClassName),5)
		return THIS.Node.Network.BasicProtocol.BuildResponse(packet, {
			'error': 'none'
		})

	def Request_RebootHandler(self, sock, packet):
		self.Node.LogMSG("({classname})# [Request_RebootHandler]".format(classname=self.ClassName),5)
		connections = THIS.Node.GetConnectedNodes()
		for key in connections:
			node = connections[key]
			if node.Obj["type"] == 2:
				self.Node.LogMSG("({classname})# [Request_RebootHandler] REBOOT".format(classname=self.ClassName),5)
				# Send reboot request to defender
				message = THIS.Node.BasicProtocol.BuildRequest("DIRECT", node.Obj["uuid"], THIS.Node.UUID, "reboot", {}, {})
				local_packet  = THIS.Node.BasicProtocol.AppendMagic(message)
				THIS.Node.SocketServer.Send(node.Socket, local_packet)
				# Return message to requestor
				payload = { 'status': 'OK' }
				return THIS.Node.BasicProtocol.BuildResponse(packet, payload)
		payload = { 'status': 'FAILD' }
		return THIS.Node.BasicProtocol.BuildResponse(packet, payload)
	
	def Request_ShutdownHandler(self, sock, packet):
		self.Node.LogMSG("({classname})# [Request_ShutdownHandler]".format(classname=self.ClassName),5)
		self.ShutdownProcess()
		self.Node.Exit("Request_ShutdownHandler")

	def Request_OnNodeChangeHandler(self, sock, packet):
		self.Node.LogMSG("({classname})# Node change event recieved ...".format(classname=self.ClassName),5)
		payload = THIS.Node.Network.BasicProtocol.GetPayloadFromJson(packet)
		src = THIS.Node.Network.BasicProtocol.GetSourceFromJson(packet)

		if src in THIS.Node.Services[103]["uuid"]:
			self.NetworkDevicesList = payload["online_devices"]

		return THIS.Node.Network.BasicProtocol.BuildResponse(packet, {
			'error': 'none'
		})
	
	def Response_GetOnlineDevicesHandler(self, sock, packet):
		self.Node.LogMSG("({classname})# Online network device list ...".format(classname=self.ClassName),5)
		payload = THIS.Node.Network.BasicProtocol.GetPayloadFromJson(packet)
		self.Node.LogMSG(payload,5)
	
	def Request_GetConnectionsListRequestHandler(self, sock, packet):
		if THIS.Node.Network.GetNetworkState() is "CONN":
			conns = []
			connections = THIS.Node.GetConnectedNodes()
			for key in connections:
				node = connections[key]
				conns.append({
					'local_type':	node.Obj["local_type"],
					'uuid':			node.Obj["uuid"],
					'ip':			node.IP,
					'port':			node.Port,
					'type':			node.Obj["type"]
				})
			payload = {
				'connections': conns
			}

			return THIS.Node.Network.BasicProtocol.BuildResponse(packet, payload)

	def Request_GetInstalledNodesListRequestHandler(self, sock, packet):
		if self.InstalledNodesDB is None:
			installed = []
		else:
			installed = self.InstalledNodesDB["installed_nodes"]
		payload = {
			'installed_nodes': installed,
		}

		return THIS.Node.Network.BasicProtocol.BuildResponse(packet, payload)
	
	def Request_SetInstalledNodeInfoRequestHandler(self, sock, packet):
		self.Node.LogMSG("({classname})# [Request_SetInstalledNodeInfoRequestHandler] {0}".format(packet,classname=self.ClassName),5)
		payload = THIS.Node.Network.BasicProtocol.GetPayloadFromJson(packet)
		uuid 	= payload["uuid"]
		enabled = payload["enabled"]

		installed = self.InstalledNodesDB["installed_nodes"]
		for item in installed:
			if (item["uuid"] == uuid):
				item["enabled"] = enabled
				break
		
		self.InstalledNodesDB["installed_nodes"] = installed
		# Save new switch to database
		self.File.SaveJSON(os.path.join(self.Node.MKSPath,"nodes.json"), self.InstalledNodesDB)
		
		payload = { 'error': 'ok' }
		return THIS.Node.Network.BasicProtocol.BuildResponse(packet, payload)
	
	def Request_GetMasterPublicInfoHandler(self, sock, packet):
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
		try:
			temperature = float(float(data[:-3]) / 10.0)
		except Exception as e:
			pass 
		
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
	
	def Request_GetServicesInfoHandler(self, sock, packet):
		if self.ServicesDB is None:
			installed = []
		else:
			installed = self.ServicesDB["on_boot_services"]
		payload = {
			'on_boot_services': installed,
		}

		return THIS.Node.Network.BasicProtocol.BuildResponse(packet, payload)
	
	def Request_SetServiceInfoHandler(self, sock, packet):
		self.Node.LogMSG("({classname})# [Request_SetServiceInfoHandler] {0}".format(packet,classname=self.ClassName),5)
		payload = THIS.Node.Network.BasicProtocol.GetPayloadFromJson(packet)
		uuid 	= payload["uuid"]
		enabled = payload["enabled"]
		
		service_found = None
		dbOnBootServices = self.ServicesDB["on_boot_services"]
		for item in dbOnBootServices:
			if (item["uuid"] == uuid):
				item["enabled"] = enabled
				service_found = item
				break
		
		if service_found is not None:
			self.ServicesDB["on_boot_services"] = dbOnBootServices
			# Save new switch to database
			self.File.SaveJSON(os.path.join(self.Node.MKSPath,"services.json"), self.ServicesDB)
			if enabled == 0:
				# Find service need attention
				connections = THIS.Node.GetConnectedNodes()
				service_need_attention = None
				for key in connections:
					node = connections[key]
					if node.Obj["type"] == service_found["type"]:
						service_need_attention = {
							"uuid": node.Obj["uuid"],
							"name": node.Obj["name"],
							"type": node.Obj["type"],
							"pid": node.Obj["pid"]
						}
						break
			else:
				service_need_attention = {
					"uuid": item["uuid"],
					"name": item["name"],
					"type": item["type"],
					"pid": 0
				}
			
			if service_need_attention is not None:
				# Find guardian instance and send message
				connections = THIS.Node.GetConnectedNodes()
				for key in connections:
					node = connections[key]
					if node.Obj["type"] == 2:
						message = THIS.Node.BasicProtocol.BuildRequest("DIRECT", node.Obj["uuid"], THIS.Node.UUID, "services_mngr", {
							"command": "enable",
							"service": {
								"enabled": enabled,
								"uuid": service_need_attention["uuid"],
								"name": service_need_attention["name"],
								"type": service_need_attention["type"],
								"pid": service_need_attention["pid"]
							}
						}, {})
						local_packet  = THIS.Node.BasicProtocol.AppendMagic(message)
						THIS.Node.SocketServer.Send(node.Socket, local_packet)
		
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
	
	def OnTerminateConnectionHandler(self, conn):
		self.Node.LogMSG("({classname})# [OnTerminateConnectionHandler]".format(classname=self.ClassName),5)
		if self.Shutdown is False:
			if conn.Obj["info"] is not None:
				if conn.Obj["info"]["is_service"] == "True":
					pass
				else:
					self.RemoveFromRunningNodes(conn.Obj["uuid"])
					nodes = self.InstalledNodesDB["installed_nodes"]
					for node in nodes:
						if node["uuid"] == conn.Obj["uuid"]:
							self.Node.LogMSG("({classname})# Start node - {0}".format(node["name"],classname=self.ClassName),5)
							node_path = os.path.join(self.Node.MKSPath,"nodes",str(node["type"]))
							proc = MkSExternalProcess.ExternalProcess()
							proc.CallProcess("python app.py &", node_path, "")
							return

	def WSDataArrivedHandler(self, sock, packet):
		try:
			#print ("(Master Appplication)# [Gateway] Data arrived.")
			command = packet['data']['header']['command']
			return self.RequestHandlers[command](sock, packet)
		except Exception as e:
			self.Node.LogMSG("({classname})# ERROR - Data arrived issue\n(EXEPTION)# {error}".format(
						classname=self.ClassName,
						error=str(e)),3)
	
	def WSConnectedHandler(self):
		self.Node.LogMSG("({classname})# Connection to Gateway was established.".format(classname=self.ClassName),5)

	def WSConnectionClosedHandler(self):
		self.Node.LogMSG("({classname})# Connection to Gateway was lost.".format(classname=self.ClassName),5)
	
	def RemoveFromRunningNodes(self, uuid):
		remove_node = None
		for node in self.RunningNodes:
			if node["uuid"] == uuid:
				remove_node = node
		if remove_node is not None:
			self.RunningNodes.remove(node)

	def LoadNodes(self):
		strNodesJson = self.File.Load(os.path.join(self.Node.MKSPath,"nodes.json"))
		if strNodesJson == "":
			self.Node.LogMSG("({classname})# ERROR - Cannot find nodes.json or it is empty.".format(classname=self.ClassName),3)
			return
		
		self.InstalledNodesDB = json.loads(strNodesJson)
		nodes = self.InstalledNodesDB["installed_nodes"]
		for node in nodes:
			if (node["enabled"] == 1):
				self.Node.LogMSG("({classname})# Start node - {0}".format(node["name"],classname=self.ClassName),5)
				node_path = os.path.join(self.Node.MKSPath,"nodes",str(node["type"]))
				proc = MkSExternalProcess.ExternalProcess()
				proc_str = "python app.py --type {0} &".format(node["type"])
				proc.CallProcess(proc_str, node_path, "")
				#self.RunningNodes.append(node)

	def ShutdownProcess(self):
		self.Shutdown = True
		shutdown_connections = []
		# TODO - Could be an issue with not locking this list. (multithreading)
		connections = THIS.Node.GetConnectedNodes()
		for key in connections:
			node = connections[key]
			shutdown_connections.append({
				"sock": node.Socket,
				"uuid": node.Obj["uuid"]
			})
		
		for item in shutdown_connections:
			if item["uuid"] != THIS.Node.UUID:
				message = THIS.Node.BasicProtocol.BuildRequest("DIRECT", item["uuid"], THIS.Node.UUID, "shutdown", {}, {})
				packet  = THIS.Node.BasicProtocol.AppendMagic(message)
				THIS.Node.SocketServer.Send(item["sock"], packet)
		
		time.sleep(5)

	def NodeSystemLoadedHandler(self):
		self.SystemLoaded = True
		# Load all installed nodes
		self.LoadNodes()
		# Load services DB
		strServicesJson = self.File.Load(os.path.join(self.Node.MKSPath,"services.json"))
		if strServicesJson == "":
			self.Node.LogMSG("({classname})# ERROR - Cannot find service.json or it is empty.".format(classname=self.ClassName),3)
			return
		
		self.ServicesDB = json.loads(strServicesJson)
		self.Node.LogMSG("({classname})# Node system was succesfully loaded.".format(classname=self.ClassName),5)

	def OnNodeWorkTick(self):
		if time.time() - self.CurrentTimestamp > self.Interval:			
			self.CheckingForUpdate = True
			self.CurrentTimestamp = time.time()
			self.Node.LogMSG("({classname})# Live ... ({0})".format(self.Node.Ticker, classname=self.ClassName),5)
			self.Node.LogMSG("({classname})# Current connections:".format(classname=self.ClassName),5)

			connections = THIS.Node.GetConnectedNodes()
			for idx, key in enumerate(connections):
				node = connections[key]
				#message = self.Node.BasicProtocol.BuildRequest("DIRECT", item.UUID, self.Node.UUID, "get_node_status", {}, {})
				#packet  = self.Node.BasicProtocol.AppendMagic(message)
				#self.Node.Transceiver.Send({"sock":item.Socket, "packet":packet}) # Response will update "enabled" or "ts" field in local DB
				self.Node.LogMSG("  {0}\t{1}\t{2}\t{3}\t{4}\t{5}".format(str(idx), node.Obj["local_type"], node.Obj["uuid"], node.IP, node.Obj["listener_port"], node.Obj["type"]),5)
			
			for idx, key in enumerate(self.Node.Services):
				service = self.Node.Services[key]
				self.Node.LogMSG("  {0}\t{1}\t{2}\t{3}\t{4}".format(str(idx), service["uuid"], service["name"], service["enabled"], service["registered"]),5)

Node = MkSMasterNode.MasterNode()
THIS = Context(Node)

def signal_handler(signal, frame):
	THIS.ShutdownProcess()
	THIS.Node.Stop("Accepted signal from other app")

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
	THIS.Node.OnTerminateConnectionCallback			= THIS.OnTerminateConnectionHandler

	# Run Node
	THIS.Node.LogMSG("(Master Application)# Start Node ...",5)
	THIS.Node.Run(THIS.OnNodeWorkTick)
	time.sleep(1)

if __name__ == "__main__":
	main()
