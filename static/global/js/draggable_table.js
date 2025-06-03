document.addEventListener('DOMContentLoaded', function () {
    const container = document.querySelector('.draggable-table')
    let isDown = false
    let startX
    let scrollLeft

    container.addEventListener('mousedown', (e) => {
        isDown = true
        startX = e.pageX - container.offsetLeft
        scrollLeft = container.scrollLeft
        container.style.cursor = 'grabbing' // changes cursor while dragging (🖐️)
        e.preventDefault() // prevents text selection on click
    })

    container.addEventListener('mouseleave', () => {
        isDown = false
        container.style.cursor = 'grab' // returns to normal
    })

    container.addEventListener('mouseup', () => {
        isDown = false
        container.style.cursor = 'grab' // returns to normal
    })

    container.addEventListener('mousemove', (e) => {
        if (!isDown) return
        e.preventDefault()
        const x = e.pageX - container.offsetLeft
        const walk = (x - startX) * 2 // adjust scroll sensibility
        container.scrollLeft = scrollLeft - walk
    })
})