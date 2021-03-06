# -*- coding: utf-8 -*-
"""
Tests for /api/v2/users subpath endpoints.
"""
from time import sleep

import pytest
import requests
import transaction

from tracim_backend import error
from tracim_backend import models
from tracim_backend.app_models.contents import content_type_list
from tracim_backend.extensions import app_list
from tracim_backend.fixtures.content import Content as ContentFixtures
from tracim_backend.fixtures.users_and_groups import Base as BaseFixture
from tracim_backend.lib.core.application import ApplicationApi
from tracim_backend.lib.core.content import ContentApi
from tracim_backend.lib.core.group import GroupApi
from tracim_backend.lib.core.user import UserApi
from tracim_backend.lib.core.userworkspace import RoleApi
from tracim_backend.lib.core.workspace import WorkspaceApi
from tracim_backend.models import get_tm_session
from tracim_backend.models.data import UserRoleInWorkspace
from tracim_backend.models.revision_protection import new_revision
from tracim_backend.tests import FunctionalTest


class TestAccountRecentlyActiveContentEndpoint(FunctionalTest):
    """
    Tests for /api/v2/users/{user_id}/workspaces/{workspace_id}/contents/recently_active # nopep8
    """
    fixtures = [BaseFixture]

    def test_api__get_recently_active_content__ok__200__nominal(self):

        # init DB
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        workspace_api = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config

        )
        workspace = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        ).create_workspace(
            'test workspace',
            save_now=True
        )
        workspace2 = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        ).create_workspace(
            'test workspace2',
            save_now=True
        )

        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        rapi = RoleApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        rapi.create_one(test_user, workspace, UserRoleInWorkspace.READER, False)
        api = ContentApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        main_folder_workspace2 = api.create(content_type_list.Folder.slug, workspace2, None, 'Hepla', '', True)  # nopep8
        main_folder = api.create(content_type_list.Folder.slug, workspace, None, 'this is randomized folder', '', True)  # nopep8
        # creation order test
        firstly_created = api.create(content_type_list.Page.slug, workspace, main_folder, 'creation_order_test', '', True)  # nopep8
        secondly_created = api.create(content_type_list.Page.slug, workspace, main_folder, 'another creation_order_test', '', True)  # nopep8
        # update order test
        firstly_created_but_recently_updated = api.create(content_type_list.Page.slug, workspace, main_folder, 'update_order_test', '', True)  # nopep8
        secondly_created_but_not_updated = api.create(content_type_list.Page.slug, workspace, main_folder, 'another update_order_test', '', True)  # nopep8
        with new_revision(
            session=dbsession,
            tm=transaction.manager,
            content=firstly_created_but_recently_updated,
        ):
            firstly_created_but_recently_updated.description = 'Just an update'
        api.save(firstly_created_but_recently_updated)
        # comment change order
        firstly_created_but_recently_commented = api.create(content_type_list.Page.slug, workspace, main_folder, 'this is randomized label content', '', True)  # nopep8
        secondly_created_but_not_commented = api.create(content_type_list.Page.slug, workspace, main_folder, 'this is another randomized label content', '', True)  # nopep8
        comments = api.create_comment(workspace, firstly_created_but_recently_commented, 'juste a super comment', True)  # nopep8
        content_workspace_2 = api.create(content_type_list.Page.slug, workspace2, main_folder_workspace2, 'content_workspace_2', '', True)  # nopep8
        dbsession.flush()
        transaction.commit()

        self.testapp.authorization = (
            'Basic',
            (
                'test@test.test',
                'password'
            )
        )
        res = self.testapp.get('/api/v2/users/me/workspaces/{workspace_id}/contents/recently_active'.format(   # nopep8
            workspace_id=workspace.workspace_id
        ), status=200)
        res = res.json_body
        assert len(res) == 7
        for elem in res:
            assert isinstance(elem['content_id'], int)
            assert isinstance(elem['content_type'], str)
            assert elem['content_type'] != 'comments'
            assert isinstance(elem['is_archived'], bool)
            assert isinstance(elem['is_deleted'], bool)
            assert isinstance(elem['label'], str)
            assert isinstance(elem['parent_id'], int) or elem['parent_id'] is None
            assert isinstance(elem['show_in_ui'], bool)
            assert isinstance(elem['slug'], str)
            assert isinstance(elem['status'], str)
            assert isinstance(elem['sub_content_types'], list)
            for sub_content_type in elem['sub_content_types']:
                assert isinstance(sub_content_type, str)
            assert isinstance(elem['workspace_id'], int)
        # comment is newest than page2
        assert res[0]['content_id'] == firstly_created_but_recently_commented.content_id
        assert res[1]['content_id'] == secondly_created_but_not_commented.content_id
        # last updated content is newer than other one despite creation
        # of the other is more recent
        assert res[2]['content_id'] == firstly_created_but_recently_updated.content_id
        assert res[3]['content_id'] == secondly_created_but_not_updated.content_id
        # creation order is inverted here as last created is last active
        assert res[4]['content_id'] == secondly_created.content_id
        assert res[5]['content_id'] == firstly_created.content_id
        # folder subcontent modification does not change folder order
        assert res[6]['content_id'] == main_folder.content_id

    def test_api__get_recently_active_content__ok__200__limit_2_multiple(self):
        # TODO - G.M - 2018-07-20 - Better fix for this test, do not use sleep()
        # anymore to fix datetime lack of precision.

        # init DB
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        workspace_api = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config

        )
        workspace = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        ).create_workspace(
            'test workspace',
            save_now=True
        )
        workspace2 = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        ).create_workspace(
            'test workspace2',
            save_now=True
        )

        api = ContentApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        main_folder_workspace2 = api.create(content_type_list.Folder.slug, workspace2, None, 'Hepla', '', True)  # nopep8
        main_folder = api.create(content_type_list.Folder.slug, workspace, None, 'this is randomized folder', '', True)  # nopep8
        # creation order test
        firstly_created = api.create(content_type_list.Page.slug, workspace, main_folder, 'creation_order_test', '', True)  # nopep8
        secondly_created = api.create(content_type_list.Page.slug, workspace, main_folder, 'another creation_order_test', '', True)  # nopep8
        # update order test
        firstly_created_but_recently_updated = api.create(content_type_list.Page.slug, workspace, main_folder, 'update_order_test', '', True)  # nopep8
        secondly_created_but_not_updated = api.create(content_type_list.Page.slug, workspace, main_folder, 'another update_order_test', '', True)  # nopep8
        with new_revision(
            session=dbsession,
            tm=transaction.manager,
            content=firstly_created_but_recently_updated,
        ):
            firstly_created_but_recently_updated.description = 'Just an update'
        api.save(firstly_created_but_recently_updated)
        # comment change order
        firstly_created_but_recently_commented = api.create(content_type_list.Page.slug, workspace, main_folder, 'this is randomized label content', '', True)  # nopep8
        secondly_created_but_not_commented = api.create(content_type_list.Page.slug, workspace, main_folder, 'this is another randomized label content', '', True)  # nopep8
        comments = api.create_comment(workspace, firstly_created_but_recently_commented, 'juste a super comment', True)  # nopep8
        content_workspace_2 = api.create(content_type_list.Page.slug, workspace2, main_folder_workspace2, 'content_workspace_2', '', True)  # nopep8
        dbsession.flush()
        transaction.commit()

        self.testapp.authorization = (
            'Basic',
            (
                'admin@admin.admin',
                'admin@admin.admin'
            )
        )
        params = {
            'limit': 2,
        }
        res = self.testapp.get(
            '/api/v2/users/me/workspaces/{}/contents/recently_active'.format(workspace.workspace_id),  # nopep8
            status=200,
            params=params
        ) # nopep8
        res = res.json_body
        assert len(res) == 2
        for elem in res:
            assert isinstance(elem['content_id'], int)
            assert isinstance(elem['content_type'], str)
            assert elem['content_type'] != 'comments'
            assert isinstance(elem['is_archived'], bool)
            assert isinstance(elem['is_deleted'], bool)
            assert isinstance(elem['label'], str)
            assert isinstance(elem['parent_id'], int) or elem['parent_id'] is None
            assert isinstance(elem['show_in_ui'], bool)
            assert isinstance(elem['slug'], str)
            assert isinstance(elem['status'], str)
            assert isinstance(elem['sub_content_types'], list)
            for sub_content_type in elem['sub_content_types']:
                assert isinstance(sub_content_type, str)
            assert isinstance(elem['workspace_id'], int)
        # comment is newest than page2
        assert res[0]['content_id'] == firstly_created_but_recently_commented.content_id
        assert res[1]['content_id'] == secondly_created_but_not_commented.content_id

        params = {
            'limit': 2,
            'before_content_id': secondly_created_but_not_commented.content_id,  # nopep8
        }
        res = self.testapp.get(
            '/api/v2/users/me/workspaces/{}/contents/recently_active'.format(workspace.workspace_id),  # nopep8
            status=200,
            params=params
        )
        res = res.json_body
        assert len(res) == 2
        # last updated content is newer than other one despite creation
        # of the other is more recent
        assert res[0]['content_id'] == firstly_created_but_recently_updated.content_id
        assert res[1]['content_id'] == secondly_created_but_not_updated.content_id

    def test_api__get_recently_active_content__err__400__bad_before_content_id(self):  # nopep8
        # TODO - G.M - 2018-07-20 - Better fix for this test, do not use sleep()
        # anymore to fix datetime lack of precision.

        # init DB
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        workspace_api = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config

        )
        workspace = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        ).create_workspace(
            'test workspace',
            save_now=True
        )
        workspace2 = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        ).create_workspace(
            'test workspace2',
            save_now=True
        )

        api = ContentApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        main_folder_workspace2 = api.create(content_type_list.Folder.slug, workspace2, None, 'Hepla', '', True)  # nopep8
        main_folder = api.create(content_type_list.Folder.slug, workspace, None, 'this is randomized folder', '', True)  # nopep8
        # creation order test
        firstly_created = api.create(content_type_list.Page.slug, workspace, main_folder, 'creation_order_test', '', True)  # nopep8
        secondly_created = api.create(content_type_list.Page.slug, workspace, main_folder, 'another creation_order_test', '', True)  # nopep8
        # update order test
        firstly_created_but_recently_updated = api.create(content_type_list.Page.slug, workspace, main_folder, 'update_order_test', '', True)  # nopep8
        secondly_created_but_not_updated = api.create(content_type_list.Page.slug, workspace, main_folder, 'another update_order_test', '', True)  # nopep8
        with new_revision(
            session=dbsession,
            tm=transaction.manager,
            content=firstly_created_but_recently_updated,
        ):
            firstly_created_but_recently_updated.description = 'Just an update'
        api.save(firstly_created_but_recently_updated)
        # comment change order
        firstly_created_but_recently_commented = api.create(content_type_list.Page.slug, workspace, main_folder, 'this is randomized label content', '', True)  # nopep8
        secondly_created_but_not_commented = api.create(content_type_list.Page.slug, workspace, main_folder, 'this is another randomized label content', '', True)  # nopep8
        comments = api.create_comment(workspace, firstly_created_but_recently_commented, 'juste a super comment', True)  # nopep8
        content_workspace_2 = api.create(content_type_list.Page.slug, workspace2, main_folder_workspace2, 'content_workspace_2', '', True)  # nopep8
        dbsession.flush()
        transaction.commit()

        self.testapp.authorization = (
            'Basic',
            (
                'admin@admin.admin',
                'admin@admin.admin'
            )
        )
        params = {
            'before_content_id': 4000
        }
        res = self.testapp.get(
            '/api/v2/users/me/workspaces/{}/contents/recently_active'.format(workspace.workspace_id),  # nopep8
            status=400,
            params=params
        )
        assert isinstance(res.json, dict)
        assert 'code' in res.json.keys()
        assert res.json_body['code'] == error.CONTENT_NOT_FOUND


