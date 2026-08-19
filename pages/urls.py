from django.urls import path

from .views import AboutPageView, HomePageView, live_health, ready_health

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("about/", AboutPageView.as_view(), name="about"),
    path("health/live/", live_health, name="health_live"),
    path("health/ready/", ready_health, name="health_ready"),
]
