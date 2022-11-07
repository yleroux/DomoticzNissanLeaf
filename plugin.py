# Basic Python Plugin Example
#
# Author: Breizhcat
#
"""
<plugin key="NissanLeaf" name="Domoticz Nissan Leaf" author="breizhcat" version="1.0.5" wikilink="http://www.domoticz.com/wiki/plugins/plugin.html" externallink="https://github.com/BreizhCat/DomoticzNissanLeaf">
    <description>
		<h2>Nissan Leaf</h2><br/>
		<h3>Features</h3>
		<ul style="list-style-type:square">
			<li>Battery Level</li>
			<li>Charging Status</li>
            <li>Range autonomy (with / without AC)</li>
            <li>Information about distance driven</li>
		</ul>
    </description>
    <params>
        <param field="Username" label="Nissan Account"  width="150px"  required="true" />
        <param field="Password" label="Nissan Password" width="150px" required="true" password="true" />
        <param field="Mode5" label="Region Code" width="500px">
            <options>
                <option label="Europe" value="NE" />
                <option label="United States" value="NNA" />
                <option label="Canada" value="NCI" />
                <option label="Japan" value="NML" />
                <option label="Australia" value="NMA" />
            </options>
        </param>
        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal" default="true" />
            </options>
        </param>
    </params>
</plugin>
"""
BASE_URL = "https://gdcportalgw.its-mo.com/api_v210707_NE/gdc/"

IMAGE_CAR = "NissanLeafCar"
IMAGE_BATTERY = "NissanLeafBattery"
IMAGE_PLUG = "NissanLeafPlug"

DEVICE_BATTERY = 1
DEVICE_RANGE_AC = 2
DEVICE_RANGE_NO_AC = 3
DEVICE_CHARGE = 4
DEVICE_UPDATE = 5
DEVICE_ODOMETER = 6
DEVICE_CABIN_TEMP = 7

import Domoticz
from datetime import datetime
import threading, time

# Based on https://github.com/nricklin/leafpy
from Crypto.Cipher import Blowfish
import requests, base64


def login(
    username, password, region_code="NNA", initial_app_strings="9s5rfKVuMrT03RtzajWNcA"
):
    baseprm = b"88dSp7wWnV3bvv9Z88zEwg"
    c1 = Blowfish.new(baseprm, Blowfish.MODE_ECB)
    packingLength = 8 - len(password) % 8
    packedPassword = password + chr(packingLength) * packingLength
    encryptedPassword = c1.encrypt(packedPassword.encode("latin-1"))
    encodedPassword = base64.standard_b64encode(encryptedPassword)

    url = BASE_URL + "/UserLoginRequest.php"
    data = {
        "RegionCode": region_code,
        "UserId": username,
        "initial_app_str": initial_app_strings,
        "Password": encodedPassword,
    }
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.post(url, data=data, headers=headers)
    r.raise_for_status()
    if not r.json()["status"] == 200:
        raise Exception(
            "Cannot login.  Probably username & password are wrong. " + r.text
        )

    custom_sessionid = r.json()["VehicleInfoList"]["vehicleInfo"][0]["custom_sessionid"]
    VIN = r.json()["CustomerInfo"]["VehicleInfo"]["VIN"]

    return custom_sessionid, VIN


class Leaf(object):
    """Make requests to the Nissan Connect API to get Leaf Info"""

    custom_sessionid = None
    VIN = None
    region_code = None

    def __init__(
        self,
        username=None,
        password=None,
        custom_sessionid=None,
        VIN=None,
        region_code="NNA",
    ):

        self.region_code = region_code
        if username and password:
            self.custom_sessionid, self.VIN = login(
                username, password, self.region_code
            )
        elif custom_sessionid and VIN:
            self.custom_sessionid = custom_sessionid
            self.VIN = VIN
        else:
            raise Exception(
                "Need either username & password or custom_sessionid & VIN."
            )

    def __getattr__(self, name):
        """
        Top secret magic.  Calling Leaf.<some_function_name>() hits <some_function_name>.php
        """

        if name.startswith("__"):
            raise AttributeError(name)

        def call(**kwargs):
            url = BASE_URL + name + ".php"
            data = {
                "RegionCode": self.region_code,
                "custom_sessionid": self.custom_sessionid,
                "VIN": self.VIN,
            }
            for k in kwargs:
                data[k] = kwargs[k]
            r = requests.post(url, data=data)
            r.raise_for_status()
            if not r.json()["status"] == 200:
                raise Exception(
                    "Error making request. Perhaps the session has expired."
                )
            return r.json()

        return call


