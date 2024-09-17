import sys
import threading
from time import sleep
import paho.mqtt.client as mqtt
from subprocess import run

class GittyUpClient():
    """ GittyUp client 
    
    The GittyUp client is used to communicate with thin-edge via MQTT
    """
    def __init__(self):
        self.client = None
        self.device_id = 'main'
        self.root = 'te/device/main//'
        self.sub_topic = f'{self.root}/cmd/device_profile/+'
        
    def connect(self):
        """Connect to the thin-edge.io MQTT broker"""
        if self.client is not None:
            print(f"MQTT client already exists. connected={self.client.is_connected()}")
            return
        
        # Don't use a clean session so no messages will go missing
        client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=self.device_id, clean_session=False)
        client.reconnect_delay_set(10, 120)

        def on_connect(client, userdata, flags, reason_code, properties):
            if reason_code.is_failure:
                print(f"Failed to connect: {reason_code}. Retrying the connection")
            else:
                print(f"Connected to MQTT broker!")

        def on_disconnect(client, userdata, mid, reason_code_list, properties):
            print(f"Client was disconnected!")

        def on_subscribe(client, userdata, mid, reason_code_list, properties):
            if reason_code_list[0].is_failure:
                print(f"Could not subscribe to given topic: {reason_code_list[0]}")

        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.on_subscribe = on_subscribe

        print(f"Trying to connect to the MQTT broker: host=localhost:1883")
            
        client.connect("localhost", 1883)
        client.loop_start()

        self.client = client

    def shutdown(self):
        """Shutdown client including any workers in progress

        Args:
            worker_timeout(float): Timeout in seconds to wait for
                each worker (individually). Defaults to 10.
        """
        if self.client and self.client.is_connected():
            self.client.disconnect()
            self.client.loop_stop()

    def subscribe(self):
        """Subscribe to thin-edge.io device profile topic."""
        self.client.subscribe(self.sub_topic)
        print(f"subscribed to topic {self.sub_topic}")

    def loop_forever(self):
         self.client.loop_forever()

if __name__ == '__main__':
    client = GittyUpClient()

    try:
        client.connect()
        client.subscribe()
        client.loop_forever()
    except ConnectionRefusedError:
            print("MQTT broker is not ready yet")
    except KeyboardInterrupt:
            print("Exiting...")
            if client:
                client.shutdown()
            sys.exit(0)
    except Exception as ex:
            print("Unexpected error. %s", ex)