class TestUserReadStatusEndpoint(FunctionalTest):
    """
    Tests for /api/v2/users/{user_id}/workspaces/{workspace_id}/contents/read_status # nopep8
    """
    def test_api__get_read_status__ok__200__nominal(self):

        # init DB
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        workspace_api = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config

        )
        workspace = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        ).create_workspace(
            'test workspace',
            save_now=True
        )
        workspace2 = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        ).create_workspace(
            'test workspace2',
            save_now=True
        )
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        rapi = RoleApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        rapi.create_one(test_user, workspace, UserRoleInWorkspace.READER, False)
        api = ContentApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        main_folder_workspace2 = api.create(content_type_list.Folder.slug, workspace2, None, 'Hepla', '', True)  # nopep8
        main_folder = api.create(content_type_list.Folder.slug, workspace, None, 'this is randomized folder', '', True)  # nopep8
        # creation order test
        firstly_created = api.create(content_type_list.Page.slug, workspace, main_folder, 'creation_order_test', '', True)  # nopep8
        secondly_created = api.create(content_type_list.Page.slug, workspace, main_folder, 'another creation_order_test', '', True)  # nopep8
        # update order test
        firstly_created_but_recently_updated = api.create(content_type_list.Page.slug, workspace, main_folder, 'update_order_test', '', True)  # nopep8
        secondly_created_but_not_updated = api.create(content_type_list.Page.slug, workspace, main_folder, 'another update_order_test', '', True)  # nopep8
        with new_revision(
            session=dbsession,
            tm=transaction.manager,
            content=firstly_created_but_recently_updated,
        ):
            firstly_created_but_recently_updated.description = 'Just an update'
        api.save(firstly_created_but_recently_updated)
        # comment change order
        firstly_created_but_recently_commented = api.create(content_type_list.Page.slug, workspace, main_folder, 'this is randomized label content', '', True)  # nopep8
        secondly_created_but_not_commented = api.create(content_type_list.Page.slug, workspace, main_folder, 'this is another randomized label content', '', True)  # nopep8
        comments = api.create_comment(workspace, firstly_created_but_recently_commented, 'juste a super comment', True)  # nopep8
        content_workspace_2 = api.create(content_type_list.Page.slug, workspace2, main_folder_workspace2, 'content_workspace_2', '', True)  # nopep8
        dbsession.flush()
        transaction.commit()

        self.testapp.authorization = (
            'Basic',
            (
                'test@test.test',
                'password'
            )
        )
        selected_contents_id = [
            firstly_created_but_recently_commented.content_id,
            firstly_created_but_recently_updated.content_id,
            firstly_created.content_id,
            main_folder.content_id,
        ]
        params = {
            'content_ids': '{cid1},{cid2},{cid3},{cid4}'.format(
                    cid1=selected_contents_id[0],
                    cid2=selected_contents_id[1],
                    cid3=selected_contents_id[2],
                    cid4=selected_contents_id[3],
            )
        }
        url = '/api/v2/users/me/workspaces/{workspace_id}/contents/read_status'.format(  # nopep8
              workspace_id=workspace.workspace_id,
        )
        res = self.testapp.get(
            url=url,
            status=200,
            params=params
        )
        res = res.json_body
        assert len(res) == 4
        for elem in res:
            assert isinstance(elem['content_id'], int)
            assert isinstance(elem['read_by_user'], bool)
        # comment is newest than page2
        assert res[0]['content_id'] == firstly_created_but_recently_commented.content_id
        # last updated content is newer than other one despite creation
        # of the other is more recent
        assert res[1]['content_id'] == firstly_created_but_recently_updated.content_id
        # creation order is inverted here as last created is last active
        assert res[2]['content_id'] == firstly_created.content_id
        # folder subcontent modification does not change folder order
        assert res[3]['content_id'] == main_folder.content_id


