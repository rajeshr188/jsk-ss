{% load static %}
"use strict";

const CACHE_PREFIX = "jsk-pwa-static-";
const CACHE_NAME = `${CACHE_PREFIX}{{ app_release|escapejs }}`;
const OFFLINE_URL = "{% url 'pwa_offline' %}";
const PRECACHE_URLS = [
  OFFLINE_URL,
  "{% static 'images/pwa-icon-192.png' %}",
  "{% static 'images/pwa-icon-512.png' %}",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names
          .filter((name) => name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;

  // Financial mutations and subresources always remain browser/network-owned.
  // Navigations are fetched without HTTP-cache reuse and no response is cached.
  if (request.method !== "GET" || request.mode !== "navigate") {
    return;
  }

  event.respondWith(
    fetch(request, { cache: "no-store" }).catch(async () => {
      const fallback = await caches.match(OFFLINE_URL, { cacheName: CACHE_NAME });
      return fallback || new Response("Connection required. Nothing was submitted.", {
        status: 503,
        headers: { "Content-Type": "text/plain; charset=utf-8" },
      });
    })
  );
});
