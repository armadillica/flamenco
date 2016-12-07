# -*- encoding: utf-8 -*-

import unittest

import responses
from bson import ObjectId

import pillarsdk
import pillarsdk.exceptions as sdk_exceptions
import pillar.tests
import pillar.auth
import pillar.tests.common_test_data as ctd

from abstract_flamenco_test import AbstractFlamencoTest


class AbstractJobTest(AbstractFlamencoTest):
    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)
        self.tmngr = self.flamenco.job_manager

        self.proj_id, self.project = self.ensure_project_exists()

        self.sdk_project = pillarsdk.Project(pillar.tests.mongo_to_sdk(self.project))

    def create_job(self):
        with self.app.test_request_context():
            # Log in as project admin user
            pillar.auth.login_user(ctd.EXAMPLE_PROJECT_OWNER_ID)

            self.mock_blenderid_validate_happy()
            task = self.tmngr.create_job(self.sdk_project)

        self.assertIsInstance(task, pillarsdk.Node)
        return task


class JobManagerTest(AbstractJobTest):
    @responses.activate
    def test_job(self):
        return
