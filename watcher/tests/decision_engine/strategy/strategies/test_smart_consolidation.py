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
from watcher.tests import base

import mock

from watcher.decision_engine.strategy.strategies.smart_consolidation import \
    SmartStrategy
from watcher.tests.decision_engine.strategy.strategies \
    import faker_cluster_state
from watcher.tests.decision_engine.strategy.strategies \
    import faker_metrics_collector


class TestingSmartStrategy(SmartStrategy):
    DEFAULT_NAME = 'smart'
    DEFAULT_DESCRIPTION = 'Smart Strategy'

    def __init__(self, name=DEFAULT_NAME, description=DEFAULT_DESCRIPTION,
                 osc=None):
        self._ceilometer = None


class TestSmartConsolidation(base.BaseTestCase):
    fake_metrics = faker_metrics_collector.FakeCeilometerMetrics()
    fake_cluster = faker_cluster_state.FakerModelCollector2()

    def test_get_vm_utilization(self):
        cluster = self.fake_cluster.generate_scenario_1()
        strategy = TestingSmartStrategy()
        strategy._ceilometer = mock.MagicMock(
            statistic_aggregation=self.fake_metrics.mock_get_statistics)
        vm_0 = cluster.get_vm_from_id("VM_0")
        vm_util = dict(cpu=1.0, ram=1, disk=10)
        self.assertEqual(strategy.get_vm_utilization(vm_0.uuid, cluster),
                         vm_util)

    def test_get_hypervisor_utilization(self):
        cluster = self.fake_cluster.generate_scenario_1()
        strategy = TestingSmartStrategy()
        strategy._ceilometer = mock.MagicMock(
            statistic_aggregation=self.fake_metrics.mock_get_statistics)
        node_0 = cluster.get_hypervisor_from_id("Node_0")
        node_util = dict(cpu=20.0, ram=3, disk=25)
        self.assertEqual(strategy.get_hypervisor_utilization(node_0, cluster),
                         node_util)

    def test_get_hypervisor_capacity(self):
        cluster = self.fake_cluster.generate_scenario_1()
        strategy = TestingSmartStrategy()
        strategy._ceilometer = mock.MagicMock(
            statistic_aggregation=self.fake_metrics.mock_get_statistics)
        node_0 = cluster.get_hypervisor_from_id("Node_0")
        node_util = dict(cpu=40, ram=64, disk=250)
        self.assertEqual(strategy.get_hypervisor_capacity(node_0, cluster),
                         node_util)

    def test_add_migration():
        pass

    def test_is_overloaded():
        pass

    def test_deactivate_unused_hypervisors():
        pass

    def test_offload_phase(self):
        '''
        Scenario: 2 hypervisors, 2VMs in total exceeding
        hypervisors capacity.
        '''
        # TODO use own models and metrics
        model = self.fake_cluster.generate_scenario_1()
        strategy = SmartStrategy()
        strategy.ceilometer = mock.MagicMock(
            statistic_aggregation=self.fake_metrics.mock_get_statistics)

    def test_consolidation_phase(self):
        '''
        Scenario: 2 hypervisors, 2 VMs which both can be
        accommodated using just one.
        Expected actions: 1 VM migration, 1 hypervisor
        state change.
        '''
        # TODO use own models and metrics
        model = self.fake_cluster.generate_scenario_1()
        strategy = SmartStrategy()
        strategy.ceilometer = mock.MagicMock(
            statistic_aggregation=self.fake_metrics.mock_get_statistics)
