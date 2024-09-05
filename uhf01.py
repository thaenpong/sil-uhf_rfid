import socket
from time import sleep
from datetime import datetime, timedelta
import RPi.GPIO as GPIO
import mysql.connector
from mysql.connector import Error

# Config the GPIO
GPIO.setmode(GPIO.BOARD)
GPIO.setup(7, GPIO.OUT)
GPIO.output(7, True)

# Configure the TCP connection
tcp_ip = "192.168.1.225"  # Replace with your IP address
tcp_port = 2022  # Replace with your port number
buffer_size = 1024  # Define the buffer size

rfid_machine_id = 2
gate_open_date = None
gate_warning_date = None


# Function to create and connect the socket
def create_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(20)
    sock.connect((tcp_ip, tcp_port))
    return sock


# Function to connect to MariaDB
def connect_to_mariadb():
    try:
        connection = mysql.connector.connect(
            host="127.0.0.1",
            database="rfid",
            user="tp",
            password="Sil@1234",
        )
        if connection.is_connected():
            print("Successfully connected to MariaDB")
            return connection
    except Error as e:
        print(f"Error: {e}")
        return None


# Function to select data from the rfid table
def select_from_rfid(label):
    try:
        connection = connect_to_mariadb()
        if connection is not None:
            cursor = connection.cursor(dictionary=True)
            query = "SELECT * FROM rfid WHERE label = %s"
            cursor.execute(query, (label,))
            records = cursor.fetchone()

            return records  # Return the records if they exist
    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("MariaDB connection is closed")
    return []


def select_from_logs():
    try:
        connection = connect_to_mariadb()
        if connection is not None:
            cursor = connection.cursor(dictionary=True)
            query = "SELECT * FROM rfid_log ORDER BY id DESC LIMIT 1"
            cursor.execute(query)
            record = cursor.fetchone()

            return record  # Return the record if it exists
    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("MariaDB connection is closed")
    return None  # Return None if no record is found


def insert_into_rfid_logs(rfid_machine_id, rfid_id):
    try:
        connection = connect_to_mariadb()
        if connection is not None:
            # print(rfid_machine_id, rfid_id)
            cursor = connection.cursor()
            query = "INSERT INTO rfid_log (rfidMachineId, rfidId) VALUES (%s, %s)"
            cursor.execute(query, (rfid_machine_id, rfid_id))
            connection.commit()
            print("Records inserted successfully into rfid_logs")
    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("MariaDB connection is closed")


# Main function to handle the TCP connection and data processing
def main():
    global gate_open_date  # Declare gate_open_date as global to modify it inside the loop
    while True:
        try:
            sock = create_socket()
            print(f"Connected to {tcp_ip} port {tcp_port}")
            while True:
                try:
                    binary_data = sock.recv(buffer_size)
                    start_index = 11  # Starting index of \xe2
                    length = 12  # Length of the sequence to extract
                    byte_sequence = binary_data[start_index : start_index + length]
                    hex_string = byte_sequence.hex().upper()
                    if hex_string:
                        # print(hex_string)
                        if gate_open_date is None:
                            is_exist = select_from_rfid(hex_string)
                            if is_exist:
                                print(is_exist["id"], rfid_machine_id)
                                insert_into_rfid_logs(rfid_machine_id, is_exist["id"])
                                print("Exit Card:", hex_string)
                                GPIO.output(7, False)
                                gate_open_date = (
                                    datetime.now()
                                )  # Set the gate open time
                                gate_warning_date = None
                                # sleep(10)
                                # GPIO.output(7, True)
                                # sleep(30)
                        else:
                            is_exist = select_from_rfid(hex_string)
                            latest = select_from_logs()
                            if gate_warning_date is None:
                                if datetime.now() > gate_open_date + timedelta(
                                    minutes=1.5
                                ):
                                    GPIO.output(7, True)
                                    sleep(1)
                                    GPIO.output(7, False)
                                    gate_warning_date = datetime.now()
                                    if is_exist["id"] == latest["rfidId"]:
                                        insert_into_rfid_logs(
                                            rfid_machine_id, is_exist["id"]
                                        )
                            else:
                                if (
                                    datetime.now()
                                    > gate_warning_date + timedelta(minutes=0.3)
                                ):
                                    GPIO.output(7, True)
                                    sleep(1)
                                    GPIO.output(7, False)
                                    gate_warning_date = datetime.now()
                                    if is_exist["id"] == latest["rfidId"]:
                                        insert_into_rfid_logs(
                                            rfid_machine_id, is_exist["id"]
                                        )
                except socket.timeout:
                    print("Socket timeout, retrying...")
                    if gate_open_date is not None:
                        if datetime.now() > gate_open_date + timedelta(minutes=1):
                            GPIO.output(7, True)  # Close the gate after 1 minute
                            gate_open_date = None  # Reset the gate open date
                    break
                except socket.error as e:
                    print("Socket error:", e)
                    break
        except socket.error as e:
            print("Failed to connect:", e)
            sleep(5)  # Wait before trying to reconnect
        except KeyboardInterrupt:
            print("Exiting...")
            break
        finally:
            try:
                sock.close()
            except:
                pass


if __name__ == "__main__":
    main()
