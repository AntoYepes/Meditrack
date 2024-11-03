// Script para mostrar/ocultar el menú desplegable
document.querySelector('.user-role').addEventListener('click', function () {
    const dropdown = document.querySelector('.dropdown');
    dropdown.classList.toggle('active');
});
