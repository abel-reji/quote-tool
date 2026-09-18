document.addEventListener("DOMContentLoaded", () => {
    const fields = {
        customer: document.getElementById("customer"),
        contact: document.getElementById("customerContact"),
        email: document.getElementById("customerEmail")
    };
    if (!fields.customer) return;
    let records = [];
    const normalize = (value) => value.trim().toLowerCase();
    const widgets = [];
    const changed = (input) => input.dispatchEvent(new Event("input", { bubbles: true }));

    for (const [key, input] of Object.entries(fields)) {
        const wrapper = input.parentElement;
        wrapper.classList.add("suggestion-field");
        input.autocomplete = "off";
        input.setAttribute("role", "combobox");
        input.setAttribute("aria-autocomplete", "list");
        input.setAttribute("aria-expanded", "false");
        const list = document.createElement("div");
        list.id = `${input.id}Suggestions`;
        list.className = "customer-suggestions";
        list.setAttribute("role", "listbox");
        list.setAttribute("aria-label", `Saved ${key} suggestions`);
        list.hidden = true;
        input.setAttribute("aria-controls", list.id);
        wrapper.appendChild(list);
        let active = -1;
        function close() {
            list.hidden = true;
            input.setAttribute("aria-expanded", "false");
            input.removeAttribute("aria-activedescendant");
            active = -1;
        }
        function select(value) {
            input.value = value;
            const matches = records.filter((record) => normalize(record[key]) === normalize(value) &&
                (key === "customer" || !fields.customer.value.trim() || normalize(record.customer) === normalize(fields.customer.value)));
            // Never guess among multiple contacts at the same customer.
            for (const other of Object.keys(fields)) {
                if (other === key) continue;
                const values = [...new Set(matches.map((record) => record[other]).filter(Boolean))];
                if (values.length === 1) fields[other].value = values[0];
                else if (key === "customer" || other !== "customer") fields[other].value = "";
            }
            Object.values(fields).forEach(changed);
            input.focus();
            widgets.forEach((widget) => widget.close());
        }
        function render() {
            close();
            list.replaceChildren();
            const query = normalize(input.value);
            const customer = normalize(fields.customer.value);
            const values = [...new Set(records.filter((record) => key === "customer" || !customer ||
                normalize(record.customer) === customer).map((record) => record[key]).filter((value) =>
                value && normalize(value).includes(query)))].slice(0, 12);
            values.forEach((value, index) => {
                const option = document.createElement("button");
                option.type = "button";
                option.tabIndex = -1;
                option.id = `${list.id}-${index}`;
                option.setAttribute("role", "option");
                option.setAttribute("aria-selected", "false");
                option.textContent = value;
                option.addEventListener("pointerdown", (event) => {
                    if (event.pointerType === "mouse") event.preventDefault();
                });
                option.addEventListener("click", () => select(value));
                list.appendChild(option);
            });
            list.hidden = values.length === 0;
            input.setAttribute("aria-expanded", String(values.length > 0));
        }
        input.addEventListener("focus", render);
        input.addEventListener("input", render);
        wrapper.addEventListener("focusout", (event) => {
            if (!wrapper.contains(event.relatedTarget)) close();
        });
        input.addEventListener("keydown", (event) => {
            if (event.key === "Escape") { close(); return; }
            if (["ArrowDown", "ArrowUp"].includes(event.key)) {
                event.preventDefault();
                if (list.hidden) render();
                const options = [...list.children];
                if (!options.length) return;
                active = (active + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
                options.forEach((option, index) => option.setAttribute("aria-selected", String(index === active)));
                input.setAttribute("aria-activedescendant", options[active].id);
                options[active].scrollIntoView({ block: "nearest" });
            } else if (event.key === "Enter" && !list.hidden && active >= 0) {
                event.preventDefault();
                list.children[active].click();
            }
        });
        widgets.push({ input, close, render });
    }
    document.addEventListener("click", (event) => {
        widgets.forEach((widget) => {
            if (!widget.input.parentElement.contains(event.target)) widget.close();
        });
    });
    quoteFetch("/api/customer-suggestions").then(async (response) => {
        if (!response.ok) throw new Error("Suggestions unavailable");
        records = await response.json();
        widgets.find((widget) => widget.input === document.activeElement)?.render();
    }).catch(() => {
        const note = document.createElement("small");
        note.textContent = "Saved suggestions are unavailable. You can still enter customer details manually.";
        fields.customer.parentElement.appendChild(note);
    });
});
