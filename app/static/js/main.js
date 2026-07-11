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

    if (!typeControls.length || !categorySelects.length) {
        continue;
    }

    const updateCategoryOptions = () => {
        const checkedTypeInput = form.querySelector("input[name='type']:checked");
        const checkedType = checkedTypeInput?.dataset.categoryType || checkedTypeInput?.value;
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
    updateCategoryOptions();
}

for (const opener of document.querySelectorAll("[data-dialog-open]")) {
    opener.addEventListener("click", () => {
        const dialog = document.getElementById(opener.dataset.dialogOpen);
        if (dialog?.showModal) {
            dialog.showModal();
            dialog.querySelector("input[name='amount']")?.focus();
        }
    });
}

for (const dialog of document.querySelectorAll("dialog")) {
    for (const closer of dialog.querySelectorAll("[data-dialog-close]")) {
        closer.addEventListener("click", () => dialog.close());
    }
    dialog.addEventListener("click", (event) => {
        if (event.target === dialog) {
            dialog.close();
        }
    });
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
