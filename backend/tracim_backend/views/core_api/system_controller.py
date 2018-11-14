# coding=utf-8
from pyramid.config import Configurator

from tracim_backend.app_models.contents import content_type_list
from tracim_backend.extensions import app_list
from tracim_backend.extensions import hapic
from tracim_backend.lib.core.application import ApplicationApi
from tracim_backend.lib.core.system import SystemApi
from tracim_backend.lib.utils.authorization import require_profile
from tracim_backend.lib.utils.request import TracimRequest
from tracim_backend.lib.utils.utils import get_timezones_list
from tracim_backend.models import Group
from tracim_backend.models.context_models import AboutModel
from tracim_backend.models.context_models import ConfigModel
from tracim_backend.models.context_models import WebdavInfo
from tracim_backend.views.controllers import Controller
from tracim_backend.views.core_api.schemas import AboutSchema
from tracim_backend.views.core_api.schemas import ApplicationSchema
from tracim_backend.views.core_api.schemas import ConfigSchema
from tracim_backend.views.core_api.schemas import ContentTypeSchema
from tracim_backend.views.core_api.schemas import TimezoneSchema
from tracim_backend.views.core_api.schemas import WebdavInfoSchema

try:  # Python 3.5+
    from http import HTTPStatus
except ImportError:
    from http import client as HTTPStatus


SWAGGER_TAG_SYSTEM_ENDPOINTS = 'System'


class SystemController(Controller):

    @hapic.with_api_doc(tags=[SWAGGER_TAG_SYSTEM_ENDPOINTS])
    @require_profile(Group.TIM_USER)
    @hapic.output_body(ApplicationSchema(many=True),)
    def applications(self, context, request: TracimRequest, hapic_data=None):
        """
        Get list of alls applications installed in this tracim instance.
        """
        app_config = request.registry.settings['CFG']
        app_api = ApplicationApi(
            app_list=app_list,
        )
        return app_api.get_all()

    @hapic.with_api_doc(tags=[SWAGGER_TAG_SYSTEM_ENDPOINTS])
    @require_profile(Group.TIM_USER)
    @hapic.output_body(ContentTypeSchema(many=True), )
    def content_types(self, context, request: TracimRequest, hapic_data=None):
        """
        Get list of alls content types availables in this tracim instance.
        """
        content_types_slugs = content_type_list.endpoint_allowed_types_slug()
        content_types = [content_type_list.get_one_by_slug(slug) for slug in content_types_slugs]
        return content_types

    @hapic.with_api_doc(tags=[SWAGGER_TAG_SYSTEM_ENDPOINTS])
    @require_profile(Group.TIM_USER)
    @hapic.output_body(TimezoneSchema(many=True),)
    def timezones_list(self, context, request: TracimRequest, hapic_data=None):
        """
        Get List of timezones
        """
        return get_timezones_list()

    @hapic.with_api_doc(tags=[SWAGGER_TAG_SYSTEM_ENDPOINTS])
    @require_profile(Group.TIM_USER)
    @hapic.output_body(AboutSchema(),)
    def about(self, context, request: TracimRequest, hapic_data=None):
        """
        Returns information about current tracim instance.
        This is the equivalent of classical "help > about" menu in classical software.
        """
        app_config = request.registry.settings['CFG']
        system_api = SystemApi(app_config)
        return system_api.get_about()

    @hapic.with_api_doc(tags=[SWAGGER_TAG_SYSTEM_ENDPOINTS])
    @require_profile(Group.TIM_USER)
    @hapic.output_body(ConfigSchema(),)
    def config(self, context, request: TracimRequest, hapic_data=None):
        """
        Returns configuration information required for frontend.
        At the moment it only returns if email notifications are activated.
        """
        app_config = request.registry.settings['CFG']
        system_api = SystemApi(app_config)
        return system_api.get_config()

    @hapic.with_api_doc(tags=[SWAGGER_TAG_SYSTEM_ENDPOINTS])
    @require_profile(Group.TIM_USER)
    @hapic.output_body(WebdavInfoSchema(),)
    def webdav_info(self, context, request: TracimRequest, hapic_data=None):
        """
        Get webdav_info
        """
        app_config = request.registry.settings['CFG']
        return WebdavInfo(
            activated=app_config.WSGIDAV_ACTIVATED,
            client_base_url=app_config.WSGIDAV_CLIENT_BASE_URL,
            encrypted=app_config.WSGIDAV_CLIENT_ENCRYPTED,
        )

    def bind(self, configurator: Configurator) -> None:
        """
        Create all routes and views using pyramid configurator
        for this controller
        """

        # About
        configurator.add_route('about', '/system/about', request_method='GET')  # nopep8
        configurator.add_view(self.about, route_name='about')

        # Config
        configurator.add_route('config', '/system/config', request_method='GET')  # nopep8
        configurator.add_view(self.config, route_name='config')

        # Applications
        configurator.add_route('applications', '/system/applications', request_method='GET')  # nopep8
        configurator.add_view(self.applications, route_name='applications')

        # Content_types
        configurator.add_route('content_types', '/system/content_types', request_method='GET')  # nopep8
        configurator.add_view(self.content_types, route_name='content_types')

        # Content_types
        configurator.add_route('timezones_list', '/system/timezones', request_method='GET')  # nopep8
        configurator.add_view(self.timezones_list, route_name='timezones_list')

        # webdav
        configurator.add_route('webdav_info', '/system/webdav', request_method='GET')  # nopep8
        configurator.add_view(self.webdav_info, route_name='webdav_info')
