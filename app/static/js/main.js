const confirmationForms = document.querySelectorAll("form[data-confirm]");

for (const element of document.querySelectorAll("[data-category-color]")) {
    const color = element.dataset.categoryColor;
    if (/^#[0-9a-f]{6}$/i.test(color)) {
        element.style.setProperty("--category-color", color);
    }
}

for (const bar of document.querySelectorAll("[data-bar-width]")) {
    const width = Number.parseFloat(bar.dataset.barWidth);
    if (Number.isFinite(width)) {
        bar.style.width = `${Math.min(100, Math.max(0, width))}%`;
    }
}

const formatRussianPhone = (input) => {
    const digits = input.value.replace(/\D/g, "");
    let subscriber = digits;
    if (digits.startsWith("7") || (digits.startsWith("8") && digits.length > 10)) {
        subscriber = digits.slice(1);
    }
    subscriber = subscriber.slice(0, 10);

    let formatted = "+7";
    if (subscriber.length) formatted += ` ${subscriber.slice(0, 3)}`;
    if (subscriber.length > 3) formatted += ` ${subscriber.slice(3, 6)}`;
    if (subscriber.length > 6) formatted += `-${subscriber.slice(6, 8)}`;
    if (subscriber.length > 8) formatted += `-${subscriber.slice(8, 10)}`;
    input.value = formatted;
};

for (const phoneInput of document.querySelectorAll("[data-russian-phone]")) {
    formatRussianPhone(phoneInput);
    phoneInput.addEventListener("focus", () => {
        if (!phoneInput.value) phoneInput.value = "+7";
    });
    phoneInput.addEventListener("input", () => formatRussianPhone(phoneInput));
    phoneInput.form?.addEventListener("submit", () => {
        if (phoneInput.value === "+7") phoneInput.value = "";
    });
}

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

for (const flash of document.querySelectorAll(".flash")) {
    window.setTimeout(() => {
        flash.classList.add("is-leaving");
        window.setTimeout(() => flash.remove(), 260);
    }, 6000);
}
