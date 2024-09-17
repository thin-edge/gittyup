#!/usr/bin/env python3

import json
import os
import time
import logging
import tomllib
import sys
from pathlib import Path
from typing import Optional
import git
from git.exc import GitCommandError
import paho.mqtt.client as mqtt

CLONE_DIR = "repo"
CHECK_INTERVAL = 15

class GittyUpClient:
    """GittyUp client

    The GittyUp client is used to communicate with thin-edge via MQTT
    """

    def __init__(self):
        self.client = None
        self.device_id = "main"
        self.root = "te/device/main//"
        self.sub_topic = f"{self.root}/cmd/device_profile/+"

    def connect(self):
        """Connect to the thin-edge.io MQTT broker"""
        if self.client is not None:
            logger.info(f"MQTT client already exists. connected={self.client.is_connected()}")
            return

        # Don't use a clean session so no messages will go missing
        client = mqtt.Client(client_id=self.device_id, clean_session=False)
        client.reconnect_delay_set(10, 120)

        client.on_connect = self.on_connect
        client.on_disconnect = self.on_disconnect
        client.on_message = self.on_message
        client.on_subscribe = self.on_subscribe

        logger.debug(f"Trying to connect to the MQTT broker: host=localhost:1883")

        client.will_set(
            "te/device/main/service/gittyup/status/health",
            json.dumps({"status": "down"}),
            qos=1,
            retain=True,
        )

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
        logger.debug(f"subscribed to topic {self.sub_topic}")

    def loop_forever(self):
        """Block infinitely"""
        self.client.loop_forever()

    def publish_tedge_command(self, topic, payload):
        """Create tedge command"""

        self.client.publish(topic=topic, payload=payload, retain=True, qos=1)

    def on_connect(self, client, userdata, flags, reason_code):
        if reason_code != 0:
            logger.error(
                f"Failed to connect. result_code={reason_code}. Retrying the connection"
            )
        else:
            logger.info(f"Connected to MQTT broker! result_code={reason_code}")
            client.publish(
                "te/device/main/service/gittyup/status/health",
                json.dumps({"status": "up"}),
                retain=True,
                qos=1,
            )
            self.subscribe()

    def on_disconnect(self, client, userdata, reason_code):
        logger.info(f"Client was disconnected: result_code={reason_code}")

    def on_message(self, client, userdata, message):
        payload_dict = json.loads(message.payload)

        if payload_dict["status"] == "successful":
            self.publish_tedge_command(message.topic, "")

    def on_subscribe(self, client, userdata, mid, granted_qos):
        for sub_result in granted_qos:
            if sub_result == 0x80:
                # error processing
                logger.error(
                    f"Could not subscribe to {self.sub_topic}. result_code={granted_qos}"
                )


def read_repo_url_from_toml(config_file: str) -> str:
    """Reads the repository URL from a TOML configuration file."""
    # TODO: properly serialise the config
    file = open(config_file, "rb")
    config_data = tomllib.load(file)
    url = config_data.get("repository", {}).get("url")
    if url:
        return url
    else:
        raise ValueError("Repository URL not found in the TOML file.")


def clone_or_pull_repo(repo_url, clone_dir="repo") -> Optional[str]:
    """
    Pulls the new information from the remote repository to the local repository, if there is any.
    If local repository does not exist, it is cloned.

    Parameters:

    - repo_url: The URL of the remote Git repository.
    - clone_dir: The directory where the repository should be cloned or pulled.
    - check_interval: Time in seconds between pull checks.

    Returns:
    - Optional[str]: If local HEAD got updated or repo was cloned, return SHA of the commit HEAD now
    points to, None otherwise.
    """
    if os.path.exists(clone_dir):
        # If the repository exists, try to pull the latest changes
        logger.debug(f"Pulling the latest changes in '{clone_dir}'...")

        repo = git.Repo(clone_dir)
        origin = repo.remotes.origin
        prev_commit = repo.head.commit

        try:
            fetch_info = origin.pull()[0]

        except GitCommandError as e:
            logger.error(f"Error during git pull: {e}")

        if fetch_info.commit.hexsha != prev_commit.hexsha:
            logger.info("Repository updated with new changes.")
            return fetch_info.commit.hexsha

        logger.info("No new changes found. Repository is already up to date.")
        return None
    else:
        # If the repository doesn't exist, clone it
        logger.debug(f"Cloning the repository '{repo_url}' into '{clone_dir}'...")

        try:
            repo = git.Repo.clone_from(repo_url, clone_dir)
        except GitCommandError as e:
            logger.error(f"Error during git clone: {e}")

        logger.info(f"Repository cloned into '{clone_dir}'.")

        return repo.head.commit.hexsha


if __name__ == "__main__":
    logger = logging.getLogger(__name__)

    repo_url = read_repo_url_from_toml("config.toml")
    client = GittyUpClient()
    try:
        client.connect()
        # Wait for connection
        time.sleep(1)

        # regularly poll remote repository until there are new commits to pull
        while True:
            commit = clone_or_pull_repo(repo_url, CLONE_DIR)
            if commit:
                profile = Path(CLONE_DIR) / "profile.json"
                if profile.exists():
                    payload = json.loads(profile.read_text(encoding="utf-8"))
                    payload["commit"] = commit
                    cmd_id = f"gittyup-{int(time.time())}"
                    client.publish_tedge_command(
                        f"te/device/main///cmd/device_profile/{cmd_id}",
                        json.dumps(payload),
                    )

            # Wait for the specified interval before checking again
            logger.info(f"Waiting for {CHECK_INTERVAL} seconds before the next pull check...")
            time.sleep(CHECK_INTERVAL)
    except ConnectionRefusedError:
        logger.error("MQTT broker is not ready yet")
    except KeyboardInterrupt:
        logger.info("Exiting...")
        if client:
            client.shutdown()
        sys.exit(0)
    except Exception as ex:
        logger.error("Unexpected error. %s", ex)
