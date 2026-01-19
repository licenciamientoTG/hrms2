function toggle360Option() {
    const isCuali = document.getElementById('tipoCuali').checked;
    const container360 = document.getElementById('container360');
    const check360 = document.getElementById('check360');

    if (isCuali) {
        // Usamos jQuery para una animación suave si está disponible, si no, CSS display
        if (typeof $ !== 'undefined') {
            $(container360).slideDown(200);
        } else {
            container360.style.display = 'block';
        }
    } else {
        if (typeof $ !== 'undefined') {
            $(container360).slideUp(200);
        } else {
            container360.style.display = 'none';
        }
        check360.checked = false; 
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('initEvalModal');
    
    modal.addEventListener('show.bs.modal', function () {
        const today = new Date();
        const currentYear = today.getFullYear();
        
        // Generar nombre automático: Evaluación [Mes] [Año]
        const monthName = today.toLocaleString('es-ES', { month: 'long' });
        const capitalizedMonth = monthName.charAt(0).toUpperCase() + monthName.slice(1);
        const evalName = `Evaluación ${capitalizedMonth} ${currentYear}`;
        
        document.getElementById('autoEvalName').value = evalName;
        document.getElementById('autoFiscalYear').value = currentYear;
        
        // Asegurarnos que el estado del 360 sea correcto al abrir
        toggle360Option();
    });
});