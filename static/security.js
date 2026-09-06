window.quoteFetch = async function (input, options = {}) {
    const headers = new Headers(options.headers);
    const token = document.querySelector('meta[name="csrf-token"]')?.content;
    const method = (options.method || "GET").toUpperCase();
    const target = new URL(input, window.location.href);
    if (token && target.origin === window.location.origin && !["GET", "HEAD", "OPTIONS"].includes(method)) {
        headers.set("X-CSRF-Token", token);
    }
    const response = await fetch(input, { ...options, headers });
    if (response.status === 401 && token) {
        window.location.assign("/login");
        throw new Error("Your session expired. Please sign in again.");
    }
    return response;
};
