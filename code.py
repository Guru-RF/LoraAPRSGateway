import board
import busio
import digitalio
import time
import adafruit_rfm9x
import adafruit_requests as requests
import adafruit_wiznet5k.adafruit_wiznet5k_socket as socket
from adafruit_wiznet5k.adafruit_wiznet5k import WIZNET5K
import config
import microcontroller
import asyncio

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

print("RF.Guru Minimalistic LoraAPRSGateway")

print("Chip Version:", eth.chip)
print("MAC Address:", [hex(i) for i in eth.mac_address])
print("My IP address is:", eth.pretty_ip(eth.ip_address))
print("")

# Initialize a requests object with a socket and ethernet interface
requests.set_socket(socket, eth)

async def udpPost(packet):
    HOST = "srvr.aprs-is.net"
    PORT = 8080
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(10)
    print(f"Connecting to {HOST}:{PORT}")
    s.connect((HOST, PORT))
    rawpacket = f'user {config.call} pass {config.passcode} vers "RF.Guru APRSGateway v0.1" \n'
    s.send(bytes(rawpacket, 'utf-8'))
    rawpacket = f'{packet}\n'
    s.send(bytes(rawpacket, 'utf-8'))
    s.close()

async def httpPost(packet,rssi):
    json_data = {
        "call": config.call,
        "lat": config.lat,
        "lon": config.lon,
        "alt": config.alt,
        "comment": config.comment,
        "symbol": config.symbol,
        "token": config.token,
        "raw": packet,
        "rssi": rssi
    }

    try:
        response = requests.post(config.url + '/' + config.token, json=json_data)
        response.close()
        print("Posted packet {0} to {1}".format(packet,config.url))
    except:
        print("Lost Packet, unable post {0} to {1}".format(packet, config.url))
        print("Restarting gateway...")
        microcontroller.reset()


async def loraRunner(loop):
    # LoRa APRS frequency
    RADIO_FREQ_MHZ = 433.775
    CS = digitalio.DigitalInOut(board.GP21)
    RESET = digitalio.DigitalInOut(board.GP20)
    spi = busio.SPI(board.GP18, MOSI=board.GP19, MISO=board.GP16)
    rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, RADIO_FREQ_MHZ, baudrate=1000000, agc=False,crc=True)

    print("Waiting for first packet ...")
    while True:
        packet = rfm9x.receive(with_header=True,timeout=60)
        if packet is not None:
            if packet[:3] == (b'<\xff\x01'):
                print("Received (RSSI): {0} (raw data): {1}".format(rfm9x.last_rssi, packet[3:]))
                try:
                    rawdata = bytes(packet[3:]).decode('utf-8')
                    #loop.create_task(httpPost(rawdata,rfm9x.last_rssi))
                    loop.create_task(udpPost(rawdata))
                    await asyncio.sleep(0)
                except:
                    print("Lost Packet, unable to decode, skipping")
                    continue


async def main():
   loop = asyncio.get_event_loop()
   loraR = asyncio.create_task(loraRunner(loop))
   await asyncio.gather(loraR)


asyncio.run(main())
