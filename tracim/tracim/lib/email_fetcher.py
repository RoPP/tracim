# -*- coding: utf-8 -*-

import sys
import time
import imaplib
import datetime
import json
import typing
from email.message import Message
from email.header import Header, decode_header, make_header
from email.utils import parseaddr, parsedate_tz, mktime_tz
from email import message_from_bytes

import markdown
import requests
from bs4 import BeautifulSoup
from email_reply_parser import EmailReplyParser

from tracim.lib.base import logger

TRACIM_SPECIAL_KEY_HEADER = 'X-Tracim-Key'
# TODO BS 20171124: Think about replace thin dict config by object
BEAUTIFULSOUP_HTML_BODY_PARSE_CONFIG = {
    'tag_blacklist': ['script', 'style', 'blockquote'],
    'class_blacklist': ['moz-cite-prefix', 'gmail_extra', 'gmail_quote',
                        'yahoo_quoted'],
    'id_blacklist': ['reply-intro'],
    'tag_whitelist': ['a', 'b', 'strong', 'i', 'br', 'ul', 'li', 'ol',
                      'em', 'i', 'u',
                      'thead', 'tr', 'td', 'tbody', 'table', 'p', 'pre'],
    'attrs_whitelist': ['href'],
}
CONTENT_TYPE_TEXT_PLAIN = 'text/plain'
CONTENT_TYPE_TEXT_HTML = 'text/html'


class DecodedMail(object):

    def __init__(self, message: Message):
        self._message = message

    def _decode_header(self, header_title: str) -> typing.Optional[str]:
        # FIXME : Handle exception
        if header_title in self._message:
            return str(make_header(decode_header(header)))
        else:
            return None

    def get_subject(self) -> typing.Optional[str]:
        return self._decode_header('subject')

    def get_from_address(self) -> typing.Optional[str]:
        return parseaddr(self._message['From'])[1]

    def get_to_address(self)-> typing.Optional[str]:
        return parseaddr(self._message['To'])[1]

    def get_first_ref(self) -> typing.Optional[str]:
        return parseaddr(self._message['References'])[1]

    def get_special_key(self) -> typing.Optional[str]:
        return self._decode_header(TRACIM_SPECIAL_KEY_HEADER)

    def get_body(self) -> typing.Optional[str]:
        body_part = self._get_mime_body_message()
        body = None
        if body_part:
            charset = body_part.get_content_charset('iso-8859-1')
            content_type = body_part.get_content_type()
            if content_type == CONTENT_TYPE_TEXT_PLAIN:
                txt_body = body_part.get_payload(decode=True).decode(
                    charset)
                body = DecodedMail._parse_txt_body(txt_body)

            elif content_type == CONTENT_TYPE_TEXT_HTML:
                html_body = body_part.get_payload(decode=True).decode(
                    charset)
                body = DecodedMail._parse_html_body(html_body)

        return body

    @classmethod
    def _parse_txt_body(cls, txt_body: str):
        txt_body = EmailReplyParser.parse_reply(txt_body)
        html_body = markdown.markdown(txt_body)
        body = DecodedMail._parse_html_body(html_body)
        return body

    @classmethod
    def _parse_html_body(cls, html_body: str):
        soup = BeautifulSoup(html_body, 'html.parser')
        config = BEAUTIFULSOUP_HTML_BODY_PARSE_CONFIG
        for tag in soup.findAll():
            if DecodedMail._tag_to_extract(tag):
                tag.extract()
            elif tag.name.lower() in config['tag_whitelist']:
                attrs = dict(tag.attrs)
                for attr in attrs:
                    if attr not in config['attrs_whitelist']:
                        del tag.attrs[attr]
            else:
                tag.unwrap()
        return str(soup)

    @classmethod
    def _tag_to_extract(cls, tag) -> bool:
        config = BEAUTIFULSOUP_HTML_BODY_PARSE_CONFIG
        if tag.name.lower() in config['tag_blacklist']:
            return True
        if 'class' in tag.attrs:
            for elem in config['class_blacklist']:
                if elem in tag.attrs['class']:
                    return True
        if 'id' in tag.attrs:
            for elem in config['id_blacklist']:
                if elem in tag.attrs['id']:
                    return True
        return False

    def _get_mime_body_message(self) -> typing.Optional[Message]:
        # TODO - G.M - 2017-11-16 - Use stdlib msg.get_body feature for py3.6+
        part = None
        # Check for html
        for part in self._message.walk():
            content_type = part.get_content_type()
            content_dispo = str(part.get('Content-Disposition'))
            if content_type == CONTENT_TYPE_TEXT_HTML \
                    and 'attachment' not in content_dispo:
                return part
        # check for plain text
        for part in self._message.walk():
            content_type = part.get_content_type()
            content_dispo = str(part.get('Content-Disposition'))
            if content_type == CONTENT_TYPE_TEXT_PLAIN \
                    and 'attachment' not in content_dispo:
                return part
        return part

    def get_key(self) -> typing.Optional[str]:

        """
        key is the string contain in some mail header we need to retrieve.
        First try checking special header, them check 'to' header
        and finally check first(oldest) mail-id of 'references' header
        """
        first_ref = self.get_first_ref()
        to_address = self.get_to_address()
        special_key = self.get_special_key()

        if special_key:
            return special_key
        if to_address:
            return DecodedMail.find_key_from_mail_address(to_address)
        if first_ref:
            return DecodedMail.find_key_from_mail_address(first_ref)

    @classmethod
    def find_key_from_mail_address(cls, mail_address: str) \
            -> typing.Optional[str]:
        """ Parse mail_adress-like string
        to retrieve key.

        :param mail_address: user+key@something like string
        :return: key
        """
        username = mail_address.split('@')[0]
        username_data = username.split('+')
        if len(username_data) == 2:
            return username_data[1]
        return None


