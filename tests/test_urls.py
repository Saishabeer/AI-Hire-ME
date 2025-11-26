from django.test import SimpleTestCase
from django.urls import resolve, reverse


class URLResolveTests(SimpleTestCase):
    def test_home_url_resolves(self):
        url = reverse("home")
        resolver = resolve(url)
        # Ensure we have a callable view
        self.assertTrue(callable(resolver.func))

    def test_interviews_list_resolves(self):
        url = reverse("interviews:list")
        resolver = resolve(url)
        self.assertTrue(callable(resolver.func))

    def test_interviews_create_resolves(self):
        url = reverse("interviews:create")
        resolver = resolve(url)
        self.assertTrue(callable(resolver.func))

    def test_realtime_session_route_resolves(self):
        url = reverse("interviews:ai_interview_realtime_session")
        resolver = resolve(url)
        self.assertTrue(callable(resolver.func))
