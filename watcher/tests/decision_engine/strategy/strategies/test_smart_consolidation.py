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


class TestSmartConsolidation(base.BaseTestCase):
    fake_cluster = faker_cluster_state.FakerModelCollector2()

    def test_get_vm_utilization(self):
        cluster = self.fake_cluster.generate_scenario_1()
        fake_metrics = faker_metrics_collector.FakeCeilometerMetrics(cluster)
        strategy = SmartStrategy()
        strategy.ceilometer = mock.MagicMock(
            statistic_aggregation=fake_metrics.mock_get_statistics)
        vm_0 = cluster.get_vm_from_id("VM_0")
        vm_util = dict(cpu=1.0, ram=1, disk=10)
        self.assertEqual(strategy.get_vm_utilization(vm_0.uuid, cluster),
                         vm_util)

    def test_get_hypervisor_utilization(self):
        cluster = self.fake_cluster.generate_scenario_1()
        fake_metrics = faker_metrics_collector.FakeCeilometerMetrics(cluster)
        strategy = SmartStrategy()
        strategy.ceilometer = mock.MagicMock(
            statistic_aggregation=fake_metrics.mock_get_statistics)
        node_0 = cluster.get_hypervisor_from_id("Node_0")
        node_util = dict(cpu=1.0, ram=1, disk=10)
        self.assertEqual(strategy.get_hypervisor_utilization(node_0, cluster),
                         node_util)

    def test_get_hypervisor_capacity(self):
        cluster = self.fake_cluster.generate_scenario_1()
        fake_metrics = faker_metrics_collector.FakeCeilometerMetrics(cluster)
        strategy = SmartStrategy()
        strategy.ceilometer = mock.MagicMock(
            statistic_aggregation=fake_metrics.mock_get_statistics)
        node_0 = cluster.get_hypervisor_from_id("Node_0")
        node_util = dict(cpu=40, ram=64, disk=250)
        self.assertEqual(strategy.get_hypervisor_capacity(node_0, cluster),
                         node_util)

    def test_get_relative_hypervisor_utilization(self):
        model = self.fake_cluster.generate_scenario_1()
        fake_metrics = faker_metrics_collector.FakeCeilometerMetrics(model)
        strategy = SmartStrategy()
        strategy.ceilometer = mock.MagicMock(
            statistic_aggregation=fake_metrics.mock_get_statistics)
        hypervisor = model.get_hypervisor_from_id('Node_0')
        rhu = strategy.get_relative_hypervisor_utilization(hypervisor, model)
        expected_rhu = {'disk': 0.04, 'ram': 0.015625, 'cpu': 0.025}
        self.assertEqual(rhu, expected_rhu)

    def test_get_relative_cluster_utilization(self):
        model = self.fake_cluster.generate_scenario_1()
        fake_metrics = faker_metrics_collector.FakeCeilometerMetrics(model)
        strategy = SmartStrategy()
        strategy.ceilometer = mock.MagicMock(
            statistic_aggregation=fake_metrics.mock_get_statistics)
        cru = strategy.get_relative_cluster_utilization(model)
        expected_cru = {'cpu': 0.05, 'disk': 0.05, 'ram': 0.0234375}
        self.assertEqual(cru, expected_cru)

    def test_add_migration(self):
        model = self.fake_cluster.generate_scenario_1()
        fake_metrics = faker_metrics_collector.FakeCeilometerMetrics(model)
        strategy = SmartStrategy()
        strategy.ceilometer = mock.MagicMock(
            statistic_aggregation=fake_metrics.mock_get_statistics)
        h1 = model.get_hypervisor_from_id('Node_0')
        h2 = model.get_hypervisor_from_id('Node_1')
        vm_uuid = 'VM_0'
        strategy.add_migration(vm_uuid, h1, h2, model)
        self.assertEqual(len(strategy.solution.actions), 1)
        expected = {'action_type': 'migrate',
                    'input_parameters': {'dst_hypervisor': h2,
                                         'src_hypervisor': h1,
                                         'migration_type': 'live',
                                         'resource_id': vm_uuid}}
        self.assertEqual(strategy.solution.actions[0], expected)

    def test_is_overloaded(self):
        strategy = SmartStrategy()
        model = self.fake_cluster.generate_scenario_1()
        fake_metrics = faker_metrics_collector.FakeCeilometerMetrics(model)
        strategy.ceilometer = mock.MagicMock(
            statistic_aggregation=fake_metrics.mock_get_statistics)
        h1 = model.get_hypervisor_from_id('Node_0')
        cc = {'cpu': 1.0, 'ram': 1.0, 'disk': 1.0}
        res = strategy.is_overloaded(h1, model, cc)
        self.assertEqual(res, False)

        cc = {'cpu': 0.025, 'ram': 1.0, 'disk': 1.0}
        res = strategy.is_overloaded(h1, model, cc)
        self.assertEqual(res, False)

        cc = {'cpu': 0.024, 'ram': 1.0, 'disk': 1.0}
        res = strategy.is_overloaded(h1, model, cc)
        self.assertEqual(res, True)

    def test_vm_fits(self):
        model = self.fake_cluster.generate_scenario_1()
        fake_metrics = faker_metrics_collector.FakeCeilometerMetrics(model)
        strategy = SmartStrategy()
        strategy.ceilometer = mock.MagicMock(
            statistic_aggregation=fake_metrics.mock_get_statistics)
        h = model.get_hypervisor_from_id('Node_1')
        vm_uuid = 'VM_0'
        cc = {'cpu': 1.0, 'ram': 1.0, 'disk': 1.0}
        res = strategy.vm_fits(vm_uuid, h, model, cc)
        self.assertEqual(res, True)

        cc = {'cpu': 0.025, 'ram': 1.0, 'disk': 1.0}
        res = strategy.vm_fits(vm_uuid, h, model, cc)
        self.assertEqual(res, False)

    def test_activate_hypervisor(self):
        model = self.fake_cluster.generate_scenario_1()
        fake_metrics = faker_metrics_collector.FakeCeilometerMetrics(model)
        strategy = SmartStrategy()
        strategy.ceilometer = mock.MagicMock(
            statistic_aggregation=fake_metrics.mock_get_statistics)
        h = model.get_hypervisor_from_id('Node_0')
        strategy.activate_hypervisor(h)
        expected = [{'action_type': 'change_nova_service_state',
                     'input_parameters': {'state': 'up',
                                          'resource_id': 'Node_0'}}]
        self.assertEqual(strategy.solution.actions, expected)

    def test_deactivate_hypervisor(self):
        model = self.fake_cluster.generate_scenario_1()
        fake_metrics = faker_metrics_collector.FakeCeilometerMetrics(model)
        strategy = SmartStrategy()
        strategy.ceilometer = mock.MagicMock(
            statistic_aggregation=fake_metrics.mock_get_statistics)
        h = model.get_hypervisor_from_id('Node_0')
        strategy.deactivate_hypervisor(h)
        expected = [{'action_type': 'change_nova_service_state',
                     'input_parameters': {'state': 'down',
                                          'resource_id': 'Node_0'}}]
        self.assertEqual(strategy.solution.actions, expected)

    def test_deactivate_unused_hypervisors(self):
        model = self.fake_cluster.generate_scenario_1()
        fake_metrics = faker_metrics_collector.FakeCeilometerMetrics(model)
        strategy = SmartStrategy()
        strategy.ceilometer = mock.MagicMock(
            statistic_aggregation=fake_metrics.mock_get_statistics)
        h1 = model.get_hypervisor_from_id('Node_0')
        h2 = model.get_hypervisor_from_id('Node_1')
        vm_uuid = 'VM_0'
        strategy.deactivate_unused_hypervisors(model)
        self.assertEqual(len(strategy.solution.actions), 0)

        # Migrate VM to free the hypervisor
        strategy.add_migration(vm_uuid, h1, h2, model)

        strategy.deactivate_unused_hypervisors(model)
        expected = {'action_type': 'change_nova_service_state',
                    'input_parameters': {'state': 'down',
                                         'resource_id': 'Node_0'}}
        self.assertEqual(len(strategy.solution.actions), 2)
        self.assertEqual(strategy.solution.actions[1], expected)

    def test_offload_phase(self):
        model = self.fake_cluster.generate_scenario_1()
        fake_metrics = faker_metrics_collector.FakeCeilometerMetrics(model)
        strategy = SmartStrategy()
        strategy.ceilometer = mock.MagicMock(
            statistic_aggregation=fake_metrics.mock_get_statistics)
        cc = {'cpu': 1.0, 'ram': 1.0, 'disk': 1.0}
        strategy.offload_phase(model, cc)
        expected = []
        self.assertEqual(strategy.solution.actions, expected)

    def test_consolidation_phase(self):
        model = self.fake_cluster.generate_scenario_1()
        fake_metrics = faker_metrics_collector.FakeCeilometerMetrics(model)
        strategy = SmartStrategy()
        strategy.ceilometer = mock.MagicMock(
            statistic_aggregation=fake_metrics.mock_get_statistics)
        h1 = model.get_hypervisor_from_id('Node_0')
        h2 = model.get_hypervisor_from_id('Node_1')
        vm_uuid = 'VM_0'
        cc = {'cpu': 1.0, 'ram': 1.0, 'disk': 1.0}
        strategy.consolidation_phase(model, cc)
        expected = [{'action_type': 'migrate',
                     'input_parameters': {'dst_hypervisor': h2,
                                          'src_hypervisor': h1,
                                          'migration_type': 'live',
                                          'resource_id': vm_uuid}}]
        self.assertEqual(strategy.solution.actions, expected)

    def test_strategy(self):
        model = self.fake_cluster.generate_scenario_2()
        fake_metrics = faker_metrics_collector.FakeCeilometerMetrics(model)
        strategy = SmartStrategy()
        strategy.ceilometer = mock.MagicMock(
            statistic_aggregation=fake_metrics.mock_get_statistics)
        h1 = model.get_hypervisor_from_id('Node_0')
        h2 = model.get_hypervisor_from_id('Node_1')
        cc = {'cpu': 1.0, 'ram': 1.0, 'disk': 1.0}
        strategy.offload_phase(model, cc)
        strategy.consolidation_phase(model, cc)
        strategy.deactivate_unused_hypervisors(model)
        strategy.optimize_solution(model)
        expected = [{'action_type': 'migrate',
                     'input_parameters': {'dst_hypervisor': h2,
                                          'src_hypervisor': h1,
                                          'migration_type': 'live',
                                          'resource_id': 'VM_3'}},
                    {'action_type': 'migrate',
                     'input_parameters': {'dst_hypervisor': h2,
                                          'src_hypervisor': h1,
                                          'migration_type': 'live',
                                          'resource_id': 'VM_1'}},
                    {'action_type': 'change_nova_service_state',
                     'input_parameters': {'state': 'down',
                                          'resource_id': 'Node_3'}},
                    {'action_type': 'change_nova_service_state',
                     'input_parameters': {'state': 'down',
                                          'resource_id': 'Node_2'}}]
        self.assertEqual(strategy.solution.actions, expected)
