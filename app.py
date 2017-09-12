#!/usr/bin/env python

from abc import ABC, abstractmethod
import argparse
import docker
import time
import signal
import sys
try:
    import blinkt
    BLINKT = True
except RuntimeError:
    BLINKT = False
    print("Blinkt! is not plugged in...")

class BlinktHelper:
    colors = {
        "initialize"    : {"r": 0, "g": 0, "b": 255, "brightness": 0.6},
        "updating"      : {"r": 0, "g": 0, "b": 255, "brightness": 0.6},
        # Show green lights when the following status occurs
        "completed"     : {"r": 0, "g": 255, "b": 0, "brightness": 0.2},
        "running"       : {"r": 0, "g": 255, "b": 0, "brightness": 0.2},
        "ready"         : {"r": 0, "g": 255, "b": 0, "brightness": 0.2},
        # Show orange lights when the following status occurs
        "disconnected"  : {"r": 255, "g": 0, "b": 0, "brightness": 0.8},
        "paused"        : {"r": 255, "g": 136, "b": 0, "brightness": 0.4},
        "warning"       : {"r": 255, "g": 136, "b": 0, "brightness": 0.4},
        # Show red lights when the following status occurs
        "down"          : {"r": 255, "g": 0, "b": 0, "brightness": 0.8},
        "exited"        : {"r": 255, "g": 0, "b": 0, "brightness": 0.8},
        "stopped"       : {"r": 255, "g": 0, "b": 0, "brightness": 0.8},
    }

    @staticmethod
    def reset_lights():
        if BLINKT:
            blinkt.set_all(0, 0, 0, 0)
            blinkt.show()

    @staticmethod
    def set_light(position, status):
        if BLINKT:
            blinkt.set_pixel(position % blinkt.NUM_PIXELS, 
                BlinktHelper.colors[status]["r"],
                BlinktHelper.colors[status]["g"],
                BlinktHelper.colors[status]["b"],
                brightness=BlinktHelper.colors[status]["brightness"])
            blinkt.show()

    @staticmethod
    def set_all(status):
        if BLINKT:
            blinkt.set_all(BlinktHelper.colors[status]["r"],
                BlinktHelper.colors[status]["g"],
                BlinktHelper.colors[status]["b"],
                brightness=BlinktHelper.colors[status]["brightness"])
            blinkt.show()

class DockerHelper(ABC):
    def __init__(self, client=docker.from_env()):
        self.client = client
        self.states = []

    def monitor(self):
        items = self.get_items()
        position = 0

        BlinktHelper.reset_lights()

        for item in items:
            status = self.get_status(item)
            self.states.append(status)
            BlinktHelper.set_light(position, status["status"])
            position += 1

        return self.states

    @abstractmethod
    def get_items(self):
        pass

    @abstractmethod
    def get_status(self, item):
        pass

class ContainerHelper(DockerHelper):
    def __init__(self, client):
        DockerHelper.__init__(self, client)

    def get_items(self):
        try:
            return self.client.containers.list(all=True)
        except:
            return []

    def get_status(self, item):
        return {"name": item.name, "status": item.status}

class NodeHelper(DockerHelper):
    def __init__(self, client):
        DockerHelper.__init__(self, client)

    def get_items(self):
        return self.client.nodes.list()

    def get_status(self, item):
        return {"name": item.id, "status": item.attrs["Status"]["State"]}


class ServiceHelper(DockerHelper):
    def __init__(self, client):
        DockerHelper.__init__(self, client)

    def get_items(self):
        return self.client.services.list()

    def get_status(self, item):
        replicas = item.attrs["Spec"]["Mode"]["Replicated"]["Replicas"]
        tasks = item.tasks()
        nbTasks = 0
        for task in tasks:
            if task["Status"]["State"] != 'running':
                continue
            nbTasks += 1
        status = "running" if nbTasks == replicas else "warning"

        return {"name": item.name, "status":status}

class HealthManager:
    def __init__(self, client=docker.from_env(), default_module="containers"):
        self.modules = {
            "containers"    : ContainerHelper(client),
            "nodes"         : NodeHelper(client),
            "services"      : ServiceHelper(client)
        }

        self.default_module = default_module

    def monitor(self, module=None, delay=None):
        module = self.default_module if not module else module
        helper = self.modules[module]

        print(helper.monitor())


def main():
    # React on signal
    signal.signal(signal.SIGINT, terminate)
    signal.signal(signal.SIGTERM, terminate)

    # Define and parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--monitor", "-m", type=str, help="Monitor filter", choices=["services", "nodes", "containers"], default="containers")
    parser.add_argument("--delay", "-d", type=int, help="Healthcheck delay (seconds)", default=10)
    args = parser.parse_args()

    # Initialization : display blue leds
    BlinktHelper.set_all("initialize")
    time.sleep(5)

    # Monitor loop
    while 1:
        watcher = HealthManager()
        watcher.monitor(module=args.monitor, delay=args.delay)
        time.sleep(args.delay)
        del watcher

def terminate(signal, frame):
    # Turn-off leds
    BlinktHelper.reset_lights()
    print( "Shutting down monitor..." )
    sys.exit(0)

if __name__ == "__main__":
    main()