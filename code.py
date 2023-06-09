import board
import busio
import digitalio
import rtc
import time
import adafruit_rfm9x
import adafruit_requests as requests
import adafruit_wiznet5k.adafruit_wiznet5k_socket as socket
from adafruit_wiznet5k.adafruit_wiznet5k import WIZNET5K
import config
import microcontroller
import asyncio
from APRS import APRS
import adafruit_ntp
from adafruit_datetime import datetime

##SPI0
SPI0_RX = board.GP12
SPI0_CSn = board.GP13
SPI0_SCK = board.GP10
SPI0_TX = board.GP11

##reset
W5x00_RSTn = board.GP14

MY_MAC = (0x00, 0x16, 0x3e, 0x03, 0x04, 0x05)

ethernetRst = digitalio.DigitalInOut(W5x00_RSTn)
ethernetRst.direction = digitalio.Direction.OUTPUT

cs = digitalio.DigitalInOut(SPI0_CSn)
spi_bus = busio.SPI(SPI0_SCK, MOSI=SPI0_TX, MISO=SPI0_RX)

# Reset W5500 first
ethernetRst.value = False
time.sleep(1)
ethernetRst.value = True

# Initialize ethernet interface with DHCP
eth = WIZNET5K(spi_bus, cs, is_dhcp=True, mac=MY_MAC, hostname='rf.guru-aprsgw', debug=False)

# our version
VERSION = "RF.Guru_APRSGateway 0.1" 

print(f"{config.call} -=- {VERSION}\n")

print("Chip Version:", eth.chip)
print("MAC Address:", [hex(i) for i in eth.mac_address])
print("My IP address is:", eth.pretty_ip(eth.ip_address))
print("")

# Initialize a requests object with a socket and ethernet interface
requests.set_socket(socket, eth)

# NTP
ntp = adafruit_ntp.NTP(socket)
while not ntp.datetime:
    time.sleep(1)
now = ntp.datetime
rtc.RTC().datetime = now

# SEND iGate Postition
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(10)
s.connect((config.aprs_host, config.aprs_port))
stamp = datetime.now()
aprs = APRS()
pos = aprs.makePosition(config.latitude, config.longitude, -1, -1, config.symbol)
altitude = "/A={:06d}".format(int(config.altitude*3.2808399))
comment = config.comment + altitude
ts = aprs.makeTimestamp('z',now.tm_mday,now.tm_hour,now.tm_min,now.tm_sec)
message = f'user {config.call} pass {config.passcode} vers {VERSION}\n'
s.send(bytes(message, 'utf-8'))
message = f'{config.call}>APDW16,TCPIP*:@{ts}{pos}{comment}\n'
s.send(bytes(message, 'utf-8'))
print(f"{stamp}: [{config.call}] iGatePossition: {message}", end="")


async def iGateAnnounce():
    global s
    while True:
        temp = microcontroller.cpus[0].temperature
        freq = microcontroller.cpus[1].frequency/1000000
        rawpacket = f'{config.call}>APDW16,TCPIP*:>Running on RP2040 t:{temp}C f:{freq}Mhz\n'
        try:
            s.send(bytes(rawpacket, 'utf-8'))
        except:
            stamp = datetime.now()
            print(f"{stamp}: [{config.call}] iGateStatus: Reconnecting to ARPS {config.aprs_host} {config.aprs_port}")
            s.close()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((config.aprs_host, config.aprs_port))
            rawauthpacket = f'user {config.call} pass {config.passcode} vers {VERSION}\n'
            s.send(bytes(rawauthpacket, 'utf-8'))
            s.send(bytes(rawpacket, 'utf-8'))
        stamp = datetime.now()
        print(f"{stamp}: [{config.call}] iGateStatus: {rawpacket}", end="")
        stamp = datetime.now()
        aprs = APRS()
        pos = aprs.makePosition(config.latitude, config.longitude, -1, -1, config.symbol)
        altitude = "/A={:06d}".format(int(config.altitude*3.2808399))
        comment = config.comment + altitude
        ts = aprs.makeTimestamp('z',now.tm_mday,now.tm_hour,now.tm_min,now.tm_sec)
        message = f'{config.call}>APDW16,TCPIP*:@{ts}{pos}{comment}\n'
        try:
            s.send(bytes(message, 'utf-8'))
        except:
            stamp = datetime.now()
            print(f"{stamp}: [{config.call}] iGateStatus: Reconnecting to ARPS {config.aprs_host} {config.aprs_port}")
            s.close()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((config.aprs_host, config.aprs_port))
            rawauthpacket = f'user {config.call} pass {config.passcode} vers {VERSION}\n'
            s.send(bytes(rawauthpacket, 'utf-8'))
            s.send(bytes(message, 'utf-8'))
        
        print(f"{stamp}: [{config.call}] iGatePossition: {message}", end="")
        await asyncio.sleep(15*60)


