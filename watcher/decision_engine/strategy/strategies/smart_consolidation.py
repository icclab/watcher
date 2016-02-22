# -*- encoding: utf-8 -*-
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

from watcher.decision_engine.strategy.strategies import base

from copy import deepcopy

LOG = log.getLogger(__name__)


class SmartStrategy(base.BaseStrategy):
    DEFAULT_NAME = 'smart'
    DEFAULT_DESCRIPTION = 'Smart Strategy'

    def __init__(self, name=DEFAULT_NAME, description=DEFAULT_DESCRIPTION,
                 osc=None):
        super(SmartStrategy, self).__init__(name, description, osc)

    def add_migration(self, migration_type, vm_uuid,
                      src_hypervisor, dst_hypervisor,
                      model):
        # TODO unmap & map VM to model environment after migration
        params = {'migration_type': migration_type,
                  'src_hypervisor': src_hypervisor,
                  'dst_hypervisor': dst_hypervisor}
        self.solution.add_action(action_type=self.MIGRATION,
                                 resource_id=vm_uuid,
                                 input_parameters=params)

    def get_prediction_model(self, model):
        return deepcopy(model)

    def get_vm_utilization(self, vm_uuid, model):
        # TODO (gaea)
        # return (cpu_util, ram_util)
        pass

    def get_hypervisor_utilization(self, hypervisor_uuid, model):
        # TODO (gaea)
        # return (cpu_util, ram_util)
        pass

    def get_hypervisor_capacity(self, hypervisor_uuid, model):
        # TODO (gaea)
        # return (cpu_capacity, ram_capacity)
        pass

    def offload_phase(self, model):
        # TODO (cima)
        pass

    def consolidation_phase(self, model):
        # TODO (cima)
        pass

    def execute(self, original_model):
        LOG.info("Executing Smart Strategy")
        model = self.get_prediction_model(original_model)

        # Offloading phase
        self.offload_phase(model)

        # Consolidation phase
        self.consolidation_phase(model)

        return self.solution