class BasePlugin:
    enabled = False

    def __init__(self):
        Domoticz.Log("__init__ called")

    def onStart(self):
        if Parameters["Mode6"] == "Debug":
            Domoticz.Debugging(1)

        self._create_icons()
        self._create_devices()
        self._updateDevices()

        Domoticz.Log("onStart called")

    def onStop(self):
        Domoticz.Log("onStop called")

    def onConnect(self, Connection, Status, Description):
        Domoticz.Log("onConnect called")

    def onMessage(self, Connection, Data):
        Domoticz.Log("onMessage called")

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Log(
            "onCommand called for Unit "
            + str(Unit)
            + ": Parameter '"
            + str(Command)
            + "', Level: "
            + str(Level)
        )

        if Unit == DEVICE_UPDATE:
            self._updateDevices()
            Domoticz.Log(str(Devices[DEVICE_ODOMETER].Options))

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log(
            "Notification: "
            + Name
            + ","
            + Subject
            + ","
            + Text
            + ","
            + Status
            + ","
            + str(Priority)
            + ","
            + Sound
            + ","
            + ImageFile
        )

    def onDisconnect(self, Connection):
        Domoticz.Log("onDisconnect called")

    def onHeartbeat(self):
        _time = datetime.now()

        if _time.minute in [0, 15, 30, 45] and _time.second < 10:
            Domoticz.Log("Mise à jour des devices")
            self._updateDevices()

    def _create_icons(self):
        if IMAGE_CAR not in Images:
            Domoticz.Image("IconNissanLeafCar.zip").Create()
        if IMAGE_BATTERY not in Images:
            Domoticz.Image("IconNissanLeafBattery.zip").Create()
        if IMAGE_PLUG not in Images:
            Domoticz.Image("IconNissanLeafPlug.zip").Create()

    def _create_devices(self):
        if DEVICE_BATTERY not in Devices:
            Domoticz.Device(
                Name="Battery",
                Unit=DEVICE_BATTERY,
                TypeName="Percentage",
                Image=Images[IMAGE_BATTERY].ID,
                Description="Battery Remaining Amount",
                Used=1,
            ).Create()

        if DEVICE_RANGE_AC not in Devices:
            Domoticz.Device(
                Name="Distance AC",
                Unit=DEVICE_RANGE_AC,
                TypeName="Custom",
                Options={"Custom": "0;km"},
                Image=Images[IMAGE_CAR].ID,
                Description="Maximum Distance with A/C",
                Used=1,
            ).Create()

        if DEVICE_RANGE_NO_AC not in Devices:
            Domoticz.Device(
                Name="Distance w/o AC",
                Unit=DEVICE_RANGE_NO_AC,
                TypeName="Custom",
                Options={"Custom": "0;km"},
                Image=Images[IMAGE_CAR].ID,
                Description="Maximum Distance with A/C",
                Used=1,
            ).Create()

        if DEVICE_CHARGE not in Devices:
            Domoticz.Device(
                Unit=DEVICE_CHARGE,
                Name="Charge",
                Image=Images[IMAGE_PLUG].ID,
                Type=244,
                Subtype=62,
                Switchtype=0,
                Used=1,
            ).Create()

        if DEVICE_UPDATE not in Devices:
            Domoticz.Device(
                Unit=DEVICE_UPDATE,
                Name="Refresh Data",
                Type=244,
                Subtype=62,
                Switchtype=9,
                Used=1,
            ).Create()

        if DEVICE_ODOMETER not in Devices:
            Domoticz.Device(
                Name="Driven",
                Unit=DEVICE_ODOMETER,
                Type=243,
                Subtype=33,
                Switchtype=3,
                Options={
                    "AddjValue2": 1000,
                    "ValueQuantity": "Kilometers",
                    "ValueUnits": "Km",
                    "AddDBLogEntry": "true",
                    "DisableLogAutoUpdate": "true",
                },
                Image=Images[IMAGE_CAR].ID,
                Description="Distance driven",
                Used=1,
            ).Create()

