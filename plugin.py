# Domoticz Woonveilig Gate03
# Works with GATE03
# Author: Sjaak Spiegels
#
# Based on code from: 
#
# https://github.com/StuffNL/domoticz-woonveilig
# https://github.com/jeroenterheerdt/python-egardia
# https://github.com/System67/GateKeeper
#
"""
<plugin key="WoonveiligGate03" name="Woonveilig Gate03" version="1.0.0" author="Sjaak" wikilink="" externallink="">
    <params>
        <param field="Address" label="IP Address" width="200px" required="true" default=""/>
        <param field="Username" label="Username" width="150px" required="true" default=""/>
        <param field="Password" label="Password" width="150px" required="true" default="" password="true"/>
        <param field="Port" label="Port (default = 80)" width="150px" required="true" default=""/>

        <param field="Mode1" label="MQTT Server" width="200px" required="true" default=""/>
        <param field="Mode2" label="MQTT Port" width="150px" required="true" default="1883"/>
        <param field="Mode3" label="MQTT Username" width="150px" required="true" default=""/>
        <param field="Mode4" label="MQTT Password" width="150px" required="true" default="" password="true"/>
        <param field="Mode5" label="MQTT State Topic" width="150px" required="true" default=""/>

        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug" default="true"/>
                <option label="False" value="Normal" />
            </options>
      </param>
  </params>
  </plugin>
"""

import Domoticz
import http.client
import base64
import json
import paho.mqtt.client as mqtt
from datetime import datetime

