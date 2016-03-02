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

from watcher.decision_engine.model import hypervisor_state as hyper_state
from watcher.decision_engine.strategy.strategies import base
from watcher.decision_engine.model import resource
from watcher.metrics_engine.cluster_history import ceilometer \
    as ceilometer_cluster_history

from copy import deepcopy

LOG = log.getLogger(__name__)


class SmartStrategy(base.BaseStrategy):
    DEFAULT_NAME = 'smart'
    DEFAULT_DESCRIPTION = 'Smart Strategy'

    def __init__(self, name=DEFAULT_NAME, description=DEFAULT_DESCRIPTION,
                 osc=None):
        super(SmartStrategy, self).__init__(name, description, osc)
        self._ceilometer = \
            ceilometer_cluster_history.CeilometerClusterHistory(osc=self.osc)
        self.number_of_migrations = 0
        self.number_of_released_hypervisors = 0

    def add_migration(self, vm, src_hypervisor,
                      dst_hypervisor, model):
        model.unmap(src_hypervisor, vm)
        model.map(dst_hypervisor, vm)
        migration_type = 'live'
        params = {'migration_type': migration_type,
                  'src_hypervisor': src_hypervisor,
                  'dst_hypervisor': dst_hypervisor}
        self.solution.add_action(action_type='migrate',
                                 resource_id=vm.uuid,
                                 input_parameters=params)
        self.number_of_migrations += 1

    def deactivate_unused_hypervisors(self, model):
        for hypervisor in model.get_all_hypervisors().values():
            if len(model.get_mapping().get_node_vms(hypervisor)) == 0:
                params = \
                    {'state': hyper_state.HypervisorState.OFFLINE.value}
                self.solution.add_action(
                    action_type='change_nova_service_state',
                    resource_id=hypervisor.uuid,
                    input_parameters=params)
                self.number_of_released_hypervisors += 1

    def get_prediction_model(self, model):
        return deepcopy(model)

    def get_vm_utilization(self, vm_uuid, model, period=3600, aggr='avg'):
        # TODO (gaea)
        """
        Collect cpu, ram and disk utilization statistics of a virtual machine
        :param vm: vm object
        :param model:
        :param period: seconds
        :param aggr: string
        :return: dict(cpu(number of vcpus used), ram(MB used), disk(B used))
        """
        cpu_util_metric = 'cpu_util'
        ram_util_metric = 'memory.usage'
        disk_util_metric = 'disk.usage'
        vm_cpu_util = \
            self._ceilometer.statistic_aggregation(resource_id=vm_uuid,
                                                   meter_name=cpu_util_metric,
                                                   period=period,
                                                   aggregate=aggr)
        vm_cpu_cores = model.get_resource_from_id(
            resource.ResourceType.cpu_cores).get_capacity(model.get_vm_from_id(vm_uuid))
        total_cpu_utilization = vm_cpu_cores * (vm_cpu_util / 100.0)

        vm_ram_util = \
            self._ceilometer.statistic_aggregation(resource_id=vm_uuid,
                                                   meter_name=ram_util_metric,
                                                   period=period,
                                                   aggregate=aggr)

        vm_disk_util = \
            self._ceilometer.statistic_aggregation(resource_id=vm_uuid,
                                                   meter_name=disk_util_metric,
                                                   period=period,
                                                   aggregate=aggr)
        return dict(cpu=total_cpu_utilization, ram=vm_ram_util,
                    disk=vm_disk_util)

    def get_hypervisor_utilization(self, hypervisor, model, period=3600,
                                   aggr='avg'):
        # TODO (gaea)
        """
        Collect cpu, ram and disk utilization statistics of a hypervisor
        :param hypervisor: hypervisor object
        :param model:
        :param period: seconds
        :param aggr: string
        :return: dict(cpu(number of cores used), ram(MB used), disk(B used))
        """
        cpu_util_metric = 'compute.node.cpu.percent'
        ram_util_metric = 'memory.usage'
        disk_util_metric = 'disk.usage'
        resource_id = "%s_%s" % (hypervisor.uuid, hypervisor.hostname)
        hypervisor_cpu_util = \
            self._ceilometer.statistic_aggregation(resource_id=resource_id,
                                                   meter_name=cpu_util_metric,
                                                   period=period,
                                                   aggregate=aggr)
        hypervisor_cpu_cores = model.get_resource_from_id(
            resource.ResourceType.cpu_cores).get_capacity(hypervisor)
        total_cpu_utilization = hypervisor_cpu_cores * \
            (hypervisor_cpu_util / 100.0)

        hypervisor_vms = \
            model.get_mapping().get_node_vms_from_id(hypervisor.uuid)

        hypervisor_ram_util = sum(map(lambda vm_uuid:
                                      self._ceilometer.statistic_aggregation(
                                          resource_id=vm_uuid,
                                          meter_name=ram_util_metric,
                                          period=period,
                                          aggregate=aggr),
                                      hypervisor_vms))

        hypervisor_disk_util = sum(map(lambda vm_uuid:
                                       self._ceilometer.statistic_aggregation(
                                           resource_id=vm_uuid,
                                           meter_name=disk_util_metric,
                                           period=period,
                                           aggregate=aggr),
                                       hypervisor_vms))

        return dict(cpu=total_cpu_utilization, ram=hypervisor_ram_util,
                    disk=hypervisor_disk_util)

    def get_hypervisor_capacity(self, hypervisor, model):
        # TODO (gaea)
        """
        Collect cpu, ram and disk capacity of a hypervisor
        :param hypervisor: hypervisor object
        :param model:
        :return: dict(cpu(cores), ram(MB), disk(B))
        """
        hypervisor_cpu_capacity = model.get_resource_from_id(
            resource.ResourceType.cpu_cores).get_capacity(hypervisor)

        # TODO - Check output of disk capacity (MB or B)
        hypervisor_disk_capacity = model.get_resource_from_id(
            resource.ResourceType.disk).get_capacity(hypervisor)

        hypervisor_ram_capacity = model.get_resource_from_id(
            resource.ResourceType.memory).get_capacity(hypervisor)
        return dict(cpu=hypervisor_cpu_capacity, ram=hypervisor_ram_capacity,
                    disk=hypervisor_disk_capacity)

    def get_relative_hypervisor_utilization(self, hypervisor, model):
        rhu = {}
        util = self.get_hypervisor_utilization(hypervisor, model)
        cap = self.get_hypervisor_capacity(hypervisor, model)
        for k in util.keys():
            rhu[k] = util[k] / cap[k]
        return rhu

    def get_relative_cluster_utilization(self, model):
        hypervisors = model.get_all_hypervisors().values()
        rcu = {}
        counters = {}
        for hypervisor in hypervisors:
            if hypervisor.state == hyper_state.HypervisorState.ONLINE:
                rhu = self.get_relative_hypervisor_utilization(hypervisor,
                                                               model)
                for k in rhu.keys():
                    if k not in rcu:
                        rcu[k] = 0
                    if k not in counters:
                        counters[k] = 0
                    rcu[k] += rhu[k]
                    counters[k] += 1
        for k in rcu.keys():
            rcu[k] /= counters[k]
        return rcu

    def is_overloaded(self, hypervisor, model, cc):
        hypervisor_capacity = self.get_hypervisor_capacity(hypervisor, model)
        hypervisor_utilization = self.get_hypervisor_utilization(
            hypervisor, model)
        metrics = ['cpu']
        for m in metrics:
            if hypervisor_utilization[m] > hypervisor_capacity[m] * cc[m]:
                return True
        return False

    def vm_fits(self, vm_uuid, hypervisor, model, cc):
        hypervisor_capacity = self.get_hypervisor_capacity(hypervisor, model)
        hypervisor_utilization = self.get_hypervisor_utilization(
            hypervisor, model)
        vm_utilization = self.get_vm_utilization(vm_uuid, model)
        metrics = ['cpu', 'ram', 'disk']
        for m in metrics:
            if vm_utilization[m] + \
                    hypervisor_utilization[m] > hypervisor_capacity[m] * cc[m]:
                return False
        return True

    def offload_phase(self, model, cc):
        '''
        Offload phase performing first-fit based bin packing to offload
        overloaded hypervisors. This is done in a fashion of moving
        the least CPU utilized VM first as live migration these
        generaly causes less troubles.

         * TODO (cima) The curent implementation doesn't consider
         hypervisors' states. Offloading phase should be able to
         active turned off hypervisors (if available) in a case
         of the resource capacity provided by activated hypervisors
         is not able to accomodate all the load. As the offload phase
         is later followed by the consolidation phase, the hypervisor
         activation in this doesn't necessarily results in more activated
         hypervisors in the final solution.
        '''

        sorted_hypervisors = sorted(
            model.get_all_hypervisors().values(),
            key=lambda x: self.get_hypervisor_utilization(x, model)['cpu'])
        for hypervisor in reversed(sorted_hypervisors):
            if self.is_overloaded(hypervisor, model):
                for vm in sorted(model.get_mapping().get_node_vms(hypervisor),
                                 key=lambda x: self.get_vm_utilization(
                        x, model)['cpu']):
                    for dst_hypervisor in sorted_hypervisors:
                        if self.vm_fits(vm, dst_hypervisor, model, cc):
                            self.add_migration(vm, hypervisor,
                                               dst_hypervisor, model)
                            break
                    if not self.is_overloaded(hypervisor, model):
                        break

    def consolidation_phase(self, model, cc):
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
            model.get_all_hypervisors().values(),
            key=lambda x: self.get_hypervisor_utilization(x, model)['cpu'])
        asc = 0
        for hypervisor in sorted_hypervisors:
            for vm in sorted(model.get_mapping().get_node_vms(hypervisor),
                             key=lambda x: self.get_vm_utilization(
                             x, model)['cpu'],
                             reverse=True):
                dsc = len(sorted_hypervisors) - 1
                for dst_hypervisor in reversed(sorted_hypervisors):
                    if self.vm_fits(vm, dst_hypervisor, model, cc):
                        self.add_migration(vm, hypervisor,
                                           dst_hypervisor, model)
                    dsc -= 1
                    if asc >= dsc:
                        break
            asc += 1

    def execute(self, original_model):
        LOG.info("Executing Smart Strategy")
        model = self.get_prediction_model(original_model)
        cru = self.get_cluster_relative_utilization(model)

        '''
        A capacity coefficient (cc) might be used to adjust optimization
        thresholds. Different resources may require different coefficient
        values as well as setting up different coefficient values in both
        phases may lead to to more efficient consolidation in the end.
        If the cc equals 1 the full resource capacity may be used, cc
        values lower than 1 will lead to resource underutilization and
        values higher than 1 will lead to resource overbooking.
        e.g. If targetted utilization is 80% of hypervisor capacity,
        the coefficient in the consolidation phase will be 0.8, but
        may any lower value in the offloading phase. The lower it gets
        the cluster will appear more 'released' (distributed) for the
        following consolidation phase.
        '''
        cc = {'cpu': 1.0,
              'ram': 1.0,
              'disk': 1.0}

        # Offloading phase
        self.offload_phase(model, cc)

        # Consolidation phase
        self.consolidation_phase(model, cc)

        # Deactivate unused hypervisors
        self.deactivate_unused_hypervisors(model)

        cru_after = self.get_cluster_relative_utilization(model)
        info = {
            'number_of_migrations': self.number_of_migrations,
            'number_of_released_hypervisors':
                self.number_of_released_hypervisors,
            'relative_cluster_utilization_before': str(cru),
            'relative_cluster_utilization_after': str(cru_after)
        }

        LOG.debug(info)

        self.solution.model = model
        self.solution.efficacy = cru_after['cpu']

        return self.solution
