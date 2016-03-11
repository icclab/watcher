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

import random
from watcher.decision_engine.model import resource


class FakerMetricsCollector(object):
    def __init__(self):
        self.emptytype = ""

    def empty_one_metric(self, emptytype):
        self.emptytype = emptytype

    def mock_get_statistics(self, resource_id, meter_name, period,
                            aggregate='avg'):
        result = 0
        if meter_name == "compute.node.cpu.percent":
            result = self.get_usage_node_cpu(resource_id)
        elif meter_name == "cpu_util":
            result = self.get_average_usage_vm_cpu(resource_id)
        elif meter_name == "hardware.ipmi.node.outlet_temperature":
            result = self.get_average_outlet_temperature(resource_id)
        return result

    def get_average_outlet_temperature(self, uuid):
        """The average outlet temperature for host"""
        mock = {}
        mock['Node_0'] = 30
        # use a big value to make sure it exceeds threshold
        mock['Node_1'] = 100
        if uuid not in mock.keys():
            mock[uuid] = 100

        return mock[str(uuid)]

    def get_usage_node_cpu(self, uuid):
        """The last VM CPU usage values to average

            :param uuid:00
            :return:
            """
        # query influxdb stream

        # compute in stream

        # Normalize
        mock = {}
        # node 0
        mock['Node_0_hostname_0'] = 7
        mock['Node_1_hostname_1'] = 7
        # node 1
        mock['Node_2_hostname_2'] = 80
        # node 2
        mock['Node_3_hostname_3'] = 5
        mock['Node_4_hostname_4'] = 5
        mock['Node_5_hostname_5'] = 10

        # node 3
        mock['Node_6_hostname_6'] = 8
        mock['Node_19_hostname_19'] = 10
        # node 4
        mock['VM_7_hostname_7'] = 4

        if uuid not in mock.keys():
            # mock[uuid] = random.randint(1, 4)
            mock[uuid] = 8

        return float(mock[str(uuid)])

    def get_average_usage_vm_cpu(self, uuid):
        """The last VM CPU usage values to average

        :param uuid:00
        :return:
        """
        # query influxdb stream

        # compute in stream

        # Normalize
        mock = {}
        # node 0
        mock['VM_0'] = 7
        mock['VM_1'] = 7
        # node 1
        mock['VM_2'] = 10
        # node 2
        mock['VM_3'] = 5
        mock['VM_4'] = 5
        mock['VM_5'] = 10

        # node 3
        mock['VM_6'] = 8

        # node 4
        mock['VM_7'] = 4
        if uuid not in mock.keys():
            # mock[uuid] = random.randint(1, 4)
            mock[uuid] = 8

        return mock[str(uuid)]

    def get_average_usage_vm_memory(self, uuid):
        mock = {}
        # node 0
        mock['VM_0'] = 2
        mock['VM_1'] = 5
        # node 1
        mock['VM_2'] = 5
        # node 2
        mock['VM_3'] = 8
        mock['VM_4'] = 5
        mock['VM_5'] = 16

        # node 3
        mock['VM_6'] = 8

        # node 4
        mock['VM_7'] = 4
        if uuid not in mock.keys():
            # mock[uuid] = random.randint(1, 4)
            mock[uuid] = 10

        return mock[str(uuid)]

    def get_average_usage_vm_disk(self, uuid):
        mock = {}
        # node 0
        mock['VM_0'] = 2
        mock['VM_1'] = 2
        # node 1
        mock['VM_2'] = 2
        # node 2
        mock['VM_3'] = 10
        mock['VM_4'] = 15
        mock['VM_5'] = 20

        # node 3
        mock['VM_6'] = 8

        # node 4
        mock['VM_7'] = 4

        if uuid not in mock.keys():
            # mock[uuid] = random.randint(1, 4)
            mock[uuid] = 4

        return mock[str(uuid)]

    def get_virtual_machine_capacity(self, vm_uuid):
        return random.randint(1, 4)

    def get_average_network_incomming(self, node):
        pass

    def get_average_network_outcomming(self, node):
        pass


class FakeCeilometerMetrics:
    def __init__(self, model):
        self.model = model

    def mock_get_statistics(self, resource_id, meter_name, period=3600,
                            aggregate='avg'):
        if meter_name == "compute.node.cpu.percent":
            return self.get_hypervisor_cpu_util(resource_id)
        elif meter_name == "cpu_util":
            return self.get_vm_cpu_util(resource_id)
        elif meter_name == "memory.usage":
            return self.get_vm_ram_util(resource_id)
        elif meter_name == "disk.root.size":
            return self.get_vm_disk_root_size(resource_id)

    def get_hypervisor_cpu_util(self, r_id):
        '''
        Calculates hypervisor utilization dynamicaly.
        Hypervisor CPU utilization should consider
        and corelate with actual VM-hypervisor mappings
        provided within a cluster model.

        Returns relative hypervisor CPU utilization <0, 100>.
        '''

        id = '%s_%s' % (r_id.split('_')[0], r_id.split('_')[1])
        vms = self.model.get_mapping().get_node_vms_from_id(id)
        util_sum = 0.0
        hypervisor_cpu_cores = self.model.get_resource_from_id(
            resource.ResourceType.cpu_cores).get_capacity_from_id(id)
        for vm_uuid in vms:
            vm_cpu_cores = self.model.get_resource_from_id(
                resource.ResourceType.cpu_cores).\
                get_capacity(self.model.get_vm_from_id(vm_uuid))
            total_cpu_util = vm_cpu_cores * self.get_vm_cpu_util(vm_uuid)
            util_sum += total_cpu_util / 100.0
        util_sum /= hypervisor_cpu_cores
        return util_sum * 100.0

    def get_vm_cpu_util(self, r_id):
        vm_cpu_util = dict()
        vm_cpu_util['VM_0'] = 10
        vm_cpu_util['VM_1'] = 30
        vm_cpu_util['VM_2'] = 60
        vm_cpu_util['VM_3'] = 20
        vm_cpu_util['VM_4'] = 40
        vm_cpu_util['VM_5'] = 50
        vm_cpu_util['VM_6'] = 100
        vm_cpu_util['VM_7'] = 100
        vm_cpu_util['VM_8'] = 100
        vm_cpu_util['VM_9'] = 100
        return vm_cpu_util[str(r_id)]

    def get_vm_ram_util(self, r_id):
        vm_ram_util = dict()
        vm_ram_util['VM_0'] = 1
        vm_ram_util['VM_1'] = 2
        vm_ram_util['VM_2'] = 4
        vm_ram_util['VM_3'] = 8
        vm_ram_util['VM_4'] = 3
        vm_ram_util['VM_5'] = 2
        vm_ram_util['VM_6'] = 1
        vm_ram_util['VM_7'] = 2
        vm_ram_util['VM_8'] = 4
        vm_ram_util['VM_9'] = 8
        return vm_ram_util[str(r_id)]

    def get_vm_disk_root_size(self, r_id):
        vm_disk_util = dict()
        vm_disk_util['VM_0'] = 10
        vm_disk_util['VM_1'] = 15
        vm_disk_util['VM_2'] = 30
        vm_disk_util['VM_3'] = 35
        vm_disk_util['VM_4'] = 20
        vm_disk_util['VM_5'] = 25
        vm_disk_util['VM_6'] = 25
        vm_disk_util['VM_7'] = 25
        vm_disk_util['VM_8'] = 25
        vm_disk_util['VM_9'] = 25
        return vm_disk_util[str(r_id)]
