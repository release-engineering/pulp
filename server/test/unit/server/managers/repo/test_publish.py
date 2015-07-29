import datetime
import signal

import mock

from .... import base
from pulp.common import dateutils, constants, error_codes
from pulp.common.tags import resource_tag, RESOURCE_REPOSITORY_TYPE, action_tag
from pulp.devel import mock_plugins
from pulp.plugins.loader.exceptions import PluginNotFound
from pulp.plugins.model import PublishReport
from pulp.server.async import tasks
from pulp.server.db.model.repository import Repo, RepoDistributor, RepoPublishResult
from pulp.server.exceptions import InvalidValue, MissingResource, PulpCodedException
import pulp.server.managers.repo.cud as repo_manager
import pulp.server.managers.repo.distributor as distributor_manager
import pulp.server.managers.repo.publish as publish_manager


class RepoSyncManagerTests(base.PulpServerTests):

    def setUp(self):
        super(RepoSyncManagerTests, self).setUp()
        mock_plugins.install()

        # Create the manager instances for testing
        self.repo_manager = repo_manager.RepoManager()
        self.distributor_manager = distributor_manager.RepoDistributorManager()
        self.publish_manager = publish_manager.RepoPublishManager()

    def tearDown(self):
        super(RepoSyncManagerTests, self).tearDown()
        mock_plugins.reset()

    def clean(self):
        super(RepoSyncManagerTests, self).clean()
        Repo.get_collection().remove()
        RepoDistributor.get_collection().remove()
        RepoPublishResult.get_collection().remove()

    @mock.patch('pulp.server.managers.repo.publish.publish.apply_async_with_reservation')
    def test_queue_publish(self, mock_publish_task):
        repo_id = 'foo'
        distributor_id = 'bar'
        overrides = {'baz': 1}
        self.publish_manager.queue_publish(repo_id, distributor_id, overrides)
        kwargs = {
            'repo_id': repo_id,
            'distributor_id': distributor_id,
            'publish_config_override': overrides
        }
        tags = [resource_tag(RESOURCE_REPOSITORY_TYPE, repo_id), action_tag('publish')]
        mock_publish_task.assert_called_with(RESOURCE_REPOSITORY_TYPE, repo_id, tags=tags,
                                             kwargs=kwargs)

    @mock.patch('pulp.server.managers.repo.publish.datetime')
    @mock.patch('pulp.server.managers.repo._common.get_working_directory',
                return_value="/var/cache/pulp/mock_worker/mock_task_id")
    @mock.patch('pulp.server.managers.event.fire.EventFireManager.fire_repo_publish_started')
    @mock.patch('pulp.server.managers.event.fire.EventFireManager.fire_repo_publish_finished')
    def test_publish(self, mock_finished, mock_started, mock_get_working_directory, dt):
        """
        Tests publish under normal conditions when everything is configured
        correctly.
        """

        # Setup
        publish_config = {'foo': 'bar'}
        self.repo_manager.create_repo('repo-1')
        self.distributor_manager.add_distributor('repo-1', 'mock-distributor', publish_config,
                                                 False, distributor_id='dist-1')
        self.distributor_manager.add_distributor('repo-1', 'mock-distributor-2', publish_config,
                                                 False, distributor_id='dist-2')
        dt.utcnow.return_value = 1234

        # Test
        self.publish_manager.publish('repo-1', 'dist-1', None)

        # Verify

        #   Database
        repo_distributor = RepoDistributor.get_collection().find_one({'repo_id': 'repo-1',
                                                                      'id': 'dist-1'})
        self.assertTrue(repo_distributor['last_publish'] is not None)
        self.assertEqual(repo_distributor['last_publish'], dt.utcnow.return_value)

        #   History
        entries = list(RepoPublishResult.get_collection().find({'repo_id': 'repo-1'}))
        self.assertEqual(1, len(entries))
        self.assertEqual('repo-1', entries[0]['repo_id'])
        self.assertEqual('dist-1', entries[0]['distributor_id'])
        self.assertEqual('mock-distributor', entries[0]['distributor_type_id'])
        self.assertTrue(entries[0]['started'] is not None)
        self.assertTrue(entries[0]['completed'] is not None)
        self.assertEqual(RepoPublishResult.RESULT_SUCCESS, entries[0]['result'])
        self.assertTrue(entries[0]['summary'] is not None)
        self.assertTrue(entries[0]['details'] is not None)
        self.assertTrue(entries[0]['error_message'] is None)
        self.assertTrue(entries[0]['exception'] is None)
        self.assertTrue(entries[0]['traceback'] is None)

        #   Call into the correct distributor
        call_args = mock_plugins.MOCK_DISTRIBUTOR.publish_repo.call_args[0]

        self.assertEqual('repo-1', call_args[0].id)
        self.assertTrue(call_args[1] is not None)
        self.assertEqual({}, call_args[2].plugin_config)
        self.assertEqual(publish_config, call_args[2].repo_plugin_config)
        self.assertEqual({}, call_args[2].override_config)

        self.assertEqual(0, mock_plugins.MOCK_DISTRIBUTOR_2.publish_repo.call_count)

        self.assertEqual(1, mock_started.call_count)
        self.assertEqual('repo-1', mock_started.call_args[0][0])

        self.assertEqual(1, mock_finished.call_count)
        self.assertEqual('repo-1', mock_finished.call_args[0][0]['repo_id'])

    @mock.patch('pulp.server.managers.repo._common.get_working_directory',
                return_value="/var/cache/pulp/mock_worker/mock_task_id")
    def test_publish_failure_report(self, mock_get_working_directory):
        """
        Tests a publish call that indicates a graceful failure.
        """
        # Setup
        publish_config = {'foo': 'bar'}
        self.repo_manager.create_repo('repo-1')
        self.distributor_manager.add_distributor('repo-1', 'mock-distributor', publish_config,
                                                 False, distributor_id='dist-1')

        mock_plugins.MOCK_DISTRIBUTOR.publish_repo.return_value = PublishReport(
            False, 'Summary of the publish', 'Details of the publish')

        # Test
        try:
            self.publish_manager.publish('repo-1', 'dist-1', None)
            self.fail("This should have raised a PulpCodedException")
        except PulpCodedException, data_exception:
            self.assertEquals(data_exception.error_code, error_codes.PLP0034)

        # Verify
        entries = list(RepoPublishResult.get_collection().find({'repo_id': 'repo-1'}))
        self.assertEqual(1, len(entries))

        check_me = entries[0]
        self.assertEqual('repo-1', check_me['repo_id'])
        self.assertEqual('dist-1', check_me['distributor_id'])
        self.assertEqual('mock-distributor', check_me['distributor_type_id'])
        self.assertTrue(check_me['started'] is not None)
        self.assertTrue(check_me['completed'] is not None)
        self.assertEqual(RepoPublishResult.RESULT_ERROR, check_me['result'])
        self.assertTrue(check_me['error_message'] is not None)
        self.assertTrue(check_me['exception'] is not None)
        self.assertTrue(check_me['traceback'] is not None)

        # Cleanup
        mock_plugins.reset()

    @mock.patch('pulp.server.managers.repo._common.get_working_directory',
                return_value="/var/cache/pulp/mock_worker/mock_task_id")
    def test_publish_with_config_override(self, mock_get_working_directory):
        """
        Tests a publish when passing in override values.
        """

        # Setup
        distributor_config = {'key-1': 'orig-1', 'key-2': 'orig-2'}
        self.repo_manager.create_repo('repo-1')
        self.distributor_manager.add_distributor('repo-1', 'mock-distributor', distributor_config,
                                                 False, 'dist-2')

        # Test
        publish_overrides = {'key-1': 'new-1', 'key-3': 'new-3'}
        self.publish_manager.publish('repo-1', 'dist-2', publish_overrides)

        # Verify call into mock
        call_args = mock_plugins.MOCK_DISTRIBUTOR.publish_repo.call_args[0]

        self.assertEqual('repo-1', call_args[0].id)
        self.assertTrue(call_args[1] is not None)
        self.assertEqual({}, call_args[2].plugin_config)
        self.assertEqual(distributor_config, call_args[2].repo_plugin_config)
        self.assertEqual(publish_overrides, call_args[2].override_config)

    def test_publish_missing_repo(self):
        """
        Tests the proper error is raised when a non-existent repo is specified.
        """

        # Test
        try:
            self.publish_manager.publish('not-here', 'doesnt-matter', None)
            self.fail('Expected exception was not raised')
        except publish_manager.MissingResource, e:
            self.assertTrue('not-here' == e.resources['resource_id'])

    def test_publish_no_distributor(self):
        """
        Tests the proper error is raised when a non-existed distributor is specified.
        """

        # Setup
        self.repo_manager.create_repo('no-dist')

        # Test
        try:
            self.publish_manager.publish('no-dist', 'fake-dist')
            self.fail('Expected exception was not raised')
        except publish_manager.MissingResource, e:
            self.assertTrue('no-dist' == e.resources['repository'])

    def test_publish_bad_distributor(self):
        """
        Tests the proper error is raised when a distributor is set but the distributor
        is no longer present as a plugin.
        """

        # Setup
        self.repo_manager.create_repo('repo')
        self.distributor_manager.add_distributor('repo', 'mock-distributor', {}, False,
                                                 distributor_id='dist-1')

        #   Simulate bouncing the server and removing the distributor plugin
        mock_plugins.DISTRIBUTOR_MAPPINGS.pop('mock-distributor')

        # Test
        self.assertRaises(PluginNotFound, self.publish_manager.publish, 'repo', 'dist-1', None)

    def test_publish_bad_database(self):
        """
        Tests the case where the database is in a bad state and no longer has the
        repo-distributor relationship collection.
        """

        # Setup
        self.repo_manager.create_repo('repo')
        self.distributor_manager.add_distributor('repo', 'mock-distributor', {}, False,
                                                 distributor_id='dist-1')

        RepoDistributor.get_collection().remove()

        # Test
        try:
            self.publish_manager.publish('repo', 'dist-1')
            self.fail('Expected exception was not raised')
        except publish_manager.MissingResource, e:
            self.assertTrue('repo' == e.resources['repository'])

    @mock.patch('pulp.server.managers.repo._common.get_working_directory',
                return_value="/var/cache/pulp/mock_worker/mock_task_id")
    def test_publish_with_error(self, mock_get_working_directory):
        """
        Tests a publish when the plugin raises an error.
        """

        # Setup
        mock_plugins.MOCK_DISTRIBUTOR.publish_repo.side_effect = Exception()

        self.repo_manager.create_repo('gonna-bail')
        self.distributor_manager.add_distributor('gonna-bail', 'mock-distributor', {}, False,
                                                 distributor_id='bad-dist')

        self.assertRaises(Exception, self.publish_manager.publish,
                          'gonna-bail', 'bad-dist')

        # Verify
        repo_distributor = RepoDistributor.get_collection().find_one(
            {'repo_id': 'gonna-bail', 'id': 'bad-dist'})

        self.assertTrue(repo_distributor is not None)
        self.assertEqual(repo_distributor['last_publish'], None)

        entries = list(RepoPublishResult.get_collection().find({'repo_id': 'gonna-bail'}))
        self.assertEqual(1, len(entries))
        self.assertEqual('gonna-bail', entries[0]['repo_id'])
        self.assertEqual('bad-dist', entries[0]['distributor_id'])
        self.assertEqual('mock-distributor', entries[0]['distributor_type_id'])
        self.assertTrue(entries[0]['started'] is not None)
        self.assertTrue(entries[0]['completed'] is not None)
        self.assertEqual(RepoPublishResult.RESULT_ERROR, entries[0]['result'])
        self.assertTrue(entries[0]['summary'] is None)
        self.assertTrue(entries[0]['details'] is None)
        self.assertTrue(entries[0]['error_message'] is not None)
        self.assertTrue(entries[0]['exception'] is not None)
        self.assertTrue(entries[0]['traceback'] is not None)

        # Cleanup
        mock_plugins.MOCK_DISTRIBUTOR.publish_repo.side_effect = None

    def _test_auto_publish_for_repo(self):
        """
        Tests automatically publishing for a repo that has both auto and non-auto
        distributors configured.
        """

        # Setup
        self.repo_manager.create_repo('publish-me')
        self.distributor_manager.add_distributor('publish-me', 'mock-distributor', {}, True, 'auto')
        self.distributor_manager.add_distributor('publish-me', 'mock-distributor-2', {}, False,
                                                 'manual')

        # Test
        self.publish_manager.auto_publish_for_repo('publish-me')

        # Verify
        self.assertEqual(1, mock_plugins.MOCK_DISTRIBUTOR.publish_repo.call_count)
        self.assertEqual(0, mock_plugins.MOCK_DISTRIBUTOR_2.publish_repo.call_count)

    def test_auto_publish_no_repo(self):
        """
        Tests that calling auto publish on a repo that doesn't exist or one that
        doesn't have any distributors assigned will not error.
        """
        # This should not raise an Exception
        self.publish_manager.auto_publish_for_repo('non-existent')

    def test_auto_publish_with_error(self):
        """
        Tests that if one auto distributor raises an error the other is still
        invoked and the error properly conveys the results.
        """

        # Setup
        mock_plugins.MOCK_DISTRIBUTOR.publish_repo.side_effect = Exception()

        self.repo_manager.create_repo('publish-me')
        self.distributor_manager.add_distributor('publish-me', 'mock-distributor', {}, True,
                                                 'auto-1')
        self.distributor_manager.add_distributor('publish-me', 'mock-distributor-2', {}, True,
                                                 'auto-2')

        # Test
        try:
            self.publish_manager.auto_publish_for_repo('publish-me')
            self.fail('Expected exception was not raised')
        except publish_manager.PulpExecutionException:
            pass

        # Cleanup
        mock_plugins.MOCK_DISTRIBUTOR.publish_repo.side_effect = None

    @mock._patch_object(RepoDistributor, 'get_collection')
    def test_last_publish(self, get_collection):
        """
        Tests retrieving the last publish instance.
        """
        repo_id = 'repo-1'
        distributor_id = 'dist-1'
        last_publish = 1234
        collection = mock.Mock()
        collection.find_one.return_value = {'last_publish': last_publish}
        get_collection.return_value = collection

        # Test
        last = self.publish_manager.last_publish(repo_id, distributor_id)

        # Verify
        get_collection.assert_called_once_with()
        collection.find_one.assert_called_once_with({'repo_id': repo_id, 'id': distributor_id})
        self.assertEqual(last_publish, last)

    def test_last_publish_never_published(self):
        """
        Tests getting the last publish date for an unpublished repo.
        """

        # Setup
        dist = RepoDistributor('repo-1', 'dist-1', 'type-1', None, True)
        RepoDistributor.get_collection().save(dist)

        # Test
        last = self.publish_manager.last_publish('repo-1', 'dist-1')  # should not error

        # Verify
        self.assertTrue(last is None)

    def test_last_missing_distributor(self):
        """
        Tests getting last publish for a distributor that doesn't exist
        """

        # Setup
        dist = RepoDistributor('repo-1', 'dist-1', 'type-1', None, True)
        RepoDistributor.get_collection().save(dist)

        # Test
        self.assertRaises(MissingResource, self.publish_manager.last_publish, 'repo-1',
                          'random-dist')

    @mock.patch('pulp.server.managers.repo._common.get_working_directory',
                return_value="/var/cache/pulp/mock_worker/mock_task_id")
    def test_publish_no_plugin_report(self, mock_get_working_directory):
        """
        Tests publishing against a sloppy plugin that doesn't return a report.
        """

        # Setup
        self.repo_manager.create_repo('sloppy')
        self.distributor_manager.add_distributor('sloppy', 'mock-distributor', {}, True,
                                                 distributor_id='slop')

        mock_plugins.MOCK_DISTRIBUTOR.publish_repo.return_value = None

        # Test
        self.publish_manager.publish('sloppy', 'slop')

        # Verify
        entries = list(RepoPublishResult.get_collection().find({'repo_id': 'sloppy'}))
        self.assertEqual(1, len(entries))
        self.assertEqual('Unknown', entries[0]['summary'])
        self.assertEqual('Unknown', entries[0]['details'])

    def test_publish_history(self):
        """
        Tests getting the history of publishes on a repo.
        """

        # Setup
        self.repo_manager.create_repo('foo')
        self.distributor_manager.add_distributor('foo', 'mock-distributor', {}, True,
                                                 distributor_id='dist-1')
        for i in range(1, 9):
            add_result('foo', 'dist-1', i)

        # Test
        entries = self.publish_manager.publish_history('foo', 'dist-1')

        # Verify 8 entries were returned and that the sort direction is descending
        self.assertEqual(8, len(entries))
        for entry in entries:
            first = dateutils.parse_iso8601_datetime(entry['started'])
            second = dateutils.parse_iso8601_datetime(entry['started'])
            self.assertTrue(first >= second)

    def test_publish_history_with_limit(self):
        """
        Tests using the limit to retrieve only a subset of the history.
        """

        # Setup
        self.repo_manager.create_repo('dragon')
        self.distributor_manager.add_distributor('dragon', 'mock-distributor', {}, True,
                                                 distributor_id='fire')
        for i in range(0, 10):
            add_result('dragon', 'fire', i)

        # Test a valid limit
        entries = self.publish_manager.publish_history('dragon', 'fire', limit=3)
        self.assertEqual(3, len(entries))
        for entry in entries:
            first = dateutils.parse_iso8601_datetime(entry['started'])
            second = dateutils.parse_iso8601_datetime(entry['started'])
            self.assertTrue(first >= second)

    def test_publish_history_invalid_limit(self):
        """
        Tests that limit is checked for invalid values
        """

        # Setup
        self.repo_manager.create_repo('test_repo')
        self.distributor_manager.add_distributor('test_repo', 'mock-distributor', {}, True,
                                                 distributor_id='dist')

        # Verify an invalid limit raises an InvalidValue exception
        self.assertRaises(InvalidValue, self.publish_manager.publish_history, 'test_repo', 'dist',
                          limit=0)
        # Verify a non-int still raises an InvalidValue exception
        self.assertRaises(InvalidValue, self.publish_manager.publish_history, 'test_repo', 'dist',
                          limit='bacon')

    def test_publish_history_ascending_sort(self):
        """
        Tests use the sort parameter to sort the results in ascending order by start time
        """

        # Setup
        self.repo_manager.create_repo('test_sort')
        self.distributor_manager.add_distributor('test_sort', 'mock-distributor', {}, True,
                                                 distributor_id='test_dist')
        # Create some consecutive publish entries
        date_string = '2013-06-01T12:00:0%sZ'
        for i in range(0, 10, 2):
            r = RepoPublishResult.expected_result(
                'test_sort', 'test_dist', 'bar', {}, date_string % str(i), date_string % str(i + 1),
                'test-summary', 'test-details', RepoPublishResult.RESULT_SUCCESS)
            RepoPublishResult.get_collection().insert(r, safe=True)

        # Test that returned entries are in ascending order by time
        entries = self.publish_manager.publish_history('test_sort', 'test_dist',
                                                       sort=constants.SORT_ASCENDING)
        self.assertEqual(5, len(entries))
        for i in range(0, 4):
            first = dateutils.parse_iso8601_datetime(entries[i]['started'])
            second = dateutils.parse_iso8601_datetime(entries[i + 1]['started'])
            self.assertTrue(first < second)

    def test_publish_history_descending_sort(self):
        """
        Tests use the sort parameter to sort the results in descending order by start time
        """

        # Setup
        self.repo_manager.create_repo('test_sort')
        self.distributor_manager.add_distributor('test_sort', 'mock-distributor', {}, True,
                                                 distributor_id='test_dist')
        # Create some consecutive publish entries
        date_string = '2013-06-01T12:00:0%sZ'
        for i in range(0, 10, 2):
            r = RepoPublishResult.expected_result(
                'test_sort', 'test_dist', 'bar', {}, date_string % str(i), date_string % str(i + 1),
                'test-summary', 'test-details', RepoPublishResult.RESULT_SUCCESS)
            RepoPublishResult.get_collection().insert(r, safe=True)

        # Test that returned entries are in descending order by time
        entries = self.publish_manager.publish_history('test_sort', 'test_dist',
                                                       sort=constants.SORT_DESCENDING)
        self.assertEqual(5, len(entries))
        for i in range(0, 4):
            first = dateutils.parse_iso8601_datetime(entries[i]['started'])
            second = dateutils.parse_iso8601_datetime(entries[i + 1]['started'])
            self.assertTrue(first > second)

    def test_publish_history_invalid_sort(self):
        """
        Tests that publish_history checks the sort parameter for invalid values
        """
        self.repo_manager.create_repo('test_sort')
        self.distributor_manager.add_distributor('test_sort', 'mock-distributor', {}, True,
                                                 distributor_id='test_dist')

        # Test that an exception is raised if sort gets an invalid value
        self.assertRaises(InvalidValue, self.publish_manager.publish_history, 'test_sort',
                          'test_dist', sort='random')

    def test_publish_history_start_date(self):

        # Setup
        self.repo_manager.create_repo('test_date')
        self.distributor_manager.add_distributor('test_date', 'mock-distributor', {}, True,
                                                 distributor_id='test_dist')
        # Create three consecutive publish entries
        date_string = '2013-06-01T12:00:0%sZ'
        for i in range(0, 6, 2):
            r = RepoPublishResult.expected_result(
                'test_date', 'test_dist', 'bar', {}, date_string % str(i), date_string % str(i + 1),
                'test-summary', 'test-details', RepoPublishResult.RESULT_SUCCESS)
            RepoPublishResult.get_collection().insert(r, safe=True)

        # Verify
        self.assertEqual(3, len(self.publish_manager.publish_history('test_date', 'test_dist')))
        start_date = '2013-06-01T12:00:02Z'
        start_entries = self.publish_manager.publish_history('test_date', 'test_dist',
                                                             start_date=start_date)
        # Confirm the dates of the retrieved entries are later than or equal to the requested date
        self.assertEqual(2, len(start_entries))
        for entries in start_entries:
            retrieved = dateutils.parse_iso8601_datetime(entries['started'])
            given_start = dateutils.parse_iso8601_datetime(start_date)
            self.assertTrue(retrieved >= given_start)

    def test_publish_history_end_date(self):

        # Setup
        self.repo_manager.create_repo('test_date')
        self.distributor_manager.add_distributor('test_date', 'mock-distributor', {}, True,
                                                 distributor_id='test_dist')
        # Create three consecutive publish entries
        date_string = '2013-06-01T12:00:0%sZ'
        for i in range(0, 6, 2):
            r = RepoPublishResult.expected_result(
                'test_date', 'test_dist', 'bar', {}, date_string % str(i), date_string % str(i + 1),
                'test-summary', 'test-details', RepoPublishResult.RESULT_SUCCESS)
            RepoPublishResult.get_collection().insert(r, safe=True)

        # Verify that all entries retrieved have dates prior to the given end date
        end_date = '2013-06-01T12:00:03Z'
        end_entries = self.publish_manager.publish_history('test_date', 'test_dist',
                                                           end_date=end_date)
        # Confirm the dates of the retrieved entries are earlier than or equal to the requested date
        self.assertEqual(2, len(end_entries))
        for entries in end_entries:
            retrieved = dateutils.parse_iso8601_datetime(entries['started'])
            given_end = dateutils.parse_iso8601_datetime(end_date)
            self.assertTrue(retrieved <= given_end)

    def test_publish_history_invalid_date(self):

        # Setup
        self.repo_manager.create_repo('test_date')
        self.distributor_manager.add_distributor('test_date', 'mock-distributor', {}, True,
                                                 distributor_id='test_dist')
        for i in range(1, 5):
            add_result('test_date', 'test_dist', i)

        # Verify exceptions are raised when malformed dates are given
        self.assertRaises(InvalidValue, self.publish_manager.publish_history, 'test_date',
                          'test_dist', start_date='2013-56-01T12:00:02Z')
        self.assertRaises(InvalidValue, self.publish_manager.publish_history, 'test_date',
                          'test_dist', end_date='2013-56-01T12:00:02Z')

    def test_publish_history_missing_repo(self):
        """
        Tests the correct error is raised when getting history for a repo that doesn't exist.
        """
        self.assertRaises(publish_manager.MissingResource, self.publish_manager.publish_history,
                          'missing', 'irrelevant')

    def test_publish_history_distributor_config(self):
        """
        Test there's distributor config included in publish history
        """
        self.repo_manager.create_repo('test_repo')
        self.distributor_manager.add_distributor('test_repo', 'mock-distributor',
                                                 {"foo": "bar"},
                                                 True, distributor_id='test_dist')

        original = RepoPublishResult.expected_result
        _call = 'pulp.server.db.model.repository.RepoPublishResult.expected_result'
        with mock.patch(_call) as call:
            call.expected_result.side_effect = original
            call.return_value = {"id":1}#original_call
            add_result('test_repo', 'test_dist', 1, dist_config={"foo": "bar"})
            self.assertTrue(call.call_args[0][3] == {"foo": "bar"})

        original = RepoPublishResult.error_result
        _call = 'pulp.server.db.model.repository.RepoPublishResult.error_result'
        with mock.patch(_call, ) as call:
            call.expected_result.side_effect = original
            call.return_value = {"id":2}#original_call
            add_result('test_repo', 'test_dist', 2, dist_config={"foo": "bar"},
                       sucess=False)
            self.assertTrue(call.call_args[0][3] == {"foo": "bar"})

        # Setup
        #self.repo_manager.create_repo('test_repo')
        #self.distributor_manager.add_distributor('test_repo', 'mock-distributor', {},
        #                                         True, distributor_id='test_dist')
        entries = self.publish_manager.publish_history('test_repo', 'test_dist')
        self.assertTrue(len(entries) == 0)
        add_result('test_repo', 'test_dist', 1)
        entry = self.publish_manager.publish_history('test_repo', 'test_dist')[0]
        self.assertTrue("distributor_config" in entry, entry)
        distributor_config = entry["distributor_config"]
        self.assertTrue(distributor_config == {})

        self.repo_manager.delete_repo('test_repo')
        self.repo_manager.create_repo('test_repo')
        self.distributor_manager.add_distributor('test_repo', 'mock-distributor',
                                                 {"foo": "bar"}, True,
                                                 distributor_id='test_dist')
        add_result('test_repo', 'test_dist', 1, dist_config={"foo": "bar"})
        entry = self.publish_manager.publish_history('test_repo', 'test_dist')[0]
        distributor_config = entry["distributor_config"]
        self.assertTrue(distributor_config == {"foo": "bar"}, distributor_config)

        self.repo_manager.delete_repo('test_repo')
        self.repo_manager.create_repo('test_repo')
        self.distributor_manager.add_distributor('test_repo', 'mock-distributor',
                                                 {"foo": "bar"}, True,
                                                 distributor_id='test_dist')
        #add_result('test_repo', 'test_dist', 1)
        #self.distributor_manager.remove_distributor("test_repo", "test_dist")
        #entry = self.publish_manager.publish_history('test_repo', 'test_dist')[0]
        #distributor_config = entry["distributor_config"]
        #self.assertTrue(distributor_config == {"foo": "bar"})

    def _test_auto_distributors(self):
        """
        Tests that the query for distributors on a repo that are configured for automatic
        distribution is correct.
        """

        # Setup
        dist_coll = RepoDistributor.get_collection()

        dist_coll.save(RepoDistributor('repo-1', 'dist-1', 'type', {}, True))
        dist_coll.save(RepoDistributor('repo-1', 'dist-2', 'type', {}, True))
        dist_coll.save(RepoDistributor('repo-1', 'dist-3', 'type', {}, False))
        dist_coll.save(RepoDistributor('repo-2', 'dist-1', 'type', {}, True))
        dist_coll.save(RepoDistributor('repo-2', 'dist-2', 'type', {}, False))

        # Test
        repo1_dists = publish_manager._auto_distributors('repo-1')
        repo2_dists = publish_manager._auto_distributors('repo-2')
        repo3_dists = publish_manager._auto_distributors('repo-3')

        # Verify
        self.assertEqual(2, len(repo1_dists))
        repo1_dist_ids = [d['id'] for d in repo1_dists]
        self.assertTrue('dist-1' in repo1_dist_ids)
        self.assertTrue('dist-2' in repo1_dist_ids)

        self.assertEqual(1, len(repo2_dists))
        repo2_dist_ids = [d['id'] for d in repo2_dists]
        self.assertTrue('dist-1' in repo2_dist_ids)

        self.assertEqual(0, len(repo3_dists))