class BasePlugin:
    TYPES_IR = ["IR","IR Sensor"]
    TYPES_KEYPAD = ["Remote Keypad", "Keypad"]
    TYPES_DOORCONTACTS = ["Door Contact"]
    PANEL_URL = "/action/panelCondGet"
    SENSOR_URL = "/action/deviceListGet" 
    TYPE_KEY = "type_f"
    UNIT_KEY = "zone"
    
    mqttClient = None
    mqttServeraddress = "localhost"
    mqttServerport = 1883
    mqttUsername = ""
    mqttPassword = ""
    mqttStatetopic = ""
    mqttEnabled = False

    _authorization = ""
    connection = None

    def __init__(self):
        return

    def onStart(self):
        Domoticz.Debug("onStart called")
        if Parameters["Mode6"] == "Debug":
            Domoticz.Debugging(1)        
            Domoticz.Log("Debugging ON")
            DumpConfigToLog()

        self._authorization = base64.b64encode("{0}:{1}".format(Parameters["Username"], Parameters["Password"]).encode()).decode("ascii")
        self.connect_to_adaptor()

        self.mqttServeraddress = Parameters["Mode1"].strip()
        self.mqttServerport = Parameters["Mode2"].strip()
        self.mqttUsername = Parameters["Mode3"].strip()
        self.mqttPassword = Parameters["Mode4"].strip()
        self.mqttStatetopic = Parameters["Mode5"].strip()

        if (self.mqttServeraddress != ""):
            try:
                self.mqttClient = mqtt.Client()
                self.mqttClient.on_connect = onMQTTConnect
                self.mqttClient.username_pw_set(username=self.mqttUsername, password=self.mqttPassword)
                self.mqttClient.connect(self.mqttServeraddress, int(self.mqttServerport), 60) 
                self.mqttClient.loop_start()  
                self.mqttEnabled = True
            except:
                self.mqttEnabled = False
     

        sensors = self.read_sensors()
                
        #Add new devices
        for sensor in sensors:
            sensor_data = sensors[sensor]
            if (int(sensor_data[self.UNIT_KEY]) not in Devices):
                Domoticz.Log("Try to add sensor " + sensor_data["name"])
                if (sensor_data[self.TYPE_KEY] in self.TYPES_DOORCONTACTS): 
                    Domoticz.Device(Name=sensor_data["name"], TypeName="Switch", Switchtype=11, Unit=int(sensor_data[self.UNIT_KEY])).Create()
                elif (sensor_data[self.TYPE_KEY] in self.TYPES_KEYPAD and 99 not in Devices):
                    Options = {"LevelActions": "||","LevelNames": "Off|Home|On","LevelOffHidden": "false","SelectorStyle": "1"}
                    Domoticz.Device(Name=sensor_data["name"], Unit=99, TypeName="Selector Switch", Switchtype=18, Image=13, Options=Options).Create()
                elif (sensor_data[self.TYPE_KEY] in self.TYPES_IR): 
                    Domoticz.Device(Name=sensor_data["name"], TypeName="Switch", Switchtype=8, Unit=int(sensor_data[self.UNIT_KEY])).Create()
                else:
                    Domoticz.Log("Device " + sensor_data["name"] + " is not added to devices")

    def onStop(self):
        Domoticz.Debug("onStop called")
        self.connection.close()
        if self.mqttEnabled:
            self.mqttClient.disconnect()

    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug("onConnect called")

    def onMQTTConnect(self, client, userdata, flags, rc):
        Domoticz.Debug("onMQTTConnect called")
        Domoticz.Debug("Connected to " + self.mqttServeraddress + " with result code {}".format(rc))

    def onMessage(self, Connection, Data):
        Domoticz.Debug("onMessage called")

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Debug("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self, Connection):
        Domoticz.Debug("onDisconnect called")

    def onHeartbeat(self):
        Domoticz.Debug("onHeartbeat called")
 
        sensors = self.read_sensors()
        
        dateTimeObj = datetime.now()
        json_msg = {}
        json_msg["Time"] = str(dateTimeObj)

        for sensor in sensors:
            sensor_data = sensors[sensor]

            sensor_triggered = get_sensor_triggered(sensor_data)

            if (sensor_data[self.TYPE_KEY] in self.TYPES_DOORCONTACTS): 
                UpdateDevice(int(sensor_data[self.UNIT_KEY]), nValue = 1 if sensor_triggered == True else 0, sValue = True if sensor_triggered == True else False)
                json_msg["DOORSENSOR" + str(sensor_data[self.UNIT_KEY])] = "OPEN" if sensor_triggered == True else "CLOSED"
            elif (sensor_data[self.TYPE_KEY] in self.TYPES_IR): 
                UpdateDevice(int(sensor_data[self.UNIT_KEY]), nValue = 1 if sensor_triggered == True else 0, sValue = True if sensor_triggered == True else False)        
                json_msg["IRSENSOR" + str(sensor_data[self.UNIT_KEY])] = "ON" if sensor_triggered == True else "OFF"
    
        panel_condition = self.read_panel_condition()
        alarm_state = get_panel_state(panel_condition)
        
        if alarm_state == "DISARM":
            DomoState = 0
            json_msg["PANEL"] = "DISARM"
        elif alarm_state == "HOME":
            DomoState = 10
            json_msg["PANEL"] = "HOME"
        elif alarm_state == "ARM":
            DomoState = 20
            json_msg["PANEL"] = "ARM"
        elif alarm_state == "FULL ARM":
            DomoState = 20
            json_msg["PANEL"] = "FULL ARM"

        UpdateDevice(Unit=99, nValue = DomoState, sValue= str(DomoState))
        if self.mqttEnabled:
            Domoticz.Debug("MQTT message: " + str(json.dumps(json_msg)))
            for i in range(3):
                try:
                    self.mqttClient.publish("tele/" + self.mqttStatetopic + "/SENSOR", payload = json.dumps(json_msg), qos=1)
                    break
                except:
                    Domoticz.Error("Connection problems MQTT check URL and port")
                    self.mqttClient.connect(self.mqttServeraddress, int(self.mqttServerport), 60) 
                    self.mqttClient.loop_start()  

    def connect_to_adaptor(self):
        Domoticz.Debug("Connecting to GATE")
        self.connection = http.client.HTTPConnection(Parameters["Address"],port=Parameters["Port"])    

    def read_sensors(self):
        Domoticz.Debug("Read sensors")

        sensors = {}
        for i in range(3):
            try:
                self.connection.request("GET", self.SENSOR_URL, headers={'Authorization': "Basic " + self._authorization})
                r1 = self.connection.getresponse()
            except:
                Domoticz.Error("Connection problems Sensors check URL and port")
                self.connect_to_adaptor()
            
            if(r1.status == 200):
                Domoticz.Debug("Valid connection data returned")
                break
        else:
            Domoticz.Error("Connection Error : " +str(r1.status) +" Reason: " + r1.reason )
            Domoticz.Error("Please check username and/or password")
            return      

        data = r1.read().decode("utf-8", "ignore")
        json = parse_to_json(data)

        for sensor in json["senrows"]:
            sensors[sensor["id"]] = sensor

        return sensors

        
    def read_panel_condition(self):
#        if (self.connection.Connected() == False):
#            self.connect_to_adaptor()

        for i in range(3):
            try:
                self.connection.request("GET", self.PANEL_URL, headers={'Authorization': "Basic " + self._authorization})
                r1 = self.connection.getresponse()
            except:
                c
                self.connect_to_adaptor()
            
            if(r1.status == 200):
                Domoticz.Debug("Valid connection data returned")
                break
        else:
            Domoticz.Error("Connection Error : " +str(r1.status) +" Reason: " + r1.reason )
            Domoticz.Error("Please check username and/or password")
            return      

        data = r1.read().decode("utf-8", "ignore")
        json = parse_to_json(data)
        Domoticz.Debug(str(json))
        return json

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

def onMQTTConnect(client, userdata, flags, rc):
    global _plugin
    _plugin.onMQTTConnect(client, userdata, flags, rc)

    # Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return

def get_sensor_triggered(sensor):
    if sensor is not None:
        Domoticz.Debug("Device: " + sensor["name"] + " status = " + sensor["status"] )
        if sensor['status'].upper() == "DOOR OPEN":
            return True
        elif sensor['status'].upper() == "DOOR CLOSE":
            return False
    else:
        return None

def get_panel_state(panel):
    if panel is not None:
        status = panel['updates']['mode_a1']
        return status.upper()
    else:
        return None

def parse_to_json(sensor_data):
    import json
    sensor_data = sensor_data.replace("/*-secure-","")
    sensor_data = sensor_data.replace("*/","")
    sensor_data = sensor_data.replace('{	senrows : [','{"senrows":[')
    property_names_to_fix = ["no","type","type_f","area", "zone", "name", "attr", "cond", "cond_ok", "battery", "battery_ok", "tamp", "tamper", "tamper_ok", "bypass", "rssi", "status", "id","su"]
    for p in property_names_to_fix:
        sensor_data = sensor_data.replace(p+' :','"'+p+'":')
    data = json.loads(sensor_data, strict=False)
    return data

def UpdateDevice(Unit, nValue, sValue):
# Make sure that the Domoticz device still exists (they can be deleted) before updating it 
    if (Unit in Devices):
        if (Devices[Unit].nValue != nValue) or (Devices[Unit].sValue != sValue):
            Devices[Unit].Update(nValue=nValue, sValue=str(sValue))
            Domoticz.Debug("Update "+str(nValue)+":'"+str(sValue)+"' ("+Devices[Unit].Name+")")
    return

