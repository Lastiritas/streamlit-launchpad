from tornado.httpclient import AsyncHTTPClient
import tornado.gen

class RetryClient:
    def __init__(
        self,
        retry_start_timeout = 0.1,
        retry_attempts = 5,
        retry_factor = 2,
    ):
        self.retry_start_timeout = retry_start_timeout
        self.retry_attempts = retry_attempts
        self.retry_factor = retry_factor

        self.http_client = AsyncHTTPClient()
    
    def fetch(self, http_request):
        return self._handle_retries(http_request)
    
    def _calculate_backoff_time(self, attempt):
        return self.retry_start_timeout * self.retry_factor * attempt

    async def _handle_retries(self, http_request):
        attempt = 1
        response = None
        while response is None and attempt < self.retry_attempts:
            response = await self._handle_request(http_request, attempt)
            attempt += 1
            await tornado.gen.sleep(self._calculate_backoff_time(attempt))
        return response
    
    async def _handle_request(self, http_request, attempt):
        try:
            print("Fetching url: %s (Attempt %s of %s)" %(http_request.url, attempt, self.retry_attempts))
            return await self.http_client.fetch(http_request)
        except Exception as e:
            print("Exception raised: %s" % e)
            return None
