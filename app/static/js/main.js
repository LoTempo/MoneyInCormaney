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

    if (!typeControls.length || !categorySelects.length) {
        continue;
    }

    const updateCategoryOptions = () => {
        const checkedType = form.querySelector("input[name='type']:checked")?.value;
        if (!checkedType) {
            return;
        }

        for (const select of categorySelects) {
            for (const option of select.options) {
                const optionType = option.dataset.categoryType;
                const allowed = !optionType || optionType === checkedType;
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
    updateCategoryOptions();
}

for (const flash of document.querySelectorAll(".flash")) {
    window.setTimeout(() => {
        flash.classList.add("is-leaving");
        window.setTimeout(() => flash.remove(), 260);
    }, 6000);
}
