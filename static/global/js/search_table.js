document.addEventListener("DOMContentLoaded", function () {
    const searchForm = document.getElementById("searchForm");

    if (searchForm) {
        searchForm.addEventListener("submit", function (event) {
            event.preventDefault();

            // Obtém a URL atual e os parâmetros existentes
            const url = new URL(window.location.href);
            const params = new URLSearchParams(url.search);

            // Adiciona o valor do campo de pesquisa sem apagar os parâmetros existentes
            const searchQuery = searchForm.querySelector("input[name='q']").value;
            if (searchQuery) {
                params.set("q", searchQuery);
            } else {
                params.delete("q");
            }

            // Atualiza a URL no navegador
            window.location.href = `${url.pathname}?${params.toString()}`;
        });
    }
});
