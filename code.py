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

# Fixed IP
#IP_ADDRESS = (172, 16, 132, 4)
#SUBNET_MASK = (255, 255, 255, 0)
#GATEWAY_ADDRESS = (172, 16, 132, 1)
#DNS_SERVER = (172, 16, 132, 1)

ethernetRst = digitalio.DigitalInOut(W5x00_RSTn)
ethernetRst.direction = digitalio.Direction.OUTPUT

cs = digitalio.DigitalInOut(SPI0_CSn)
spi_bus = busio.SPI(SPI0_SCK, MOSI=SPI0_TX, MISO=SPI0_RX)

# Reset W5500 first
ethernetRst.value = False
time.sleep(1)
ethernetRst.value = True

# Initialize ethernet interface with DHCP
eth = WIZNET5K(spi_bus, cs, is_dhcp=True, mac=MY_MAC, hostname='aprsgate', debug=False)
# Fixed IP
#eth = WIZNET5K(spi_bus, cs, is_dhcp=False, mac=MY_MAC)
#eth.ifconfig = (IP_ADDRESS, SUBNET_MASK, GATEWAY_ADDRESS, DNS_SERVER)

print("RF.Guru Minimalistic LoraAPRSGateway")

print("Chip Version:", eth.chip)
print("MAC Address:", [hex(i) for i in eth.mac_address])
print("My IP address is:", eth.pretty_ip(eth.ip_address))

# Initialize a requests object with a socket and ethernet interface
requests.set_socket(socket, eth)

async def httpPost(packet,rssi):
    json_data = {
        "call": config.call,
        "raw": packet,
        "rssi": rssi
    }

    try:
        response = requests.post(config.url + '/' + config.token, json=json_data)
        response.close()
        print("Posted to the cloud (raw data): {0}".format(packet))
    except:
        print("Lost Packet, unable post to {}".format(config.url))
        print("Restarting gateway...")
        microcontroller.reset()


async def loraRunner():
    print("Lora Runner")
    # LoRa APRS frequency
    RADIO_FREQ_MHZ = 433.775
    CS = digitalio.DigitalInOut(board.GP21)
    RESET = digitalio.DigitalInOut(board.GP20)
    spi = busio.SPI(board.GP18, MOSI=board.GP19, MISO=board.GP16)
    rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, RADIO_FREQ_MHZ, baudrate=1000000, agc=False,crc=False)

    while True:
        packet = rfm9x.receive(with_header=True,timeout=60)
        if packet is not None:
            if packet[:3] == (b'<\xff\x01'):
                print("Received (raw data): {0}".format(packet[3:]))
                print("RSSI: {0}".format(rfm9x.last_rssi))
            try:
                rawdata = bytes(packet[3:]).decode('utf-8')
            except:
                print("Lost Packet, unable to decode, skipping")
                continue
            httpPost(rawdata,rfm9x.last_rssi)


async def main():
   loraR = asyncio.create_task(loraRunner())
   await asyncio.gather(loraR)


asyncio.run(main())
