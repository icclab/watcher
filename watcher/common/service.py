# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
##
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging
import signal
import socket

from oslo_config import cfg
from oslo_log import _options
from oslo_log import log
import oslo_messaging as messaging
from oslo_service import service
from oslo_utils import importutils

from watcher._i18n import _LE
from watcher._i18n import _LI
from watcher.common import config
from watcher.common import context
from watcher.common import rpc
from watcher.objects import base as objects_base


service_opts = [
    cfg.IntOpt('periodic_interval',
               default=60,
               help='Seconds between running periodic tasks.'),
    cfg.StrOpt('host',
               default=socket.getfqdn(),
               help='Name of this node.  This can be an opaque identifier.  '
               'It is not necessarily a hostname, FQDN, or IP address. '
               'However, the node name must be valid within '
               'an AMQP key, and if using ZeroMQ, a valid '
               'hostname, FQDN, or IP address.'),
]

cfg.CONF.register_opts(service_opts)

LOG = log.getLogger(__name__)


class RPCService(service.Service):

    def __init__(self, host, manager_module, manager_class):
        super(RPCService, self).__init__()
        self.host = host
        manager_module = importutils.try_import(manager_module)
        manager_class = getattr(manager_module, manager_class)
        self.manager = manager_class(host, manager_module.MANAGER_TOPIC)
        self.topic = self.manager.topic
        self.rpcserver = None
        self.deregister = True

    def start(self):
        super(RPCService, self).start()
        admin_context = context.RequestContext('admin', 'admin', is_admin=True)

        target = messaging.Target(topic=self.topic, server=self.host)
        endpoints = [self.manager]
        serializer = objects_base.IronicObjectSerializer()
        self.rpcserver = rpc.get_server(target, endpoints, serializer)
        self.rpcserver.start()

        self.handle_signal()
        self.manager.init_host()
        self.tg.add_dynamic_timer(
            self.manager.periodic_tasks,
            periodic_interval_max=cfg.CONF.periodic_interval,
            context=admin_context)

        LOG.info(_LI('Created RPC server for service %(service)s on host '
                     '%(host)s.'),
                 {'service': self.topic, 'host': self.host})

    def stop(self):
        try:
            self.rpcserver.stop()
            self.rpcserver.wait()
        except Exception as e:
            LOG.exception(_LE('Service error occurred when stopping the '
                              'RPC server. Error: %s'), e)
        try:
            self.manager.del_host(deregister=self.deregister)
        except Exception as e:
            LOG.exception(_LE('Service error occurred when cleaning up '
                              'the RPC manager. Error: %s'), e)

        super(RPCService, self).stop(graceful=True)
        LOG.info(_LI('Stopped RPC server for service %(service)s on host '
                     '%(host)s.'),
                 {'service': self.topic, 'host': self.host})

    def _handle_signal(self):
        LOG.info(_LI('Got signal SIGUSR1. Not deregistering on next shutdown '
                     'of service %(service)s on host %(host)s.'),
                 {'service': self.topic, 'host': self.host})
        self.deregister = False

    def handle_signal(self):
        """Add a signal handler for SIGUSR1.

        The handler ensures that the manager is not deregistered when it is
        shutdown.
        """
        signal.signal(signal.SIGUSR1, self._handle_signal)


_DEFAULT_LOG_LEVELS = ['amqp=WARN', 'amqplib=WARN', 'qpid.messaging=INFO',
                       'oslo.messaging=INFO', 'sqlalchemy=WARN',
                       'keystoneclient=INFO', 'stevedore=INFO',
                       'eventlet.wsgi.server=WARN', 'iso8601=WARN',
                       'paramiko=WARN', 'requests=WARN', 'neutronclient=WARN',
                       'glanceclient=WARN', 'watcher.openstack.common=WARN']


def prepare_service(argv=[], conf=cfg.CONF):
    log.register_options(conf)
    config.parse_args(argv)
    cfg.set_defaults(_options.log_opts,
                     default_log_levels=_DEFAULT_LOG_LEVELS)
    log.setup(conf, 'python-watcher')
    conf.log_opt_values(LOG, logging.DEBUG)