class TestDoPublish(base.PulpServerTests):
    """
    Assert correct behavior from the _do_publish() method.
    """
    def setUp(self):
        super(TestDoPublish, self).setUp()
        mock_plugins.install()
        self.repo_manager = repo_manager.RepoManager()
        self.distributor_manager = distributor_manager.RepoDistributorManager()
        self.publish_manager = publish_manager.RepoPublishManager()

    def tearDown(self):
        super(TestDoPublish, self).tearDown()
        mock_plugins.reset()
        Repo.get_collection().remove()
        RepoDistributor.get_collection().remove()
        RepoPublishResult.get_collection().remove()

    @mock.patch('pulp.server.managers.repo.publish.register_sigterm_handler',
                side_effect=tasks.register_sigterm_handler)
    def test_wraps_publish_in_register_sigterm_handler(self, register_sigterm_handler):
        """
        Assert that the distributor's publish_repo() method is wrapped by
        pulp.server.async.tasks.register_sigterm_handler.
        """
        def publish_repo(self, *args, **kwargs):
            """
            This method will be attached to the distributor_instance, and will allow us to assert
            that the register_sigterm_handler is called before the publish_repo is called. We can
            tell because inside here the SIGTERM handler has been altered.
            """
            signal_handler = signal.getsignal(signal.SIGTERM)
            self.assertNotEqual(signal_handler, starting_term_handler)

            # Make sure that the signal handler is the distributor's cancel method
            self.assertEqual(distributor_instance.cancel_publish_repo.call_count, 0)
            signal_handler(signal.SIGTERM, None)
            self.assertEqual(distributor_instance.cancel_publish_repo.call_count, 1)

        publish_config = {'foo': 'bar'}
        distributor_id = 'dist-1'
        repo_id = 'repo-1'
        repo = self.repo_manager.create_repo(repo_id)
        self.distributor_manager.add_distributor(repo_id, 'mock-distributor', publish_config, False,
                                                 distributor_id=distributor_id)
        distributor_instance, distributor_config = \
            publish_manager.RepoPublishManager._get_distributor_instance_and_config(repo_id,
                                                                                    distributor_id)
        # Set our special publish_repo() from above to the instance so we can make our assertions
        distributor_instance.publish_repo = publish_repo
        transfer_repo = mock.MagicMock()
        conduit = mock.MagicMock()
        call_config = mock.MagicMock()
        call_config.flatten.return_value = {}
        starting_term_handler = signal.getsignal(signal.SIGTERM)

        publish_manager.RepoPublishManager._do_publish(repo, distributor_id, distributor_instance,
                                                       transfer_repo, conduit, call_config)

        register_sigterm_handler.assert_called_once_with(
            publish_repo, distributor_instance.cancel_publish_repo)
        # Make sure the TERM handler is set back to normal
        self.assertEqual(signal.getsignal(signal.SIGTERM), starting_term_handler)


def assert_last_sync_time(time_in_iso):
    now = dateutils.now_utc_datetime_with_tzinfo()
    finished = dateutils.parse_iso8601_datetime(time_in_iso)

    # Compare them within a threshold since they won't be exact
    difference = now - finished
    return difference.seconds < 2


def add_result(repo_id, dist_id, offset, sucess=True, dist_config={}):
    started = dateutils.now_utc_datetime_with_tzinfo()
    completed = started + datetime.timedelta(days=offset)
    if sucess:
        r = RepoPublishResult.expected_result(
            repo_id, dist_id, 'bar', dist_config, dateutils.format_iso8601_datetime(started),
            dateutils.format_iso8601_datetime(completed), 'test-summary', 'test-details',
            RepoPublishResult.RESULT_SUCCESS)
    else:
        r = RepoPublishResult.error_result(
            repo_id, dist_id, 'bar', dist_config, dateutils.format_iso8601_datetime(started),
            dateutils.format_iso8601_datetime(completed), [],
            RepoPublishResult.RESULT_ERROR)

    RepoPublishResult.get_collection().insert([r], safe=True)
