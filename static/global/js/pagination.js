document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".page-link").forEach((link) => {
        link.addEventListener("click", function (event) {
            event.preventDefault();

            // gets the current url and the existing parameters
            const url = new URL(window.location.href);
            const params = new URLSearchParams(url.search);

            // updates or adds the 'page' parameter
            params.set("page", this.getAttribute("href").split("=")[1]);

            // updates url in browser without reloading page
            window.location.href = `${url.pathname}?${params.toString()}`;
        });
    });
});