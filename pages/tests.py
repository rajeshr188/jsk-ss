from django.test import SimpleTestCase
from django.urls import reverse


class PublicPageTests(SimpleTestCase):
    def test_home_is_branded(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Jai Shri Krishna Jewellery")
        self.assertNotContains(response, "Django starter project")

    def test_about_page(self):
        response = self.client.get(reverse("about"))
        self.assertContains(response, "About our savings scheme")
