import serial
from time import sleep  

# commands
get_version = b'\x02ETC:VER ?;\x03\x0E'
get_settings = b'\x02CMN:ALL ?;\x03\x1C'
get_measurement = b'\x02ETC:FWD ?;\x03\x1A'
acknowledge = b'\x06'
endoftext = b'\x03'

lf = serial.Serial('/dev/ttyUSB0', baudrate=19200, timeout=10)


lf.write(get_version)
print(lf.read()) # ack/nack
print(lf.read_until(endoftext))
print(lf.read()) #checksum
lf.write(acknowledge)
print()

lf.write(get_settings)
print(lf.read()) # ack/nack
print(lf.read_until(endoftext))
print(lf.read()) #checksum
lf.write(acknowledge)
print()

while True:
    lf.write(get_measurement)
    print(lf.read()) # ack/nack
    print(lf.read_until(endoftext))
    print(lf.read()) #checksum
    lf.write(acknowledge)
    print()

    sleep(2)
