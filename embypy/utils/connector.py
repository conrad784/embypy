#!/usr/bin/env python3

import json
from requests import Session, adapters, exceptions
from requests.compat import urlparse, urlunparse, urlencode
import asyncio
import aiohttp
import async_timeout
from requests.compat import urlparse, urlunparse, urlencode
import websockets
import ssl

adapters.DEFAULT_RETRIES = 5

class WebSocket:
  def __init__(self, conn, url, ssl_str=None):
    self.on_message = []
    self.url        = url
    self.conn       = conn
    if not ssl_str:
      self.ssl      = None
    else:
      self.ssl      = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
      self.ssl.load_verify_locations(cafile=ssl_str)

  def connect(self):
    asyncio.get_event_loop().create_task(self.handler())

  async def handler(self):
    self.ws = await websockets.connect(self.url, ssl=self.ssl)
    while True:
      message = await self.ws.recv()
      for handle in self.on_message:
        await handle(message)

  def close(self):
    self.ws.close()
    self.ws = None

class Connector:
  def __init__(self, url, **kargs):
    if ('api_key'  not in kargs or 'device_id' not in kargs) and \
       ('username' not in kargs or 'password'  not in kargs):
      raise ValueError('provide api key and device id or username/password')

    self.ssl       = kargs.get('ssl', False)
    self.userid    = kargs.get('userid')
    self.api_key   = kargs.get('api_key')
    self.username  = kargs.get('username')
    self.password  = kargs.get('password')
    self.device_id = kargs.get('device_id')
    self.loop      = kargs.get('loop', asyncio.get_event_loop())

    p            = urlparse(url)
    conn         = aiohttp.TCPConnector(verify_ssl=self.ssl)
    self.scheme  = p.scheme
    self.netloc  = p.netloc
    self.session = Session()

    #connect to websocket is user wants to
    if 'ws' in kargs:
      self.ws = WebSocket(self, self.get_url(websocket=True), self.ssl)
    else:
      self.ws = None

  def get_stream(self, url):
    class A:
      def __init__(self, g):
        self.g = g
      def read(self):
        return g.__next__()
    g = self.session.get(url, stream=True, verify=self.ssl) #.raw
    return A(g.iter_lines())

  def get_url(self, path='/', websocket=False, attach_api_key=True, **query):
    if attach_api_key:
      query.update({'api_key':self.api_key, 'deviceId': self.device_id})

    if websocket:
      scheme = {'http':'ws', 'https':'wss'}[self.scheme]
      return urlunparse((scheme, self.netloc,path, '', '{params}', '')).format(
        UserId   = self.userid,
        ApiKey   = self.api_key,
        DeviceId = self.device_id,
        params   = urlencode(query)
      )
    else:
      return urlunparse((self.scheme,self.netloc,path,'','{params}','')).format(
        UserId   = self.userid,
        ApiKey   = self.api_key,
        DeviceId = self.device_id,
        params   = urlencode(query)
      )

  def set_on_message(self, func):
    self.ws.on_message = func

  def post(self, path, data={}, **params):
    url = self.get_url(path, **params)
    for i in range(4):
      try:
        return self.session.post(url,
                                json=data,
                                timeout=11,
                                verify=self.ssl
        )
      except exceptions.Timeout:
        if i>= 3:
          raise exceptions.Timeout('Timeout ', url)
      except exceptions.ConnectionError:
        if i>= 3:
          raise exceptions.ConnectionError('Emby server is probably down')


  def getJson(self, path, **query):
    url = self.get_url(path, **query)

    for i in range(4):
      try:
        return self.session.get(url,
                                timeout=11,
                                verify=self.ssl
        ).json()
      except exceptions.Timeout:
        if i>= 3:
          raise exceptions.Timeout('Timeout ', url)
      except exceptions.ConnectionError:
        if i>= 3:
          raise exceptions.ConnectionError('Emby server is probably down')
