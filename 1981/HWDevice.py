import os
import sys
import json

from mksdk import MkSAbstractDevice

DEF_ID 		= 0
DEF_TYPE 	= 1
DEF_VALUE 	= 2
DEF_PIN 	= 3

class LocalHWDevice(MkSAbstractDevice.AbstractDevice):
	def __init__(self):
		MkSAbstractDevice.AbstractDevice.__init__(self)

		self.Handlers = {
			'get_device_uuid':		self.GetDeviceUuidHandler,
			'get_device_info':		self.GetDeviceInfoHandler,
			'get_sensor_info':		self.GetSensorInfoHandler,
			'set_sensor_info':		self.SetSensorInfoHandler,
			'get_sensor_list_info': self.GetSensorListInfoHandler
		}

		self.SwitchList = []

		switches = self.DeviceInfoJson["switches"]
		for item in switches:
			self.SwitchList.append([item["id"],item["type"],0,item["pin"]])

	def GetDeviceUuidHandler(self, payload):
		return "{\"uuid\":\"" + self.UUID + "\"}"

	def GetDeviceInfoHandler(self, payload):
		return json.dumps(self.DeviceInfoJson)

	def GetSensorListInfoHandler(self, payload):
		sensors = "{\"sensors\":["
		for item in self.SwitchList:
			sensors += "{\"id\":\"" + str(item[DEF_ID]) + "\",\"value\":" + str(item[DEF_VALUE]) + "},"
		sensors = sensors[:-1] + ']}'
		return sensors

	def GetSensorInfoHandler(self, payload):
		sensorId = payload["sensor"]["id"]

		for item in self.SwitchList:
			if sensorId in item[DEF_ID]:
				return "{\"sensor\":{\"id\":\"" + str(item[DEF_ID]) + "\",\"value\":" + str(item[DEF_VALUE]) + "}}"

	def SetSensorInfoHandler(self, payload):
		sensorId 	= payload["sensor"]["id"]
		sensorValue = payload["sensor"]["value"]

		print "[Device]", sensorId, sensorValue

		# Set HW relay.
		# Check voltage, if it is as expected.

		# Update database.
		for item in self.SwitchList:
			if sensorId in item[DEF_ID]:
				item[DEF_VALUE] = sensorValue
				return "{\"sensor\":{\"id\":\"" + str(item[DEF_ID]) + "\",\"value\":" + str(item[DEF_VALUE]) + "}}"
		return ""

	def Send(self, data):
		jsonData 	= json.loads(data)
		command 	= jsonData['cmd']
		resData = self.Handlers[command](jsonData['payload'])

		response = "{\"cmd\":\"" + command + "\",\"payload\":" + resData + "}"
		return response

	# Here will be all the GPIO logic