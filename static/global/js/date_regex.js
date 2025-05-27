document.querySelectorAll('.date-input').forEach(input => {
    input.addEventListener('input', function (e) {
        let value = e.target.value;

        // Remove qualquer coisa que não seja número ou barra
        let cleanedValue = value.replace(/[^0-9]/g, '');

        // Verifica se o valor é composto apenas de números
        if (cleanedValue.length > 0) {
            // Começa a formatação, inserindo as barras onde for necessário
            if (cleanedValue.length >= 3 && cleanedValue.length <= 4) {
                // Formatação para dd/mm
                value = cleanedValue.replace(/^(\d{2})(\d{1,2})/, '$1/$2');
            } else if (cleanedValue.length > 4) {
                // Formatação para dd/mm/yyyy
                value = cleanedValue.replace(/^(\d{2})(\d{2})(\d{1,4})/, '$1/$2/$3');
            } else {
                value = cleanedValue;
            }
        }

        // Se a entrada não for numérica, apenas exibe o valor sem alterações
        e.target.value = value;
    });
});