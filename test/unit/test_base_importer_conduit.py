#!/usr/bin/python
#
# Copyright (c) 2011 Red Hat, Inc.
#
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

# Python
import mock
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../common/")
import mock_plugins
import testutil

from pulp.server.content.conduits._base import BaseImporterConduit, ImporterConduitException
import pulp.server.content.types.database as types_database
from pulp.server.db.model.gc_repository import Repo
import pulp.server.managers.factory as manager_factory
from pulp.server.managers.repo.cud import RepoManager
from pulp.server.managers.repo.importer import RepoImporterManager

# -- test cases ---------------------------------------------------------------

class BaseImporterConduitTests(testutil.PulpTest):

    def clean(self):
        super(BaseImporterConduitTests, self).clean()
        types_database.clean()

        Repo.get_collection().remove()

    def setUp(self):
        super(BaseImporterConduitTests, self).setUp()
        mock_plugins.install()

        self.repo_manager = RepoManager()
        self.importer_manager = RepoImporterManager()

        self.repo_id = u'\u0938\u093e\u092f\u0932\u0940'
        self.repo_manager.create_repo(self.repo_id)
        self.conduit = BaseImporterConduit(self.repo_id, 'test-importer')

    def tearDown(self):
        super(BaseImporterConduitTests, self).tearDown()
        manager_factory.reset()

    def test_get_set_scratchpad(self):
        """
        Tests scratchpad calls.
        """

        # Setup
        self.importer_manager.set_importer(self.repo_id, 'mock-importer', {})

        # Test - get no scratchpad
        self.assertTrue(self.conduit.get_scratchpad() is None)

        # Test - set scrathpad
        value = 'dragon'
        self.conduit.set_scratchpad(value)

        # Test - get updated value
        self.assertEqual(value, self.conduit.get_scratchpad())

    def test_scratchpad_with_error(self):
        # Setup
        mock_manager = mock.Mock()
        mock_manager.get_importer_scratchpad.side_effect = Exception()
        mock_manager.set_importer_scratchpad.side_effect = Exception()

        manager_factory._INSTANCES[manager_factory.TYPE_REPO_IMPORTER] = mock_manager

        # Test
        self.assertRaises(ImporterConduitException, self.conduit.get_scratchpad)
        self.assertRaises(ImporterConduitException, self.conduit.set_scratchpad, 'foo')