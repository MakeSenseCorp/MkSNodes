#!/usr/bin/python
import os
import sys
import signal
import json
import time
import thread
import threading
import calendar
from datetime import datetime

from mksdk import MkSFile

class TimerAction:
	def __init__(self, clockId, timerId):
		self.ClockId 	= clockId
		self.TimerId  	= timerId
		self.Activated 	= False
		self.TimeStamp  = None

class MkSTimer():
	def __init__(self):
		# Flags
		self.IsThreadRunning  		= False
		# Objects
		self.CurrentTimestamp 		= time.time()
		self.File 					= MkSFile.File()
		# Events
		self.OnClockTickEvent 		= None
		self.OnTimerTriggerEvent 	= None
		self.Clocks 				= {}
		self.Actions				= {}
		self.IntervalForAction 		= 10
		self.ConvertionTable		= {	6: 'SUN', 
										0: 'MON', 
										1: 'TUE', 
										2: 'WED', 
										3: 'THU',  
										4: 'FRI', 
										5: 'SAT' }

	def Run(self):
		self.IsThreadRunning = True
		thread.start_new_thread(self.WorkerThread, ())

	def Stop(self):
		self.IsThreadRunning = False

	def WorkerThread(self):
		print "[DEBUG::Timer] Start"
		# TODO - Find next closest timestamp
		while self.IsThreadRunning:
			Now 	= datetime.now()
			Date 	= str(Now.day) + "-" + str(Now.month) + "-" + str(Now.year)

			dtCurrent = Date + " " + str(Now.hour) + ":" + str(Now.minute)
			currentStamp = datetime.strptime(dtCurrent, "%d-%m-%Y %H:%M")


			self.CurrentTimestamp = calendar.timegm(currentStamp.utctimetuple())
			for uuid, clock in self.Clocks.iteritems():
				timers = clock["timers"]
				for timer in timers:
					DateTime 		= Date + " " + timer["start"]
					CurrentDateTime = datetime.strptime(DateTime, "%d-%m-%Y %H:%M")
					Timestamp 		= calendar.timegm(CurrentDateTime.utctimetuple())

					objAction = self.Actions[(uuid, timer["id"])]
					if self.ConvertionTable[datetime.today().weekday()] in timer["days"]:
						if Timestamp <= self.CurrentTimestamp and (self.CurrentTimestamp - Timestamp) < self.IntervalForAction:
							if objAction.Activated == False:
								if self.OnTimerTriggerEvent is not None:
									self.OnTimerTriggerEvent(uuid, timer["action"])
									objAction.Activated = True
									objAction.TimeStamp = self.CurrentTimestamp
						else:
							objAction.Activated = False

			# Sleep till next minute
			tillNextMinute = time.time() % 60
			time.sleep(60 - int(tillNextMinute))

			if self.OnClockTickEvent is not None:
				self.OnClockTickEvent()
		print "[DEBUG::Timer] Exit"

	def AddTimer(self, uuid, timer):
		clock = self.Clocks[uuid]
		clock["timers"].append(timer)
		self.Clocks[uuid] = clock
		self.SaveClock("timer/db_" + uuid + ".json", clock)
		self.Actions[(uuid, timer["id"])] = TimerAction(uuid, timer["id"])

	def RemoveTimer(self, uuid, timerId):
		clock = self.Clocks[uuid]

		for item in clock["timers"]:
			if str(item["id"]) == str(timerId):
				clock["timers"].remove(item)
				del self.Actions[(uuid, int(timerId))]

		self.Clocks[uuid] = clock
		self.SaveClock("timer/db_" + uuid + ".json", clock)

	def GetTimers(self, uuid):
		# TODO - Main process does not exit with this (BUG)
		# return json.dumps(self.Timers.get(uuid))
		return json.dumps(self.Clocks.get(uuid))

	def SaveClock(self, file, clock):
		self.File.SaveStateToFile(file, json.dumps(clock))

	def LoadClocks(self, idList):
		for uuid in idList:
			RawClocks = self.File.LoadStateFromFile("timer/db_" + uuid + ".json")
			self.Clocks[uuid] = json.loads(RawClocks)
			timers = self.Clocks[uuid]["timers"]
			for timer in timers:
				self.Actions[(uuid, timer["id"])] = TimerAction(uuid, timer["id"])