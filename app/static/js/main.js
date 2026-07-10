const confirmationForms = document.querySelectorAll("form[data-confirm]");

for (const form of confirmationForms) {
    form.addEventListener("submit", (event) => {
        const message = form.dataset.confirm || "Подтвердите действие";
        if (!window.confirm(message)) {
            event.preventDefault();
        }
    });
}

const categoryForms = document.querySelectorAll("form");

for (const form of categoryForms) {
    const typeControls = form.querySelectorAll(
        "[data-category-type-controls] input[name='type']",
    );
    const categorySelects = form.querySelectorAll(
        "[data-category-select], [data-parent-category-select]",
    );
    const scopeControls = form.querySelectorAll("[data-scope-controls] input[name='scope']");
    const expenseSourceControls = form.querySelectorAll("input[name='expense_source']");

    if (!typeControls.length || !categorySelects.length) {
        continue;
    }

    const updateCategoryOptions = () => {
        const checkedTypeInput = form.querySelector("input[name='type']:checked");
        const expenseSource = form.querySelector("input[name='expense_source']:checked")?.value;
        const checkedType = checkedTypeInput?.value === "expense" && expenseSource === "savings"
            ? "savings"
            : checkedTypeInput?.dataset.categoryType || checkedTypeInput?.value;
        const checkedScope = form.querySelector("input[name='scope']:checked")?.value
            || form.querySelector("input[name='scope'][type='hidden']")?.value;
        if (!checkedType) {
            return;
        }

        for (const select of categorySelects) {
            for (const option of select.options) {
                const optionType = option.dataset.categoryType;
                const optionScope = option.dataset.categoryScope;
                const typeAllowed = !optionType || optionType === checkedType;
                const scopeAllowed = !optionScope || !checkedScope || optionScope === checkedScope;
                const allowed = typeAllowed && scopeAllowed;
                option.hidden = !allowed;
                option.disabled = !allowed;

                if (!allowed && option.selected) {
                    select.value = "";
                }
            }
        }
    };

    for (const control of typeControls) {
        control.addEventListener("change", updateCategoryOptions);
    }
    for (const control of scopeControls) {
        control.addEventListener("change", updateCategoryOptions);
    }
    for (const control of expenseSourceControls) {
        control.addEventListener("change", updateCategoryOptions);
    }
    updateCategoryOptions();
}

for (const form of document.querySelectorAll("[data-transaction-form]")) {
    const sourceBlock = form.querySelector("[data-expense-source]");
    const typeInputs = form.querySelectorAll("input[name='type']");
    const updateSource = () => {
        const type = form.querySelector("input[name='type']:checked")?.value;
        sourceBlock.hidden = type !== "expense";
    };
    for (const input of typeInputs) {
        input.addEventListener("change", updateSource);
    }
    updateSource();
}

for (const form of document.querySelectorAll("[data-analytics-filter]")) {
    const periodSelect = form.querySelector("[data-period-select]");
    const customDates = form.querySelectorAll("[data-custom-date]");
    const updateCustomDates = () => {
        const custom = periodSelect.value === "custom";
        for (const field of customDates) {
            field.hidden = !custom;
        }
    };
    periodSelect.addEventListener("change", updateCustomDates);
    updateCustomDates();
}

for (const flash of document.querySelectorAll(".flash")) {
    window.setTimeout(() => {
        flash.classList.add("is-leaving");
        window.setTimeout(() => flash.remove(), 260);
    }, 6000);
}
