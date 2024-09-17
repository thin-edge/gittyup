import json
import sys
import paho.mqtt.client as mqtt

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
        client = mqtt.Client(client_id=self.device_id, clean_session=False)
        client.reconnect_delay_set(10, 120)

        client.on_connect = self.on_connect
        client.on_disconnect = self.on_disconnect
        client.on_message = self.on_message
        client.on_subscribe = self.on_subscribe

        print(f"Trying to connect to the MQTT broker: host=localhost:1883")
            
        client.connect("localhost", 1883)
        client.loop_start()

        self.client = client

    def shutdown(self):
        """Shutdown client including any workers in progress"""
        if self.client and self.client.is_connected():
            self.client.disconnect()
            self.client.loop_stop()

    def subscribe(self):
        """Subscribe to thin-edge.io device profile topic."""
        self.client.subscribe(self.sub_topic)
        print(f"subscribed to topic {self.sub_topic}")

    def loop_forever(self):
         """Block infinitely"""
         self.client.loop_forever()

    def publish_tedge_command(self, topic, payload):
        """ Create tedge command"""

        self.client.publish(topic=topic, payload=payload, retain=True, qos=1)

    def on_connect(self, client, userdata, flags, reason_code):
            if reason_code.is_failure:
                print(f"Failed to connect. result_code={reason_code}. Retrying the connection")
            else:
                print(f"Connected to MQTT broker! result_code={reason_code}")
                self.subscribe()

    def on_disconnect(self, client, userdata, mid, reason_code):
        print(f"Client was disconnected: result_code={reason_code}")

    def on_message(self, client, userdata, message):
        payload_dict = json.loads(message.payload)

        if payload_dict['status'] == "successful":
            self.publish_tedge_command(message.topic, '')
            
    def on_subscribe(self, client, userdata, mid, granted_qos):
        for sub_result in granted_qos:
            if sub_result == 0x80:
                # error processing
                print(f"Could not subscribe to {self.sub_topic}. result_code={granted_qos}")

if __name__ == '__main__':
    client = GittyUpClient()

    try:
        client.connect()
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
