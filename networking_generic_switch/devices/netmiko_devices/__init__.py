# Copyright 2016 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import itertools
import random
import time
import uuid

import netmiko
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import timeutils
from tooz import coordination

from networking_generic_switch import devices
from networking_generic_switch import exceptions as exc

LOG = logging.getLogger(__name__)
CONF = cfg.CONF

DLM_COORDINATOR = None


def get_coordinator():
    global DLM_COORDINATOR
    if not DLM_COORDINATOR and CONF.ngs_coordination.backend_url:
        DLM_COORDINATOR = coordination.get_coordinator(
            CONF.ngs_coordination.backend_url,
            ('ngs-' + CONF.host).encode('ascii'))
        DLM_COORDINATOR.start()
    return DLM_COORDINATOR


def _reset_coordinator():
    global DLM_COORDINATOR
    if DLM_COORDINATOR:
        DLM_COORDINATOR.stop()
    DLM_COORDINATOR = None


class NetmikoLock(object):
    """Netmiko-specific tooz lock wrapper

    If coordination backend is configured, it will attempt to grab any lock
    from a predefined set of names, with the set length as configured value.

    """

    def __init__(self, coordinator, locks_pool_size=1, locks_prefix='ngs-',
                 timeout=None):
        self.coordinator = coordinator
        self.locks_prefix = locks_prefix
        self.lock_names = ["{}{}".format(locks_prefix, i)
                           for i in range(locks_pool_size)]
        self.watch = timeutils.StopWatch(duration=timeout)
        self.locks_pool_size = locks_pool_size

    def __enter__(self):
        if self.coordinator:
            LOG.debug("Trying to acquire lock for %s", self.locks_prefix)
            self.watch.start()
            locked = False
            # NOTE(pas-ha) itertools.cycle essentialy keeps 2 copies of the
            # provided iterable, but the number of allowed connections is
            # usually small (~10) so memory penalty should be negligible
            for name in itertools.cycle(self.lock_names):
                lock = self.coordinator.get_lock(name)
                try:
                    locked = lock.acquire(blocking=False)
                except coordination.LockAcquireFailed:
                    locked = False
                if locked or self.watch.expired():
                    break
                else:
                    time.sleep(random.random())
                    LOG.debug("Failed to acquire lock %s", name)
            if not locked:
                msg = ("Failed to acquire any of %s locks for %s"
                       "for a netmiko action in %s seconds" % (
                           self.locks_pool_size, self.locks_prefix,
                           self.watch.elapsed))
                LOG.error(msg)
                raise coordination.LockAcquireFailed(msg)
            self.watch.stop()
            LOG.debug("Acquired lock %s", name)
            self.lock = lock
        else:
            self.lock = False
            return self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.coordinator and self.lock:
            self.lock.release()


class NetmikoSwitch(devices.GenericSwitchDevice):

    ADD_NETWORK = None

    DELETE_NETWORK = None

    PLUG_PORT_TO_NETWORK = None

    DELETE_PORT = None

    SAVE_CONFIGURATION = None

    def __init__(self, device_cfg):
        super(NetmikoSwitch, self).__init__(device_cfg)
        device_type = self.config.get('device_type', '')
        # use part that is after 'netmiko_'
        device_type = device_type.partition('netmiko_')[2]
        if device_type not in netmiko.platforms:
            raise exc.GenericSwitchNetmikoNotSupported(
                device_type=device_type)
        self.config['device_type'] = device_type

        self.locker = get_coordinator()
        self.max_sessions = int(self.config.pop('ngs_netmiko_max_sessions', 1))
        self.lock_name = self.config.get(
            'host', '') or self.config.get('ip', '')

    def _format_commands(self, commands, **kwargs):
        if not commands:
            return
        if not all(kwargs.values()):
            raise exc.GenericSwitchNetmikoMethodError(cmds=commands,
                                                      args=kwargs)
        try:
            cmd_set = [cmd.format(**kwargs) for cmd in commands]
        except (KeyError, TypeError):
            raise exc.GenericSwitchNetmikoMethodError(cmds=commands,
                                                      args=kwargs)
        return cmd_set

    def send_commands_to_device(self, cmd_set):
        if not cmd_set:
            LOG.debug("Nothing to execute")
            return

        with NetmikoLock(self.locker, locks_pool_size=self.max_sessions,
                         locks_prefix=self.lock_name,
                         timeout=CONF.ngs_coordination.acquire_timeout):
            try:
                with netmiko.ConnectHandler(**self.config) as net_connect:
                    net_connect.enable()
                    output = net_connect.send_config_set(
                        config_commands=cmd_set)
                    # NOTE (vsaienko) always save configuration when
                    # configuration is applied successfully.
                    if self.SAVE_CONFIGURATION:
                        net_connect.send_command(self.SAVE_CONFIGURATION)
            except Exception as e:
                raise exc.GenericSwitchNetmikoConnectError(config=self.config,
                                                           error=e)

        LOG.debug(output)

    def add_network(self, segmentation_id, network_id):
        # NOTE(zhenguo): Remove dashes from uuid as on most devices 32 chars
        # is the max length of vlan name.
        network_id = uuid.UUID(network_id).hex
        self.send_commands_to_device(
            self._format_commands(self.ADD_NETWORK,
                                  segmentation_id=segmentation_id,
                                  network_id=network_id))

    def del_network(self, segmentation_id):
        self.send_commands_to_device(
            self._format_commands(self.DELETE_NETWORK,
                                  segmentation_id=segmentation_id))

    def plug_port_to_network(self, port, segmentation_id):
        self.send_commands_to_device(
            self._format_commands(self.PLUG_PORT_TO_NETWORK,
                                  port=port,
                                  segmentation_id=segmentation_id))

    def delete_port(self, port, segmentation_id):
        self.send_commands_to_device(
            self._format_commands(self.DELETE_PORT,
                                  port=port,
                                  segmentation_id=segmentation_id))