class TestUserSetContentAsRead(FunctionalTest):
    """
    Tests for /api/v2/users/me/workspaces/{workspace_id}/contents/{content_id}/read  # nopep8
    """

    def test_api_set_content_as_read__ok__200__nominal(self):
        # init DB
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        workspace_api = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config

        )
        workspace = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        ).create_workspace(
            'test workspace',
            save_now=True
        )
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        rapi = RoleApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        rapi.create_one(test_user, workspace, UserRoleInWorkspace.READER, False)
        api = ContentApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        api2 = ContentApi(
            current_user=test_user,
            session=dbsession,
            config=self.app_config,
        )
        main_folder = api.create(content_type_list.Folder.slug, workspace, None, 'this is randomized folder', '', True)  # nopep8
        # creation order test
        firstly_created = api.create(content_type_list.Page.slug, workspace, main_folder, 'creation_order_test', '', True)  # nopep8
        api.mark_unread(firstly_created)
        api2.mark_unread(firstly_created)
        dbsession.flush()
        transaction.commit()

        self.testapp.authorization = (
            'Basic',
            (
                'test@test.test',
                'password'
            )
        )
        # before
        res = self.testapp.get('/api/v2/users/{user_id}/workspaces/{workspace_id}/contents/read_status'.format(  # nopep8
            user_id=test_user.user_id,
            workspace_id=workspace.workspace_id
            ),
            status=200
        )
        assert res.json_body[0]['content_id'] == firstly_created.content_id
        assert res.json_body[0]['read_by_user'] is False

        # read
        self.testapp.put(
            '/api/v2/users/{user_id}/workspaces/{workspace_id}/contents/{content_id}/read'.format(  # nopep8
                workspace_id=workspace.workspace_id,
                content_id=firstly_created.content_id,
                user_id=test_user.user_id,
            )
        )
        # after
        res = self.testapp.get('/api/v2/users/{user_id}/workspaces/{workspace_id}/contents/read_status'.format(  # nopep8
            user_id=test_user.user_id,
            workspace_id=workspace.workspace_id
            ),
            status=200
        )
        assert res.json_body[0]['content_id'] == firstly_created.content_id
        assert res.json_body[0]['read_by_user'] is True


