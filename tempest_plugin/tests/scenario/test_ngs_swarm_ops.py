# Copyright 2016 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from tempest.lib import decorators
from tempest import test

from tempest_plugin.tests.scenario import test_ngs_basic_ops

# NOTE(pas-ha) using 4 separate test case classes to force
# test runner to run them in parallel


class NGSSwarmOps1(test_ngs_basic_ops.NGSBasicOpsBase):
    @decorators.idempotent_id('59cb81a5-3fd5-4ad3-8c4a-c0b27435cb91')
    @test.services('network')
    def test_ngs_swarm_ops(self):
        self._test_ngs_basic_ops()


class NGSSwarmOps2(test_ngs_basic_ops.NGSBasicOpsBase):
    @decorators.idempotent_id('59cb81a5-3fd5-4ad3-8c4a-c0b27435cb92')
    @test.services('network')
    def test_ngs_swarm_ops(self):
        self._test_ngs_basic_ops()


class NGSSwarmOps3(test_ngs_basic_ops.NGSBasicOpsBase):
    @decorators.idempotent_id('59cb81a5-3fd5-4ad3-8c4a-c0b27435cb93')
    @test.services('network')
    def test_ngs_swarm_ops(self):
        self._test_ngs_basic_ops()


class NGSSwarmOps4(test_ngs_basic_ops.NGSBasicOpsBase):
    @decorators.idempotent_id('59cb81a5-3fd5-4ad3-8c4a-c0b27435cb94')
    @test.services('network')
    def test_ngs_swarm_ops(self):
        self._test_ngs_basic_ops()
