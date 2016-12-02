# -*- coding: utf-8 -*-
"""
auto-loaded via _load_modules_from in deployment.py
"""
import os
import os.path
import sys
import re
import time
import math
import shutil
from nixops.backends import MachineDefinition, MachineState
from nixops.nix_expr import Function, Call, RawValue
import nixops.util
import nixops.known_hosts
from xml import etree
import datetime
import digitalocean

SSH_KEY = """ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAtq8LpgrnFQWpIcK5YdrQNzu22sPrbkHKD83g8v/s7Nu3Omb7h5TLBOZ6DYPSorGMKGjDFqo0witXRagWq95HaA9epFXmhJlO3NTxyTAzIZSzql+oJkqszNpmYY09L00EIplE/YKXPlY2a+sGx3CdJxbglGfTcqf0J2DW4wO2ikZSOXRiLEbztyDwc+TNwYJ3WtzTFWhG/9hbbHGZtpwQl6X5l5d2Mhl2tlKJ/zQYWV1CVXLSyKhkb4cQPkL05enguCQgijuI/WsUE6pqdl4ypziXGjlHAfH+zO06s6EDMQYr50xgYRuCBicF86GF8/fOuDJS5CJ8/FWr16fiWLa2Aw== tom@leto"""

class DigitalOceanDefinition(MachineDefinition):
    @classmethod
    def get_type(cls):
        return "digital-ocean"

    def __init__(self, xml, config):
        MachineDefinition.__init__(self, xml, config)
        self.auth_token = config["digital-ocean"]["authToken"]
        self.region = config["digital-ocean"]["region"]
        self.size = config["digital-ocean"]["size"]
        self.key_name = config["digital-ocean"]["keyName"]

    def show_type(self):
        return "{0} [{1}]".format(self.get_type(), self.region)


class DigitalOceanState(MachineState):
    @classmethod
    def get_type(cls):
        return "digital-ocean"

    state = nixops.util.attr_property("state", MachineState.MISSING, int)  # override
    public_ipv4 = nixops.util.attr_property("publicIpv4", None)
    public_dns_name = nixops.util.attr_property("publicDnsName", None)
    region = nixops.util.attr_property("digital-ocean.region", None)
    size = nixops.util.attr_property("digital-ocean.size", None)
    key_name = nixops.util.attr_property("digital-ocean.keyName", None)
    auth_token = nixops.util.attr_property("digital-ocean.authToken", None)
    droplet_id = nixops.util.attr_property("digital-ocean.dropletId", None)

    def __init__(self, depl, name, id):
        MachineState.__init__(self, depl, name, id)

    def get_ssh_name(self):
        print "SSH name",self.public_ipv4
        return self.public_ipv4

    def get_ssh_flags(self, *args, **kwargs):
        super_flags = super(DigitalOceanState, self).get_ssh_flags(*args, **kwargs)
        return super_flags + ['-o', 'UserKnownHostsFile=/dev/null', '-o', 'StrictHostKeyChecking=no']

    def get_ssh_private_key_file(self):
        return open('/home/tom/.ssh/id_rsa').read()

    def create_after(self, resources, defn):
        return set()

    def destroy(self, wipe=False):
        droplet = digitalocean.Droplet(id=self.droplet_id)
        droplet.destroy()

    def create(self, defn, check, allow_reboot, allow_recreate):
        """Create or update the resource defined by ‘defn’."""
        self.manager = digitalocean.Manager(token=defn.auth_token)
        droplet = digitalocean.Droplet(
            token=defn.auth_token,
            name='Example',
            region=defn.region,
            ssh_keys=[SSH_KEY],
            image='ubuntu-14-04-x64', # only for lustration
            size_slug=defn.size,
        )
        droplet.create()

        status = 'in-progress'
        while status == 'in-progress':
            actions = droplet.get_actions()
            for action in actions:
                action.load()
                if action.status != 'in-progress':
                    status = action.status
            time.sleep(1)
        if status != 'completed':
            raise Exception("unexptected status: {}".format(status))

        droplet.load()
        self.droplet_id = droplet.id
        self.public_ipv4 = droplet.ip_address
        print "PUBLIC", self.public_ipv4

        self.wait_for_ssh()
        self.run_command('curl https://raw.githubusercontent.com/elitak/nixos-infect/master/nixos-infect | bash 2>&1')

        self.reboot_sync()
