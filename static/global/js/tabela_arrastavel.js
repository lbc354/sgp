document.addEventListener('DOMContentLoaded', function () {
    const container = document.querySelector('.tabela-container')
    let isDown = false
    let startX
    let scrollLeft

    container.addEventListener('mousedown', (e) => {
        isDown = true
        startX = e.pageX - container.offsetLeft
        scrollLeft = container.scrollLeft
        container.style.cursor = 'grabbing' // Altera cursor enquanto arrasta
        e.preventDefault() // Impede a seleção de texto ao clicar
    })

    container.addEventListener('mouseleave', () => {
        isDown = false
        container.style.cursor = 'grab' // Retorna ao normal
    })

    container.addEventListener('mouseup', () => {
        isDown = false
        container.style.cursor = 'grab' // Retorna ao normal
    })

    container.addEventListener('mousemove', (e) => {
        if (!isDown) return
        e.preventDefault()
        const x = e.pageX - container.offsetLeft
        const walk = (x - startX) * 2 // Ajuste a sensibilidade do scroll
        container.scrollLeft = scrollLeft - walk
    })
})