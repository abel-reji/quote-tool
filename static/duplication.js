document.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-duplicate-number]");
    if (!button || button.disabled) return;
    const number = decodeURIComponent(button.dataset.duplicateNumber);
    if (!window.confirm(`Duplicate saved quote ${number}? The copy gets a new number, today's date, and Pending status. Unsaved edits are not included.`)) return;
    button.disabled = true;
    const label = button.textContent;
    button.textContent = "Duplicating...";
    try {
        const response = await quoteFetch(`/api/quotes/${encodeURIComponent(number)}/duplicate`, {method: "POST"});
        const result = await response.json();
        if (!response.ok) throw new Error(result.message || "Unable to duplicate quote.");
        window.location.assign(result.edit_url);
    } catch (error) {
        window.alert(error.message || "Unable to duplicate quote.");
        button.disabled = false;
        button.textContent = label;
    }
});
