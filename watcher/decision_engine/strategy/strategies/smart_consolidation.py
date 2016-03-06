# -*- encoding: utf-8 -*-
#
# Authors: Vojtech CIMA <cima@zhaw.ch>
#          Bruno GRAZIOLI <gaea@zhaw.ch>
#          Sean MURPHY <murp@zhaw.ch>
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

from watcher._i18n import _LE
from watcher.common.exception import NoDataFound, WatcherException
from watcher.decision_engine.model import hypervisor_state as hyper_state
from watcher.decision_engine.model import vm_state
from watcher.decision_engine.model import resource
from watcher.decision_engine.strategy.strategies import base
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
        self._ceilometer = None
        self.number_of_migrations = 0
        self.number_of_released_hypervisors = 0
        self.ceilometer_vm_data_cache = dict()

    @property
    def ceilometer(self):
        if self._ceilometer is None:
            self._ceilometer = (ceilometer_cluster_history.
                                CeilometerClusterHistory(osc=self.osc))
        return self._ceilometer

    @ceilometer.setter
    def ceilometer(self, ceilometer):
        self._ceilometer = ceilometer

    def activate_hypervisor(self, hypervisor):
        """
        Adds an action for hypervisor activation into the solution.
        :param hypervisor: hypervisor object
        :return: None
        """

        params = {'state': hyper_state.HypervisorState.ONLINE.value}
        self.solution.add_action(
            action_type='change_nova_service_state',
            resource_id=hypervisor.uuid,
            input_parameters=params)
        self.number_of_released_hypervisors -= 1

    def deactivate_hypervisor(self, hypervisor):
        """
        Adds an action for hypervisor deactivation into the solution.
        :param hypervisor: hypervisor object
        :return: None
        """

        params = {'state': hyper_state.HypervisorState.OFFLINE.value}
        self.solution.add_action(
            action_type='change_nova_service_state',
            resource_id=hypervisor.uuid,
            input_parameters=params)
        self.number_of_released_hypervisors += 1

    def add_migration(self, vm_uuid, src_hypervisor,
                      dst_hypervisor, model):
        """
        Adds an action for VM migration into the solution.
        :param: vm_uuid: string
        :param src_hypervisor: hypervisor object
        :param dst_hypervisor: hypervisor object
        :param model: model_root object
        :return: None
        """

        vm = model.get_vm_from_id(vm_uuid)

        if vm.state != vm_state.VMState.ACTIVE:
            '''
            Watcher curently only supports live VM migration which
            requires VM to be active and both hypervisors to share
            storage. When supported, the block migration may be used
            as a fallback migration mechanism.

            TODO check whether this works and consider better exception
            '''
            LOG.error('Cannot live migrate VM %s in state %s.' %
                      (vm_uuid, vm.state.value))
            raise WatcherException

        migration_type = 'live'

        if dst_hypervisor.state == hyper_state.HypervisorState.OFFLINE:
            self.activate_hypervisor(dst_hypervisor)
        model.get_mapping().unmap(src_hypervisor, vm)
        model.get_mapping().map(dst_hypervisor, vm)

        params = {'migration_type': migration_type,
                  'src_hypervisor': src_hypervisor,
                  'dst_hypervisor': dst_hypervisor}
        self.solution.add_action(action_type='migrate',
                                 resource_id=vm.uuid,
                                 input_parameters=params)
        self.number_of_migrations += 1

    def deactivate_unused_hypervisors(self, model):
        """
        Generates actions for deactivation of unused hypervisors.
        :param model: model_root object
        :return: None
        """

        for hypervisor in model.get_all_hypervisors().values():
            if len(model.get_mapping().get_node_vms(hypervisor)) == 0:
                self.deactivate_hypervisor(hypervisor)

    def get_prediction_model(self, model):
        """
        Returns a deepcopy of a model representing current cluster state.
        :param model: model_root object
        :return: model_root object
        """

        return deepcopy(model)

    def get_vm_utilization(self, vm_uuid, model, period=3600, aggr='avg'):
        """
        Collect cpu, ram and disk utilization statistics of a virtual machine
        :param vm: vm object
        :param model: model_root object
        :param period: seconds
        :param aggr: string
        :return: dict(cpu(number of vcpus used), ram(MB used), disk(B used))
        """

        if vm_uuid in self.ceilometer_vm_data_cache.keys():
            return self.ceilometer_vm_data_cache.get(vm_uuid)

        cpu_util_metric = 'cpu_util'
        ram_util_metric = 'memory.usage'

        ram_alloc_metric = 'memory'
        disk_alloc_metric = 'disk.root.size'
        vm_cpu_util = \
            self.ceilometer.statistic_aggregation(resource_id=vm_uuid,
                                                  meter_name=cpu_util_metric,
                                                  period=period,
                                                  aggregate=aggr)
        vm_cpu_cores = model.get_resource_from_id(
            resource.ResourceType.cpu_cores).\
            get_capacity(model.get_vm_from_id(vm_uuid))

        if vm_cpu_util:
            total_cpu_utilization = vm_cpu_cores * (vm_cpu_util / 100.0)
        else:
            total_cpu_utilization = vm_cpu_cores

        vm_ram_util = \
            self.ceilometer.statistic_aggregation(resource_id=vm_uuid,
                                                  meter_name=ram_util_metric,
                                                  period=period,
                                                  aggregate=aggr)

        if not vm_ram_util:
            vm_ram_util = \
                self.ceilometer.statistic_aggregation(
                    resource_id=vm_uuid,
                    meter_name=ram_alloc_metric,
                    period=period,
                    aggregate=aggr)

        vm_disk_util = \
            self.ceilometer.statistic_aggregation(
                resource_id=vm_uuid,
                meter_name=disk_alloc_metric,
                period=period,
                aggregate=aggr)

        if not vm_ram_util or not vm_disk_util:
            LOG.error(
                _LE("No values returned by %(resource_id)s "
                    "for memory.usage or disk.root.size"),
                resource_id=vm_uuid
            )
            raise NoDataFound

        self.ceilometer_vm_data_cache[vm_uuid] = \
            dict(cpu=total_cpu_utilization, ram=vm_ram_util,
                 disk=vm_disk_util)
        return self.ceilometer_vm_data_cache.get(vm_uuid)

    def get_hypervisor_utilization(self, hypervisor, model, period=3600,
                                   aggr='avg'):
        """
        Collect cpu, ram and disk utilization statistics of a hypervisor
        :param hypervisor: hypervisor object
        :param model: model_root object
        :param period: seconds
        :param aggr: string
        :return: dict(cpu(number of cores used), ram(MB used), disk(B used))
        """

        hypervisor_vms = \
            model.get_mapping().get_node_vms_from_id(hypervisor.uuid)
        hypervisor_ram_util = 0
        hypervisor_disk_util = 0
        hypervisor_cpu_util = 0
        for vm_uuid in hypervisor_vms:
            vm_util = self.get_vm_utilization(vm_uuid, model)
            hypervisor_cpu_util += vm_util['cpu']
            hypervisor_ram_util += vm_util['ram']
            hypervisor_disk_util += vm_util['disk']

        return dict(cpu=hypervisor_cpu_util, ram=hypervisor_ram_util,
                    disk=hypervisor_disk_util)

    def get_hypervisor_capacity(self, hypervisor, model):
        """
        Collect cpu, ram and disk capacity of a hypervisor
        :param hypervisor: hypervisor object
        :param model: model_root object
        :return: dict(cpu(cores), ram(MB), disk(B))
        """

        hypervisor_cpu_capacity = model.get_resource_from_id(
            resource.ResourceType.cpu_cores).get_capacity(hypervisor)

        hypervisor_disk_capacity = model.get_resource_from_id(
            resource.ResourceType.disk_capacity).get_capacity(hypervisor)

        hypervisor_ram_capacity = model.get_resource_from_id(
            resource.ResourceType.memory).get_capacity(hypervisor)
        return dict(cpu=hypervisor_cpu_capacity, ram=hypervisor_ram_capacity,
                    disk=hypervisor_disk_capacity)

    def get_relative_hypervisor_utilization(self, hypervisor, model):
        """
        Returns relative hypervisor utilization (rhu).
        :param hypervisor: hypervisor object
        :param model: model_root object
        :return: {'cpu': <0,1>, 'ram': <0,1>, 'disk': <0,1>}
        """

        rhu = {}
        util = self.get_hypervisor_utilization(hypervisor, model)
        cap = self.get_hypervisor_capacity(hypervisor, model)
        for k in util.keys():
            rhu[k] = float(util[k]) / float(cap[k])
        return rhu

    def get_relative_cluster_utilization(self, model):
        """
        Returns relative cluster utilization (rcu). RCU is an
        average of relative utilizations (rhu) of active hypervisors.
        :param model: model_root object
        :return: {'cpu': <0,1>, 'ram': <0,1>, 'disk': <0,1>}
        """

        hypervisors = model.get_all_hypervisors().values()
        rcu = {}
        counters = {}
        for hypervisor in hypervisors:
            if hypervisor.state == hyper_state.HypervisorState.ONLINE.value:
                rhu = self.get_relative_hypervisor_utilization(
                    hypervisor, model)
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
        """
        Indicates whether a hypervisor is overloaded considering
        provided resource capacity coefficients (cc).
        :param hypervisor: hypervisor object
        :param model: model_root object
        :param cc: dictionary containing resource capacity coefficients
        :return: [True, False]
        """

        hypervisor_capacity = self.get_hypervisor_capacity(hypervisor, model)
        hypervisor_utilization = self.get_hypervisor_utilization(
            hypervisor, model)
        metrics = ['cpu']
        for m in metrics:
            if hypervisor_utilization[m] > hypervisor_capacity[m] * cc[m]:
                return True
        return False

    def vm_fits(self, vm_uuid, hypervisor, model, cc):
        """
        Indicates whether is a hypervisor able to accomodate a VM
        considering provided resource capacity coefficients (cc).
        :param vm_uuid: string
        :param hypervisor: hypervisor object
        :param model: model_root object
        :param cc: dictionary containing resource capacity coefficients
        :return: [True, False]
        """

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

    def optimize_solution(self, model):
        """
        Optimizes solution by eliminating unnecessesary or
        circular set of migrations which can be replaced by
        a more efficient solution.
        e.g.:
         * A->B, B->C => replace migrations A->B, B->C with
           a single migration A->C as both solution result in
           VM running on hypervisor C which can be achieved with
           one migration instead of two.
         * A->B, B->A => remove A->B and B->A as they do not result
           in a new VM placement.
        """

        migrate_actions = (
            a for a in self.solution.actions if a[
                'action_type'] == 'migrate')
        vm_to_be_migrated = (a['input_parameters']['resource_id']
                             for a in migrate_actions)
        vm_uuids = list(set(vm_to_be_migrated))
        for vm_uuid in vm_uuids:
            actions = list(
                a for a in self.solution.actions if a[
                    'input_parameters'][
                        'resource_id'] == vm_uuid)
            if len(actions) > 1:
                src = actions[0]['input_parameters']['src_hypervisor']
                dst = actions[-1]['input_parameters']['dst_hypervisor']
                for a in actions:
                    self.solution.actions.remove(a)
                    self.number_of_migrations -= 1
                if src != dst:
                    self.add_migration(vm_uuid, src, dst, model)

    def offload_phase(self, model, cc):
        """
        Performs offloading phase considering provided resource
        capacity coefficients.
        Offload phase performing first-fit based bin packing to offload
        overloaded hypervisors. This is done in a fashion of moving
        the least CPU utilized VM first as live migration these
        generaly causes less troubles. This phase results in a cluster
        with no overloaded hypervisors.

        :param model: model_root object
        :param cc: dictionary containing resource capacity coefficients

        * This phase is be able to activate turned off hypervisors (if needed
        and any available) in the case of the resource capacity provided by
        active hypervisors is not able to accomodate all the load.
        As the offload phase is later followed by the consolidation phase,
        the hypervisor activation in this phase doesn't necessarily results
        in more activated hypervisors in the final solution.
        """

        sorted_hypervisors = sorted(
            model.get_all_hypervisors().values(),
            key=lambda x: self.get_hypervisor_utilization(x, model)['cpu'])
        for hypervisor in reversed(sorted_hypervisors):
            if self.is_overloaded(hypervisor, model, cc):
                for vm in sorted(model.get_mapping().get_node_vms(hypervisor),
                                 key=lambda x: self.get_vm_utilization(
                        x, model)['cpu']):
                    for dst_hypervisor in reversed(sorted_hypervisors):
                        if self.vm_fits(vm, dst_hypervisor, model, cc):
                            self.add_migration(vm, hypervisor,
                                               dst_hypervisor, model)
                            break
                    if not self.is_overloaded(hypervisor, model, cc):
                        break

    def consolidation_phase(self, model, cc):
        """
        Performs consolidation phase considering provided resource
        capacity coefficients.
        Consolidation phase performing first-fit based bin packing.
        First, hypervisors with the lowest cpu utilization are consolidated
        by moving their load to hypervisors with the highest cpu utilization
        which can accomodate the load. In this phase the most cpu utilizied
        VMs are prioritizied as their load is more difficult to accomodate
        in the system than less cpu utilizied VMs which can be later used
        to fill smaller CPU capacity gaps.

        :param model: model_root object
        :param cc: dictionary containing resource capacity coefficients
        """

        sorted_hypervisors = sorted(
            model.get_all_hypervisors().values(),
            key=lambda x: self.get_hypervisor_utilization(x, model)['cpu'])
        asc = 0
        for hypervisor in sorted_hypervisors:
            vms = sorted(model.get_mapping().get_node_vms(hypervisor),
                         key=lambda x: self.get_vm_utilization(x,
                         model)['cpu'])
            for vm in reversed(vms):
                dsc = len(sorted_hypervisors) - 1
                for dst_hypervisor in reversed(sorted_hypervisors):
                    if asc >= dsc:
                        break
                    if self.vm_fits(vm, dst_hypervisor, model, cc):
                        self.add_migration(vm, hypervisor,
                                           dst_hypervisor, model)
                    dsc -= 1
            asc += 1

    def execute(self, original_model):
        """
        Strategy's main entry point.
        This strategy produces a solution resulting in more
        efficient utilizition of cluster resources using following
        four phases:
         * Offload phase - handling over-utilized resources
         * Consolidation phase - handling under-utilized resources
         * Solution optimization - reducing number of migrations
         * Deactivation of unused hypervisors

        :param original_model: root_model object

        * A capacity coefficient (cc) might be used to adjust optimization
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
        """

        LOG.info("Executing Smart Strategy")
        model = self.get_prediction_model(original_model)
        cru = self.get_relative_cluster_utilization(model)
        self.ceilometer_vm_data_cache = dict()

        cc = {'cpu': 1.0, 'ram': 1.0, 'disk': 1.0}

        # Offloading phase
        self.offload_phase(model, cc)

        # Consolidation phase
        self.consolidation_phase(model, cc)

        # Optimize solution
        self.optimize_solution(model)

        # Deactivate unused hypervisors
        self.deactivate_unused_hypervisors(model)

        cru_after = self.get_relative_cluster_utilization(model)
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
