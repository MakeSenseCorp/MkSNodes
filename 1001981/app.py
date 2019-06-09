#!/usr/bin/python
import os
import sys
import signal
import json
import time
import thread
import threading
if sys.platform in ["win32"]:
	import Queue as queue
else:
	import queue

import subprocess
from subprocess import call

sys.path.append(".\TDMReplace")
from Api import FWAdapter
from Api import Definitions
from Api import Utils

from mksdk import MkSFile
from mksdk import MkSNode
from mksdk import MkSSlaveNode
from mksdk import MkSLocalHWConnector
from mksdk import MkSUSBAdaptor
from mksdk import MkSProtocol
from mksdk import MkSExternalProcess

from flask import Response, request

class FileUpload():
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

	def CheckFileUploaded(self):
		print ("CheckFileUploaded")
		counter = 0
		for item in self.Fragments:
			counter += item["index"]

		print (counter, self.FragmentsCount)
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
		self.CustomRequestHandlers				= {
			'surface_fw_info': 						self.SurfaceFWInfoRequestHandler,
			'surface_run_test':						self.SurfaceRunTestRequestHandler,
			'surface_get_test_output':				self.SurfaceGetTestOutputRequestHandler,
			'surface_toggle_fw':					self.SurfaceToggleFWRequestHandler,
			'surface_get_upload_list':				self.SurfaceGetUploadListRequestHandler,
			'surface_dfu_fw':						self.SurfaceDfuFirmwareRequestHandler,
		}
		self.CustomResponseHandlers				= {
		}

		# Init Firmware adaptor
		self.FW 								= FWAdapter.Adaptor(Utils.GetDefaultTBPath())

		self.External 							= MkSExternalProcess.ExternalProcess()
		self.External.OnProcessDataPipeCallback = self.ProcessDataPipe
		self.External.OnProcessDoneCallback 	= self.ProceesDone
		self.External.OnProcessErrorCallback 	= self.ProcessError
		self.RequestQueue						= queue.Queue(0) # Thread safe Queue
		self.CurrentProcessedRequest 			= None
		self.Tests 								= None

		self.RequestQueue.put({
			'request': ['--print_tests'],
			'user': {
				'socket': None,
				'packet': ""
			}
		})

		self.Uploads 							= []
		self.UploadsMonitorRunning				= False
		self.Locker				 				= threading.Lock()

	def FindUpload(self, name):
		print ("FindUpload")
		for item in self.Uploads:
			if item.Name == name:
				return item
		return None

	def UploadsMonitorThread(self):
		while self.UploadsMonitorRunning is True:
			time.sleep(5)
			# Itterate over uploads and find one that reached timeout
			for upload in self.Uploads:
				if upload.Timestamp > (time.time() - 10):
					# Delete upload send message to uploader owner
					self.Uploads.remove(upload)
	
	def SurfaceFWInfoRequestHandler(self, sock, packet):
		print ("SurfaceFWInfoRequestHandler")
		device = packet["payload"]["data"]["device"]
		# Get FW type and version
		fwType, fwVersion, blVersion, mwVersion, returnCode = self.FW.GetVersion(device)
		THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
			'fw_version': fwVersion,
			'fw_type': fwType,
			'bl_version': blVersion,
			'mw_version':mwVersion
		})

	def SurfaceRunTestRequestHandler(self, sock, packet):
		print ("SurfaceRunTestRequestHandler", packet)
		device = packet["payload"]["data"]["device"]
		test = packet["payload"]["data"]["test"]
		self.RequestQueue.put({
			'request': ['--test', str(test), '--sid', str(device), '--json'],
			'user': {
				'socket': sock,
				'packet': packet
			}
		})
		THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, { })

	def SurfaceGetTestOutputRequestHandler(self, sock, packet):
		print ("SurfaceGetTestOutputRequestHandler", packet)
		test = packet["payload"]["data"]["test"]
		THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
			'status': 'unavailable'
		})
	
	def SurfaceToggleFWRequestHandler(self, sock, packet):
		print ("SurfaceToggleFWRequestHandler", packet)
		device = packet["payload"]["data"]["device"]
		# Get FW type and version
		returnCode = self.FW.ToggleFW(device)
		THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
			'return_code': returnCode
		})

	def SurfaceGetUploadListRequestHandler(self, sock, packet):
		print ("SurfaceGetUploadListRequestHandler", packet)
		file = MkSFile.File()
		fwFiles = file.ListFilesInFolder(".\\fw-upload\\")
		THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
			'files': fwFiles
		})
	
	def SurfaceDfuFirmwareRequestHandler(self, sock, packet):
		print ("SurfaceDfuFirmwareRequestHandler", packet)
		fileName 	= packet["payload"]["data"]["fw_file"]
		device 		= packet["payload"]["data"]["device"]
		uuid 		= packet["payload"]["header"]["destination"]
		if ".bin" in fileName: 
			returnCode = self.FW.FlashAlternate(os.path.realpath(".\\fw-upload\\" + fileName), device)
			THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
				'uuid': uuid,
				'file': fileName,
				'return_code': returnCode,
				'error': 'none'
			})
		else:
			THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
				'error': 'cannot dfu (not a bin file)'
			})

	def ProceesDone(self, data, user):
		print ("[Node]# ProceesDone")
		if "--print_tests" in self.CurrentProcessedRequest["request"]:
			try:
				if data is not None or data is not "":
					jsonData = json.loads(data)
					self.Tests = jsonData["tests"]
			except Exception as e:
				print ("[Node]# ProceesDone ERROR", e)
		if "--test" in self.CurrentProcessedRequest["request"]:
			print ("[Node]# Test finished its run.")
			sock 	= user["socket"]
			packet 	= user["packet"]
			#THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
			#	'error': 'none',
			#	'test': 'name',
			#	'status': 'ok'
			#})

	def ProcessDataPipe(self, data, user):
		print ("[Node]# ProcessDataPipe,", data)
	
	def ProcessError(self, error, user):
		print ("[Node]# ERROR,", error)

	def UndefindHandler(self, message_type, source, data):
		print "UndefindHandler"

	# Websockets
	def WSDataArrivedHandler(self, message_type, source, data):
		command = data['device']['command']
		self.Handlers[command](message_type, source, data)

	def WSConnectedHandler(self):
		print "WSConnectedHandler"

	def WSConnectionClosedHandler(self):
		print "WSConnectionClosedHandler"

	def NodeSystemLoadedHandler(self):
		print "NodeSystemLoadedHandler"

	def OnMasterFoundHandler(self, masters):
		print "OnMasterFoundHandler"

	def OnMasterSearchHandler(self):
		print "OnMasterSearchHandler"

	def OnMasterDisconnectedHandler(self):
		print "OnMasterDisconnectedHandler"

	def OnDeviceConnectedHandler(self):
		print "OnDeviceConnectedHandler"

	def OnLocalServerStartedHandler(self):
		print "OnLocalServerStartedHandler"

	def OnAceptNewConnectionHandler(self, sock):
		print "OnAceptNewConnectionHandler"

	def OnTerminateConnectionHandler(self, sock):
		print "OnTerminateConnectionHandler"

	# Request from local network.
	def OnGetSensorInfoRequestHandler(self, packet, sock):
		print "OnGetSensorInfoRequestHandler"
		THIS.Node.LocalServiceNode.SendSensorInfoResponse(sock, packet, self.Tests)

	# Request from local network.
	def OnSetSensorInfoRequestHandler(self, packet, sock):
		print "OnSetSensorInfoRequestHandler"

	'''
	{
		"direction": "proxy_request", 
		"command": "upload_file", 
		"piggybag": {
			"identifier": 2
		}, 
		"payload": {
			"header": {
				"source": "WEBFACE", 
				"destination": "ac6de837-7863-72a9-c789-a0aae7e9d410"
			}, 
			"data": {
				"upload": {
					"chank_size": 87, 
					"file": "elopBuild.sh", 
					"content": "006520000a", 
					"chank": 1, 
					"action": "dfu", 
					"size": 87,
					"chanks": 1
				}
			}
		}
	}
	'''

	# Upload file handler, packet already in JSON type
	def OnUploadFileRequestHandler(self, packet, sock):
		print ("OnUploadFileRequestHandler")
		self.Locker.acquire()
		try:
			content 	= packet["payload"]["data"]["upload"]["content"]
			action 		= packet["payload"]["data"]["upload"]["action"]
			chankSize 	= packet["payload"]["data"]["upload"]["chank_size"]
			index 		= packet["payload"]["data"]["upload"]["chank"]
			size 		= packet["payload"]["data"]["upload"]["size"]
			name 		= packet["payload"]["data"]["upload"]["file"]
			chanks 		= packet["payload"]["data"]["upload"]["chanks"]
			uuid 		= packet["payload"]["header"]["destination"]
			print ("Upload Info:", name, index, chankSize, size, action, chanks)

			upload = self.FindUpload(name)
			if upload is None:
				upload = FileUpload(name, size, uuid, chanks)
				self.Uploads.append(upload)

			isUploaded = upload.AddFragment(content, index, chankSize)
			if isUploaded is True:
				# Upload is done
				data, length = upload.GetFileRaw()
				self.Uploads.remove(upload)

				file = MkSFile.File()
				file.SaveArrayToFile(".\\fw-upload\\" + name, data)
				THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
					'file': name,
					'length': length,
					'uuid': uuid,
					'status': 'done'
				})
			else:
				THIS.Node.LocalServiceNode.SendCustomCommandResponse(sock, packet, {
					'file': name,
					'length': length,
					'uuid': uuid,
					'status': 'inprogress',
					'chunk': index
				})
			self.Locker.release()
		except Exception as e:
			print (e)
			self.Locker.release()

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
		if self.RequestQueue.empty() is False:
			# Wait till previouse request finish processing (Do not block)
			if self.External.GetStatus() is False:
				self.CurrentProcessedRequest = self.RequestQueue.get()
				if sys.platform in ["win32"]:
					processName = ["python", '-u', "./TDMReplace/TDMTester.py", "--json"]
				elif sys.platform in ["linux","linux2"]:
					processName = ["/usr/local/bin/python3", '-u', "./TDMReplace/TDMTester.py", "--json"]
				else:
					processName = ["/usr/local/bin/python3", '-u', "./TDMReplace/TDMTester.py", "--json"]
				processName += self.CurrentProcessedRequest['request']
				user = self.CurrentProcessedRequest['user']
				self.External.CallProcess(processName, user)
		
		if time.time() - self.CurrentTimestamp > self.Interval:
			print "WorkingHandler"

			self.CheckingForUpdate = True
			self.CurrentTimestamp = time.time()

			for idx, item in enumerate(THIS.Node.LocalServiceNode.GetConnections()):
				print "  ", str(idx), item.LocalType, item.UUID, item.IP, item.Port, item.Type

Service = MkSSlaveNode.SlaveNode()
Node 	= MkSNode.Node("TDD Tests", Service)
THIS 	= Context(Node)

def signal_handler(signal, frame):
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
	THIS.Node.LocalServiceNode.OnUploadFileRequestCallback			= THIS.OnUploadFileRequestHandler
	THIS.Node.LocalServiceNode.OnCustomCommandRequestCallback		= THIS.OnCustomCommandRequestHandler
	THIS.Node.LocalServiceNode.OnCustomCommandResponseCallback		= THIS.OnCustomCommandResponseHandler

	THIS.Node.Run(THIS.WorkingHandler)
	print "Exit Node ..."

if __name__ == "__main__":
    main()