#         if DEVICE_CABIN_TEMP not in Devices:
#             Domoticz.Device(
#                 Unit=DEVICE_CABIN_TEMP,
#                 Name="Cabin Temp",
#                 Type=80,
#                 Subtype=5,
#                 Used=1,
#             ).Create()

    def _updateDevices(self):
        thread = threading.Thread(
            name="UpdateLeafInformations",
            target=BasePlugin._connect_and_update,
            args=(self,),
        )
        thread.start()

    def _connect_and_update(self):
        try:
            Domoticz.Log("Plugin running - Trying to connect")
            leaf = Leaf(
                Parameters["Username"],
                Parameters["Password"],
                region_code=Parameters["Mode5"],
            )
            if leaf:
                battery = leaf.BatteryStatusRecordsRequest()

                batteryRemaining = battery["BatteryStatusRecords"]["BatteryStatus"][
                    "BatteryRemainingAmount"
                ]
                batteryCapacity = battery["BatteryStatusRecords"]["BatteryStatus"][
                    "BatteryCapacity"
                ]
                batteryValue = float(
                    "{:.2f}".format(
                        (int(batteryRemaining) / int(batteryCapacity)) * 100
                    )
                )

                nValue = int(batteryValue)
                sValue = (
                    str(batteryValue)
                    + ";"
                    + str(batteryValue)
                    + ";"
                    + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                Devices[DEVICE_BATTERY].Update(nValue=nValue, sValue=sValue)
                Domoticz.Log("Battery = " + str(batteryValue) + " %")

                nValue = int(
                    int(battery["BatteryStatusRecords"]["CruisingRangeAcOn"]) / 1000
                )
                sValue = (
                    str(nValue)
                    + ";"
                    + str(nValue)
                    + ";"
                    + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                Domoticz.Log("Range with AC = {} km".format(nValue))
                Devices[DEVICE_RANGE_AC].Update(nValue=nValue, sValue=sValue)

                nValue = int(
                    int(battery["BatteryStatusRecords"]["CruisingRangeAcOff"]) / 1000
                )
                sValue = (
                    str(nValue)
                    + ";"
                    + str(nValue)
                    + ";"
                    + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                Devices[DEVICE_RANGE_NO_AC].Update(nValue=nValue, sValue=sValue)
                Domoticz.Log("Range without AC = {} km".format(nValue))

                status = battery["BatteryStatusRecords"]["BatteryStatus"][
                    "BatteryChargingStatus"
                ]
                if status == "NOT_CHARGING":
                    Devices[DEVICE_CHARGE].Update(nValue=0, sValue="0")
                else:
                    Devices[DEVICE_CHARGE].Update(nValue=1, sValue="1")

                Domoticz.Log("Charging State = {}".format(status))

                distance = leaf.PriceSimulatorDetailInfoRequest()
                today = False
                for i in distance["PriceSimulatorDetailInfoResponsePersonalData"][
                    "PriceSimulatorDetailInfoDateList"
                ]["PriceSimulatorDetailInfoDate"]:
                    km = 0
                    for j in i["PriceSimulatorDetailInfoTripList"][
                        "PriceSimulatorDetailInfoTrip"
                    ]:
                        km += int(j["TravelDistance"])

                    nValue = 0
                    kmsValue = float("{:.2f}".format(km))
                    sValue = str(kmsValue) + ";" + str(kmsValue) + ";" + i["TargetDate"]
                    Devices[DEVICE_ODOMETER].Update(nValue=nValue, sValue=sValue)

                    if i["TargetDate"] == datetime.now().strftime("%Y-%m-%d"):
                        today = True
                        sValue = str(kmsValue) + ";" + str(kmsValue)
                        Devices[DEVICE_ODOMETER].Update(nValue=nValue, sValue=sValue)

                if not today:
                    Devices[DEVICE_ODOMETER].Update(nValue=0, sValue="0;0")


#                 Domoticz.Log("Retrieve Cabin Temp")
#                 result = leaf.GetInteriorTemperatureRequestForNsp()
#                 while True:
#                     temp = leaf.GetInteriorTemperatureResultForNsp(resultKey=result['resultKey'])

#                     if temp['responseFlag'] == '0':
#                         time.sleep(30)
#                     else:
#                         Domoticz.Log(f"Cabin Temp ={temp['Inc_temp']}°c")
#                         Devices[DEVICE_CABIN_TEMP].Update(nValue=0, sValue=f"{temp['Inc_temp']}")
#                         break
            else:
                Domoticz.Log("onHeartbeat Connection ko")
        except Exception as err:
            Domoticz.Error(
                "handleThread: "
                + str(err)
                + " line "
                + format(sys.exc_info()[-1].tb_lineno)
            )


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

    # Generic helper functions


def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug("'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return
