const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

async function fixture(count, options = {}) {
    const elements = {};
    let ready;
    const document = {
        getElementById(id) {
            return elements[id] ||= {
                value: id === "dispositionFilter" ? "all" : "", hidden: true, disabled: false, innerHTML: "", textContent: "",
                handlers: {}, addEventListener(name, fn) { this.handlers[name] = fn; },
                setAttribute() {}, contains() { return false; }, scrollIntoView() {}, querySelectorAll() { return []; },
            };
        },
        createElement() { return { set textContent(value) { this.innerHTML = value; } }; },
        addEventListener(name, fn) { if (name === "DOMContentLoaded") ready = fn; },
    };
    const quotes = Array.from({ length: count }, (_, index) => ({
        quote_number: `Q${index + 1}`, customer: index >= 25 ? "Later Customer" : "First Customer",
        project_description: "Pump", date_created: "2026-09-18", line_item_count: 1,
        disposition: options.mixed ? ["pending", "won", "lost"][index % 3] : "pending",
    }));
    const html = readFileSync(join(__dirname, "../templates/landing.html"), "utf8");
    const code = html.match(/<script nonce="[^"]*">([\s\S]*?)<\/script>/)[1];
    const requests = [];
    const timers = new Map();
    let timerId = 0;
    vm.runInNewContext(code, { document, setTimeout: fn => { timers.set(++timerId, fn); return timerId; }, clearTimeout: id => timers.delete(id), quoteFetch: async (url, request) => {
        if (request) {
            requests.push({url, ...request});
            if (options.wait) await options.wait;
            return {ok: !options.updateError, json: async () => options.updateError
                ? {message: "Save failed"} : JSON.parse(request.body)};
        }
        if (options.error) throw new Error("Offline");
        return { ok: true, json: async () => ({ quotes }) };
    } });
    await ready();
    const click = (id) => elements[id].handlers.click();
    const search = (term) => {
        elements.quoteSearch.value = term;
        elements.quoteSearch.handlers.input();
    };
    const visible = () => (elements.quoteList.innerHTML.match(/class="quote-list-entry"/g) || []).length;
    const filter = (status) => {
        elements.dispositionFilter.handlers.click({target: {closest: () => ({dataset: {filter: status}})}});
    };
    const update = (number, value) => {
        const select = {value, dataset: {statusNumber: encodeURIComponent(number)}};
        return elements.quoteList.handlers.change({target: {closest: () => select}});
    };
    return { elements, click, search, visible, filter, update, requests, timers };
}

test("pages contain at most 25 quotes with correct boundary controls", async () => {
    const { elements: e, click, visible } = await fixture(51);
    assert.equal(visible(), 25);
    assert.equal(e.quotePreviousPage.disabled, true);
    assert.match(e.quotePageStatus.textContent, /1-25 of 51/);
    click("quoteNextPage");
    assert.equal(visible(), 25);
    assert.match(e.quotePageStatus.textContent, /26-50 of 51/);
    click("quoteNextPage");
    assert.equal(visible(), 1);
    assert.equal(e.quoteNextPage.disabled, true);
    click("quoteNextPage");
    assert.equal(visible(), 1);
    click("quotePreviousPage");
    assert.equal(visible(), 25);
});

test("search covers all quotes and resets pagination", async () => {
    const { elements: e, click, search, visible } = await fixture(78);
    click("quoteNextPage");
    search("Later Customer");
    assert.equal(visible(), 25);
    assert.match(e.quotePageStatus.textContent, /1-25 of 53/);
    assert.equal(e.quotePreviousPage.disabled, true);
    search("Q78");
    assert.equal(visible(), 1);
    assert.match(e.quoteList.innerHTML, /Q78/);
    search("missing");
    assert.equal(e.quoteList.hidden, true);
    assert.equal(e.quotePagination.hidden, true);
    search("");
    assert.equal(visible(), 25);
    assert.match(e.quotePageStatus.textContent, /1-25 of 78/);
});

test("empty, one-page, and exact-page lists have no extra pages", async () => {
    for (const count of [0, 1, 25]) {
        const { elements: e, visible } = await fixture(count);
        assert.equal(visible(), count);
        assert.equal(e.quoteNextPage.disabled, true);
        assert.equal(e.quotePreviousPage.disabled, true);
        assert.equal(e.quotePagination.hidden, count === 0);
    }
});

test("load errors leave pagination hidden", async () => {
    const { elements: e } = await fixture(51, { error: true });
    assert.equal(e.quotePagination.hidden, true);
    assert.equal(e.quoteList.hidden, true);
    assert.equal(e.quoteListState.textContent, "Offline");
});

test("disposition filters combine with search and reset the page", async () => {
    const f = await fixture(90, {mixed: true});
    f.click("quoteNextPage");
    f.filter("won");
    assert.equal(f.visible(), 25);
    assert.match(f.elements.quotePageStatus.textContent, /1-25 of 30/);
    f.search("First Customer");
    assert.equal(f.visible(), 8);
    f.filter("lost");
    assert.equal(f.visible(), 8);
    f.filter("all");
    assert.equal(f.visible(), 25);
});

test("quick updates patch only disposition and clamp an emptied last page", async () => {
    const f = await fixture(26);
    f.filter("pending");
    f.click("quoteNextPage");
    await f.update("Q26", "won");
    assert.equal(f.requests[0].url, "/api/quotes/Q26/disposition");
    assert.equal(f.requests[0].method, "PATCH");
    assert.deepEqual(JSON.parse(f.requests[0].body), {disposition: "won"});
    assert.match(f.elements.quotePageStatus.textContent, /1-25 of 25/);
    f.filter("won");
    assert.equal(f.visible(), 1);
    assert.match(f.elements.quoteList.innerHTML, /Q26/);
});

test("failed updates preserve saved disposition and show an error", async () => {
    const f = await fixture(1, {updateError: true});
    f.filter("pending");
    await f.update("Q1", "lost");
    assert.equal(f.visible(), 1);
    assert.equal(f.elements.quickDispositionMessage.textContent, "Save failed");
    assert.match(f.elements.quoteList.innerHTML, /value="pending" selected/);
});

test("duplicate updates are blocked while saving, even if filters rerender", async () => {
    let release;
    const wait = new Promise(resolve => { release = resolve; });
    const f = await fixture(1, {wait});
    const pending = f.update("Q1", "won");
    f.filter("pending");
    assert.match(f.elements.quoteList.innerHTML, /data-status-number="Q1" disabled/);
    await f.update("Q1", "lost");
    assert.equal(f.requests.length, 1);
    release();
    await pending;
    assert.equal(f.elements.quoteList.hidden, true);
});

test("dates are readable without shifting the stored calendar day", async () => {
    const f = await fixture(1);
    assert.match(f.elements.quoteList.innerHTML, /Sep 18, 2026/);
    assert.match(f.elements.quoteList.innerHTML, /quote-customer-name/);
});

test("successful feedback disappears but errors remain until dismissed", async () => {
    const f = await fixture(1);
    await f.update("Q1", "won");
    assert.equal(f.elements.quickDispositionFeedback.hidden, false);
    assert.equal(f.timers.size, 1);
    [...f.timers.values()][0]();
    assert.equal(f.elements.quickDispositionFeedback.hidden, true);
    const failed = await fixture(1, {updateError: true});
    await failed.update("Q1", "lost");
    assert.equal(failed.timers.size, 0);
    assert.equal(failed.elements.quickDispositionFeedback.hidden, false);
    failed.click("dismissDispositionFeedback");
    assert.equal(failed.elements.quickDispositionFeedback.hidden, true);
});
