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
from mksdk import MkSUtils

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
		self.SearchNetworks()
	
	def SearchNetworks(self):
		self.Node.LogMSG("({classname})# Searching for networks ...".format(classname=self.ClassName),5)
		items = self.Utilities.GetSystemIPs()
		for item in items:
			if ("127.0.0" not in item[0] and "" != item[0]):
				net = ".".join(item[0].split('.')[0:-1]) + '.'
				if net not in self.Networks:
					self.Networks.append(net)
		
		for network in self.Networks:
			thread.start_new_thread(self.PingDevicesThread, (network, range(1,50), 1,))
			thread.start_new_thread(self.PingDevicesThread, (network, range(50,100), 2,))
			thread.start_new_thread(self.PingDevicesThread, (network, range(100,150), 3,))
			thread.start_new_thread(self.PingDevicesThread, (network, range(150,200), 4,))

	def PingDevicesThread(self, network, ip_range, index):
		while (self.ThreadWorking is True):
			for client in ip_range:
				if (self.ThreadWorking is False):
					self.Node.LogMSG("({classname})# Exit this thread {0}".format(index,classname=self.ClassName),5)
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
				time.sleep(0.5)

	def UndefindHandler(self, message_type, source, data):
		self.Node.LogMSG("UndefindHandler",5)
	
	def GetOnlineDevicesHandler(self, sock, packet):
		self.Node.LogMSG("({classname})# [GetOnlineDevicesHandler]".format(classname=self.ClassName),5)
		self.ThreadLock.acquire()
		listOfDevice = []
		for key in self.OnlineDevices:
			listOfDevice.append(self.OnlineDevices[key])
		self.ThreadLock.release()
		self.Node.LogMSG("({classname})# [GetOnlineDevicesHandler] {0}".format(listOfDevice, classname=self.ClassName),5)
		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'online_devices': listOfDevice
		})
	
	def NodeSystemLoadedHandler(self):
		self.Node.LogMSG("({classname})# Node system loaded ...".format(classname=self.ClassName),5)
	
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
		for key in self.OnlineDevices:
			if key == conn.IP:
				del self.OnlineDevices[key]["mks"]
	''' 
		Description: 	Response for request (get_node_info) 
						For each device found this service send get_node_info, if there is a response
						the device marked as MKS by adding "mks" value to dictionary.
		Return: 		N/A
	'''	
	def OnGetNodeInfoHandler(self, info):
		self.Node.LogMSG("({classname})# [OnGetNodeInfoHandler]".format(classname=self.ClassName),5)
		self.ThreadLock.acquire()
		for key in self.OnlineDevices:
			if key == info["ip"]:
				self.OnlineDevices[key]["mks"] = {
					"type": info["type"],
					"name": info["name"]
				}
		self.ThreadLock.release()

	def WorkingHandler(self):
		try:
			if time.time() - self.CurrentTimestamp > self.Interval:
				self.CurrentTimestamp = time.time()

				self.Node.LogMSG("\nTables:",5)
				connections = THIS.Node.GetConnectedNodes()
				for idx, key in enumerate(connections):
					node = connections[key]
					self.Node.LogMSG("  {0}\t{1}\t{2}\t{3}\t{4}\t{5}\t{6}\t{7}".format(str(idx),node.Obj["local_type"],node.Obj["uuid"],node.IP,node.Obj["listener_port"],node.Obj["type"],node.Obj["pid"],node.Obj["name"]),5)
				self.Node.LogMSG("",5)

				self.ThreadLock.acquire()
				# Find disconnected devices
				network_device_to_delete = []
				for key in self.OnlineDevices:
					network_device = self.OnlineDevices[key]
					if (MkSUtils.Ping(network_device["ip"]) is False):
						self.Node.LogMSG("Offline device " + network_device["ip"],5)
						network_device_to_delete.append(key)
					else:
						self.Node.LogMSG("  {0}\t{1}\t{2}".format(network_device["ip"],network_device["datetime"],network_device["ts"]),5)
				
				# Send disconnected devices
				if len(network_device_to_delete) > 0:
					THIS.Node.EmitOnNodeChange({
						'disconnected_devices': network_device_to_delete
					})
				
				# Remove disconnected devices
				for key in network_device_to_delete:
					del self.OnlineDevices[key]
				
				# Find MKS enabled devices
				for key in self.OnlineDevices:
					# Check if connection is already opened
					conn = self.Node.GetNode(key, 16999)
					if conn is None:
						conn, status = self.Node.ConnectNode(key, 16999)
						if status is True:
							self.Node.LogMSG("({classname})# Makesense device found".format(key,classname=self.ClassName),5)
							message = self.Node.BasicProtocol.BuildRequest("DIRECT", "MASTER", self.Node.UUID, "get_node_info", {}, {})
							packet  = self.Node.BasicProtocol.AppendMagic(message)
							self.Node.SocketServer.Send(conn.Socket, packet)
					else:
						message = self.Node.BasicProtocol.BuildRequest("DIRECT", "MASTER", self.Node.UUID, "get_node_info", {}, {})
						packet  = self.Node.BasicProtocol.AppendMagic(message)
						self.Node.SocketServer.Send(conn.Socket, packet)
				
				# Send online devices
				list_of_devices = []
				for key in self.OnlineDevices:
					list_of_devices.append(self.OnlineDevices[key])
				self.ThreadLock.release()
				THIS.Node.EmitOnNodeChange({
					'event': 'online_devices',
					'online_devices': list_of_devices
				})
		except Exception as e:
			self.Node.LogMSG("({classname})# WorkingHandler ERROR ... \n{0}".format(e,classname=self.ClassName),5)

Node = MkSSlaveNode.SlaveNode()
THIS = Context(Node)

def signal_handler(signal, frame):
	THIS.ThreadWorking = False
	THIS.Node.Stop("Accepted signal from other app")
	time.sleep(1)

def main():
	signal.signal(signal.SIGINT, signal_handler)
	THIS.Node.SetLocalServerStatus(True)
	
	# Node callbacks
	THIS.Node.NodeSystemLoadedCallback			= THIS.NodeSystemLoadedHandler
	THIS.Node.OnApplicationRequestCallback		= THIS.OnApplicationCommandRequestHandler
	THIS.Node.OnApplicationResponseCallback		= THIS.OnApplicationCommandResponseHandler
	THIS.Node.OnGetNodeInfoCallback				= THIS.OnGetNodeInfoHandler
	THIS.Node.OnTerminateConnectionCallback		= THIS.OnTerminateConnectionHandler
	
	THIS.Node.Run(THIS.WorkingHandler)
	THIS.ThreadWorking = False
	THIS.Node.LogMSG("Exit Node ...",5)

if __name__ == "__main__":
    main()

