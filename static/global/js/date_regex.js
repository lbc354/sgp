document.querySelectorAll('.date-input').forEach(input => {
    input.addEventListener('input', function (e) {
        let value = e.target.value;

        // removes anything different from number or slash
        let cleanedValue = value.replace(/[^0-9]/g, '');

        // checks if value is composed by numbers only
        if (cleanedValue.length > 0) {
            // starts formatting, inserting slashes where necessary
            if (cleanedValue.length >= 3 && cleanedValue.length <= 4) {
                // format to dd/mm
                value = cleanedValue.replace(/^(\d{2})(\d{1,2})/, '$1/$2');
            } else if (cleanedValue.length > 4) {
                // format to dd/mm/yyyy
                value = cleanedValue.replace(/^(\d{2})(\d{2})(\d{1,4})/, '$1/$2/$3');
            } else {
                value = cleanedValue;
            }
        }

        // if input is not numeric, just displays the value without changes
        e.target.value = value;
    });
});