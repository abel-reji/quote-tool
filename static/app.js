document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("quoteForm");
    const lineItemsContainer = document.getElementById("lineItemsContainer");
    const addLineItemBtn = document.getElementById("addLineItemBtn");
    const quoteTotalEl = document.getElementById("quoteTotal");
    const lineItemTemplate = document.getElementById("lineItemTemplate");
    const formMessage = document.getElementById("formMessage");
    const saveQuoteBtn = document.getElementById("saveQuoteBtn");
    const config = window.quoteEditorConfig || { editMode: false, quote: null };

    function toNumber(value) {
        const num = parseFloat(value);
        return Number.isFinite(num) ? num : 0;
    }

    function roundToTwo(value) {
        return Math.round((value + Number.EPSILON) * 100) / 100;
    }

    function formatCurrency(value) {
        return `$${roundToTwo(value).toFixed(2)}`;
    }

    function showMessage(type, text) {
        formMessage.className = `form-message ${type}`;
        formMessage.textContent = text;
        formMessage.hidden = false;
        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    function clearMessage() {
        formMessage.hidden = true;
        formMessage.textContent = "";
        formMessage.className = "form-message";
    }

    function renumberLineItems() {
        const rows = lineItemsContainer.querySelectorAll(".line-item");
        rows.forEach((row, index) => {
            const title = row.querySelector(".line-item-title");
            title.textContent = `Line Item ${index + 1}`;
        });
    }

    function updateLineTotal(row) {
        const quantity = toNumber(row.querySelector(".quantity").value);
        const sellPrice = toNumber(row.querySelector(".sell-price").value);
        const lineTotal = quantity * sellPrice;
        row.querySelector(".line-total-display").value = formatCurrency(lineTotal);
        return roundToTwo(lineTotal);
    }

    function updateQuoteTotal() {
        const rows = lineItemsContainer.querySelectorAll(".line-item");
        let total = 0;

        rows.forEach((row) => {
            total += updateLineTotal(row);
        });

        quoteTotalEl.textContent = formatCurrency(total);
    }

    function updateSellPriceFromMargin(row) {
        const netCost = toNumber(row.querySelector(".net-cost").value);
        const grossMarginInput = row.querySelector(".gross-margin");
        const sellPriceInput = row.querySelector(".sell-price");
        const grossMarginPercent = toNumber(grossMarginInput.value);

        if (netCost <= 0 || grossMarginPercent <= 0) {
            sellPriceInput.value = "";
            updateLineTotal(row);
            updateQuoteTotal();
            return;
        }

        const marginDecimal = grossMarginPercent / 100;

        if (marginDecimal >= 1) {
            sellPriceInput.value = "";
            updateLineTotal(row);
            updateQuoteTotal();
            return;
        }

        const sellPrice = netCost / (1 - marginDecimal);
        sellPriceInput.value = roundToTwo(sellPrice).toFixed(2);

        updateLineTotal(row);
        updateQuoteTotal();
    }

    function updateMarginFromSellPrice(row) {
        const netCost = toNumber(row.querySelector(".net-cost").value);
        const sellPrice = toNumber(row.querySelector(".sell-price").value);
        const grossMarginInput = row.querySelector(".gross-margin");

        if (netCost <= 0 || sellPrice <= 0) {
            grossMarginInput.value = "";
            updateLineTotal(row);
            updateQuoteTotal();
            return;
        }

        const grossMarginPercent = ((sellPrice - netCost) / sellPrice) * 100;
        grossMarginInput.value = roundToTwo(grossMarginPercent).toFixed(2);

        updateLineTotal(row);
        updateQuoteTotal();
    }

    function handleNetCostChange(row) {
        const lastEditedPricingField = row.dataset.lastEditedPricingField || "";

        if (lastEditedPricingField === "margin") {
            updateSellPriceFromMargin(row);
        } else if (lastEditedPricingField === "sell_price") {
            updateMarginFromSellPrice(row);
        } else {
            updateLineTotal(row);
            updateQuoteTotal();
        }
    }

    function attachRowListeners(row) {
        const quantityInput = row.querySelector(".quantity");
        const netCostInput = row.querySelector(".net-cost");
        const sellPriceInput = row.querySelector(".sell-price");
        const grossMarginInput = row.querySelector(".gross-margin");
        const removeBtn = row.querySelector(".remove-line-item-btn");

        grossMarginInput.addEventListener("input", () => {
            row.dataset.lastEditedPricingField = "margin";
            updateSellPriceFromMargin(row);
        });

        sellPriceInput.addEventListener("input", () => {
            row.dataset.lastEditedPricingField = "sell_price";
            updateMarginFromSellPrice(row);
        });

        netCostInput.addEventListener("input", () => {
            handleNetCostChange(row);
        });

        quantityInput.addEventListener("input", () => {
            updateLineTotal(row);
            updateQuoteTotal();
        });

        removeBtn.addEventListener("click", () => {
            row.remove();
            renumberLineItems();
            updateQuoteTotal();
        });
    }

    function populateRow(row, item = {}) {
        row.querySelector(".item-name").value = item.item_name || "";
        row.querySelector(".item-description").value = item.item_description || "";
        row.querySelector(".item-long-description").value = item.item_long_description || "";
        row.querySelector(".quantity").value = item.quantity ?? 1;
        row.querySelector(".net-cost").value = item.net_cost_each ?? "";
        row.querySelector(".sell-price").value = item.sell_price_each ?? "";
        row.querySelector(".gross-margin").value = item.gross_margin_percent ?? "";
        row.querySelector(".lead-time").value = item.lead_time || "";
        updateLineTotal(row);
    }

    function createLineItemRow(item = null) {
        const fragment = lineItemTemplate.content.cloneNode(true);
        const row = fragment.querySelector(".line-item");
        row.dataset.lastEditedPricingField = "";
        attachRowListeners(row);
        lineItemsContainer.appendChild(row);
        if (item) {
            populateRow(row, item);
        }
        renumberLineItems();
        updateQuoteTotal();
    }

    function collectLineItems() {
        const rows = lineItemsContainer.querySelectorAll(".line-item");

        return Array.from(rows).map((row) => ({
            item_name: row.querySelector(".item-name").value.trim(),
            item_description: row.querySelector(".item-description").value.trim(),
            item_long_description: row.querySelector(".item-long-description").value.trim(),
            quantity: Number(row.querySelector(".quantity").value || 0),
            net_cost_each: Number(row.querySelector(".net-cost").value || 0),
            sell_price_each: Number(row.querySelector(".sell-price").value || 0),
            gross_margin_percent: Number(row.querySelector(".gross-margin").value || 0),
            lead_time: row.querySelector(".lead-time").value.trim()
        }));
    }

    function validateLineItems(lineItems) {
        if (lineItems.length === 0) {
            throw new Error("At least one line item is required.");
        }

        for (let i = 0; i < lineItems.length; i++) {
            const item = lineItems[i];
            const lineNumber = i + 1;

            if (!item.item_name) {
                throw new Error(`Line Item ${lineNumber}: Item Name is required.`);
            }

            if (!item.quantity || item.quantity <= 0) {
                throw new Error(`Line Item ${lineNumber}: Quantity must be greater than zero.`);
            }

            if (item.net_cost_each < 0) {
                throw new Error(`Line Item ${lineNumber}: Net Cost cannot be negative.`);
            }

            if (item.sell_price_each <= 0 && item.gross_margin_percent <= 0) {
                throw new Error(`Line Item ${lineNumber}: Enter either Sell Price or Gross Margin.`);
            }
        }
    }

    addLineItemBtn.addEventListener("click", () => {
        clearMessage();
        createLineItemRow();
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        clearMessage();

        try {
            const lineItems = collectLineItems();
            validateLineItems(lineItems);

            const selectedDisposition = document.querySelector('input[name="disposition"]:checked');

            const payload = {
                branch_id: document.getElementById("branchId").value,
                customer: document.getElementById("customer").value.trim(),
                customer_contact: document.getElementById("customerContact").value.trim(),
                customer_email: document.getElementById("customerEmail").value.trim(),
                project_description: document.getElementById("projectDescription").value.trim(),
                disposition: selectedDisposition ? selectedDisposition.value : "pending",
                line_items: lineItems
            };

            const endpoint = config.editMode && config.quote
                ? `/update-quote/${encodeURIComponent(config.quote.quote_number)}`
                : "/save-quote";
            const method = config.editMode ? "PUT" : "POST";

            saveQuoteBtn.disabled = true;
            saveQuoteBtn.textContent = config.editMode ? "Updating Quote..." : "Saving Quote...";

            const response = await fetch(endpoint, {
                method,
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            });

            const rawText = await response.text();

            let result;
            try {
                result = JSON.parse(rawText);
            } catch (parseError) {
                console.error("Server did not return JSON:");
                console.error(rawText);
                throw new Error("Server returned invalid response. Check Flask terminal for details.");
            }

            if (!response.ok) {
                throw new Error(result.message || "Failed to save quote.");
            }

            showMessage(
                "success",
                `${config.editMode ? "Quote updated" : "Quote saved"}: ${result.quote_number}. Total: ${formatCurrency(Number(result.quote_total))}`
            );

            if (!config.editMode && result.edit_url) {
                window.history.replaceState({}, "", result.edit_url);
            }

            window.open(result.pdf_url, "_blank");
        } catch (error) {
            console.error("Error saving quote:", error);
            showMessage("error", error.message);
        } finally {
            saveQuoteBtn.disabled = false;
            saveQuoteBtn.textContent = config.editMode ? "Update Quote & Open PDF" : "Save Quote & Open PDF";
        }
    });

    if (config.editMode && config.quote && Array.isArray(config.quote.line_items) && config.quote.line_items.length) {
        config.quote.line_items.forEach((item) => createLineItemRow(item));
    } else {
        createLineItemRow();
    }
});