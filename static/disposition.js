document.addEventListener("DOMContentLoaded", () => {
    const button = document.getElementById("updateDispositionBtn");
    if (!button) return;
    const message = document.getElementById("dispositionMessage");
    const radios = [...document.querySelectorAll('input[name="disposition"]')];

    radios.forEach((radio) => radio.addEventListener("change", () => { message.hidden = true; }));
    button.addEventListener("click", async () => {
        if (button.disabled) return;
        // Use the saved identifier, not a quote number the user has edited but not saved.
        const number = document.getElementById("existingQuoteNumber")?.value?.trim();
        const disposition = radios.find((radio) => radio.checked)?.value;
        if (!number || !disposition) return;
        const controls = [button, ...radios, document.getElementById("saveQuoteBtn"),
            document.getElementById("deleteQuoteBtn")].filter(Boolean);
        const previousStates = controls.map((control) => control.disabled);
        controls.forEach((control) => { control.disabled = true; });
        button.textContent = "Updating...";
        message.hidden = true;
        try {
            const response = await quoteFetch(`/api/quotes/${encodeURIComponent(number)}/disposition`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ disposition }),
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || "Could not update disposition.");
            if (window.quoteEditorConfig?.quote) window.quoteEditorConfig.quote.disposition = result.disposition;
            message.className = "form-message success";
            message.textContent = `Disposition updated to ${result.disposition}. Other edits have not been saved.`;
        } catch (error) {
            message.className = "form-message error";
            message.textContent = error.message || "Could not update disposition. Please try again.";
        } finally {
            message.hidden = false;
            button.textContent = "Update Disposition";
            controls.forEach((control, index) => { control.disabled = previousStates[index]; });
        }
    });
});