class MailFetcher(object):

    def __init__(self,
                 host: str,
                 port: str,
                 user: str,
                 password: str,
                 use_ssl: bool,
                 folder: str,
                 delay: int,
                 endpoint: str,
                 token: str) \
            -> None:
        """
        Fetch mail from a mailbox folder through IMAP and add their content to
        Tracim through http according to mail Headers.
        Fetch is regular.
        :param host: imap server hostname
        :param port: imap connection port
        :param user: user login of mailbox
        :param password: user password of mailbox
        :param use_ssl: use imap over ssl connection
        :param folder: mail folder where new mail are fetched
        :param delay: seconds to wait before fetching new mail again
        :param endpoint: tracim http endpoint where decoded mail are send.
        :param token: token to authenticate http connexion
        """
        self._connection = None
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_ssl = use_ssl
        self.folder = folder
        self.delay = delay
        self.endpoint = endpoint
        self.token = token

        self._is_active = True

    def run(self) -> None:
        while self._is_active:
            time.sleep(self.delay)
            try:
                self._connect()
                messages = self._fetch()
                # TODO - G.M -  2017-11-22 retry sending unsended mail
                # These mails are return by _notify_tracim, flag them with "unseen"
                # or store them until new _notify_tracim call
                cleaned_mails = [DecodedMail(msg) for msg in messages]
                self._notify_tracim(cleaned_mails)
                self._disconnect()
            except Exception as e:
                # TODO - G.M - 2017-11-23 - Identify possible exceptions
                log = 'IMAP error: {}'
                logger.warning(self, log.format(e.__str__()))

    def stop(self) -> None:
        self._is_active = False

    def _connect(self) -> None:
        # TODO - G.M - 2017-11-15 Verify connection/disconnection
        # Are old connexion properly close this way ?
        if self._connection:
            self._disconnect()
        # TODO - G.M - 2017-11-23 Support for predefined SSLContext ?
        # without ssl_context param, tracim use default security configuration
        # which is great in most case.
        if self.use_ssl:
            self._connection = imaplib.IMAP4_SSL(self.host, self.port)
        else:
            self._connection = imaplib.IMAP4(self.host, self.port)

        try:
            self._connection.login(self.user, self.password)
        except Exception as e:
            log = 'IMAP login error: {}'
            logger.warning(self, log.format(e.__str__()))

    def _disconnect(self) -> None:
        if self._connection:
            self._connection.close()
            self._connection.logout()
            self._connection = None

    def _fetch(self) -> list:
        """
        Get news message from mailbox
        :return: list of new mails
        """
        messages = []
        # select mailbox
        rv, data = self._connection.select(self.folder)
        if rv == 'OK':
            # get mails
            # TODO - G.M -  2017-11-15 Which files to select as new file ?
            # Unseen file or All file from a directory (old one should be moved/
            # deleted from mailbox during this process) ?
            rv, data = self._connection.search(None, "(UNSEEN)")
            if rv == 'OK':
                # get mail content
                for num in data[0].split():
                    # INFO - G.M - 2017-11-23 - Fetch (RFC288) to retrieve all complete mails
                    # see example : https://docs.python.org/fr/3.5/library/imaplib.html#imap4-example .
                    # Be careful, This method remove also mails from Unseen mails

                    rv, data = self._connection.fetch(num, '(RFC822)')
                    if rv == 'OK':
                        msg = message_from_bytes(data[0][1])
                        messages.append(msg)
                    else:
                        log = 'IMAP : Unable to get mail : {}'
                        logger.debug(self, log.format(str(rv)))
            else:
                # FIXME : Distinct error from empty mailbox ?
                pass
        else:
            log = 'IMAP : Unable to open mailbox : {}'
            logger.debug(self, log.format(str(rv)))
        return messages

    def _notify_tracim(self, mails: list) -> list:
        """
        Send http request to tracim endpoint
        :param mails: list of mails to send
        :return: unsended mails
        """
        unsended_mails = []
        while mails:
            mail = mails.pop()
            msg = {'token': self.token,
                   'user_mail': mail.get_from_address(),
                   'content_id': mail.get_key(),
                   'payload': {
                       'content': mail.get_body(),
                   }}
            try:
                r = requests.post(self.endpoint, json=msg)
                if r.status_code not in [200, 204]:
                    log = 'bad status code response when sending mail to tracim: {}'  # nopep8
                    logger.error(self, log.format(str(r.status_code)))
            # TODO - G.M - Verify exception correctly works
            except requests.exceptions.Timeout:
                log = 'Timeout error to transmit fetched mail to tracim : {}'
                logger.error(self, log.format(str(e)))
                unsended_mail.append(mail)
                break
            except requests.exceptions.RequestException as e:
                log = 'Fail to transmit fetched mail to tracim : {}'
                logger.error(self, log.format(str(e)))
                break
        return unsended_mails
