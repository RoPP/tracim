# coding: utf-8
from pyramid.config import Configurator
from tracim_backend.lib.proxy.proxy import Proxy
from tracim_backend.lib.utils.request import TracimRequest
from tracim_backend.views.controllers import Controller


class RadicaleProxyController(Controller):
    def __init__(self):
        self._proxy = Proxy(
            # FIXME BS 2018-11-27: from config
            base_address='http://127.0.0.1/',
        )

    def radicale_proxy__user(self, context, request: TracimRequest):
        # FIXME BS 2018-11-26: check authenticated user can make this request
        user_id = int(request.matchdict['user_id'])

        return self._proxy.get_response_for_request(
            request,
            '/user/{}.ics'.format(
                str(user_id),
            )
        )

    def radicale_proxy__workspace(self, context, request: TracimRequest):
        # FIXME BS 2018-11-26: check authenticated user can make this request
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
