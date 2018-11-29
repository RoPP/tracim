# coding: utf-8
from urllib.parse import urljoin

import requests
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
        behind_url = urljoin(self._base_address, path)
        behind_response = requests.request(
            method=request.method,
            # FIXME BS 2018-11-29: Exclude some headers (like basic auth)
            headers=dict(request.headers),
            data=request.body,
            url=behind_url,
        )

        drop_headers = {
            'keep-alive': None,
            'connection': 'keep-alive',
            'content-encoding': None,
            'content-length': None,
        }
        headers = []
        for header_name, header_value in dict(behind_response.headers).items():
            if (header_name.lower(), header_value.lower()) not in drop_headers\
                    and header_name.lower() not in drop_headers.keys():
                headers.append((header_name, header_value))

        return Response(
            status=behind_response.status_code,
            headerlist=headers,
            body=behind_response.content,
        )
