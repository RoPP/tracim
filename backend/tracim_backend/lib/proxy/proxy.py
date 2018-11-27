# coding: utf-8
from pyramid.response import Response
from tracim_backend.lib.utils.request import TracimRequest


class Proxy(object):
    def __init__(self, base_address: str) -> None:
        self._base_address = base_address

    def get_response_for_request(
        self,
        request: TracimRequest,
        path: str,
    ) -> Response:
        response = Response()
