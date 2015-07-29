#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import sys

import pulp.devel.test_runner
from pulp.devel.test_runner import run_tests
print pulp.devel.test_runner.__file__

# Find and eradicate any existing .pyc files, so they do not eradicate us!
PROJECT_DIR = os.path.dirname(__file__)
subprocess.call(['find', PROJECT_DIR, '-name', '*.pyc', '-delete'])

# These paths should all pass PEP-8 checks
paths_to_check = [
    'agent',
    'bindings/pulp/bindings/actions.py',
    'bindings/pulp/bindings/consumer.py',
    'bindings/pulp/bindings/exceptions.py',
    'bindings/pulp/bindings/repo_groups.py',
    'bindings/pulp/bindings/repository.py',
    'bindings/pulp/bindings/responses.py',
    'bindings/pulp/bindings/search.py',
    'bindings/pulp/bindings/server.py',
    'bindings/pulp/bindings/tasks.py',
    'bindings/pulp/bindings/upload.py',
    'bindings/test/unit/test_consumer.py',
    'bindings/test/unit/test_repo_groups.py',
    'bindings/test/unit/test_repository.py',
    'bindings/test/unit/test_responses.py',
    'bindings/test/unit/test_search.py',
    'bindings/test/unit/test_server.py',
    'bindings/test/unit/test_tasks.py',
    'bindings/test/unit/test_upload.py',
    'client_lib/pulp/',
    'repoauth/',
    'server/pulp/plugins',
    'server/pulp/server/agent/',
    'server/pulp/server/async/',
    'server/pulp/server/auth/',
    'server/pulp/server/content/',
    'server/pulp/server/db/',
    'server/pulp/server/event/',
    'server/pulp/server/maintenance/',
    'server/pulp/server/managers',
    'server/pulp/server/tasks/',
    'server/pulp/server/webservices/middleware/',
    'server/pulp/server/webservices/views/',
    'server/test/unit/plugins/',
    'server/test/unit/server/']

os.environ['DJANGO_SETTINGS_MODULE'] = 'pulp.server.webservices.settings'

PACKAGES = [
    os.path.abspath(os.path.dirname(__file__)),
    os.path.abspath(os.path.join('.', 'pulp')),
    os.path.abspath(os.path.join('.', 'pulp_node')),
]


TESTS_ALL_PLATFORMS = [
    os.path.abspath(os.path.join('.','agent/test/unit')),
    os.path.abspath(os.path.join('.','bindings/test/unit')),
    os.path.abspath(os.path.join('.','client_consumer/test/unit')),
    os.path.abspath(os.path.join('.','client_lib/test/unit')),
    os.path.abspath(os.path.join('.','common/test/unit'))
]

TESTS_NON_RHEL5 = [
    os.path.abspath(os.path.join('.','client_admin/test/unit')),
    os.path.abspath(os.path.join('.','nodes/test/unit')),
    os.path.abspath(os.path.join('.','server/test/unit')),
    os.path.abspath(os.path.join('.','repoauth/test')),
    os.path.abspath(os.path.join('.','devel/test/unit'))
]

dir_safe_all_platforms = [os.path.join(os.path.dirname(__file__), x) for x in TESTS_ALL_PLATFORMS]
dir_safe_non_rhel5 = [os.path.join(os.path.dirname(__file__), x) for x in TESTS_NON_RHEL5]

test_dir = os.path.abspath(os.path.dirname(__file__))
abspaths_to_check = []

for p in paths_to_check:
    abspaths_to_check.append(os.path.join(test_dir, p))

tests_exit_code = run_tests(PACKAGES, dir_safe_all_platforms, dir_safe_non_rhel5,
                            flake8_paths=abspaths_to_check)

sys.exit(tests_exit_code)