class TestUserSetContentAsUnread(FunctionalTest):
    """
    Tests for /api/v2/users/{user_id}/workspaces/{workspace_id}/contents/{content_id}/unread  # nopep8
    """
    def test_api_set_content_as_unread__ok__200__nominal(self):
        # init DB
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        workspace_api = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config

        )
        workspace = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        ).create_workspace(
            'test workspace',
            save_now=True
        )
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        rapi = RoleApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        rapi.create_one(test_user, workspace, UserRoleInWorkspace.READER, False)
        api = ContentApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        api2 = ContentApi(
            current_user=test_user,
            session=dbsession,
            config=self.app_config,
        )
        main_folder = api.create(content_type_list.Folder.slug, workspace, None, 'this is randomized folder', '', True)  # nopep8
        # creation order test
        firstly_created = api.create(content_type_list.Page.slug, workspace, main_folder, 'creation_order_test', '', True)  # nopep8
        api.mark_read(firstly_created)
        api2.mark_read(firstly_created)
        dbsession.flush()
        transaction.commit()

        self.testapp.authorization = (
            'Basic',
            (
                'test@test.test',
                'password'
            )
        )
        # before
        res = self.testapp.get('/api/v2/users/{user_id}/workspaces/{workspace_id}/contents/read_status'.format(  # nopep8
            user_id=test_user.user_id,
            workspace_id=workspace.workspace_id
        ), status=200)
        assert res.json_body[0]['content_id'] == firstly_created.content_id
        assert res.json_body[0]['read_by_user'] is True

        # unread
        self.testapp.put(
            '/api/v2/users/{user_id}/workspaces/{workspace_id}/contents/{content_id}/unread'.format(  # nopep8
                workspace_id=workspace.workspace_id,
                content_id=firstly_created.content_id,
                user_id=test_user.user_id,
            )
        )
        # after
        res = self.testapp.get('/api/v2/users/{user_id}/workspaces/{workspace_id}/contents/read_status'.format(  # nopep8
            user_id=test_user.user_id,
            workspace_id=workspace.workspace_id
        ), status=200)
        assert res.json_body[0]['content_id'] == firstly_created.content_id
        assert res.json_body[0]['read_by_user'] is False



class TestUserSetWorkspaceAsRead(FunctionalTest):
    """
    Tests for /api/v2/users/{user_id}/workspaces/{workspace_id}/read
    """
    def test_api_set_content_as_read__ok__200__nominal(self):
        # init DB
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        workspace_api = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config

        )
        workspace = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        ).create_workspace(
            'test workspace',
            save_now=True
        )
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        rapi = RoleApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        rapi.create_one(test_user, workspace, UserRoleInWorkspace.READER, False)
        api = ContentApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        api2 = ContentApi(
            current_user=test_user,
            session=dbsession,
            config=self.app_config,
        )
        main_folder = api.create(content_type_list.Folder.slug, workspace, None, 'this is randomized folder', '', True)  # nopep8
        # creation order test
        firstly_created = api.create(content_type_list.Page.slug, workspace, main_folder, 'creation_order_test', '', True)  # nopep8
        api.mark_unread(main_folder)
        api.mark_unread(firstly_created)
        api2.mark_unread(main_folder)
        api2.mark_unread(firstly_created)
        dbsession.flush()
        transaction.commit()

        self.testapp.authorization = (
            'Basic',
            (
                'test@test.test',
                'password'
            )
        )
        res = self.testapp.get('/api/v2/users/{user_id}/workspaces/{workspace_id}/contents/read_status'.format(  # nopep8
            user_id=test_user.user_id,
            workspace_id=workspace.workspace_id
        ), status=200)
        assert res.json_body[0]['content_id'] == firstly_created.content_id
        assert res.json_body[0]['read_by_user'] is False
        assert res.json_body[1]['content_id'] == main_folder.content_id
        assert res.json_body[1]['read_by_user'] is False
        self.testapp.put(
            '/api/v2/users/{user_id}/workspaces/{workspace_id}/read'.format(  # nopep8
                workspace_id=workspace.workspace_id,
                content_id=firstly_created.content_id,
                user_id=test_user.user_id,
            )
        )
        res = self.testapp.get('/api/v2/users/{user_id}/workspaces/{workspace_id}/contents/read_status'.format(  # nopep8
            user_id=test_user.user_id,
            workspace_id=workspace.workspace_id
        ), status=200)
        assert res.json_body[0]['content_id'] == firstly_created.content_id
        assert res.json_body[0]['read_by_user'] is True
        assert res.json_body[1]['content_id'] == main_folder.content_id
        assert res.json_body[1]['read_by_user'] is True

