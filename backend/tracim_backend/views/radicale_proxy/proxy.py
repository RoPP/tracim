# coding: utf-8
from pyramid.config import Configurator
from pyramid.response import Response
from tracim_backend.extensions import hapic
from tracim_backend.exceptions import NotAuthorized
from tracim_backend.exceptions import NotAuthenticated
from tracim_backend.lib.proxy.proxy import Proxy
from tracim_backend.lib.utils.authorization import check_user_calendar_authorization
from tracim_backend.lib.utils.request import TracimRequest
from tracim_backend.views.controllers import Controller


class RadicaleProxyController(Controller):
    def __init__(self):
        self._proxy = Proxy(
            # FIXME BS 2018-11-27: from config
            base_address='http://127.0.0.1:4321',
        )

    # FIXME BS 2018-11-29: enable doc
    # @hapic.with_api_doc()
    @hapic.handle_exception(NotAuthenticated, http_code=401)
    @hapic.handle_exception(NotAuthorized, http_code=403)
    def radicale_proxy__user(self, context, request: TracimRequest):
        user_id = int(request.matchdict['user_id'])

        try:
            check_user_calendar_authorization(request, user_id)
        # TODO BS 2018-12-04: managed in decorators ?
        except NotAuthenticated:
            return Response(
                status=401,
                headerlist=[
                    ('WWW-Authenticate', 'Basic realm="Tracim credentials"'),
                ]
            )

        return self._proxy.get_response_for_request(
            request,
            '/user/{}.ics'.format(
                str(user_id),
            ),
            extra_headers={
                # NOTE BS 2018-12-04: Radicale must be configured with "http_x_remote_user" as
                # auth type config value.
                'X-Remote-User': request.current_user.user_id,
            }
        )

    # FIXME BS 2018-11-29: enable doc
    # @hapic.with_api_doc()
    @hapic.handle_exception(NotAuthenticated, http_code=401)
    @hapic.handle_exception(NotAuthorized, http_code=403)
    def radicale_proxy__workspace(self, context, request: TracimRequest):
        # FIXME BS 2018-11-26: check authenticated user can make this request
        # (use new right validation objects)
        return self._proxy.get_response_for_request(request)

    def bind(self, configurator: Configurator) -> None:
        """
        Create all routes and views using pyramid configurator
        for this controller
        """
        # Radicale user calendar
        configurator.add_route(
            'radicale_proxy__user',
            '/radicale/user/{user_id:[0-9]+}.ics',
        )
        configurator.add_view(
            self.radicale_proxy__user,
            route_name='radicale_proxy__user',
        )

        # Radicale workspace calendar
        configurator.add_route(
            'radicale_proxy__workspace',
            '/radicale/workspace/{workspace_id:[0-9]+}.ics',
        )
        configurator.add_view(
            self.radicale_proxy__workspace,
            route_name='radicale_proxy__workspace',
        )
