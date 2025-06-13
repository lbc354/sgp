document.addEventListener('DOMContentLoaded', function () {
    const inputs = document.querySelectorAll('.formatted-currency-value');

    inputs.forEach(input => {
        input.addEventListener('input', function () {
            let value = input.value;

            // removes everything different of number
            value = value.replace(/\D/g, '');

            if (!value) {
                input.value = '';
                return;
            }

            // pads the number with zeros to the left if it has less than 3 digits
            while (value.length < 3) {
                value = '0' + value;
            }

            // separartes integer and decimal parts
            let inteiro = value.slice(0, -2);
            let decimal = value.slice(-2);

            // remove leading zeros from the integer part, but keep 0 if empty
            inteiro = inteiro.replace(/^0+/, '') || '0';

            // apply thousands separator
            inteiro = inteiro.replace(/\B(?=(\d{3})+(?!\d))/g, '.');

            // update formatted value
            input.value = `${inteiro},${decimal}`;
        });
    });
});