class TestAccountEnableWorkspaceNotification(FunctionalTest):
    """
    Tests for /api/v2/users/{user_id}/workspaces/{workspace_id}/notifications/activate
    """
    def test_api_enable_account_workspace_notification__ok__200__user_nominal(self):
        # init DB
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        workspace_api = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config

        )
        workspace = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        ).create_workspace(
            'test workspace',
            save_now=True
        )
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        rapi = RoleApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        rapi.create_one(test_user, workspace, UserRoleInWorkspace.READER, with_notif=False)  # nopep8
        transaction.commit()
        role = rapi.get_one(test_user.user_id, workspace.workspace_id)
        assert role.do_notify is False
        self.testapp.authorization = (
            'Basic',
            (
                'test@test.test',
                'password',
            )
        )
        self.testapp.put_json('/api/v2/users/{user_id}/workspaces/{workspace_id}/notifications/activate'.format(  # nopep8
            user_id=test_user.user_id,
            workspace_id=workspace.workspace_id
        ), status=204)

        dbsession = get_tm_session(self.session_factory, transaction.manager)
        rapi = RoleApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        role = rapi.get_one(test_user.user_id, workspace.workspace_id)
        assert role.do_notify is True


class TestAccountDisableWorkspaceNotification(FunctionalTest):
    """
    Tests for /api/v2/users/me/workspaces/{workspace_id}/notifications/deactivate  # nopep8
    """
    def test_api_enable_account_workspace_notification__ok__200__nominal(self):
        # init DB
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        workspace_api = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config

        )
        workspace = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        ).create_workspace(
            'test workspace',
            save_now=True
        )
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        rapi = RoleApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        rapi.create_one(test_user, workspace, UserRoleInWorkspace.READER, with_notif=True)  # nopep8
        transaction.commit()
        role = rapi.get_one(test_user.user_id, workspace.workspace_id)
        assert role.do_notify is True
        self.testapp.authorization = (
            'Basic',
            (
                'test@test.test',
                'password',
            )
        )
        self.testapp.put_json('/api/v2/users/me/workspaces/{workspace_id}/notifications/deactivate'.format(  # nopep8
            user_id=test_user.user_id,
            workspace_id=workspace.workspace_id
        ), status=204)
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        rapi = RoleApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        role = rapi.get_one(test_user.user_id, workspace.workspace_id)
        assert role.do_notify is False


class TestAccountWorkspaceEndpoint(FunctionalTest):
    """
    Tests for /api/v2/users/me/workspaces
    """
    fixtures = [BaseFixture, ContentFixtures]

    def test_api__get_account_workspaces__ok_200__nominal_case(self):
        """
        Check obtain all workspaces reachables for user with user auth.
        """
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()

        workspace_api = WorkspaceApi(
            session=dbsession,
            current_user=admin,
            config=self.app_config,
        )
        workspace = workspace_api.get_one(1)
        app_api = ApplicationApi(
            app_list
        )

        default_sidebar_entry = app_api.get_default_workspace_menu_entry(workspace=workspace)  # nope8
        self.testapp.authorization = (
            'Basic',
            (
                'admin@admin.admin',
                'admin@admin.admin'
            )
        )
        res = self.testapp.get('/api/v2/users/1/workspaces', status=200)
        res = res.json_body
        workspace = res[0]
        assert workspace['workspace_id'] == 1
        assert workspace['label'] == 'Business'
        assert workspace['slug'] == 'business'
        assert workspace['is_deleted'] is False

        assert len(workspace['sidebar_entries']) == len(default_sidebar_entry)
        for counter, sidebar_entry in enumerate(default_sidebar_entry):
            workspace['sidebar_entries'][counter]['slug'] = sidebar_entry.slug
            workspace['sidebar_entries'][counter]['label'] = sidebar_entry.label
            workspace['sidebar_entries'][counter]['route'] = sidebar_entry.route
            workspace['sidebar_entries'][counter]['hexcolor'] = sidebar_entry.hexcolor  # nopep8
            workspace['sidebar_entries'][counter]['fa_icon'] = sidebar_entry.fa_icon  # nopep8


class TestAccountEndpoint(FunctionalTest):
    # -*- coding: utf-8 -*-
    """
    Tests for GET /api/v2/users/me
    """
    fixtures = [BaseFixture]

    def test_api__get_user__ok_200__nominal(self):
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        uapi.save(test_user)
        transaction.commit()
        user_id = int(test_user.user_id)

        self.testapp.authorization = (
            'Basic',
            (
                'test@test.test',
                'password'
            )
        )
        res = self.testapp.get(
            '/api/v2/users/me',
            status=200
        )
        res = res.json_body
        assert res['user_id'] == user_id
        assert res['created']
        assert res['is_active'] is True
        assert res['profile'] == 'users'
        assert res['email'] == 'test@test.test'
        assert res['public_name'] == 'bob'
        assert res['timezone'] == 'Europe/Paris'
        assert res['is_deleted'] is False


