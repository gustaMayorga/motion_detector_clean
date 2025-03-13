/**
 * Panel de Estadísticas del Sistema
 * 
 * Muestra gráficos y métricas sobre el rendimiento y uso del sistema de vigilancia.
 */
class StatisticsPanel {
    /**
     * Inicializa el panel de estadísticas
     * @param {string} containerId ID del contenedor HTML
     * @param {string} apiEndpoint Endpoint de la API para estadísticas
     */
    constructor(containerId, apiEndpoint) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Container with ID ${containerId} not found`);
            return;
        }
        
        this.apiEndpoint = apiEndpoint;
        this.charts = {};
        this.updateInterval = null;
        this.timeRange = 'day'; // 'day', 'week', 'month'
        
        this.initialize();
    }
    
    /**
     * Inicializar componentes de la UI
     */
    initialize() {
        // Crear estructura básica si no existe
        if (!document.getElementById('statistics-container')) {
            this.container.innerHTML = `
                <div class="stats-controls d-flex justify-content-between mb-3">
                    <div class="time-range-controls btn-group">
                        <button class="btn btn-outline-secondary time-range-btn active" data-range="day">Día</button>
                        <button class="btn btn-outline-secondary time-range-btn" data-range="week">Semana</button>
                        <button class="btn btn-outline-secondary time-range-btn" data-range="month">Mes</button>
                    </div>
                    <div class="update-controls">
                        <button id="refresh-stats" class="btn btn-primary">
                            <i class="fas fa-sync-alt"></i> Actualizar
                        </button>
                    </div>
                </div>
                
