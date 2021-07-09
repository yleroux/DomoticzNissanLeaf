import json, time, requests, argparse
from datetime import datetime


parser = argparse.ArgumentParser(prog="Domoticz Leaf Upload History")
group = parser.add_argument_group(title="Arguments")
group.add_argument("-f", "--file",  default=None, required = True)
group.add_argument("-s", "--server",  default=None, required = True)
group.add_argument("-d", "--device", default=None, required = True)

args = parser.parse_args()

with open(args.file) as fp:
    data = json.load(fp)
today_date = "2021-05-17" #datetime.now().strftime('%Y-%m-%d')
url_to_request = "http://" + args.server + "/json.htm?type=command&param=udevice&idx=" + args.device
for i in data['PriceSimulatorDetailInfoResponsePersonalData']['PriceSimulatorDetailInfoDateList']['PriceSimulatorDetailInfoDate']:
    km = 0
    
    for j in i['PriceSimulatorDetailInfoTripList']['PriceSimulatorDetailInfoTrip']:
        km += int(j['TravelDistance'])
        if i['TargetDate'] == today_date:
            print("---> TRIP" + j['GpsDatetime'])

    url_arguements = "&nvalue=0&svalue=" + str(km) + ";" + str(km) + ";" + i['TargetDate']
    #result = requests.get(url_to_request + url_arguements)
    #print(i['TargetDate']+" : " + str(km) + " m [Server Code: " + str(result.status_code) + "]")
    print(i['TargetDate']+" : " + str(km) + " m ")


    #time.sleep(2)