async def tcpPost(packet):
    global s
    rawpacket = f'{packet}\n'
    try:
        s.send(bytes(rawpacket, 'utf-8'))
    except:
        stamp = datetime.now()
        print(f"{stamp}: [{config.call}] AprsTCPSend: Reconnecting to ARPS {config.aprs_host} {config.aprs_port}")
        s.close()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10)
        s.connect((config.aprs_host, config.aprs_port))
        rawauthpacket = f'user {config.call} pass {config.passcode} vers {VERSION}\n'
        s.send(bytes(rawauthpacket, 'utf-8'))
        s.send(bytes(rawpacket, 'utf-8'))
    stamp = datetime.now()
    print(f"{stamp}: [{config.call}] AprsTCPSend: {packet}")
    await asyncio.sleep(0)

async def httpPost(packet,rssi):
    await asyncio.sleep(0)
    json_data = {
        "call": config.call,
        "lat": config.latitude,
        "lon": config.longitude,
        "alt": config.altitude,
        "comment": config.comment,
        "symbol": config.symbol,
        "token": config.token,
        "raw": packet,
        "rssi": rssi
    }

    try:
        response = requests.post(config.url + '/' + config.token, json=json_data)
        response.close()
        stamp = datetime.now()
        print(f"{stamp}: [{config.call}] AprsRestSend: {packet}")
        await asyncio.sleep(0)
    except:
        stamp = datetime.now()
        print("{0}: [{1}] AprsRestSend: Lost Packet, unable post {2} to {3}".format(stamp, config.call, packet, config.url))
        print(f"{stamp}: [{config.call}] AprsRestSend: Restarting gateway...")
        microcontroller.reset()


async def loraRunner(loop):
    # LoRa APRS frequency
    RADIO_FREQ_MHZ = 433.775
    CS = digitalio.DigitalInOut(board.GP21)
    RESET = digitalio.DigitalInOut(board.GP20)
    spi = busio.SPI(board.GP18, MOSI=board.GP19, MISO=board.GP16)
    rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, RADIO_FREQ_MHZ, baudrate=1000000, agc=False,crc=True)

    while True:
        await asyncio.sleep(0)
        stamp = datetime.now()
        print(f"{stamp}: [{config.call}] loraRunner: Waiting for lora APRS packet ...\r", end="")
        packet = rfm9x.receive(with_header=True,timeout=10)
        if packet is not None:
            if packet[:3] == (b'<\xff\x01'):
                try:
                    rawdata = bytes(packet[3:]).decode('utf-8')
                    stamp = datetime.now()
                    print(f"\r{stamp}: [{config.call}] loraRunner: RSSI:{rfm9x.last_rssi} Data:{rawdata}")
                    loop.create_task(tcpPost(rawdata))
                    if config.enable is True:
                        loop.create_task(httpPost(rawdata,rfm9x.last_rssi))
                except:
                    print(f"{stamp}: [{config.call}] loraRunner: Lost Packet, unable to decode, skipping")
                    continue


async def main():
   loop = asyncio.get_event_loop()
   loraR = asyncio.create_task(loraRunner(loop))
   loraA = asyncio.create_task(iGateAnnounce())
   await asyncio.gather(loraR, loraA)


asyncio.run(main())
