from django.utils.cache import patch_cache_control


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
