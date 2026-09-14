from django.utils.cache import patch_cache_control


class NoCacheAuthenticatedPageMiddleware:
    """Prevent protected HTML pages from being restored after logout."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        user = getattr(request, 'user', None)
        content_type = response.get('Content-Type', '')
        is_html = content_type.startswith('text/html')

        if user is not None and user.is_authenticated and is_html:
            patch_cache_control(
                response,
                no_cache=True,
                no_store=True,
                must_revalidate=True,
                private=True,
                max_age=0,
            )
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'

        return response
