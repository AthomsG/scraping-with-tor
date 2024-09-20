from stem import Signal
from stem.control import Controller
import time
import socket
import socks
from urllib.request import urlopen

# Create a function to print useful debug information
def print_debug_info():
    print("Attempting to connect to TOR Control Port...")
    try:
        controller = Controller.from_port(port=9051)
        print("Connected to TOR Control Port")
        return controller
    except Exception as e:
        print(f"Error connecting to TOR Control Port: {e}")
        return None

def connectTor():
    socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", 9050, True)
    socket.socket = socks.socksocket

def renewTor(controller):
    try:
        controller.authenticate("abc123")  # or simply controller.authenticate() if using cookie-based
        controller.signal(Signal.NEWNYM)
        print("TOR IP renewed successfully")
    except Exception as e:
        print(f"Error renewing TOR IP: {e}")

def showIP():
    try:
        ip = urlopen('https://icanhazip.com').read().decode().strip()
        print(f"Current IP: {ip}")
    except Exception as e:
        print(f"Error retrieving IP: {e}")

controller = print_debug_info()

if controller:
    for i in range(5):
        renewTor(controller)
        connectTor()
        showIP()
        time.sleep(10)
else:
    print("Failed to connect to TOR. Please check if TOR is running and configured correctly.")