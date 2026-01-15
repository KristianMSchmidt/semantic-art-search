from django.conf import settings
from django.utils import translation


class SessionLanguageMiddleware:
    """
    Middleware that activates the language stored in the user's session.

    Django's LocaleMiddleware checks Accept-Language header and URL prefix,
    but we use session-based language selection. This middleware activates
    the translation based on the session value.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        language = request.session.get(settings.LANGUAGE_SESSION_KEY, "en")
        if language in dict(settings.LANGUAGES):
            translation.activate(language)
            request.LANGUAGE_CODE = language
        response = self.get_response(request)
        return response
