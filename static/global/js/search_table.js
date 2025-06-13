document.addEventListener("DOMContentLoaded", function () {
    const searchForm = document.getElementById("searchForm");

    if (searchForm) {
        searchForm.addEventListener("submit", function (event) {
            event.preventDefault();

            // gets the current url and the existing parameters
            const url = new URL(window.location.href);
            const params = new URLSearchParams(url.search);

            // adds the search field value without deleting existing parameters
            const searchQuery = searchForm.querySelector("input[name='q']").value;
            if (searchQuery) {
                params.set("q", searchQuery);
            } else {
                params.delete("q");
            }

            // updates url in browser
            window.location.href = `${url.pathname}?${params.toString()}`;
        });
    }
});