                <div id="statistics-container">
                    <div class="row">
                        <div class="col-md-6">
                            <div class="card mb-4">
                                <div class="card-header">
                                    <h5 class="card-title">Alertas por Tipo</h5>
                                </div>
                                <div class="card-body">
                                    <canvas id="alerts-by-type-chart"></canvas>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="card mb-4">
                                <div class="card-header">
                                    <h5 class="card-title">Alertas por Hora del Día</h5>
                                </div>
                                <div class="card-body">
                                    <canvas id="alerts-by-hour-chart"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-6">
                            <div class="card mb-4">
                                <div class="card-header">
                                    <h5 class="card-title">Rendimiento del Sistema</h5>
                                </div>
                                <div class="card-body">
                                    <canvas id="system-performance-chart"></canvas>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="card mb-4">
                                <div class="card-header">
                                    <h5 class="card-title">Uso de Almacenamiento</h5>
                                </div>
                                <div class="card-body">
                                    <canvas id="storage-usage-chart"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-12">
                            <div class="card mb-4">
                                <div class="card-header">
                                    <h5 class="card-title">Resumen de Eventos</h5>
                                </div>
                                <div class="card-body">
                                    <div class="table-responsive">
                                        <table class="table table-striped" id="events-summary-table">
                                            <thead>
                                                <tr>
                                                    <th>Tipo de Evento</th>
                                                    <th>Hoy</th>
                                                    <th>Esta Semana</th>
                                                    <th>Este Mes</th>
                                                    <th>Total</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                <tr>
                                                    <td colspan="5" class="text-center">
                                                        <div class="spinner-border spinner-border-sm" role="status">
                                                            <span class="sr-only">Cargando...</span>
                                                        </div>
                                                        Cargando datos...
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // Configurar event listeners
            this.setupEventListeners();
        }
        
        // Cargar datos iniciales
        this.loadStatistics();
        
        // Iniciar actualización automática
        this.startAutoUpdate();
    }
    
    /**
     * Configurar event listeners para controles de la UI
     */
    setupEventListeners() {
        // Botones de rango de tiempo
        const timeRangeButtons = document.querySelectorAll('.time-range-btn');
        timeRangeButtons.forEach(button => {
            button.addEventListener('click', () => {
                // Actualizar clase activa
                timeRangeButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                
                // Cambiar rango de tiempo
                const range = button.getAttribute('data-range');
                this.changeTimeRange(range);
            });
        });
        
        // Botón de actualizar
        const refreshButton = document.getElementById('refresh-stats');
        if (refreshButton) {
            refreshButton.addEventListener('click', () => {
                this.loadStatistics();
            });
        }
    }
    
    /**
     * Cargar estadísticas desde la API
     */
    loadStatistics() {
        // Mostrar indicadores de carga en gráficos
        document.querySelectorAll('canvas').forEach(canvas => {
            canvas.style.opacity = '0.5';
        });
        
        // Mostrar indicador de carga en la tabla
        const tableBody = document.querySelector('#events-summary-table tbody');
        if (tableBody) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center">
                        <div class="spinner-border spinner-border-sm" role="status">
                            <span class="sr-only">Cargando...</span>
                        </div>
                        Cargando datos...
                    </td>
                </tr>
            `;
        }
        
        // Cargar datos desde la API
        fetch(`${this.apiEndpoint}?timeRange=${this.timeRange}`)
            .then(response => response.json())
            .then(data => {
                // Actualizar gráficos con los datos
                this.updateCharts(data);
                
                // Actualizar tabla de resumen
                this.updateEventsSummary(data.eventsSummary);
                
                // Restaurar opacidad de los gráficos
                document.querySelectorAll('canvas').forEach(canvas => {
                    canvas.style.opacity = '1';
                });
            })
            .catch(error => {
                console.error('Error loading statistics:', error);
                
                // Mostrar mensaje de error en la tabla
                if (tableBody) {
                    tableBody.innerHTML = `
                        <tr>
                            <td colspan="5" class="text-center text-danger">
                                <i class="fas fa-exclamation-triangle"></i>
                                Error al cargar estadísticas. Por favor, intente nuevamente.
                            </td>
                        </tr>
                    `;
                }
                
                // Restaurar opacidad de los gráficos
                document.querySelectorAll('canvas').forEach(canvas => {
                    canvas.style.opacity = '1';
                });
            });
    }
    
    /**
     * Cambiar rango de tiempo para las estadísticas
     */
    changeTimeRange(range) {
        if (this.timeRange === range) return;
        
        this.timeRange = range;
        this.loadStatistics();
    }
    
    /**
     * Iniciar actualización automática
     */
    startAutoUpdate() {
        // Detener actualización existente si hay alguna
        this.stopAutoUpdate();
        
        // Actualizar cada 5 minutos
        this.updateInterval = setInterval(() => {
            this.loadStatistics();
        }, 5 * 60 * 1000);
    }
    
    /**
     * Detener actualización automática
     */
    stopAutoUpdate() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }
    
    /**
     * Actualizar gráficos con nuevos datos
     */
    updateCharts(data) {
        // Actualizar o crear gráfico de alertas por tipo
        this.updateAlertsByTypeChart(data.alertsByType);
        
        // Actualizar o crear gráfico de alertas por hora
        this.updateAlertsByHourChart(data.alertsByHour);
        
        // Actualizar o crear gráfico de rendimiento del sistema
        this.updateSystemPerformanceChart(data.systemPerformance);
        
        // Actualizar o crear gráfico de uso de almacenamiento
        this.updateStorageUsageChart(data.storageUsage);
    }
    
    /**
     * Actualizar gráfico de alertas por tipo
     */
    updateAlertsByTypeChart(data) {
        const ctx = document.getElementById('alerts-by-type-chart');
        if (!ctx) return;
        
        // Traducir tipos de alerta
        const typeLabels = {
            'intrusion': 'Intrusión',
            'theft_detected': 'Robo',
            'loitering': 'Merodeo',
            'perimeter_breach': 'Violación de Perímetro',
            'tailgating': 'Acceso No Autorizado'
        };
        
        const labels = data.map(item => typeLabels[item.type] || item.type);
        const values = data.map(item => item.count);
        
        if (this.charts.alertsByType) {
            // Actualizar gráfico existente
            this.charts.alertsByType.data.labels = labels;
            this.charts.alertsByType.data.datasets[0].data = values;
            this.charts.alertsByType.update();
        } else {
            // Crear nuevo gráfico
            this.charts.alertsByType = new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: [
                            '#FF6384',
                            '#36A2EB',
                            '#FFCE56',
                            '#4BC0C0',
                            '#9966FF',
                            '#FF9F40'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    legend: {
                        position: 'right'
                    },
                    title: {
                        display: false
                    }
                }
            });
        }
    }
    
    /**
     * Actualizar gráfico de alertas por hora
     */
    updateAlertsByHourChart(data) {
        const ctx = document.getElementById('alerts-by-hour-chart');
        if (!ctx) return;
        
        // Preparar datos para el gráfico
        const hours = Array.from({ length: 24 }, (_, i) => i);
        const labels = hours.map(hour => `${hour}:00`);
        
        // Convertir datos a formato para el gráfico
        const datasets = [];
        Object.entries(data).forEach(([type, hourlyData]) => {
            // Traducir tipos de alerta
            const typeLabels = {
                'intrusion': 'Intrusión',
                'theft_detected': 'Robo',
                'loitering': 'Merodeo',
                'perimeter_breach': 'Violación de Perímetro',
                'tailgating': 'Acceso No Autorizado'
            };
            
            const typeName = typeLabels[type] || type;
            
            // Crear array de datos por hora
            const hourValues = hours.map(hour => {
                const hourStr = hour.toString();
                return hourlyData[hourStr] || 0;
            });
            
            datasets.push({
                label: typeName,
                data: hourValues,
                borderColor: this.getColorForType(type),
                backgroundColor: this.getColorForType(type, 0.2),
                borderWidth: 2,
                fill: true
            });
        });
        
        if (this.charts.alertsByHour) {
            // Actualizar gráfico existente
            this.charts.alertsByHour.data.labels = labels;
            this.charts.alertsByHour.data.datasets = datasets;
            this.charts.alertsByHour.update();
        } else {
            // Crear nuevo gráfico
            this.charts.alertsByHour = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            title: {
                                display: true,
                                text: 'Hora del día'
                            }
                        },
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Número de alertas'
                            }
                        }
                    }
                }
            });
        }
    }
    
    /**
     * Actualizar gráfico de rendimiento del sistema
     */
    updateSystemPerformanceChart(data) {
        const ctx = document.getElementById('system-performance-chart');
        if (!ctx) return;
        
        const labels = data.timestamps.map(ts => new Date(ts * 1000).toLocaleTimeString());
        
        const datasets = [
            {
                label: 'CPU (%)',
                data: data.cpu,
                borderColor: '#FF6384',
                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                borderWidth: 2,
                fill: true
            },
            {
                label: 'Memoria (%)',
                data: data.memory,
                borderColor: '#36A2EB',
                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                borderWidth: 2,
                fill: true
            }
        ];
        
        if (this.charts.systemPerformance) {
            // Actualizar gráfico existente
            this.charts.systemPerformance.data.labels = labels;
            this.charts.systemPerformance.data.datasets = datasets;
            this.charts.systemPerformance.update();
        } else {
            // Crear nuevo gráfico
            this.charts.systemPerformance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100,
                            title: {
                                display: true,
                                text: 'Utilización (%)'
                            }
                        }
                    }
                }
            });
        }
    }
    
    /**
     * Actualizar gráfico de uso de almacenamiento
     */
    updateStorageUsageChart(data) {
        const ctx = document.getElementById('storage-usage-chart');
        if (!ctx) return;
        
        if (this.charts.storageUsage) {
            // Actualizar gráfico existente
            this.charts.storageUsage.data.datasets[0].data = [
                data.used,
                data.total - data.used
            ];
            this.charts.storageUsage.update();
        } else {
            // Crear nuevo gráfico
            this.charts.storageUsage = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['Utilizado', 'Disponible'],
                    datasets: [{
                        data: [data.used, data.total - data.used],
                        backgroundColor: [
                            '#FF6384',
                            '#36A2EB'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutoutPercentage: 70,
                    legend: {
                        position: 'bottom'
                    },
                    title: {
                        display: false
                    },
                    plugins: {
                        doughnutlabel: {
                            labels: [
                                {
                                    text: `${this.formatStorageSize(data.used)} / ${this.formatStorageSize(data.total)}`,
                                    font: {
                                        size: '16'
                                    }
                                },
                                {
                                    text: `${Math.round(data.used / data.total * 100)}%`,
                                    font: {
                                        size: '24'
                                    }
                                }
                            ]
                        }
                    }
                }
            });
        }
    }
    
    /**
     * Actualizar tabla de resumen de eventos
     */
    updateEventsSummary(data) {
        const tableBody = document.querySelector('#events-summary-table tbody');
        if (!tableBody) return;
        
        // Traducir tipos de evento
        const typeLabels = {
            'intrusion': 'Intrusión',
            'theft_detected': 'Robo',
            'loitering': 'Merodeo',
            'perimeter_breach': 'Violación de Perímetro',
            'tailgating': 'Acceso No Autorizado',
            'suspicious_behavior': 'Comportamiento Sospechoso',
            'object_left': 'Objeto Abandonado',
            'crowd_forming': 'Formación de Multitud'
        };
        
        // Construir filas de la tabla
        let tableHtml = '';
        
        Object.entries(data).forEach(([type, counts]) => {
            const eventType = typeLabels[type] || type;
            
            tableHtml += `
                <tr>
                    <td>${eventType}</td>
                    <td>${counts.today}</td>
                    <td>${counts.week}</td>
                    <td>${counts.month}</td>
                    <td>${counts.total}</td>
                </tr>
            `;
        });
        
        // Agregar fila de totales
        const totals = Object.values(data).reduce((acc, counts) => {
            return {
                today: acc.today + counts.today,
                week: acc.week + counts.week,
                month: acc.month + counts.month,
                total: acc.total + counts.total
            };
        }, { today: 0, week: 0, month: 0, total: 0 });
        
        tableHtml += `
            <tr class="table-active font-weight-bold">
                <td>TOTAL</td>
                <td>${totals.today}</td>
                <td>${totals.week}</td>
                <td>${totals.month}</td>
                <td>${totals.total}</td>
            </tr>
        `;
        
        // Actualizar tabla
        tableBody.innerHTML = tableHtml;
    }
    
    /**
     * Obtener color para un tipo de alerta
     */
    getColorForType(type, alpha = 1) {
        const colors = {
            'intrusion': `rgba(255, 99, 132, ${alpha})`,
            'theft_detected': `rgba(54, 162, 235, ${alpha})`,
            'loitering': `rgba(255, 206, 86, ${alpha})`,
            'perimeter_breach': `rgba(75, 192, 192, ${alpha})`,
            'tailgating': `rgba(153, 102, 255, ${alpha})`,
            'suspicious_behavior': `rgba(255, 159, 64, ${alpha})`,
            'default': `rgba(201, 203, 207, ${alpha})`
        };
        
        return colors[type] || colors.default;
    }
    
    /**
     * Formatear tamaño de almacenamiento
     */
    formatStorageSize(bytes) {
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        if (bytes === 0) return '0 B';
        const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
        return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
    }
    
    /**
     * Limpiar recursos al destruir el componente
     */
    destroy() {
        // Detener actualización automática
        this.stopAutoUpdate();
        
        // Destruir gráficos
        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
        
        this.charts = {};
    }
}

// Exportar para uso en módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { StatisticsPanel };
} 