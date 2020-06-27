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
import smtplib, ssl
import base64

from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.MIMEImage import MIMEImage

from mksdk import MkSFile
from mksdk import MkSSlaveNode
from mksdk import MkSUtils

class Context():
	def __init__(self, node):
		self.ClassName 					= "EMail Service"
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
		self.RequestHandlers			= {
			'send_email_html':					self.Request_SendEmailHtmlHandler,
			'send_email_html_with_image':		self.Request_SendEmailHtmlWithImageHandler
		}
		self.ResponseHandlers			= {
		}
		self.Orders 					= Queue.Queue()
		self.NodesDict					= {}

		self.GmailUser 					= "yegeniy.kiveisha.mks@gmail.com"
		self.GmailPassword 				= "makesense100$"

	def UndefindHandler(self, message_type, source, data):
		self.Node.LogMSG("({classname})# [UndefindHandler]".format(classname=self.ClassName),5)
	
	def Request_SendEmailHtmlHandler(self, sock, packet):
		self.Node.LogMSG("({classname})# [Request_SendEmailHtmlHandler]".format(classname=self.ClassName),5)
		payload = self.Node.BasicProtocol.GetPayloadFromJson(packet)
		
		to 		= payload["message"]["to"]
		subject = payload["message"]["subject"]
		body 	= payload["message"]["body"]
		context = ssl.create_default_context()

		message = 'Subject: {}\n\n{}'.format(subject, body)

		try:
			#server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
			#server = smtplib.SMTP('smtp.gmail.com',587)
			server = smtplib.SMTP('smtp.gmail.com:587')
			server.ehlo()
			server.starttls()
			server.login(self.GmailUser, self.GmailPassword)
			server.sendmail(self.GmailUser, to, message)
			server.close()

			self.Node.LogMSG("({classname})# Mail was sent.".format(classname=self.ClassName),5)
		except Exception as e:
			self.Node.LogException("[Request_SendEmailHtmlHandler]",e,3)
			return THIS.Node.BasicProtocol.BuildResponse(packet, {
				'status': 'FAILED'
			})
		
		return THIS.Node.BasicProtocol.BuildResponse(packet, {
			'status': 'OK'
		})
	
	def Request_SendEmailHtmlWithImageHandler(self, sock, packet):
		self.Node.LogMSG("({classname})# [Request_SendEmailHtmlWithImageHandler]".format(classname=self.ClassName),5)
		payload = self.Node.BasicProtocol.GetPayloadFromJson(packet)

		to 		= payload["message"]["to"]
		subject = payload["message"]["subject"]
		body 	= payload["message"]["body"]
		image 	= payload["message"]["image"]

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

			self.Node.LogMSG("({classname})# Mail was sent.".format(classname=self.ClassName),5)
			self.Node.LogMSG("({classname})# Node system loaded ...".format(classname=self.ClassName),5)
		except Exception as e:
			self.LogException("[Request_SendEmailHtmlWithImageHandler]",e,3)

		return

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

	def WorkingHandler(self):
		if time.time() - self.CurrentTimestamp > self.Interval:
			self.CheckingForUpdate = True
			self.CurrentTimestamp = time.time()

			self.Node.LogMSG("\nTables:",5)
			connections = THIS.Node.GetConnectedNodes()
			for idx, key in enumerate(connections):
				node = connections[key]
				self.Node.LogMSG("  {0}\t{1}\t{2}\t{3}\t{4}\t{5}\t{6}\t{7}".format(str(idx),node.Obj["local_type"],node.Obj["uuid"],node.IP,node.Obj["listener_port"],node.Obj["type"],node.Obj["pid"],node.Obj["name"]),5)
			self.Node.LogMSG("",5)

Node = MkSSlaveNode.SlaveNode()
THIS = Context(Node)

def signal_handler(signal, frame):
	THIS.Node.Stop("Accepted signal from other app")

def main():
	signal.signal(signal.SIGINT, signal_handler)
	THIS.Node.SetLocalServerStatus(True)
	
	# Node callbacks
	THIS.Node.NodeSystemLoadedCallback						= THIS.NodeSystemLoadedHandler
	THIS.Node.OnApplicationRequestCallback					= THIS.OnApplicationCommandRequestHandler
	THIS.Node.OnApplicationResponseCallback					= THIS.OnApplicationCommandResponseHandler
	
	THIS.Node.Run(THIS.WorkingHandler)
	print ("Exit Node ...")

if __name__ == "__main__":
    main()
