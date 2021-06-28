import tornado
import tornado.gen
from tornado.httpclient import HTTPRequest, AsyncHTTPClient, HTTPError
from tornado.web import RequestHandler
from tornado.websocket import WebSocketHandler, websocket_connect

AsyncHTTPClient.configure(None, defaults={'decompress_response': False})

MAX_RETRIES = 100

class ProxyHandler(RequestHandler):
    def initialize(self, proxy_url='/', **kwargs):
        super(ProxyHandler, self).initialize(**kwargs)
        self.proxy_url = proxy_url

    async def post(self, url=None):
        return await self.handle_req(url)

    async def get(self, url=None):
        return await self.handle_req(url)

    async def handle_req(self, url=None):
        print("INCOMING URL: "+url)
        #url = url or self.proxy_url
        if url is None:
            if self.request.uri.startswith('/'):
                url = self.request.uri[1:]
            else:
                url = self.request.uri

        debug = True
        if url[:6] == 'static' or url[:7] == 'favicon':
            debug = False

        url = self.proxy_url+url

        if debug:
            print("{} : {}".format(self.request.method, url))

        incoming_headers = {}

        for k,v in self.request.headers.items():
            if not k.lower() in ['host', 'pragma', 'upgrade-insecure-requests', 'if-none-match',
                                 'sec-fetch-user', 'sec-fetch-site', 'sec-fetch-mode', 'accept-encoding']:
                # 'accept-encoding', 'accept-language', 'accept', 'cache-control',
                incoming_headers[k] = v

        for field, possible_values in incoming_headers.items():
            print("Incoming Headers {} : {}".format(field, possible_values))

        body = None
        if self.request.method == 'POST':
            body = self.request.body

        req = HTTPRequest(url, headers=incoming_headers, method=self.request.method, body=body)
        client = AsyncHTTPClient()

        response = None
        retries = 0

        while not response and retries < MAX_RETRIES:
            try:
                response = await client.fetch(req)
            except HTTPError as e:
                print("Tornado raised exception : {}".format(e))
                response = None
                retries += 1
                await tornado.gen.sleep(0.3)

            if response.error:
                print(" **** response.error")
                print(response.error)
                if response.code == 599: # Maybe server wasn't yet ready
                    print(" **** response.error 599 ***")
                    response = None
                    retries += 1
                    await tornado.gen.sleep(0.1)

        if not response:
            self.set_status(404)
            self.finish()
            return

        if debug:
            print(incoming_headers)

            print(response)

            print(response.headers)

            print(response.code)

        self.set_status(response.code)
        if response.code != 200:
            self.finish()
        else:
            if response.body:
                if debug:
                    print("response body")
                for header, v in response.headers.get_all():
                    if header.lower() == 'content-length':
                        self.set_header(header, str(max(len(response.body), int(v))))
                    else:
                        self.set_header(header, v)

            self.write(response.body)

            self.finish()


class ProxyWSHandler(WebSocketHandler):
    def initialize(self, proxy_url='/', **kwargs):
        super(ProxyWSHandler, self).initialize(**kwargs)
        self.proxy_url = proxy_url
        self.ws = None
        self.closed = True

    async def open(self, url=None):
        self.closed = False
        #url = url or self.proxy_url
        if url is None:
            if self.request.uri.startswith('/'):
                url = self.request.uri[1:]
            else:
                url = self.request.uri
        url = self.proxy_url+url

        def write(msg):
            if self.closed or msg is None:
                if self.ws:
                    self.ws.close()
                    self.ws = None
            else:
                if self.ws:
                    self.write_message(msg, binary=isinstance(msg, bytes))

        if url[:4] == 'http':
            url = 'ws' + url[4:]

        print("WEBSOCKET OPENING ON "+url)
        self.ws = await websocket_connect(url, on_message_callback=write)

    async def on_message(self, message):
        if self.ws:
            await self.ws.write_message(message, binary=isinstance(message, bytes))

    def on_close(self):
        if self.ws:
            self.ws.close()
            self.ws = None
            self.closed = True
