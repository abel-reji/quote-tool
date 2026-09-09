const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

function fixture(status, token = "stale-session-token") {
    const redirects = [];
    const response = { status };
    const window = { location: {
        href: "https://quotes.example.test/quote-tool",
        origin: "https://quotes.example.test",
        assign: (path) => redirects.push(path),
    } };
    const context = vm.createContext({
        window, Headers, URL,
        document: { querySelector: () => ({ content: token }) },
        fetch: async () => response,
    });
    vm.runInContext(readFileSync(join(__dirname, "../static/security.js"), "utf8"), context);
    return { window, redirects, response };
}

test("expired background requests redirect the page and reject the operation", async () => {
    const { window, redirects } = fixture(401);
    await assert.rejects(window.quoteFetch("/save-quote", { method: "POST" }), /session expired/);
    assert.deepEqual(redirects, ["/login"]);
});

test("successful requests do not redirect", async () => {
    const { window, redirects, response } = fixture(200);
    assert.equal(await window.quoteFetch("/api/quotes"), response);
    assert.deepEqual(redirects, []);
});

test("desktop mode does not acquire web-login redirects", async () => {
    const { window, redirects, response } = fixture(401, "");
    assert.equal(await window.quoteFetch("/api/quotes"), response);
    assert.deepEqual(redirects, []);
});
