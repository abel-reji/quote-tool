document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("quoteForm");
    const lineItemsContainer = document.getElementById("lineItemsContainer");
    const addLineItemBtn = document.getElementById("addLineItemBtn");
    const quoteTotalEl = document.getElementById("quoteTotal");
    const lineItemTemplate = document.getElementById("lineItemTemplate");
    const formMessage = document.getElementById("formMessage");
    const saveQuoteBtn = document.getElementById("saveQuoteBtn");
    const deleteQuoteBtn = document.getElementById("deleteQuoteBtn");
    const existingQuoteNumberInput = document.getElementById("existingQuoteNumber");
    const editableQuoteNumberInput = document.getElementById("quoteNumber");
    const dateCreatedInput = document.getElementById("dateCreated");
    let currentQuoteNumber = existingQuoteNumberInput?.value?.trim() || "";
    const isEditMode = Boolean(currentQuoteNumber);
    const config = window.quoteEditorConfig || { editMode: false, entryMode: "app", quote: null };
    const entryMode = config.entryMode || "app";
    const isP21Mode = entryMode === "p21";
    const DRAFT_KEY = `quoteToolDraftData:${entryMode}`;

    function parseNumericValue(value) {
        if (value === null || value === undefined) return 0;
        const cleaned = String(value).replace(/[^0-9.-]/g, "");
        if (!cleaned || cleaned === "-" || cleaned === "." || cleaned === "-.") return 0;
        const num = parseFloat(cleaned);
        return Number.isFinite(num) ? num : 0;
    }

    function roundToTwo(value) {
        return Math.round((value + Number.EPSILON) * 100) / 100;
    }

    function formatCurrency(value) {
        const number = parseNumericValue(value);
        return "$" + roundToTwo(number).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function formatPercent(value) {
        const number = parseNumericValue(value);
        if (!Number.isFinite(number) || number === 0) return "";
        return roundToTwo(number).toFixed(2);
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

    function formatCurrencyInputsInRow(row) {
        const netCostInput = row.querySelector(".net-cost");
        const sellPriceInput = row.querySelector(".sell-price");

        if (netCostInput && netCostInput.value.trim() !== "") {
            netCostInput.value = formatCurrency(netCostInput.value);
        }

        if (sellPriceInput && sellPriceInput.value.trim() !== "") {
            sellPriceInput.value = formatCurrency(sellPriceInput.value);
        }
    }

    function updateLineTotal(row) {
        const quantity = parseNumericValue(row.querySelector(".quantity").value);
        const sellPrice = parseNumericValue(row.querySelector(".sell-price").value);
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
        const netCost = parseNumericValue(row.querySelector(".net-cost").value);
        const grossMarginInput = row.querySelector(".gross-margin");
        const sellPriceInput = row.querySelector(".sell-price");
        const grossMarginPercent = parseNumericValue(grossMarginInput.value);

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
        sellPriceInput.value = formatCurrency(sellPrice);

        updateLineTotal(row);
        updateQuoteTotal();
    }

    function updateMarginFromSellPrice(row) {
        const netCost = parseNumericValue(row.querySelector(".net-cost").value);
        const sellPrice = parseNumericValue(row.querySelector(".sell-price").value);
        const grossMarginInput = row.querySelector(".gross-margin");

        if (netCost <= 0 || sellPrice <= 0) {
            grossMarginInput.value = "";
            updateLineTotal(row);
            updateQuoteTotal();
            return;
        }

        const grossMarginPercent = ((sellPrice - netCost) / sellPrice) * 100;
        grossMarginInput.value = formatPercent(grossMarginPercent);

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

    function attachCurrencyFieldBehavior(input, onInputCallback) {
        input.addEventListener("focus", () => {
            input.value = input.value.replace(/[^0-9.-]/g, "");
        });

        input.addEventListener("input", () => {
            if (typeof onInputCallback === "function") {
                onInputCallback();
            }
        });

        input.addEventListener("blur", () => {
            const numericValue = parseNumericValue(input.value);
            if (input.value.trim() === "" || numericValue === 0) {
                input.value = "";
            } else {
                input.value = formatCurrency(numericValue);
            }
        });
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

        attachCurrencyFieldBehavior(sellPriceInput, () => {
            row.dataset.lastEditedPricingField = "sell_price";
            updateMarginFromSellPrice(row);
        });

        attachCurrencyFieldBehavior(netCostInput, () => {
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
            saveDraft();
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

        formatCurrencyInputsInRow(row);
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
        } else {
            updateLineTotal(row);
        }

        renumberLineItems();
        updateQuoteTotal();
        return row;
    }

    function collectLineItems() {
        const rows = lineItemsContainer.querySelectorAll(".line-item");

        return Array.from(rows).map((row) => ({
            item_name: row.querySelector(".item-name").value.trim(),
            item_description: row.querySelector(".item-description").value.trim(),
            item_long_description: row.querySelector(".item-long-description").value.trim(),
            quantity: Number(row.querySelector(".quantity").value || 0),
            net_cost_each: parseNumericValue(row.querySelector(".net-cost").value),
            sell_price_each: parseNumericValue(row.querySelector(".sell-price").value),
            gross_margin_percent: parseNumericValue(row.querySelector(".gross-margin").value),
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

    function saveDraft() {
        if (isEditMode) return;

        const lineItems = collectLineItems();
        const selectedDisposition = document.querySelector('input[name="disposition"]:checked');

        const draftData = {
            entry_type: entryMode,
            branch_id: document.getElementById("branchId").value,
            quote_number: editableQuoteNumberInput ? editableQuoteNumberInput.value : "",
            date_created: dateCreatedInput ? dateCreatedInput.value : "",
            customer: document.getElementById("customer").value,
            customer_contact: document.getElementById("customerContact").value,
            customer_email: document.getElementById("customerEmail").value,
            project_description: document.getElementById("projectDescription").value,
            disposition: selectedDisposition ? selectedDisposition.value : "pending",
            line_items: lineItems
        };

        localStorage.setItem(DRAFT_KEY, JSON.stringify(draftData));
    }

    function clearDraft() {
        localStorage.removeItem(DRAFT_KEY);
    }

    function loadDraft() {
        if (isEditMode) return false;

        const draftJson = localStorage.getItem(DRAFT_KEY);
        if (!draftJson) return false;

        try {
            const draftData = JSON.parse(draftJson);

            if (draftData.branch_id) document.getElementById("branchId").value = draftData.branch_id;
            if (editableQuoteNumberInput && draftData.quote_number) editableQuoteNumberInput.value = draftData.quote_number;
            if (dateCreatedInput && draftData.date_created) dateCreatedInput.value = draftData.date_created;
            if (draftData.customer) document.getElementById("customer").value = draftData.customer;
            if (draftData.customer_contact) document.getElementById("customerContact").value = draftData.customer_contact;
            if (draftData.customer_email) document.getElementById("customerEmail").value = draftData.customer_email;
            if (draftData.project_description) document.getElementById("projectDescription").value = draftData.project_description;

            if (draftData.disposition) {
                const radio = document.querySelector(`input[name="disposition"][value="${draftData.disposition}"]`);
                if (radio) radio.checked = true;
            }

            if (draftData.line_items && Array.isArray(draftData.line_items) && draftData.line_items.length > 0) {
                lineItemsContainer.innerHTML = "";
                draftData.line_items.forEach((item) => createLineItemRow(item));
            }

            return true;
        } catch (e) {
            console.error("Failed to parse draft data", e);
            clearDraft();
            return false;
        }
    }

    form.addEventListener("input", () => {
        saveDraft();
    });

    addLineItemBtn.addEventListener("click", () => {
        clearMessage();
        const newRow = createLineItemRow();
        saveDraft();
        newRow.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        clearMessage();

        try {
            const lineItems = collectLineItems();
            validateLineItems(lineItems);

            const selectedDisposition = document.querySelector('input[name="disposition"]:checked');

            const payload = {
                entry_type: entryMode,
                branch_id: document.getElementById("branchId").value,
                customer: document.getElementById("customer").value.trim(),
                customer_contact: document.getElementById("customerContact").value.trim(),
                customer_email: document.getElementById("customerEmail").value.trim(),
                project_description: document.getElementById("projectDescription").value.trim(),
                disposition: selectedDisposition ? selectedDisposition.value : "pending",
                line_items: lineItems
            };

            if (isEditMode && editableQuoteNumberInput) {
                payload.quote_number = editableQuoteNumberInput.value.trim();
            }

            if ((isEditMode || isP21Mode) && editableQuoteNumberInput && !editableQuoteNumberInput.value.trim()) {
                throw new Error("Quote number is required.");
            }

            if ((isEditMode || isP21Mode) && dateCreatedInput) {
                if (!dateCreatedInput.value) {
                    throw new Error("Date created is required.");
                }
                payload.date_created = dateCreatedInput.value;
            }

            if (isP21Mode && editableQuoteNumberInput) {
                payload.quote_number = editableQuoteNumberInput.value.trim();
            }

            const formData = new FormData();
            formData.append("data", JSON.stringify(payload));

            const fileInput = document.getElementById("quoteAttachments");
            if (fileInput && fileInput.files.length > 0) {
                Array.from(fileInput.files).forEach((file) => {
                    formData.append("attachments", file);
                });
            }

            const endpoint = isEditMode
                ? `/update-quote/${encodeURIComponent(currentQuoteNumber)}`
                : "/save-quote";
            const method = isEditMode ? "PUT" : "POST";

            saveQuoteBtn.disabled = true;
            saveQuoteBtn.textContent = isEditMode ? "Updating Quote..." : "Saving Quote...";

            const response = await fetch(endpoint, {
                method,
                body: formData
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
                `${isEditMode ? "Quote updated" : "Quote saved"}: ${result.quote_number}. Total: ${formatCurrency(result.quote_total)}`
            );

            if (result.edit_url) {
                if (isEditMode) {
                    currentQuoteNumber = result.quote_number;
                    if (existingQuoteNumberInput) {
                        existingQuoteNumberInput.value = result.quote_number;
                    }
                    if (editableQuoteNumberInput) {
                        editableQuoteNumberInput.value = result.quote_number;
                    }
                } else {
                    clearDraft();
                }

                window.history.replaceState({}, "", result.edit_url);
            }

            window.open(result.pdf_url, "_blank");
        } catch (error) {
            console.error("Error saving quote:", error);
            showMessage("error", error.message);
        } finally {
            saveQuoteBtn.disabled = false;
            saveQuoteBtn.textContent = isEditMode ? "Update Quote & Open PDF" : "Save Quote & Open PDF";
        }
    });

    if (deleteQuoteBtn && currentQuoteNumber) {
        deleteQuoteBtn.addEventListener("click", async () => {
            const confirmed = window.confirm(
                `Delete quote ${currentQuoteNumber}? This cannot be undone.`
            );

            if (!confirmed) {
                return;
            }

            try {
                deleteQuoteBtn.disabled = true;
                deleteQuoteBtn.textContent = "Deleting...";

                const response = await fetch(
                    `/delete-quote/${encodeURIComponent(currentQuoteNumber)}`,
                    { method: "DELETE" }
                );

                const result = await response.json();

                if (!response.ok) {
                    throw new Error(result.message || "Failed to delete quote.");
                }

                clearDraft();
                window.location.href = result.redirect_url || "/";
            } catch (error) {
                console.error("Error deleting quote:", error);
                showMessage("error", error.message);
                deleteQuoteBtn.disabled = false;
                deleteQuoteBtn.textContent = "Delete Quote";
            }
        });
    }

    if (isEditMode && config.quote && Array.isArray(config.quote.line_items) && config.quote.line_items.length) {
        config.quote.line_items.forEach((item) => createLineItemRow(item));
    } else {
        const hasDraft = loadDraft();
        if (!hasDraft) {
            createLineItemRow();
        }
    }
});
