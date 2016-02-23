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

from watcher.decision_engine.strategy.strategies.smart_consolidation import \
    SmartStrategy
from watcher.tests.decision_engine.strategy.strategies \
    import faker_cluster_state
from watcher.tests.decision_engine.strategy.strategies \
    import faker_metrics_collector


class TestSmartConsolidation(base.BaseTestCase):
    fake_metrics = faker_metrics_collector.FakerMetricsCollector()
    fake_cluster = faker_cluster_state.FakerModelCollector()

    def test_get_vm_utilization(self):
        pass

    def test_get_hypervisor_utilization(self):
        strategy = SmartStrategy()
        cluster = self.fake_cluster.generate_scenario_1()

    def test_get_hypervisor_capacity(self):
        pass
