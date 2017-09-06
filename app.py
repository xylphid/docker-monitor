#!/usr/bin/env python

from abc import ABC, abstractmethod
import argparse
import docker
try:
	import blinkt
	BLINKT = True
except RuntimeError:
	BLINKT = False
	print("Blinkt! is not plugged in...")

class DockerHelper(ABC):
	def __init__(self, client=docker.from_env()):
		self.client = client
		self.colors = {
			"running": {"r": 0, "g": 255, "b": 0, "brightness": 0.8},
			"warning": {"r": 255, "g": 136, "b": 0, "brightness": 0.4},
			"stopped": {"r": 255, "g": 0, "b": 0, "brightness": 1},
		}
		self.states = []
		
		if BLINKT:
			blinkt.set_clear_on_exit(False)
			blinkt.set_all(0, 0, 255, brightness=1)
			print(blinkt.NUM_PIXELS)

	def monitor(self):
		items = self.get_items()
		position = 0
		for item in items:
			status = self.get_status(item)
			self.states.append(status)
			self.set_light(position, status["status"])
			position += 1

		return self.states

	def set_light(self, position, status):
		if BLINKT:
			blinkt.set_pixel(position % blinkt.NUM_PIXELS, 
				self.colors[status]["r"],
				self.colors[status]["g"],
				self.colors[status]["b"],
				brightness=self.colors[status]["brightness"])
			blinkt.show()

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
		return self.client.containers.list()

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
			"containers"	: ContainerHelper(client),
			"nodes"			: NodeHelper(client),
			"services"		: ServiceHelper(client)
		}

		self.default_module = default_module

	def monitor(self, module=None, delay=None):
		module = self.default_module if not module else module
		helper = self.modules[module]

		print(helper.monitor())


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--monitor", "-m", type=str, help="Monitor filter", choices=["services", "nodes", "containers"], default="containers")
	parser.add_argument("--delay", "-d", help="Healthcheck delay (seconds)", default=10)
	args = parser.parse_args()
	print(args)

	watcher = HealthManager()
	watcher.monitor(module=args.monitor, delay=args.delay)

if __name__ == "__main__":
    main()