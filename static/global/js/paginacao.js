document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".page-link").forEach((link) => {
        link.addEventListener("click", function (event) {
            event.preventDefault();

            // Obtem a URL atual e os parâmetros existentes
            const url = new URL(window.location.href);
            const params = new URLSearchParams(url.search);

            // Atualiza ou adiciona o parâmetro 'page'
            params.set("page", this.getAttribute("href").split("=")[1]);

            // Atualiza a URL no navegador sem recarregar a página
            window.location.href = `${url.pathname}?${params.toString()}`;
        });
    });
});