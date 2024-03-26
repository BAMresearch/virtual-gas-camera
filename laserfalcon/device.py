
import serial
from time import sleep 
from logging import getLogger

logger = getLogger(__name__)

#TODO: handle transmission errors with retry, more docstrings

class Device:
    """Class for representing a Laser Falcon methane measurement device."""

    def __init__(self, connection: serial.Serial = None) -> None:
        if connection is None:
            connection = serial.Serial('/dev/ttyUSB0', baudrate=19200, timeout=3)
        self._connection = connection
    
    def send_command(self, command: bytes) -> bytes:
        """Send a command, receive response, and check it, including checksum."""
        ACKNOWLEDGE = b'\x06'
        NOT_ACKNOWLEDGE = b'\x15'
        ENDOFTEXT = b'\x03'
        STARTOFTEXT = b'\x02'

        logger.debug(f'sending command: {command}')
        sum_calc_out = 0
        for curr_byte in  command: 
            sum_calc_out ^= curr_byte # xor the bytes
        sum_calc_out ^= ENDOFTEXT[0] # add "end of text" byte to checksum
        
        self._connection.write(STARTOFTEXT)
        self._connection.write(command)
        self._connection.write(ENDOFTEXT)
        self._connection.write(sum_calc_out.to_bytes(1,"big")) # convert int to single byte)
        self._connection.flush() # make sure all data is out before we continue

        ack_nack = self._connection.read() # either ack or nack
        if ack_nack != ACKNOWLEDGE:
            raise RuntimeError(f"No achknowledge received after sending command to device. Returned values was: {ack_nack}")
        
        response = self._connection.read_until(ENDOFTEXT)
        logger.debug(f'got response: {response}')
        checksum = self._connection.read()
        logger.debug(f'got checksum: {checksum}')
        
        # check response including checksum
        first_byte = response[0:1]
        if first_byte != STARTOFTEXT:
            raise RuntimeError(f"No start of text (STX 0x02) at beginning of response. Response was: {first_byte}")
        sum_calc = 0
        for curr_byte in  response[1:]: # STX / 0x02 (first byte) is not part of checksum
            sum_calc ^= curr_byte # xor the bytes
        sum_calc = sum_calc.to_bytes(1,"big") # convert int to single byte

        if sum_calc != checksum:
            self._connection.write(NOT_ACKNOWLEDGE)
            raise RuntimeError(f"Checksum mismatch in response: calculated: {sum_calc}, expected: {checksum}")        
        self._connection.write(ACKNOWLEDGE)
        self._connection.flush() # make sure all data is out before we continue
        sleep(0.01) # give device some time to process ACK before next command

        return response[1:-1] # don't include bytes for start of text, end of text, return only data string

    def get_version(self) -> str:
        """Returns the version string as reported by the device."""
        CMD_GETVER = b'ETC:VER ?;' # bytes
        RESP_START = "ETC:VER "# string
        RESP_END = ";" # string

        response = self.send_command(CMD_GETVER)
        response = response.decode()
        start_index = response.find(RESP_START)
        end_index = response.find(RESP_END, start_index + len(RESP_START))
        version = response[start_index + len(RESP_START):end_index]
        return version

    def get_settings(self) -> dict:
        """Returns the device settings as a dictonary of returned key/value pairs. Values are strings."""
        GET_SETTINGS = b'CMN:ALL ?;' # bytes
        RESP_START = "CMN:"# string
        RESP_END = ";" # string

        response = self.send_command(GET_SETTINGS)
        response = response.decode()
        start_index = response.find(RESP_START)
        # check response ends with correct end
        if response[-1] != RESP_END:
            raise RuntimeError(f"configuration response does not end with {RESP_END}")
        settings_string = response[start_index + len(RESP_START):-1]
        settings_pairs = settings_string.split(';')
        # Split each substring by space and create key-value pairs
        key_value_pairs = [substring.split(' ', 1) for substring in settings_pairs]
        # Create a dictionary from the key-value pairs
        settings_dict = {key.strip(): value.strip() for key, value in key_value_pairs}

        return settings_dict

    def get_measurement(self) -> dict:
        """
        Returns a dict containing the data of a single measurement sample consisting of 5 sub-samples.
        The results can be acessed with the following keys 'error': reported error, 1 for none, 'main_value': averaged total/main result,
        'sub_values': list of 5 dicts with the individual measurements. each consists of the keys 'value', '1f', '2f', 'time'.

        """
        GET_MEASUREMENT = b'ETC:FWD ?;'
        RESP_START = "ETC:FWD "# string
        RESP_END = ";" # string

        response = self.send_command(GET_MEASUREMENT)
        response = response.decode()
        start_index = response.find(RESP_START)
        # check response ends with correct end
        if response[-1] != RESP_END:
            raise RuntimeError(f"measurement data does not end with {RESP_END}")
        measurements_string = response[start_index + len(RESP_START):-1]
        values = measurements_string.split(";")

        # assemble result dictionary
        results = {}

        results["error"] = int(values[0])
        results["main_value"] = int(values[1])
        results["sub_values"] = []
        SUBVALUES_START = 2
        SUBVALUES_ELEMENTS = 4

        for subvalue_nr in range(5): # assemble all 5 subvalues
            subvalue_dict = {}
            THIS_SUBVALUE_START = SUBVALUES_START + (SUBVALUES_ELEMENTS * subvalue_nr)
            subvalue_dict["value"] = int(values[THIS_SUBVALUE_START])
            subvalue_dict["1f"]    = float(values[THIS_SUBVALUE_START+1])
            subvalue_dict["2f"]    = float(values[THIS_SUBVALUE_START+2])
            subvalue_dict["time"]  = int(values[THIS_SUBVALUE_START+3])
            results["sub_values"].append(subvalue_dict)

        return results
    





 