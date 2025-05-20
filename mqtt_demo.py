import paho.mqtt.client as mqtt
import json
from datetime import datetime

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    # Subscribe to all video analytics topics
    client.subscribe("video_analytics/#")

def on_message(client, userdata, msg):
    try:
        # Try to parse JSON messages
        payload = json.loads(msg.payload.decode())
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{timestamp}] Topic: {msg.topic}")
        print(f"Message: {json.dumps(payload, indent=2)}")
    except json.JSONDecodeError:
        # If not JSON, print raw message
        print(f"\n[{timestamp}] Topic: {msg.topic}")
        print(f"Message: {msg.payload.decode()}")

def main():
    # Create MQTT client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    # Connect to broker
    print("Connecting to MQTT broker...")
    client.connect("localhost", 1883, 60)

    # Start the loop
    print("Listening for messages...")
    client.loop_forever()

if __name__ == "__main__":
    main() 