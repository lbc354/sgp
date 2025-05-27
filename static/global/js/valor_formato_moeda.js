// sem R$
// function formatToReais(value) {
//     return new Intl.NumberFormat('pt-BR', {
//         minimumFractionDigits: 2,
//         maximumFractionDigits: 2
//     }).format(value);
// }

// com R$
function formatToBRL(value) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL',
    }).format(value);
}

document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.valor-real').forEach(function (el) {
        const raw = el.dataset.valor;
        if (raw) {
            const num = parseFloat(raw);
            if (!isNaN(num)) {
                el.textContent = formatToBRL(num);
            }
        }
    });
});
