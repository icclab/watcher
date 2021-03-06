# -*- encoding: utf-8 -*-
# Copyright (c) 2015 b<>com
#
# Authors: Jean-Emile DARTOIS <jean-emile.dartois@b-com.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from oslo_log import log
import six
import voluptuous

from watcher._i18n import _
from watcher.applier.actions import base
from watcher.common import exception
from watcher.common import nova_helper
from watcher.common import utils

LOG = log.getLogger(__name__)


class Migrate(base.BaseAction):

    # input parameters constants
    MIGRATION_TYPE = 'migration_type'
    LIVE_MIGRATION = 'live'
    DST_HYPERVISOR = 'dst_hypervisor'
    SRC_HYPERVISOR = 'src_hypervisor'

    def check_resource_id(self, value):
        if (value is not None and
                len(value) > 0 and not
                utils.is_uuid_like(value)):
            raise voluptuous.Invalid(_("The parameter"
                                       " resource_id is invalid."))

    @property
    def schema(self):
        return voluptuous.Schema({
            voluptuous.Required(self.RESOURCE_ID): self.check_resource_id,
            voluptuous.Required(self.MIGRATION_TYPE,
                                default=self.LIVE_MIGRATION):
                                    voluptuous.Any(*[self.LIVE_MIGRATION]),
            voluptuous.Required(self.DST_HYPERVISOR):
                voluptuous.All(voluptuous.Any(*six.string_types),
                               voluptuous.Length(min=1)),
            voluptuous.Required(self.SRC_HYPERVISOR):
                voluptuous.All(voluptuous.Any(*six.string_types),
                               voluptuous.Length(min=1)),
        })

    @property
    def instance_uuid(self):
        return self.resource_id

    @property
    def migration_type(self):
        return self.input_parameters.get(self.MIGRATION_TYPE)

    @property
    def dst_hypervisor(self):
        return self.input_parameters.get(self.DST_HYPERVISOR)

    @property
    def src_hypervisor(self):
        return self.input_parameters.get(self.SRC_HYPERVISOR)

    def migrate(self, destination):
        nova = nova_helper.NovaHelper(osc=self.osc)
        LOG.debug("Migrate instance %s to %s", self.instance_uuid,
                  destination)
        instance = nova.find_instance(self.instance_uuid)
        if instance:
            if self.migration_type == 'live':
                return nova.live_migrate_instance(
                    instance_id=self.instance_uuid, dest_hostname=destination)
            else:
                raise exception.Invalid(
                    message=(_('Migration of type %(migration_type)s is not '
                               'supported.') %
                             {'migration_type': self.migration_type}))
        else:
            raise exception.InstanceNotFound(name=self.instance_uuid)

    def execute(self):
        return self.migrate(destination=self.dst_hypervisor)

    def revert(self):
        return self.migrate(destination=self.src_hypervisor)

    def precondition(self):
        # todo(jed) check if the instance exist/ check if the instance is on
        # the src_hypervisor
        pass

    def postcondition(self):
        # todo(jed) we can image to check extra parameters (nework reponse,ect)
        pass
