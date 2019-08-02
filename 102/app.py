#!/usr/bin/python
import os
import sys
import gc
import signal
import json
import time
import thread
import threading
import logging

import urllib2
import urllib
import Queue
import smtplib
import base64

from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.MIMEImage import MIMEImage

from mksdk import MkSFile
from mksdk import MkSNode
from mksdk import MkSSlaveNode
from mksdk import MkSLocalHWConnector
from mksdk import MkSUSBAdaptor
from mksdk import MkSProtocol

from flask import Response, request

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
		self.CustomRequestHandlers		= {
			'send_email_html':					self.SendEmailHtmlHandler,
			'send_email_html_with_image':		self.SendEmailHtmlWithImageHandler
		}
		self.CustomResponseHandlers		= {
		}
		self.Orders 					= Queue.Queue()
		self.NodesDict					= {}

		self.GmailUser 					= "yegeniy.kiveisha.mks@gmail.com"
		self.GmailPassword 				= "makesense100$"

	def UndefindHandler(self, message_type, source, data):
		print ("UndefindHandler")
	
	# { 
	# 	u'direction': u'proxy_request', 
	# 	u'command': u'send_email', 
	# 	u'piggybag': 0, 
	# 	u'payload': {
	# 		u'header': {
	# 			u'source': u'ac6de837-9863-72a9-c789-a0aae7e9d021', 
	# 			u'destination': u'ac6de837-9863-72a9-c789-a0aae7e9d023'
	# 		}, u'data': {
	# 			u'json': {
	# 				u'body': u'Hello', 
	# 				u'to': [u'yevgeniy.kiveisha@gmail.com'], 
	# 				u'type': u'text', 
	# 				u'subject': u'Test'
	# 			}, 
	# 			u'request': u'task_order'
	# 		}
	# 	}
	# }
	
	def SendEmailHtmlHandler(self, sock, packet):
		print ("SendEmailHtmlHandler", packet)
		
		to 		= packet["payload"]["data"]["json"]["to"]
		subject = packet["payload"]["data"]["json"]["subject"]
		body 	= packet["payload"]["data"]["json"]["body"]

		# to = ["yevgeniy.kiveisha@gmail.com"]
		# subject = "Makesense message"
		# body = "Hey, \nJust want to let you know security cameras detected motyion."
		email_text = """\
			From: %s
			To: %s
			Subject: %s

			%s
			""" % (self.GmailUser, ", ".join(to), subject, body)

		try:
			server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
			server.ehlo()
			server.login(self.GmailUser, self.GmailPassword)
			server.sendmail(self.GmailUser, to, email_text)
			server.close()

			print ('Email sent')
		except Exception as e:
			print ('Something went wrong...', e)
	
	def SendEmailHtmlWithImageHandler(self, sock, packet):
		print ("SendEmailHtmlHandler", packet)

		to 		= packet["payload"]["data"]["json"]["to"]
		subject = packet["payload"]["data"]["json"]["subject"]
		body 	= packet["payload"]["data"]["json"]["body"]
		image 	= packet["payload"]["data"]["json"]["image"]

		# to = "yevgeniy.kiveisha@gmail.com"

		# Create the root message and fill in the from, to, and subject headers
		msgRoot = MIMEMultipart('related')
		# msgRoot['Subject'] = 'MakeSense - Security alert from camera'
		msgRoot['Subject'] = subject
		msgRoot['From'] = self.GmailUser
		msgRoot['To'] = to
		msgRoot.preamble = 'This is a multi-part message in MIME format.'

		# Encapsulate the plain and HTML versions of the message body in an
		# 'alternative' part, so message agents can decide which they want to display.
		msgAlternative = MIMEMultipart('alternative')
		msgRoot.attach(msgAlternative)

		msgText = MIMEText('This is the alternative plain text message.')
		msgAlternative.attach(msgText)

		# We reference the image in the IMG SRC attribute by the ID we give it below
		# msgText = MIMEText('<b>Image taken by camera<br><img src="cid:image1"><br>', 'html')
		msgText = MIMEText(body, 'html')
		msgAlternative.attach(msgText)

		# This example assumes the image is in the current directory
		# fp = open('1.jpg', 'rb')
		msgImage = MIMEImage(base64.b64decode(image)) #(fp.read())
		# fp.close()

		# Define the image's ID as referenced above
		msgImage.add_header('Content-ID', '<image1>')
		msgRoot.attach(msgImage)

		try:
			server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
			server.ehlo()
			server.login(self.GmailUser, self.GmailPassword)
			server.sendmail(self.GmailUser, to, msgRoot.as_string())
			server.close()

			print ('Email sent!')
		except Exception as e:
			print ('Something went wrong...', e)

		return

	# Websockets
	def WSDataArrivedHandler(self, message_type, source, data):
		command = data['device']['command']
		self.Handlers[command](message_type, source, data)

	def WSConnectedHandler(self):
		print ("WSConnectedHandler")

	def WSConnectionClosedHandler(self):
		print ("WSConnectionClosedHandler")

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
		print ("OnLocalServerStartedHandler")

	def OnAceptNewConnectionHandler(self, sock):
		print ("OnAceptNewConnectionHandler")

	def OnTerminateConnectionHandler(self, sock):
		print ("OnTerminateConnectionHandler")

	def OnGetSensorInfoRequestHandler(self, packet, sock):
		print ("OnGetSensorInfoRequestHandler")

	def OnSetSensorInfoRequestHandler(self, packet, sock):
		print ("OnSetSensorInfoRequestHandler")
	
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
	
	def SetAddRequestHandler(self, key):
		print ("[WEB API] SetAddRequestHandler")

		fields 		= [k for k in request.form]
		jsonData 	= json.loads(fields[0])
		req   		= jsonData["request"]
		data  		= jsonData["json"]

		print (req, data)

		return json.dumps({
			'response':'OK'
		})

	def OnLocalServerListenerStartedHandler(self, sock, ip, port):
		THIS.Node.LocalServiceNode.AppendFaceRestTable(endpoint="/get/node_info/<key>", 						endpoint_name="get_node_info", 			handler=THIS.GetNodeInfoHandler)
		THIS.Node.LocalServiceNode.AppendFaceRestTable(endpoint="/set/node_info/<key>/<id>", 					endpoint_name="set_node_info", 			handler=THIS.SetNodeInfoHandler, 	method=['POST'])
		THIS.Node.LocalServiceNode.AppendFaceRestTable(endpoint="/get/node_sensors_info/<key>", 				endpoint_name="get_node_sensors", 		handler=THIS.GetSensorsInfoHandler)
		THIS.Node.LocalServiceNode.AppendFaceRestTable(endpoint="/set/node_sensor_info/<key>/<id>/<value>", 	endpoint_name="set_node_sensor_value", 	handler=THIS.SetSensorInfoHandler)
		THIS.Node.LocalServiceNode.AppendFaceRestTable(endpoint="/set/add_request/<key>", 						endpoint_name="add_request", 			handler=THIS.SetAddRequestHandler, 	method=['POST'])

	def WorkingHandler(self):
		if time.time() - self.CurrentTimestamp > self.Interval:
			print ("WorkingHandler")

			self.CheckingForUpdate = True
			self.CurrentTimestamp = time.time()

			for idx, item in enumerate(THIS.Node.LocalServiceNode.GetConnections()):
				print ("  ", str(idx), item.LocalType, item.UUID, item.IP, item.Port, item.Type)

Service = MkSSlaveNode.SlaveNode()
Node 	= MkSNode.Node("EMail Service", Service)
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
	# TODO - On file upload event.
	THIS.Node.LocalServiceNode.OnCustomCommandRequestCallback		= THIS.OnCustomCommandRequestHandler
	THIS.Node.LocalServiceNode.OnCustomCommandResponseCallback		= THIS.OnCustomCommandResponseHandler
	
	THIS.Node.Run(THIS.WorkingHandler)
	print ("Exit Node ...")

if __name__ == "__main__":
    main()
