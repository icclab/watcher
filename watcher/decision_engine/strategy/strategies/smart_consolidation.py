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

    def add_migration(self, vm, src_hypervisor,
                      dst_hypervisor, model):
        model.unmap(src_hypervisor, vm)
        model.map(dst_hypervisor, vm)
        migration_type = 'live'
        params = {'migration_type': migration_type,
                  'src_hypervisor': src_hypervisor,
                  'dst_hypervisor': dst_hypervisor}
        self.solution.add_action(action_type=self.MIGRATION,
                                 resource_id=vm.uuid,
                                 input_parameters=params)

    def get_prediction_model(self, model):
        return deepcopy(model)

    def get_vm_utilization(self, vm, model):
        # TODO (gaea)
        # return {'cpu': cpu, 'ram': ram, 'disk': disk}
        pass

    def get_hypervisor_utilization(self, hypervisor, model):
        # TODO (gaea)
        # return {'cpu': cpu, 'ram': ram, 'disk': disk}
        pass

    def get_hypervisor_capacity(self, hypervisor, model):
        # TODO (gaea)
        # return {'cpu': cpu, 'ram': ram, 'disk': disk}
        pass

    def is_overloaded(self, hypervisor, model):
        hypervisor_capacity = self.get_hypervisor_capacity(hypervisor, model)
        hypervisor_utilization = self.get_hypervisor_utilization(
            hypervisor, model)
        metrics = ['cpu']
        for m in metrics:
            if hypervisor_utilization[m] > hypervisor_capacity[m]:
                return True
        return False

    def vm_fits(self, vm, hypervisor, model):
        hypervisor_capacity = self.get_hypervisor_capacity(hypervisor, model)
        hypervisor_utilization = self.get_hypervisor_utilization(
            hypervisor, model)
        vm_utilization = self.get_vm_utilization(vm, model)
        metrics = ['cpu', 'ram', 'disk']
        for m in metrics:
            if vm_utilization[m] + \
                    hypervisor_utilization[m] > hypervisor_capacity[m]:
                return False
        return True

    def offload_phase(self, model):
        '''
        Offload phase performing first-fit based bin packing to offload
        overloaded hypervisors. This is done in a fashion of moving
        the least CPU utilized VM first as live migration these
        generaly causes less troubles.
        '''

        sorted_hypervisors = sorted(
            model.get_all_hypervisors(),
            key=lambda x: self.get_hypervisor_utilization(x, model)['cpu'])
        for hypervisor in reversed(sorted_hypervisors):
            if self.is_overloaded(hypervisor, model):
                for vm in sorted(model.get_mapping().get_node_vms_from_id(
                        hypervisor.uuid),
                        key=lambda x: self.get_vm_utilization(
                        vm, model)['cpu']):
                    for dst_hypervisor in sorted_hypervisors:
                        if self.vm_fits(vm, dst_hypervisor, model):
                            self.add_migration(vm, hypervisor,
                                               dst_hypervisor, model)
                            break
                    if not self.is_overloaded(hypervisor, model):
                        break

    def consolidation_phase(self, model):
        '''
        Consolidation phase performing first-fit based bin packing.
        First, hypervisors with the lowest cpu utilization are consolidated
        by moving their load to hypervisors with the highest cpu utilization
        which can accomodate the load. In this phase the most cpu utilizied
        VMs are prioritizied as their load is more difficult to accomodate
        in the system than less cpu utilizied VMs which can be later used
        to fill smaller CPU capacity gaps.
        '''

        sorted_hypervisors = sorted(
            model.get_all_hypervisors(),
            key=lambda x: self.get_hypervisor_utilization(x, model)['cpu'])
        asc = 0
        for hypervisor in sorted_hypervisors:
            for vm in sorted(model.get_mapping().get_node_vms_from_id(
                    hypervisor.uuid),
                    key=lambda x: self.get_vm_utilization(vm, model)['cpu'],
                    reverse=True):
                dsc = len(sorted_hypervisors) - 1
                for dst_hypervisor in reversed(sorted_hypervisors):
                    if self.vm_fits(vm, dst_hypervisor, model):
                        self.add_migration(vm, hypervisor,
                                           dst_hypervisor, model)
                    dsc -= 1
                    if asc >= dsc:
                        break
            asc += 1

    def execute(self, original_model):
        LOG.info("Executing Smart Strategy")
        model = self.get_prediction_model(original_model)

        # Offloading phase
        self.offload_phase(model)

        # Consolidation phase
        self.consolidation_phase(model)

        return self.solution
