from django.http import HttpResponsePermanentRedirect
from django.utils.cache import patch_cache_control


class WwwRedirectMiddleware:
    """Send www visitors to the main address.

    Sign-ins belong to one address, so someone signed in at the main address
    would look signed out on the www one. Forms submitted from a www page left
    open keep their data.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host()
        if host.lower().startswith('www.'):
            url = f'{request.scheme}://{host[4:]}{request.get_full_path()}'
            return HttpResponsePermanentRedirect(url, preserve_request=request.method not in ('GET', 'HEAD'))
        return self.get_response(request)


class RevalidateHtmlMiddleware:
    """Tell browsers to re-check HTML pages on every visit.

    Static files carry content hashes in their names, so a deploy changes the
    URLs the pages point to. Without this, a browser may reuse an old copy of
    a page (Django sends no caching headers by default) and keep showing the
    previous images until someone refreshes.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (response.get('Content-Type', '').startswith('text/html')
                and not response.has_header('Cache-Control')):
            patch_cache_control(response, no_cache=True)
        return response
