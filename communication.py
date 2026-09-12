import serial
import struct


class ESP32Bluetooth:

    def __init__(self, port, baudrate=115200):

        self.esp = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=1
        )


   
    # Python -> ESP32
    def send_command(self, command):

        self.esp.write(command.encode("utf-8"))


   
    # Request Sensor Data
    

    def request_temperature(self):

        self.send_command("T")

        data = self.esp.read(4)

        if len(data) == 4:
            return struct.unpack("<i", data)[0]

        return None


    def request_gas(self):

        self.send_command("G")

        data = self.esp.read(1)

        if len(data) == 1:
            return struct.unpack("<?", data)[0]

        return None


    def request_baby_awake(self):

        self.send_command("B")

        data = self.esp.read(1)

        if len(data) == 1:
            return struct.unpack("<?", data)[0]

        return None


    def request_all_sensors(self):

        self.send_command("A")

        data = self.esp.read(6)

        if len(data) == 6:

            temp, gas, baby_awake = struct.unpack(
                "<i??",
                data
            )

            return {
                "temperature": temp,
                "gas": gas,
                "baby_awake": baby_awake
            }

        return None


    
    # Python -> ESP32
    # Cry Commands

    def send_cry_detected(self):

        self.send_command("CRY_DETECTED\n")


    def send_cry_ended(self):

        self.send_command("CRY_ENDED\n")


   
    # ESP32 -> Python
    # Alerts


    def read_message(self):

        if self.esp.in_waiting > 0:

            message = self.esp.readline()

            if message:

                return message.decode(
                    "utf-8",
                    errors="ignore"
                ).strip()

        return None


    # ==================================
    # Close Bluetooth
    # ==================================

    def close(self):

        if self.esp.is_open:
            self.esp.close()