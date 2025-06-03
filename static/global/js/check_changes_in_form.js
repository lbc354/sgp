document.addEventListener("DOMContentLoaded", function () {
    // get the form element
    const form = document.querySelector("form");

    // get the submit button within the form
    const submitButton = form.querySelector("button[type=submit]");

    // capture the initial state of the form data when the page loads
    const initialFormData = new FormData(form);

    // disable the submit button initially to prevent unnecessary submissions
    submitButton.disabled = true;

    // listen for any input changes within the form
    form.addEventListener("input", function () {
        // get the current state of the form data after input
        const currentFormData = new FormData(form);
        let changed = false;

        // compare each field's current value with the initial value
        for (const [key, value] of currentFormData.entries()) {
            if (value !== initialFormData.get(key)) {
                changed = true; // a change was detected
                break; // exit the loop early for performance
            }
        }

        // enable the submit button only if something has changed
        submitButton.disabled = !changed;
    });
});