class TestAccountKnownMembersEndpoint(FunctionalTest):
    # -*- coding: utf-8 -*-
    """
    Tests for GET /api/v2/users/me
    """
    fixtures = [BaseFixture]

    def test_api__get_user__ok_200__admin__by_name(self):
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        test_user2 = uapi.create_user(
            email='test2@test2.test2',
            password='password',
            name='bob2',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        uapi.save(test_user)
        uapi.save(test_user2)
        transaction.commit()
        user_id = int(admin.user_id)

        self.testapp.authorization = (
            'Basic',
            (
                'admin@admin.admin',
                'admin@admin.admin'
            )
        )
        params = {
            'acp': 'bob',
        }
        res = self.testapp.get(
            '/api/v2/users/me/known_members',
            status=200,
            params=params,
        )
        res = res.json_body
        assert len(res) == 2
        assert res[0]['user_id'] == test_user.user_id
        assert res[0]['public_name'] == test_user.display_name
        assert res[0]['avatar_url'] is None

        assert res[1]['user_id'] == test_user2.user_id
        assert res[1]['public_name'] == test_user2.display_name
        assert res[1]['avatar_url'] is None

    def test_api__get_user__ok_200__admin__by_name_exclude_user(self):
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        test_user2 = uapi.create_user(
            email='test2@test2.test2',
            password='password',
            name='bob2',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )

        uapi.save(test_user)
        uapi.save(test_user2)
        transaction.commit()
        user_id = int(admin.user_id)

        self.testapp.authorization = (
            'Basic',
            (
                'admin@admin.admin',
                'admin@admin.admin'
            )
        )
        params = {
            'acp': 'bob',
            'exclude_user_ids': str(test_user2.user_id)
        }
        res = self.testapp.get(
            '/api/v2/users/me/known_members',
            status=200,
            params=params,
        )
        res = res.json_body
        assert len(res) == 1
        assert res[0]['user_id'] == test_user.user_id
        assert res[0]['public_name'] == test_user.display_name
        assert res[0]['avatar_url'] is None

    def test_api__get_user__ok_200__admin__by_name_exclude_workspace(self):
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        test_user2 = uapi.create_user(
            email='test2@test2.test2',
            password='password',
            name='bob2',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        workspace_api = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config

        )
        workspace = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        ).create_workspace(
            'test workspace',
            save_now=True
        )
        workspace2 = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        ).create_workspace(
            'test workspace2',
            save_now=True
        )
        role_api = RoleApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        role_api.create_one(test_user, workspace, UserRoleInWorkspace.READER, False)
        role_api.create_one(test_user2, workspace2, UserRoleInWorkspace.READER, False)
        uapi.save(test_user)
        uapi.save(test_user2)
        transaction.commit()
        user_id = int(admin.user_id)

        self.testapp.authorization = (
            'Basic',
            (
                'admin@admin.admin',
                'admin@admin.admin'
            )
        )
        params = {
            'acp': 'bob',
            'exclude_workspace_ids': str(workspace2.workspace_id)
        }
        res = self.testapp.get(
            '/api/v2/users/me/known_members',
            status=200,
            params=params,
        )
        res = res.json_body
        assert len(res) == 1
        assert res[0]['user_id'] == test_user.user_id
        assert res[0]['public_name'] == test_user.display_name
        assert res[0]['avatar_url'] is None

    def test_api__get_user__ok_200__admin__by_name_exclude_workspace_and_user(self):
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        test_user2 = uapi.create_user(
            email='test2@test2.test2',
            password='password',
            name='bob2',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        test_user3 = uapi.create_user(
            email='test3@test3.test3',
            password='password',
            name='bob3',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        workspace_api = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config

        )
        workspace = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        ).create_workspace(
            'test workspace',
            save_now=True
        )
        workspace2 = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        ).create_workspace(
            'test workspace2',
            save_now=True
        )
        role_api = RoleApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        role_api.create_one(test_user, workspace, UserRoleInWorkspace.READER, False)
        role_api.create_one(test_user2, workspace2, UserRoleInWorkspace.READER, False)
        role_api.create_one(test_user3, workspace, UserRoleInWorkspace.READER, False)
        uapi.save(test_user)
        uapi.save(test_user2)
        transaction.commit()
        user_id = int(admin.user_id)

        self.testapp.authorization = (
            'Basic',
            (
                'admin@admin.admin',
                'admin@admin.admin'
            )
        )
        params = {
            'acp': 'bob',
            'exclude_workspace_ids': str(workspace2.workspace_id),
            'exclude_user_ids': str(test_user3.user_id)
        }
        res = self.testapp.get(
            '/api/v2/users/me/known_members',
            status=200,
            params=params,
        )
        res = res.json_body
        assert len(res) == 1
        assert res[0]['user_id'] == test_user.user_id
        assert res[0]['public_name'] == test_user.display_name
        assert res[0]['avatar_url'] is None

    def test_api__get_user__ok_200__admin__by_name__deactivated_members(self):
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        test_user2 = uapi.create_user(
            email='test2@test2.test2',
            password='password',
            name='bob2',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        test_user2.is_active = False
        uapi.save(test_user)
        uapi.save(test_user2)
        transaction.commit()
        user_id = int(admin.user_id)

        self.testapp.authorization = (
            'Basic',
            (
                'admin@admin.admin',
                'admin@admin.admin'
            )
        )
        params = {
            'acp': 'bob',
        }
        res = self.testapp.get(
            '/api/v2/users/me/known_members',
            status=200,
            params=params,
        )
        res = res.json_body
        assert len(res) == 1
        assert res[0]['user_id'] == test_user.user_id
        assert res[0]['public_name'] == test_user.display_name
        assert res[0]['avatar_url'] is None

    def test_api__get_user__ok_200__admin__by_email(self):
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        test_user2 = uapi.create_user(
            email='test2@test2.test2',
            password='password',
            name='bob2',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        uapi.save(test_user)
        uapi.save(test_user2)
        transaction.commit()
        user_id = int(admin.user_id)

        self.testapp.authorization = (
            'Basic',
            (
                'admin@admin.admin',
                'admin@admin.admin'
            )
        )
        params = {
            'acp': 'test',
        }
        res = self.testapp.get(
            '/api/v2/users/me/known_members',
            status=200,
            params=params,
        )
        res = res.json_body
        assert len(res) == 2
        assert res[0]['user_id'] == test_user.user_id
        assert res[0]['public_name'] == test_user.display_name
        assert res[0]['avatar_url'] is None

        assert res[1]['user_id'] == test_user2.user_id
        assert res[1]['public_name'] == test_user2.display_name
        assert res[1]['avatar_url'] is None

    def test_api__get_user__err_403__admin__too_small_acp(self):
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        test_user2 = uapi.create_user(
            email='test2@test2.test2',
            password='password',
            name='bob2',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        uapi.save(test_user)
        transaction.commit()
        user_id = int(admin.user_id)

        self.testapp.authorization = (
            'Basic',
            (
                'admin@admin.admin',
                'admin@admin.admin'
            )
        )
        params = {
            'acp': 't',
        }
        res = self.testapp.get(
            '/api/v2/users/me/known_members',
            status=400,
            params=params
        )
        assert isinstance(res.json, dict)
        assert 'code' in res.json.keys()
        assert res.json_body['code'] == error.GENERIC_SCHEMA_VALIDATION_ERROR  # nopep8

    def test_api__get_user__ok_200__normal_user_by_email(self):
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        test_user2 = uapi.create_user(
            email='test2@test2.test2',
            password='password',
            name='bob2',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        test_user3 = uapi.create_user(
            email='test3@test3.test3',
            password='password',
            name='bob3',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        uapi.save(test_user)
        uapi.save(test_user2)
        uapi.save(test_user3)
        workspace_api = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config

        )
        workspace = WorkspaceApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        ).create_workspace(
            'test workspace',
            save_now=True
        )
        role_api = RoleApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        role_api.create_one(test_user, workspace, UserRoleInWorkspace.READER, False)
        role_api.create_one(test_user2, workspace, UserRoleInWorkspace.READER, False)
        transaction.commit()
        user_id = int(test_user.user_id)

        self.testapp.authorization = (
            'Basic',
            (
                'test@test.test',
                'password'
            )
        )
        params = {
            'acp': 'test',
        }
        res = self.testapp.get(
            '/api/v2/users/me/known_members',
            status=200,
            params=params
        )
        res = res.json_body
        assert len(res) == 2
        assert res[0]['user_id'] == test_user.user_id
        assert res[0]['public_name'] == test_user.display_name
        assert res[0]['avatar_url'] is None

        assert res[1]['user_id'] == test_user2.user_id
        assert res[1]['public_name'] == test_user2.display_name
        assert res[1]['avatar_url'] is None


class TestSetEmailEndpoint(FunctionalTest):
    # -*- coding: utf-8 -*-
    """
    Tests for PUT /api/v2/users/me/email
    """
    fixtures = [BaseFixture]

    def test_api__set_account_email__err_400__admin_same_email(self):
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        uapi.save(test_user)
        transaction.commit()
        user_id = int(test_user.user_id)

        self.testapp.authorization = (
            'Basic',
            (
                'test@test.test',
                'password',
            )
        )
        # check before
        res = self.testapp.get(
            '/api/v2/users/me',
            status=200
        )
        res = res.json_body
        assert res['email'] == 'test@test.test'

        # Set password
        params = {
            'email': 'admin@admin.admin',
            'loggedin_user_password': 'password',
        }
        res = self.testapp.put_json(
            '/api/v2/users/me/email',
            params=params,
            status=400,
        )
        assert res.json_body
        assert 'code' in res.json_body
        assert res.json_body['code'] == error.EMAIL_ALREADY_EXIST_IN_DB
        # Check After
        res = self.testapp.get(
            '/api/v2/users/me',
            status=200
        )
        res = res.json_body
        assert res['email'] == 'test@test.test'

    def test_api__set_account_email__err_403__admin_wrong_password(self):
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        uapi.save(test_user)
        transaction.commit()
        user_id = int(test_user.user_id)

        self.testapp.authorization = (
            'Basic',
            (
                'test@test.test',
                'password'
            )
        )
        # check before
        res = self.testapp.get(
            '/api/v2/users/me',
            status=200
        )
        res = res.json_body
        assert res['email'] == 'test@test.test'

        # Set password
        params = {
            'email': 'mysuperemail@email.fr',
            'loggedin_user_password': 'badpassword',
        }
        res = self.testapp.put_json(
            '/api/v2/users/me/email',
            params=params,
            status=403,
        )
        assert res.json_body
        assert 'code' in res.json_body
        assert res.json_body['code'] == error.WRONG_USER_PASSWORD  # nopep8
        # Check After
        res = self.testapp.get(
            '/api/v2/users/me',
            status=200
        )
        res = res.json_body
        assert res['email'] == 'test@test.test'

    def test_api__set_account_email__ok_200__user_nominal(self):
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        uapi.save(test_user)
        transaction.commit()
        user_id = int(test_user.user_id)

        self.testapp.authorization = (
            'Basic',
            (
                'test@test.test',
                'password'
            )
        )
        # check before
        res = self.testapp.get(
            '/api/v2/users/me',
            status=200
        )
        res = res.json_body
        assert res['email'] == 'test@test.test'

        # Set password
        params = {
            'email': 'mysuperemail@email.fr',
            'loggedin_user_password': 'password',
        }
        self.testapp.put_json(
            '/api/v2/users/me/email',
            params=params,
            status=200,
        )
        self.testapp.authorization = (
            'Basic',
            (
                'mysuperemail@email.fr',
                'password'
            )
        )
        # Check After
        res = self.testapp.get(
            '/api/v2/users/me',
            status=200
        )
        res = res.json_body
        assert res['email'] == 'mysuperemail@email.fr'


class TestSetPasswordEndpoint(FunctionalTest):
    # -*- coding: utf-8 -*-
    """
    Tests for PUT /api/v2/users/me/password
    """
    fixtures = [BaseFixture]

    def test_api__set_account_password__err_403__admin_wrong_password(self):
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        uapi.save(test_user)
        transaction.commit()
        user_id = int(test_user.user_id)

        self.testapp.authorization = (
            'Basic',
            (
                'admin@admin.admin',
                'admin@admin.admin'
            )
        )
        # check before
        user = uapi.get_one(user_id)
        assert user.validate_password('password')
        assert not user.validate_password('mynewpassword')
        # Set password
        params = {
            'new_password': 'mynewpassword',
            'new_password2': 'mynewpassword',
            'loggedin_user_password': 'wrongpassword',
        }
        res = self.testapp.put_json(
            '/api/v2/users/me/password',
            params=params,
            status=403,
        )
        assert res.json_body
        assert 'code' in res.json_body
        assert res.json_body['code'] == error.WRONG_USER_PASSWORD
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        # Check After
        user = uapi.get_one(user_id)
        assert user.validate_password('password')
        assert not user.validate_password('mynewpassword')

    def test_api__set_account_password__err_400__admin_passwords_do_not_match(self):  # nopep8
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        uapi.save(test_user)
        transaction.commit()
        user_id = int(test_user.user_id)

        self.testapp.authorization = (
            'Basic',
            (
                'admin@admin.admin',
                'admin@admin.admin'
            )
        )
        # check before
        user = uapi.get_one(user_id)
        assert user.validate_password('password')
        assert not user.validate_password('mynewpassword')
        assert not user.validate_password('mynewpassword2')
        # Set password
        params = {
            'new_password': 'mynewpassword',
            'new_password2': 'mynewpassword2',
            'loggedin_user_password': 'admin@admin.admin',
        }
        res = self.testapp.put_json(
            '/api/v2/users/me/password',
            params=params,
            status=400,
        )
        assert res.json_body
        assert 'code' in res.json_body
        assert res.json_body['code'] == error.PASSWORD_DO_NOT_MATCH
        # Check After
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        user = uapi.get_one(user_id)
        assert user.validate_password('password')
        assert not user.validate_password('mynewpassword')
        assert not user.validate_password('mynewpassword2')

    def test_api__set_account_password__ok_200__nominal(self):
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        uapi.save(test_user)
        transaction.commit()
        user_id = int(test_user.user_id)

        self.testapp.authorization = (
            'Basic',
            (
                'test@test.test',
                'password'
            )
        )
        # check before
        user = uapi.get_one(user_id)
        assert user.validate_password('password')
        assert not user.validate_password('mynewpassword')
        # Set password
        params = {
            'new_password': 'mynewpassword',
            'new_password2': 'mynewpassword',
            'loggedin_user_password': 'password',
        }
        self.testapp.put_json(
            '/api/v2/users/me/password',
            params=params,
            status=204,
        )
        # Check After
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        user = uapi.get_one(user_id)
        assert not user.validate_password('password')
        assert user.validate_password('mynewpassword')



class TestSetUserInfoEndpoint(FunctionalTest):
    # -*- coding: utf-8 -*-
    """
    Tests for PUT /api/v2/users/me
    """
    fixtures = [BaseFixture]

    def test_api__set_account_info__ok_200__nominal(self):
        dbsession = get_tm_session(self.session_factory, transaction.manager)
        admin = dbsession.query(models.User) \
            .filter(models.User.email == 'admin@admin.admin') \
            .one()
        uapi = UserApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        gapi = GroupApi(
            current_user=admin,
            session=dbsession,
            config=self.app_config,
        )
        groups = [gapi.get_one_with_name('users')]
        test_user = uapi.create_user(
            email='test@test.test',
            password='password',
            name='bob',
            groups=groups,
            timezone='Europe/Paris',
            lang='fr',
            do_save=True,
            do_notify=False,
        )
        uapi.save(test_user)
        transaction.commit()
        user_id = int(test_user.user_id)

        self.testapp.authorization = (
            'Basic',
            (
                'test@test.test',
                'password',
            )
        )
        # check before
        res = self.testapp.get(
            '/api/v2/users/me',
            status=200
        )
        res = res.json_body
        assert res['user_id'] == user_id
        assert res['public_name'] == 'bob'
        assert res['timezone'] == 'Europe/Paris'
        assert res['lang'] == 'fr'
        # Set params
        params = {
            'public_name': 'updated',
            'timezone': 'Europe/London',
            'lang': 'en',
        }
        self.testapp.put_json(
            '/api/v2/users/me',
            params=params,
            status=200,
        )
        # Check After
        res = self.testapp.get(
            '/api/v2/users/me',
            status=200
        )
        res = res.json_body
        assert res['user_id'] == user_id
        assert res['public_name'] == 'updated'
        assert res['timezone'] == 'Europe/London'
        assert res['lang'] == 'en'
