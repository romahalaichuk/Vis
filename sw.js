const CACHE_NAME = "cache-v1";
const urlsToCache = [
	"/",
	"/styles.css",
	"/script.js",
	"/img/APPnG1000018783.png",
	"/img/SRpNg5b777339.png",
	"/manifest.json",
];

self.addEventListener("install", (event) => {
	event.waitUntil(
		caches.open(CACHE_NAME).then((cache) => {
			console.log("Opened cache");
			return cache.addAll(urlsToCache);
		})
	);
});

self.addEventListener("fetch", (event) => {
	event.respondWith(
		caches.match(event.request).then((response) => {
			return response || fetch(event.request);
		})
	);
});
